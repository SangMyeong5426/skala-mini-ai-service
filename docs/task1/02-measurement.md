# Before/After 실측

평가 기준 "같은 입력으로 개선 전/후를 돌려 수치로 차이를 제시"의 근거를 모은다.
**직접 실행해 얻은 값만 적는다.** 원자료는 [`runs/`](../../runs/)에 있고, 이 문서의 표는
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
| `e2e` | `tools/measure_queries.py --spawn` | 회귀 쿼리([`tools/queries.json`](../../tools/queries.json), 10개 · 11턴)를 `POST /chat`으로 보낸다. **질문마다 서버를 새로 띄우고 끝나면 내린다** |

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
([`tools/eval_nodes.py`](../../tools/eval_nodes.py), 세트 설명은 [`tools/evalsets/README.md`](../../tools/evalsets/README.md)).
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
| repeat | 1회 (temperature 0). 회귀 쿼리는 질문마다 서버를 새로 띄움 |
| 임베딩 | qwen3-embedding:0.6b (항목 2·3·5) |

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

### 답변 작성 (write) — `runs/eval-write_before_20261020-110710.json`

judge 세트 정상 5건의 질문·수집 사실로 quality 모델(qwen3:8b)의 `write`를 직접 불렀다.

| 지표 | 값 |
| --- | --- |
| 완료 | 5/5 (300초 timeout 0) |
| 지연 중앙값 · 최대 | 34.8초 · 78.3초 |
| 토큰 중앙값 (입력 + 생성, 생각 포함) | 1,029 |

### runbook 선택 (runbook) — `runs/eval-runbook_before_20261020-112839.json`

키워드 규칙이라 LLM을 쓰지 않는다. **6/10.** 알림이 아직 없는 시스템(r07·r08)은 `db-down`, 알림 종류가
섞이면(r04) 또는 알림과 질문 증상이 다르면(r09) 규칙 순서상 먼저 걸리는 `cpu-spike`를 골랐다.

### 회귀 쿼리 (e2e) — `runs/e2e_before_20261020-111046.json`

질문마다 서버를 새로 띄워 11턴을 보냈다. **timeout 0건.**

| # | 질문 | route | 지연 |
| --- | --- | --- | --- |
| 1 | payments-service 결제 응답이 느려지고 CPU가 치솟았어요… | incident | 37.9초 |
| 2 | cache-service 메모리 사용률이 계속 올라가고 있어요 | incident | 50.5초 |
| 3 | log-service 디스크 공간이 부족하다는 알림이 왔어요 | incident | 90.5초 |
| 4 | gateway-service에서 payments-service로 가는 요청이 타임아웃… | incident | 39.7초 |
| 5 | web-01 CPU 급증, auth-service 커넥션 풀도 같이 확인해줘 | incident | 51.6초 |
| 6 | payments-service랑 cache-service 둘 다 저하됐는데… | incident | 52.2초 |
| 7 | 로그인 응답이 느려요, 원인 확인해주세요 | incident | 36.1초 |
| 8 | billing-service 응답이 느려요 | incident | 47.8초 |
| 9 | 안녕, 너는 누구야? | chat | 1.9초 |
| 10 | 제 이름은 민수입니다 | chat | 1.9초 |
| 10.2 | 제 이름이 뭐였죠? | chat | 1.2초 |
| | **합계** | | **411.4초** (추정 비용 $0.0478) |

### 요약

| 평가 | Before |
| --- | --- |
| 분류 정확도 | 23/30 (76.7%) |
| 대상 시스템 정확도 | 6/15 (40%), 엉뚱한 진단 7건, timeout 1건 |
| 오염 초안 탐지 | 0/7 |
| 답변 작성 지연 중앙값 | 34.8초 |
| runbook 선택 | 6/10 |
| 회귀 쿼리 11턴 합계 | 411.4초, timeout 0 |

route 결과 파일은 `eval_nodes.py`에 항목별 오류 기록을 넣기 전 버전으로 쟀다. 그 측정에서는 오류가
없었으므로 채점은 같다.

## step1 (항목 1 — thinking 끔) — 2026-10-20

`OLLAMA_THINK=false scripts/measure-at feat/ollama-think step1` (코드 `63fdab2` — 항목 1만 적용).

| 평가 | base | step1 | 원자료 |
| --- | --- | --- | --- |
| 분류 정확도 | 23/30 | 24/30 | `runs/eval-route_step1_20261020-111855.json` |
| 분류 지연 중앙값 | 0.986초 | 0.121초 | 〃 |
| 대상 시스템 정확도 | 6/15 | **5/15** | `runs/eval-target_step1_20261020-111901.json` |
| 엉뚱한 진단 | 7 | **10** | 〃 |
| plan 지연 중앙값 · 최대 | 2.239초 · 300.0초 | 0.588초 · 1.2초 | 〃 |
| 오염 초안 탐지 | 0/7 | 0/7 (코드 검사라 같다) | `runs/eval-judge_step1_20261020-111913.json` |
| 답변 작성 지연 중앙값 · 최대 | 34.8초 · 78.3초 | **9.3초 · 12.2초** | `runs/eval-write_step1_20261020-111914.json` |
| 답변 작성 토큰 중앙값 | 1,029 | 580 | 〃 |
| 회귀 쿼리 11턴 합계 | 411.4초 | **101.4초 (−75.3%)** | `runs/e2e_step1_20261020-112004.json` |
| 추정 비용 합계 | $0.0478 | $0.0289 (−39.6%) | 〃 |

thinking을 끄면 빨라지는 대신 0.6b의 판단이 거칠어진다. 대상 계획에서 시스템 다섯 개를 한꺼번에 조사하거나
(i04·i07), 회귀 쿼리 10번 "제 이름은 민수입니다"를 장애로 분류했다(1.9초 → 11.9초). 이 손실을 항목 2·3이 메운다.

## final (항목 1~5 모두) — 2026-10-20

```bash
OLLAMA_THINK=false ROUTER=semantic TARGET_RESOLVER=semantic VALIDATOR=grounded RUNBOOK_SELECTOR=semantic \
  scripts/measure-at feat/runbook-rag final
```

코드 `bdd205e`. 노드 평가는 노드 하나만 부르므로, 각 노드의 final 결과가 곧 그 노드를 바꾼 항목의 효과다
(route ← 항목 2, plan ← 항목 3, validate ← 항목 4, replan_check ← 항목 5, write ← 항목 1).
route·target은 판정 방식(method)을 기록하도록 도구를 고친 뒤 같은 조건으로 한 번 더 쟀고, 두 번 모두 같은
점수였다(`…113217`·`…113756`, `…113223`·`…113803`).

### 노드 평가

| 평가 | base | step1 | **final** | 원자료 (final) |
| --- | --- | --- | --- | --- |
| 분류 정확도 | 23/30 | 24/30 | **30/30** | `runs/eval-route_final_20261020-113756.json` |
| 분류 방식 | LLM | LLM | 임베딩 29 · LLM 폴백 1 | 〃 |
| 분류 지연 중앙값 | 0.986초 | 0.121초 | **0.043초** | 〃 |
| 대상 시스템 정확도 | 6/15 | 5/15 | **13/15** | `runs/eval-target_final_20261020-113803.json` |
| 진단할 질문 · 되물을 질문 | 6/10 · 0/5 | 5/10 · 0/5 | **10/10 · 3/5** | 〃 |
| 엉뚱한 진단 | 7 | 10 | **2** | 〃 |
| plan 지연 중앙값 · 최대 | 2.239초 · 300.0초 | 0.588초 · 1.2초 | 0.035초 · 1.5초 | 〃 |
| 오염 초안 탐지 · 정상 오탐 | 0/7 · 0/5 | 0/7 · 0/5 | **6/7 · 0/5** | `runs/eval-judge_final_20261020-113227.json` |
| 검수 지연 중앙값 | 0초 | 0초 | 3.465초 | 〃 |
| 답변 작성 지연 중앙값 | 34.8초 | 9.3초 | 10.2초 | `runs/eval-write_final_20261020-113307.json` |
| runbook 선택 | 6/10 | 6/10 | **8/10** | `runs/eval-runbook_final_20261020-113405.json` |

final에서 틀린 것:

| 평가 | 문항 | 결과 |
| --- | --- | --- |
| target | i11 사이트가 전체적으로 너무 느려요 | 되묻기 대신 web-01 — "사이트"가 웹 서버 설명에 끌림 |
| target | i15 서버가 좀 이상한데? | 되묻기 대신 web-01 — "서버"가 웹 서버 설명에 끌림 |
| judge | b1 실제 응답 원문(질문 무관) | 통과 — LLM 판정이 놓침. 같은 유형의 합성 초안 b5는 잡았다 |
| runbook | r01 payments CPU 치솟음 + 응답 느림 | high-latency — base는 맞혔다 |
| runbook | r04 gateway → payments 타임아웃 | high-latency — base도 틀렸다(cpu-spike) |

### 회귀 쿼리 — `runs/e2e_final_20261020-113408.json`

| # | 질문 | base | step1 | **final** |
| --- | --- | --- | --- | --- |
| 1 | payments-service 결제 응답이 느려지고 CPU가 치솟았어요… | 37.9초 | 11.1초 | 15.5초 |
| 2 | cache-service 메모리 사용률이 계속 올라가고 있어요 | 50.5초 | 8.2초 | 15.4초 |
| 3 | log-service 디스크 공간이 부족하다는 알림이 왔어요 | 90.5초 | 10.2초 | 14.3초 |
| 4 | gateway-service에서 payments-service로… (두 시스템) | 39.7초 | 10.6초 | 31.6초 |
| 5 | web-01 CPU 급증, auth-service 커넥션 풀도… (두 시스템) | 51.6초 | 12.5초 | 23.9초 |
| 6 | payments-service랑 cache-service 둘 다… (두 시스템) | 52.2초 | 12.6초 | 34.2초 |
| 7 | 로그인 응답이 느려요, 원인 확인해주세요 | 36.1초 | 12.9초 | 23.0초 |
| 8 | billing-service 응답이 느려요 | 47.8초 (진단¹) | 10.7초 (진단¹) | **0.09초 (되묻기)** |
| 9 | 안녕, 너는 누구야? | 1.9초 | 0.4초 | 0.4초 |
| 10 | 제 이름은 민수입니다 | 1.9초 | 11.9초 (장애로 오분류) | 0.3초 |
| 10.2 | 제 이름이 뭐였죠? | 1.2초 | 0.2초 | 0.2초 |
| | **합계** | **411.4초** | **101.4초** | **159.0초** |
| | 추정 비용 합계 (가상 단가) | $0.0478 | $0.0289 | $0.0514 |
| | timeout | 0 | 0 | 0 |

¹ 회귀 쿼리 결과에는 조사 대상이 남지 않는다. 같은 질문인 대상 평가 i06에서 base·step1 모두 auth-service로
채웠다.

final이 step1보다 느리고 비싼 이유는 **장애 답변마다 검수 LLM 판정(8b)이 한 번 더 돌기 때문**이다(검수 한 번에
약 3.5초). 시스템이 둘인 질문(4~6)은 비교 분석 여부를 묻는 LLM 계획과 더 긴 답변이 더해져 20초 이상 늘었다.
반대로 대상 밖 시스템(8)은 진단 없이 바로 되묻고 끝나 0.09초다.

final 구성에서 실제로 나간 답을 따로 확인했다(답변 본문을 기록하도록 도구를 고친 뒤, 기록은 scratchpad).
"ai 에이전트에 대해 설명해줘"는 0.38초에 일반 대화로 답했다. **"제 이름이 뭐였죠?"는 "민수님의 이름이 정확히
알려졌습니다."라고 답했다** — 이름은 기억하지만 질문에 맞는 답이 아니다. 대화 답변(0.6b)도 thinking을 끈
영향이다([0002 한계](../decisions/0002-ollama-think-control.md#한계와-트레이드오프)).

## final2 (final + 대화 경로만 thinking) — 2026-10-20

final의 대화 답이 어색해져([0002](../decisions/0002-ollama-think-control.md#한계와-트레이드오프)) 대화 경로만 thinking을
다시 켰다([0007](../decisions/0007-chat-keeps-thinking.md)). 장애 처리 경로는 같은 코드다.

```bash
OLLAMA_THINK=false ROUTER=semantic TARGET_RESOLVER=semantic VALIDATOR=grounded RUNBOOK_SELECTOR=semantic \
  scripts/measure-at feat/chat-think final2 e2e        # OLLAMA_THINK_CHAT 은 지정하지 않아 true
```

`runs/e2e_final2_20261020-132116.json` (코드 `32b59c1`, 이 측정부터 답변 본문을 기록한다).

| # | final | final2 | final2 답변 (대화만) |
| --- | --- | --- | --- |
| 1 | 15.5초 | 18.0초 | |
| 2 | 15.4초 | 12.5초 | |
| 3 | 14.3초 | 13.1초 | |
| 4 | 31.6초 | 16.5초 | |
| 5 | 23.9초 | 19.9초 | |
| 6 | 34.2초 | 14.2초 | |
| 7 | 23.0초 | 14.5초 | |
| 8 | 0.09초 | 0.09초 | (되묻기) |
| 9 | 0.4초 | 0.9초 | "안녕하세요! 저는 빠르게 비서입니다." |
| 10 | 0.3초 | 0.5초 | "안녕하세요!" |
| 10.2 | 0.2초 | 0.6초 | "저의 이름은 민수입니다." |
| **합계** | **159.0초** | **110.8초** | 추정 비용 $0.0514 → $0.0496, timeout 0 |

**1회 측정의 편차가 크다.** 장애 질문 1~7은 final과 final2가 같은 코드인데 합계가 158.0초 → 108.8초(−31%)로
달라졌다. 모니터링 Tool이 호출마다 수치를 흔들어(지터) 프롬프트가 달라지고, 그에 따라 생성 길이와 검수 결과가
달라진다. base → final의 차이(411초 → 110~159초)는 이 편차보다 훨씬 크지만, 발표용 수치는 `--repeat 3`으로
다시 재 중앙값을 쓰는 편이 안전하다([`followups.md`](../followups.md)).

## 발표용 수치 — base · final2 반복 3회 중앙값 (2026-10-20)

1회 측정의 편차가 커서(같은 장애 경로 코드가 158.0초 · 108.8초) base와 final2를 회귀 쿼리 3회씩 다시 쟀다.
**발표와 결과 보고서에는 이 절의 수치를 쓴다.**

```bash
MEASURE_REPEAT=3 scripts/measure-at base before-r3 e2e
OLLAMA_THINK=false ROUTER=semantic TARGET_RESOLVER=semantic VALIDATOR=grounded RUNBOOK_SELECTOR=semantic \
  MEASURE_REPEAT=3 scripts/measure-at main final2-r3 e2e
```

원자료: `runs/e2e_before-r3_20261020-133012.json`(코드 `199c839`, 13:30~13:54) ·
`runs/e2e_final2-r3_20261020-135431.json`(코드 `072e1fa`, 13:54~14:04). 회귀 쿼리 11턴 × 3회, 질문마다 서버를 새로 띄웠다.

| 지표 | base | final2 | 변화 |
| --- | --- | --- | --- |
| 11턴 합계 — 회차별 | 383.0 · 396.5 · 600.8초 | 145.8 · 115.0 · 123.8초 | |
| **11턴 합계 — 중앙값** | **396.5초** | **123.8초** | **−68.8%** |
| 장애 질문 8건 합계 — 중앙값 | 391.5초 | 120.7초 | −69.2% |
| 300초 timeout (33턴 중) | **1** (q3 3회차) | 0 | |
| 회차 사이 편차 (최대 ÷ 최소) | 1.57배 | 1.27배 | |
| 추정 비용 — 회차 중앙값 (가상 단가) | $0.0501 | $0.0506 | +1% |

질문별 중앙값 (timeout은 300초로 셈 — 실제로는 그보다 길다):

| # | 질문 | base 3회 → 중앙값 | final2 3회 → 중앙값 |
| --- | --- | --- | --- |
| 1 | payments-service 결제 응답이 느려지고 CPU가 치솟았어요… | 64.4 · 31.6 · 31.7 → **31.7초** | 18.0 · 15.5 · 22.2 → **18.0초** |
| 2 | cache-service 메모리 사용률이 계속 올라가고 있어요 | 35.6 · 38.9 · 52.6 → **38.9초** | 18.2 · 13.9 · 20.5 → **18.2초** |
| 3 | log-service 디스크 공간이 부족하다는 알림이 왔어요 | 90.3 · 76.4 · **300.0(timeout)** → **90.3초** | 16.1 · 13.0 · 12.9 → **13.0초** |
| 4 | gateway-service에서 payments-service로… | 34.2 · 34.9 · 42.3 → **34.9초** | 16.7 · 16.2 · 15.7 → **16.2초** |
| 5 | web-01 CPU 급증, auth-service 커넥션 풀도… | 28.2 · 88.5 · 36.0 → **36.0초** | 38.9 · 20.2 · 16.6 → **20.2초** |
| 6 | payments-service랑 cache-service 둘 다… | 48.0 · 50.4 · 64.6 → **50.4초** | 19.7 · 18.4 · 16.3 → **18.4초** |
| 7 | 로그인 응답이 느려요, 원인 확인해주세요 | 32.2 · 35.2 · 32.3 → **32.3초** | 14.9 · 14.6 · 16.4 → **14.9초** |
| 8 | billing-service 응답이 느려요 | 45.4 · 35.6 · 37.2 → **37.2초** (진단) | 0.1 · 0.1 · 0.1 → **0.1초** (되묻기) |
| 9 | 안녕, 너는 누구야? | 1.8 · 2.3 · 1.6 → **1.8초** | 2.1 · 0.8 · 0.9 → **0.9초** |
| 10 | 제 이름은 민수입니다 | 1.9 · 1.7 · 1.4 → **1.7초** | 0.5 · 0.9 · 0.9 → **0.9초** |
| 10.2 | 제 이름이 뭐였죠? | 1.1 · 1.1 · 1.1 → **1.1초** | 0.6 · 1.3 · 1.3 → **1.3초** |
| | **질문별 중앙값의 합** | **356.3초** | **122.1초 (−65.7%)** |

- **final2는 3회 모두 base의 가장 빠른 회차(383.0초)보다 2.6배 이상 빨랐다.** 장애 질문은 질문별 중앙값 기준
  13.0~20.2초(base 31.7~90.3초)다.
- **base의 timeout이 1회 측정에서는 안 보이다가 반복 측정에서 드러났다.** q3은 1회 측정에서 90.5초였지만 3회차에
  300초를 넘겼다. 생각 토큰 폭주가 입력에 따라 가끔 나는 현상이라는 0002의 관찰과 맞는다.
- `compare`의 질문별 중앙값은 성공한 회차만 쓴다(base q3을 83.3초로, 합 349.3초로 셈). 위 표는 timeout을 300초로
  넣었다. 회차 합계는 두 방식 모두 걸린 시간을 그대로 더했다.
- 비용은 거의 같다. thinking을 꺼서 줄인 토큰을 검수 LLM 판정이 다시 쓴다. base 3회차의 비용($0.0376)이 낮은 것은
  timeout 난 질문의 비용이 기록되지 않아서다.
- 대화 답은 3회 모두 "저의 이름은 민수입니다."였다([0007 한계](../decisions/0007-chat-keeps-thinking.md#한계와-트레이드오프)).
  인사 답은 회차마다 문장이 달랐다 — temperature 0이어도 서버를 새로 띄우면 출력이 조금씩 달라진다.
- base를 먼저, final2를 나중에 쟀다(번갈아 재지 않음). 기기 발열 같은 영향이 있었다면 final2 쪽에 불리하게 들어갔다.
- 노드 평가(분류·대상·검수·runbook)는 temperature 0에 고정 입력이라 반복하지 않았다. final route·target을 같은 조건으로
  두 번 재 같은 점수가 나온 것으로 갈음한다.

## 성능 개선 시도 — 작은 모델 교체 (기각) — 2026-10-20

장애 질문 1건 13~20초 중 약 13.5초가 qwen3:8b(작성 약 10초 · 판정 약 3.5초)라, 작은 모델로 바꿔 보는 시험을 했다.
채택 기준을 먼저 정했고 **세 시험 모두 기준을 넘지 못해 채택하지 않았다** — [0008](../decisions/0008-smaller-models-rejected.md).

`LANGCHAIN_TRACING_V2=false project/.venv/bin/python tools/try_models.py` → `runs/try-models_20261020-142735.json`

| 시험 | 속도 | 품질 | 결론 |
| --- | --- | --- | --- |
| 작성 qwen3.5:2b (판정 8b) | 5건 43.1초 → 25.8초 (−40%) | 5건 중 3건이 하지 않은 조치를 완료했다고 씀 | 기각 |
| 판정 qwen3.5:2b | 판정 3.56초 → 1.78초 | 오염 탐지 6/7 → 5/7 | 기각 |
| 판정 qwen3:0.6b | 판정 3.56초 → 0.56초 | 오염 7/7, 정상 오탐 0/5 → 5/5 | 기각 |

## 결과 요약 — base → final

| 개선 항목 | 핵심 수치 (base → final) | 결정 기록 |
| --- | --- | --- |
| 1 thinking 제어 | 회귀 쿼리 합계 411.4초 → 101.4초(step1) · 답변 작성 중앙값 34.8초 → 9.3초 · plan 최악 300초 timeout → 1.2초 | [0002](../decisions/0002-ollama-think-control.md) |
| 2 의미 라우터 | 분류 23/30 → **30/30**, 분류 지연 0.986초 → 0.043초 | [0003](../decisions/0003-semantic-router.md) |
| 3 대상 추정·되묻기 | 대상 6/15 → **13/15**, 되묻기 0/5 → 3/5, 엉뚱한 진단 7 → 2 | [0004](../decisions/0004-target-resolver.md) |
| 4 검수 근거 검증 | 오염 초안 탐지 0/7 → **6/7**, 정상 오탐 0/5 유지, 검수 +3.5초 | [0005](../decisions/0005-grounded-validator.md) |
| 5 runbook 의미 검색 | 6/10 → 8/10 — **원래 문항만 보면 5/6 → 4/6**, 효과 불확실 | [0006](../decisions/0006-runbook-selector.md) |
| 시도 — 작성·판정 작은 모델 | 작성 −40% 빨라지지만 거짓 완료 주장 3/5 · 작은 판정기는 탐지 저하 또는 전부 반려 → **기각** | [0008](../decisions/0008-smaller-models-rejected.md) |
| 1 보완 — 대화만 thinking | 대화 답 자연스러움 6건 중 1 → 4, 대화 지연 +0.5초 (0.2초 → 0.7초, base 1.2~1.9초) | [0007](../decisions/0007-chat-keeps-thinking.md) |
| **전체 (회귀 쿼리 11턴, 반복 3회 중앙값)** | **396.5초 → 123.8초 (−68.8%)**, timeout 33턴 중 1 → 0, 추정 비용 +1% | [발표용 수치](#발표용-수치--base--final2-반복-3회-중앙값-2026-10-20) |
| 전체 (1회 측정, 참고) | 411.4초 → 159.0초 (final) · 110.8초 (final2) — 편차가 커서 발표에는 위 줄을 쓴다 | — |
