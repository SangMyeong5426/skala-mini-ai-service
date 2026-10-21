# 체크리스트 — 과제 2

[`01-plan.md`](01-plan.md)(무엇을)와 [`03-design.md`](03-design.md)(어떻게)를 할 일 단위로 내린 목록이다.
끝낸 항목은 체크하고 근거(커밋·파일)를 옆에 적는다. 직접 해야 하는 일은 **(직접)**으로 표시했다 — 끝나면 알려 달라.
과제 1 체크리스트는 [`task1/checklist.md`](task1/checklist.md).

마지막 갱신: 2026-10-20 (Day1)

## 마감

| 마감 | 할 일 | 상태 |
| --- | --- | --- |
| Day1 17:00 | 과제 2 진행 계획 Google Spread 등록 **(직접)** | ⬜ |
| Day3 13:00 | Git 주소·결과 보고서 주소 Google Spread 등록 **(직접)** | ⬜ |
| Day3 17:30 | 개인별 결과 보고서 발표 **(직접)** | ⬜ |

## Day1 — 구현

### 0. 전환

- [x] `task1` 태그, 과제 1 문서를 `docs/task1/`로 옮기고 링크 정리
- [x] 계획·설계를 과제 2로, 항목 7 제외 결정 — [0009](decisions/0009-rating-domain.md)
- [ ] Google Spread 계획 등록 **(직접)**
- [x] 강사에게 "LLM 단독 vs 에이전트"를 Before/After로 인정하는지 문의 **(직접)** — 괜찮다는 답(2026-10-21, 사용자 확인)

### 1. 데이터

- [x] `tools/fetch_ratings.py` — API 월별 수집, `data/ratings/raw/` (2024-01~2026-09, 33개월 3,190건)
- [x] 사례 DB `data/ratings/cases.json`(~2026-06, 1,396건), 기간 테스트 `tests/test_rating_data.py`
- [x] 기준표 `criteria.json`, 시행규칙 `rule-8.md` — 사례집 재사용 조건은 확인 대기([followups](followups.md))

### 2. 평가셋 (기능 코드보다 먼저)

- [x] 평가셋 A `rating.json` 40개 (2026-07~09, 시드 고정) — `tools/make_rating_evalset.py`, [0010](decisions/0010-rating-data-and-evalsets.md)
- [x] `rating_route.json` 30 · `rating_clarify.json` 12 · `rating_judge.json` 12 — [`tools/evalsets/README.md`](../tools/evalsets/README.md)
- [x] 회귀 쿼리 `queries_rating.json` 10개(11턴)

### 3. 뼈대 + Before

- [x] `mcp_server_rating.py` (Tool `rating_stats`, Resource 기준표·법령·사례) — `b0cb295`
- [x] LLM 단독으로 끝까지 도는 등급 그래프, `AGENT_DOMAIN` — `b0cb295`
- [x] `tools/eval_rating.py`, `scripts/measure-at` 단계 — `b0cb295`
- [x] Before 1차 측정 `before0` (`b0cb295`) — 등급 14/40, 라우팅 15/30, 되묻기 6/12, 탐지 0/7

### 4~6. 기능

- [x] 유사 사례 검색 + 항목별 단계 판정(등급 = 단계 최댓값) — `242dcb4`, [0011](decisions/0011-case-search-and-item-levels.md)
- [x] 검수(형식 → 등급 일치 → 사례 → 수치 → LLM 판정) — `3024e52`, [0012](decisions/0012-rating-validator.md)
- [x] 의미 라우터 교체(margin 0.04), 되묻기 — `0876038`, [0013](decisions/0013-rating-router-and-clarify.md)

### 7. After

- [x] After·Before·사례 검색 끔 측정(`0876038`) — 등급 18/40 · 14/40 · 8/40, 분류 29/30 · 15/30, 되묻기 10/12 · 6/12, 탐지 7/7 · 0/7
- [x] 보고서 버그 수정 2건 — `1de544c`(사례 번호), `fbb9717`(사례 개요 수치·등급 낮추기 조언)
- [x] 상세 설명 평가셋 B(결정서 사유 39건)와 기준선 — `123c07e`, [0014](decisions/0014-detail-evalset.md)
- [x] 법령 근거 제도 안내(기능 8, 계획 후 추가) — `da1b049`, [0015](decisions/0015-law-grounded-answers.md)
- [x] 평가셋 B·기준선·제도 문의·최종 회귀 쿼리 측정 — `123c07e`·`da1b049`·`292ac84`
- [x] 결합 규칙: 개발용 38문항으로 R1 선택, A·B 한 번 확인 — `292ac84`, [0016](decisions/0016-combine-cases-and-criteria.md)
- [x] 법령 답변 조문 대조 검수 — `3d4af59`
- [x] 사례 DB 쏠림 원인 확인·수정(개요 없는 간소화 등급분류 결정 포함) — `18a9ba8`, [0017](decisions/0017-simplified-decisions-in-case-db.md)
- [x] 사례 DB 수정 뒤 개발용 다시 고르기(R1)와 최종 확인 — A 19/40 · B 27/39 · 평범한 게임 8/10 · 회귀 쿼리, `18a9ba8`·`133901f`(`runs/*check2*`)
- [x] `02-measurement.md` 표, 결정 기록 0009~0017 의 Before/After 칸
- [x] 발표 준비 노트(코드 변경·이유·과제 2 세부 기능 표·수치·한계·시연) — [`05-presentation-notes.md`](05-presentation-notes.md)
- [x] 발표·코드 학습 가이드(과제 안내의 발표 순서·평가 항목 기준 장표 구성안, 코드 따라 읽기, 자기 점검 문제) — [`06-study-guide.md`](06-study-guide.md)
- [x] 5분 발표 덱 9장(주제·task·결과·한계 2분 + Agent Graph·MCP·RAG 코드 3분) — `presentation/`(git에 넣지 않음), 장별 대본은 발표자 노트
- [x] 결과 보고서를 제출 형식으로(번호·성함, 기술 요소, 기능·최종 실행 화면 캡처, Before/After 화면 캡처, 느낀점) — [`04-report.md`](04-report.md), `docs/images/`, `tools/report_before_after.py`
- [x] 시연용 OpenAI 백엔드(등급 점검) — [0018](decisions/0018-openai-backend-for-rating-demo.md), `tests/test_rating_openai.py`, 실제 API 7턴·웹 화면 확인
- [x] 채팅 화면 문구를 등급 점검용으로(제목·입력 예시·진행 표시, `/health` 의 domain 기준) — `project/web_chat.html`, 웹 화면에서 확인
- [x] OpenAI 보조 측정(A·B·분류·제도 문의·평범한 게임 Before/After) — `ae379fc`, `runs/*oa-*`, [`02-measurement.md`](02-measurement.md) "보조 측정" 절
- [x] 결합 규칙 R1 을 기본값으로 둘지 **(직접)** — 유지로 결정(2026-10-21), [0016](decisions/0016-combine-cases-and-criteria.md)

## Day2 — 정리

- [x] 반복 측정(repeat 3) — 회귀 쿼리 Before/After 3회, `f585537`, `runs/e2e_r3-*`, [`02-measurement.md`](02-measurement.md) "반복 측정" 절
- [x] 결정 기록, `02-measurement.md` 표, 결과 보고서, 아키텍처 다이어그램 — 0009~0018, [`04-report.md`](04-report.md), `project/doc/README.md`(`3d40556`)
- [ ] `main` 머지·push **(직접 승인)**
