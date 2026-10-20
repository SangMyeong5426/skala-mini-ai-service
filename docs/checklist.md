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
- [ ] 강사에게 "LLM 단독 vs 에이전트"를 Before/After로 인정하는지 문의 **(직접)**

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
- [x] `02-measurement.md` 표, 결정 기록 0009~0016 의 Before/After 칸
- [ ] 결합 규칙 R1 을 기본값으로 둘지 **(직접)** — [followups](followups.md)

## Day2 — 정리

- [ ] 반복 측정(repeat 3)
- [ ] 결정 기록, `02-measurement.md` 표, 결과 보고서, 아키텍처 다이어그램
- [ ] `main` 머지·push **(직접 승인)**
