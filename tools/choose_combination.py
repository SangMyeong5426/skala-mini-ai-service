"""결합 규칙을 개발용 문항으로 고른다 — 평가셋 A·B 는 보지 않는다(결정 0016).

    project/.venv/bin/python tools/choose_combination.py runs/eval-rdev_<label>_<시각>.json

에이전트를 개발용 문항(tools/evalsets/rating_dev.json)으로 한 번 돌린 결과(행마다 항목 판정·검색된 사례 등급)에
후보 규칙(agent/rating/assess.py 의 COMBINE_RULES)을 하나씩 적용해 본다. LLM 을 다시 부르지 않는다 — 규칙은 판정 뒤의
코드 계산이라서다. 고르는 기준은 미리 정했다: 정확도가 가장 높은 것, 동률이면 과소평가가 적은 것, 그래도 같으면
후보 순서가 앞인(단순한) 것. 결과는 runs/choose-combination_<시각>.json 에 남기고, 고른 값을 COMBINE_RULE 에 옮긴다.
"""
import json
import sys
from datetime import datetime
from pathlib import Path

from measure_queries import ROOT, _display

sys.path.insert(0, str(ROOT / "project"))
from agent.rating.assess import COMBINE_RULES, combine  # noqa: E402
from agent.rating.data import RATINGS  # noqa: E402


def items_of(row: dict) -> dict:
    """eval 행의 항목 요약 → combine 이 읽는 모양."""
    return {name: {"present": True, "evidence": "인용" if i["quote"] else ""} for name, i in row["items"].items()}


def main(path: Path) -> None:
    run = json.loads(path.read_text())
    if run["kind"] != "rdev":
        sys.exit("개발용 문항(rdev) 결과만 쓴다 — 평가셋 A·B 결과로 고르지 않는다")
    rows = [r for r in run["results"] if r["action"] == "assess" and r["rating_items"]]
    table = []
    for order, rule in enumerate(COMBINE_RULES):
        preds = [combine(r["rating_items"], items_of(r), r["case_ratings"], rule)[0] for r in rows]
        diffs = [RATINGS.index(p) - RATINGS.index(r["label"]) for p, r in zip(preds, rows, strict=True)]
        table.append({"rule": rule, "order": order, "correct": sum(d == 0 for d in diffs), "n": len(run["results"]),
                      "under": sum(d < 0 for d in diffs), "over": sum(d > 0 for d in diffs)})
        print(f"R{order} {rule:11} 정답 {table[-1]['correct']}/{table[-1]['n']}  과소 {table[-1]['under']}  과대 {table[-1]['over']}")
    chosen = sorted(table, key=lambda t: (-t["correct"], t["under"], t["order"]))[0]
    print(f"\n고름: {chosen['rule']} (되묻기·오류 {len(run['results']) - len(rows)}건은 모든 규칙에서 오답)")
    out = ROOT / "runs" / f"choose-combination_{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    out.write_text(json.dumps({"source": _display(path), "git": run["git"], "table": table, "chosen": chosen["rule"]},
                              ensure_ascii=False, indent=2) + "\n")
    print(f"저장: {_display(out)}")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
