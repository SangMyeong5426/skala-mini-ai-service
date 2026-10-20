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

- [ ] `tools/fetch_ratings.py` — API 월별 수집, `data/ratings/raw/`
- [ ] 사례 DB `data/ratings/cases.json`(~2026-06), 기간 테스트
- [ ] 기준표 `criteria.json`, 시행규칙 `rule-8.md`

### 2. 평가셋 (기능 코드보다 먼저)

- [ ] 평가셋 A `rating.json` 40개 (2026-07~09, 시드 고정)
- [ ] `rating_route.json` 30 · `rating_clarify.json` 12 · `rating_judge.json` 12
- [ ] 회귀 쿼리 `queries_rating.json` 10개

### 3. 뼈대 + Before

- [ ] `mcp_server_rating.py` (Tool `rating_stats`, Resource 기준표·법령·사례)
- [ ] LLM 단독으로 끝까지 도는 등급 그래프, `AGENT_DOMAIN`
- [ ] `tools/eval_rating.py`, `scripts/measure-at` 단계
- [ ] Before 측정

### 4~6. 기능

- [ ] 유사 사례 검색 + 항목별 단계 판정(등급 = 단계 최댓값)
- [ ] 검수(형식 → 등급 일치 → 사례 → 수치 → LLM 판정)
- [ ] 의미 라우터 교체, 되묻기

### 7. After

- [ ] After 측정, 1차 표

## Day2 — 정리

- [ ] 반복 측정(repeat 3)
- [ ] 결정 기록, `02-measurement.md` 표, 결과 보고서, 아키텍처 다이어그램
- [ ] `main` 머지·push **(직접 승인)**
