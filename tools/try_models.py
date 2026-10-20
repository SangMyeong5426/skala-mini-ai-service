"""답변 작성·검수 판정을 더 작은 모델로 바꿔도 되는지 시험한다 — 성능 개선 시도(결정 0008).

    project/.venv/bin/python tools/try_models.py
    project/.venv/bin/python tools/try_models.py --writers qwen3:8b qwen3.5:2b --judges qwen3:8b qwen3.5:2b qwen3:0.6b

장애 질문 1건(13~20초)의 대부분은 qwen3:8b 두 번이다 — 답변 작성 약 10초, 검수 판정 약 3.5초.
더 작은 모델로 바꾸면 빨라지지만 품질이 떨어질 수 있어, 채택 기준을 시험 전에 정해 두고 판정한다.

1. 작성 : 후보 모델로 judge 세트 정상 5건의 질문·수집 사실에 보고서를 쓰고, 기준 판정기(qwen3:8b)로 검수한다.
          지연·번호 형식·수치 대조·검수 결과·초안 본문을 남긴다.
2. 판정 : 후보 모델을 판정기로 써서 judge 세트 12건(정상 5 · 오염 7)을 채점한다.

채택 기준
- 판정 : 오염 탐지 ≥ 6/7, 정상 오탐 0/5 (지금 qwen3:8b 수준)
- 작성 : 5건 모두 번호 형식·수치 대조·기준 판정 통과, **하지 않은 조치를 했다고 쓰지 않을 것**.
         에이전트는 조회만 하고 조치는 하지 않는다. "재시작했습니다" 같은 완료형 주장은 보고서를 거짓으로 만든다.
         완료형 표현은 아래 정규식으로 표시만 하고, 판단은 사람이 초안을 읽고 한다.

모든 호출은 think=false(지금 운영 설정)다. 결과는 runs/try-models_<시각>.json.
"""
import argparse
import asyncio
import json
import re
import sys
import time
from datetime import datetime

from measure_queries import ROOT, _display, _git_state

PROJECT = ROOT / "project"
sys.path.insert(0, str(PROJECT))
from agent.ollama_llm import OllamaQualityLLM  # noqa: E402
from agent.validator import GroundedValidator, ungrounded_numbers  # noqa: E402

JUDGE_SET = ROOT / "tools" / "evalsets" / "judge.json"
REFERENCE_JUDGE = "qwen3:8b"
# 조치를 이미 했다고 말하는 완료형 서술 — 표시용 휴리스틱이다. 최종 판단은 사람이 한다.
COMPLETED_ACTION = re.compile(r"(했습니다|하였습니다|되었습니다|됐습니다|막았습니다|확보했습니다|조정했습니다|"
                              r"시도했습니다|완료|해결되었)")


def _collected(item: dict) -> list[dict]:
    out = []
    for e in item["collected"]:
        if e["source"] == "runbook":
            out.append({"source": "runbook",
                        "data": (PROJECT / "data" / "runbooks" / f"{e['ref']}.md").read_text()})
        else:
            out.append(e)
    return out


def try_writers(models: list[str], cases: list[dict]) -> dict:
    referee = GroundedValidator(OllamaQualityLLM(REFERENCE_JUDGE, usd_per_1k_tokens=0.0, think=False))
    report = {}
    for model in models:
        writer = OllamaQualityLLM(model, usd_per_1k_tokens=0.0, think=False)
        rows = []
        for c in (c for c in cases if c["expected"] == "pass"):
            collected = _collected(c)
            started = time.perf_counter()
            draft, usage = asyncio.run(writer.write(c["query"], collected, 1, None))
            latency = round(time.perf_counter() - started, 3)
            verdict = referee.check(c["query"], collected, draft)
            rows.append({"id": c["id"], "latency_s": latency, "tokens": usage.get("tokens"),
                         "numbered": "1)" in draft,
                         "ungrounded": ungrounded_numbers(draft, collected, c["query"]),
                         "referee_ok": verdict["ok"], "referee_stage": verdict["stage"],
                         "completed_action_phrases": COMPLETED_ACTION.findall(draft), "draft": draft})
            print(f"  작성 {model:11} {c['id']} {latency:5.1f}s 검수={'통과' if verdict['ok'] else '반려'} "
                  f"완료형={rows[-1]['completed_action_phrases']}", flush=True)
        report[model] = {
            "latency_total_s": round(sum(r["latency_s"] for r in rows), 1),
            "numbered": f"{sum(r['numbered'] for r in rows)}/{len(rows)}",
            "grounded": f"{sum(not r['ungrounded'] for r in rows)}/{len(rows)}",
            "referee_pass": f"{sum(r['referee_ok'] for r in rows)}/{len(rows)}",
            "drafts_with_completed_action_phrases": sum(bool(r["completed_action_phrases"]) for r in rows),
            "rows": rows}
    return report


def try_judges(models: list[str], cases: list[dict]) -> dict:
    report = {}
    for model in models:
        validator = GroundedValidator(OllamaQualityLLM(model, usd_per_1k_tokens=0.0, think=False))
        rows = []
        for c in cases:
            started = time.perf_counter()
            out = validator.check(c["query"], _collected(c), c["draft"])
            got = "pass" if out["ok"] else "fail"
            rows.append({"id": c["id"], "expected": c["expected"], "got": got, "stage": out["stage"],
                         "latency_s": round(time.perf_counter() - started, 3)})
        bad = [r for r in rows if r["expected"] == "fail"]
        good = [r for r in rows if r["expected"] == "pass"]
        judged = [r["latency_s"] for r in rows if r["stage"] in (None, "judge")]
        report[model] = {"bad_detected": f"{sum(r['got'] == 'fail' for r in bad)}/{len(bad)}",
                         "good_false_reject": f"{sum(r['got'] == 'fail' for r in good)}/{len(good)}",
                         "judge_latency_median_s": sorted(judged)[len(judged) // 2] if judged else None,
                         "rows": rows}
        print(f"  판정 {model:11} 오염 탐지 {report[model]['bad_detected']} · 정상 오탐 "
              f"{report[model]['good_false_reject']} · 판정 지연 중앙값 {report[model]['judge_latency_median_s']}s",
              flush=True)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--writers", nargs="+", default=["qwen3:8b", "qwen3.5:2b"])
    parser.add_argument("--judges", nargs="+", default=["qwen3:8b", "qwen3.5:2b", "qwen3:0.6b"])
    args = parser.parse_args()

    cases = json.loads(JUDGE_SET.read_text())
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    git_state = _git_state()
    print("== 작성 (기준 판정기 qwen3:8b)")
    writers = try_writers(args.writers, cases)
    print("== 판정")
    judges = try_judges(args.judges, cases)
    out = ROOT / "runs" / f"try-models_{stamp}.json"
    out.write_text(json.dumps({"started_at": stamp, "git": git_state, "think": False,
                               "reference_judge": REFERENCE_JUDGE, "writers": writers, "judges": judges},
                              ensure_ascii=False, indent=2) + "\n")
    print(f"\n저장: {_display(out)}")
    for model, r in writers.items():
        print(f"작성 {model}: 합계 {r['latency_total_s']}s · 번호 {r['numbered']} · 수치 대조 {r['grounded']} · "
              f"기준 판정 {r['referee_pass']} · 완료형 표현 초안 {r['drafts_with_completed_action_phrases']}건")


if __name__ == "__main__":
    main()
