# skala-mini-ai-service

> SKALA — **AI 서비스 개발 Mini-project** (3일, 개인 과제)

운영 인시던트 대응 에이전트(Base AI Agent)를 개선하거나, 주제를 바꿔 새 AI Agent를 만든다.
LangGraph StateGraph · MCP(Tool/Resource/Prompt) · SSE 스트리밍 · SQLite 세션 · LangSmith
추적이 이미 조립된 상태에서 출발한다. 원본 설명은 [`project/doc/README.md`](project/doc/README.md).

| 항목 | 값 |
| --- | --- |
| 저장소 | <https://github.com/SangMyeong5426/skala-mini-ai-service> |
| 과제 | **2. 신규 프로젝트** — 게임 등급분류 사전 점검 에이전트 ([`docs/01-plan.md`](docs/01-plan.md)) |
| 핵심 결과 (LLM 단독 → 에이전트) | 등급 정확도 한 문장 14 → 19/40 · 상세 설명 24 → 27/39 · 분류 15 → 29/30 · 되묻기 6 → 10/12 · 오염 초안 탐지 0 → 7/7 · 제도 문의 2 → 15/17. 한 문장 설명에서는 사례 5건 다수결(22/40)보다 낮다 ([`02-measurement.md`](docs/02-measurement.md)) |
| 요건·평가 기준 | [`docs/00-assignment.md`](docs/00-assignment.md) |
| 상세 설계 | [`docs/03-design.md`](docs/03-design.md) |
| 진행 체크리스트 | [`docs/checklist.md`](docs/checklist.md) |
| 결과 보고서 | TBD (Day2) |
| Before/After 실측 | [`docs/02-measurement.md`](docs/02-measurement.md) |
| 과제 1 (보존) | Base 개선 항목 1~5와 결과 — [`docs/task1/`](docs/task1/), 태그 `task1` |
| 결정 기록 | [`docs/decisions/`](docs/decisions/) |

## 빠른 시작 (macOS)

필요한 것: Python 3.11, [Ollama](https://ollama.com). 모든 명령은 `project/`에서 실행한다.

```bash
git clone https://github.com/SangMyeong5426/skala-mini-ai-service.git
cd skala-mini-ai-service/project
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
측정에서 원본 동작을 재현하거나, 문제가 생겼을 때 재배포 없이 끄는 데 쓴다. 지정하지 않으면
**ollama 백엔드는 개선 쪽, fake·openai 백엔드는 원본 쪽**이 기본이다. 실제 값은 `/health`의 `switches`에 나온다.

| 환경변수 | 개선 (ollama 기본) | 원본 | 항목 |
| --- | --- | --- | --- |
| `OLLAMA_THINK` | `false` | `default`(옵션을 보내지 않음) · `true` | 1 — [0002](docs/decisions/0002-ollama-think-control.md) |
| `OLLAMA_THINK_CHAT` | `true` (대화 경로만 생각) | `default` — `OLLAMA_THINK=default`면 따라간다 | 1 보완 — [0007](docs/decisions/0007-chat-keeps-thinking.md) |
| `ROUTER` | `semantic` | `llm` | 2 — [0003](docs/decisions/0003-semantic-router.md) |
| `TARGET_RESOLVER` | `semantic` | `legacy` | 3 — [0004](docs/decisions/0004-target-resolver.md) |
| `VALIDATOR` | `grounded` | `format` | 4 — [0005](docs/decisions/0005-grounded-validator.md) |
| `RUNBOOK_SELECTOR` | `semantic` | `keyword` | 5 — [0006](docs/decisions/0006-runbook-selector.md) |

과제 2(`AGENT_DOMAIN=rating`, 기본값)는 아래 부품을 더 쓴다. `ROUTER`·`VALIDATOR`는 같은 이름으로 도메인에 맞는
부품이 켜진다. **모두 끄면 LLM 단독이고, 그것이 과제 2의 Before다**([결정 0009](docs/decisions/0009-rating-domain.md)).
`AGENT_DOMAIN=incident`면 과제 1 그대로 돈다.

| 환경변수 | 개선 (ollama 기본) | 원본 (LLM 단독) | 기능 |
| --- | --- | --- | --- |
| `ROUTER` | `semantic` — 등급 점검 예시 문장 | `llm` | 5 의미 라우터 |
| `CASE_SEARCH` | `semantic` — 유사 사례 검색 + 통계 Tool | `off` | 3 |
| `RATING_ASSESSOR` | `criteria` — 기준표로 항목별 단계 판정, 등급은 코드가 계산 | `direct` — LLM 이 등급을 바로 답함 | 3 |
| `VALIDATOR` | `grounded` — 등급·사례·수치 대조 + LLM 판정 | `format` | 4 |
| `RATING_CLARIFY` | `rule` — 정보가 모자라면 되묻기 | `off` | 6 |
| `CHAT_GROUNDING` | `law` — 제도 문의는 법령 조문에 근거해 답하고, 근거가 없으면 답할 수 없다고 한다 | `off` — 0.6b 가 근거 없이 대화로 답함 | 8 |

판정 기준은 `ROUTER_MARGIN`(0.029)·`TARGET_MIN_SCORE`(0.40)·`TARGET_MARGIN`(0.04)으로 덮어쓸 수 있다.
임베딩 모델은 `OLLAMA_EMBED_MODEL`(기본 `qwen3-embedding:0.6b`).

## 개발

```bash
cd project
.venv/bin/python -m pytest      # 스모크 테스트 — fake 백엔드, MCP subprocess까지 실제로 띄운다
.venv/bin/ruff check .          # 린트
```

Before/After 측정 — 잴 커밋을 worktree로 꺼내 그 코드로 잰다. ollama가 떠 있어야 한다
(자세한 방법은 [`docs/task1/02-measurement.md`](docs/task1/02-measurement.md#측정-방법)).

```bash
# 과제 2 — 같은 커밋에서 스위치만 바꾼다 (docs/02-measurement.md)
scripts/measure-at <커밋> after rating
ROUTER=llm RATING_CLARIFY=off CASE_SEARCH=off RATING_ASSESSOR=direct VALIDATOR=format \
  scripts/measure-at <커밋> before rating
# 과제 1
scripts/measure-at base before write,e2e
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
│   ├── mcp_server_rating.py     MCP "rating" — 등급 통계 Tool, 기준표·시행규칙·사례 Resource (과제 2)
│   ├── agent/                   그래프·LLM 백엔드 3종·MCP 클라이언트·세션·재시도
│   │                            + embedding·router·target·validator·runbook (과제 1 개선 항목 2~5)
│   │                            + rating/ — 등급 점검 그래프·판정·사례 검색·검수·되묻기 (과제 2)
│   ├── data/                    monitoring.json, runbooks/ 6종
│   │                            + router_examples.json(분류 예시), systems.json(시스템 카탈로그)
│   │                            + ratings/ — 등급분류 원자료·사례 DB·기준표·시행규칙 (과제 2)
│   ├── doc/                     원본 매뉴얼
│   ├── sh/                      setup·run 스크립트 (+ run_agent_fake.sh)
│   ├── tests/                   스모크 테스트 (추가)
│   ├── pyproject.toml           ruff·pytest 설정 (추가)
│   ├── requirements.txt         원본 의존성
│   └── requirements-dev.txt     pytest·ruff (추가)
├── docs/
│   ├── 00-assignment.md         과제 요건·일정·평가 기준
│   ├── 01-plan.md               진행 계획 (Google Spread 등록 원본) — 과제 2
│   ├── 02-measurement.md        Before/After 실측 — 과제 2
│   ├── 03-design.md             상세 설계 — 과제 2
│   ├── checklist.md             체크리스트 — 진행 상황
│   ├── task1/                   과제 1(Base 개선) 계획·측정·설계·보고서 — 보존
│   ├── decisions/               결정 기록 — 항목별 한계·트레이드오프
│   └── followups.md             미해결·확인 대기
├── tools/
│   ├── measure_queries.py       회귀 쿼리 실측·비교 (--spawn: 질문마다 서버 새로)
│   ├── eval_nodes.py            노드 단위 평가 — route·target·judge·write·runbook
│   ├── tune_embedding.py        의미 판정 기준 조정 (평가 세트 미사용, --domain rating)
│   ├── eval_rating.py           과제 2 노드 평가 — rate·rroute·rclarify·rjudge
│   ├── fetch_ratings.py         게임물관리위원회 API 수집·사례 DB 생성 (과제 2)
│   ├── make_rating_evalset.py   평가셋 A 표본 추출 (시드 고정)
│   ├── queries_rating.json      과제 2 회귀 쿼리 10개 (11턴)
│   ├── try_models.py            작성·판정 모델 교체 시험 (기각, 결정 0008)
│   ├── queries.json             회귀 쿼리 10개 (11턴)
│   ├── evalsets/                라벨 평가 세트 — 과제 1 4종 + 과제 2 4종(rating*)
│   └── tuning/                  조정용 문장 (평가 세트 아님)
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
| 진행 계획 Google Spread 등록 (과제 2) | [`docs/01-plan.md`](docs/01-plan.md#google-spread-등록용) | Day1 17시 |

## 확정된 결정

| 항목 | 결정 | 문서 |
| --- | --- | --- |
| 과제 | 2. 신규 프로젝트 — 게임 등급분류 사전 점검 (과제 1 개선 항목 1~5를 끝낸 뒤 전환) | [`docs/01-plan.md`](docs/01-plan.md) |
| 저장소 구조와 도구 | 원본은 `project/`, 산출물은 밖. venv · ruff · pytest(fake) | [결정 0001](docs/decisions/0001-repository-layout-and-tooling.md) |
| 측정 백엔드 | ollama (qwen3:0.6b / qwen3:8b). fake 수치는 근거로 쓰지 않는다 | [`docs/02-measurement.md`](docs/02-measurement.md) |

미해결 항목 전체는 [`docs/followups.md`](docs/followups.md).
