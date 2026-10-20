"""과제 2 — 게임 등급분류 사전 점검 그래프 (docs/03-design.md, 결정 0009).

과제 1 그래프(agent/graph.py)와 같은 뼈대·노드 이름·이벤트 타입을 쓴다.

route → (chat 직행 | review 파이프라인)
review: plan(장르·플랫폼, 조사 task) → research(유사 사례 · 통계 Tool · 기준표 Resource)
        → replan_check(사례가 모자라면 범위를 넓혀 재조사) → analysis(항목별 단계 판정 → 등급)
        → write → validate(반려 시 재작성) → finalize
        정보가 모자라면 plan 이나 analysis 에서 clarify 로 빠져 되묻는다.

부품(SupervisorDeps 의 router·case_retriever·assessor·clarifier·validator)이 모두 None 이면 LLM 단독이다 —
research 할 task 가 없고, analysis 는 quality_llm.rate_direct 가 등급을 바로 답하고, validate 는 형식만 본다.
그 상태가 Before 다.
"""
import asyncio
import json
import time
from functools import partial
from typing import TypedDict

from langgraph.config import get_stream_writer
from langgraph.graph import END, StateGraph
from langsmith import traceable

from ..deps import SupervisorDeps
from .assess import normalize_direct
from .profile import CLARIFY_MARK, description_with_history, extract_profile, follows_clarify

MAX_ATTEMPTS = 3   # 과제 1 과 같다 — 실모델 무한 재작성 방지
MIN_CASES = 3      # 사례가 이보다 적으면 검색 범위를 넓힌다
QUESTIONS = [
    "무엇을 하는 게임인가요? (장르, 플랫폼, 이용자가 하는 일)",
    "폭력 표현이 있나요? 있다면 무기·피·신체 훼손이 어느 정도로 보이나요?",
    "노출이나 성적인 표현이 있나요?",
    "공포·혐오 연출, 욕설·비속어, 술·담배·약물, 범죄 묘사가 있나요?",
    "카지노·슬롯·베팅처럼 도박을 본뜬 요소나 확률형 아이템이 있나요?",
]


class RatingState(TypedDict, total=False):
    query: str
    thread_id: str
    history: list[dict]
    route: str
    description: str        # 판정할 게임 설명 — 되묻기 다음 턴이면 이전 질문과 이어 붙인 것
    profile: dict           # {"genre", "platform"} — 코드로 뽑은 필터
    tasks: list[dict]
    collected: list[dict]
    replan_rounds: int
    retry_count: int
    parallel_elapsed: float
    assessment: dict
    clarify: dict
    draft: str
    validation_attempts: int
    validation_feedback: str
    final: str
    last_prompt: str
    cost_usd: float
    events: list[dict]


def _cost(state: RatingState, usage: dict) -> float:
    return round(state.get("cost_usd", 0.0) + usage.get("usd", 0.0), 6)


@traceable(name="rating.route_node")
async def route_node(state: RatingState, deps: SupervisorDeps) -> dict:
    """제도 문의·잡담(chat)과 점검 요청(review)을 가른다. 직전 답이 되묻기였으면 묻지 않고 review 다."""
    if follows_clarify(state.get("history", [])):
        result, usage = {"route": "review", "method": "clarify-followup"}, {"usd": 0.0}
    elif deps.router is not None:
        result, usage = await deps.router.route(state["query"])
    else:
        result, usage = deps.fast_llm.route(state["query"])
        result = {**result, "method": "llm"}
    event = {"type": "RouteDecided", "route": result["route"],
             **{k: result[k] for k in ("method", "gap") if k in result}}
    return {"route": result["route"], "cost_usd": _cost(state, usage),
            "events": state.get("events", []) + [event]}


@traceable(name="rating.chat_answer_node")
async def chat_answer_node(state: RatingState, deps: SupervisorDeps) -> dict:
    writer = get_stream_writer()
    reply, usage = await deps.fast_llm.chat(
        state["query"], state.get("history", []),
        on_token=lambda piece: writer({"type": "AnswerToken", "delta": piece}))
    return {"final": reply, "last_prompt": usage.get("prompt"), "cost_usd": _cost(state, usage),
            "events": state["events"] + [{"type": "Finalize", "pipeline": "chat-direct"}]}


@traceable(name="rating.plan_node")
async def plan_node(state: RatingState, deps: SupervisorDeps) -> dict:
    """장르·플랫폼은 코드가 뽑고, 켜진 부품에 맞춰 조사 task 를 만든다. LLM 을 부르지 않는다."""
    description = description_with_history(state["query"], state.get("history", []))
    profile = extract_profile(description)
    if deps.clarifier is not None:
        reason = deps.clarifier.check(description)
        if reason:
            event = {"type": "ClarifyRequested", "method": "rule", "reason": reason}
            return {"description": description, "profile": profile, "tasks": [],
                    "clarify": {"reason": reason, "method": "rule"}, "events": state["events"] + [event]}
    tasks = []
    if deps.case_retriever is not None:
        tasks += [{"id": "task-cases", "agent": "research", "kind": "cases", "scope": "genre+platform",
                   "status": "pending"},
                  {"id": "task-stats", "agent": "research", "kind": "stats", "status": "pending"}]
    if deps.assessor is not None:
        tasks.append({"id": "task-criteria", "agent": "research", "kind": "criteria", "status": "pending"})
    event = {"type": "PlanCreated", "task_count": len(tasks), "targets": [t["kind"] for t in tasks], **profile}
    return {"description": description, "profile": profile, "tasks": tasks,
            "events": state["events"] + [event]}


@traceable(name="rating.clarify_node")
async def clarify_node(state: RatingState, deps: SupervisorDeps) -> dict:
    """정보가 모자랄 때 등급을 찍지 않고 되묻는다. LLM 을 부르지 않는다."""
    questions = "\n".join(f"{i}. {q}" for i, q in enumerate(QUESTIONS, 1))
    final = (f"{CLARIFY_MARK} — {state['clarify']['reason']}.\n\n"
             f"아래 질문에 답해 주시면 기준표와 비슷한 실제 사례로 점검하겠습니다.\n\n{questions}")
    return {"final": final, "events": state["events"] + [{"type": "Finalize", "pipeline": "clarify"}]}


async def _run_task(task: dict, state: RatingState, deps: SupervisorDeps) -> dict:
    profile = state.get("profile", {})
    if task["kind"] == "cases":
        cases, scope = await deps.case_retriever.search(
            state["description"], profile.get("genre"), profile.get("platform"), task["scope"])
        return {"source": "cases", "scope": scope, "data": cases}
    if task["kind"] == "stats":
        server = await deps.mcp.find_tool("rating_stats")
        data = await deps.mcp.call_tool(
            "rating_stats", {"genre": profile.get("genre") or "", "platform": profile.get("platform") or ""},
            server=server)
        return {"source": "stats", "data": data}
    server = await deps.mcp.find_resource("criteria://descriptors")
    return {"source": "criteria", "data": json.loads(await deps.mcp.read_resource("criteria://descriptors", server))}


@traceable(name="rating.research_node")
async def research_node(state: RatingState, deps: SupervisorDeps) -> dict:
    tasks = state["tasks"]
    pending = [i for i, t in enumerate(tasks) if t["status"] == "pending"]
    if not pending:
        return {"events": state["events"] + [{"type": "ResearchSkipped", "reason": "pending research task 0개"}]}
    started = time.perf_counter()
    results = await asyncio.gather(*(_run_task(tasks[i], state, deps) for i in pending))
    elapsed = round(time.perf_counter() - started, 2)
    new_tasks = [dict(t) for t in tasks]
    events = list(state["events"])
    for i, result in zip(pending, results, strict=True):
        new_tasks[i]["status"] = "done"
        size = len(result["data"]) if result["source"] == "cases" else None
        events.append({"type": "TaskCompleted", "id": new_tasks[i]["id"], "source": result["source"],
                       **({"scope": result["scope"], "count": size} if size is not None else {})})
    return {"tasks": new_tasks, "collected": state.get("collected", []) + results,
            "parallel_elapsed": elapsed, "events": events}


WIDER = {"genre+platform": "platform", "platform": "all"}


@traceable(name="rating.replan_check_node")
async def replan_check_node(state: RatingState, deps: SupervisorDeps) -> dict:
    """유사 사례가 MIN_CASES 건보다 적으면 검색 범위를 한 단계 넓혀 다시 조사한다(장르+플랫폼 → 플랫폼 → 전체)."""
    rounds = state.get("replan_rounds", 0)
    cases = [c for c in state.get("collected", []) if c["source"] == "cases"]
    wider = WIDER.get(cases[-1]["scope"]) if cases else None
    if not cases or len(cases[-1]["data"]) >= MIN_CASES or wider is None:
        return {"events": state["events"] + [{"type": "ReplanCheck", "round": rounds, "is_sufficient": True}]}
    gap_task = {"id": f"task-cases-{wider}", "agent": "research", "kind": "cases", "scope": wider,
                "status": "pending"}
    verdict = {"type": "ReplanCheck", "round": rounds, "is_sufficient": False, "gap_task": gap_task["id"],
               "found": len(cases[-1]["data"])}
    return {"tasks": state["tasks"] + [gap_task], "replan_rounds": rounds + 1,
            "events": state["events"] + [verdict]}


@traceable(name="rating.analysis_node")
async def analysis_node(state: RatingState, deps: SupervisorDeps) -> dict:
    """항목별 단계 판정 → 등급. assessor 가 없으면 LLM 이 등급을 바로 답한다(Before)."""
    if deps.assessor is not None:
        assessment, usage = deps.assessor.assess(state["description"], state.get("collected", []))
    else:
        raw, usage = deps.quality_llm.rate_direct(state["description"])
        assessment = normalize_direct(raw)
    update = {"assessment": assessment, "cost_usd": _cost(state, usage)}
    event = {"type": "AnalysisCompleted", "method": assessment["method"], "rating": assessment["rating"],
             **({"dropped": len(assessment["dropped"])} if "dropped" in assessment else {})}
    events = state["events"] + [event]
    if deps.clarifier is not None and not assessment.get("described", True):
        reason = "설명만으로는 무엇을 하는 게임인지 알 수 없습니다"
        update["clarify"] = {"reason": reason, "method": "assess"}
        events.append({"type": "ClarifyRequested", "method": "assess", "reason": reason})
    return {**update, "events": events}


@traceable(name="rating.write_node")
async def write_node(state: RatingState, deps: SupervisorDeps) -> dict:
    attempt = state.get("validation_attempts", 0) + 1
    writer = get_stream_writer()
    draft, usage = await deps.quality_llm.write(
        state["query"], state["assessment"], state.get("collected", []), attempt,
        state.get("validation_feedback"),
        on_token=lambda piece: writer({"type": "AnswerToken", "attempt": attempt, "delta": piece}))
    return {"draft": draft, "last_prompt": usage.get("prompt"), "cost_usd": _cost(state, usage),
            "events": state["events"] + [{"type": "DraftWritten", "attempt": attempt, "length": len(draft)}]}


def check_format(draft: str) -> dict:
    """Before 의 검수 — 30자 이상 + "예상 등급:" 줄. 과제 1 base 의 "30자 + 1)" 과 같은 수준이다."""
    ok = len(draft) >= 30 and "예상 등급:" in draft
    reason = None if ok else f"응답이 너무 짧거나 '예상 등급:' 줄이 없습니다({len(draft)}자)"
    return {"ok": ok, "stage": None if ok else "format", "reason": reason, "usage": None,
            "feedback": None if ok else f"{reason}. 첫 줄에 '예상 등급: <등급>'을 쓰고 항목별 근거를 적으세요."}


@traceable(name="rating.validate_node")
async def validate_node(state: RatingState, deps: SupervisorDeps) -> dict:
    """VALIDATOR=grounded 면 사실 대조 검수(deps.validator), 아니면 형식만. 3회째에도 떨어지면 경고를 붙여 내보낸다."""
    draft = state["draft"]
    attempts = state.get("validation_attempts", 0) + 1
    if deps.validator is not None:
        # 질문 대신 판정한 설명을 넘긴다 — 되묻기 다음 턴이면 이전 질문까지 이어 붙인 것이다.
        result = deps.validator.check(state.get("description", state["query"]), state["assessment"],
                                      state.get("collected", []), draft)
    else:
        result = check_format(draft)
    update: dict = {"validation_attempts": attempts}
    if result["usage"]:
        update["cost_usd"] = _cost(state, result["usage"])
    if result["ok"]:
        verdict, feedback = "합격", None
    elif attempts >= MAX_ATTEMPTS:
        verdict, feedback = "합격(최대 시도 도달 — 경고 표시)", None
        update["draft"] = f"⚠️ 검수를 통과하지 못한 답변입니다 — {result['reason']}\n\n{draft}"
    else:
        verdict, feedback = "불합격", result["feedback"]
    event = {"type": "Validation", "attempt": attempts, "verdict": verdict,
             "stage": result["stage"], "reason": result["reason"]}
    return {**update, "validation_feedback": feedback, "events": state["events"] + [event]}


@traceable(name="rating.finalize_node")
async def finalize_node(state: RatingState, deps: SupervisorDeps) -> dict:
    return {"final": state["draft"],
            "events": state["events"] + [{"type": "Finalize", "pipeline": "rating-v2"}]}


def _after_route(state: RatingState) -> str:
    return "chat_answer" if state["route"] == "chat" else "plan"


def _after_plan(state: RatingState) -> str:
    return "clarify" if state.get("clarify") else "research"


def _after_replan_check(state: RatingState) -> str:
    return "analysis" if state["events"][-1].get("is_sufficient") else "research"


def _after_analysis(state: RatingState) -> str:
    return "clarify" if state.get("clarify") else "write"


def _after_validate(state: RatingState) -> str:
    return "finalize" if state.get("validation_feedback") is None else "write"


def build_rating_graph(deps: SupervisorDeps):
    g = StateGraph(RatingState)
    for name, fn in [("route", route_node), ("chat_answer", chat_answer_node), ("plan", plan_node),
                     ("clarify", clarify_node), ("research", research_node),
                     ("replan_check", replan_check_node), ("analysis", analysis_node),
                     ("write", write_node), ("validate", validate_node), ("finalize", finalize_node)]:
        g.add_node(name, partial(fn, deps=deps))   # 과제 1 Wave 13 — 명시적 의존성 주입
    g.set_entry_point("route")
    g.add_conditional_edges("route", _after_route, {"chat_answer": "chat_answer", "plan": "plan"})
    g.add_edge("chat_answer", END)
    g.add_conditional_edges("plan", _after_plan, {"clarify": "clarify", "research": "research"})
    g.add_edge("clarify", END)
    g.add_edge("research", "replan_check")
    g.add_conditional_edges("replan_check", _after_replan_check,
                            {"analysis": "analysis", "research": "research"})
    g.add_conditional_edges("analysis", _after_analysis, {"clarify": "clarify", "write": "write"})
    g.add_edge("write", "validate")
    g.add_conditional_edges("validate", _after_validate, {"finalize": "finalize", "write": "write"})
    g.add_edge("finalize", END)
    return g.compile()
