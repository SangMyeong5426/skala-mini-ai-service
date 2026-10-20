# Before/After 실측

평가 기준 "같은 입력으로 개선 전/후를 돌려 수치로 차이를 제시"의 근거를 모은다.
**직접 실행해 얻은 값만 적는다.** 원자료는 [`runs/`](../runs/)에 있고, 이 문서의 표는
그 파일에서 옮긴 것이다. 표마다 원자료 파일명을 적는다.

## 측정 방법

1. 서버를 **새로** 띄운다. MCP 클라이언트가 프로세스 첫 모니터링 조회를 일부러 한 번
   실패시키므로(재시도 데모), 띄운 직후에 재야 Before와 After의 retry 조건이 같다.

   ```bash
   cd project && bash sh/run_agent_ollma.sh
   ```

2. 다른 터미널에서 회귀 쿼리([`tools/queries.json`](../tools/queries.json), 10개 · 11턴)를 보낸다.

   ```bash
   project/.venv/bin/python tools/measure_queries.py run --label before --repeat 3
   ```

3. 개선 후 같은 백엔드·모델·repeat로 다시 재고 비교한다.

   ```bash
   project/.venv/bin/python tools/measure_queries.py compare runs/before_<시각>.json runs/after_<시각>.json
   ```

| 지표 | 뜻 | 출처 |
| --- | --- | --- |
| `latency_s` | `POST /chat` 왕복 시간(초). 반복 측정의 중앙값 | 측정 스크립트가 잰다 |
| `cost_usd` | 노드별 LLM 호출 비용 추정의 합. 반복 평균 | 응답 `metadata.cost_usd` |
| `retry_count` | MCP Tool 재시도 횟수 | 응답 `metadata.retry_count` |
| `replan_rounds` | 조사 부족으로 재계획한 횟수 | 응답 `metadata.replan_rounds` |
| `validation_attempts` | 답변 검증 시도 횟수(반려되면 늘어난다) | 응답 `metadata.validation_attempts` |
| `task_count` · `gate_removed` | 계획한 task 수, 게이트가 걸러낸 task 수 | 응답 `metadata` |

검색 정확도처럼 응답 metadata에 없는 지표가 필요하면, 측정 스크립트에 지표를 더하고
이 표에도 행을 더한다.

## 지킬 것

- **fake 백엔드 수치는 Before/After 근거로 쓰지 않는다.** 응답과 비용이 고정 규칙으로 만든
  값이고, 회귀 쿼리 10개 중 5번만 incident로 간다. 배관이 도는지 확인하는 데만 쓴다.
- `cost_usd`는 실제 청구액이 아니다. ollama는 로컬 추론이라 청구가 없고, 이 값은
  토큰 수에 가상 단가(`server.py`의 `usd_per_1k_tokens`)를 곱한 추정이다. 표에 그렇게 적는다.
- 같은 백엔드·같은 모델·같은 repeat 수로 잰 것끼리만 비교한다. `compare`가 다르면 경고한다.
- 측정 시점의 커밋은 결과 파일의 `git.commit`에 남는다. Before는 `base` 태그에서 잰다.

## 측정 환경

| 항목 | 값 |
| --- | --- |
| 기기 | TBD |
| LLM 백엔드 · 모델 | TBD (예: ollama · qwen3:0.6b / qwen3:8b) |
| repeat | TBD |

## 결과

| 개선 항목 | Before 파일 | After 파일 | 핵심 수치 | 해석 |
| --- | --- | --- | --- | --- |
| TBD | TBD | TBD | TBD | TBD |
