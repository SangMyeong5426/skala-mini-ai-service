"""기능 4 — 등급 점검 보고서 검수. 과제 1 검수(agent/validator.py)처럼 싼 것부터 보고, 앞에서 떨어지면 뒤는 부르지 않는다.

  ① 형식      30자 이상 + "예상 등급: <등급>" 줄                                (코드, 비용 0)
  ② 등급 일치  보고서의 예상 등급 = 코드가 계산한 등급                              (코드)
  ③ 사례 대조  「제목」으로 든 사례가 검색된 사례이고, 괄호 속 등급이 실제와 같은가    (코드)
  ④ 수치 대조  보고서의 수치가 통계 Tool 결과 · 사례 수 · 게임 설명에 있는가          (코드)
  ⑤ LLM 판정  설명한 그 게임을 점검했는가 · 판정 결과와 맞는가 · 단정·잘못된 안내가 없는가 (quality 모델 1회)

①~④는 "다른 등급을 썼다", "없는 사례·등급·수치를 지어냈다"를 잡는다. 판정에 없는 항목을 근거로 들거나 다른 게임을
이야기하거나 등급을 보장하는 것은 글의 뜻이라 ⑤의 몫이다.
"""
import re

from langsmith import traceable

from ..validator import LIST_MARKER, NUMBER
from .data import ITEMS, RATINGS
from .facts import latest, render_facts

RATING_LINE = re.compile(r"예상 등급\s*[:：]\s*(" + "|".join(RATINGS) + ")")
CITED = re.compile(r"「([^」]+)」\s*(?:\(([^)]*)\))?")
QUOTED = re.compile(r'"[^"\n]*"')
# 등급분류번호(예: CC-OM-240201-001, GC-CC-NP-251031-001) — 사례를 가리키는 번호라 수치가 아니다.
CASE_ID = re.compile(r"[A-Z]{2}(?:-[A-Z]{2}){1,2}-\d{6}-\d{3}")
LEVEL = re.compile(r"단계\s*\d")
# 등급 이름(12세·15세)과 청소년 기준 나이(만 18세 · 19세), 내용정보 항목 수는 수치 근거 없이도 쓴다.
ALWAYS_ALLOWED = {12.0, 15.0, 18.0, 19.0, float(len(ITEMS))}


def _norm_title(title: str) -> str:
    return re.sub(r"[\W_]+", "", title).casefold()


def stated_rating(draft: str) -> str | None:
    found = RATING_LINE.search(draft)
    return found.group(1) if found else None


def case_problems(draft: str, cases: list[dict]) -> list[str]:
    """「제목」(등급 …) 으로 든 사례마다 — 검색된 사례인가, 괄호 속 등급이 실제와 같은가.

    제목은 띄어쓰기·문장부호·대소문자를 무시하고, 줄여 쓴 제목(3글자 이상)이 검색된 제목에 들어 있으면 같은 사례로 본다.
    """
    titles = [(_norm_title(c["title"]), c) for c in cases]
    problems = []
    for title, paren in CITED.findall(draft):
        key = _norm_title(title)
        case = next((c for t, c in titles if t == key or (len(key) >= 3 and key in t)), None)
        if case is None:
            problems.append(f"검색되지 않은 사례 「{title}」를 들었습니다")
            continue
        said = next((r for r in RATINGS if r in (paren or "")), None)
        if said and said != case["rating"]:
            problems.append(f"「{title}」의 실제 등급은 {case['rating']}인데 {said}(이)라고 썼습니다")
    return problems


def ungrounded_numbers(draft: str, collected: list[dict], description: str) -> list[str]:
    """보고서의 수치 중 통계 Tool 결과·사례 수·게임 설명 어디에도 없는 것.

    사례 제목·괄호(③이 본다), 따옴표 속 설명 인용(근거 검사가 본다), 등급분류번호, "단계 N", 목록 번호 "1)"은
    수치로 보지 않는다.
    통계의 결정일 범위는 근거에서 뺀다 — 날짜 숫자가 지어낸 작은 수치를 덮어 주지 않게.
    """
    allowed = set(ALWAYS_ALLOWED) | {float(n) for n in NUMBER.findall(description)}
    stats = latest(collected, "stats")
    if stats:
        allowed |= {float(stats["total"]), *map(float, stats["by_rating"].values()),
                    *map(float, stats["descriptors"].values())}
    allowed.add(float(len(latest(collected, "cases") or [])))
    text = LEVEL.sub(" ", CASE_ID.sub(" ", QUOTED.sub(" ", CITED.sub(" ", draft))))
    unknown: list[str] = []
    for token in NUMBER.findall(LIST_MARKER.sub(" ", text)):
        if float(token) not in allowed and token not in unknown:
            unknown.append(token)
    return unknown


def _fail(stage: str, reason: str, feedback: str, usage: dict | None = None) -> dict:
    return {"ok": False, "stage": stage, "reason": reason, "feedback": f"{reason}. {feedback}", "usage": usage}


class RatingValidator:
    """VALIDATOR=grounded (AGENT_DOMAIN=rating)."""

    def __init__(self, judge_llm):
        self.judge_llm = judge_llm   # judge(query, facts, draft) -> (verdict, usage) 를 가진 quality 모델

    @traceable(name="rating_validator.check")
    def check(self, description: str, assessment: dict, collected: list[dict], draft: str) -> dict:
        """{"ok", "stage", "reason", "feedback", "usage"} — stage 는 떨어진 단계(format·rating·cases·numbers·judge)."""
        said = stated_rating(draft)
        if len(draft) < 30 or said is None:
            return _fail("format", f"'예상 등급:' 줄이 없거나 응답이 너무 짧습니다({len(draft)}자)",
                         "첫 줄에 '예상 등급: <등급>'을 쓰고 항목별 근거를 적으세요.")
        if said != assessment["rating"]:
            return _fail("rating", f"판정 결과는 {assessment['rating']}인데 보고서는 {said}라고 썼습니다",
                         "예상 등급은 판정 결과를 그대로 쓰세요.")
        problems = case_problems(draft, latest(collected, "cases") or [])
        if problems:
            return _fail("cases", "; ".join(problems),
                         "사례는 수집된 사례 목록에 있는 것만, 「제목」(등급 · 내용정보) 형식으로 목록 그대로 쓰세요.")
        unknown = ungrounded_numbers(draft, collected, description)
        if unknown:
            return _fail("numbers", f"수집된 통계에 없는 수치를 썼습니다: {', '.join(unknown)}",
                         "수치는 통계에 있는 값만 그대로 쓰세요.")
        verdict, usage = self.judge_llm.judge(description, render_facts(assessment, collected), draft)
        if verdict["relevant"] and verdict["faithful"]:
            return {"ok": True, "stage": None, "reason": None, "feedback": None, "usage": usage}
        what = "설명한 게임과 관련 없는 보고서" if not verdict["relevant"] else "판정 결과·사실과 맞지 않는 내용"
        return _fail("judge", f"{what} — {verdict['reason']}",
                     "사용자가 설명한 게임에 대해, 판정 결과와 어긋나지 않게 다시 쓰세요.", usage)
