# 평가 세트

[`tools/eval_nodes.py`](../eval_nodes.py)가 읽는 라벨 데이터다. 개선 항목 2·3·4의 Before/After를
같은 입력으로 재기 위해 둔다. 회귀 쿼리([`../queries.json`](../queries.json))는 지연시간 측정용이라 따로 있다.

| 파일 | 개수 | 부르는 노드 | 라벨 | 개선 항목 |
| --- | --- | --- | --- | --- |
| `route.json` | 30 (chat 15 · incident 15) | `route_node` | `expected_route` | 2 의미 라우터 |
| `target.json` | 15 (진단 10 · 되묻기 5) | `plan_node` | `expected_action`, `expected_targets`, `expected_runbook` | 3 대상 시스템 추정, 5 runbook |
| `judge.json` | 12 (정상 5 · 오염 7) | `validate_node` | `expected`(pass/fail), `defect` | 4 검수 강화 |

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

## 지킬 것

- **라벨은 개선 코드를 보고 바꾸지 않는다.** 결과가 마음에 안 든다고 정답을 옮기면 Before/After가
  의미를 잃는다. 라벨이 틀렸다고 판단되면 고치고, **Before부터 다시 잰다**.
- 의미 라우터(항목 2)의 예시 문장은 이 파일의 질문과 겹치지 않게 따로 둔다. 겹치면 정답을 외운 것이 된다.
- 문항을 더하거나 빼도 Before부터 다시 잰다. 결과 파일의 `evalset`과 개수로 어느 세트로 쟀는지 남는다.
