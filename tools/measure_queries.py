"""회귀 쿼리로 에이전트를 실측하고, 두 측정을 비교한다 — Before/After 근거 수집용.

떠 있는 서버(기본 http://127.0.0.1:8100)에 tools/queries.json 의 쿼리를 POST /chat 으로
보내고, 쿼리마다 왕복 지연시간과 응답 metadata(비용·retry·replan·validation 등)를
runs/<label>_<시각>.json 에 남긴다. 서버 코드는 건드리지 않는다.

    project/.venv/bin/python tools/measure_queries.py run --label before
    project/.venv/bin/python tools/measure_queries.py run --label after --repeat 3
    project/.venv/bin/python tools/measure_queries.py compare runs/before_*.json runs/after_*.json

같은 백엔드·같은 모델·같은 repeat 수로 잰 것끼리만 비교한다(compare 가 다르면 경고).
MCP 클라이언트는 프로세스 최초의 모니터링 조회를 일부러 한 번 실패시키므로(재시도 데모),
서버를 새로 띄운 직후에 재야 Before/After 의 retry_count 조건이 같아진다.
"""
import argparse
import json
import statistics
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_QUERIES = ROOT / "tools" / "queries.json"
DEFAULT_OUT_DIR = ROOT / "runs"
METRICS = ["latency_s", "cost_usd", "retry_count", "replan_rounds",
           "validation_attempts", "task_count", "gate_removed"]


def _display(path: Path) -> str:
    """저장소 안이면 상대 경로로, 밖이면(--out-dir 로 다른 곳을 줬을 때) 그대로."""
    path = path.resolve()
    return str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)


def _git_state() -> dict:
    def git(*args: str) -> str:
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                              text=True, check=False).stdout.strip()
    return {"commit": git("rev-parse", "--short", "HEAD") or None,
            "dirty": bool(git("status", "--porcelain"))}


def _measure_turn(client: httpx.Client, message: str, thread_id: str) -> dict:
    started = time.perf_counter()
    try:
        r = client.post("/chat", json={"message": message, "thread_id": thread_id})
        latency = round(time.perf_counter() - started, 3)
        r.raise_for_status()
    except httpx.HTTPError as e:
        return {"ok": False, "latency_s": round(time.perf_counter() - started, 3),
                "error": f"{type(e).__name__}: {e}"}
    body = r.json()
    meta = body.get("metadata", {})
    return {"ok": True, "latency_s": latency, "reply_chars": len(body.get("reply", "")),
            "route": meta.get("route"),
            **{k: meta.get(k) for k in METRICS if k != "latency_s"},
            "langsmith_run_id": meta.get("langsmith_run_id"), "error": None}


def run(args: argparse.Namespace) -> None:
    queries = json.loads(Path(args.queries).read_text())
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    with httpx.Client(base_url=args.base_url, timeout=args.timeout) as client:
        try:
            health = client.get("/health").json()
        except httpx.HTTPError as e:
            sys.exit(f"서버({args.base_url})에 연결할 수 없습니다 — 먼저 sh/run_agent_*.sh 로 띄우세요. ({e})")
        print(f"backend={health.get('llm_backend')} fast={health.get('fast_llm')} "
              f"quality={health.get('quality_llm')} repeat={args.repeat}")

        results = []
        for rep in range(1, args.repeat + 1):
            for q in queries:
                thread_id = f"{args.label}-{stamp}-q{q['id']}-r{rep}"
                for turn, message in enumerate(q["turns"], start=1):
                    row = {"query_id": q["id"], "turn": turn, "repeat": rep,
                           "message": message, "thread_id": thread_id,
                           **_measure_turn(client, message, thread_id)}
                    results.append(row)
                    status = "ok " if row["ok"] else "ERR"
                    print(f"  [{status}] r{rep} q{q['id']}.{turn} {row['latency_s']:>7.2f}s  {message[:40]}")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{args.label}_{stamp}.json"
    out.write_text(json.dumps({
        "label": args.label, "started_at": stamp, "base_url": args.base_url,
        "repeat": args.repeat, "queries_file": _display(Path(args.queries)),
        "git": _git_state(), "health": health, "results": results,
    }, ensure_ascii=False, indent=2) + "\n")
    print(f"\n저장: {_display(out)}\n")
    print(_summary_table(_summarize(results)))


def _summarize(results: list[dict]) -> dict[tuple[int, int], dict]:
    """(query_id, turn) 별로 반복 측정을 모은다. 지연시간은 중앙값, 나머지는 평균."""
    groups: dict[tuple[int, int], list[dict]] = {}
    for r in results:
        groups.setdefault((r["query_id"], r["turn"]), []).append(r)
    summary = {}
    for key, rows in sorted(groups.items()):
        ok = [r for r in rows if r["ok"]]
        s = {"n": len(rows), "errors": len(rows) - len(ok),
             "route": ok[0]["route"] if ok else None}
        for m in METRICS:
            values = [r[m] for r in ok if r.get(m) is not None]
            if not values:
                s[m] = None
            elif m == "latency_s":
                s[m] = round(statistics.median(values), 3)
            else:
                s[m] = round(statistics.fmean(values), 6)
        summary[key] = s
    return summary


def _fmt(v) -> str:
    if v is None:
        return "-"
    return f"{v:g}" if isinstance(v, float) else str(v)


def _summary_table(summary: dict) -> str:
    head = "| # | route | " + " | ".join(METRICS) + " | errors |"
    lines = [head, "|" + " --- |" * (len(METRICS) + 3)]
    for (qid, turn), s in summary.items():
        label = f"{qid}" if turn == 1 else f"{qid}.{turn}"
        lines.append(f"| {label} | {s['route'] or '-'} | "
                     + " | ".join(_fmt(s[m]) for m in METRICS) + f" | {s['errors']} |")
    totals = {m: sum(s[m] for s in summary.values() if s[m] is not None) for m in METRICS}
    lines.append("| **합계** | | " + " | ".join(_fmt(round(totals[m], 6)) for m in METRICS)
                 + f" | {sum(s['errors'] for s in summary.values())} |")
    return "\n".join(lines)


def compare(args: argparse.Namespace) -> None:
    before, after = (json.loads(Path(p).read_text()) for p in (args.before, args.after))
    for field in ("llm_backend", "fast_llm", "quality_llm"):
        if before["health"].get(field) != after["health"].get(field):
            print(f"⚠️  {field} 가 다릅니다: {before['health'].get(field)} → {after['health'].get(field)}")
    if before["repeat"] != after["repeat"]:
        print(f"⚠️  repeat 수가 다릅니다: {before['repeat']} → {after['repeat']}")

    b, a = _summarize(before["results"]), _summarize(after["results"])
    print(f"\nBefore: {before['label']} ({before['git']['commit']}) / "
          f"After: {after['label']} ({after['git']['commit']})\n")
    print("| # | " + " | ".join(f"{m} (B→A)" for m in METRICS) + " |")
    print("|" + " --- |" * (len(METRICS) + 1))
    for key in sorted(set(b) | set(a)):
        qid, turn = key
        label = f"{qid}" if turn == 1 else f"{qid}.{turn}"
        cells = [f"{_fmt(b.get(key, {}).get(m))} → {_fmt(a.get(key, {}).get(m))}" for m in METRICS]
        print(f"| {label} | " + " | ".join(cells) + " |")
    for m in METRICS:
        tb = sum(s[m] for s in b.values() if s[m] is not None)
        ta = sum(s[m] for s in a.values() if s[m] is not None)
        change = f"{(ta - tb) / tb * 100:+.1f}%" if tb else "-"
        print(f"- 합계 {m}: {_fmt(round(tb, 6))} → {_fmt(round(ta, 6))} ({change})")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="떠 있는 서버에 회귀 쿼리를 보내 측정한다")
    p_run.add_argument("--label", required=True, help="결과 파일 이름 앞부분 (예: before, after-rag)")
    p_run.add_argument("--base-url", default="http://127.0.0.1:8100")
    p_run.add_argument("--queries", default=str(DEFAULT_QUERIES))
    p_run.add_argument("--repeat", type=int, default=1, help="같은 쿼리 세트를 몇 번 돌릴지")
    p_run.add_argument("--timeout", type=float, default=300.0, help="요청당 제한 시간(초)")
    p_run.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    p_run.set_defaults(func=run)

    p_cmp = sub.add_parser("compare", help="두 측정 결과를 쿼리별로 비교한다")
    p_cmp.add_argument("before")
    p_cmp.add_argument("after")
    p_cmp.set_defaults(func=compare)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
