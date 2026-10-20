"""기능 4 — 등급 점검 보고서 검수의 코드 단계(형식 → 등급 일치 → 사례 대조 → 수치 대조). LLM 판정은 가짜로 둔다."""
from agent.rating.check import RatingValidator, case_problems, ungrounded_numbers

DESC = "좀비를 총으로 쏘면 피가 튀는 PC 생존 FPS예요. 좀비는 3종류예요"
CASES = [{"id": "C1", "title": "맨 인 더 다크 (Man In The Dark)", "rating": "청소년이용불가",
          "descriptors": ["폭력성"], "genre": "FPS/TPS", "platform": "PC/온라인 게임", "summary": "좀비 소탕 FPS"},
         {"id": "C2", "title": "Plants vs. Zombies: Replanted", "rating": "12세이용가",
          "descriptors": ["폭력성"], "genre": "캐주얼", "platform": "PC/온라인 게임", "summary": "좀비 디펜스"}]
STATS = {"filter": {"genre": "FPS/TPS", "platform": "PC/온라인 게임"}, "total": 53,
         "by_rating": {"전체이용가": 0, "12세이용가": 18, "15세이용가": 6, "청소년이용불가": 29},
         "descriptors": {"폭력성": 52, "선정성": 3, "공포": 3, "언어": 16, "약물": 6, "범죄": 0, "사행성": 2},
         "period": "2024-01-04 ~ 2026-06-25"}
COLLECTED = [{"source": "cases", "scope": "genre+platform", "data": CASES}, {"source": "stats", "data": STATS}]
ASSESSMENT = {"method": "criteria", "rating": "15세이용가", "described": True, "items": {}, "dropped": []}
GOOD = ("예상 등급: 15세이용가\n1) 항목별 판단\n- 폭력성: 사실적인 폭력 표현(15세이용가) — 근거: \"피가 튀는\"\n"
        "2) 비슷한 실제 사례\n- 「맨 인 더 다크」(청소년이용불가 · 폭력성)\n"
        "3) 같은 장르·플랫폼 통계: 사례 53건 중 청소년이용불가 29건, 단계 2\n"
        "※ 참고용 예측이며 실제 등급은 게임물관리위원회 심의로 정해집니다.")


class Judge:
    def __init__(self, ok: bool = True):
        self.ok, self.calls = ok, 0

    def judge(self, query, facts, draft):
        self.calls += 1
        return {"relevant": True, "faithful": self.ok, "reason": "가짜 판정"}, {"usd": 0.002}


def test_good_report_passes_all_code_stages_and_reaches_the_judge():
    judge = Judge()
    result = RatingValidator(judge).check(DESC, ASSESSMENT, COLLECTED, GOOD)

    assert result["ok"] and judge.calls == 1


def test_stages_fail_in_order_and_skip_the_judge():
    judge = Judge()
    v = RatingValidator(judge)

    assert v.check(DESC, ASSESSMENT, COLLECTED, "15세쯤 됩니다")["stage"] == "format"
    assert v.check(DESC, ASSESSMENT, COLLECTED, GOOD.replace("15세이용가\n1)", "12세이용가\n1)"))["stage"] == "rating"
    assert v.check(DESC, ASSESSMENT, COLLECTED, GOOD.replace("맨 인 더 다크", "없는 게임"))["stage"] == "cases"
    assert v.check(DESC, ASSESSMENT, COLLECTED, GOOD.replace("29건", "40건"))["stage"] == "numbers"
    assert judge.calls == 0


def test_judge_rejection_carries_feedback_and_cost():
    result = RatingValidator(Judge(ok=False)).check(DESC, ASSESSMENT, COLLECTED, GOOD)

    assert result["stage"] == "judge"
    assert "다시 쓰세요" in result["feedback"]
    assert result["usage"] == {"usd": 0.002}


def test_case_titles_match_loosely_but_ratings_must_match():
    assert case_problems("「맨 인 더 다크 (Man In The Dark)」(청소년이용불가)", CASES) == []
    assert case_problems("「plants vs zombies replanted」(12세이용가)", CASES) == []
    assert case_problems("「맨 인 더 다크」(15세이용가 · 폭력성)", CASES) == [
        "「맨 인 더 다크」의 실제 등급은 청소년이용불가인데 15세이용가(이)라고 썼습니다"]


def test_numbers_from_titles_quotes_and_levels_are_not_counted():
    draft = '「Plants vs. Zombies: Replanted」(12세이용가) 근거: "좀비는 3종류" 단계 2, 53건 중 18건'

    assert ungrounded_numbers(draft, COLLECTED, DESC) == []
    assert ungrounded_numbers("사례 9건", COLLECTED, DESC) == ["9"]
    assert ungrounded_numbers("2024년 사례", COLLECTED, DESC) == ["2024"]   # 결정일 범위는 근거가 아니다
