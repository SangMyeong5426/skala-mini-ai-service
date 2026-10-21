# 상세 설계 — 과제 2 (게임 등급분류 사전 점검)

[`01-plan.md`](01-plan.md)의 기능을 **어느 파일·함수를 어떻게 만드는지**까지 내린 문서다.
과제 1 설계는 [`task1/03-design.md`](task1/03-design.md).

## 구현하며 바뀐 것 (2026-10-20)

계획 그대로 가지 않은 것과 이유. 근거는 각 결정 기록에 있다.

| 계획 | 실제 | 이유 |
| --- | --- | --- |
| `task1` 태그만 달고 01·03 문서를 바꿔 쓴다 | 과제 1 문서 5개를 `docs/task1/`로 옮기고 링크를 고쳤다 | 결정 기록 0002~0008이 과제 1 문서의 절을 가리킨다. 바꿔 쓰면 뜻이 달라진다 |
| 아케이드만 뺀다 | 베팅성 보드게임도 뺐다(사행성 게임물 범위 밖) | 사례 기간 328건 중 327건이 청소년이용불가 — 장르만으로 정답이 정해져 비교가 흐려진다([0010](decisions/0010-rating-data-and-evalsets.md)) |
| 판정 프롬프트에 통계를 넣는다 | 통계는 보고서에만 쓴다 | 위원회 데이터는 모바일이 청소년이용불가 쪽으로 쏠려 있다(모바일 퍼즐 38건 중 28건) — 판정을 끌어올릴 수 있다([0011](decisions/0011-case-search-and-item-levels.md)). 당시 사례 DB 기준이고, 쏠림의 주된 원인은 사례 DB 필터였다([0017](decisions/0017-simplified-decisions-in-case-db.md)) |
| 판정 근거는 설명 구절만 | 설명 구절 **또는 검색된 사례 번호**(그 항목이 붙은 사례) | 실제 개요는 한 문장(중앙값 43자)이라 구절만으로는 근거가 거의 없다. 사례 근거도 코드가 검사한다(0011) |
| 되묻기는 길이·단서 규칙 + 이력 | 판정 전 길이 규칙(15자) + **판정 후 판정 LLM 의 described** | 길어도 내용이 없는 질문은 규칙으로 못 잡는다([0013](decisions/0013-rating-router-and-clarify.md)) |
| 라우터 margin 은 과제 1 규칙(틀린 예시 |gap| 최댓값 + 0.005) | 대체 LLM 의 예시 정답률까지 넣은 결합 정답률로 골랐다(0.04) | 과제 1 규칙대로면 0.066 — 예시의 절반 가까이를 0.6b 에 넘기는데, 0.6b 는 예시에서도 16/30(0013) |
| Before·After를 같은 커밋에서 | 1차 Before(`before0`)는 뼈대 커밋 `b0cb295`, 발표용 Before·After는 `0876038`에서 함께 | 1차는 측정 경로를 일찍 검증하려고 겹쳐 돌렸다. 비교는 같은 커밋의 것만 쓴다 |
| 항목 7(항목별 심사 서브에이전트, 선택) | 뺐다 | 등급은 최댓값 하나로 정해져 이득이 없고, 과대평가·지연 위험이 커진다([0009](decisions/0009-rating-domain.md)) |
| 평가는 평가셋 A(한 문장 개요)만 | 상세 설명 평가셋 B(위원회 결정서 사유 39건)와 기준선(사례 다수결 등)을 더했다 | 개요가 짧아 정확도 상한이 낮다. 상세 설명일 때와 사례만 쓸 때를 함께 봐야 당시 정확도(평가셋 A 18/40)를 읽을 수 있다([0014](decisions/0014-detail-evalset.md)) |
| 제도 문의는 0.6b 대화 그대로 | 법령 조문 검색 + 인용·수치 코드 검사, 근거가 없으면 "답할 수 없음"(기능 8, 계획 후 추가) | 0.6b 가 "청소년이용불가는 14세 이상"이라고 틀리게 답했다 — 사용자 제안([0015](decisions/0015-law-grounded-answers.md)) |
| 보고서는 작성 모델이 자유롭게 쓴다 | 사례 번호를 숨기고, 사례 개요의 수치를 근거로 인정하고, "등급을 낮추려면"은 기준표로 코드가 계산 | 회귀 쿼리에서 점검 답변 6건 중 3건이 재작성 3회 뒤 경고로 나갔다(사례 번호·개요 숫자가 수치 대조에 걸림, 틀린 조언) |
| 사례는 판정의 근거로만 쓴다 | 결합 규칙 R1 — 기준표 판정과 가장 가까운 사례의 등급 중 높은 쪽 | 사례 1건만 보는 기준선(23/40)이 에이전트(18/40)보다 높았다. 후보 5개와 고르는 기준을 결과 전에 적고 개발용 문항으로 골랐다([0016](decisions/0016-combine-cases-and-criteria.md)) |
| 사례 DB 는 개요 있는 결정만 | 개요 없는 결정(대부분 간소화 등급분류)도 넣고, 평가 입력에만 개요를 요구한다(`usable_case` / `usable`) | "개요 있음" 필터가 청소년이용불가가 빠지는 간소화 결정을 지워 모바일 사례가 77% 청소년이용불가로 쏠렸다([0017](decisions/0017-simplified-decisions-in-case-db.md)) |

## 전제

- **오늘(Day1, 2026-10-20) 밤까지 구현과 1차 측정을 끝낸다.** Day2는 반복 측정·결정 기록·보고서,
  Day3는 발표 준비만 한다. 계획을 쓴 시각은 16시 15분이고, 남은 시간은 약 7시간이다.
- 과제 1 코드(인시던트 도메인)는 지우지 않는다. 새 도메인은 `agent/rating/`에 따로 두고 환경변수
  `AGENT_DOMAIN`으로 고른다. 기존 테스트와 측정이 그대로 돌고, 공용 부품(임베딩, 의미 라우터, 검수 틀,
  MCP 클라이언트, 스위치, 측정 도구)을 다시 쓴다.
- 브랜치는 `feat/game-rating` 하나로 하고 단계마다 커밋한다. 커밋마다 `pytest`·`ruff`를 통과시킨다.
  항목마다 브랜치를 나누는 과제 1 방식은 시간 때문에 쓰지 않는다.
- 사용자가 직접 할 일은 **(직접)**으로 표시한다. 측정 명령도 직접 실행한다.

## 구조

### 새로 만들거나 고치는 파일

```text
project/
  mcp_server_rating.py          새 MCP 서버 — Tool rating_stats, Resource criteria·law·cases
  data/ratings/raw/*.json       API 원자료(월별)
  data/ratings/cases.json       사례 DB — 2026-06-30까지 결정분
  data/ratings/criteria.json    내용정보 7항목 × 4단계 기준(출처 포함)
  data/ratings/rule-8.md        시행규칙 제8조
  data/ratings/router_examples.json
  agent/rating/llm.py           도메인 프롬프트 — Ollama fast/quality, fake
  agent/rating/graph.py         등급 점검 그래프
  agent/rating/assess.py        단계 → 등급 규칙, 근거 인용 검사 (순수 함수)
  agent/rating/cases.py         유사 사례 검색 (제목·장르·플랫폼·개요 임베딩 kNN)
  agent/rating/check.py         검수 (형식 → 사실 대조 → LLM 판정)
  agent/deps.py                 필드 추가
  agent/mcp_client.py           find_tool 추가, rating 서버 등록
  agent/router.py               라벨 이름 일반화 (incident 고정 → 인자로)
  server.py                     AGENT_DOMAIN 분기, 등급 부품 조립
  tests/test_rating_*.py
tools/
  fetch_ratings.py              API 수집·분할
  make_rating_evalset.py        평가셋 A 표본 추출 (시드 고정)
  eval_rating.py                rate · rroute · rclarify · rjudge
  evalsets/rating*.json         평가셋 4종
  queries_rating.json           회귀 쿼리 10개
scripts/measure-at              단계 추가, MEASURE_QUERIES
```

### 그래프 — 같은 뼈대, 다른 도메인

노드 이름과 이벤트 타입은 과제 1과 같게 둔다. 프론트(`web_chat.html`)를 고치지 않고 그대로 쓰기 위해서다.

| 노드 | 과제 1 (인시던트) | 과제 2 (등급 점검) |
| --- | --- | --- |
| route | 일반 대화 / 장애 신고 | 제도 문의·잡담 / 점검 요청 |
| plan | 대상 시스템 추정, 모르면 clarify | 장르·플랫폼·설명 정리, 정보가 모자라면 clarify. 켜진 부품에 맞춰 조사 task를 만든다 |
| clarify | 시스템 목록으로 되묻기 | 7항목 체크리스트로 되묻기 |
| research | 모니터링 Tool + runbook Resource | 통계 Tool + 기준표 Resource + 유사 사례 검색 |
| replan_check | runbook이 없으면 추가 조사 | 사례가 3건 미만이면 검색 범위를 넓혀(장르 → 플랫폼 → 전체) 다시 조사 |
| analysis | 패턴 분석(선택) | **항목별 단계 판정 → 등급 = 단계 최댓값** (항상 실행) |
| write → validate | 재작성 루프 최대 3회 | 같은 루프, 검수 내용만 바꾼다 |
| gate | 섞여 든 analysis task 제거 | 뺀다 — LLM이 task를 만들지 않는다 |

### 스위치 — 모두 끄면 Before(LLM 단독)

지정하지 않으면 fake 만 원본 쪽이고 ollama·openai 는 개선 쪽이 기본이다(`server._rating_switch`). openai 는 시연용이고 측정에 쓰지 않는다([0018](decisions/0018-openai-backend-for-rating-demo.md)).
과제 1(인시던트)은 그대로 — openai 는 원본 쪽이 기본이다.

| 환경변수 | After (기본) | Before | 하는 일 |
| --- | --- | --- | --- |
| `AGENT_DOMAIN` | `rating` | — | `incident`면 과제 1 그대로 |
| `ROUTER` | `semantic` | `llm` | 과제 1 의미 라우터를 등급 예시 문장으로 |
| `RATING_CLARIFY` | `rule` | `off` | 정보가 모자라면 되묻기 |
| `CASE_SEARCH` | `semantic` | `off` | 유사 사례 검색 + 통계 Tool |
| `RATING_ASSESSOR` | `criteria` | `direct` | 기준표로 항목별 단계 판정 / LLM이 등급을 바로 답함 |
| `VALIDATOR` | `grounded` | `format` | 사실 대조 검수 / 형식만 |

Before는 `ROUTER=llm RATING_CLARIFY=off CASE_SEARCH=off RATING_ASSESSOR=direct VALIDATOR=format`이다.
부품을 하나씩 끄면 어느 부품이 얼마나 기여했는지도 잴 수 있다 — 한계·트레이드오프 근거로 쓴다.

### LLM 호출 — fast/quality 분리는 그대로

| 메서드 | 모델 | 언제 |
| --- | --- | --- |
| `fast.route` | qwen3:0.6b | Before 라우팅, 의미 라우터가 판정을 미룰 때 |
| `fast.chat` | qwen3:0.6b | 제도 문의·잡담 |
| `quality.assess` | qwen3:8b | 7항목 단계 JSON — 기준표·사례·통계를 함께 준다 |
| `quality.rate_direct` | qwen3:8b | Before — 설명만 보고 등급·내용정보 JSON |
| `quality.write` | qwen3:8b | 점검 보고서 |
| `quality.judge` | qwen3:8b | 검수 마지막 단계 |

## 단계별 구현

시간은 목표다. 밀리면 [덜어 내는 순서](#덜어-내는-순서)대로 뺀다.

### 0. 확정·등록 (16:15–16:45)

- **(직접)** Google Spread 계획 등록(17시 마감) — `01-plan.md` 맨 끝 표.
- **(직접)** 강사에게 "LLM 단독 vs 에이전트"를 Before/After로 인정하는지 문의.
- `main`의 지금 커밋에 `task1` 태그를 달고, 과제 1 문서(계획·측정·설계·보고서·체크리스트)를 `docs/task1/`로 옮겨
  링크를 고친다. 결정 기록 0001~0008은 공용 부품의 근거라 그 자리에 둔다.
- 브랜치 `feat/game-rating`. 확인 못 한 것을 `followups.md`로.

### 1. 데이터 (16:45–17:30)

- `tools/fetch_ratings.py` — API를 월 단위로 받아 `data/ratings/raw/YYYY-MM.json`에 저장한다. 시작 시점은
  2024-01로 하되, 오래된 달의 개요 채움률을 보고 정한다(평가 결과를 보고 정하지 않는다).
- 분할: `cases.json` = 2026-06-30까지 결정분 중 개요 있음 · 4개 연령 등급 · 아케이드 제외. (→ 개요 조건은 0017 에서 사례 DB 에서 뺐다)
  평가용(2026-07~09)은 2단계에서 뽑는다.
- `criteria.json` — 사례집 요약표(7항목 × 4단계, 열 = 전체·12·15·청불)를 옮기고 출처를 적는다.
  옮기기 전에 GRAC 홈페이지 저작권 정책을 확인한다.
- `rule-8.md` — 국가법령정보센터의 시행규칙 제8조.
- 완료 기준: 건수·채움률 출력. 테스트로 "사례 DB의 최신 결정일 ≤ 2026-06-30"을 고정한다.

### 2. 평가셋 먼저 (17:30–18:15)

기능 코드를 쓰기 전에 만들고, 결과를 본 뒤에는 고치지 않는다.

| 파일 | 내용 | 채점 |
| --- | --- | --- |
| `evalsets/rating.json` (A) | 2026-07~09 결정분, 등급별 10개씩 40개(시드 고정). 입력 = 장르·플랫폼·개요. **제목은 뺀다** — LLM이 유명 게임 등급을 외워서 맞히지 않게 | 정확도, ±1단계 정확도, 과소평가 건수, 내용정보 F1 |
| `evalsets/rating_route.json` | 제도 문의·잡담 15 + 점검 요청 15 | 분류 정확도 |
| `evalsets/rating_clarify.json` | 충분한 설명 6 + 모자란 설명 6("우리 게임 몇 세야?") | 되묻기 정답률 |
| `evalsets/rating_judge.json` | 정상 5 + 오염 7(등급 불일치, 없는 사례, 사례 등급 조작, 통계 조작, 없는 기준 문구, 무관한 게임, 근거 없는 단정) | 탐지율, 오탐률 |
| `queries_rating.json` | 회귀 쿼리 10개(제도 문의 3, 점검 4, 정보 부족 2, 되묻기 후 보충 1) | 지연·비용 |

- 라우터 예시 문장(`data/ratings/router_examples.json`)은 평가셋과 겹치지 않게 따로 쓴다.
- `tools/evalsets/README.md`, `project/doc/regression_test_queries.md`를 함께 고친다.
- 2단계와 3단계는 파일이 겹치지 않아 세션 두 개로 나눠 돌릴 수 있다(원하면).

### 3. 뼈대 + Before (18:15–19:30)

- `mcp_server_rating.py`
  - Tool `rating_stats(genre, platform)`: 사례 DB에서 같은 장르·플랫폼의 등급 분포와 내용정보 빈도.
  - Resource `criteria://descriptors`, `law://game-industry/rule-8`, `ratings://cases`.
  - `mcp_client.py`에 rating 서버를 등록하고 `find_tool`을 더한다. 과제 1처럼 어느 서버가 제공하는지
    조회한 뒤에 부른다.
- `agent/rating/llm.py` — Ollama·fake 두 가지. 이번 단계에는 `route`·`chat`·`rate_direct`·`write`만.
- `agent/rating/graph.py` — 부품이 모두 `None`이면 LLM 단독으로 끝까지 돈다.
- `server.py` — `AGENT_DOMAIN` 분기. 기본값은 `rating`이고, `conftest.py`는 기존 테스트를 위해 `incident`로 고정한다.
- `tools/eval_rating.py`, `scripts/measure-at`에 단계 추가(`rate`, `rroute`, `rclarify`, `rjudge`, e2e는 `MEASURE_QUERIES`).
- 완료 기준: fake 백엔드로 등급 그래프가 끝까지 돈다(`tests/test_rating_smoke.py`).
- **(직접) Before 측정 시작**:

  ```bash
  ROUTER=llm RATING_CLARIFY=off CASE_SEARCH=off RATING_ASSESSOR=direct VALIDATOR=format \
    MEASURE_QUERIES=tools/queries_rating.json scripts/measure-at HEAD before rate,rroute,rclarify,rjudge,e2e
  ```

  측정하는 동안 같은 ollama를 쓰지 않는다. 4단계 코딩은 fake 테스트로만 확인한다.

### 4. 핵심 — 단계 판정 + 유사 사례 (19:30–20:45)

- `agent/rating/assess.py`
  - `rating_from_levels(items)`: 해당 항목 단계의 최댓값을 등급으로 바꾼다(0 = 전체이용가 … 3 = 청소년이용불가).
  - `ungrounded_evidence(items, description)`: LLM이 근거로 인용한 문구가 설명에 실제로 있는지 본다.
    없으면 그 항목의 근거를 지우고 이벤트에 남긴다.
- `quality.assess` — 기준표 28문장, 유사 사례 5건(등급·내용정보), 통계를 주고 항목마다
  `{present, level, evidence}`를 JSON 스키마로 받는다. **등급은 LLM이 아니라 코드가 정한다.**
- `agent/rating/cases.py` — `CaseRetriever`: 서버 기동 때 사례 글(제목 — 장르 · 플랫폼 — 개요)을 한 번 임베딩해 두고(`ratings://cases`),
  질문과 가까운 사례 k=5를 고른다. 장르·플랫폼 필터 → 3건 미만이면 replan_check가 범위를 넓힌다.
  기동이 10초를 넘으면 임베딩을 파일로 캐시한다(gitignore).
- 테스트: 최댓값 규칙, 근거 검사, 필터·넓히기(가짜 임베더).

### 5. 검수 (20:45–21:30)

`agent/rating/check.py` — 과제 1 검수처럼 싼 것부터 보고, 앞에서 떨어지면 뒤는 부르지 않는다.

1. 형식: "예상 등급:" 줄이 있는가.
2. 등급 일치: 초안의 예상 등급이 코드가 계산한 등급과 같은가.
3. 사례 일치: 초안에 나온 사례 게임이 검색된 사례 안에 있고, 같은 줄의 등급이 실제와 같은가.
4. 수치 대조: 통계 수치가 Tool 결과에 있는가 — 과제 1의 `ungrounded_numbers`를 다시 쓴다.
5. LLM 판정: 질문과 관련 있는가, 근거와 맞는가(도메인 프롬프트).

### 6. 라우터 + 되묻기 (21:30–22:00)

- `SemanticRouter`에서 `incident`로 고정된 라벨을 인자로 받게 바꾼다. 예시 문장을 교체하고
  `tune_embedding.py --examples`로 margin을 다시 정한다(ollama 사용 — Before 측정이 끝난 뒤).
- 되묻기 규칙: 요청 문구를 뺀 설명이 짧거나, 장르·플랫폼·내용 단서가 하나도 없으면 체크리스트로 묻는다.
  직전 답이 되묻기였으면 이전 사용자 메시지를 이어 붙여 판정한다(세션 이력 사용).

### 7. After 측정 (22:00–23:00)

- **(직접)** 같은 커밋, 기본 스위치로 After를 잰다:

  ```bash
  MEASURE_QUERIES=tools/queries_rating.json scripts/measure-at HEAD after rate,rroute,rclarify,rjudge,e2e
  ```

- 부품 하나 끈 비교(1회): `CASE_SEARCH=off`로 `rate`만 — 사례 검색이 정확도와 지연에 주는 영향.
- `02-measurement.md`에 1차 표. 정리는 Day2에 한다.

### 8. 선택 (23:00~)

- ~~항목별 심사 서브에이전트~~ — 검토 후 뺐다. 등급은 가장 높은 항목 하나로 정해지므로 항목을 나눠 심사해도
  최종 등급에 더해지는 정보가 없고, 판정을 7번 따로 하면 그중 하나라도 높게 볼 확률이 커져 과대평가가 늘며,
  로컬 ollama는 요청을 차례로 처리해 지연이 약 7배가 된다. 정답 데이터에 항목별 단계가 없어 효과를 잴 수도 없다
  ([0009](decisions/0009-rating-domain.md)).
- 결정서 사유 167건 RAG.

## 덜어 내는 순서

8(결정서 RAG) → 6의 되묻기 → 6의 라우터 재조정(LLM 라우팅 유지) → 5의 LLM 판정(코드 검사만 남김) → 평가셋 judge.
**마지노선은 1~4와 7의 `rate`**다. 이것만 있어도 "LLM 단독 vs 기준표+사례" 등급 정확도 비교가 나온다.

## 지킬 것

- 평가셋은 기능 코드보다 먼저 만들고, 결과를 본 뒤에 고치지 않는다.
- 판정 기준(margin 등)은 평가셋이 아니라 예시 문장 leave-one-out으로 정한다.
- 사례 DB에 평가 기간(7~9월)이 섞이지 않게 테스트로 고정한다.
- 같은 신청자의 비슷한 게임이 사례에 있으면 답이 새는 것처럼 작동할 수 있다 — Day2에 평가 게임과
  같은 신청자의 사례 비율을 세서 한계로 적는다.
- 새 환경변수는 단계마다 `.env.example`과 README 스위치 표에 적는다. 그래프 다이어그램(`project/doc/README.md`)은 Day2에 고친다.

## Day2로 넘기는 것

반복 측정(repeat 3), 결정 기록(0009~), `02-measurement.md`·`04-report.md`, 아키텍처 다이어그램,
`checklist.md`, main 머지, GitHub 원격 저장소.
