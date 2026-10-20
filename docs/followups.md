# 미해결 · 확인 대기

아직 확인하지 못했거나 미뤄 둔 것. 추측으로 메우지 않고 여기 남긴다. 해결하면 지우고
결과를 해당 문서로 옮긴다.

| 항목 | 상태 | 다음 행동 |
| --- | --- | --- |
| 진행 계획 Google Spread 등록 | 과제 1로 계획 작성 완료, 등록 전 | [`01-plan.md`](01-plan.md#google-spread-등록용) 표를 옮긴다 (Day1 17시까지) |
| 임베딩 API | `qwen3-embedding:0.6b`는 받아져 있으나 호출은 확인 전 | 항목 2 착수 전에 `/api/embed` 한 번 호출, 차원·지연 확인 |
| 평가 세트 라벨 검토 | 작성자 검토 전 ([`tools/evalsets/`](../tools/evalsets/)). Before 3종은 이 라벨로 측정 완료 | 라벨이 틀렸다고 보면 고치고 Before를 다시 잰다 (route·target·judge 합쳐 수 분, target은 폭주 시 문항당 최대 5분) |
| 회귀 쿼리 지연시간 Before | 미측정 | 백엔드를 새로 띄운 직후 `measure_queries.py run --label before` — 장애 질문이 문항당 수 분 걸릴 수 있다 |
| Before 측정 | `base` 태그(`199c839`) 생성됨, 측정 전 | 모델·`.env` 준비 후 `base`에서 ollama로 `measure_queries.py run --label before` |
| 대화 이름 기억 (0.6b 한계) | 대화 경로만 thinking을 켜 원래 수준으로 되돌렸다([0007](decisions/0007-chat-keeps-thinking.md)). 그래도 이름 기억 3건 중 정답 1건 | 대화 이력에서 "제 이름은 X"를 코드로 뽑아 프롬프트에 사실로 넣기(fake 백엔드 방식), 또는 대화를 큰 모델로. 범위 밖 |
| runbook 선택 효과 (항목 5) | 8/10이지만 원래 문항만 보면 5/6 → 4/6 ([0006](decisions/0006-runbook-selector.md)) | 설계와 무관한 사람이 쓴 문항으로 다시 잰다. 그 전까지 효과를 주장하지 않는다 |
| "서버"·"사이트" → web-01 끌림 (항목 3) | 되물어야 할 질문 2건을 web-01로 진단 ([0004](decisions/0004-target-resolver.md)) | 시스템 설명 문구를 고치면 조정용 문장으로 기준을 다시 정한다. 평가 세트로 맞추지 않는다 |
| LLM 판정이 실제 응답 원문 b1을 놓침 (항목 4) | 같은 유형의 합성 초안 b5는 잡았다 ([0005](decisions/0005-grounded-validator.md)) | 판정 프롬프트·모델을 바꾸면 judge 평가로 다시 잰다 |
| LLM 생성 길이 상한 | 없음 — `num_predict` 미지정, 컨텍스트를 넘겨도 계속 생성. 스트림 호출은 300초 timeout도 사실상 안 걸린다(조각이 계속 오므로) | 항목 1 이후에도 반복 출력에 빠지면 길어질 수 있다. 상한·전체 시간 제한은 범위 밖 후속 과제 ([결정 0002](decisions/0002-ollama-think-control.md)) |
| 동기 HTTP 호출이 이벤트 루프를 막음 | `OllamaLLM._chat`이 async 노드 안에서 `httpx.post`(동기)를 부른다 — 호출 동안 서버의 다른 요청·SSE 전송이 멈춘다 | 코드로 확인만 했다. 범위 밖. 동시 사용자가 생기면 `httpx.AsyncClient`로 바꿀 후보 |
| GitHub 원격 저장소 | 미생성 | 만든 뒤 Google Spread에 Git 주소 등록 (Day3 14시까지) |
| `project/sh/run_frontend.sh` 안내문 | 원본이 없는 `./sh/run.sh`(fake 모드)를 가리킨다 | 원본이라 두었다. fake 모드는 `sh/run_agent_fake.sh`를 쓴다 |
