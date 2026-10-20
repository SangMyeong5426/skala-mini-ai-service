# 상세 수정 설계

[`01-plan.md`](01-plan.md)의 개선 항목을 **어느 파일·함수를 어떻게 바꾸는지**까지 내린 문서다.
구현 중에 설계와 다르게 가면 이 문서를 먼저 고치고, 왜 바꿨는지는 해당 결정 기록에 남긴다.

## 구현하며 바뀐 것 (2026-10-20)

아래 본문은 구현 전 설계 그대로 두고, 달라진 점만 여기 모은다. 이유는 각 결정 기록에 있다.

| 항목 | 설계 | 구현 | 이유 |
| --- | --- | --- | --- |
| 공통 | 스위치 기본값은 ollama면 개선, `ROUTER`만 fake·openai에서 base | **모든 스위치가** ollama면 개선, fake·openai면 base | fake는 Wave 데모를 결정론으로 재현하는 백엔드, openai는 과금이라 측정 대상이 아니다 |
| 공통 | step2~4를 커밋마다 스위치 조합으로 잰다 | **final 한 번**으로 잰다 | 노드 평가는 노드 하나만 부른다. route는 `ROUTER`에만, plan은 `TARGET_RESOLVER`에만 반응하므로 final의 노드별 결과가 곧 각 항목의 효과다 |
| 공통 | — | `/health`에 실제 스위치 값(`switches`) | 결과 파일에 어떤 조합으로 쟀는지 남기기 위해 |
| 1 | `OLLAMA_THINK` 하나로 모든 호출 | 대화 경로만 `OLLAMA_THINK_CHAT`(기본 true)로 분리 | 생각을 끄면 대화 답이 어색해졌다 — [0007](../decisions/0007-chat-keeps-thinking.md) |
| 2 | 질의에 Qwen3 지시문 | **지시문 없음**, margin 0.029 | 예시 LOO 정답률 0.95(지시문 0.925) — [0003](../decisions/0003-semantic-router.md) |
| 2 | — | `setup_ollama.sh`·`run_agent_ollma.sh`에 임베딩 모델 | 새 PC에서 기동 시 모델이 없으면 lifespan이 실패한다 |
| 3 | auth-service 기본값 세 곳 **삭제** | **남겨 두고** 새 경로가 닿지 않게 함 | `TARGET_RESOLVER=legacy`로 원본을 그대로 재현하려면 base 경로가 남아 있어야 한다 |
| 3 | margin·min_score를 예시로 조정 | 별도 조정용 문장(`tools/tuning/target.json`)으로 격자 탐색, min_score 0.40 · margin 0.04 | 대상 추정은 예시 kNN이 아니라 시스템 설명과의 유사도라 LOO를 쓸 수 없다 |
| 5 | 유사도가 낮으면 키워드 규칙 폴백 | **폴백 없이 1위**, 지시문 없음 | 조정 데이터가 없어 임계값을 정할 근거가 없다. base도 늘 무언가를 고른다(맞는 게 없으면 db-down) |
| 5 | target 세트의 6문항으로 측정 | runbook 세트 10문항을 새로 만듦 | 6문항으로는 차이를 말하기 어렵다. 새 문항은 설계 뒤에 썼다 — [0006](../decisions/0006-runbook-selector.md)에 편향을 적었다 |

## 공통 원칙

### 1. 새 기능은 새 모듈 + 의존성 주입

노드 함수의 시그니처(`state, deps`)는 그대로 둔다. 바뀌는 판단은 새 모듈의 객체로 만들고
`SupervisorDeps`에 실어 노드에 주입한다. **필드가 `None`이면 노드는 base 동작을 그대로 한다** —
v1 파이프라인, fake 백엔드, 기존 테스트가 손대지 않아도 돈다.

```python
@dataclass
class SupervisorDeps:
    fast_llm: Any
    quality_llm: Any
    mcp: Any
    session_store: Any
    version: str
    embedder: Any = None          # 2·3·5가 함께 쓰는 임베딩 클라이언트
    router: Any = None            # 항목 2 — None이면 fast_llm.route
    target_resolver: Any = None   # 항목 3 — None이면 base의 auth-service 폴백
    validator: Any = None         # 항목 4 — None이면 30자 + "1)" 검사
    runbook_selector: Any = None  # 항목 5 — None이면 알림 키워드 규칙
```

조립은 `server.py`에 `_build_components()`를 새로 두고 lifespan에서 부른다. `_build_llms()`와
같은 방식으로 환경변수를 읽는다. `tools/eval_nodes.py`는 lifespan을 그대로 쓰므로 고치지 않는다.

### 2. 개선마다 환경변수 스위치

| 환경변수 | 개선 후 기본값 | base 동작 | 항목 |
| --- | --- | --- | --- |
| `OLLAMA_THINK` | `false` | `default`(옵션을 보내지 않음) | 1 |
| `ROUTER` | `semantic` (fake·openai는 `llm`) | `llm` | 2 |
| `TARGET_RESOLVER` | `semantic` | `legacy` | 3 |
| `VALIDATOR` | `grounded` | `format` | 4 |
| `RUNBOOK_SELECTOR` | `semantic` | `keyword` | 5 |

이유는 셋이다. ① 라벨을 고쳐 Before를 다시 재야 할 때 `base` 체크아웃 없이 스위치만 내려 잰다.
② 발표에서 같은 서버로 전/후를 바로 보여 줄 수 있다. ③ 문제가 생기면 재배포 없이 끈다 —
원본 Wave 14의 `SUPERVISOR_VERSION` 토글과 같은 생각이다. 새 환경변수는 `project/.env.example`에 적는다.

### 3. 측정 순서

항목 1이 fast 모델(qwen3:0.6b)의 thinking을 끄면 **LLM 분류와 plan 결과 자체가 달라진다.**
그래서 항목 1을 끝낸 상태(`step1`)에서 노드 평가 3종과 회귀 쿼리를 다시 재고, 그것을 항목 2~4의
Before로 쓴다. 발표의 최종 비교는 `base` → 최종 한 번이다.

| 라벨 | 상태 | 재는 것 |
| --- | --- | --- |
| `before` | `base` 태그 | 노드 평가 3종(완료) + 답변 작성 `write` + 회귀 쿼리 `e2e` |
| `step1` | 항목 1 | 노드 평가 3종 + `write` + `e2e` |
| `step2` | 항목 1~2 | route |
| `step3` | 항목 1~3 | target |
| `step4` | 항목 1~4 | judge + `e2e` |
| `final` | 전부 | 노드 평가 3종 + `write` + `e2e` |

모두 `scripts/measure-at <커밋> <label> [단계]`으로 잰다 — 커밋을 worktree로 꺼내 재고, 회귀 쿼리는
질문마다 서버를 새로 띄운다([`02-measurement.md`](02-measurement.md#측정-방법)).

### 4. 브랜치와 기록

항목 하나 = 브랜치 하나(`feat/ollama-think`, `feat/semantic-router`, `feat/target-resolver`,
`feat/grounded-validator`, `feat/runbook-rag`). 테스트 통과와 측정을 마치면 `main`에 merge하고,
`docs/decisions/`에 결정 기록을 하나씩 쓴다(템플릿의 "한계와 트레이드오프" 절 필수).
`server.py`·그래프를 바꾸면 `project/doc/README.md`의 아키텍처 다이어그램도 같이 고친다.

---

## 항목 1 — Ollama thinking 제어

**문제**: `OllamaLLM._chat`·`_chat_stream`이 `think`를 보내지 않아, qwen3가 화면에 안 나가는 생각
토큰을 만든다. 8b 답변 작성이 40초~5분 30초+, 0.6b plan 호출도 300초 timeout(i08, 2회 재현).

| 파일 | 변경 |
| --- | --- |
| `agent/ollama_llm.py` | `OllamaLLM.__init__(model, usd_per_1k_tokens, think: bool \| None = None)`. `think`가 `None`이 아니면 `_chat`·`_chat_stream`의 payload에 `"think": self.think`를 넣는다 |
| `server.py` `_build_llms` | `OLLAMA_THINK`(`false`·`true`·`default`)를 읽어 fast·quality 생성자에 넘긴다 |
| `.env.example` | `# OLLAMA_THINK=false` 와 설명 한 줄 |

openai·fake 백엔드는 해당 없음.

**테스트** (`tests/test_ollama_think.py`, ollama 없이): `httpx.post`·`AsyncClient.stream`을 가짜로
바꿔 payload를 잡는다 — `think=False`면 `"think": false`가 들어가고, `None`이면 키가 없다.

**완료 기준**: 테스트 통과. `step1` 측정에서 회귀 쿼리 timeout 0건, target 평가의 i08 오류 사라짐.

**측정**: 회귀 쿼리 지연시간(중앙값·합계·timeout 건수), 노드 평가 3종 재측정(분류 정확도 변화 포함).

**예상 한계**: 추론 과정을 끄면 분류·계획·답변 품질이 떨어질 수 있다 — `validation_attempts`와
분류 정확도가 나빠지는지 같이 본다. 나빠지면 fast만 끄고 quality는 켜는 조합을 비교한다.

---

## 항목 2 — 임베딩 기반 의미 라우터

**문제**: qwen3:0.6b 분류가 일반 질문 15개 중 6개를 장애로 보낸다(분류 23/30).

### 새 모듈

| 파일 | 내용 |
| --- | --- |
| `agent/embedding.py` | `OllamaEmbedder(model="qwen3-embedding:0.6b")` — `async embed(texts) -> list[list[float]]` (`/api/embed`), `cosine(a, b)`. 질문 쪽에는 Qwen3-Embedding 권장 형식의 지시문(`Instruct: …\nQuery: …`)을 붙인다 |
| `agent/router.py` | `LLMRouter(fast_llm)` — base 동작 래퍼. `SemanticRouter(embedder, examples, fallback, margin, k)` |
| `data/router_examples.json` | `{"chat": [...], "incident": [...]}` 클래스당 15~20문장 |

### `SemanticRouter.route(query)` 흐름

1. 서버 기동 시 예시 문장을 한 번에 임베딩해 메모리에 둔다(실측 7문장 0.185초).
2. 질문을 임베딩하고(실측 0.038초) 클래스별로 **상위 k개(기본 3) 유사도 평균**을 낸다.
3. `incident - chat` 차이의 절댓값이 `ROUTER_MARGIN` 이상이면 그 클래스로 정한다.
4. 차이가 작으면 `LLMRouter`(항목 1이 적용된 fast 모델)로 넘긴다.
5. 결과 `{"route", "needs_analysis": False, "method": "semantic"|"llm-fallback", "scores"}`와 usage를 돌려준다.

`needs_analysis`는 정하지 않는다 — incident 경로에서는 `plan_node`가 자기 결과로 덮어쓰므로
라우터 값은 쓰이지 않는다(코드 확인).

### 그래프 변경

`route_node`: `deps.router`가 있으면 `await deps.router.route(query)`, 없으면 기존 `deps.fast_llm.route`.
`RouteDecided` 이벤트에 `method`와 `scores`를 더한다. LangSmith에는 `@traceable`로 남긴다.

### 지킬 것

- 예시 문장은 `tools/evalsets/route.json`의 질문과 **겹치지 않게** 쓴다. `tests/`에 겹침 검사 테스트를 둔다.
- `ROUTER_MARGIN`은 평가 세트로 고르지 않는다. 예시 문장 안에서 하나씩 빼고 맞히는 방식
  (leave-one-out)으로 정하고 그 값을 결정 기록에 남긴다. 평가 세트로 고르면 정답을 외운 것이 된다.
- 임베딩은 ollama가 필요하다. fake·openai 백엔드의 기본값은 `ROUTER=llm`이다.

**테스트** (`tests/test_router.py`): 손으로 정한 벡터를 돌려주는 가짜 embedder로 — 차이가 크면
semantic, 작으면 fallback이 불리는지. 예시 문장 ↔ 평가 세트 겹침 0건.

**완료 기준**: `step2` 분류 정확도가 `step1`보다 높고, 재현된 오분류(c01·c02)가 chat으로 간다.

**측정**: 분류 정확도·클래스별 정답, LLM fallback 비율, route 단계 지연(임베딩 0.04초 대 LLM 약 1초).

**예상 한계**: 예시가 다루지 않는 표현에 약하다. margin을 넓히면 fallback이 늘어 LLM 지연과 오분류가
돌아온다. 임베딩 모델이 GPU 메모리 2.4GB를 더 쓴다(16GB 기기에서 8b·0.6b와 동시 상주) — 메모리가 모자라면
모델 교체 로드(실측 1.4초)가 생긴다. 예시 문장을 계속 관리해야 한다.

---

## 항목 3 — 대상 시스템 추정·되묻기

**문제**: 시스템명이 없으면 세 곳(`graph._extract_system_name`, ollama·openai `plan` 프롬프트,
`_guess_target(s)`)에서 auth-service로 채운다. target 평가 6/15, 되묻기 0/5, 엉뚱한 진단 7건.

### 시스템 카탈로그를 MCP Resource로

| 파일 | 변경 |
| --- | --- |
| `data/systems.json` (새 파일) | `[{"name": "auth-service", "description": "로그인·인증·세션 토큰 발급"}, …]` 6개 |
| `mcp_server.py` | Resource `catalog://systems` — 위 파일을 그대로 돌려준다 |
| `agent/mcp_client.py` | 템플릿 없는 정적 resource를 찾는 `find_resource(uri)` 추가(`list_resources` 조회). 기존 `find_resource_template`과 같은 "서버 탐색 후 요청" 방식 |

에이전트가 `data/monitoring.json`을 직접 읽어 시스템 목록을 만드는 곳이 세 군데(`graph.py`,
`ollama_llm.py`, `openai_llm.py`)다. 카탈로그를 MCP로 받으면 목록의 출처가 MCP 서버 하나로 모인다.

### 새 모듈 `agent/target.py` — `TargetResolver(embedder, catalog, threshold, margin)`

`resolve(query) -> {"targets": [...], "method": ..., "reason": ...}`

| 순서 | 조건 | 결과 |
| --- | --- | --- |
| 1 | 카탈로그 시스템명이 질문에 있다 | 등장한 **전부**, 등장 순서대로 (`name-match`) — i04 두 시스템 누락 해결 |
| 2 | `xxx-service` 꼴인데 카탈로그에 없다 (예: billing-service) | `[]`, 이유 "모니터링 대상 아님" |
| 3 | 질문 ↔ 시스템 설명 유사도 1위가 `threshold` 이상이고 2위와 `margin` 이상 차이 | 1위 하나 (`semantic`) |
| 4 | 그 밖 | `[]`, 이유 "시스템 특정 불가" |

### 그래프 변경

| 위치 | 변경 |
| --- | --- |
| `plan_node` | `deps.target_resolver`가 있으면 먼저 `resolve`. 대상이 없으면 **research task 0개 + `ClarifyRequested` 이벤트**를 돌려준다(평가 채점 약속). 대상이 있으면 research task는 resolver 결과로 만들고, LLM plan은 **대상이 2개 이상일 때만** 불러 `needs_analysis`만 받는다 |
| 새 노드 `clarify` | LLM 없이 템플릿으로 답한다 — "어느 시스템인지 알려 주세요" + 카탈로그 6개와 설명. `final`을 채우고 END |
| 새 조건 엣지 `plan → clarify \| gate` | research task가 없으면 `clarify` |
| `_extract_system_name` | resolver의 첫 대상을 쓴다. 폴백 `auth-service` 삭제 |
| ollama·openai `plan` 프롬프트, `_guess_target(s)` | "언급되지 않았으면 auth-service" 문구와 폴백 삭제 |

LLM plan을 대상 2개 이상일 때만 부르는 이유: 대상은 이제 코드가 정하고, LLM이 더할 수 있는 것은
`analysis` 필요 여부뿐이다. `analyze`는 여러 시스템 비교라 대상 1개면 쓸 일이 없다. 그 결과 단일
시스템 질문에서 LLM 호출이 하나 줄고, i08 같은 plan 폭주 위험도 줄어든다.

**프론트(선택, 2줄)**: `web_chat.html`의 `STEP_LABELS`에 `ClarifyRequested` 문구를 더한다.
안 더해도 되묻기 답변 자체는 `FinalAnswer`로 보인다.

**테스트** (`tests/test_target.py`): 이름 매칭 2개, 대상 밖 시스템, 가짜 embedder로 임계값 위·아래.
`tests/test_smoke.py`에 fake 백엔드로 "서버가 좀 이상한데?" → `ClarifyRequested` + research 0개.

**완료 기준**: `step3` target 정확도 상승, 되묻기 5건 중 다수 정답, 엉뚱한 진단 감소, 진단 정답 6/10 아래로 안 떨어짐.

**측정**: target 정확도, 진단·되묻기 정답 수, 엉뚱한 진단 건수, plan 단계 지연.

**예상 한계**: 설명 문구에 따라 결과가 흔들린다. 임계값을 높이면 진단할 질문까지 되묻는다(과잉 되묻기) —
진단 정답 수로 감시한다. 카탈로그를 시스템 추가 때마다 관리해야 한다. 기동 시 MCP 왕복이 하나 는다.

---

## 항목 4 — 검수 근거 검증

**문제**: `validate_node`가 30자 + `1)`만 본다. 오염 초안 7건 중 0건 탐지.

### 새 모듈 `agent/validator.py` — 세 겹, 싼 것부터

| 단계 | 검사 | 비용 | 잡을 것 (judge.json) |
| --- | --- | --- | --- |
| ① 형식 | 30자 이상 + `1)` (base 그대로) | 0 | — |
| ② 수치 근거 | 초안의 수치가 수집값(모니터링 수치·알림 문구·runbook·analysis·질문)에 있는지. 알림 개수(`len(alerts)`)와 번호(`1)`)는 허용 | 0, 결정론 | b2 수치 조작, b3 수집 안 한 지표, b4 다른 시스템 |
| ③ LLM-as-judge | quality 모델에 질문·수집 사실·초안을 주고 JSON(`relevant`, `faithful`, `reason`)으로 채점. `think=false` | LLM 1회 | b1·b5 질문 무관, b6 결론 왜곡, b7 지표 바꿔치기 |

앞 단계에서 떨어지면 뒤 단계는 부르지 않는다. 불합격이면 구체적인 반려 사유(예: "수집되지 않은 수치
99.8%를 인용했습니다")를 `validation_feedback`에 넣어 기존 재작성 루프(최대 3회)를 탄다.

| 파일 | 변경 |
| --- | --- |
| `agent/validator.py` | `FormatCheck`, `NumberGroundingCheck`, `LLMJudge`, 셋을 묶는 `GroundedValidator.check(query, collected, draft)` |
| `agent/ollama_llm.py` · `openai_llm.py` · `fake_llm.py` | quality 클래스에 `judge(query, facts, draft)` 추가 — 백엔드마다 같은 인터페이스. fake는 결정론 규칙 |
| `graph.validate_node` | `deps.validator`가 있으면 그 결과를 쓴다. 이벤트에 `stage`(어느 단계에서 떨어졌나)와 `reason` 추가 |
| 3회 실패 시 | base는 "통과 처리"로 그대로 내보낸다. 근거 검증에서 떨어진 채 3회에 도달하면 답변 맨 앞에 "⚠️ 검수를 통과하지 못한 답변 — 사유"를 붙여 내보낸다 |

**테스트** (`tests/test_validator.py`): `tools/evalsets/judge.json`을 읽어 ② 수치 근거 검사가
정상 5건을 하나도 떨어뜨리지 않고 b2·b3·b4를 떨어뜨리는지(LLM 없이). ③은 가짜 judge로 순서·사유 전달만.

**완료 기준**: `step4` 오염 초안 탐지 0/7 → 5/7 이상, 정상 초안 오탐 0/5 유지.

**측정**: 탐지율, 오탐률, 검수 단계 지연(③의 LLM 1회), 회귀 쿼리 지연시간·`validation_attempts` 변화.

**예상 한계**: 판정 모델도 틀린다. 작성 모델과 같은 계열(qwen3:8b)이라 같은 실수를 놓칠 수 있다.
장애 답변마다 LLM 호출이 하나 늘어 지연이 커진다. 정상 답변을 떨어뜨리면 재작성이 늘어 더 느려진다.
수치 추출 정규식이 단위·버전 번호·인스턴스 번호(`payments-service-3`)를 잘못 읽을 수 있다.

---

## 항목 5 — runbook 선택을 의미 기반으로 (선택)

**문제**: `replan_check_node`가 모니터링 status·alerts 문구의 키워드로 runbook을 고르고, 안 맞으면 `db-down`.
질문 내용은 보지 않는다.

| 파일 | 변경 |
| --- | --- |
| `agent/runbook.py` (새 파일) | `RunbookSelector(embedder, runbooks, threshold)` — 기동 시 runbook 6종을 임베딩(메타데이터 incident_type = 파일 이름). `select(query, collected)`는 질문 + 알림 문구로 검색해 1위를 고른다. 유사도가 낮으면 키워드 규칙으로 폴백 |
| `graph.replan_check_node` | `deps.runbook_selector`가 있으면 `_classify_incident_type` 대신 사용 |
| runbook 목록 | 인덱싱용 본문은 `data/runbooks/*.md`를 직접 읽는다. 선택된 runbook 조회는 지금처럼 MCP Resource로 한다 |

**측정 준비**: 구현 전에 `tools/eval_nodes.py`에 `runbook` 하위 명령을 더하고(`target.json`의
`expected_runbook` 6건, 모니터링 기준값의 알림 문구로 collected 구성) **키워드 규칙으로 Before부터 잰다.**

**예상 한계**: 문서 6개라 검색 이득이 작을 수 있다. runbook이 바뀌면 다시 임베딩해야 한다. 인덱싱이
MCP를 거치지 않아 데이터 출처가 두 갈래가 된다.

---

## 일정 배분 (Day2)

| 시간 | 항목 | 비고 |
| --- | --- | --- |
| 오전 앞 | 1 | 1시간 안쪽. 끝나면 `step1` 측정을 백그라운드로 |
| 오전 뒤 ~ 오후 초 | 2 | `embedding.py`는 3·5가 같이 쓴다 |
| 오후 | 3 | MCP Resource 추가 포함 |
| 오후 뒤 ~ 저녁 | 4 | 저녁에 `final` 측정 시작 — 장애 질문이 오래 걸린다 |
| 여유 | 5 | 없으면 뺀다 (Day3 13시 마감) |
