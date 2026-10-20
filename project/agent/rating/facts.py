"""수집한 사실·판정 결과를 프롬프트용 글로 적는다 — 작성(write)과 검수(judge)가 같은 사실을 보게.

과제 1 의 validator.render_facts 와 같은 생각이다. collected 는 research 노드가 모은 목록이고 항목마다
{"source": "cases" | "stats" | "criteria", "data": ...} 모양이다. 사례 검색 범위를 넓혀 다시 조사하면
cases 가 여러 번 쌓이므로 늘 마지막 것을 쓴다.

작성·검수용 글에는 사례 번호(예: CC-OM-240201-001)를 넣지 않고 「제목」으로만 적는다. 번호를 보이면 작성 모델이
그대로 옮겨 쓰고, 그 숫자가 수치 대조에 걸려 재작성이 되풀이됐다(2026-10-20 회귀 쿼리 3건). 판정 프롬프트
(llm.cases_text)는 번호가 있어야 근거 사례를 가리킬 수 있어 따로 둔다.
"""
from .data import ITEMS, RATINGS


def latest(collected: list[dict], source: str):
    """source 가 같은 수집 결과 중 마지막 것의 data. 없으면 None."""
    found = [c for c in collected if c["source"] == source]
    return found[-1]["data"] if found else None


def render_case(case: dict) -> str:
    descriptors = ", ".join(case["descriptors"]) or "내용정보 없음"
    return f"「{case['title']}」({case['rating']} · {descriptors}) {case['genre']} · {case['platform']} — {case['summary']}"


def render_stats(stats: dict) -> str:
    f = stats["filter"]
    where = " · ".join(v for v in (f.get("genre"), f.get("platform")) if v) or "전체"
    by_rating = ", ".join(f"{r} {stats['by_rating'][r]}건" for r in RATINGS)
    return f"{where} 사례 {stats['total']}건 중 {by_rating}"


def render_assessment(assessment: dict, cases: list[dict] | None = None, criteria: dict | None = None) -> str:
    """판정 결과. 항목 줄은 보고서에 바로 옮겨 쓸 수 있는 모양 — '- 항목: 기준 문구(등급) — 근거: …'."""
    if assessment["method"] == "direct":
        descriptors = ", ".join(assessment["descriptors"]) or "없음"
        return (f"예상 등급: {assessment['rating']} (LLM 단독 판정)\n내용정보: {descriptors}\n"
                f"이유: {assessment.get('reason', '')}")
    lines = [f"예상 등급: {assessment['rating']} (항목 단계의 최댓값으로 코드가 계산)"]
    if assessment.get("rating_source") == "cases":   # 결합 규칙(결정 0016)이 사례 등급을 따랐다
        near = assessment["nearest"]
        lines = [f"예상 등급: {assessment['rating']} (기준표 판정은 {assessment['rating_items']}이지만, 설명에 표현 수위가 "
                 f"충분하지 않아 가장 비슷한 실제 사례 「{near['title']}」({near['rating']})를 반영)"]
    titles = {c["id"]: c["title"] for c in cases or []}
    items = {name: assessment["items"].get(name, {"present": False}) for name in ITEMS}
    present = [(name, item) for name, item in items.items() if item["present"]]
    for name, item in present:
        grounds = []
        if item["evidence"]:
            grounds.append(f'설명 인용 "{item["evidence"]}"')
        if item.get("case_ids"):
            grounds.append("비슷한 사례 " + ", ".join(f"「{titles.get(i, i)}」" for i in item["case_ids"]))
        lines.append(f"- {name}: {item['phrase']}({RATINGS[item['level']]}) — 근거: {' / '.join(grounds)}")
    absent = [name for name in ITEMS if not items[name]["present"]]
    if not present:
        lines.append("- 해당 항목 없음")
    if absent:
        lines.append(f"- 해당 없음: {', '.join(absent)}")
    if assessment.get("rating_source") == "cases":
        lines.append("등급을 낮추려면: 설명만으로는 판정 근거가 부족해 비슷한 사례의 등급을 따랐습니다. 폭력·선정·사행 표현의 "
                     "수위를 자세히 알려 주시면 기준표로 다시 판정합니다.")
    elif criteria is not None:
        lines.append(f"등급을 낮추려면: {lowering_advice(items, criteria)}")
    return "\n".join(lines)


def lowering_advice(items: dict, criteria: dict) -> str:
    """등급을 정한 항목(가장 높은 단계)을 기준표의 한 단계 아래 표현으로 바꾸면 무엇이 되는지 — 코드가 계산한다.

    작성 모델이 이 부분을 자유롭게 쓰면 "단계를 낮추면 15세로 조정" 같은 틀린 말을 했다(2026-10-20 회귀 쿼리).
    """
    present = {name: item["level"] for name, item in items.items() if item["present"]}
    top = max(present.values(), default=0)
    if top == 0:
        return "이미 가장 낮은 등급(전체이용가)입니다."
    leaders = [name for name, level in present.items() if level == top]
    lowered = max([top - 1, *(level for name, level in present.items() if name not in leaders)])
    changes = ", ".join(f"{name}을(를) '{criteria['items'][name][top]}'에서 '{criteria['items'][name][top - 1]}' 수준으로"
                        for name in leaders)
    return f"{changes} 낮추면 {RATINGS[lowered]}를 노려 볼 수 있습니다."


def render_facts(assessment: dict, collected: list[dict]) -> str:
    """판정 결과 + 유사 사례 + 통계. 기준표 전문은 넣지 않는다(판정 결과에 해당 단계 문구가 이미 들어 있다)."""
    cases = latest(collected, "cases")
    parts = [f"## 판정 결과\n{render_assessment(assessment, cases, latest(collected, 'criteria'))}"]
    if cases:
        parts.append("## 비슷한 실제 사례 (게임물관리위원회 결정)\n" + "\n".join(f"- {render_case(c)}" for c in cases))
    stats = latest(collected, "stats")
    if stats:
        parts.append(f"## 같은 장르·플랫폼 통계\n{render_stats(stats)}")
    return "\n\n".join(parts)
