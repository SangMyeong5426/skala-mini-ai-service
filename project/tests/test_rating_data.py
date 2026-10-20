"""과제 2 데이터의 약속 — 사례 DB 에 평가 기간이 섞이지 않는가, 기준표 모양이 맞는가 (결정 0010).

사례 DB 에 평가 기간(2026-07~09) 결정이 들어가면 평가 게임이 유사 사례로 검색돼 답이 샌다.
"""
import json
from pathlib import Path

from agent.rating.data import (
    CASES_UNTIL,
    EVAL_FROM,
    EVAL_UNTIL,
    EXCLUDED_GENRES,
    EXCLUDED_PLATFORMS,
    ITEMS,
    RATINGS,
    build_cases,
    load_cases,
    load_criteria,
    load_raw,
    usable,
    usable_case,
)


def test_cases_end_before_eval_period():
    cases = load_cases()

    assert cases, "사례 DB 가 비어 있다 — tools/fetch_ratings.py build"
    assert max(c["date"] for c in cases) <= CASES_UNTIL


def test_cases_follow_the_filter():
    for c in load_cases():
        assert c["rating"] in RATINGS
        assert c["platform"] not in EXCLUDED_PLATFORMS
        assert c["genre"] not in EXCLUDED_GENRES
        assert set(c["descriptors"]) <= set(ITEMS)


def test_cases_file_is_rebuilt_from_raw():
    """커밋한 cases.json 이 원자료와 규칙으로 다시 만든 것과 같다 — 손으로 고치지 않았다."""
    assert build_cases(load_raw()) == load_cases()


def test_cases_keep_simplified_decisions_without_summary():
    """간소화 등급분류(개요 없음)를 빼면 모바일 사례가 청소년이용불가로 쏠린다(결정 0017)."""
    mobile = [c for c in load_cases() if c["platform"] == "모바일 게임"]
    no_summary = [c for c in mobile if not c["summary"].strip()]

    assert no_summary, "개요 없는 결정이 사례 DB 에 없다"
    assert sum(c["rating"] == "전체이용가" for c in mobile) > sum(c["rating"] == "청소년이용불가" for c in mobile)


def test_usable_drops_refused_canceled_and_gambling():
    row = {"summary": "검으로 몬스터를 베는 액션 게임", "rating": "12세이용가",
           "platform": "모바일 게임", "genre": "액션", "canceled": False}

    assert usable(row) and usable_case(row)
    assert not usable({**row, "summary": " "}) and usable_case({**row, "summary": " "})
    assert not usable({**row, "rating": "등급거부"})
    assert not usable({**row, "canceled": True})
    assert not usable({**row, "platform": "아케이드 게임"})
    assert not usable({**row, "genre": "보드게임(베팅성)"})


def test_criteria_has_four_levels_per_item():
    criteria = load_criteria()

    assert criteria["levels"] == RATINGS
    assert list(criteria["items"]) == ITEMS
    assert all(len(phrases) == 4 for phrases in criteria["items"].values())


def test_evalset_a_is_outside_the_case_db():
    """평가셋 A 의 게임은 사례 DB 에 없다 — 있으면 자기 자신이 유사 사례로 검색된다."""
    evalset = Path(__file__).resolve().parents[2] / "tools" / "evalsets" / "rating.json"
    items = json.loads(evalset.read_text())
    case_ids = {c["id"] for c in load_cases()}
    raw = {r["id"]: r for r in load_raw()}

    assert len(items) == 40
    for item in items:
        assert item["rateno"] not in case_ids
        assert EVAL_FROM <= raw[item["rateno"]]["date"] <= EVAL_UNTIL
        assert raw[item["rateno"]]["title"] not in item["message"]


def test_evalset_b_labels_come_from_the_api_and_hide_the_conclusion():
    """평가셋 B — 정답은 같은 번호의 API 결정 등급이고, 입력에는 등급·규정 호수(결론)가 남지 않는다."""
    import re

    evalset = Path(__file__).resolve().parents[2] / "tools" / "evalsets" / "rating_detail.json"
    items = json.loads(evalset.read_text())
    raw = {r["id"]: r for r in load_raw()}
    leak = re.compile("|".join([*RATINGS, "이용가", "등급", r"제\s*7\s*조", "따라서"]))

    assert items
    for item in items:
        assert item["label"]["rating"] == raw[item["rateno"]]["rating"]
        assert usable(raw[item["rateno"]])
        assert not leak.search(item["detail"]), item["id"]
