# 0006: runbook 선택을 의미 검색으로 (선택 항목)

- 상태: Accepted — **효과 불확실**, 아래 Before/After 참고
- 날짜: 2026-10-20
- 계획 항목: [`01-plan.md`](../task1/01-plan.md) 순번 5 · 설계 [`03-design.md`](../task1/03-design.md#항목-5--runbook-선택을-의미-기반으로-선택)

## 문제

`replan_check_node`는 수집한 모니터링 상태·알림 문구에서 키워드(latency·pool·cpu·memory·heap·timeout·
network·disk·down)를 순서대로 찾아 runbook을 고르고, 하나도 안 맞으면 `db-down`이다. **사용자가 말한
증상은 보지 않는다.** 그래서 알림이 아직 없는 시스템의 증상 신고는 늘 `db-down`, 알림이 여러 종류면 규칙
순서상 먼저 걸리는 쪽(대개 `cpu-spike`)이 된다. 안내 자료가 든 첫 번째 개선 예시이기도 하다.

## 결정

runbook 6종을 기동 때 임베딩해 두고(메타데이터 = 파일 이름 = incident_type), **"질문 + 수집한 알림 문구"와
가장 가까운 runbook**을 고른다. 고른 runbook의 본문 조회는 지금처럼 MCP Resource로 한다.

| 파일 | 변경 |
| --- | --- |
| `agent/runbook.py` | `RunbookSelector`, `load_runbooks`, `symptom_text` |
| `agent/graph.py` | `replan_check_node`가 선택기를 쓰고 이벤트에 `method`. 없으면 base 그대로 |
| `tools/evalsets/runbook.json` · `eval_nodes.py runbook` | 10문항 평가와 Before 측정 |

임계값과 키워드 폴백은 두지 않았다. 조정할 데이터가 없어 임계값을 정할 근거가 없고, base도 늘 무언가를
고른다. 지시문도 붙이지 않았다 — 같은 "질문 ↔ 문서" 구조인 대상 추정(0004)에서 지시문 없이가 나았다.

## Before/After

| 문항 | base (키워드) | final (의미 검색) |
| --- | --- | --- |
| 전체 10 | 6/10 | **8/10** |
| r01~r06 — target 세트에서 가져온 문항 | **5/6** | 4/6 |
| r07~r10 — 항목 5 설계 **뒤에** 쓴 문항 | 1/4 | 4/4 |

| 문항 | 정답 | base | final |
| --- | --- | --- | --- |
| r01 payments CPU 치솟음 + 응답 느림 | cpu-spike | ✓ | ✗ high-latency — "응답이 느려지고"에 끌렸다 |
| r04 gateway → payments 타임아웃 | network-timeout | ✗ cpu-spike | ✗ high-latency |
| r07 web-01 CPU 100% (알림 없음) | cpu-spike | ✗ db-down | ✓ |
| r08 web-01 메모리 증가 (알림 없음) | memory-leak | ✗ db-down | ✓ |
| r09 payments DB 연결 실패 (알림은 CPU) | db-down | ✗ cpu-spike | ✓ |

**좋아진 것은 전부 설계 뒤에 쓴 문항에서 나왔다.** 처음부터 있던 6문항에서는 오히려 하나를 잃었다.
질문을 보는 쪽이 "알림이 없거나 질문 증상과 다른" 상황을 고치는 것은 맞지만, 질문에 여러 증상이 섞이면
(r01: 느림 + CPU) 엉뚱한 쪽으로 끌린다. 평가 세트를 보고 규칙을 섞어 맞추지는 않았다. 원자료는
`runs/eval-runbook_before_20261020-112839.json`과 [`02-measurement.md`](../task1/02-measurement.md#final).

## 한계와 트레이드오프

- **효과가 불확실하다.** 10문항, 그중 4문항은 base의 약점을 알고 쓴 문항이다. 이 항목을 개선이라고 말하려면
  설계와 무관한 사람이 쓴 문항으로 다시 재야 한다. 그 전까지 발표에서는 "구조적 약점(질문을 안 봄)을
  고쳤지만 기존 문항에서는 1건 나빠졌다"로 말한다.
- **증상이 섞인 질문에 약하다.** 알림의 키워드 신호와 질문의 의미 신호를 함께 쓰는 방식이 후보지만,
  평가 세트를 본 뒤에 고르면 맞춘 것이 되므로 하지 않았다.
- **문서 6개짜리 검색이다.** 검색으로 얻는 이득이 작고, runbook이 바뀌면 다시 임베딩해야 한다(기동 시 자동).
- **인덱싱이 MCP를 거치지 않는다.** 본문 조회는 MCP Resource로 하지만, 임베딩용 본문은 `data/runbooks/`를
  직접 읽는다 — 데이터 출처가 두 갈래다. MCP에 runbook 목록 Resource를 두면 하나로 모을 수 있다.
- 스위치(`RUNBOOK_SELECTOR=keyword`)로 base 규칙으로 바로 되돌릴 수 있다.
