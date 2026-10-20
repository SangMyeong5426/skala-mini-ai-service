# 진행 계획 (초안)

Google Spread에 등록하는 계획의 원본이다. 진행 중에 고칠 수 있다.
양식과 예시는 [`00-assignment.md`](00-assignment.md#진행-계획-양식).

## 과제 선택

| 항목 | 값 |
| --- | --- |
| 과제 | **1. Base AI Agent 기능 개선/추가** |
| 주제 | 질문을 제대로 이해하고, 근거 있는 답만 내보내는 인시던트 대응 에이전트 |
| 선택 이유 | ① Before 기준점(`base` 태그)과 측정 도구가 이미 있어 같은 입력으로 전/후 비교가 된다. ② 고칠 문제를 실제 화면에서 재현했다 — 일반 질문을 장애로 오분류해 엉뚱한 auth-service 진단을 내고, 검수는 그것을 통과시킨다(아래 "코드에서 확인한 사실"). ③ 구현 시간이 약 1.5일이라 도메인을 새로 만드는 과제 2보다 기술 요소·한계 분석에 시간을 쓸 수 있다. |
| Google Spread 등록 | TBD |

## 개선/추가 포인트

우선순위 순서다. 일정이 밀리면 아래부터 덜어 낸다 — ⑤를 빼고, 그래도 모자라면 ④를 코드 기반
수치 검증만 남긴다. 항목 하나를 끝내면 상태를 바꾸고, 수치는 [`02-measurement.md`](02-measurement.md)에,
결정과 한계는 [`decisions/`](decisions/)에 남긴다.

| 순번 | 영역 | 무엇을 바꾸나 | 추가 설명 | 기술 요소 | Before/After 지표 | 결정 기록 | 상태 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 그래프 개선 (성능) | Ollama thinking 출력 제어 | 지금은 `think`를 넘기지 않아 qwen3가 화면에 안 보이는 생각 토큰을 수천 개 만든다(답변 작성 40초~5분 30초+). `OLLAMA_THINK` 환경변수를 LLM 생성자에 주입해 끈다. | 의존성 주입, LangSmith | 회귀 쿼리 10개의 지연시간(중앙값·합계)·timeout 건수, 품질 감시용 validation_attempts | [0002](decisions/0002-ollama-think-control.md) | 완료 |
| 2 | RAG (라우팅) | route 분류를 임베딩 기반 의미 라우터로 | chat/incident 예시 문장을 `qwen3-embedding:0.6b`로 임베딩해 두고 질문과의 유사도(kNN)로 판정한다. 두 쪽 점수 차가 작을 때만 기존 LLM 분류로 넘긴다. 라우터는 `SupervisorDeps`로 주입해 그래프 코드는 그대로 둔다. | RAG, 의존성 주입, 모듈화, 단위 테스트 | 라벨 붙인 평가 질문 30개(예시 문장과 겹치지 않게)의 분류 정확도·오분류 수, route 단계 지연 | [0003](decisions/0003-semantic-router.md) | 완료 |
| 3 | 그래프 개선 (하드코딩) | 대상 시스템 미지정 시 auth-service 고정 폴백 제거 | 세 곳에 박힌 기본값을 없앤다. 시스템 설명(예: auth-service = 로그인·인증)을 임베딩해 질문에서 대상을 추정하고(2번 인프라 재사용), 확신이 낮으면 진단 대신 "어느 시스템인지" 되묻는 답을 낸다. | RAG, MCP(Tool 대상 결정), 단위 테스트 | 시스템 추정 정확도, 시스템 없는 질문에 대한 엉뚱한 진단 건수 | [0004](decisions/0004-target-resolver.md) | 완료 |
| 4 | 평가 | 검수(validate)에 근거 검증 추가 | 지금은 "30자 이상 + `1)` 포함"만 본다. ① 코드: 답변 속 수치가 수집된 모니터링 값에 있는지 대조, ② LLM-as-judge: 질문과 관련 있는 답인지 채점. 불합격이면 기존 재작성 루프(최대 3회)를 탄다. | 평가(LLM-as-judge), LangSmith, 단위 테스트 | 오염 초안(수치 조작·엉뚱한 답) 탐지율, 정상 초안 오탐률, 추가 지연·비용 | [0005](decisions/0005-grounded-validator.md) | 완료 |
| 5 | RAG (선택) | runbook 선택을 키워드 → 의미 기반으로 | 지금은 모니터링 알림 문구의 키워드로 고르고 안 맞으면 `db-down`이다. runbook 6종을 임베딩(메타데이터에 incident_type)하고 질문+알림으로 검색한다. 안내 자료 예시 1번. | RAG, MCP Resource | 장애유형 정답률, 임베딩 추가 지연 | [0006](decisions/0006-runbook-selector.md) | 완료 — 효과 불확실 |

항목별로 어느 파일·함수를 어떻게 바꾸는지는 [`03-design.md`](03-design.md)에 있다.

공통: 새 기능은 기존 파일에 섞지 않고 새 모듈(예: `agent/embedding.py`, `agent/router.py`,
`agent/validator.py`)로 두고 `SupervisorDeps`로 주입한다. 노드마다 `@traceable`로 LangSmith 트리에 남긴다.
`graph.py`를 통째로 쪼개는 리팩터링은 하지 않는다 — 개선과 섞이면 Before/After가 흐려진다.

### 범위 밖

- openai 백엔드 개선. 과금이라 측정 대상이 아니다. 인터페이스만 깨지 않게 둔다.
- 프론트(`web_chat.html`) 변경. 3번의 "되묻기" 답도 기존 말풍선으로 충분하다.
- 메모리 요약(예시 5번), 서브그래프 멀티에이전트(예시 3번), Human-in-the-loop(예시 4번).

## 측정 계획

| 지표 묶음 | 입력 | 도구 | 비교 |
| --- | --- | --- | --- |
| 지연시간·비용·retry·검증 횟수 | 회귀 쿼리 10개 ([`tools/queries.json`](../tools/queries.json)) | `tools/measure_queries.py` (있음) | 항목 1 전/후, `base` → 최종 |
| 분류 정확도 | [`tools/evalsets/route.json`](../tools/evalsets/route.json) 30개 — 오늘 재현한 오분류 포함 | `tools/eval_nodes.py route` | 항목 2 전/후 |
| 시스템 추정·되묻기 | [`tools/evalsets/target.json`](../tools/evalsets/target.json) 15개 — 시스템명 유무·간접 표현 | `tools/eval_nodes.py target` | 항목 3 전/후 |
| 검수 탐지율 | [`tools/evalsets/judge.json`](../tools/evalsets/judge.json) 12개 — 정상 5 + 오염 7(실제 응답 1) | `tools/eval_nodes.py judge` | 항목 4 전/후 |

- 백엔드는 ollama(qwen3:0.6b / qwen3:8b)로 고정한다. fake 수치는 쓰지 않는다.
- 분류·추정·검수 평가는 서버 없이 해당 클래스를 직접 부른다. temperature 0이라 같은 입력이면 결과가 재현된다.
- 단계마다 바로 앞 상태와 비교하고(`base` → `step1` → `step2` …), 마지막에 `base` → 최종을 한 번 더 잰다.
- `base`의 장애 질문은 300초 timeout을 넘길 수 있다. 넘긴 건수도 Before 수치로 그대로 적는다.

## 일정

| 언제 | 할 일 |
| --- | --- |
| Day1 ~17시 | 계획 등록(Google Spread). 평가 질문 세트 작성. `base`에서 Before 측정 |
| Day2 오전 | 1 thinking 제어 → 측정. 2 의미 라우터 |
| Day2 오후 | 3 대상 시스템 추정·되묻기. 4 검수 강화 |
| Day2 저녁 | 5(여유 시). `base` → 최종 측정 시작 — 장애 질문이 몇 분씩 걸리므로 Day3로 미루지 않는다 |
| Day3 ~13시 | 결정 기록·한계 정리, 결과 보고서, Git 주소·보고서 주소 등록 (**마감 13시**, 2026-10-20 일정 변경) |
| Day3 ~17:30 | 발표 — 문제 → 개선 포인트 → Before/After → 한계·추가 개선 |

## Google Spread 등록용

상세 설계([`03-design.md`](03-design.md))와 Before 실측([`02-measurement.md`](02-measurement.md))을 반영했다.

| 순번 | 영역 | 무엇을 바꾸나 | 추가설명 |
| --- | --- | --- | --- |
| 1 | 그래프 개선(성능) | Ollama thinking 출력 제어 | qwen3가 화면에 안 보이는 생각 토큰을 수천 개 만들어 답변이 40초~5분 이상 걸리고, plan 호출이 300초 timeout 남(실측). think 옵션을 환경변수로 주입해 분류·계획·작성 단계는 끄고(대화 경로는 답변 품질을 위해 유지), 회귀 쿼리 10개로 지연시간·timeout 건수를 전/후 비교 |
| 2 | RAG | route 분류를 임베딩 기반 의미 라우터로 변경 | 예시 문장을 qwen3-embedding으로 임베딩해 두고 유사도(kNN)로 chat/incident 판정, 점수 차가 작을 때만 LLM 폴백. 일반 질문 15개 중 6개를 장애로 오분류(분류 정확도 23/30)하는 문제를 라벨 평가셋 30문항으로 전/후 비교 |
| 3 | 그래프 개선·MCP | Target System 누락 시 auth-service 기본값 하드코딩 제거 + 되묻기 | 시스템 카탈로그를 MCP Resource로 제공하고 설명 임베딩으로 대상 시스템 추정. 특정할 수 없거나 대상 밖이면 진단 대신 되묻기 노드로 응답. 대상 시스템 정확도 6/15·엉뚱한 진단 7건을 평가셋 15문항으로 비교 |
| 4 | 평가 | 검수 노드에 근거 검증 3단계(형식 → 수치 대조 → LLM-as-judge) 추가 | 형식(30자·번호)만 보던 검수에 "수집된 수치를 정확히 인용했는가·질문과 관련 있는가" 채점 추가. 오염 초안 7종 탐지 0/7을 개선하고 정상 초안 오탐률을 함께 측정 |
| 5 | RAG(선택) | incident_type(runbook) 매핑을 키워드 → 의미 검색으로 변경 | runbook 6종을 임베딩(메타데이터에 incident_type)해 질문+알림 문구로 검색. runbook 평가셋 10문항으로 전/후 비교 |
| 공통 | 모듈화·테스트 | 새 기능을 모듈로 분리, 의존성 주입·환경변수 스위치·단위 테스트 추가 | SupervisorDeps로 주입하고 스위치로 개선 전/후를 같은 서버에서 재현. 노드별 처리는 LangSmith로 추적 |

## 코드에서 확인한 사실

계획을 세운 재료다. Base 코드(`project/`)를 읽고 **직접 확인한 것만** 적는다.

| 위치 | 현재 동작 | 연결되는 항목 |
| --- | --- | --- |
| [`agent/fake_llm.py`](../project/agent/fake_llm.py) `FastLLM.route` | route 판정이 정규식 키워드(`장애·진단·다운·지연·급증·incident·티켓`)뿐이다. fake 백엔드로 회귀 쿼리 10개를 돌리면 **5번만 incident로 간다**(2026-10-20 실측). | 측정 시 주의 |
| [`agent/ollama_llm.py`](../project/agent/ollama_llm.py) · [`openai_llm.py`](../project/agent/openai_llm.py) `route` | LLM이 JSON으로 분류하고, JSON이 깨지면 위 정규식으로 폴백한다. | 2 |
| `route` → `plan` → `validate` (ollama, qwen3:0.6b) | 일반 질문을 장애로 잘못 분류한다. 2026-10-20 재현: `ai 에이전트에 대해 설명해줘`·`LangGraph에 대해 설명해줘`는 incident, `AI 에이전트가 뭐야?`·`점심 메뉴 추천해줘`는 chat. incident로 가면 시스템명이 없어 `auth-service`로 폴백하고, 그 모니터링 값으로 질문과 무관한 진단을 쓴다. `validate_node`는 30자 이상 + `1)` 포함만 보므로 통과한다. | 2, 3, 4 |
| [`agent/graph.py`](../project/agent/graph.py) `_extract_system_name`, [`agent/ollama_llm.py`](../project/agent/ollama_llm.py) `plan` 프롬프트 · `_guess_target` | 시스템명이 없으면 `auth-service` — 세 곳에 박혀 있다. plan 프롬프트에 "언급되지 않았으면 auth-service를 기본으로 조사하라"가 그대로 들어 있다. | 3 |
| [`agent/graph.py`](../project/agent/graph.py) `replan_check_node` · `_classify_incident_type` | plan은 모니터링 task만 세우므로 incident는 항상 한 번 재계획(`replan_rounds`=1)한다. 그때 runbook은 **질문이 아니라 모니터링 status·alerts 문구의 키워드**로 고르고, 안 맞으면 `db-down`이다. | 5 |
| [`agent/graph.py`](../project/agent/graph.py) `validate_node` | 합격 조건은 30자 이상 + `1)` 포함뿐이다. 3회 불합격이면 통과 처리한다. | 4 |
| [`agent/ollama_llm.py`](../project/agent/ollama_llm.py) `_chat` · `_chat_stream` | 요청에 `think`를 지정하지 않는다. Ollama 0.33 + qwen3는 이때 생각(thinking)을 별도 필드로 내고, 코드는 `content`만 읽는다. 생각 토큰은 화면에 나가지 않고 시간만 쓴다. 2026-10-20 실측: write 단계(qwen3:8b)가 한 번은 5,420토큰 · 5분 30초를 넘기고도 끝나지 않았고(payments-service 질의), 다른 한 번은 40.8초에 끝났다 — 질의마다 편차가 크다. qwen3:0.6b 짧은 질문은 `think` 미지정 1.77초(생각 527자), `think:false` 0.78초. 0.6b의 plan 호출도 폭주한다 — `결제가 자꾸 실패한다는 고객 문의가 들어오고 있어요`가 두 번 모두 300초 timeout(한 번은 5분에 36,132토큰 생성 후 취소). | 1 |
| [`agent/graph.py`](../project/agent/graph.py) `research_node` | 노드 하나가 모니터링 Tool과 runbook Resource를 병렬로 부른다. | 범위 밖 (예시 3번) |
| [`agent/graph.py`](../project/agent/graph.py) | 노드 10개와 라우팅 함수가 한 파일(338줄)에 있다. | 공통 (새 모듈로 분리) |
| [`agent/ollama_llm.py`](../project/agent/ollama_llm.py) · [`openai_llm.py`](../project/agent/openai_llm.py) `chat` | chat 경로는 이력의 **마지막 10개 메시지**만 프롬프트에 넣는다. incident 경로는 이력을 쓰지 않는다. | 범위 밖 (예시 5번) |
| [`agent/mcp_client.py`](../project/agent/mcp_client.py) `call_tool` | 프로세스 첫 `get_monitoring_status` 호출을 일부러 한 번 실패시킨다(재시도 데모). | 측정 시 주의 |
| 로컬 Ollama | `qwen3-embedding:0.6b`, `nomic-embed-text`가 이미 받아져 있다(2026-10-20 `ollama list`). 임베딩 API 동작은 아직 확인 전. | 2, 3, 5 |
| 테스트 | 원본에는 테스트가 없다. 이 저장소 세팅에서 스모크 테스트 6개를 더했다([`project/tests/`](../project/tests/)). | 공통 |
| 평가 | 안내 자료가 언급한 `eval/run_eval.py`는 학생 배포본에 없다. | 4 |
