# 3일 체크리스트

[`01-plan.md`](01-plan.md)(무엇을)와 [`03-design.md`](03-design.md)(어떻게)를 할 일 단위로 내린 목록이다.
끝낸 항목은 체크하고 근거(커밋·파일)를 옆에 적는다. 직접 해야 하는 일(Google Spread 등록 등)은
**(직접)**으로 표시했다 — 끝나면 체크해 달라.

마지막 갱신: 2026-10-20 (Day1) — 개선 항목 1~5 구현·측정을 Day1에 앞당겨 마쳤다.

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
- [x] 답변 작성 Before: 중앙값 34.8초 — `runs/eval-write_before_20261020-110710.json`
- [x] 회귀 쿼리 Before: 11턴 합계 411.4초, timeout 0 — `runs/e2e_before_20261020-111046.json`
- [x] runbook 선택 Before: 6/10 — `runs/eval-runbook_before_20261020-112839.json`
- [ ] 평가 세트 라벨 검토 — 고치면 Before부터 다시 잰다

## 구현 (계획상 Day2 — Day1에 진행)

항목마다 같은 순서로 닫았다: 브랜치 → 구현 → 테스트 → 측정 → 결정 기록 → 문서. 브랜치는 이어서 쌓았고
(`feat/ollama-think` → `feat/semantic-router` → `feat/target-resolver` → `feat/grounded-validator` →
`feat/runbook-rag`), `main` merge는 확인받은 뒤 한 번에 한다.

### 항목 1 — Ollama thinking 제어 (`feat/ollama-think`)

- [x] `OllamaLLM.__init__`에 `think` 인자, `_chat`·`_chat_stream` payload에 반영 — `21961b1`
- [x] `server._build_llms`가 `OLLAMA_THINK` 읽기, `.env.example`에 항목 추가 — `21961b1`
- [x] 테스트 `tests/test_ollama_think.py` (payload 확인, ollama 없이, 9개) — `21961b1`
- [x] `step1` 측정: 노드 평가 3종 + `write` + `e2e` — `runs/*_step1_*.json`
- [x] 결정 기록 `0002` — 대상 정확도 하락·대화 답변 품질 하락을 한계로 기록

### 항목 2 — 의미 라우터 (`feat/semantic-router`)

- [x] `agent/embedding.py` — `OllamaEmbedder`, `cosine` — `01e3ed9`
- [x] `data/router_examples.json` — 클래스당 20문장, 평가 세트와 겹치지 않게 — `01e3ed9`
- [x] `agent/router.py` — `LLMRouter`, `SemanticRouter`(상위 3개 평균, margin, LLM 폴백) — `01e3ed9`
- [x] `SupervisorDeps` 필드, `server._build_components`, `route_node` 분기 + 이벤트 `method`·`gap` — `01e3ed9`
- [x] margin을 예시 문장 leave-one-out으로 결정: 0.029, 지시문 없음 — `bdd205e`
- [x] 테스트 `tests/test_router.py` (가짜 embedder, 예시↔평가 세트 겹침 0건) — `01e3ed9`
- [x] 측정: 분류 30/30, 임베딩 29 · LLM 폴백 1 — `runs/eval-route_final_20261020-113756.json`
- [x] 결정 기록 `0003`

### 항목 3 — 대상 시스템 추정·되묻기 (`feat/target-resolver`)

- [x] `data/systems.json` 카탈로그 6개(설명 포함) — `eded3b5`
- [x] `mcp_server.py` Resource `catalog://systems`, `mcp_client.find_resource` — `eded3b5`
- [x] `agent/target.py` — `TargetResolver`(이름 매칭 → 대상 밖 → 설명 임베딩 → 되묻기) — `eded3b5`
- [x] `plan_node` 변경(대상 없으면 research 0개 + `ClarifyRequested`, LLM plan은 대상 2개 이상일 때만) — `eded3b5`
- [x] 새 노드 `clarify`, 조건 엣지 `plan → clarify | gate` — `eded3b5`
- [x] auth-service 기본값 — 지우지 않고 `TARGET_RESOLVER=legacy` 재현용으로 남김(설계 변경, [03](03-design.md#구현하며-바뀐-것-2026-10-20))
- [x] `web_chat.html` `STEP_LABELS`에 `ClarifyRequested` — `eded3b5`
- [x] 테스트 `tests/test_target.py` (규칙 + fake 그래프에서 MCP 카탈로그 실호출) — `eded3b5`
- [x] min_score 0.40 · margin 0.04를 조정용 문장으로 결정 — `bdd205e`
- [x] 측정: 대상 13/15, 되묻기 3/5, 엉뚱한 진단 2 — `runs/eval-target_final_20261020-113803.json`
- [x] 결정 기록 `0004`

### 항목 4 — 검수 근거 검증 (`feat/grounded-validator`)

- [x] `agent/validator.py` — 형식 → 수치 대조 → LLM-as-judge — `fcfdb87`
- [x] 백엔드 3종 quality 클래스에 `judge()` (fake는 늘 통과) — `fcfdb87`
- [x] `validate_node` 분기 + 이벤트 `stage`·`reason`, 3회 실패 시 경고 문구 — `fcfdb87`
- [x] 테스트 `tests/test_validator.py` (수치 대조가 정상 5건 통과·b2·b3·b4 탈락) — `fcfdb87`
- [x] 측정: 오염 초안 6/7, 정상 오탐 0/5, 검수 +3.5초 — `runs/eval-judge_final_20261020-113227.json`
- [x] 결정 기록 `0005`

### 항목 5 — runbook 의미 검색 (선택, `feat/runbook-rag`)

- [x] `eval_nodes.py`에 `runbook` 하위 명령, runbook 평가 세트 10문항, 키워드 규칙으로 Before — `6a552f6`
- [x] `agent/runbook.py` — `RunbookSelector`, `replan_check_node` 분기 — `6a552f6`
- [x] 측정: 8/10 — 단, 원래 문항만 보면 5/6 → 4/6 — `runs/eval-runbook_final_20261020-113405.json`
- [x] 결정 기록 `0006` (효과 불확실)

### 최종 측정

- [x] `final` 측정: 노드 평가 5종 + 회귀 쿼리 — 회귀 쿼리 11턴 411.4초 → 159.0초, timeout 0 — `runs/*_final_*.json`
- [x] base → step1 → final 표 ([`02-measurement.md`](02-measurement.md#결과-요약--base--final))
- [x] 아키텍처 다이어그램·소스 구조 갱신 (`project/doc/README.md`)
- [x] 대화 경로만 thinking 유지(`OLLAMA_THINK_CHAT`, `feat/chat-think`) — `32b59c1`, 결정 기록 `0007`
- [x] final2 재측정: 회귀 쿼리 110.8초, 대화 답 원래 수준 — `runs/e2e_final2_20261020-132116.json`
- [x] `main`에 merge
- [ ] 발표용 수치 확정: base·final2를 `--repeat 3`으로 재측정 (1회 측정 편차 ±30% 안팎)

## Day3 — 마무리 (13시 마감)

- [x] `final` 결과를 [`02-measurement.md`](02-measurement.md)에 `base` → 최종 표로 정리
- [x] 결정 기록마다 "한계와 트레이드오프" 채움 확인 (0002~0006)
- [ ] 결과 보고서 작성 (Google Spread)
- [ ] GitHub 원격 저장소 생성·push
- [ ] **(직접)** Git 주소·결과 보고서 주소 Google Spread 등록 — 마감 13:00
- [ ] 발표 자료: 문제 → 개선 포인트 → Before/After 수치 → 한계·추가 개선
- [ ] 발표 리허설 — 코드 설명 질문 대비(항목별 결정 기록이 답안)
- [ ] **(직접)** 발표 — 17:30까지

## 평가 기준별 근거 현황

| 기준 (배점) | 근거 | 현재 |
| --- | --- | --- |
| 기능 구현 완성도 (30) | 항목 1~5 동작 + 테스트 66개 | 구현·측정 완료, `main`에 merge |
| Before/After 실측 (보너스 10) | `runs/` + `02-measurement.md` | base·step1·final·final2 완료, 반복 측정은 남음 |
| 기술 요소 (30) | RAG(2·3·5), MCP(3 — Resource 추가), 의존성 주입(스위치·`SupervisorDeps`), LangSmith(새 단계 모두 `@traceable`), 모듈화(새 모듈 5개), 단위 테스트(6 → 66) | 반영. Multi-Agent는 범위 밖 |
| 한계·트레이드오프 (20) | `decisions/` 0002~0007 | 실측 기반으로 작성 |
| 발표 (20) | 발표 자료 | 미착수 |
