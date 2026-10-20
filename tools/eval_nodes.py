"""그래프 노드를 서버 없이 직접 불러 라벨 평가 세트로 채점한다 — 개선 항목의 Before/After.

    project/.venv/bin/python tools/eval_nodes.py route  --label before
    project/.venv/bin/python tools/eval_nodes.py target --label before
    project/.venv/bin/python tools/eval_nodes.py judge  --label before
    project/.venv/bin/python tools/eval_nodes.py write  --label before
    project/.venv/bin/python tools/eval_nodes.py runbook --label before
    project/.venv/bin/python tools/eval_nodes.py all    --label before

| 하위 명령 | 부르는 곳              | 평가 세트                          | 채점                                 |
| route     | route_node             | tools/evalsets/route.json          | chat/incident 분류 정확도            |
| target    | plan_node              | tools/evalsets/target.json         | 대상 시스템 일치, 되묻기, 엉뚱한 진단 |
| judge     | validate_node          | tools/evalsets/judge.json          | 오염 초안 탐지율, 정상 초안 오탐률    |
| write     | quality_llm.write      | judge.json 정상 5건의 질문·수집 사실 | 답변 작성 LLM 호출 지연·토큰·완료 여부 |
| runbook   | replan_check_node      | tools/evalsets/runbook.json        | 고른 runbook(incident_type) 정답률     |

의존성은 server.py 의 lifespan 을 그대로 실행해 얻는다(LLM·MCP 서버·세션 저장소). 개선 코드가
SupervisorDeps 구성이나 노드 안쪽을 바꿔도 이 스크립트는 고치지 않는다. 대신 개선 코드는 아래
채점 약속을 지킨다.

- route  : route_node 가 돌려준 상태의 "route" 값을 정답과 비교한다.
- target : plan_node 가 돌려준 research task 의 target 목록. **하나도 없으면 되묻기(clarify)로 본다.**
- judge  : validate_node 가 돌려준 validation_feedback 이 None 이면 합격으로 본다.
- write  : write_node 는 LangGraph 실행 안에서만 쓸 수 있는 스트림 writer 를 꺼내므로 그래프 밖에서
           부를 수 없다. 재려는 것은 LLM 호출 자체라 quality_llm.write 를 직접 부르고, --cap 초를
           넘기면 취소한다(연결이 끊기며 ollama 생성도 멈춘다).
- runbook: replan_check_node 가 추가한 gap task(kind=runbook)의 target. 수집 사실은 모니터링 기준값
           (data/monitoring.json, 지터 없음)으로 만든다 — research 직후의 상태를 재현한다.

--code-root 로 다른 체크아웃(예: scripts/measure-at 이 만든 git worktree)의 project/ 코드를 잴 수 있다.
평가 세트와 채점은 늘 이 파일 옆의 것을 쓴다 — Before 와 After 를 같은 입력으로 재기 위해서다.
결과는 runs/eval-<하위 명령>_<label>_<시각>.json 에 남는다.
"""
import argparse
import asyncio
import json
import os
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path

import httpx
from measure_queries import ROOT, _display, _git_state, _switches

EVALSETS = ROOT / "tools" / "evalsets"
DEFAULT_OUT_DIR = ROOT / "runs"
KINDS = ["route", "target", "judge", "write", "runbook"]


def _load(kind: str) -> list[dict]:
    return json.loads((EVALSETS / f"{kind}.json").read_text())


def _median(values: list[float]) -> float | None:
    return round(statistics.median(values), 3) if values else None


async def _timed(coro) -> tuple[dict | None, float, str | None]:
    """노드 하나를 실행해 (결과, 걸린 시간, 오류)를 돌려준다.

    노드가 예외를 내도 평가를 멈추지 않는다 — 소형 모델의 thinking 폭주로 LLM 호출이
    timeout 에 걸리는 것도 그 버전의 실제 동작이라 결과로 남긴다(오답으로 센다).
    """
    started = time.perf_counter()
    try:
        out, error = await coro, None
    except Exception as e:  # noqa: BLE001 — 어떤 실패든 행 하나로 기록한다
        out, error = None, f"{type(e).__name__}: {e}"[:300]
    return out, round(time.perf_counter() - started, 3), error


def _fresh_state(query: str) -> dict:
    return {"query": query, "thread_id": "eval", "history": [], "events": [], "cost_usd": 0.0}


def _collected(entries: list[dict], project: Path) -> list[dict]:
    """평가 세트의 runbook 은 본문 대신 이름(ref)으로 적혀 있다 — 잴 코드의 파일에서 읽어 채운다."""
    out = []
    for e in entries:
        if e["source"] == "runbook" and "ref" in e:
            text = (project / "data" / "runbooks" / f"{e['ref']}.md").read_text()
            out.append({"source": "runbook", "data": text})
        else:
            out.append({"source": e["source"], "data": e["data"]})
    return out


# ── route ─────────────────────────────────────────────────────────────────
async def eval_route(deps, ctx: dict) -> tuple[list[dict], dict]:
    from agent.graph import route_node

    rows = []
    for item in _load("route"):
        out, latency, error = await _timed(route_node(_fresh_state(item["query"]), deps))
        got = (out or {}).get("route")
        rows.append({**item, "got": got, "latency_s": latency, "error": error,
                     "ok": got == item["expected_route"]})
        _print_row(rows[-1], f"{item['expected_route']:8} → {got}")

    by_class = {}
    for label in ("chat", "incident"):
        group = [r for r in rows if r["expected_route"] == label]
        by_class[label] = f"{sum(r['ok'] for r in group)}/{len(group)}"
    summary = {"accuracy": round(sum(r["ok"] for r in rows) / len(rows), 3),
               "correct": f"{sum(r['ok'] for r in rows)}/{len(rows)}",
               "chat_correct": by_class["chat"], "incident_correct": by_class["incident"],
               "errors": sum(r["error"] is not None for r in rows),
               "latency_median_s": _median([r["latency_s"] for r in rows])}
    return rows, summary


# ── target ────────────────────────────────────────────────────────────────
async def eval_target(deps, ctx: dict) -> tuple[list[dict], dict]:
    from agent.graph import plan_node

    rows = []
    for item in _load("target"):
        out, latency, error = await _timed(plan_node(_fresh_state(item["query"]), deps))
        targets = sorted({t["target"] for t in (out or {}).get("tasks", [])
                          if t.get("agent") == "research" and t.get("target")})
        # 노드가 실패하면 되묻지도 진단하지도 못한 것이다 — 어느 정답과도 맞지 않는다.
        action = "error" if error else ("diagnose" if targets else "clarify")
        expected = sorted(item["expected_targets"])
        if item["expected_action"] == "clarify":
            ok = action == "clarify"
        else:
            ok = action == "diagnose" and targets == expected
        # 엉뚱한 진단: 진단을 내렸는데 되물었어야 했거나, 정답에 없는 시스템을 조사했다.
        off_target = action == "diagnose" and (
            item["expected_action"] == "clarify" or any(t not in expected for t in targets))
        rows.append({**item, "got_action": action, "got_targets": targets,
                     "ok": ok, "off_target": off_target, "latency_s": latency, "error": error})
        _print_row(rows[-1], f"{item['expected_action']:8} {expected} → {action} {targets}")

    diagnose = [r for r in rows if r["expected_action"] == "diagnose"]
    clarify = [r for r in rows if r["expected_action"] == "clarify"]
    summary = {"accuracy": round(sum(r["ok"] for r in rows) / len(rows), 3),
               "correct": f"{sum(r['ok'] for r in rows)}/{len(rows)}",
               "diagnose_correct": f"{sum(r['ok'] for r in diagnose)}/{len(diagnose)}",
               "clarify_correct": f"{sum(r['ok'] for r in clarify)}/{len(clarify)}",
               "off_target": sum(r["off_target"] for r in rows),
               "errors": sum(r["error"] is not None for r in rows),
               "latency_median_s": _median([r["latency_s"] for r in rows]),
               "latency_max_s": max(r["latency_s"] for r in rows)}
    return rows, summary


# ── judge ─────────────────────────────────────────────────────────────────
async def eval_judge(deps, ctx: dict) -> tuple[list[dict], dict]:
    from agent.graph import validate_node

    rows = []
    for item in _load("judge"):
        state = {**_fresh_state(item["query"]),
                 "collected": _collected(item["collected"], ctx["project"]),
                 "draft": item["draft"], "validation_attempts": 0}
        out, latency, error = await _timed(validate_node(state, deps))
        if error:
            got = "error"
        else:
            got = "pass" if out.get("validation_feedback") is None else "fail"
        rows.append({"id": item["id"], "expected": item["expected"], "defect": item["defect"],
                     "got": got, "ok": got == item["expected"],
                     "feedback": (out or {}).get("validation_feedback"),
                     "latency_s": latency, "error": error})
        _print_row(rows[-1], f"{item['expected']} → {got}  {item['defect'] or ''}")

    bad = [r for r in rows if r["expected"] == "fail"]
    good = [r for r in rows if r["expected"] == "pass"]
    summary = {"bad_detected": f"{sum(r['got'] == 'fail' for r in bad)}/{len(bad)}",
               "good_false_reject": f"{sum(r['got'] == 'fail' for r in good)}/{len(good)}",
               "accuracy": round(sum(r["ok"] for r in rows) / len(rows), 3),
               "errors": sum(r["error"] is not None for r in rows),
               "latency_median_s": _median([r["latency_s"] for r in rows])}
    return rows, summary


# ── write ─────────────────────────────────────────────────────────────────
async def eval_write(deps, ctx: dict) -> tuple[list[dict], dict]:
    rows = []
    for item in [c for c in _load("judge") if c["expected"] == "pass"]:
        collected = _collected(item["collected"], ctx["project"])
        out, latency, error = await _timed(asyncio.wait_for(
            deps.quality_llm.write(item["query"], collected, 1, None), timeout=ctx["cap"]))
        draft, usage = out if out else ("", {})
        rows.append({"id": item["id"], "query": item["query"], "ok": error is None,
                     "latency_s": latency, "tokens": usage.get("tokens"),
                     "draft_chars": len(draft), "numbered": "1)" in draft,
                     "draft": draft, "error": error})
        _print_row(rows[-1], f"{len(draft)}자 tokens={usage.get('tokens')}")

    done = [r for r in rows if r["ok"]]
    summary = {"completed": f"{len(done)}/{len(rows)}",
               "timeouts": sum((r["error"] or "").startswith("TimeoutError") for r in rows),
               "cap_s": ctx["cap"],
               "latency_median_s": _median([r["latency_s"] for r in rows]),
               "latency_max_s": max(r["latency_s"] for r in rows),
               "tokens_median": _median([r["tokens"] for r in done if r["tokens"]]),
               "numbered": f"{sum(r['numbered'] for r in done)}/{len(done)}"}
    return rows, summary


# ── runbook ───────────────────────────────────────────────────────────────
async def eval_runbook(deps, ctx: dict) -> tuple[list[dict], dict]:
    from agent.graph import replan_check_node

    monitoring = json.loads((ctx["project"] / "data" / "monitoring.json").read_text())
    rows = []
    for item in _load("runbook"):
        collected = [{"source": "monitoring", "data": {
            "system_name": s, "status": monitoring[s]["status"],
            "cpu_percent": monitoring[s]["cpu_base"], "memory_percent": monitoring[s]["memory_base"],
            "alerts": monitoring[s].get("alerts", [])}} for s in item["targets"]]
        tasks = [{"id": f"task-{i}", "agent": "research", "kind": "monitoring", "target": s,
                  "status": "done"} for i, s in enumerate(item["targets"])]
        state = {**_fresh_state(item["query"]), "tasks": tasks, "collected": collected,
                 "replan_rounds": 0}
        out, latency, error = await _timed(replan_check_node(state, deps))
        gap = next((t for t in (out or {}).get("tasks", []) if t.get("kind") == "runbook"), None)
        got = gap["target"] if gap else None
        rows.append({**item, "got": got, "ok": got == item["expected_runbook"],
                     "latency_s": latency, "error": error})
        _print_row(rows[-1], f"{item['expected_runbook']:15} → {got}")

    summary = {"accuracy": round(sum(r["ok"] for r in rows) / len(rows), 3),
               "correct": f"{sum(r['ok'] for r in rows)}/{len(rows)}",
               "errors": sum(r["error"] is not None for r in rows),
               "latency_median_s": _median([r["latency_s"] for r in rows])}
    return rows, summary


EVALUATORS = {"route": eval_route, "target": eval_target, "judge": eval_judge,
              "write": eval_write, "runbook": eval_runbook}


def _print_row(row: dict, detail: str) -> None:
    mark = "ok " if row["ok"] else "XX "
    error = f"  ! {row['error']}" if row.get("error") else ""
    print(f"  [{mark}] {row['id']:4} {row['latency_s']:>6.2f}s  {detail}{error}", flush=True)


# ── 실행 ──────────────────────────────────────────────────────────────────
def _check_ollama() -> None:
    try:
        httpx.get("http://127.0.0.1:11434/api/tags", timeout=2.0).raise_for_status()
    except httpx.HTTPError:
        sys.exit("ollama serve 가 응답하지 않습니다 — project/ 에서 bash sh/run_agent_ollma.sh 로 "
                 "백엔드를 띄워 두거나 `ollama serve` 를 실행하세요.")


async def _run(kinds: list[str], args: argparse.Namespace) -> None:
    code_root = Path(args.code_root).resolve()
    project = code_root / "project"
    git_state = _git_state(code_root)   # 시작 시점 — 측정 도중 파일이 바뀌어도 기록이 흔들리지 않게
    # server import 전에 정한다 — server.py 의 load_dotenv() 는 이미 있는 값을 덮어쓰지 않는다.
    os.environ["LLM_BACKEND"] = args.backend
    os.environ["LANGCHAIN_PROJECT"] = "capstone-all-total-eval"
    switches = _switches()
    sys.path.insert(0, str(project))
    import server

    if args.backend == "ollama":
        _check_ollama()
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    ctx = {"project": project, "cap": args.cap}

    async with server.lifespan(server.app):
        deps = server.app.state.deps
        health = {"llm_backend": server.app.state.llm_backend,
                  "fast_llm": deps.fast_llm.name, "quality_llm": deps.quality_llm.name,
                  # 서버가 실제로 켠 개선 스위치 (base 코드에는 없다)
                  "switches": getattr(server.app.state, "switches", None)}
        print(f"코드: {_display(code_root)} ({git_state['commit']}) backend={health['llm_backend']} "
              f"fast={health['fast_llm']} quality={health['quality_llm']}")
        for kind in kinds:
            print(f"\n== {kind}")
            rows, summary = await EVALUATORS[kind](deps, ctx)
            out = out_dir / f"eval-{kind}_{args.label}_{stamp}.json"
            out.write_text(json.dumps({
                "kind": kind, "label": args.label, "started_at": stamp,
                "evalset": _display(EVALSETS / f"{'judge' if kind == 'write' else kind}.json"),
                "code_root": _display(code_root), "git": git_state, "switches": switches,
                "health": health, "summary": summary, "results": rows,
            }, ensure_ascii=False, indent=2) + "\n")
            print(f"  요약: {json.dumps(summary, ensure_ascii=False)}")
            print(f"  저장: {_display(out)}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("kind", choices=[*KINDS, "all"])
    parser.add_argument("--label", required=True, help="결과 파일 이름에 들어간다 (예: before, step2)")
    parser.add_argument("--backend", default="ollama", choices=["ollama", "fake"],
                        help="fake 는 스크립트 점검용이다. 결과를 근거로 쓰지 않는다")
    parser.add_argument("--code-root", default=str(ROOT),
                        help="잴 코드의 체크아웃 — 그 안의 project/ 를 import 한다")
    parser.add_argument("--cap", type=float, default=300.0,
                        help="write 의 LLM 호출 하나에 주는 최대 시간(초). 넘기면 취소하고 timeout 으로 센다")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    args = parser.parse_args()
    asyncio.run(_run(KINDS if args.kind == "all" else [args.kind], args))


if __name__ == "__main__":
    main()
