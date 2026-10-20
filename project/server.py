"""all_total 통합 실습 — FastAPI 백엔드 (Wave 1·3·12·14 축 + 전체 조립).

- Wave 1  : lifespan에서 Agent 번들(MCP 연결·LLM·그래프)을 프로세스당 정확히 1회 생성,
            app.state로 모든 요청이 공유 (creation_count/instance_id로 증명)
- Wave 2  : mcp_server.py를 subprocess(stdio)로 기동해 연결 유지
- Wave 3  : GET /chat/stream — 그래프 실행 과정을 SSE 이벤트로 스트리밍
- Wave 12 : 대화 이력을 SQLite(session.db)에 저장 — 재시작해도 유지
- Wave 14 : SUPERVISOR_VERSION(v1/v2) 환경변수로 legacy/신형 파이프라인 즉시 전환
- LangSmith: 요청당 chat_request 루트 run 아래로 노드·LLM·MCP 호출이 계층 기록됨
"""
import json
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv

load_dotenv()   # LANGCHAIN_TRACING_V2 / API_KEY / PROJECT — import보다 먼저

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from langsmith import traceable
from langsmith.run_helpers import get_current_run_tree
from pydantic import BaseModel

from agent.deps import SupervisorDeps
from agent.fake_llm import FastLLM, QualityLLM
from agent.graph import build_graph
from agent.mcp_client import RATING_SERVER_SCRIPTS, MCPClient
from agent.rating.graph import build_rating_graph
from agent.session_store import SqliteSessionStore
from agent.supervisor_v1 import run_v1

CREATION_COUNT = 0   # Wave 1 — 프로세스 내 Agent 번들 생성 횟수 (항상 1이어야 정상)


class ChatRequest(BaseModel):   # Wave 1 — Pydantic 요청 검증
    message: str
    thread_id: str = "default"


def _parse_think(name: str, value: str) -> bool | None:
    value = value.strip().lower()
    if value == "default":
        return None
    if value in ("true", "false"):
        return value == "true"
    raise ValueError(f"{name} 는 false · true · default 중 하나여야 합니다: {value!r}")


def _ollama_think() -> bool | None:
    """OLLAMA_THINK=false(기본) | true | default — qwen3 의 생각(thinking) 출력.

    default 는 옵션을 보내지 않는 원본 동작이다. 측정에서 원본을 재현할 때 쓴다
    (docs/decisions/0002-ollama-think-control.md).
    """
    return _parse_think("OLLAMA_THINK", os.environ.get("OLLAMA_THINK", "false"))


def _ollama_think_chat(general: bool | None) -> bool | None:
    """OLLAMA_THINK_CHAT=true | false | default — 대화(chat) 경로만 따로 정한다.

    지정하지 않으면 OLLAMA_THINK 가 원본(default)일 때는 원본 그대로, 그 밖에는 true 다.
    대화는 원래 1~2초 경로라 생각을 켜도 비용이 작고, 끄면 답이 어색해진다
    (docs/decisions/0007-chat-keeps-thinking.md).
    """
    value = os.environ.get("OLLAMA_THINK_CHAT")
    if value is None:
        return None if general is None else True
    return _parse_think("OLLAMA_THINK_CHAT", value)


def _domain() -> str:
    """AGENT_DOMAIN=rating(기본, 과제 2 등급 점검) | incident(과제 1 인시던트 대응) — 결정 0009."""
    value = os.environ.get("AGENT_DOMAIN", "rating").strip().lower()
    if value not in ("rating", "incident"):
        raise ValueError(f"AGENT_DOMAIN 은 rating · incident 중 하나여야 합니다: {value!r}")
    return value


def _build_llms(domain: str = "incident"):
    """LLM_BACKEND=fake(기본, 결정론) | ollama(로컬 실모델) | openai(실제 OpenAI API)."""
    backend = os.environ.get("LLM_BACKEND", "fake")
    if domain == "rating":
        return _build_rating_llms(backend)
    if backend == "ollama":
        from agent.ollama_llm import OllamaFastLLM, OllamaQualityLLM
        think = _ollama_think()
        fast = OllamaFastLLM(os.environ.get("OLLAMA_FAST_MODEL", "qwen3:0.6b"),
                             usd_per_1k_tokens=0.00015, think=think,
                             chat_think=_ollama_think_chat(think))
        quality = OllamaQualityLLM(os.environ.get("OLLAMA_QUALITY_MODEL", "qwen3:8b"),
                                   usd_per_1k_tokens=0.005, think=think)
        return backend, fast, quality
    if backend == "openai":
        from agent.openai_llm import OpenAIFastLLM, OpenAIQualityLLM
        fast = OpenAIFastLLM(os.environ.get("OPENAI_FAST_MODEL", "gpt-4o-mini"),
                             usd_per_1k_tokens=0.00015)
        quality = OpenAIQualityLLM(os.environ.get("OPENAI_QUALITY_MODEL", "gpt-4o"),
                                   usd_per_1k_tokens=0.005)
        return backend, fast, quality
    fast = FastLLM("fast-model-stub", usd_per_1k_tokens=0.00015)
    quality = QualityLLM("quality-model-stub", usd_per_1k_tokens=0.005)
    return backend, fast, quality


def _build_rating_llms(backend: str):
    """과제 2 — 프롬프트만 등급 점검용이고 모델·thinking 설정은 과제 1 과 같다."""
    if backend == "openai":
        raise ValueError("AGENT_DOMAIN=rating 은 openai 백엔드를 지원하지 않습니다 — 과금이라 범위 밖(결정 0009)")
    if backend == "ollama":
        from agent.rating.llm import OllamaRatingFastLLM, OllamaRatingQualityLLM
        think = _ollama_think()
        fast = OllamaRatingFastLLM(os.environ.get("OLLAMA_FAST_MODEL", "qwen3:0.6b"),
                                   usd_per_1k_tokens=0.00015, think=think,
                                   chat_think=_ollama_think_chat(think))
        quality = OllamaRatingQualityLLM(os.environ.get("OLLAMA_QUALITY_MODEL", "qwen3:8b"),
                                         usd_per_1k_tokens=0.005, think=think)
        return backend, fast, quality
    from agent.rating.llm import FakeRatingFastLLM, FakeRatingQualityLLM
    return (backend, FakeRatingFastLLM("fast-model-stub", usd_per_1k_tokens=0.00015),
            FakeRatingQualityLLM("quality-model-stub", usd_per_1k_tokens=0.005))


def _switch(name: str, improved: str, base: str, backend: str, allowed: tuple[str, ...]) -> str:
    """개선 스위치 값. 지정이 없으면 ollama 는 개선 쪽, fake·openai 는 base 쪽이 기본이다.

    fake 는 Wave 데모를 결정론으로 재현하는 백엔드이고 openai 는 과금이라 측정 대상이 아니다.
    """
    value = os.environ.get(name, improved if backend == "ollama" else base).strip().lower()
    if value not in allowed:
        raise ValueError(f"{name} 는 {' · '.join(allowed)} 중 하나여야 합니다: {value!r}")
    return value


def _make_embedder():
    from agent.embedding import OllamaEmbedder
    return OllamaEmbedder(os.environ.get("OLLAMA_EMBED_MODEL", "qwen3-embedding:0.6b"))


async def _build_components(backend: str, fast_llm, quality_llm, mcp) -> tuple[dict, dict]:
    """개선 항목의 부품을 스위치대로 만들어 (SupervisorDeps 에 실을 필드, 실제 스위치 값)을 돌려준다.

    끈 부품은 넣지 않는다 — 필드가 None 이면 노드가 base 동작을 한다(docs/03-design.md 공통 원칙).
    """
    ollama = backend == "ollama"
    switches = {"OLLAMA_THINK": os.environ.get("OLLAMA_THINK", "false") if ollama else None,
                # 실제로 쓰는 값 — 지정이 없을 때 OLLAMA_THINK 에 따라 정해지므로 환경변수가 아니라 결과를 적는다
                "OLLAMA_THINK_CHAT": ({None: "default", True: "true", False: "false"}[fast_llm.chat_think]
                                      if ollama else None),
                "ROUTER": _switch("ROUTER", "semantic", "llm", backend, ("semantic", "llm")),
                "TARGET_RESOLVER": _switch("TARGET_RESOLVER", "semantic", "legacy", backend,
                                           ("semantic", "legacy")),
                "VALIDATOR": _switch("VALIDATOR", "grounded", "format", backend,
                                     ("grounded", "format")),
                "RUNBOOK_SELECTOR": _switch("RUNBOOK_SELECTOR", "semantic", "keyword", backend,
                                            ("semantic", "keyword"))}
    parts: dict = {}
    if "semantic" in (switches["ROUTER"], switches["TARGET_RESOLVER"], switches["RUNBOOK_SELECTOR"]):
        parts["embedder"] = _make_embedder()
    if switches["ROUTER"] == "semantic":   # 항목 2
        from agent.router import DEFAULT_MARGIN, LLMRouter, SemanticRouter, load_examples
        parts["router"] = await SemanticRouter.create(
            parts["embedder"], LLMRouter(fast_llm), load_examples(),
            margin=float(os.environ.get("ROUTER_MARGIN", DEFAULT_MARGIN)))
    if switches["TARGET_RESOLVER"] == "semantic":   # 항목 3 — 카탈로그는 MCP Resource 로 받는다
        from agent.target import DEFAULT_MARGIN as TARGET_MARGIN
        from agent.target import DEFAULT_MIN_SCORE, TargetResolver
        catalog_server = await mcp.find_resource("catalog://systems")
        catalog = json.loads(await mcp.read_resource("catalog://systems", server=catalog_server))
        parts["target_resolver"] = await TargetResolver.create(
            parts["embedder"], catalog,
            min_score=float(os.environ.get("TARGET_MIN_SCORE", DEFAULT_MIN_SCORE)),
            margin=float(os.environ.get("TARGET_MARGIN", TARGET_MARGIN)))
    if switches["VALIDATOR"] == "grounded":   # 항목 4 — 판정은 답변을 쓰는 quality 모델이 맡는다
        from agent.validator import GroundedValidator
        parts["validator"] = GroundedValidator(quality_llm)
    if switches["RUNBOOK_SELECTOR"] == "semantic":   # 항목 5
        from agent.runbook import RunbookSelector, load_runbooks
        parts["runbook_selector"] = await RunbookSelector.create(parts["embedder"], load_runbooks())
    return parts, switches


async def _build_rating_components(backend: str, fast_llm, quality_llm, mcp) -> tuple[dict, dict]:
    """과제 2 — 등급 점검 부품을 스위치대로 만든다. 모두 끄면 LLM 단독(Before)이다(결정 0009)."""
    ollama = backend == "ollama"
    switches = {"AGENT_DOMAIN": "rating",
                "OLLAMA_THINK": os.environ.get("OLLAMA_THINK", "false") if ollama else None,
                "OLLAMA_THINK_CHAT": ({None: "default", True: "true", False: "false"}[fast_llm.chat_think]
                                      if ollama else None),
                "ROUTER": _switch("ROUTER", "semantic", "llm", backend, ("semantic", "llm")),
                "RATING_CLARIFY": _switch("RATING_CLARIFY", "rule", "off", backend, ("rule", "off")),
                "CASE_SEARCH": _switch("CASE_SEARCH", "semantic", "off", backend, ("semantic", "off")),
                "RATING_ASSESSOR": _switch("RATING_ASSESSOR", "criteria", "direct", backend,
                                           ("criteria", "direct")),
                "VALIDATOR": _switch("VALIDATOR", "grounded", "format", backend, ("grounded", "format")),
                "CHAT_GROUNDING": _switch("CHAT_GROUNDING", "law", "off", backend, ("law", "off"))}
    parts: dict = {"domain": "rating"}
    if "semantic" in (switches["ROUTER"], switches["CASE_SEARCH"]) or switches["CHAT_GROUNDING"] == "law":
        parts["embedder"] = _make_embedder()
    if switches["ROUTER"] == "semantic":   # 기능 5 — 과제 1 의미 라우터에 등급 점검 예시 문장
        from agent.rating.data import ROUTER_EXAMPLES_PATH, ROUTER_MARGIN
        from agent.router import LLMRouter, SemanticRouter, load_examples
        parts["router"] = await SemanticRouter.create(
            parts["embedder"], LLMRouter(fast_llm), load_examples(ROUTER_EXAMPLES_PATH, "review"),
            margin=float(os.environ.get("ROUTER_MARGIN", ROUTER_MARGIN)), work_label="review")
    if switches["CASE_SEARCH"] == "semantic":   # 기능 3 — 사례 DB 는 MCP Resource 로 받는다
        from agent.rating.cases import CaseRetriever
        cases_server = await mcp.find_resource("ratings://cases")
        cases = json.loads(await mcp.read_resource("ratings://cases", server=cases_server))
        parts["case_retriever"] = await CaseRetriever.create(parts["embedder"], cases)
    if switches["RATING_ASSESSOR"] == "criteria":   # 기능 3 — 판정은 답변을 쓰는 quality 모델이 맡는다
        from agent.rating.assess import CriteriaAssessor
        parts["assessor"] = CriteriaAssessor(quality_llm)
    if switches["RATING_CLARIFY"] == "rule":   # 기능 6
        from agent.rating.clarify import ClarifyRule
        parts["clarifier"] = ClarifyRule()
    if switches["VALIDATOR"] == "grounded":   # 기능 4
        from agent.rating.check import RatingValidator
        parts["validator"] = RatingValidator(quality_llm)
    if switches["CHAT_GROUNDING"] == "law":   # 기능 8 — 조문은 MCP Resource 로 받는다
        from agent.rating.law import LawAnswerer
        law_server = await mcp.find_resource("law://game-industry/articles")
        law = json.loads(await mcp.read_resource("law://game-industry/articles", server=law_server))
        parts["law_answerer"] = await LawAnswerer.create(parts["embedder"], quality_llm, law["articles"])
    return parts, switches


@asynccontextmanager
async def lifespan(app: FastAPI):
    global CREATION_COUNT
    CREATION_COUNT += 1
    domain = _domain()
    mcp = MCPClient(server_scripts=RATING_SERVER_SCRIPTS if domain == "rating" else None)
    await mcp.start()   # Wave 2 — MCP subprocess는 서버 수명 동안 딱 1개
    backend, fast_llm, quality_llm = _build_llms(domain)
    build = _build_rating_components if domain == "rating" else _build_components
    parts, switches = await build(backend, fast_llm, quality_llm, mcp)
    app.state.llm_backend = backend
    app.state.switches = switches
    deps = SupervisorDeps(
        fast_llm=fast_llm,
        quality_llm=quality_llm,
        mcp=mcp,
        session_store=SqliteSessionStore(),
        # 등급 점검은 v2 그래프만 있다 — v1(Wave 14 legacy)은 인시던트 도메인 것이다.
        version=os.environ.get("SUPERVISOR_VERSION", "v2") if domain == "incident" else "v2",
        **parts,
    )
    app.state.deps = deps
    graph_builder = build_rating_graph if domain == "rating" else build_graph
    app.state.graph = graph_builder(deps) if deps.version == "v2" else None
    app.state.instance_id = id(deps)
    yield
    await mcp.stop()
    deps.session_store.close()
    try:   # 종료 전 LangSmith 배치 전송 플러시 — kill 시 run이 pending으로 남는 것 방지
        from langchain_core.tracers.langchain import wait_for_all_tracers
        wait_for_all_tracers()
    except Exception:
        pass


app = FastAPI(lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok", "instance_id": app.state.instance_id,
            "creation_count": CREATION_COUNT,
            "domain": app.state.deps.domain,
            "supervisor_version": app.state.deps.version,
            "llm_backend": app.state.llm_backend,
            "fast_llm": app.state.deps.fast_llm.name,
            "quality_llm": app.state.deps.quality_llm.name,
            "switches": app.state.switches}


@app.get("/version")
async def version():
    return {"supervisor_version": app.state.deps.version}


def _metadata(result: dict, run_id: str | None) -> dict:
    return {
        "route": result.get("route"),
        "task_count": len(result.get("tasks", [])),
        "gate_removed": result.get("gate_removed", 0),
        "replan_rounds": result.get("replan_rounds", 0),
        "retry_count": result.get("retry_count", 0),
        "parallel_elapsed": result.get("parallel_elapsed"),
        "validation_attempts": result.get("validation_attempts", 0),
        "cost_usd": result.get("cost_usd", 0.0),
        "llm_backend": app.state.llm_backend,
        "supervisor_version": app.state.deps.version,
        "instance_id": app.state.instance_id,
        "langsmith_run_id": run_id,
    }


@traceable(name="chat_request")
async def _handle_chat(message: str, thread_id: str) -> tuple[dict, str | None]:
    deps = app.state.deps
    history = deps.session_store.load(thread_id)   # Wave 12
    if deps.version == "v2":
        result = await app.state.graph.ainvoke(
            {"query": message, "thread_id": thread_id, "history": history,
             "events": [], "cost_usd": 0.0})
    else:
        result = await run_v1(deps, message, thread_id, history)   # Wave 14
    deps.session_store.append(thread_id, "user", message)
    deps.session_store.append(thread_id, "assistant", result["final"])
    rt = get_current_run_tree()
    return result, (str(rt.id) if rt else None)


@app.post("/chat")
async def chat(req: ChatRequest):
    result, run_id = await _handle_chat(req.message, req.thread_id)
    return {"reply": result["final"], "events": result.get("events", []),
            "metadata": _metadata(result, run_id)}


@app.get("/chat/stream")
async def chat_stream(message: str, thread_id: str = "default"):
    """Wave 3 — 그래프의 노드별 진행 상황을 SSE로 스트리밍.

    이벤트마다 'data: {json}\\n\\n' 형태로 내려보내고 마지막에 data: [DONE] 센티널을
    보낸다 — 프론트엔드는 \\n\\n 경계로 이벤트를 분리해 파싱해야 한다(Wave 3b).
    """
    deps = app.state.deps

    async def gen():
        history = deps.session_store.load(thread_id)
        if deps.version != "v2":
            result = await run_v1(deps, message, thread_id, history)
            for ev in result["events"]:
                yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'type': 'FinalAnswer', 'reply': result['final']}, ensure_ascii=False)}\n\n"
        else:
            seen = 0
            final = ""
            last_prompt = None   # finalize까지 살아남은 최종 write/chat 호출의 실제 프롬프트
            # stream_mode를 리스트로 주면 (mode, payload) 튜플이 나온다 — "updates"는
            # 노드가 끝날 때마다의 상태 델타, "custom"은 write_node/chat_answer_node가
            # get_stream_writer()로 실행 중에 즉시 흘려보내는 토큰(AnswerToken) 이벤트다.
            async for mode, payload in app.state.graph.astream(
                    {"query": message, "thread_id": thread_id, "history": history,
                     "events": [], "cost_usd": 0.0}, stream_mode=["updates", "custom"]):
                if mode == "custom":
                    yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                    continue
                for node_name, delta in payload.items():
                    for ev in (delta.get("events") or [])[seen:]:
                        ev = {**ev, "node": node_name}
                        yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"
                    if delta.get("events"):
                        seen = len(delta["events"])
                    if delta.get("final"):
                        final = delta["final"]
                    if delta.get("last_prompt"):
                        last_prompt = delta["last_prompt"]
            yield f"data: {json.dumps({'type': 'FinalAnswer', 'reply': final, 'prompt': last_prompt}, ensure_ascii=False)}\n\n"
            deps.session_store.append(thread_id, "user", message)
            deps.session_store.append(thread_id, "assistant", final)
        yield "data: [DONE]\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8100, log_level="warning")
