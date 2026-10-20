"""등급 정확도 평가셋을 원자료에서 만든다 — A(한 문장 개요)와 B(상세 설명). 결정 0010·0014.

    project/.venv/bin/python tools/make_rating_evalset.py           # A — tools/evalsets/rating.json
    project/.venv/bin/python tools/make_rating_evalset.py detail    # B — tools/evalsets/rating_detail.json
    project/.venv/bin/python tools/make_rating_evalset.py dev       # 개발용 — tools/evalsets/rating_dev.json

개발용 — A 와 같은 기간·같은 규칙에서 **A 에 뽑히지 않은 것**으로 등급마다 10개(15세는 남은 8개 전부), 시드 20261021.
    결합 규칙(사례 등급 ↔ 기준표 판정)을 이 문항으로만 고른다. A·B 는 고른 뒤 한 번만 확인한다(결정 0016).

A — 기능 코드보다 먼저, 시드 고정.

평가 기간(2026-07-01 ~ 2026-09-30) 결정 중 사례 DB 와 같은 규칙(agent/rating/data.py 의 usable)을
통과한 것에서 등급마다 10개씩 뽑아 tools/evalsets/rating.json 에 쓴다.

- 입력 문장에는 장르·플랫폼·개요만 넣고 **제목은 뺀다.** LLM 이 이름난 게임의 등급을 외워서 맞히지 않게.
- 정답은 실제 결정 등급(rating)과 내용정보(descriptors)다.
- 같은 신청자의 게임이 사례 DB 에 있는지(applicant_in_cases)를 적어 둔다 — 같은 회사의 비슷한 게임이
  사례로 검색되면 답이 새는 것처럼 작동할 수 있어, 결과를 이 값으로 나눠 볼 수 있게 한다.

B — 위원회 결정서의 등급분류 사유(공공데이터포털 "게임물관리위원회_등급분류증명서 및 결정서 정보", 2026년 2분기,
    공공누리 1유형 — tools/evalsets/source/)에서 결론과 기준어를 지우고 내용 서술만 입력으로 쓴다. 정답은 같은
    등급분류번호의 API 결정 등급이다. A 와 같은 규칙(usable)으로 거르고, 간소화 설문 결정(내용 서술 없음)은 뺀다.
    표본을 뽑지 않고 남은 것을 모두 쓴다. 한 문장 개요(A)로는 정확도 상한이 낮아(결정 0010) 추가했다.
    - 지우는 것: "따라서 …" 또는 "게임산업진흥에 관한 법률 …"부터 끝까지(등급·규정 호수가 있는 결론),
      "＊ 기준어" 머리(예: "＊ 선정성(제한적인 선정적 표현)" — 단계를 바로 말해 준다).
    - 남는 것: 개요와 "- 상세" 서술. 서술에는 심의자의 낱말("사실적으로 묘사", "경미하게")이 남는다 — 개발자가 쓰는
      설명보다 기준표에 가까운 말투라 쉬울 수 있다(한계).
    - 이 게임들은 사례 DB 기간(2026-04~06)에 있다. 평가할 때 자기 자신과 같은 제목의 사례는 검색에서 뺀다
      (tools/eval_rating.py rateb).

이 파일을 다시 돌려도 같은 결과가 나와야 한다(원자료·시드가 같으면). 결과를 본 뒤 문항을 바꾸지 않는다.
"""
import csv
import json
import random
import re
import sys

from measure_queries import ROOT, _display

sys.path.insert(0, str(ROOT / "project"))
from agent.rating.data import (  # noqa: E402
    EVAL_FROM,
    EVAL_UNTIL,
    RATINGS,
    load_cases,
    load_raw,
    usable,
)

SEED = 20261020
DEV_SEED = 20261021
PER_RATING = 10
OUT = ROOT / "tools" / "evalsets" / "rating.json"
OUT_DETAIL = ROOT / "tools" / "evalsets" / "rating_detail.json"
OUT_DEV = ROOT / "tools" / "evalsets" / "rating_dev.json"
DECISIONS = ROOT / "tools" / "evalsets" / "source" / "grac_decision_reasons_2026q2.csv"
MESSAGE = "출시 전에 등급을 미리 점검하고 싶어요. 장르: {genre}, 플랫폼: {platform}. 게임 내용: {summary}"
CONCLUSION = re.compile(r"따라서|게임산업진흥에\s*관한\s*법률")
HEADER = re.compile(r"(?:^|(?<=\s))＊\s[^-－]*")   # "＊ 기준어" — 욕설 가림표(f＊＊k)는 뒤에 띄어쓰기가 없다
BULLET = re.compile(r"\s[-－]\s+")
LEAK = re.compile("|".join([*RATINGS, "이용가", "등급", r"제\s*7\s*조"]))


def strip_reason(reason: str) -> str:
    """결정서 사유 → 입력으로 쓸 내용 서술."""
    text = CONCLUSION.split(reason)[0]
    text = BULLET.sub(" ", HEADER.sub(" ", " " + text))
    return re.sub(r"\s+", " ", text).strip()


def build_detail() -> None:
    raw = {r["id"]: r for r in load_raw()}
    items, skipped = [], {"간소화 설문": 0, "API 에 없음": 0, "범위 밖": 0}
    with DECISIONS.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            reason = row["등급분류사유"]
            r = raw.get(row["등급분류번호"])
            if "간소화 등급분류 설문" in reason:
                skipped["간소화 설문"] += 1
            elif r is None:
                skipped["API 에 없음"] += 1
            elif not usable(r):
                skipped["범위 밖"] += 1
            else:
                text = strip_reason(reason)
                assert not LEAK.search(text), f"정답 단서가 남았다: {r['id']} {text}"
                items.append({
                    "id": f"b{len(items) + 1:02d}", "rateno": r["id"], "title": r["title"],
                    "message": MESSAGE.format(genre=r["genre"] or "기타", platform=r["platform"], summary=text),
                    "genre": r["genre"], "platform": r["platform"], "detail": text,
                    "label": {"rating": r["rating"], "descriptors": r["descriptors"]},
                })
    OUT_DETAIL.write_text(json.dumps(items, ensure_ascii=False, indent=1) + "\n")
    counts = {g: sum(i["label"]["rating"] == g for i in items) for g in RATINGS}
    print(f"결정서 {sum(skipped.values()) + len(items)}건 중 {len(items)}건 → {_display(OUT_DETAIL)}")
    print("뺀 것:", skipped, "등급별:", counts)


def main(dev: bool = False) -> None:
    pool = [r for r in load_raw() if EVAL_FROM <= r["date"] <= EVAL_UNTIL and usable(r)]
    pool.sort(key=lambda r: (r["date"], r["id"]))
    if dev:   # 평가셋 A 에 뽑힌 결정은 뺀다
        taken = {i["rateno"] for i in json.loads(OUT.read_text())}
        pool = [r for r in pool if r["id"] not in taken]
    applicants = {c["applicant"] for c in load_cases()}
    rng = random.Random(DEV_SEED if dev else SEED)
    items = []
    for rating in RATINGS:
        candidates = [r for r in pool if r["rating"] == rating]
        picked = rng.sample(candidates, min(PER_RATING, len(candidates)))
        for r in sorted(picked, key=lambda r: (r["date"], r["id"])):
            items.append({
                "id": f"{'d' if dev else 'a'}{len(items) + 1:02d}",
                "rateno": r["id"],
                "message": MESSAGE.format(genre=r["genre"] or "기타", platform=r["platform"],
                                          summary=r["summary"]),
                "genre": r["genre"], "platform": r["platform"], "summary": r["summary"],
                "label": {"rating": r["rating"], "descriptors": r["descriptors"]},
                "applicant_in_cases": r["applicant"] in applicants,
            })
    out = OUT_DEV if dev else OUT
    out.write_text(json.dumps(items, ensure_ascii=False, indent=1) + "\n")
    counts = {g: sum(i["label"]["rating"] == g for i in items) for g in RATINGS}
    print(f"평가 기간 후보 {len(pool)}건 중 {len(items)}개 {counts} → {_display(out)}")
    print("같은 신청자가 사례 DB 에 있는 문항:", sum(i["applicant_in_cases"] for i in items), "/", len(items))


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else "summary"
    {"summary": main, "detail": build_detail, "dev": lambda: main(dev=True)}[command]()
