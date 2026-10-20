#!/usr/bin/env bash
#
# all_total — fake(결정론) LLM으로 에이전트를 "기동만" 해두는 스크립트.
#
# run_agent_ollma.sh와 같은 서버를 띄우되 LLM 자리에 agent/fake_llm.py를 꽂는다.
# 모델·API 키·Ollama 없이 그래프·MCP·세션·SSE 배관이 도는지 바로 확인할 때 쓴다.
# 응답 문장과 비용은 고정 규칙으로 만든 값이라 품질·지연시간 비교에는 쓰지 않는다.
#
# .env는 있으면 읽고(LangSmith 기록), 없어도 기동한다 — 이 모드는 키가 필요 없다.
#
# 종료하려면 이 터미널에서 Ctrl+C.
#
set -euo pipefail
cd "$(dirname "$0")/.."

[ -x ".venv/bin/python3" ] && export PATH="$PWD/.venv/bin:$PATH"

# ── 0) LangSmith 환경 (선택) ───────────────────────────────────────────
if [ -f .env ]; then
    set -a; source .env; set +a
    export LANGCHAIN_PROJECT="capstone-all-total"   # ollama/openai 모드와 프로젝트 분리
    echo "LangSmith: project=$LANGCHAIN_PROJECT tracing=${LANGCHAIN_TRACING_V2:-}"
else
    export LANGCHAIN_TRACING_V2=false
    echo ".env가 없어 LangSmith 기록 없이 기동합니다."
fi

# ── 1) 이전 실행 정리 ──────────────────────────────────────────────────
lsof -ti:8100 | xargs kill -9 2>/dev/null || true
rm -f session.db

cleanup() {
    echo
    echo "에이전트를 종료합니다..."
    lsof -ti:8100 | xargs kill -9 2>/dev/null || true
}
trap cleanup EXIT

# ── 2) 서버 기동 (백그라운드로 띄운 뒤 준비될 때까지 대기) ─────────────
LLM_BACKEND=fake SUPERVISOR_VERSION=v2 python3 server.py &
SERVER_PID=$!
for _ in $(seq 1 40); do
    curl -s http://127.0.0.1:8100/health >/dev/null 2>&1 && break
    sleep 0.5
done

echo
curl -s http://127.0.0.1:8100/health | python3 -m json.tool --no-ensure-ascii

cat <<EOF

################################################################
 에이전트가 떠 있습니다 (http://127.0.0.1:8100, LLM_BACKEND=fake)
################################################################

브라우저 채팅 화면은 새 터미널에서:  bash sh/run_frontend.sh
종료하려면 이 터미널에서 Ctrl+C.
EOF

wait "$SERVER_PID"
