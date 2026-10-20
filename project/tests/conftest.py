"""테스트 공용 픽스처 — 항상 fake 백엔드로, LangSmith 전송 없이 돈다.

server.py 는 import 시점에 load_dotenv() 를 부르는데, load_dotenv 는 이미 있는
환경변수를 덮어쓰지 않는다. 그래서 import 전에 여기서 고정해 두면 .env 에 무엇이
있든(ollama·openai·tracing=true) 테스트는 결정론적이고 과금·외부 전송이 없다.
"""
import os

os.environ["LLM_BACKEND"] = "fake"
os.environ["SUPERVISOR_VERSION"] = "v2"
os.environ["LANGCHAIN_TRACING_V2"] = "false"
os.environ["LANGSMITH_TRACING"] = "false"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture
def client(tmp_path, monkeypatch):
    """lifespan 까지 실제로 돌린 앱 — MCP 서버 2개가 subprocess 로 뜬다.

    세션 저장소만 tmp_path 로 돌려 project/session.db 를 건드리지 않는다.
    """
    import server
    from agent.session_store import SqliteSessionStore

    monkeypatch.setattr(server, "SqliteSessionStore",
                        lambda: SqliteSessionStore(tmp_path / "session.db"))
    with TestClient(server.app) as c:
        yield c
