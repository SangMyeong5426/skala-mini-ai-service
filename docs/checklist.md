# 3일 체크리스트

[`01-plan.md`](01-plan.md)(무엇을)와 [`03-design.md`](03-design.md)(어떻게)를 할 일 단위로 내린 목록이다.
끝낸 항목은 체크하고 근거(커밋·파일)를 옆에 적는다. 직접 해야 하는 일(Google Spread 등록 등)은
**(직접)**으로 표시했다 — 끝나면 체크해 달라.

마지막 갱신: 2026-10-20 (Day1)

## 마감

| 마감 | 할 일 | 상태 |
| --- | --- | --- |
| Day1 17:00 | 과제·진행 계획(초안) Google Spread 등록 | ⬜ |
| Day3 13:00 | Git 주소·결과 보고서 주소 Google Spread 등록 | ⬜ |
| Day3 17:30 | 개인별 결과 보고서 발표 | ⬜ |

## Day1 — 환경·계획·Before

### 개발 환경

- [x] Base AI Agent를 `project/`에 원본 구조 그대로 옮김 — `199c839`
- [x] `.venv`(Python 3.11) + 의존성, pytest·ruff — `199c839`
- [x] fake 백엔드 스모크 테스트 6개, CI, pre-commit 훅, 커밋 템플릿 — `199c839`
- [x] 원본 상태 첫 커밋에 `base` 태그 — `199c839`
- [x] Ollama 모델 준비: qwen3:0.6b · qwen3:8b · qwen3-embedding:0.6b
- [x] `project/.env` 작성 (LangSmith 키)
- [x] 안내 자료 실행 순서 1 → 2 → 3-1 → 4 동작 확인 (백엔드 :8100, 프론트 :8600, 웹 채팅)

### 과제·계획

- [x] Base 코드 분석 — 오분류·기본값 하드코딩·thinking 지연 재현 ([`01-plan.md`](01-plan.md#코드에서-확인한-사실))
- [x] 과제 선택: 1. Base AI Agent 개선 — `ee9c0fc`
- [x] 진행 계획(초안): 개선 항목 4 + 선택 1, 측정 계획, 일정 — `ee9c0fc`
- [x] 변경된 일정 반영 (마감 Day3 14시 → 13시) — `38131c0`
- [x] 항목별 상세 수정 설계 — `148984a`
- [x] Google Spread 등록용 표 정리 ([`01-plan.md`](01-plan.md#google-spread-등록용)) — `148984a`
- [ ] **(직접)** Google Spread에 선택 과제·진행 계획 등록 — 마감 Day1 17:00

### Before 측정 (`base`)

- [x] 측정 도구: 회귀 쿼리 `tools/measure_queries.py`, 노드 평가 `tools/eval_nodes.py` — `199c839`, `38131c0`
- [x] 평가 세트 3종: route 30 · target 15 · judge 12 — `38131c0`
- [x] 분류 Before: 23/30 (76.7%) — `runs/eval-route_before_20261020-101334.json`
- [x] 대상 시스템 Before: 6/15, 엉뚱한 진단 7건, timeout 1건 — `runs/eval-target_before_20261020-102502.json`
- [x] 검수 Before: 오염 초안 탐지 0/7 — `runs/eval-judge_before_20261020-103034.json`
- [x] 측정 격리: `scripts/measure-at`(커밋을 worktree로 꺼내 측정), 회귀 쿼리 질문마다 서버 새로 띄우기, 답변 작성 `write` 평가 — `468cf17`
- [ ] 답변 작성(`write`)·회귀 쿼리(`e2e`) Before — `scripts/measure-at base before write,e2e` (측정 중)
- [ ] 평가 세트 라벨 검토 — 고치면 Before 3종을 다시 잰다

## Day2 — 구현

항목마다 같은 순서로 닫는다: 브랜치 → 구현 → 테스트 → 측정 → 결정 기록 → 문서 → `main`에 merge.

### 항목 1 — Ollama thinking 제어 (`feat/ollama-think`)

- [x] `OllamaLLM.__init__`에 `think` 인자, `_chat`·`_chat_stream` payload에 반영 — `21961b1`
- [x] `server._build_llms`가 `OLLAMA_THINK` 읽기, `.env.example`에 항목 추가 — `21961b1`
- [x] 테스트 `tests/test_ollama_think.py` (payload 확인, ollama 없이, 9개) — `21961b1`
- [ ] `step1` 측정: 노드 평가 3종 + `write` + `e2e` → 항목 2~4의 Before
- [ ] 결정 기록 `0002` (한계: 추론을 끈 만큼 품질 변화) — 초안 작성, 수치 대기
- [ ] `02-measurement.md`·`01-plan.md` 상태 갱신, merge

### 항목 2 — 의미 라우터 (`feat/semantic-router`)

- [ ] `agent/embedding.py` — `OllamaEmbedder`, `cosine`, 질의 지시문
- [ ] `data/router_examples.json` — 클래스당 15~20문장, 평가 세트와 겹치지 않게
- [ ] `agent/router.py` — `LLMRouter`, `SemanticRouter`(상위 3개 평균, margin, LLM 폴백)
- [ ] `SupervisorDeps` 필드 추가, `server._build_components`, `route_node` 분기 + 이벤트 `method`·`scores`
- [ ] `ROUTER_MARGIN`을 예시 문장 leave-one-out으로 결정
- [ ] 테스트 `tests/test_router.py` (가짜 embedder, 예시↔평가 세트 겹침 0건)
- [ ] `step2` 측정: 분류 정확도·폴백 비율·route 지연
- [ ] 결정 기록 `0003` (한계: 예시 커버리지, margin, 메모리 2.4GB)
- [ ] 문서 갱신(아키텍처 다이어그램 포함), merge

### 항목 3 — 대상 시스템 추정·되묻기 (`feat/target-resolver`)

- [ ] `data/systems.json` 카탈로그 6개(설명 포함)
- [ ] `mcp_server.py` Resource `catalog://systems`, `mcp_client.find_resource`
- [ ] `agent/target.py` — `TargetResolver`(이름 매칭 → 대상 밖 → 설명 임베딩 → 되묻기)
- [ ] `plan_node` 변경(대상 없으면 research 0개 + `ClarifyRequested`, LLM plan은 대상 2개 이상일 때만)
- [ ] 새 노드 `clarify`, 조건 엣지 `plan → clarify | gate`
- [ ] auth-service 기본값 세 곳 삭제 (`_extract_system_name`, ollama·openai plan 프롬프트, `_guess_target(s)`)
- [ ] (선택) `web_chat.html` `STEP_LABELS`에 `ClarifyRequested`
- [ ] 테스트 `tests/test_target.py` + 스모크에 되묻기 경로
- [ ] `step3` 측정: target 정확도·되묻기·엉뚱한 진단
- [ ] 결정 기록 `0004` (한계: 과잉 되묻기, 카탈로그 관리)
- [ ] 문서 갱신, merge

### 항목 4 — 검수 근거 검증 (`feat/grounded-validator`)

- [ ] `agent/validator.py` — 형식 → 수치 대조 → LLM-as-judge
- [ ] 백엔드 3종 quality 클래스에 `judge()` (fake는 결정론)
- [ ] `validate_node` 분기 + 이벤트 `stage`·`reason`, 3회 실패 시 경고 문구
- [ ] 테스트 `tests/test_validator.py` (수치 대조가 정상 5건 통과·b2·b3·b4 탈락)
- [ ] `step4` 측정: 탐지율·오탐률·검수 지연 + 회귀 쿼리
- [ ] 결정 기록 `0005` (한계: 판정 모델 편향, 지연 증가)
- [ ] 문서 갱신, merge

### 항목 5 — runbook 의미 검색 (선택, `feat/runbook-rag`)

- [ ] `eval_nodes.py`에 `runbook` 하위 명령 추가, 키워드 규칙으로 Before 측정
- [ ] `agent/runbook.py` — `RunbookSelector`, `replan_check_node` 분기
- [ ] 측정·결정 기록 `0006`·merge — 시간이 없으면 항목째 뺀다

### Day2 저녁

- [ ] `final` 측정 시작: 노드 평가 3종 + 회귀 쿼리 (장애 질문이 오래 걸리므로 미루지 않는다)

## Day3 — 마무리 (13시 마감)

- [ ] `final` 결과를 [`02-measurement.md`](02-measurement.md)에 `base` → 최종 표로 정리
- [ ] 결정 기록마다 "한계와 트레이드오프" 채움 확인
- [ ] 결과 보고서 작성 (Google Spread)
- [ ] GitHub 원격 저장소 생성·push
- [ ] **(직접)** Git 주소·결과 보고서 주소 Google Spread 등록 — 마감 13:00
- [ ] 발표 자료: 문제 → 개선 포인트 → Before/After 수치 → 한계·추가 개선
- [ ] 발표 리허설 — 코드 설명 질문 대비(항목별 결정 기록이 답안)
- [ ] **(직접)** 발표 — 17:30까지

## 평가 기준별 근거 현황

| 기준 (배점) | 근거 | 현재 |
| --- | --- | --- |
| 기능 구현 완성도 (30) | 항목 1~4 동작 + 테스트 | 설계 완료, 구현 전 |
| Before/After 실측 (보너스 10) | `runs/` + `02-measurement.md` | Before 노드 평가 3종 완료, 회귀 쿼리 미측정 |
| 기술 요소 (30) | RAG(2·3·5), MCP(3), 의존성 주입(공통), LangSmith(공통), 모듈화(공통), 단위 테스트(공통) | 설계에 반영. Multi-Agent는 범위 밖 |
| 한계·트레이드오프 (20) | `decisions/` 각 결정 | 설계에 항목별 예상 한계 초안 |
| 발표 (20) | 발표 자료 | 미착수 |
