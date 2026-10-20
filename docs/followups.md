# 미해결 · 확인 대기

아직 확인하지 못했거나 미뤄 둔 것. 추측으로 메우지 않고 여기 남긴다. 해결하면 지우고
결과를 해당 문서로 옮긴다.

| 항목 | 상태 | 다음 행동 |
| --- | --- | --- |
| 진행 계획 Google Spread 등록 | 과제 1로 계획 작성 완료, 등록 전 | [`01-plan.md`](01-plan.md#google-spread-등록용) 표를 옮긴다 (Day1 17시까지) |
| 임베딩 API | `qwen3-embedding:0.6b`는 받아져 있으나 호출은 확인 전 | 항목 2 착수 전에 `/api/embed` 한 번 호출, 차원·지연 확인 |
| 평가 질문 세트 | 없음 | 분류 30문항(예시 문장과 겹치지 않게), 시스템 추정, 검수용 오염 초안 — Before 측정 전에 만든다 |
| Before 측정 | `base` 태그(`199c839`) 생성됨, 측정 전 | 모델·`.env` 준비 후 `base`에서 ollama로 `measure_queries.py run --label before` |
| ollama Before 측정 소요 시간 | incident 1건이 5분 넘게 끝나지 않는다(qwen3:8b thinking, [`01-plan.md`](01-plan.md#코드에서-확인한-사실)) | `measure_queries.py` 기본 timeout 300초에 걸려 오류로 남을 수 있다. 이 상태로 Before를 잴지, 시간 상한을 어떻게 둘지 개선 계획과 함께 정한다 |
| GitHub 원격 저장소 | 미생성 | 만든 뒤 Google Spread에 Git 주소 등록 (Day3 14시까지) |
| `project/sh/run_frontend.sh` 안내문 | 원본이 없는 `./sh/run.sh`(fake 모드)를 가리킨다 | 원본이라 두었다. fake 모드는 `sh/run_agent_fake.sh`를 쓴다 |
