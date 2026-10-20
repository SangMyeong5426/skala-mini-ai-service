"""과제 2 데이터의 약속 — 사례 DB 에 평가 기간이 섞이지 않는가, 기준표 모양이 맞는가 (결정 0010).

사례 DB 에 평가 기간(2026-07~09) 결정이 들어가면 평가 게임이 유사 사례로 검색돼 답이 샌다.
"""
from agent.rating.data import (
    CASES_UNTIL,
    EXCLUDED_GENRES,
    EXCLUDED_PLATFORMS,
    ITEMS,
    RATINGS,
    build_cases,
    load_cases,
    load_criteria,
    load_raw,
    usable,
)


def test_cases_end_before_eval_period():
    cases = load_cases()

    assert cases, "사례 DB 가 비어 있다 — tools/fetch_ratings.py build"
    assert max(c["date"] for c in cases) <= CASES_UNTIL


def test_cases_follow_the_filter():
    for c in load_cases():
        assert c["summary"].strip()
        assert c["rating"] in RATINGS
        assert c["platform"] not in EXCLUDED_PLATFORMS
        assert c["genre"] not in EXCLUDED_GENRES
        assert set(c["descriptors"]) <= set(ITEMS)


def test_cases_file_is_rebuilt_from_raw():
    """커밋한 cases.json 이 원자료와 규칙으로 다시 만든 것과 같다 — 손으로 고치지 않았다."""
    assert build_cases(load_raw()) == load_cases()


def test_usable_drops_refused_canceled_and_gambling():
    row = {"summary": "검으로 몬스터를 베는 액션 게임", "rating": "12세이용가",
           "platform": "모바일 게임", "genre": "액션", "canceled": False}

    assert usable(row)
    assert not usable({**row, "summary": " "})
    assert not usable({**row, "rating": "등급거부"})
    assert not usable({**row, "canceled": True})
    assert not usable({**row, "platform": "아케이드 게임"})
    assert not usable({**row, "genre": "보드게임(베팅성)"})


def test_criteria_has_four_levels_per_item():
    criteria = load_criteria()

    assert criteria["levels"] == RATINGS
    assert list(criteria["items"]) == ITEMS
    assert all(len(phrases) == 4 for phrases in criteria["items"].values())
