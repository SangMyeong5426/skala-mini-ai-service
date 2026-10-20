"""기능 3 — 항목별 단계 판정과 등급 규칙. 판정 결과를 정리한다.

LLM(quality)은 기준표·유사 사례를 보고 내용정보 7항목마다 단계(0~3)와 근거를 낸다. 코드는 두 가지를 한다.

  1. 근거 검사 — 근거는 "게임 설명 속 구절"이나 "검색된 사례 중 그 항목이 붙은 사례"만 인정한다.
     둘 다 아니면 그 항목을 지운다(dropped). 지어낸 근거로 등급이 오르는 것을 막는다.
  2. 등급 계산 — 해당 항목 단계의 최댓값이 등급이다(0 전체이용가 … 3 청소년이용불가). LLM 에게 등급을 묻지 않는다.

등급이 가장 높은 항목 하나로 정해지므로 한 항목의 과대평가가 곧 전체 과대평가다 — 그래서 항목을 나눠 따로
심사하지 않고(결정 0009) 근거 없는 항목을 지운다.

method=direct 는 Before(LLM 단독) — rate_direct 가 등급을 바로 답한 것을 같은 모양으로 맞춘다.
"""
import re

from langsmith import traceable

from .data import ITEMS, RATINGS
from .facts import latest

MIN_OVERLAP = 0.8   # 인용이 조사·띄어쓰기만 다를 때를 허용하는 2글자 조각 겹침 비율


def _norm(text: str) -> str:
    """띄어쓰기·문장부호를 지운다 — 한글·영문·숫자만 남긴다."""
    return re.sub(r"[\W_]+", "", text)


def _bigrams(text: str) -> set[str]:
    return {text[i:i + 2] for i in range(len(text) - 1)}


def quote_found(evidence: str, description: str) -> bool:
    """근거 구절이 설명에 있는가. 그대로 있거나, 2글자 조각의 MIN_OVERLAP 이상이 설명에 있으면 있다고 본다."""
    e, d = _norm(evidence), _norm(description)
    if len(e) < 2:
        return False
    if e in d:
        return True
    pieces = _bigrams(e)
    return len(pieces & _bigrams(d)) / len(pieces) >= MIN_OVERLAP


def normalize_items(raw_items: dict, description: str, cases: list[dict],
                    criteria: dict) -> tuple[dict, list[dict]]:
    """LLM 이 낸 항목 판정 → (항목별 판정, 지운 항목). 모양이 깨진 값은 '해당 없음'으로 둔다."""
    by_id = {c["id"]: c for c in cases}
    raw_items = raw_items if isinstance(raw_items, dict) else {}
    items, dropped = {}, []
    for name in ITEMS:
        raw = raw_items.get(name) if isinstance(raw_items.get(name), dict) else {}
        level = raw.get("level") if isinstance(raw.get("level"), int) and 0 <= raw.get("level") <= 3 else 0
        evidence = str(raw.get("evidence") or "").strip()
        case_ids = [c for c in raw.get("case_ids") or [] if isinstance(c, str)]
        present = bool(raw.get("present"))
        if present and level == 0 and criteria["items"][name][0] == "특기사항 없음":
            present = False   # 0단계가 '특기사항 없음'인 항목은 0단계면 해당 없음이다
        quote_ok = present and quote_found(evidence, description)
        cases_ok = [cid for cid in case_ids if cid in by_id and name in by_id[cid]["descriptors"]] if present else []
        if present and not quote_ok and not cases_ok:
            dropped.append({"item": name, "level": level, "evidence": evidence, "case_ids": case_ids})
            present = False
        items[name] = {"present": present, "level": level if present else 0,
                       "phrase": criteria["items"][name][level] if present else None,
                       "evidence": evidence if quote_ok else "", "case_ids": cases_ok}
    return items, dropped


def rating_from_items(items: dict) -> str:
    """해당 항목 단계의 최댓값 → 등급. 해당 항목이 없으면 전체이용가."""
    return RATINGS[max((item["level"] for item in items.values() if item["present"]), default=0)]


# 결합 규칙 — 기준표 판정(항목 단계 최댓값)과 비슷한 사례의 등급을 어떻게 합칠까(결정 0016).
# 한 문장 개요에서는 사례 1건 기준선이, 상세 설명에서는 기준표 판정이 강했다(결정 0011). 후보는 결과를 보기 전에 정했고,
# 평가셋 A 와 겹치지 않는 개발용 문항(tools/evalsets/rating_dev.json)으로 골랐다(tools/choose_combination.py).
#   items       R0 지금 방식 — 항목 단계 최댓값
#   case-floor  R1 사례를 하한으로 — R0 와 가장 가까운 사례 등급 중 높은 쪽
#   thin-nn1    R2 얇으면 사례 1건 — 설명 구절 근거가 있는 항목이 없으면 가장 가까운 사례의 등급
#   thin-vote5  R3 얇으면 사례 다수결 — R2 와 같되 사례 5건 다수결(동률이면 더 가까운 쪽)
#   thin-floor  R4 얇으면 사례를 하한으로 — 설명 구절 근거가 없을 때만 R1
COMBINE_RULES = ("items", "case-floor", "thin-nn1", "thin-vote5", "thin-floor")
# 개발용 38문항(runs/choose-combination_20261020-182207.json): R0 14 · R1 18 · R2 17 · R3 17 · R4 16 — 정답이 가장 많은 R1.
# 과소평가 21 → 11, 과대평가 2 → 8. 상세 설명에도 적용되는 규칙이라 평가셋 B 에서 처음 확인한다.
COMBINE_RULE = "case-floor"


def has_quote(items: dict) -> bool:
    """설명 속 구절을 근거로 든 항목이 있는가 — 없으면 '얇은 설명'으로 본다."""
    return any(item["present"] and item["evidence"] for item in items.values())


def vote(case_ratings: list[str]) -> str:
    counts = {r: case_ratings.count(r) for r in case_ratings}
    top = max(counts.values())
    return next(r for r in case_ratings if counts[r] == top)


def combine(items_rating: str, items: dict, case_ratings: list[str], rule: str = COMBINE_RULE) -> tuple[str, str]:
    """(최종 등급, 어디서 왔나 — "items" 또는 "cases"). case_ratings 는 가까운 순서의 사례 등급."""
    if rule == "items" or not case_ratings:
        return items_rating, "items"
    nn1 = case_ratings[0]
    higher = max(items_rating, nn1, key=RATINGS.index)
    thin = not has_quote(items)
    rating = {"case-floor": higher,
              "thin-nn1": nn1 if thin else items_rating,
              "thin-vote5": vote(case_ratings) if thin else items_rating,
              "thin-floor": higher if thin else items_rating}[rule]
    return rating, "items" if rating == items_rating else "cases"


class CriteriaAssessor:
    """RATING_ASSESSOR=criteria — 기준표·유사 사례로 항목별 단계를 판정하고 등급은 코드가 계산한다."""

    def __init__(self, llm):
        self.llm = llm   # assess(description, criteria, cases) -> (raw, usage) 를 가진 quality 모델

    @traceable(name="criteria_assessor.assess")
    def assess(self, description: str, collected: list[dict]) -> tuple[dict, dict]:
        criteria = latest(collected, "criteria")
        cases = latest(collected, "cases") or []
        raw, usage = self.llm.assess(description, criteria, cases)
        items, dropped = normalize_items(raw.get("items", {}), description, cases, criteria)
        items_rating = rating_from_items(items)
        rating, source = combine(items_rating, items, [c["rating"] for c in cases])
        nearest = {"title": cases[0]["title"], "rating": cases[0]["rating"]} if cases else None
        return {"method": "criteria", "rating": rating, "rating_items": items_rating, "rating_source": source,
                "combine_rule": COMBINE_RULE, "nearest": nearest,
                "described": bool(raw.get("described", True)), "items": items, "dropped": dropped}, usage


def normalize_direct(raw: dict) -> dict:
    """rate_direct 의 JSON 을 판정 모양으로. 깨졌으면 전체이용가·내용정보 없음으로 둔다(오답으로 셈해진다)."""
    rating = raw.get("rating") if raw.get("rating") in RATINGS else RATINGS[0]
    descriptors = [d for d in raw.get("descriptors", []) if d in ITEMS] if isinstance(raw.get("descriptors"), list) else []
    return {"method": "direct", "rating": rating, "described": True,
            "descriptors": list(dict.fromkeys(descriptors)), "reason": str(raw.get("reason", ""))}


def predicted_descriptors(assessment: dict) -> list[str]:
    """판정이 붙인 내용정보 항목 — 채점(내용정보 F1)에 쓴다."""
    if assessment["method"] == "direct":
        return assessment["descriptors"]
    return [name for name in ITEMS if assessment["items"][name]["present"]]
