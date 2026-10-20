"""과제 2 — 등급 점검 그래프의 노드를 서버 없이 직접 불러 평가셋으로 채점한다 (Before/After).

    project/.venv/bin/python tools/eval_rating.py rate     --label before
    project/.venv/bin/python tools/eval_rating.py rateb    --label before
    project/.venv/bin/python tools/eval_rating.py rroute   --label before
    project/.venv/bin/python tools/eval_rating.py rclarify --label before
    project/.venv/bin/python tools/eval_rating.py rjudge   --label before
    project/.venv/bin/python tools/eval_rating.py all      --label before

| 하위 명령 | 부르는 곳                                  | 평가셋                    | 채점                                          |
| rate      | plan → research ⇄ replan_check → analysis | evalsets/rating.json (A) | 등급 정확도, ±1단계, 과소·과대평가, 되묻기, 내용정보 F1 |
| rateb     | 〃 — 상세 설명                             | evalsets/rating_detail.json (B) | 〃. 자기 자신·같은 제목의 사례는 검색에서 뺀다 |
| rroute    | route_node                                | evalsets/rating_route.json   | chat/review 분류 정확도                    |
| rclarify  | plan → research ⇄ replan_check → analysis | evalsets/rating_clarify.json | 되묻기 정답률                              |
| rjudge    | validate_node                             | evalsets/rating_judge.json   | 오염 초안 탐지율, 정상 초안 오탐률          |
| rbase     | case_retriever 만 (LLM 없음)              | rating.json · rating_detail.json | 기준선 — 가장 가까운 사례 1건, 5건 다수결 |

의존성은 server.py 의 lifespan 을 AGENT_DOMAIN=rating 으로 실행해 얻는다. 부품 스위치(ROUTER·CASE_SEARCH·
RATING_ASSESSOR·RATING_CLARIFY·VALIDATOR)는 환경변수로 준다 — 모두 끄면 LLM 단독(Before)이다(결정 0009).
채점 약속은 이렇다. 그래프 코드가 바뀌어도 이 약속만 지키면 이 파일은 고치지 않는다.

- rate·rateb·rclarify : 상태에 clarify 가 생기면 되묻기로 본다(rate 에서는 오답). 아니면 assessment["rating"] 이 예상 등급이다.
- rateb : 평가셋 B 의 게임은 사례 DB 기간에 있다. 문항마다 case_retriever.exclude(번호, 제목)로 자기 자신을 뺀다.
- rroute        : route_node 가 돌려준 route.
- rjudge        : validate_node 가 돌려준 validation_feedback 이 None 이면 합격.
- rbase         : 그래프와 같은 범위 넓히기(사례 3건 미만이면 장르+플랫폼 → 플랫폼 → 전체)로 찾은 사례의 등급만 본다.
                  5건 다수결이 동률이면 더 가까운 사례의 등급. CASE_SEARCH=semantic 이어야 한다.

--code-root 로 다른 체크아웃(scripts/measure-at 이 만든 git worktree)의 project/ 코드를 잴 수 있다. 평가셋과 채점은
늘 이 파일 옆의 것을 쓴다. 결과는 runs/eval-<하위 명령>_<label>_<시각>.json 에 남는다.
"""
import argparse
import asyncio
import json
import os
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

from eval_nodes import _check_ollama, _fresh_state, _median, _timed
from measure_queries import ROOT, _display, _git_state, _switches

EVALSETS = ROOT / "tools" / "evalsets"
DEFAULT_OUT_DIR = ROOT / "runs"
FILES = {"rate": "rating", "rateb": "rating_detail", "rroute": "rating_route", "rclarify": "rating_clarify",
         "rjudge": "rating_judge", "rbase": "rating"}
MAX_ROUNDS = 4   # research ⇄ replan_check 왕복 상한 — 그래프는 범위를 두 번까지만 넓힌다


def _load(kind: str) -> list[dict]:
    return json.loads((EVALSETS / f"{FILES[kind]}.json").read_text())


async def _until_assessment(query: str, deps, g) -> dict:
    """plan → research ⇄ replan_check → analysis. 분기는 그래프의 _after_* 함수를 그대로 쓴다."""
    state = _fresh_state(query)
    state = {**state, **await g.plan_node(state, deps)}
    if g._after_plan(state) == "clarify":
        return state
    for _ in range(MAX_ROUNDS):
        state = {**state, **await g.research_node(state, deps)}
        state = {**state, **await g.replan_check_node(state, deps)}
        if g._after_replan_check(state) == "analysis":
            break
    return {**state, **await g.analysis_node(state, deps)}


def _prf(pairs: list[tuple[list[str], list[str]]]) -> dict:
    """내용정보 마이크로 정밀도·재현율·F1 — (정답, 예측) 목록."""
    tp = sum(len(set(gold) & set(pred)) for gold, pred in pairs)
    fp = sum(len(set(pred) - set(gold)) for gold, pred in pairs)
    fn = sum(len(set(gold) - set(pred)) for gold, pred in pairs)
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    return {"precision": round(p, 3), "recall": round(r, 3), "f1": round(2 * p * r / (p + r), 3) if p + r else 0.0}


async def eval_rate(deps, ctx: dict, kind: str = "rate") -> tuple[list[dict], dict]:
    ratings, describe = ctx["RATINGS"], ctx["predicted_descriptors"]
    retriever = deps.case_retriever if kind == "rateb" else None
    rows = []
    for item in _load(kind):
        if retriever is not None:
            retriever.exclude(item["rateno"], item["title"])
        out, latency, error = await _timed(_until_assessment(item["message"], deps, ctx["graph"]))
        gold = item["label"]["rating"]
        if out is None:
            action, pred, desc = "error", None, []
        elif out.get("clarify"):
            action, pred, desc = "clarify", None, []
        else:
            action, pred, desc = "assess", out["assessment"]["rating"], describe(out["assessment"])
        assessment = (out or {}).get("assessment", {})
        cases = [c for c in (out or {}).get("collected", []) if c["source"] == "cases"]
        rows.append({
            "id": item["id"], "label": gold, "pred": pred, "action": action, "ok": pred == gold,
            "diff": ratings.index(pred) - ratings.index(gold) if pred else None,
            "descriptors_label": item["label"]["descriptors"], "descriptors_pred": desc,
            "method": assessment.get("method"), "dropped": assessment.get("dropped", []),
            "cases_scope": cases[-1]["scope"] if cases else None,
            "cases": [c["id"] for c in cases[-1]["data"]] if cases else [],
            "applicant_in_cases": item.get("applicant_in_cases"),
            "latency_s": latency, "cost_usd": (out or {}).get("cost_usd"), "error": error,
        })
        print(f"  {item['id']} {gold:>8} → {pred or action:>8} {'✓' if pred == gold else '✗'} {latency:6.1f}s")
    if retriever is not None:
        retriever.exclude()
    n = len(rows)
    rated = [r for r in rows if r["pred"]]

    def acc(group: list[dict]) -> str:
        return f"{sum(r['ok'] for r in group)}/{len(group)}"

    summary = {
        "n": n, "accuracy": acc(rows),
        "within_one": f"{sum(abs(r['diff']) <= 1 for r in rated)}/{n}",
        "under": sum(r["diff"] < 0 for r in rated), "over": sum(r["diff"] > 0 for r in rated),
        "clarified": sum(r["action"] == "clarify" for r in rows),
        "errors": sum(r["action"] == "error" for r in rows),
        "descriptors": _prf([(r["descriptors_label"], r["descriptors_pred"]) for r in rows]),
        "accuracy_by_label": {g: acc([r for r in rows if r["label"] == g]) for g in ratings},
        "accuracy_applicant_in_cases": acc([r for r in rows if r["applicant_in_cases"]]),
        "accuracy_applicant_new": acc([r for r in rows if r["applicant_in_cases"] is False]),
        "confusion": {g: dict(Counter(r["pred"] or r["action"] for r in rows if r["label"] == g)) for g in ratings},
        "dropped_items": sum(len(r["dropped"]) for r in rows),
        "latency_median_s": _median([r["latency_s"] for r in rows]),
        "cost_usd_sum": round(sum(r["cost_usd"] or 0 for r in rows), 6),
    }
    return rows, summary


async def eval_rroute(deps, ctx: dict) -> tuple[list[dict], dict]:
    g = ctx["graph"]
    rows = []
    for item in _load("rroute"):
        out, latency, error = await _timed(g.route_node(_fresh_state(item["query"]), deps))
        pred = out["route"] if out else None
        event = out["events"][-1] if out else {}
        rows.append({"id": item["id"], "expected": item["expected_route"], "pred": pred,
                     "ok": pred == item["expected_route"], "method": event.get("method"),
                     "gap": event.get("gap"), "latency_s": latency, "error": error})
        print(f"  {item['id']} {item['expected_route']:>6} → {pred}  {event.get('method')}")
    summary = {"n": len(rows), "accuracy": f"{sum(r['ok'] for r in rows)}/{len(rows)}",
               "chat_as_review": sum(r["expected"] == "chat" and r["pred"] == "review" for r in rows),
               "review_as_chat": sum(r["expected"] == "review" and r["pred"] == "chat" for r in rows),
               "methods": dict(Counter(r["method"] for r in rows)),
               "latency_median_s": _median([r["latency_s"] for r in rows])}
    return rows, summary


async def eval_rclarify(deps, ctx: dict) -> tuple[list[dict], dict]:
    rows = []
    for item in _load("rclarify"):
        out, latency, error = await _timed(_until_assessment(item["query"], deps, ctx["graph"]))
        action = "error" if out is None else ("clarify" if out.get("clarify") else "assess")
        clarify = (out or {}).get("clarify") or {}
        rows.append({"id": item["id"], "expected": item["expected_action"], "pred": action,
                     "ok": action == item["expected_action"], "method": clarify.get("method"),
                     "latency_s": latency, "error": error})
        print(f"  {item['id']} {item['expected_action']:>7} → {action}  {clarify.get('method') or ''}")
    summary = {"n": len(rows), "accuracy": f"{sum(r['ok'] for r in rows)}/{len(rows)}",
               "missed_clarify": sum(r["expected"] == "clarify" and r["pred"] != "clarify" for r in rows),
               "needless_clarify": sum(r["expected"] == "assess" and r["pred"] == "clarify" for r in rows),
               "latency_median_s": _median([r["latency_s"] for r in rows])}
    return rows, summary


async def eval_rjudge(deps, ctx: dict) -> tuple[list[dict], dict]:
    g = ctx["graph"]
    rows = []
    for item in _load("rjudge"):
        state = {**_fresh_state(item["query"]), "assessment": item["assessment"],
                 "collected": item["collected"], "draft": item["draft"]}
        out, latency, error = await _timed(g.validate_node(state, deps))
        passed = out is not None and out["validation_feedback"] is None
        event = out["events"][-1] if out else {}
        rows.append({"id": item["id"], "expected": item["expected"], "defect": item["defect"],
                     "passed": passed, "ok": passed == (item["expected"] == "pass"),
                     "stage": event.get("stage"), "reason": event.get("reason"),
                     "latency_s": latency, "error": error})
        print(f"  {item['id']} {item['expected']:>4} → {'pass' if passed else 'fail'}  {event.get('stage') or ''}")
    bad = [r for r in rows if r["expected"] == "fail"]
    good = [r for r in rows if r["expected"] == "pass"]
    summary = {"n": len(rows), "detected": f"{sum(not r['passed'] for r in bad)}/{len(bad)}",
               "false_reject": f"{sum(not r['passed'] for r in good)}/{len(good)}",
               "stages": dict(Counter(r["stage"] for r in rows if not r["passed"])),
               "latency_median_s": _median([r["latency_s"] for r in rows])}
    return rows, summary


async def eval_rateb(deps, ctx: dict) -> tuple[list[dict], dict]:
    return await eval_rate(deps, ctx, "rateb")


async def eval_rbase(deps, ctx: dict) -> tuple[list[dict], dict]:
    """기준선 — LLM 없이 비슷한 사례의 등급만으로 맞힌다. 에이전트가 사례 검색 위에 무엇을 더했는지 보려고 둔다."""
    g, ratings, retriever = ctx["graph"], ctx["RATINGS"], deps.case_retriever
    if retriever is None:
        sys.exit("rbase 는 CASE_SEARCH=semantic 이어야 한다")
    rows = []
    for kind in ("rate", "rateb"):
        for item in _load(kind):
            retriever.exclude(item["rateno"], item["title"]) if kind == "rateb" else retriever.exclude()
            profile = ctx["extract_profile"](item["message"])
            scope = "genre+platform"
            while True:
                found, used = await retriever.search(item["message"], profile["genre"], profile["platform"], scope)
                if len(found) >= g.MIN_CASES or g.WIDER.get(used) is None:
                    break
                scope = g.WIDER[used]
            votes = Counter(c["rating"] for c in found)
            top = max(votes.values(), default=0)
            vote = next((c["rating"] for c in found if votes[c["rating"]] == top), None)
            gold = item["label"]["rating"]
            rows.append({"set": kind, "id": item["id"], "label": gold, "nn1": found[0]["rating"] if found else None,
                         "vote": vote, "scope": used, "cases": [c["id"] for c in found]})
        retriever.exclude()

    def summarize(kind: str) -> dict:
        group = [r for r in rows if r["set"] == kind]
        majority = max(ratings, key=lambda g: sum(r["label"] == g for r in group))
        return {"n": len(group),
                "nn1": f"{sum(r['nn1'] == r['label'] for r in group)}/{len(group)}",
                "vote5": f"{sum(r['vote'] == r['label'] for r in group)}/{len(group)}",
                "vote5_under": sum(r["vote"] is not None and ratings.index(r["vote"]) < ratings.index(r["label"])
                                   for r in group),
                "always_majority": f"{sum(r['label'] == majority for r in group)}/{len(group)} ({majority})",
                "uniform_random_expected": round(len(group) / len(ratings), 1)}
    return rows, {"A": summarize("rate"), "B": summarize("rateb")}


EVALUATORS = {"rate": eval_rate, "rateb": eval_rateb, "rroute": eval_rroute, "rclarify": eval_rclarify,
              "rjudge": eval_rjudge, "rbase": eval_rbase}


async def _run(kinds: list[str], args: argparse.Namespace) -> None:
    code_root = Path(args.code_root).resolve()
    project = code_root / "project"
    git_state = _git_state(code_root)
    # server import 전에 정한다 — server.py 의 load_dotenv() 는 이미 있는 값을 덮어쓰지 않는다.
    os.environ["LLM_BACKEND"] = args.backend
    os.environ["AGENT_DOMAIN"] = "rating"
    os.environ["LANGCHAIN_PROJECT"] = "capstone-all-total-eval"
    switches = _switches()
    sys.path.insert(0, str(project))
    import server
    from agent.rating import graph
    from agent.rating.assess import predicted_descriptors
    from agent.rating.data import RATINGS
    from agent.rating.profile import extract_profile

    if args.backend == "ollama":
        _check_ollama()
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    ctx = {"graph": graph, "RATINGS": RATINGS, "predicted_descriptors": predicted_descriptors,
           "extract_profile": extract_profile}

    async with server.lifespan(server.app):
        deps = server.app.state.deps
        health = {"llm_backend": server.app.state.llm_backend, "domain": deps.domain,
                  "fast_llm": deps.fast_llm.name, "quality_llm": deps.quality_llm.name,
                  "switches": server.app.state.switches}
        print(f"코드: {_display(code_root)} ({git_state['commit']}) backend={health['llm_backend']} "
              f"switches={json.dumps(health['switches'], ensure_ascii=False)}")
        for kind in kinds:
            print(f"\n== {kind}")
            rows, summary = await EVALUATORS[kind](deps, ctx)
            out = out_dir / f"eval-{kind}_{args.label}_{stamp}.json"
            out.write_text(json.dumps({
                "kind": kind, "label": args.label, "started_at": stamp,
                "evalset": _display(EVALSETS / f"{FILES[kind]}.json"),
                "code_root": _display(code_root), "git": git_state, "switches": switches,
                "health": health, "summary": summary, "results": rows,
            }, ensure_ascii=False, indent=2) + "\n")
            print(f"  요약: {json.dumps(summary, ensure_ascii=False)}")
            print(f"  저장: {_display(out)}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("kind", choices=[*EVALUATORS, "all"])
    parser.add_argument("--label", required=True, help="결과 파일 이름에 들어간다 (예: before, after)")
    parser.add_argument("--backend", default="ollama", choices=["ollama", "fake"],
                        help="fake 는 스크립트 점검용이다. 결과를 근거로 쓰지 않는다")
    parser.add_argument("--code-root", default=str(ROOT),
                        help="잴 코드의 체크아웃 — 그 안의 project/ 를 import 한다")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    args = parser.parse_args()
    kinds = [k for k in EVALUATORS if k != "rbase"] if args.kind == "all" else [args.kind]
    asyncio.run(_run(kinds, args))


if __name__ == "__main__":
    main()
