"""평가셋 A(등급 정확도)를 원자료에서 뽑는다 — 기능 코드보다 먼저, 시드 고정 (결정 0010).

    project/.venv/bin/python tools/make_rating_evalset.py

평가 기간(2026-07-01 ~ 2026-09-30) 결정 중 사례 DB 와 같은 규칙(agent/rating/data.py 의 usable)을
통과한 것에서 등급마다 10개씩 뽑아 tools/evalsets/rating.json 에 쓴다.

- 입력 문장에는 장르·플랫폼·개요만 넣고 **제목은 뺀다.** LLM 이 이름난 게임의 등급을 외워서 맞히지 않게.
- 정답은 실제 결정 등급(rating)과 내용정보(descriptors)다.
- 같은 신청자의 게임이 사례 DB 에 있는지(applicant_in_cases)를 적어 둔다 — 같은 회사의 비슷한 게임이
  사례로 검색되면 답이 새는 것처럼 작동할 수 있어, 결과를 이 값으로 나눠 볼 수 있게 한다.

이 파일을 다시 돌려도 같은 결과가 나와야 한다(원자료·시드가 같으면). 결과를 본 뒤 문항을 바꾸지 않는다.
"""
import json
import random
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
PER_RATING = 10
OUT = ROOT / "tools" / "evalsets" / "rating.json"
MESSAGE = "출시 전에 등급을 미리 점검하고 싶어요. 장르: {genre}, 플랫폼: {platform}. 게임 내용: {summary}"


def main() -> None:
    pool = [r for r in load_raw() if EVAL_FROM <= r["date"] <= EVAL_UNTIL and usable(r)]
    pool.sort(key=lambda r: (r["date"], r["id"]))
    applicants = {c["applicant"] for c in load_cases()}
    rng = random.Random(SEED)
    items = []
    for rating in RATINGS:
        picked = rng.sample([r for r in pool if r["rating"] == rating], PER_RATING)
        for r in sorted(picked, key=lambda r: (r["date"], r["id"])):
            items.append({
                "id": f"a{len(items) + 1:02d}",
                "rateno": r["id"],
                "message": MESSAGE.format(genre=r["genre"] or "기타", platform=r["platform"],
                                          summary=r["summary"]),
                "genre": r["genre"], "platform": r["platform"], "summary": r["summary"],
                "label": {"rating": r["rating"], "descriptors": r["descriptors"]},
                "applicant_in_cases": r["applicant"] in applicants,
            })
    OUT.write_text(json.dumps(items, ensure_ascii=False, indent=1) + "\n")
    print(f"평가 기간 후보 {len(pool)}건 중 등급마다 {PER_RATING}개 → {_display(OUT)}")
    print("같은 신청자가 사례 DB 에 있는 문항:", sum(i["applicant_in_cases"] for i in items), "/", len(items))


if __name__ == "__main__":
    main()
