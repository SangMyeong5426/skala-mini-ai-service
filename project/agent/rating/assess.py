"""판정 결과를 정리한다 — Before(LLM 단독)의 답을 같은 모양으로 맞춘다.

등급 점검 그래프의 analysis 노드가 만든 판정은 늘 {"method", "rating", "described", ...} 모양이다.
method=direct 는 LLM 이 등급을 바로 답한 것(Before)이다.
"""
from .data import ITEMS, RATINGS


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
