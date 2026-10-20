"""기능 3 — 근거 검사와 등급 규칙(가장 높은 단계 = 등급). LLM 없이 코드만 본다."""
from agent.rating.assess import (
    CriteriaAssessor,
    normalize_items,
    quote_found,
    rating_from_items,
)
from agent.rating.data import ITEMS, load_criteria

CRITERIA = load_criteria()
DESC = "좀비를 총으로 쏘면 피가 튀고 신체가 훼손되는 PC 생존 게임"
CASES = [{"id": "C1", "title": "좀비 서바이벌", "rating": "청소년이용불가", "descriptors": ["폭력성", "공포"],
          "genre": "액션", "platform": "PC/온라인 게임", "summary": "좀비를 처치하는 생존 게임"}]


def _raw(**items) -> dict:
    blank = {"present": False, "level": 0, "evidence": "", "case_ids": []}
    return {name: {**blank, **items.get(name, {})} for name in ITEMS}


def test_rating_is_the_highest_present_level():
    items, _ = normalize_items(_raw(폭력성={"present": True, "level": 1, "evidence": "총으로 쏘면"},
                                    공포={"present": True, "level": 2, "evidence": "좀비"}), DESC, [], CRITERIA)

    assert rating_from_items(items) == "15세이용가"


def test_no_present_item_means_all_ages():
    items, dropped = normalize_items(_raw(), DESC, [], CRITERIA)

    assert rating_from_items(items) == "전체이용가"
    assert dropped == []


def test_quote_allows_spacing_and_punctuation_but_not_invention():
    assert quote_found("피가 튀고", DESC)
    assert quote_found("피가튀고 , 신체가 훼손", DESC)
    assert not quote_found("성인 노출 장면", DESC)
    assert not quote_found("피", DESC)   # 한 글자는 근거로 치지 않는다


def test_invented_evidence_is_dropped_and_does_not_raise_the_rating():
    items, dropped = normalize_items(
        _raw(선정성={"present": True, "level": 3, "evidence": "노출이 심한 의상"}), DESC, [], CRITERIA)

    assert not items["선정성"]["present"]
    assert dropped == [{"item": "선정성", "level": 3, "evidence": "노출이 심한 의상", "case_ids": []}]
    assert rating_from_items(items) == "전체이용가"


def test_case_evidence_counts_only_for_a_retrieved_case_with_that_item():
    items, dropped = normalize_items(
        _raw(공포={"present": True, "level": 2, "evidence": "", "case_ids": ["C1"]},
             약물={"present": True, "level": 2, "evidence": "", "case_ids": ["C1"]},
             범죄={"present": True, "level": 2, "evidence": "", "case_ids": ["NOT-RETRIEVED"]}),
        DESC, CASES, CRITERIA)

    assert items["공포"]["present"] and items["공포"]["case_ids"] == ["C1"]
    assert not items["약물"]["present"]   # C1 에는 약물이 붙지 않았다
    assert not items["범죄"]["present"]   # 검색되지 않은 사례
    assert [d["item"] for d in dropped] == ["약물", "범죄"]


def test_level_zero_of_a_none_item_is_absent_and_broken_values_are_ignored():
    items, dropped = normalize_items(
        {"선정성": {"present": True, "level": 0, "evidence": "좀비"}, "폭력성": {"present": True, "level": 7},
         "공포": "깨진 값"}, DESC, [], CRITERIA)

    assert not items["선정성"]["present"]   # 0단계 = 특기사항 없음
    assert not items["폭력성"]["present"]   # 단계가 범위 밖 → 0, 근거 없음 → 지운다
    assert not items["공포"]["present"]
    assert [d["item"] for d in dropped] == ["폭력성"]


def test_assessor_uses_latest_cases_and_criteria_from_collected():
    class LLM:
        def assess(self, description, criteria, cases):
            self.seen = (criteria, cases)
            return {"described": True, "items": _raw(폭력성={"present": True, "level": 3,
                                                          "evidence": "신체가 훼손되는"})}, {"usd": 0.001}

    llm = LLM()
    collected = [{"source": "cases", "scope": "genre+platform", "data": []},
                 {"source": "criteria", "data": CRITERIA},
                 {"source": "cases", "scope": "platform", "data": CASES}]
    assessment, usage = CriteriaAssessor(llm).assess(DESC, collected)

    assert llm.seen == (CRITERIA, CASES)
    assert assessment["rating"] == "청소년이용불가"
    assert assessment["items"]["폭력성"]["phrase"] == "과도한 폭력 표현"
    assert usage == {"usd": 0.001}


def test_combination_rules_follow_their_definitions():
    from agent.rating.assess import COMBINE_RULES, combine

    quoted = {"폭력성": {"present": True, "level": 1, "evidence": "총으로 쏘면"}}
    thin = {"폭력성": {"present": True, "level": 1, "evidence": "", "case_ids": ["C1"]}}
    near = ["청소년이용불가", "12세이용가", "12세이용가"]

    assert COMBINE_RULES[0] == "items"
    assert combine("12세이용가", quoted, near, "items") == ("12세이용가", "items")
    assert combine("12세이용가", quoted, near, "case-floor") == ("청소년이용불가", "cases")
    assert combine("12세이용가", quoted, near, "thin-nn1") == ("12세이용가", "items")     # 구절 근거가 있다
    assert combine("15세이용가", thin, near, "thin-nn1") == ("청소년이용불가", "cases")
    assert combine("15세이용가", thin, near, "thin-vote5") == ("12세이용가", "cases")      # 다수결은 낮출 수도 있다
    assert combine("15세이용가", thin, near, "thin-floor") == ("청소년이용불가", "cases")
    assert combine("15세이용가", thin, [], "case-floor") == ("15세이용가", "items")       # 사례가 없으면 그대로
