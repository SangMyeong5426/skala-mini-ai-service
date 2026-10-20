# 작업 규칙

SKALA 「AI 서비스 개발 Mini-project」(3일, 개인 과제) 저장소다. 이 문서는 이 저장소에서
작업할 때 지킬 규칙만 담는다. 개요와 실행 명령은 [`README.md`](README.md)에 있다.

## 이 문서는 두 이름으로 존재한다

`AGENTS.md`와 `CLAUDE.md`는 같은 문서다. 도구마다 읽는 파일이 달라 두 이름으로 둔다.
한쪽을 고치면 `cp CLAUDE.md AGENTS.md`로 다른 쪽을 맞추고 같은 커밋에 넣는다.
`scripts/check-rule-docs`가 pre-commit 훅과 CI에서 이것을 검사한다.

## 이 프로젝트의 성격

- Base AI Agent(운영 인시던트 대응 에이전트)를 **개선하거나(과제 1), 주제를 바꿔 새로
  만든다(과제 2).** 어느 쪽인지는 [`docs/01-plan.md`](docs/01-plan.md)에 적는다. 아직 TBD면
  과제 선택을 전제로 한 작업을 하지 않는다.
- 평가 기준은 [`docs/00-assignment.md`](docs/00-assignment.md)에 있다. 기능 30 · Before/After 10(보너스)
  · 기술 요소 30 · 한계·트레이드오프 20 · 발표 20.
- **작성자가 코드를 직접 설명할 수 있어야 한다**(과제 조건). 그래서 한 번에 크게 바꾸지 않는다.
  개선 항목 하나를 작게 나눠 바꾸고, 바꿀 때마다 왜 그렇게 했는지 결정 기록에 남긴다.
- **요청받은 것만 한다.** 계획 표에 없는 기능을 임의로 더하지 않는다. 3일 안에 못 끝낼 것을
  벌여 두면 발표에서 손해다.

## `project/`는 원본 구조를 지킨다

`project/`는 강사가 배포한 `all_total_vue_student`에서 출발한다.

- `server.py`, `web_demo_server.py`, `mcp_server.py`, `mcp_server_docs.py`, `web_chat.html`,
  `data/`, `sh/`, `doc/`는 옮기거나 이름을 바꾸지 않는다. 실행 스크립트와 매뉴얼이 이 경로를 전제로 한다.
- `agent/` 안을 여러 모듈로 나누는 것은 개선 범위다(모듈화). 그때는 `doc/README.md`의
  소스 디렉토리 구조와 아키텍처 다이어그램을 함께 고친다.
- 문서·도구·측정 결과는 `project/` 안에 두지 않는다. 각각 `docs/`, `tools/`, `runs/`에 둔다.
- 모든 명령은 `project/`에서 실행한다. 가상환경은 `project/.venv`(Python 3.11)다.
- 포트: 백엔드 8100, 프론트 8600, Ollama 11434. `sh/run_*.sh`는 기동할 때 해당 포트를
  점유한 프로세스를 강제 종료하고 `session.db`를 지운다.

## LLM 백엔드

| `LLM_BACKEND` | 언제 | 주의 |
| --- | --- | --- |
| `fake` | 테스트·CI·배관 확인 | 응답·비용이 고정 규칙이다. 성능 근거로 쓰지 않는다 |
| `ollama` | 기본 개발과 Before/After 측정 | 로컬 추론, 과금 없음 |
| `openai` | 시연이 꼭 필요할 때만 | **과금된다.** 에이전트는 사용자 확인 없이 이 모드를 띄우거나 요청을 보내지 않는다 |

## 수치

- **직접 실행해 얻은 값만 결과로 적는다.** 안내 자료의 예시나 다른 곳의 수치를 우리 결과 자리에 옮기지 않는다.
- Before/After는 같은 입력(`tools/queries.json`), 같은 백엔드·모델, 같은 repeat 수로 잰다.
  원자료는 `runs/`에 남기고, 표는 [`docs/02-measurement.md`](docs/02-measurement.md)에 옮긴다.
  `runs/`의 파일은 손으로 고치지 않는다.
- 서버를 새로 띄운 직후에 잰다. MCP 클라이언트가 프로세스 첫 모니터링 조회를 일부러 한 번
  실패시키므로 조건을 맞춰야 retry 횟수를 비교할 수 있다.
- `cost_usd`는 토큰 수 × 가상 단가의 추정이다. 실제 청구액이라고 쓰지 않는다.
- fake 백엔드로 잰 수치를 개선 효과의 근거로 쓰지 않는다.

## 코드와 문서를 함께 고친다

| 바꾸는 것 | 함께 맞출 곳 |
| --- | --- |
| 그래프 노드·엣지 | `project/doc/README.md` 아키텍처·시퀀스 다이어그램, `project/tests/`, `docs/01-plan.md` |
| `/chat` 응답의 `metadata` 필드 | `server.py`의 `_metadata`, `tools/measure_queries.py`의 `METRICS`, `docs/02-measurement.md` 지표 표 |
| 새 환경변수 | `project/.env.example`, `README.md` |
| 회귀 쿼리 | `tools/queries.json`, `project/doc/regression_test_queries.md` |
| 평가 세트 라벨·문항 | `tools/evalsets/*.json`, `tools/evalsets/README.md` — 바꾸면 Before부터 다시 잰다. 개선 코드를 보고 라벨을 옮기지 않는다 |
| `route_node`·`plan_node`·`validate_node`의 반환 모양 | `tools/eval_nodes.py`의 채점 약속(모듈 docstring) — plan이 되묻기를 할 때는 research task를 하나도 만들지 않는다 |
| 개선 항목 하나를 끝냈을 때 | `docs/01-plan.md` 상태, `docs/02-measurement.md` 결과, `docs/decisions/` 새 결정 |

## 검증

변경을 끝냈다고 말하기 전에 아래를 실행해 통과를 확인한다.

```bash
cd project
.venv/bin/python -m pytest
.venv/bin/ruff check .
```

동작을 바꾼 변경이면 테스트를 더한다. ruff 예외(`pyproject.toml`의 `per-file-ignores`)는 원본에
있던 위반이다 — 그 파일을 고칠 때 위반도 고치고 예외 줄을 지운다. 새 예외를 더하지 않는다.

## 문서

- 한국어로 쓴다.
- 아직 정하지 못한 칸은 지우지 말고 `TBD`로 둔다. 빈칸이 보여야 무엇이 남았는지 안다.
- 확인하지 못한 것은 [`docs/followups.md`](docs/followups.md)에 적는다. 추측으로 메우지 않는다.

## Git

- 커밋 제목: `type(scope): 요약` — type은 `feat` `fix` `refactor` `docs` `test` `chore` `ci` `perf`,
  scope는 `agent` `mcp` `api` `fe` `data` `eval` `docs` `infra`. 템플릿은 `.gitmessage`.
- 개선 항목 하나 = 브랜치 하나(`feat/<kebab-case>`)를 권한다. `main`은 항상 테스트가 통과하는 상태로 둔다.
- 원본 상태의 첫 커밋에 `base` 태그를 단다. Before 측정의 기준점이다. 태그를 옮기지 않는다.
- `git push --force`, `git reset --hard`, 이력 재작성을 하지 않는다.

## 안전

- 비밀값(LangSmith·OpenAI 키)을 파일에 쓰거나 화면에 출력하지 않는다. `.env`에만 두고 커밋하지 않는다.
  `.env.example`에는 형식만 남긴다.
- 과제 안내 PDF는 저작물이라 저장소에 넣지 않는다(`.gitignore`의 `*.pdf`).
