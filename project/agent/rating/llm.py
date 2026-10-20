"""등급 점검 도메인의 LLM 호출 — fast(분류·대화) / quality(판정·작성·검수) 분리는 과제 1 그대로.

전송(_chat, _chat_stream)과 비용 계산은 agent/ollama_llm.py 의 OllamaLLM 을 그대로 쓰고, 여기에는 프롬프트와
JSON 스키마만 둔다. fake 판은 테스트용 결정론 규칙이다 — 판정 품질의 근거로 쓰지 않는다.
"""
import json
import re

from langsmith import traceable

from ..fake_llm import FakeLLM
from ..ollama_llm import OllamaLLM
from ..validator import JUDGE_SCHEMA, judge_user_message, parse_verdict
from .data import ITEMS, RATINGS
from .facts import render_facts

DISCLAIMER = "※ 참고용 예측이며 실제 등급은 게임물관리위원회 심의로 정해집니다."

ROUTE_SCHEMA = {
    "type": "object",
    "properties": {"route": {"type": "string", "enum": ["chat", "review"]}},
    "required": ["route"],
}
ROUTE_SYSTEM = ("당신은 게임 등급분류 도우미의 라우터다. 사용자가 만들었거나 출시할 특정 게임의 등급을 예상하거나 "
                "점검해 달라고 하면 route=review, 등급분류 제도·절차에 대한 일반 질문이나 인사·잡담이면 route=chat.")
# 소형 모델의 형식 붕괴 대비 — 코드 레벨 폴백 (과제 1 ollama_llm.route 와 같은 생각)
REVIEW_HINT = re.compile(r"몇 ?세|등급.{0,6}(예상|점검|받을|나올|어떻게)|점검해|심의 받")

DIRECT_SCHEMA = {
    "type": "object",
    "properties": {
        "rating": {"type": "string", "enum": RATINGS},
        "descriptors": {"type": "array", "items": {"type": "string", "enum": ITEMS}},
        "reason": {"type": "string"},
    },
    "required": ["rating", "descriptors", "reason"],
}
DIRECT_SYSTEM = ("당신은 한국 게임물 등급분류 전문가다. 게임 설명을 보고 게임물관리위원회가 매길 등급"
                 f"({' · '.join(RATINGS)})과 해당하는 내용정보 항목({' · '.join(ITEMS)})을 예상한다. "
                 "reason 에는 판단 이유를 한국어 한두 문장으로 쓴다.")

ITEM_SCHEMA = {
    "type": "object",
    "properties": {
        "present": {"type": "boolean"},
        "level": {"type": "integer", "enum": [0, 1, 2, 3]},
        "evidence": {"type": "string"},
        "case_ids": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["present", "level", "evidence", "case_ids"],
}
ASSESS_SCHEMA = {
    "type": "object",
    "properties": {
        "described": {"type": "boolean"},
        "items": {"type": "object", "properties": {name: ITEM_SCHEMA for name in ITEMS}, "required": ITEMS},
    },
    "required": ["described", "items"],
}
ASSESS_SYSTEM = (
    "당신은 한국 게임물 등급분류 심사 보조자다. 기준표의 내용정보 7개 항목마다 게임 설명에 그 항목에 해당하는 표현이 "
    "있는지(present)와 단계(level)를 판정한다.\n"
    "- level 은 기준표의 열이다: 0=전체이용가, 1=12세이용가, 2=15세이용가, 3=청소년이용불가 수준의 표현.\n"
    "- 근거는 두 가지만 쓸 수 있다. evidence 에는 게임 설명 속 구절을 바꾸지 않고 그대로 옮긴다. case_ids 에는 "
    "비슷한 실제 사례 중 같은 성격의 게임(같은 시리즈·같은 소재·같은 표현)이고 그 항목이 붙은 사례 번호를 적는다.\n"
    "- 두 근거가 다 없으면 present=false, level=0, evidence=\"\", case_ids=[] 로 둔다. 설명에 없는 표현을 짐작해서 넣지 않는다.\n"
    "- described: 설명에 무엇을 하는 게임인지(내용·표현)가 조금이라도 있으면 true, 장르·플랫폼·요청 문구뿐이면 false."
)

WRITE_SYSTEM = (
    "당신은 게임 등급분류 사전 점검 보고서 작성자다. 주어진 판정 결과와 수집된 사실만 사용해 한국어로 아래 형식을 지킨다.\n"
    "첫 줄: '예상 등급: <판정 결과의 예상 등급 그대로>'\n"
    "1) 항목별 판단 — 판정 결과의 항목 줄을 그대로 옮긴다. 예: '- 폭력성: 사실적인 폭력 표현(15세이용가) — 근거: \"설명 인용\"'. "
    "판정 결과에 없는 항목은 쓰지 않는다. 해당 항목이 없으면 한 줄로 그렇게 쓴다.\n"
    "2) 비슷한 실제 사례 — 사례는 반드시 「제목」(등급 · 내용정보) 형식으로, 수집된 사례 목록에 있는 것만, 등급은 목록 그대로 쓴다.\n"
    "3) 같은 장르·플랫폼 통계 — 수치는 통계에 있는 값만 그대로 쓴다. 통계가 없으면 이 줄을 뺀다.\n"
    "4) 등급을 낮추려면 — 판정 결과의 '등급을 낮추려면' 문장을 그대로 옮기고, 설명에 맞게 한 문장만 덧붙인다.\n"
    f"마지막 줄: '{DISCLAIMER}'\n"
    "판정 결과와 다른 등급을 쓰지 않는다. 등급을 보장하거나 심의를 받지 않아도 된다고 말하지 않는다. "
    "날짜·기간·등급분류번호는 쓰지 않는다."
)

JUDGE_SYSTEM = (
    "당신은 게임 등급분류 사전 점검 보고서 검수자다. 사용자 질문, 판정 결과·수집된 사실, 보고서 초안을 보고 두 가지를 판정한다.\n"
    "relevant: 초안이 사용자가 설명한 그 게임을 점검한 것인가. 다른 게임·다른 장르를 이야기하면 false.\n"
    "faithful: 초안이 판정 결과·수집된 사실과 맞는가. 판정 결과에 없는 항목을 근거로 들거나, 항목의 단계를 다르게 쓰거나, "
    "등급을 보장하거나('반드시 ~받는다'), 등급분류를 받지 않아도 된다는 식으로 사실과 다른 안내를 하면 false.\n"
    "reason 에는 판정 근거를 한국어 한 문장으로 쓴다. 문제가 없으면 둘 다 true 다."
)


LAW_SCHEMA = {
    "type": "object",
    "properties": {
        "kind": {"type": "string", "enum": ["smalltalk", "law"]},
        "answerable": {"type": "boolean"},
        "answer": {"type": "string"},
        "citations": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["kind", "answerable", "answer", "citations"],
}
LAW_SYSTEM = (
    "당신은 게임 등급분류 제도 안내자다. 아래 '조문'만 근거로 한국어로 답한다.\n"
    "- 인사·감사·잡담이면 kind=smalltalk, answerable=false, answer=\"\", citations=[].\n"
    "- 조문에 질문의 답이 있으면 kind=law, answerable=true, answer 에 두세 문장으로 답하고, citations 에 근거 조문의 "
    "key(예: \"게임산업법 제21조\")를 그대로 적는다.\n"
    "- 조문에 답의 일부만 있으면(예: 다른 법률에 맡긴다) 조문에 있는 것만 말하고, 조문에 없는 나이·금액·기간·연락처 같은 "
    "수치나 사실은 쓰지 않는다. 답이 전혀 없으면 kind=law, answerable=false."
)


LAW_JUDGE_SCHEMA = {
    "type": "object",
    "properties": {"supported": {"type": "boolean"}, "reason": {"type": "string"}},
    "required": ["supported", "reason"],
}
LAW_JUDGE_SYSTEM = (
    "당신은 법령 안내의 검수자다. 질문, 인용 조문 원문, 답을 보고 supported 를 판정한다.\n"
    "supported=true: 답의 모든 내용이 인용 조문에 직접 쓰여 있고, 질문이 묻는 대상에 대한 내용이다.\n"
    "supported=false: 조문의 다른 항목·다른 대상의 내용을 질문의 대상에 붙였거나(예: 15세이용가의 기준을 청소년이용불가의 "
    "나이로 씀), 조문에 없는 나이·금액·기간·사실을 덧붙였거나, 조문이 다른 법률에 맡긴 내용을 단정했다.\n"
    "reason 에는 판정 근거를 한국어 한 문장으로 쓴다."
)


def law_user_message(question: str, articles: list[dict]) -> str:
    rows = "\n\n".join(f"[{a['key']}] ({a['title']})\n{a['text']}" for a in articles)
    return f"## 조문\n{rows}\n\n## 질문\n{question}"


def criteria_text(criteria: dict) -> str:
    rows = [f"- {name}: " + " / ".join(f"{lv} {p}" for lv, p in enumerate(phrases))
            for name, phrases in criteria["items"].items()]
    return "단계 0=전체이용가, 1=12세이용가, 2=15세이용가, 3=청소년이용불가\n" + "\n".join(rows)


def cases_text(cases: list[dict]) -> str:
    if not cases:
        return "(비슷한 사례 없음)"
    return "\n".join(f"- [{c['id']}] 「{c['title']}」 {c['rating']} · 내용정보: {', '.join(c['descriptors']) or '없음'}"
                     f" — {c['summary']}" for c in cases)


def write_user_message(query: str, assessment: dict, collected: list[dict], feedback: str | None) -> str:
    user = f"## 사용자 요청\n{query}\n\n{render_facts(assessment, collected)}"
    if feedback:
        user += f"\n\n## 이전 초안에 대한 검증 반려 사유 (반드시 반영)\n{feedback}"
    return user


class OllamaRatingFastLLM(OllamaLLM):
    """분류·제도 안내 대화 (qwen3:0.6b)."""

    def __init__(self, model: str, usd_per_1k_tokens: float, think: bool | None = None,
                 chat_think: bool | None = None):
        super().__init__(model, usd_per_1k_tokens, think)
        self.chat_think = chat_think   # 과제 1 결정 0007 — 대화 경로만 생각을 따로 정한다

    @traceable(run_type="llm", name="ollama_rating_fast.route")
    def route(self, query: str) -> tuple[dict, dict]:
        content, usage = self._chat(ROUTE_SYSTEM, query, schema=ROUTE_SCHEMA)
        try:
            route = json.loads(content).get("route")
        except (json.JSONDecodeError, AttributeError):
            route = None
        if route not in ("chat", "review"):
            route = "review" if REVIEW_HINT.search(query) else "chat"
        return {"route": route, "needs_analysis": False}, usage

    @traceable(run_type="llm", name="ollama_rating_fast.chat")
    async def chat(self, query: str, history: list[dict], on_token=None) -> tuple[str, dict]:
        system = ("당신은 게임 등급분류 제도를 안내하는 간결한 한국어 비서다. 두세 문장으로 답하라. 모르는 수치나 "
                  "절차는 지어내지 말고 게임물관리위원회 안내를 확인하라고 말하라. 특정 게임의 등급을 물으면 게임 내용"
                  "(무엇을 하는 게임인지, 폭력·선정·사행 표현의 수위)을 설명해 달라고 하라.")
        rendered = "\n".join(f"{m['role']}: {m['content']}" for m in history[-10:])
        user = f"## 지금까지의 대화\n{rendered or '(없음)'}\n\n## 사용자의 새 메시지\n{query}"
        return await self._chat_stream(system, user, on_token=on_token, think=self.chat_think)


class OllamaRatingQualityLLM(OllamaLLM):
    """판정·보고서 작성·검수 (qwen3:8b)."""

    @traceable(run_type="llm", name="ollama_rating_quality.rate_direct")
    def rate_direct(self, description: str) -> tuple[dict, dict]:
        """Before(RATING_ASSESSOR=direct) — 기준표·사례 없이 설명만 보고 등급을 바로 답한다."""
        content, usage = self._chat(DIRECT_SYSTEM, f"## 게임 설명\n{description}", schema=DIRECT_SCHEMA)
        try:
            return json.loads(content), usage
        except json.JSONDecodeError:
            return {}, usage

    @traceable(run_type="llm", name="ollama_rating_quality.assess")
    def assess(self, description: str, criteria: dict, cases: list[dict]) -> tuple[dict, dict]:
        user = (f"## 기준표 (내용정보 항목별 단계)\n{criteria_text(criteria)}\n\n"
                f"## 비슷한 실제 사례 (게임물관리위원회 결정)\n{cases_text(cases)}\n\n## 게임 설명\n{description}")
        content, usage = self._chat(ASSESS_SYSTEM, user, schema=ASSESS_SCHEMA)
        try:
            return json.loads(content), usage
        except json.JSONDecodeError:
            return {}, usage

    @traceable(run_type="llm", name="ollama_rating_quality.write")
    async def write(self, query: str, assessment: dict, collected: list[dict], attempt: int,
                    feedback: str | None, on_token=None) -> tuple[str, dict]:
        return await self._chat_stream(WRITE_SYSTEM, write_user_message(query, assessment, collected, feedback),
                                       on_token=on_token, think=self.think)

    @traceable(run_type="llm", name="ollama_rating_quality.answer_law")
    def answer_law(self, question: str, articles: list[dict]) -> tuple[dict, dict]:
        """기능 8 — 검색된 조문만 보고 제도 질문에 답한다. 인용·수치 검사는 law.LawAnswerer 가 한다."""
        content, usage = self._chat(LAW_SYSTEM, law_user_message(question, articles), schema=LAW_SCHEMA)
        try:
            return json.loads(content), usage
        except json.JSONDecodeError:
            return {}, usage

    @traceable(run_type="llm", name="ollama_rating_quality.judge_law")
    def judge_law(self, question: str, articles: list[dict], answer: str) -> tuple[dict, dict]:
        """기능 8 검수 — 답이 인용 조문으로 직접 뒷받침되는가. JSON 이 깨지면 뒷받침되지 않는 것으로 본다(답하지 않는 쪽)."""
        user = f"{law_user_message(question, articles)}\n\n## 답\n{answer}"
        content, usage = self._chat(LAW_JUDGE_SYSTEM, user, schema=LAW_JUDGE_SCHEMA)
        try:
            raw = json.loads(content)
            return {"supported": bool(raw.get("supported")), "reason": str(raw.get("reason", ""))}, usage
        except (json.JSONDecodeError, AttributeError):
            return {"supported": False, "reason": "검수 판정 JSON 을 읽지 못함"}, usage

    @traceable(run_type="llm", name="ollama_rating_quality.judge")
    def judge(self, query: str, facts: str, draft: str) -> tuple[dict, dict]:
        content, usage = self._chat(JUDGE_SYSTEM, judge_user_message(query, facts, draft), schema=JUDGE_SCHEMA)
        return parse_verdict(content), usage


# ── fake — 테스트용 결정론 규칙 ─────────────────────────────────────────────
# 낱말 → (항목, 단계). 설명에 그 낱말이 있으면 그 낱말을 근거로 인용한다.
FAKE_RULES = [("신체", "폭력성", 3), ("피", "폭력성", 2), ("칼", "폭력성", 1), ("총", "폭력성", 1),
              ("수영복", "선정성", 2), ("노출", "선정성", 3), ("욕설", "언어", 2), ("좀비", "공포", 1),
              ("슬롯", "사행성", 2), ("룰렛", "사행성", 2), ("마약", "약물", 3)]


def _fake_items(description: str) -> dict:
    """설명에 낱말이 있으면 그 낱말부터 몇 글자를 근거 구절로 인용한다(한 글자 근거는 근거 검사에서 지워진다)."""
    items = {name: {"present": False, "level": 0, "evidence": "", "case_ids": []} for name in ITEMS}
    for word, name, level in FAKE_RULES:
        at = description.find(word)
        if at >= 0 and level > items[name]["level"]:
            quote = description[at:at + len(word) + 4].strip()
            items[name] = {"present": True, "level": level, "evidence": quote, "case_ids": []}
    return items


class FakeRatingFastLLM(FakeLLM):
    @traceable(run_type="llm", name="fake_rating_fast.route")
    def route(self, query: str) -> tuple[dict, dict]:
        route = "review" if REVIEW_HINT.search(query) else "chat"
        return {"route": route, "needs_analysis": False}, self._usage(query, route)

    @traceable(run_type="llm", name="fake_rating_fast.chat")
    async def chat(self, query: str, history: list[dict], on_token=None) -> tuple[str, dict]:
        reply = "등급분류는 게임물관리위원회가 합니다. 점검할 게임의 내용을 알려 주세요."
        if on_token is not None:
            on_token(reply)
        return reply, self._usage(query, reply)


class FakeRatingQualityLLM(FakeLLM):
    @traceable(run_type="llm", name="fake_rating_quality.rate_direct")
    def rate_direct(self, description: str) -> tuple[dict, dict]:
        items = _fake_items(description)
        level = max((i["level"] for i in items.values() if i["present"]), default=0)
        result = {"rating": RATINGS[level], "descriptors": [n for n, i in items.items() if i["present"]],
                  "reason": "fake 규칙"}
        return result, self._usage(description, str(result))

    @traceable(run_type="llm", name="fake_rating_quality.assess")
    def assess(self, description: str, criteria: dict, cases: list[dict]) -> tuple[dict, dict]:
        result = {"described": len(description.replace(" ", "")) >= 15, "items": _fake_items(description)}
        return result, self._usage(description, str(result))

    @traceable(run_type="llm", name="fake_rating_quality.write")
    async def write(self, query: str, assessment: dict, collected: list[dict], attempt: int,
                    feedback: str | None, on_token=None) -> tuple[str, dict]:
        lines = [f"예상 등급: {assessment['rating']}", "1) 항목별 판단"]
        for name, item in assessment.get("items", {}).items():
            if item["present"]:
                lines.append(f'- {name}: {item["phrase"]}({RATINGS[item["level"]]}) — 근거: "{item["evidence"]}"')
        if len(lines) == 2:
            lines.append("- 해당 항목 없음")
        lines.append(DISCLAIMER)
        draft = "\n".join(lines)
        if on_token is not None:
            on_token(draft)
        return draft, self._usage(query, draft)

    @traceable(run_type="llm", name="fake_rating_quality.answer_law")
    def answer_law(self, question: str, articles: list[dict]) -> tuple[dict, dict]:
        """인사는 smalltalk, 질문에 조문 제목 낱말이 있으면 그 조문을 인용, 아니면 답할 수 없음."""
        if re.search(r"안녕|고마|감사", question):
            result = {"kind": "smalltalk", "answerable": False, "answer": "", "citations": []}
        else:
            hit = next((a for a in articles if a["title"][:2] in question), None)
            result = ({"kind": "law", "answerable": True, "answer": f"{hit['title']}에 관한 규정이 있습니다.",
                       "citations": [hit["key"]]} if hit else
                      {"kind": "law", "answerable": False, "answer": "", "citations": []})
        return result, self._usage(question, str(result))

    @traceable(run_type="llm", name="fake_rating_quality.judge_law")
    def judge_law(self, question: str, articles: list[dict], answer: str) -> tuple[dict, dict]:
        verdict = {"supported": True, "reason": "fake 백엔드 — 판정 생략"}
        return verdict, self._usage(question + answer, str(verdict))

    @traceable(run_type="llm", name="fake_rating_quality.judge")
    def judge(self, query: str, facts: str, draft: str) -> tuple[dict, dict]:
        verdict = {"relevant": True, "faithful": True, "reason": "fake 백엔드 — 판정 생략"}
        return verdict, self._usage(query + facts + draft, str(verdict))
