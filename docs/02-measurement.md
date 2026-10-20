# Before/After 실측 — 과제 2

과제 1 측정은 [`task1/02-measurement.md`](task1/02-measurement.md)에 있다.

## 측정 방법

- **Before = 스위치를 모두 끈 LLM 단독, After = 기본값.** 같은 커밋, 같은 평가셋에서 스위치만 바꾼다
  ([결정 0009](decisions/0009-rating-domain.md)).

  ```bash
  ROUTER=llm RATING_CLARIFY=off CASE_SEARCH=off RATING_ASSESSOR=direct VALIDATOR=format \
    MEASURE_QUERIES=tools/queries_rating.json scripts/measure-at <커밋> before rate,rroute,rclarify,rjudge,e2e
  MEASURE_QUERIES=tools/queries_rating.json scripts/measure-at <커밋> after rate,rroute,rclarify,rjudge,e2e
  ```

- 백엔드는 ollama — qwen3:0.6b(분류·대화), qwen3:8b(판정·작성·검수), qwen3-embedding:0.6b(사례 검색·라우터).
- 평가셋은 [`tools/evalsets/`](../tools/evalsets/)의 `rating*.json`, 회귀 쿼리는 [`tools/queries_rating.json`](../tools/queries_rating.json).

## 지표

| 지표 | 정의 |
| --- | --- |
| 등급 정확도 | 평가셋 A 40개 중 예상 등급이 실제 결정 등급과 같은 비율 |
| ±1단계 정확도 | 한 단계 차이까지 맞은 것으로 친 비율 |
| 과소평가 · 과대평가 | 실제보다 낮게 · 높게 본 건수. 과소평가가 더 위험하다(출시 후 등급 상향) |
| 되묻기로 끝남 | 평가셋 A에서 등급 대신 되물은 건수 — 오답으로 센다 |
| 내용정보 F1 | 예상한 내용정보 항목과 실제 항목의 마이크로 F1 |
| 분류 정확도 | 라우팅 평가셋 30문항 |
| 되묻기 정답률 | 되묻기 평가셋 12문항 |
| 탐지율 · 오탐률 | 검수 평가셋 — 오염 초안 7개 중 잡은 비율, 정상 초안 5개 중 막은 비율 |
| 지연 · 비용 | 단계별 지연 중앙값, 회귀 쿼리 왕복 시간, 토큰 × 가상 단가(`cost_usd`, 실제 청구액 아님) |

## 결과

TBD — 측정 후 적는다.
