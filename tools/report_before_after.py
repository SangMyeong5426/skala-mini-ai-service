"""결과 보고서의 Before/After 요약을 runs/ 원자료에서 그대로 읽어 찍는다.

    python3 tools/report_before_after.py

Before = 기능 스위치를 모두 끈 LLM 단독, After = 에이전트(같은 커밋, qwen3). 파일은 docs/04-report.md 부록과 같다.
"""
import json
from pathlib import Path

RUNS = Path(__file__).resolve().parent.parent / "runs"
ITEMS = [
    ("등급 정확도 A (한 문장, 40)", "eval-rate_before_20261020-171219.json", "eval-rate_check2_20261020-192221.json", "accuracy"),
    ("등급 정확도 B (상세, 39)", "eval-rateb_before_20261020-174818.json", "eval-rateb_check2_20261020-193409.json", "accuracy"),
    ("질문 분류 (30)", "eval-rroute_before_20261020-171528.json", "eval-rroute_after_20261020-170106.json", "accuracy"),
    ("되묻기 (12)", "eval-rclarify_before_20261020-171534.json", "eval-rclarify_after_20261020-170112.json", "accuracy"),
    ("오염 보고서 탐지 (7)", "eval-rjudge_before_20261020-171619.json", "eval-rjudge_after_20261020-170331.json", "detected"),
    ("제도 문의 (17)", "eval-rlaw_check-before_20261020-185652.json", "eval-rlaw_check_20261020-184629.json", "ok"),
]
REPEAT = ("e2e_r3-before_20261021-095213.json", "e2e_r3-after_20261021-095349.json")


def summary_value(name: str, key: str) -> str:
    return json.loads((RUNS / name).read_text())["summary"][key]


def median_total(name: str) -> float:
    totals: dict[int, float] = {}
    for row in json.loads((RUNS / name).read_text())["results"]:
        totals[row["repeat"]] = totals.get(row["repeat"], 0.0) + row["latency_s"]
    values = sorted(totals.values())
    return values[len(values) // 2]


def main() -> None:
    print("Before(LLM 단독) → After(에이전트)  [같은 커밋, 스위치만 바꿈, qwen3]")
    for label, before, after, key in ITEMS:
        print(f"- {label}: {summary_value(before, key)} → {summary_value(after, key)}")
    before, after = (median_total(name) for name in REPEAT)
    print(f"- 회귀 쿼리 11턴 합계 (3회 중앙값): {before:.1f}초 → {after:.1f}초")


if __name__ == "__main__":
    main()
