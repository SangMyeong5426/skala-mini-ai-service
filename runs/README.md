# runs/

[`tools/measure_queries.py`](../tools/measure_queries.py)가 남기는 실측 원자료다.
**커밋한다** — Before/After 표([`docs/02-measurement.md`](../docs/02-measurement.md))의 근거라서다.

- 파일 이름: `<label>_<YYYYmmdd-HHMMSS>.json`
- 손으로 고치지 않는다. 잘못 잰 파일은 지우고 다시 잰다.
- fake 백엔드로 잰 파일은 남기지 않는다(`--out-dir`로 다른 곳에 둔다). Before/After 근거가 아니다.
