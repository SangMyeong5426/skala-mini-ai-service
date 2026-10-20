# 0001: 저장소 구조와 개발 도구

- 상태: Accepted
- 날짜: 2026-10-20

## 문제

Base AI Agent(`all_total_vue_student`)는 실행 스크립트(`sh/`)와 매뉴얼(`doc/`)이 자기 폴더
구조를 전제로 쓰여 있다. 반면 이 과제는 계획·실측·결정·보고서 같은 산출물이 따로 필요하고,
평가는 개선 전/후 수치 비교와 단위 테스트를 본다. 원본은 테스트도 측정 도구도 없다.

## 결정

**원본은 `project/`에 그대로 두고, 과제 산출물은 그 바깥에 둔다.**

| 위치 | 담는 것 |
| --- | --- |
| `project/` | Base AI Agent. 원본 파일을 옮기거나 이름을 바꾸지 않는다. 개선은 이 위에 변경으로 쌓는다 |
| `project/tests/`, `project/pyproject.toml`, `project/requirements-dev.txt`, `project/sh/run_agent_fake.sh` | 원본에 더한 개발 도구 |
| `docs/` | 과제 요건, 진행 계획, 실측, 결정 기록 |
| `tools/` | 측정처럼 서버 밖에서 서버를 다루는 스크립트 |
| `runs/` | 실측 원자료 |

이전 미니 프로젝트(`skala-solar-aiops`)에서 강사 스켈레톤을 `project/`에 두고 문서·도구를 밖에
둔 구조를 그대로 따른다. 원본 경로가 유지되므로 안내 자료의 명령(`bash sh/setup_venv.sh` 등)이
`project/` 안에서 그대로 통한다.

**도구는 `venv` + `requirements.txt`, `ruff`, `pytest`.** 원본의 `sh/setup_venv.sh`가 이미
`project/.venv`(Python 3.11)를 만들므로 그 위에 `requirements-dev.txt`만 더한다.
`pyproject.toml`에는 도구 설정만 두고 패키징하지 않는다.

**테스트는 fake 백엔드로 그래프 전체를 실제로 돌린다.** `TestClient`가 lifespan을 실행해
MCP 서버 두 개를 subprocess로 띄우고, route·plan·gate·research·validate·세션·SSE를 지난다.
LLM·키·네트워크가 없어 CI에서도 돈다.

**ruff 규칙은 원본이 통과하는 범위에서 시작한다.** 원본에 이미 있던 위반 16건은 코드를 고치지
않고 `per-file-ignores`로 고정했다. 세팅 단계에서 원본을 고치면 그 변경이 개선 작업과 섞여
Before/After 비교의 기준점이 흐려진다.

## 한계와 트레이드오프

- 원본 `requirements.txt`는 `>=` 범위라 설치 시점마다 버전이 달라질 수 있다. 2026-10-20 설치
  결과(fastapi 0.150.0, langgraph 1.2.16, langchain-core 1.6.12, langsmith 0.14.11,
  fastmcp 4.1.1, mcp 2.3.0)는 여기 기록만 하고 고정하지 않았다. 원본을 바꾸지 않기 위해서다.
- 스모크 테스트는 fake 백엔드의 결정론적 응답에 기대므로, ollama/openai에서만 나는 문제(JSON
  형식 붕괴, 지연)는 잡지 못한다. 그건 `tools/measure_queries.py` 실측으로 본다.
- 테스트 하나가 MCP subprocess 두 개를 띄우므로 테스트가 늘면 느려진다(현재 6개, 약 7초).
