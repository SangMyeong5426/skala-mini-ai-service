"""항목 4 — 답변 검수(validate)에 근거 검증을 더한다.

base 검수는 "30자 이상 + '1)' 포함"만 본다. 그래서 수치를 지어내거나, 질문과 무관한 시스템을 진단하거나,
degraded 를 정상이라고 결론 내린 초안도 모두 통과했다(오염 초안 7종 탐지 0/7). 세 겹으로 본다 — 싼 것부터,
앞에서 떨어지면 뒤는 부르지 않는다.

  ① 형식      30자 이상 + "1)"                          (base 그대로, 비용 0)
  ② 수치 대조  초안의 수치가 수집된 사실·질문에 있는가     (코드, 비용 0, 결정론)
  ③ LLM 판정  질문과 관련 있는가 · 사실과 맞는가          (quality 모델 1회)

②는 지어낸 수치(b2·b3·b4)를 잡지만, 수치는 맞고 판단이 틀린 경우(질문 무관 b1·b5, 결론 왜곡 b6,
지표 바꿔치기 b7)는 못 잡는다 — 그것이 ③의 몫이다.
"""
import json
import re

from langsmith import traceable

NUMBER = re.compile(r"\d+(?:\.\d+)?")
LIST_MARKER = re.compile(r"(?<![\d.])\d\)")   # 번호 절차 표시 "1)" "2)" — 인용 수치가 아니다

JUDGE_SYSTEM = (
    "당신은 ICT 운영 대응 보고서 검수자다. 사용자 질문, 에이전트가 수집한 사실, 답변 초안을 보고 "
    "두 가지를 판정한다.\n"
    "relevant: 초안이 사용자 질문에 대한 답인가. 질문이 지금 일어난 장애 신고가 아닌데(개념 설명 요청, "
    "잡담 등) 시스템 진단을 내놓았거나, 질문이 가리킨 것과 다른 시스템을 진단했으면 false.\n"
    "faithful: 초안의 수치·상태·결론이 수집된 사실과 맞는가. 수치를 다른 지표에 붙였거나(예: 메모리 "
    "값을 CPU라고 씀), 상태가 degraded인데 정상이라고 하거나, 알림·임계치를 넘었는데 조치가 필요 없다고 "
    "결론 내리면 false.\n"
    "reason에는 판정 근거를 한국어 한 문장으로 쓴다. 문제가 없으면 둘 다 true다."
)
JUDGE_SCHEMA = {
    "type": "object",
    "properties": {"relevant": {"type": "boolean"}, "faithful": {"type": "boolean"},
                   "reason": {"type": "string"}},
    "required": ["relevant", "faithful", "reason"],
}
JUDGE_JSON_INSTRUCTIONS = (
    'JSON 객체로만 응답하라. 스키마: {"relevant": boolean, "faithful": boolean, "reason": string}'
)


def render_facts(collected: list[dict]) -> str:
    """write 프롬프트와 같은 모양으로 수집 사실을 적는다 — 작성자와 판정자가 같은 사실을 본다."""
    facts = []
    for c in collected:
        if c["source"] == "monitoring":
            d = c["data"]
            facts.append(f"- 모니터링 {d['system_name']}: 상태={d['status']}, "
                         f"CPU {d['cpu_percent']}%, 메모리 {d['memory_percent']}%, "
                         f"알림 {len(d['alerts'])}건 {d['alerts']}")
        elif c["source"] == "runbook":
            facts.append(f"- runbook 발췌:\n{c['data'].strip()}")
        elif c["source"] == "analysis":
            facts.append(f"- 패턴 분석: {c['data'].strip()}")
    return "\n".join(facts) or "(수집된 사실 없음)"


def judge_user_message(query: str, facts: str, draft: str) -> str:
    return f"## 사용자 질문\n{query}\n\n## 수집된 사실\n{facts}\n\n## 답변 초안\n{draft}"


def parse_verdict(content: str) -> dict:
    """판정 JSON 을 읽는다. 깨졌으면 통과로 둔다 — 판정기 고장으로 답변을 막지 않는다(한계로 기록)."""
    try:
        raw = json.loads(content)
        return {"relevant": bool(raw.get("relevant", True)),
                "faithful": bool(raw.get("faithful", True)),
                "reason": str(raw.get("reason", ""))}
    except (json.JSONDecodeError, AttributeError):
        return {"relevant": True, "faithful": True, "reason": "판정 JSON 을 읽지 못해 통과 처리"}


def ungrounded_numbers(draft: str, collected: list[dict], query: str = "") -> list[str]:
    """초안에 나온 수치 중 수집된 사실(모니터링 값·알림 문구·runbook·분석)과 질문 어디에도 없는 것.

    마지막 확인 시각(last_checked)은 근거에서 뺀다 — 날짜 숫자가 지어낸 수치를 덮어 주지 않게.
    알림 개수와 조사한 시스템 수는 근거로 친다("알림 2건", "2개 시스템").
    """
    evidence = [query]
    monitoring = [c["data"] for c in collected if c["source"] == "monitoring"]
    for d in monitoring:
        evidence += [d["system_name"], str(d["cpu_percent"]), str(d["memory_percent"]),
                     str(len(d["alerts"])), *d["alerts"]]
    evidence += [str(c["data"]) for c in collected if c["source"] != "monitoring"]
    evidence.append(str(len(monitoring)))
    allowed = {float(n) for n in NUMBER.findall(" ".join(evidence))}

    unknown: list[str] = []
    for token in NUMBER.findall(LIST_MARKER.sub(" ", draft)):
        if float(token) not in allowed and token not in unknown:
            unknown.append(token)
    return unknown


class GroundedValidator:
    def __init__(self, judge_llm):
        self.judge_llm = judge_llm   # judge(query, facts, draft) -> (verdict, usage) 를 가진 quality 모델

    @traceable(name="grounded_validator.check")
    def check(self, query: str, collected: list[dict], draft: str) -> dict:
        """{"ok", "stage", "reason", "feedback", "usage"} — stage 는 떨어진 단계(format·numbers·judge)."""
        if len(draft) < 30 or "1)" not in draft:
            return {"ok": False, "stage": "format", "usage": None,
                    "reason": f"응답이 너무 짧거나 번호 절차가 없습니다({len(draft)}자)",
                    "feedback": f"응답이 너무 짧습니다({len(draft)}자, 최소 30자). 절차를 "
                                f"1) 2) 3) 번호로 구체적으로 설명하세요."}

        unknown = ungrounded_numbers(draft, collected, query)
        if unknown:
            reason = f"수집된 사실에 없는 수치를 인용했습니다: {', '.join(unknown)}"
            return {"ok": False, "stage": "numbers", "usage": None, "reason": reason,
                    "feedback": f"{reason}. 수치는 수집된 사실에 있는 값만 그대로 인용하세요."}

        verdict, usage = self.judge_llm.judge(query, render_facts(collected), draft)
        if verdict["relevant"] and verdict["faithful"]:
            return {"ok": True, "stage": None, "reason": None, "feedback": None, "usage": usage}
        what = "질문과 관련 없는 답변" if not verdict["relevant"] else "수집된 사실과 맞지 않는 내용"
        reason = f"{what} — {verdict['reason']}"
        return {"ok": False, "stage": "judge", "usage": usage, "reason": reason,
                "feedback": f"{reason}. 사용자 질문에 맞게, 수집된 사실과 어긋나지 않게 다시 쓰세요."}
