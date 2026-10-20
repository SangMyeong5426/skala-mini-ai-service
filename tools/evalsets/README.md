# 평가 세트

[`tools/eval_nodes.py`](../eval_nodes.py)가 읽는 라벨 데이터다. 개선 항목 2·3·4의 Before/After를
같은 입력으로 재기 위해 둔다. 회귀 쿼리([`../queries.json`](../queries.json))는 지연시간 측정용이라 따로 있다.

| 파일 | 개수 | 부르는 노드 | 라벨 | 개선 항목 |
| --- | --- | --- | --- | --- |
| `route.json` | 30 (chat 15 · incident 15) | `route_node` | `expected_route` | 2 의미 라우터 |
| `target.json` | 15 (진단 10 · 되묻기 5) | `plan_node` | `expected_action`, `expected_targets`, `expected_runbook` | 3 대상 시스템 추정, 5 runbook |
| `judge.json` | 12 (정상 5 · 오염 7) | `validate_node` | `expected`(pass/fail), `defect` | 4 검수 강화 |
| `runbook.json` | 10 | `replan_check_node` | `expected_runbook` | 5 runbook 선택 |

조정용 문장(`../tuning/`)은 평가 세트가 아니다. 판정 기준(margin·min_score)을 정하는 데만 쓰고,
평가 세트로는 기준을 고르지 않는다.

## 라벨을 붙인 기준

- **route**: 지금 장애가 났다고 알리거나 확인을 요청하면 `incident`, 그 밖에(개념 설명, 운영 용어 질문,
  인사, 일상)는 `chat`. "장애 대응 보고서는 어떻게 쓰나요?"처럼 장애 단어가 있어도 지금 일어난
  장애가 아니면 `chat`이다.
- **target**: 모니터링 대상 6개(`project/data/monitoring.json`) 중 질문이 가리키는 시스템. 이름이
  없어도 뜻이 분명하면(로그인 → auth-service, 결제 → payments-service, 캐시 → cache-service,
  로그 → log-service) 그 시스템이다. 대상 밖 시스템이거나 특정할 수 없으면 `clarify`(되묻기)다.
  `expected_runbook`은 증상이 runbook 하나를 분명히 가리킬 때만 적고, 아니면 `null`이다.
- **judge**: 정상 초안은 수집된 수치·runbook만 정확히 인용하고 질문에 답한다. 오염 초안은 결함
  종류(`defect`)를 하나씩 심었다. `b1`만 실제 응답 원문이고(2026-10-20 웹 채팅, "ai 에이전트에 대해
  설명해줘" 오분류), 나머지는 손으로 썼다(`source`). runbook은 본문 대신 이름(`ref`)으로 적고
  스크립트가 `project/data/runbooks/`에서 읽어 넣는다.

- **runbook**: 증상이 runbook 하나를 분명히 가리키는 질문만 넣었다. 6문항(r01~r06)은 target 세트에서
  가져왔고, 4문항(r07~r10)은 **항목 5 설계 뒤에** 새로 썼다 — 모니터링에 아직 알림이 없거나 알림과
  질문 증상이 다른 경우다. 질문을 보지 않는 base 규칙의 약점을 겨냥한 문항이 들어 있다는 뜻이다.

## 지킬 것

- **라벨은 개선 코드를 보고 바꾸지 않는다.** 결과가 마음에 안 든다고 정답을 옮기면 Before/After가
  의미를 잃는다. 라벨이 틀렸다고 판단되면 고치고, **Before부터 다시 잰다**.
- 의미 라우터(항목 2)의 예시 문장은 이 파일의 질문과 겹치지 않게 따로 둔다. 겹치면 정답을 외운 것이 된다.
- 문항을 더하거나 빼도 Before부터 다시 잰다. 결과 파일의 `evalset`과 개수로 어느 세트로 쟀는지 남는다.

## 과제 2 — 게임 등급분류 사전 점검

[`tools/eval_rating.py`](../eval_rating.py)가 읽는다. **기능 코드보다 먼저** 만들었다(결정 [0010](../../docs/decisions/0010-rating-data-and-evalsets.md)).
회귀 쿼리는 [`../queries_rating.json`](../queries_rating.json)(10개, 11턴).

| 파일 | 개수 | 부르는 노드 | 라벨 | 기능 |
| --- | --- | --- | --- | --- |
| `rating.json` (A) | 40 (등급마다 10) | plan → research → replan_check → analysis | `label.rating`, `label.descriptors` | 3 사례 검색·단계 판정 |
| `rating_detail.json` (B) | 39 (전체 3 · 12세 7 · 15세 10 · 청소년이용불가 19) | 〃 | 〃 | 3 — 상세 설명일 때 |
| `rating_route.json` | 30 (chat 15 · review 15) | `route_node` | `expected_route` | 5 의미 라우터 |
| `rating_clarify.json` | 12 (되묻기 6 · 점검 6) | plan → … → analysis | `expected_action`(clarify/assess) | 6 되묻기 |
| `rating_judge.json` | 12 (정상 5 · 오염 7) | `validate_node` | `expected`(pass/fail), `defect` | 4 검수 |

- **rating(A)**: 평가 기간(2026-07-01 ~ 2026-09-30)의 실제 결정에서 [`../make_rating_evalset.py`](../make_rating_evalset.py)가
  시드 20261020으로 등급마다 10개씩 뽑았다. 사례 DB(~2026-06-30)와 기간이 겹치지 않는다. 입력은 장르·플랫폼·개요이고
  **제목은 뺐다.** 정답은 게임물관리위원회의 결정 등급과 내용정보다. 개요에 원작·시리즈 이름이 들어 있는 문항이
  있다(예: 디아블로 4) — 이름난 작품이면 LLM 이 외워서 맞힐 수 있고, Before·After에 똑같이 작용한다.
- **rating_detail(B)**: 한 문장 개요(A)로는 정확도 상한이 낮아 추가했다(결정 [0014](../../docs/decisions/0014-detail-evalset.md)).
  위원회 결정서의 등급분류 사유에서 결론("따라서 … 결정함")과 "＊ 기준어" 머리를 지우고 개요와 상세 서술만 남겼다
  (`make_rating_evalset.py detail`). 정답은 같은 등급분류번호의 API 결정 등급이다. 간소화 설문 결정(내용 서술 없음)과
  사행성 게임물은 뺐고, 남은 것을 모두 썼다(표본 추출 없음). 이 게임들은 사례 DB 기간(2026-04~06)에 있어 평가할 때
  자기 자신과 같은 제목의 사례를 검색에서 뺀다. 등급이 고르지 않다 — **늘 청소년이용불가라고 답해도 19/39**다.
  출처: 공공데이터포털 「게임물관리위원회_등급분류증명서 및 결정서 정보」 2026년 2분기(공공누리 1유형, 출처 표시),
  `source/grac_decision_reasons_2026q2.csv`(원본 CP949를 UTF-8로 바꿔 저장).
- **rating_route**: 출시할 게임 하나의 등급을 예상·점검해 달라면 `review`, 제도 질문·인사·기능 질문은 `chat`.
  등급 이름("청소년이용불가")이나 항목 이름("폭력성")이 들어 있어도 특정 게임의 점검이 아니면 `chat`이다.
- **rating_clarify**: 무엇을 하는 게임인지(내용·표현) 한 줄도 없으면 `clarify`, 짧아도 내용이 있으면 `assess`.
  장르·플랫폼·희망 등급만 있는 것은 `clarify`다.
- **rating_judge**: 사례·통계는 실제 사례 DB에서 가져왔고(`collected`), 판정 결과(`assessment`)와 초안은 손으로 썼다.
  오염 초안은 결함을 하나씩 심었다 — 예상 등급과 계산 등급 불일치(p1), 검색되지 않은 사례 인용(p2), 사례 등급 바꿔치기(p3),
  통계 수치 조작(p4), 판정에 없는 항목 근거(p5), 다른 게임 이야기(p6), 근거 없는 단정·잘못된 안내(p7).
