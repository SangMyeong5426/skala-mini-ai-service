"""테스트 공용 픽스처 — 항상 fake 백엔드로, LangSmith 전송 없이 돈다.

server.py 는 import 시점에 load_dotenv() 를 부르는데, load_dotenv 는 이미 있는
환경변수를 덮어쓰지 않는다. 그래서 import 전에 여기서 고정해 두면 .env 에 무엇이
있든(ollama·openai·tracing=true) 테스트는 결정론적이고 과금·외부 전송이 없다.
"""
import os
from contextlib import contextmanager

os.environ["LLM_BACKEND"] = "fake"
os.environ["AGENT_DOMAIN"] = "incident"   # 기존 테스트는 과제 1 도메인 기준. 등급 점검은 rating_client 로 띄운다
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
    # 한 프로세스에서 앱을 여러 번 띄우므로 생성 횟수(Wave 1)는 픽스처마다 0 에서 센다.
    monkeypatch.setattr(server, "CREATION_COUNT", 0)
    with TestClient(server.app) as c:
        yield c


@pytest.fixture
def rating_app(tmp_path, monkeypatch):
    """과제 2 — AGENT_DOMAIN=rating 앱을 스위치를 바꿔 띄운다: `with rating_app(RATING_ASSESSOR="criteria") as c:`.

    지정하지 않은 부품 스위치는 fake 기본(원본 쪽) — 모두 끄면 LLM 단독이다.
    """
    import server
    from agent.session_store import SqliteSessionStore

    @contextmanager
    def start(**switches):
        monkeypatch.setenv("AGENT_DOMAIN", "rating")
        for name, value in switches.items():
            monkeypatch.setenv(name, value)
        monkeypatch.setattr(server, "SqliteSessionStore",
                            lambda: SqliteSessionStore(tmp_path / "session.db"))
        monkeypatch.setattr(server, "CREATION_COUNT", 0)
        with TestClient(server.app) as c:
            yield c

    return start


@pytest.fixture
def rating_client(rating_app):
    """부품을 모두 끈(LLM 단독) 등급 점검 앱."""
    with rating_app() as c:
        yield c
