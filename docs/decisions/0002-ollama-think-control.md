# 0002: Ollama thinking 출력 제어

- 상태: Accepted
- 날짜: 2026-10-20
- 계획 항목: [`01-plan.md`](../01-plan.md) 순번 1 · 설계 [`03-design.md`](../03-design.md#항목-1--ollama-thinking-제어)

## 문제

`agent/ollama_llm.py`의 `_chat`·`_chat_stream`이 요청에 `think`를 보내지 않는다. Ollama 0.33 + qwen3는
이때 생각(thinking)을 켜고, 생각은 `message.thinking`이라는 별도 필드로 내보낸다. 코드는
`message.content`만 읽기 때문에 **생각은 화면에 한 글자도 나가지 않고 시간만 쓴다.**

실측(2026-10-20, 같은 기기):

- 답변 작성(qwen3:8b) — payments-service 질의에서 5,420토큰·5분 30초를 넘기고도 끝나지 않았다.
  다른 질의는 40.8초.
- 계획(qwen3:0.6b) — `결제가 자꾸 실패한다는 고객 문의가 들어오고 있어요`가 두 번 모두 300초 timeout.
  ollama 로그에는 한 호출이 5분 동안 36,132토큰을 만든 뒤 취소된 기록이 있다.
- 생성 길이에 상한이 없다. `num_predict`를 주지 않고, 컨텍스트(4096)를 넘겨도 앞부분을 밀어내며
  계속 만든다(로그의 `truncated = 1`).

## 검토한 선택지

### A. `think: false` — 생각을 끈다

옵션 하나로 끝난다. 생각에 쓰던 시간이 통째로 빠진다. 대신 모델이 추론 없이 바로 답하므로 분류·계획·답변
품질이 달라질 수 있다.

### B. 생각은 두고 `num_predict`로 길이 상한

폭주는 막지만, 생각이 먼저 나오므로 상한이 생각 도중에 걸리면 **답변이 빈 채로** 끝난다. 시간을 줄이는
게 아니라 실패를 빨리 낼 뿐이다.

### C. 생각도 화면에 스트리밍

사용자가 기다리는 동안 무언가 보이지만, 걸리는 시간과 폭주 위험은 그대로다. 운영 보고에 모델의 생각이
섞여 나오는 것도 맞지 않다.

### D. 생각하지 않는 모델로 교체

모델을 새로 받고 품질을 다시 검증해야 한다. 3일 범위를 넘는다.

## 결정

**A를 택하고 환경변수 스위치로 둔다.** `OLLAMA_THINK=false`(기본) · `true` · `default`.
`default`는 옵션을 보내지 않는 원본 동작이라 같은 코드로 Before를 재현할 수 있다. fast·quality 두 모델에
같은 값을 쓴다.

| 파일 | 변경 |
| --- | --- |
| `agent/ollama_llm.py` | 생성자 `think` 인자, 두 요청의 payload를 `_payload()`로 모아 `think` 반영 |
| `server.py` | `_ollama_think()` — 환경변수 해석, 잘못된 값이면 기동 시 오류 |
| `.env.example` | `OLLAMA_THINK` |
| `tests/test_ollama_think.py` | payload, 생각 필드가 답변에 섞이지 않음, 환경변수 해석 (ollama 없이) |

## Before/After

TBD — [`02-measurement.md`](../02-measurement.md)의 step1 절. `base`와 `step1`을 같은 입력·같은 방식
(`scripts/measure-at`)으로 잰다.

## 한계와 트레이드오프

- **추론을 끈 만큼 판단이 달라질 수 있다.** 분류(route)·계획(plan) 정확도와 검수 재작성 횟수로 감시한다.
  나빠진 항목이 있으면 fast만 끄고 quality는 켜는 조합을 따로 잰다 — 지금은 스위치 하나가 둘 다 바꾼다.
- **생성 길이 상한이 없는 근본 문제는 남는다.** 생각을 꺼도 모델이 반복 출력에 빠지면 길어질 수 있다.
  `num_predict` 상한이나 스트림 전체 시간 제한은 후속 과제로 [`followups.md`](../followups.md)에 둔다.
- 측정용 `default`를 남겨 두었으므로 운영에서 실수로 켜지 않도록 `.env.example`에 원본 동작이라고 적었다.
- openai 백엔드에는 해당 없다.
