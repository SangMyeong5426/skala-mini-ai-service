# Before/After 실측

평가 기준 "같은 입력으로 개선 전/후를 돌려 수치로 차이를 제시"의 근거를 모은다.
**직접 실행해 얻은 값만 적는다.** 원자료는 [`runs/`](../runs/)에 있고, 이 문서의 표는
그 파일에서 옮긴 것이다. 표마다 원자료 파일명을 적는다.

## 측정 방법

**`scripts/measure-at`으로 잰다.** 잴 커밋을 git worktree로 따로 꺼내 그 코드로 돌린다. 측정 도구와
평가 세트는 지금 작업 트리의 것을, 에이전트 코드만 그 커밋의 것을 쓰므로 Before와 After가 같은 입력·같은
채점으로 잰다. 측정 도중 작업 트리의 파일을 고쳐도 결과에 섞이지 않는다.

```bash
scripts/measure-at base before write,e2e                      # Before (원본 코드)
OLLAMA_THINK=false scripts/measure-at feat/ollama-think step1  # 항목 1 적용, 전 단계
project/.venv/bin/python tools/measure_queries.py compare runs/e2e_before_<시각>.json runs/e2e_step1_<시각>.json
```

| 단계 | 도구 | 하는 일 |
| --- | --- | --- |
| `route`·`target`·`judge` | `tools/eval_nodes.py` | 노드를 직접 불러 라벨 세트로 채점 (아래 "노드 단위 평가") |
| `write` | `tools/eval_nodes.py write` | 답변 작성 LLM 호출(`quality_llm.write`) 하나의 지연·토큰. judge 세트 정상 5건의 질문·수집 사실을 입력으로 쓰고, 300초를 넘기면 취소해 timeout으로 센다 |
| `e2e` | `tools/measure_queries.py --spawn` | 회귀 쿼리([`tools/queries.json`](../tools/queries.json), 10개 · 11턴)를 `POST /chat`으로 보낸다. **질문마다 서버를 새로 띄우고 끝나면 내린다** |

질문마다 서버를 새로 띄우는 이유: base에서는 클라이언트가 300초 timeout으로 끊어도 서버가 그 요청의
LLM 생성을 끝까지 계속한다. 한 서버로 이어서 재면 앞 질문의 생성이 ollama를 붙잡아 뒤 질문의 지연에
섞인다. 프로세스를 내리면 연결이 끊기며 ollama 생성도 취소된다. 대신 MCP 첫 조회 재시도(데모)가 장애
질문마다 한 번씩 일어나 `retry_count`가 늘 1이다 — Before와 After 조건이 같으므로 비교에는 문제없다.

측정하는 동안 같은 ollama로 다른 요청(웹 채팅 등)을 보내지 않는다. 지연시간이 섞인다.

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
  개선 스위치(`OLLAMA_THINK` 등) 값은 `switches`에 남는다.
- route·target·judge의 Before(10:13~10:30)는 `scripts/measure-at`을 만들기 전에 작업 트리에서 쟀다
  (`agent_matches_base: true`, LangSmith 추적 켜짐). 이후 측정은 worktree에 `.env`가 없어 추적이 꺼진
  채로 돈다. 추적은 별도 스레드로 보내므로 LLM 호출 시간(초 단위)에 비해 차이는 무시할 만하다.

## 노드 단위 평가

개선 항목 2·3·4는 서버 왕복 대신 해당 노드를 직접 불러 라벨 세트로 채점한다
([`tools/eval_nodes.py`](../tools/eval_nodes.py), 세트 설명은 [`tools/evalsets/README.md`](../tools/evalsets/README.md)).
의존성은 `server.py`의 lifespan을 그대로 실행해 얻으므로 서버와 같은 조립으로 돈다.

```bash
project/.venv/bin/python tools/eval_nodes.py all --label before
```

결과 파일의 `git.agent_matches_base`가 `true`여야 Before로 쓴다(에이전트 코드가 `base` 태그와 같다는 뜻).

## 측정 환경

| 항목 | 값 |
| --- | --- |
| 기기 | Apple M5, RAM 16GB (Metal, GPU 가용 11.8GiB) |
| LLM 백엔드 · 모델 | ollama 0.33.0 · qwen3:0.6b(fast) / qwen3:8b(quality), temperature 0 |
| repeat | 노드 평가 1회 (temperature 0). 회귀 쿼리는 TBD |

## Before (`base`) — 2026-10-20

### 분류 (route) — `runs/eval-route_before_20261020-101334.json`

| 지표 | 값 |
| --- | --- |
| 정확도 | **23/30 (76.7%)** |
| chat 정답 | 9/15 — 일반 질문 6개를 장애로 오분류 |
| incident 정답 | 14/15 |
| route 단계 지연 중앙값 | 0.986초 |

오분류 7건:

| id | 질문 | 정답 → 결과 |
| --- | --- | --- |
| c01 | ai 에이전트에 대해 설명해줘 | chat → incident |
| c02 | LangGraph에 대해 설명해줘 | chat → incident |
| c04 | RAG와 파인튜닝의 차이를 알려줘 | chat → incident |
| c11 | p95 latency가 무슨 뜻이야? | chat → incident |
| c12 | 장애 대응 보고서는 보통 어떤 항목으로 쓰나요? | chat → incident |
| c13 | 쿠버네티스에서 오토스케일링은 어떻게 동작해? | chat → incident |
| i13 | 로그 수집이 멈춘 것 같아요, 확인 부탁해요 | incident → chat |

개념·기술 설명 요청이 장애로 가는 경향이 뚜렷하다. 인사·일상·감사는 모두 맞혔다.

### 대상 시스템 (target) — `runs/eval-target_before_20261020-102502.json`

| 지표 | 값 |
| --- | --- |
| 정확도 | **6/15 (40%)** |
| 진단해야 할 질문 | 6/10 |
| 되물어야 할 질문 | **0/5** — 5건 모두 auth-service 진단으로 갔다 |
| 엉뚱한 진단 (되물어야 했거나 정답에 없는 시스템 조사) | **7건** |
| 오류 | 1건 — i08 plan 호출이 300초 timeout (`ReadTimeout`) |
| plan 단계 지연 | 중앙값 2.239초, 최대 300.044초 |

틀린 9건:

| id | 질문 | 정답 → 결과 |
| --- | --- | --- |
| i04 | gateway-service에서 payments-service로 가는 요청이 타임아웃 나고 있어요 | 두 시스템 → gateway-service만 |
| i08 | 결제가 자꾸 실패한다는 고객 문의가 들어오고 있어요 | payments-service → **timeout 300초** |
| i12 | 캐시 히트율이 갑자기 떨어졌어요 | cache-service → auth-service |
| i13 | 로그 수집이 멈춘 것 같아요, 확인 부탁해요 | log-service → auth-service |
| i06 | billing-service 응답이 느려요 | 되묻기 → auth-service |
| i10 | 방금 배포한 뒤로 5xx 에러가 급증했어요 | 되묻기 → auth-service |
| i11 | 사이트가 전체적으로 너무 느려요 | 되묻기 → auth-service |
| i14 | DB 연결이 끊겼다는 에러가 계속 나요 | 되묻기 → auth-service |
| i15 | 서버가 좀 이상한데? | 되묻기 → auth-service |

시스템 이름이 질문에 그대로 있으면 대부분 맞힌다. 간접 표현이나 대상 밖·모호한 질문은
전부 auth-service로 채워진다 — 기본값 하드코딩 세 곳([`01-plan.md`](01-plan.md#코드에서-확인한-사실))이 그대로 드러난다.

i08은 같은 입력으로 두 번 재도 두 번 다 300초에 걸렸다(temperature 0). 첫 시도 때 ollama 로그에는
plan 호출 하나가 5분 동안 36,132토큰을 생성하다 클라이언트 timeout으로 취소된 기록이 남았다 —
qwen3:0.6b도 thinking이 폭주한다. 실서버였다면 이 질문은 5분 뒤 오류로 끝난다. 항목 1의 근거이기도 하다.

### 검수 (judge) — `runs/eval-judge_before_20261020-103034.json`

| 지표 | 값 |
| --- | --- |
| 오염 초안 탐지 | **0/7** — 결함 7종 모두 통과 |
| 정상 초안 오탐 | 0/5 |
| 검수 지연 | 0초 (문자열 검사뿐) |

현재 검수는 "30자 이상 + `1)` 포함"만 본다. 수치 조작, 수집하지 않은 지표, 다른 시스템 진단,
질문 무관(실제 응답 원문 b1 포함), 결론 왜곡, 지표 바꿔치기가 모두 형식을 지켜서 통과한다.

### 요약

| 평가 | Before |
| --- | --- |
| 분류 정확도 | 23/30 (76.7%) |
| 대상 시스템 정확도 | 6/15 (40%), 엉뚱한 진단 7건, timeout 1건 |
| 오염 초안 탐지 | 0/7 |
| 회귀 쿼리 지연시간 | TBD — 백엔드를 새로 띄운 직후 `measure_queries.py`로 잰다 |

route 결과 파일은 `eval_nodes.py`에 항목별 오류 기록을 넣기 전 버전으로 쟀다. 그 측정에서는 오류가
없었으므로 채점은 같다.

## 결과

| 개선 항목 | Before 파일 | After 파일 | 핵심 수치 | 해석 |
| --- | --- | --- | --- | --- |
| TBD | TBD | TBD | TBD | TBD |
