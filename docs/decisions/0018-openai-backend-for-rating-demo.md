# 0018: 등급 점검을 OpenAI 로도 띄운다 — 보내는 곳만 바꾸고 본 측정에는 쓰지 않는다

- 상태: Accepted
- 날짜: 2026-10-21
- 계획 항목: 시연 준비 (계획 표 밖 — 사용자 요청)

## 문제

사용자가 웹 화면에서 직접 써 보고 시연할 때 로컬 모델 대신 OpenAI API 를 쓰고 싶어 했다. 로컬 qwen3:8b 는 점검 한 번에 40~60초가 걸린다.
그런데 등급 점검 도메인은 `LLM_BACKEND=openai` 를 막아 두었다 — 과금이라 범위 밖으로 둔 것이다(`server._build_rating_llms`, 결정 0009 범위).

## 검토한 선택지

### A. Ollama 등급 클래스를 물려받아 보내는 곳(`_chat`·`_chat_stream`)만 OpenAI 로 바꾼다

프롬프트·JSON 스키마·응답 파싱·폴백이 qwen 때와 같다. 바뀌는 코드가 전송 두 메서드뿐이라 설명하기 쉽다.
Ollama 에 주던 JSON 스키마를 OpenAI 의 `response_format`(json_schema)으로 그대로 넘길 수 있다.

### B. OpenAI 용 프롬프트를 따로 쓴다

모델에 맞춰 다듬을 수 있지만, 같은 일을 하는 프롬프트가 두 벌이 되고 판정 규칙이 백엔드마다 달라진다.

### C. 과제 1 의 `OpenAILLM`(JSON 모드)을 쓴다

JSON 모드는 스키마를 강제하지 않아 지시문에 형식을 다시 적어야 한다 — B 와 같은 문제가 생긴다.

## 결정

**A를 택한다.** `agent/rating/llm.py`의 `OpenAITransport` + `OpenAIRatingFastLLM`(기본 gpt-4o-mini) · `OpenAIRatingQualityLLM`(기본 gpt-4o).
모델은 기존 `OPENAI_FAST_MODEL` · `OPENAI_QUALITY_MODEL` 로 바꾼다(새 환경변수 없음).

- **임베딩은 로컬 Ollama 를 그대로 쓴다**(qwen3-embedding:0.6b). 라우터 기준(0.04)과 사례·조문 임베딩 캐시가 이 모델 기준이다.
  그래서 OpenAI 로 띄워도 Ollama 가 떠 있어야 한다.
- **스위치 기본값**: 과제 2 는 openai 도 개선 쪽(에이전트)이 기본이다(`server._rating_switch`). 시연용으로 연 것이라 LLM 단독으로 뜨면 안 된다.
  과제 1(인시던트)의 규칙(openai 는 원본 쪽)은 그대로 둔다.
- **본 측정에는 쓰지 않는다.** Before/After 본 수치는 모두 Ollama(qwen3)로 잰 값이다. OpenAI 결과를 그 자리에 옮기지 않는다.
  사용자 요청으로 "강한 모델에서 상승폭이 줄지 않나"를 보는 **보조 측정**을 한 번 했고(2026-10-21), 별도 절·별도 표로만 둔다.
  이를 위해 `tools/eval_rating.py` · `scripts/measure-at` 가 openai 를 받는다(`ae379fc`).
- 테스트(`tests/test_rating_openai.py`)는 `httpx.MockTransport` 로 요청 모양·스트림·키 없음을 본다 — 실제 API 를 부르지 않는다.

## Before/After

본 측정 대상이 아니다. 2026-10-21 실제 API 로 7턴을 보내 동작을 확인했다(gpt-4o-mini / gpt-4o, 기록은 남기지 않음).
같은 날 보조 측정(Before/After)을 했다 — [`02-measurement.md`](../02-measurement.md) "보조 측정" 절.

- 상승폭: 등급 A +5 → +2, 등급 B +3 → +6, 질문 분류 +14 → −1, 제도 문의 +13 → +13, 평범한 게임 −1 → −4 (qwen → OpenAI).
- 강한 모델에서는 단순 분류의 이득이 사라지고, 근거·검증 구조(제도 문의)와 기준표 판정(상세 설명)의 이득은 남았다. 평범한 게임에서는 되묻기·R1 때문에 LLM 단독보다 나빴다.

- 7턴 모두 qwen 때와 같은 경로를 탔다(제도 문의 3 · 점검 3 · 되묻기 1). 한 턴에 1~7초(qwen 은 점검 40~60초).
- 같은 입력에서 답이 다를 수 있다. 예: "보스를 처치하는 장면에서 신체가 절단" — qwen 15세이용가, gpt-4o 청소년이용불가.
  "청소년이용불가는 몇 살부터" — gpt-4o 는 나이를 붙이지 않고 "청소년은 이용할 수 없다"(제21조)로 답했다.

## 한계와 트레이드오프

- **과금된다.** 요청마다 OpenAI 계정에 청구된다. `cost_usd` 는 토큰 수 × 가상 단가라 실제 청구액과 다르다.
- gpt-4o 판정은 평범한 설명(리듬·축구 게임)에도 "무슨 게임인지 알 수 없다"며 되물었다 — qwen 기준으로 쓴 되묻기 조건이 이 모델에는 너무 민감하다.
- 프롬프트·검수 규칙은 qwen 결과를 보며 다듬었고 OpenAI 에 맞춰 고치지 않았다. 보조 측정도 그대로 쟀다 — OpenAI 에 맞추면 수치가 달라질 수 있다.
- LangSmith 추적 이름이 물려받은 메서드의 것(`ollama_rating_*`)으로 남는다 — 모델 이름은 `usage.model` 에 `openai:…` 로 남는다.
- `sh/run_agent_openai.sh` 는 Ollama 를 띄우지 않는다. 먼저 `ollama serve` 가 떠 있어야 하고, 처음 기동이 20초를 넘으면
  스크립트의 상태 확인이 먼저 끝나 서버가 터미널에서 떨어져 돈다(스크립트는 원본 그대로 둔다).
