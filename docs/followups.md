# 미해결 · 확인 대기

아직 확인하지 못했거나 미뤄 둔 것. 추측으로 메우지 않고 여기 남긴다. 해결하면 지우고
결과를 해당 문서로 옮긴다.

| 항목 | 상태 | 다음 행동 |
| --- | --- | --- |
| 과제 선택 (1 또는 2) | 미정 | [`01-plan.md`](01-plan.md)에 적고 Google Spread 등록 (Day1 17시까지) |
| Ollama fast 모델 `qwen3:0.6b` | 미설치 (2026-10-20 확인, `qwen3:8b`는 있음) | `cd project && bash sh/setup_ollama.sh` — 실행 중인 ollama serve를 내렸다 다시 띄운다 |
| LangSmith 키 | `project/.env` 없음 | `cp -n project/.env.example project/.env` 후 `LANGCHAIN_API_KEY` 채우기 |
| Before 기준점 | 첫 커밋 전 | 원본 상태로 첫 커밋 후 `git tag base`, 그 커밋에서 ollama로 Before 측정 |
| GitHub 원격 저장소 | 미생성 | 만든 뒤 Google Spread에 Git 주소 등록 (Day3 14시까지) |
| `project/sh/run_frontend.sh` 안내문 | 원본이 없는 `./sh/run.sh`(fake 모드)를 가리킨다 | 원본이라 두었다. fake 모드는 `sh/run_agent_fake.sh`를 쓴다 |
