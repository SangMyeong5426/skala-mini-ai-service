"""회귀 쿼리로 에이전트를 실측하고, 두 측정을 비교한다 — Before/After 근거 수집용.

떠 있는 서버(기본 http://127.0.0.1:8100)에 tools/queries.json 의 쿼리를 POST /chat 으로
보내고, 쿼리마다 왕복 지연시간과 응답 metadata(비용·retry·replan·validation 등)를
runs/<label>_<시각>.json 에 남긴다. 서버 코드는 건드리지 않는다.

    project/.venv/bin/python tools/measure_queries.py run --label before
    project/.venv/bin/python tools/measure_queries.py run --label after --repeat 3
    project/.venv/bin/python tools/measure_queries.py compare runs/before_*.json runs/after_*.json

--spawn 을 주면 쿼리마다 서버를 새로 띄우고 끝나면 내린다(--code-root 의 project/ 코드로).
클라이언트가 timeout 으로 끊어도 서버는 그 요청을 끝까지 처리하므로, 한 서버로 이어서 재면
앞 쿼리의 LLM 생성이 뒤 쿼리를 막는다. 쿼리마다 프로세스를 내리면 그 생성도 함께 취소돼
쿼리끼리 영향을 주지 않는다. scripts/measure-at 이 이 방식으로 부른다.

같은 백엔드·같은 모델·같은 repeat 수로 잰 것끼리만 비교한다(compare 가 다르면 경고).
MCP 클라이언트는 프로세스 최초의 모니터링 조회를 일부러 한 번 실패시키므로(재시도 데모),
서버를 새로 띄운 직후에 재야 retry_count 조건이 같아진다. --spawn 이면 장애 질문마다 1 이다.
"""
import argparse
import json
import os
import signal
import statistics
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import httpx

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_QUERIES = ROOT / "tools" / "queries.json"
DEFAULT_OUT_DIR = ROOT / "runs"
METRICS = ["latency_s", "cost_usd", "retry_count", "replan_rounds",
           "validation_attempts", "task_count", "gate_removed"]
# 에이전트 동작을 정하는 경로. 측정 시점에 이 경로가 base 태그와 같으면 Before 로 쓸 수 있다.
AGENT_PATHS = ["project/agent", "project/server.py", "project/mcp_server.py",
               "project/mcp_server_docs.py", "project/data"]
# 개선 스위치(docs/03-design.md). 결과 파일에 그대로 남겨 어떤 조합으로 쟀는지 보이게 한다.
SWITCHES = ["LLM_BACKEND", "OLLAMA_THINK", "OLLAMA_THINK_CHAT", "ROUTER", "TARGET_RESOLVER", "VALIDATOR",
            "RUNBOOK_SELECTOR"]


def _display(path: Path) -> str:
    """저장소 안이면 상대 경로로, 밖이면(--out-dir 로 다른 곳을 줬을 때) 그대로."""
    path = path.resolve()
    return str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)


def _git_state(root: Path = ROOT) -> dict:
    """root 체크아웃의 커밋과, 에이전트 코드가 base 태그와 같은지.

    측정을 시작할 때 한 번 부른다 — 끝날 때 부르면 측정 도중 바뀐 파일이 기록에 섞인다.
    """
    def git(*args: str) -> str:
        return subprocess.run(["git", *args], cwd=root, capture_output=True,
                              text=True, check=False).stdout.strip()
    # 작업 트리(커밋 안 한 변경 포함)를 base 와 비교한다. 0=같음, 1=다름, 그 외=base 태그 없음.
    diff = subprocess.run(["git", "diff", "--quiet", "base", "--", *AGENT_PATHS],
                          cwd=root, capture_output=True, check=False).returncode
    untracked = git("ls-files", "--others", "--exclude-standard", "--", *AGENT_PATHS)
    return {"commit": git("rev-parse", "--short", "HEAD") or None,
            "dirty": bool(git("status", "--porcelain")),
            "agent_matches_base": None if diff not in (0, 1) else (diff == 0 and not untracked)}


def _switches() -> dict:
    return {k: os.environ.get(k) for k in SWITCHES}


class _Server:
    """--spawn 용. <code-root>/project 에서 server:app 을 새 프로세스로 띄우고 내린다."""

    def __init__(self, project_dir: Path, port: int, log_path: Path):
        env = {**os.environ}
        env.setdefault("LLM_BACKEND", "ollama")
        env.setdefault("SUPERVISOR_VERSION", "v2")
        self._log = open(log_path, "a")  # noqa: SIM115 — stop() 에서 닫는다
        # MCP 서버 자식 프로세스까지 한 번에 내리려고 프로세스 그룹을 따로 둔다.
        self.proc = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "server:app", "--host", "127.0.0.1",
             "--port", str(port), "--log-level", "warning"],
            cwd=project_dir, env=env, stdout=self._log, stderr=subprocess.STDOUT,
            start_new_session=True)

    def wait_ready(self, client: httpx.Client, timeout: float = 90.0) -> dict:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.proc.poll() is not None:
                raise RuntimeError(f"서버가 기동 중 종료됐습니다 (exit {self.proc.returncode}) "
                                   f"— 로그: {self._log.name}")
            try:
                return client.get("/health", timeout=2.0).json()
            except httpx.HTTPError:
                time.sleep(0.5)
        raise RuntimeError(f"서버가 {timeout:.0f}초 안에 뜨지 않았습니다 — 로그: {self._log.name}")

    def stop(self) -> None:
        """SIGTERM 후 5초 안에 안 내려가면 SIGKILL. 남은 LLM 생성은 연결이 끊기며 취소된다."""
        try:
            os.killpg(self.proc.pid, signal.SIGTERM)
            self.proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(self.proc.pid, signal.SIGKILL)
            self.proc.wait()
        except ProcessLookupError:
            pass
        self._log.close()


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
            "reply": body.get("reply", ""), "route": meta.get("route"),
            **{k: meta.get(k) for k in METRICS if k != "latency_s"},
            "langsmith_run_id": meta.get("langsmith_run_id"), "error": None}


def run(args: argparse.Namespace) -> None:
    queries = json.loads(Path(args.queries).read_text())
    code_root = Path(args.code_root).resolve()
    git_state, switches = _git_state(code_root), _switches()
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    port = urlparse(args.base_url).port
    log_path = Path(tempfile.gettempdir()) / f"skala-measure-{args.label}-{stamp}.log"

    health = None
    results = []
    with httpx.Client(base_url=args.base_url, timeout=args.timeout) as client:
        if not args.spawn:
            try:
                health = client.get("/health").json()
            except httpx.HTTPError as e:
                sys.exit(f"서버({args.base_url})에 연결할 수 없습니다 — 먼저 sh/run_agent_*.sh 로 띄우세요. ({e})")
            print(f"backend={health.get('llm_backend')} fast={health.get('fast_llm')} "
                  f"quality={health.get('quality_llm')} repeat={args.repeat}")
        else:
            print(f"쿼리마다 서버를 새로 띄운다: {_display(code_root)}/project :{port} "
                  f"(서버 로그 {log_path})")

        for rep in range(1, args.repeat + 1):
            for q in queries:
                server = _Server(code_root / "project", port, log_path) if args.spawn else None
                try:
                    if server:
                        h = server.wait_ready(client)
                        if health is None:
                            health = h
                            print(f"backend={h.get('llm_backend')} fast={h.get('fast_llm')} "
                                  f"quality={h.get('quality_llm')} repeat={args.repeat}")
                    thread_id = f"{args.label}-{stamp}-q{q['id']}-r{rep}"
                    for turn, message in enumerate(q["turns"], start=1):
                        row = {"query_id": q["id"], "turn": turn, "repeat": rep,
                               "message": message, "thread_id": thread_id,
                               **_measure_turn(client, message, thread_id)}
                        results.append(row)
                        status = "ok " if row["ok"] else "ERR"
                        print(f"  [{status}] r{rep} q{q['id']}.{turn} {row['latency_s']:>7.2f}s  "
                              f"{message[:40]}", flush=True)
                finally:
                    if server:
                        server.stop()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{args.label}_{stamp}.json"
    out.write_text(json.dumps({
        "label": args.label, "started_at": stamp, "base_url": args.base_url,
        "spawn": args.spawn, "timeout_s": args.timeout, "repeat": args.repeat,
        "queries_file": _display(Path(args.queries)), "code_root": _display(code_root),
        "git": git_state, "switches": switches, "health": health, "results": results,
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
    for field in ("repeat", "spawn", "timeout_s"):
        if before.get(field) != after.get(field):
            print(f"⚠️  {field} 가 다릅니다: {before.get(field)} → {after.get(field)}")

    b, a = _summarize(before["results"]), _summarize(after["results"])
    print(f"\nBefore: {before['label']} ({before['git']['commit']}) / "
          f"After: {after['label']} ({after['git']['commit']})\n")
    print("| # | " + " | ".join(f"{m} (B→A)" for m in METRICS) + " | errors (B→A) |")
    print("|" + " --- |" * (len(METRICS) + 2))
    for key in sorted(set(b) | set(a)):
        qid, turn = key
        label = f"{qid}" if turn == 1 else f"{qid}.{turn}"
        cells = [f"{_fmt(b.get(key, {}).get(m))} → {_fmt(a.get(key, {}).get(m))}" for m in METRICS]
        errors = f"{b.get(key, {}).get('errors', '-')} → {a.get(key, {}).get('errors', '-')}"
        print(f"| {label} | " + " | ".join(cells) + f" | {errors} |")
    for m in METRICS:
        tb = sum(s[m] for s in b.values() if s[m] is not None)
        ta = sum(s[m] for s in a.values() if s[m] is not None)
        change = f"{(ta - tb) / tb * 100:+.1f}%" if tb else "-"
        print(f"- 합계 {m}: {_fmt(round(tb, 6))} → {_fmt(round(ta, 6))} ({change})")
    eb = sum(s["errors"] for s in b.values())
    ea = sum(s["errors"] for s in a.values())
    print(f"- 오류(timeout 포함): {eb} → {ea}")
    if before.get("repeat", 1) > 1 or after.get("repeat", 1) > 1:
        print("\n회차별 11턴 합계 지연 (오류 난 턴도 걸린 시간을 더한다 — 사용자가 기다린 시간):")
        for name, data in (("Before", before), ("After", after)):
            print(f"- {name}: {_repeat_totals(data['results'])}")


def _repeat_totals(results: list[dict]) -> str:
    """회차마다 모든 턴의 지연을 더하고, 회차 사이 편차를 보인다 — 1회 측정의 흔들림을 가늠하는 용도."""
    totals: dict[int, float] = {}
    for r in results:
        totals[r["repeat"]] = totals.get(r["repeat"], 0.0) + r["latency_s"]
    values = [round(totals[k], 1) for k in sorted(totals)]
    line = " · ".join(f"r{k} {v:g}초" for k, v in zip(sorted(totals), values, strict=True))
    if len(values) > 1:
        line += (f"  (중앙값 {statistics.median(values):g}초, 범위 {min(values):g}~{max(values):g}초, "
                 f"최대/최소 {max(values) / min(values):.2f}배)")
    return line


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
    p_run.add_argument("--code-root", default=str(ROOT),
                       help="측정하는 코드의 체크아웃 (git 상태 기록, --spawn 의 서버 코드)")
    p_run.add_argument("--spawn", action="store_true",
                       help="쿼리마다 --code-root 의 서버를 새로 띄우고 내린다 (--base-url 의 포트)")
    p_run.set_defaults(func=run)

    p_cmp = sub.add_parser("compare", help="두 측정 결과를 쿼리별로 비교한다")
    p_cmp.add_argument("before")
    p_cmp.add_argument("after")
    p_cmp.set_defaults(func=compare)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
