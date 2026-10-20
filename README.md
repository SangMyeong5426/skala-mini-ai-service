# skala-mini-ai-service

> SKALA — **AI 서비스 개발 Mini-project** (3일, 개인 과제)

운영 인시던트 대응 에이전트(Base AI Agent)를 개선하거나, 주제를 바꿔 새 AI Agent를 만든다.
LangGraph StateGraph · MCP(Tool/Resource/Prompt) · SSE 스트리밍 · SQLite 세션 · LangSmith
추적이 이미 조립된 상태에서 출발한다. 원본 설명은 [`project/doc/README.md`](project/doc/README.md).

| 항목 | 값 |
| --- | --- |
| 과제 | **1. Base AI Agent 개선** — 질문을 제대로 이해하고 근거 있는 답만 내보내는 에이전트 ([`docs/01-plan.md`](docs/01-plan.md)) |
| 요건·평가 기준 | [`docs/00-assignment.md`](docs/00-assignment.md) |
| 상세 수정 설계 | [`docs/03-design.md`](docs/03-design.md) |
| 진행 체크리스트 | [`docs/checklist.md`](docs/checklist.md) |
| Before/After 실측 | [`docs/02-measurement.md`](docs/02-measurement.md) |
| 결정 기록 | [`docs/decisions/`](docs/decisions/) |

## 빠른 시작 (macOS)

필요한 것: Python 3.11, [Ollama](https://ollama.com). 모든 명령은 `project/`에서 실행한다.

```bash
cd project
bash sh/setup_venv.sh                                    # .venv + requirements.txt (최초 1회)
./.venv/bin/python3 -m pip install -r requirements-dev.txt   # pytest, ruff
cp -n .env.example .env                                  # LangSmith 키를 채운다
bash sh/setup_ollama.sh                                  # qwen3:0.6b / qwen3:8b 준비 (최초 1회)
```

**`cp`에서 `-n`을 빼지 않는다.** 이미 키를 채운 `.env`를 말없이 덮어쓴다.

| 순서 | 무엇 | 명령 (`project/`에서) | 주소 |
| --- | --- | --- | --- |
| 1 | 백엔드 — 로컬 Ollama | `bash sh/run_agent_ollma.sh` | <http://127.0.0.1:8100> |
| 1' | 백엔드 — LLM 없이 (fake, 결정론) | `bash sh/run_agent_fake.sh` | <http://127.0.0.1:8100> |
| 1'' | 백엔드 — OpenAI (**과금**, y/N 확인) | `bash sh/run_agent_openai.sh` | <http://127.0.0.1:8100> |
| 2 | 프론트 — Vue 채팅 화면 (새 터미널) | `bash sh/run_frontend.sh` | <http://localhost:8600> |

### 개선 스위치

개선마다 환경변수 하나로 켜고 끈다. 값은 `project/.env`에 적거나 실행할 때 앞에 붙인다.
측정에서 원본 동작을 재현하거나, 문제가 생겼을 때 재배포 없이 끄는 데 쓴다.

| 환경변수 | 값 | 항목 |
| --- | --- | --- |
| `OLLAMA_THINK` | `false`(기본) · `true` · `default`(원본 동작 — 옵션을 보내지 않음) | 1 — [결정 0002](docs/decisions/0002-ollama-think-control.md) |

## 개발

```bash
cd project
.venv/bin/python -m pytest      # 스모크 테스트 — fake 백엔드, MCP subprocess까지 실제로 띄운다
.venv/bin/ruff check .          # 린트
```

Before/After 측정 — 잴 커밋을 worktree로 꺼내 그 코드로 잰다. ollama가 떠 있어야 한다
(자세한 방법은 [`docs/02-measurement.md`](docs/02-measurement.md#측정-방법)).

```bash
scripts/measure-at base before write,e2e
OLLAMA_THINK=false scripts/measure-at feat/ollama-think step1
```

clone 직후 한 번, 커밋 템플릿과 pre-commit 훅(AGENTS≡CLAUDE, `.env` 차단, ruff)을 켠다.

```bash
./scripts/setup-git-hooks
```

## 저장소 구조

```text
skala-mini-ai-service/
├── project/                 Base AI Agent (all_total_vue_student 원본 구조 그대로)
│   ├── server.py                FastAPI :8100 — /health /version /chat /chat/stream
│   ├── web_demo_server.py       채팅 화면 + 프록시 :8600
│   ├── web_chat.html            Vue 3 (CDN) 채팅 UI
│   ├── mcp_server.py            MCP "ops" — Tool·Resource·Prompt
│   ├── mcp_server_docs.py       MCP "docs" — decoy
│   ├── agent/                   그래프·LLM 백엔드 3종·MCP 클라이언트·세션·재시도
│   ├── data/                    monitoring.json, runbooks/ 6종
│   ├── doc/                     원본 매뉴얼
│   ├── sh/                      setup·run 스크립트 (+ run_agent_fake.sh)
│   ├── tests/                   스모크 테스트 (추가)
│   ├── pyproject.toml           ruff·pytest 설정 (추가)
│   ├── requirements.txt         원본 의존성
│   └── requirements-dev.txt     pytest·ruff (추가)
├── docs/
│   ├── 00-assignment.md         과제 요건·일정·평가 기준
│   ├── 01-plan.md               진행 계획 (Google Spread 등록 원본)
│   ├── 02-measurement.md        Before/After 실측
│   ├── 03-design.md             항목별 상세 수정 설계
│   ├── checklist.md             3일 체크리스트 — 진행 상황
│   ├── decisions/               결정 기록 — 개선 항목별 한계·트레이드오프
│   └── followups.md             미해결·확인 대기
├── tools/
│   ├── measure_queries.py       회귀 쿼리 실측·비교
│   └── queries.json             회귀 쿼리 10개 (11턴)
├── runs/                    실측 원자료 (커밋한다)
├── scripts/                 measure-at(커밋 단위 측정), setup-git-hooks, check-rule-docs
├── .github/workflows/ci.yml ruff + pytest(fake) + AGENTS≡CLAUDE
├── AGENTS.md / CLAUDE.md    작업 규칙 (같은 문서)
└── .gitmessage              커밋 템플릿
```

## 일정

| 언제 | 할 일 | 상태 |
| --- | --- | --- |
| Day1 ~17시 | 과제 선택, 진행 계획(초안) → Google Spread | 진행 중 |
| ~Day3 **13시** | 구현 마무리, 결과 보고서 작성 → Git 주소·보고서 주소를 Google Spread에 | — |
| ~Day3 17:30 | 개인별 결과 보고서 발표 (반별 자율 진행) | — |

## 결정 대기 중

| 항목 | 문서 | 기한 |
| --- | --- | --- |
| 진행 계획 Google Spread 등록 | [`docs/01-plan.md`](docs/01-plan.md#google-spread-등록용) | Day1 17시 |

## 확정된 결정

| 항목 | 결정 | 문서 |
| --- | --- | --- |
| 과제 | 1. Base AI Agent 개선 — 개선 항목 4개 + 선택 1개 | [`docs/01-plan.md`](docs/01-plan.md) |
| 저장소 구조와 도구 | 원본은 `project/`, 산출물은 밖. venv · ruff · pytest(fake) | [결정 0001](docs/decisions/0001-repository-layout-and-tooling.md) |
| 측정 백엔드 | ollama (qwen3:0.6b / qwen3:8b). fake 수치는 근거로 쓰지 않는다 | [`docs/02-measurement.md`](docs/02-measurement.md) |

미해결 항목 전체는 [`docs/followups.md`](docs/followups.md).
