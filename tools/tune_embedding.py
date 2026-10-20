"""의미 라우터·대상 추정의 판정 기준을 평가 세트 없이 정한다 — 항목 2·3.

    project/.venv/bin/python tools/tune_embedding.py

router : data/router_examples.json 안에서 leave-one-out. 예시 하나를 빼고 나머지 예시로 그 예시를
         분류해 두 클래스 점수 차(gap)를 모은다. 지시문을 붙일 때와 뗄 때를 비교하고, margin 후보마다
         "판정한 것의 정답률"과 "LLM 으로 넘기는 비율"을 낸다. 권장 margin 은 LOO 에서 틀린 예시의
         |gap| 최댓값보다 조금 크게 잡는다 — 예시끼리도 헷갈린 영역은 LLM 에 넘긴다는 뜻이다.
target : tools/tuning/target.json(평가 세트와 별개인 조정용 문장)으로 min_score·margin 격자 탐색.
         시스템을 맞혀야 할 문장의 정답률과 되물어야 할 문장의 정답률 평균이 가장 높은 조합들 중,
         모든 문장이 판정 경계에서 가장 멀리 떨어지는 조합(최악의 여유가 가장 큰 조합)을 고른다 —
         경계에 붙은 값은 문장이 조금만 달라져도 판정이 뒤집힌다.

평가 세트(tools/evalsets/)는 읽지 않는다. 결과는 runs/tune-embedding_<시각>.json 에 남기고, 고른 값은
agent/router.py·agent/target.py 의 기본값과 결정 기록(0003·0004)에 옮긴다.

    project/.venv/bin/python tools/tune_embedding.py --domain rating

과제 2 : router 만 — data/ratings/router_examples.json(chat / review)으로 같은 leave-one-out 을 한다.
         고른 값은 agent/rating/data.py 의 ROUTER_MARGIN 과 결정 0013 에 옮긴다. 결과는 runs/tune-embedding-rating_<시각>.json.
"""
import argparse
import asyncio
import json
import statistics
import sys
from datetime import datetime

from measure_queries import ROOT, _display, _git_state

sys.path.insert(0, str(ROOT / "project"))
from agent.embedding import OllamaEmbedder, cosine  # noqa: E402
from agent.rating.data import RATING_ROUTE_INSTRUCTION, ROUTER_EXAMPLES_PATH  # noqa: E402
from agent.router import (  # noqa: E402
    DEFAULT_K,
    EXAMPLES_PATH,
    ROUTE_INSTRUCTION,
    class_scores,
    load_examples,
)
from agent.target import TARGET_INSTRUCTION  # noqa: E402

TUNING_TARGET = ROOT / "tools" / "tuning" / "target.json"
CATALOG = ROOT / "project" / "data" / "systems.json"
MARGINS = [round(0.005 * i, 3) for i in range(21)]            # 0 ~ 0.1
MIN_SCORES = [round(0.2 + 0.025 * i, 3) for i in range(25)]   # 0.2 ~ 0.8


def _pred(gap: float, work_label: str = "incident") -> str:
    return work_label if gap > 0 else "chat"


async def tune_router(embedder: OllamaEmbedder, examples_path=EXAMPLES_PATH, work_label: str = "incident",
                      route_instruction: str = ROUTE_INSTRUCTION, fallback=None) -> dict:
    examples = load_examples(examples_path, work_label)
    report = {}
    for name, instruction in (("instruction", route_instruction), ("none", None)):
        vecs = {label: await embedder.embed(texts, instruction) for label, texts in examples.items()}
        gaps = []
        for label, label_vecs in vecs.items():
            for i, vec in enumerate(label_vecs):
                rest = {lab: [v for j, v in enumerate(vs) if not (lab == label and j == i)]
                        for lab, vs in vecs.items()}
                s = class_scores(vec, rest, DEFAULT_K)
                gaps.append({"text": examples[label][i], "label": label,
                             "gap": round(s[work_label] - s["chat"], 4)})
        wrong = [g for g in gaps if _pred(g["gap"], work_label) != g["label"]]
        curve = []
        for m in MARGINS:
            decided = [g for g in gaps if abs(g["gap"]) >= m]
            correct = sum(_pred(g["gap"], work_label) == g["label"] for g in decided)
            curve.append({"margin": m, "decided": len(decided),
                          "accuracy_decided": round(correct / len(decided), 3) if decided else None,
                          "fallback_rate": round(1 - len(decided) / len(gaps), 3)})
        suggested = round(max(abs(g["gap"]) for g in wrong) + 0.005, 3) if wrong else 0.0
        if fallback is not None:
            # 과제 2 — margin 아래는 LLM 이 판정한다. 그 LLM 이 예시 문장에서 얼마나 맞히는지까지 넣어,
            # "margin 위는 의미 판정 + 아래는 LLM" 의 예시 정답률이 가장 높은 margin 을 고른다(동률이면 작은 쪽).
            for g in gaps:
                g["llm"] = fallback(g["text"])
            for row in curve:
                hits = sum((_pred(g["gap"], work_label) if abs(g["gap"]) >= row["margin"] else g["llm"]) == g["label"]
                           for g in gaps)
                row["combined_accuracy"] = round(hits / len(gaps), 3)
            best = max(r["combined_accuracy"] for r in curve)
            suggested = min(r["margin"] for r in curve if r["combined_accuracy"] == best)
            print(f"[router/{name}] 대체 LLM 의 예시 정답률 "
                  f"{sum(g['llm'] == g['label'] for g in gaps)}/{len(gaps)} → 결합 정답률 최고 {best} @ margin {suggested}")
        abs_gaps = sorted(abs(g["gap"]) for g in gaps)
        report[name] = {"loo_accuracy": round(1 - len(wrong) / len(gaps), 3), "wrong": wrong,
                        "suggested_margin": suggested,
                        "abs_gap_min_median": [abs_gaps[0], statistics.median(abs_gaps)],
                        "curve": curve}
        print(f"[router/{name}] LOO 정답률 {report[name]['loo_accuracy']}  "
              f"틀린 예시 {len(wrong)}개  권장 margin {suggested}  "
              f"|gap| 최소·중앙 {report[name]['abs_gap_min_median']}")
        for g in wrong:
            print(f"    틀림: {g['label']:8} gap={g['gap']:+.4f}  {g['text']}")
    return report


async def tune_target(embedder: OllamaEmbedder) -> dict:
    data = json.loads(TUNING_TARGET.read_text())
    catalog = json.loads(CATALOG.read_text())
    docs = await embedder.embed([f"{s['name']}: {s['description']}" for s in catalog])

    def ranked(vec):
        return sorted(((cosine(vec, d), s["name"]) for s, d in zip(catalog, docs, strict=True)),
                      reverse=True)

    report = {}
    for name, instruction in (("instruction", TARGET_INSTRUCTION), ("none", None)):
        pos_vecs = await embedder.embed([p["query"] for p in data["positives"]], instruction)
        amb_vecs = await embedder.embed(data["ambiguous"], instruction)
        pos = [(p, ranked(v)) for p, v in zip(data["positives"], pos_vecs, strict=True)]
        amb = [(q, ranked(v)) for q, v in zip(data["ambiguous"], amb_vecs, strict=True)]

        grid = []
        for min_score in MIN_SCORES:
            for margin in MARGINS:
                def decide(r, min_score=min_score, margin=margin):
                    (s1, n1), (s2, _) = r[0], r[1]
                    return n1 if s1 >= min_score and s1 - s2 >= margin else None

                def slack(r, clarify, min_score=min_score, margin=margin):
                    # 경계까지의 여유. 진단할 문장은 두 조건을 모두, 되물을 문장은 하나만 어기면 된다.
                    (s1, _), (s2, _) = r[0], r[1]
                    if clarify:
                        return max(min_score - s1, margin - (s1 - s2))
                    return min(s1 - min_score, (s1 - s2) - margin)
                pos_acc = statistics.fmean(decide(r) == p["target"] for p, r in pos)
                amb_acc = statistics.fmean(decide(r) is None for _, r in amb)
                worst = min([slack(r, False) for _, r in pos] + [slack(r, True) for _, r in amb])
                grid.append({"min_score": min_score, "margin": margin, "pos_acc": round(pos_acc, 3),
                             "amb_acc": round(amb_acc, 3), "balanced": round((pos_acc + amb_acc) / 2, 3),
                             "worst_slack": round(worst, 4)})
        top = max(g["balanced"] for g in grid)
        best = [g for g in grid if g["balanced"] == top]
        chosen = max(best, key=lambda g: g["worst_slack"])
        report[name] = {
            "chosen": chosen, "tied_best": len(best),
            "positives": [{"query": p["query"], "target": p["target"], "top1": r[0][1],
                           "s1": round(r[0][0], 4), "s2": round(r[1][0], 4)} for p, r in pos],
            "ambiguous": [{"query": q, "top1": r[0][1], "s1": round(r[0][0], 4),
                           "s2": round(r[1][0], 4)} for q, r in amb],
        }
        print(f"[target/{name}] 최고 균형 정답률 {top} (동률 {len(best)}개) → 선택 {chosen}")
        for row in report[name]["positives"]:
            mark = "ok" if row["top1"] == row["target"] else "XX"
            print(f"    {mark} {row['target']:16} 1위={row['top1']:16} s1={row['s1']:.3f} "
                  f"s2={row['s2']:.3f}  {row['query']}")
        for row in report[name]["ambiguous"]:
            print(f"    ?? {'(되묻기)':16} 1위={row['top1']:16} s1={row['s1']:.3f} "
                  f"s2={row['s2']:.3f}  {row['query']}")
    return report


async def main(domain: str) -> None:
    embedder = OllamaEmbedder()
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    report = {"started_at": stamp, "git": _git_state(), "embedder": embedder.name, "domain": domain}
    if domain == "rating":
        from agent.rating.llm import (
            OllamaRatingFastLLM,  # 서버와 같은 대체 LLM — qwen3:0.6b, 생각 끔
        )
        fast = OllamaRatingFastLLM("qwen3:0.6b", usd_per_1k_tokens=0.00015, think=False)
        report["router"] = await tune_router(embedder, ROUTER_EXAMPLES_PATH, "review", RATING_ROUTE_INSTRUCTION,
                                             fallback=lambda text: fast.route(text)[0]["route"])
        out = ROOT / "runs" / f"tune-embedding-rating_{stamp}.json"
    else:
        report["router"] = await tune_router(embedder)
        report["target"] = await tune_target(embedder)
        out = ROOT / "runs" / f"tune-embedding_{stamp}.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(f"\n저장: {_display(out)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--domain", choices=["incident", "rating"], default="incident",
                        help="incident = 과제 1(router + target), rating = 과제 2(router)")
    asyncio.run(main(parser.parse_args().domain))
