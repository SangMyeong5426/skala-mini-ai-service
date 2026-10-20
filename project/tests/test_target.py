"""항목 3 — 대상 시스템 추정과 되묻기. 가짜 embedder 로 규칙을 보고, 그래프는 fake 백엔드로 돌린다."""
import asyncio
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from agent.target import SERVICE_LIKE, TargetResolver

DATA = Path(__file__).resolve().parents[1] / "data"
CATALOG = [{"name": "auth-service", "description": "로그인 인증"},
           {"name": "cache-service", "description": "캐시"},
           {"name": "web-01", "description": "웹 서버"}]


class TableEmbedder:
    """정해 둔 문장은 정해 둔 벡터로, 나머지는 기본 벡터로 돌려준다."""

    name = "table-embedder"

    def __init__(self, table: dict[str, list[float]], default: list[float]):
        self.table, self.default = table, default

    async def embed(self, texts, instruction=None):
        return [self.table.get(t, self.default) for t in texts]


def _resolver(query_vec: list[float], min_score=0.5, margin=0.1) -> TargetResolver:
    docs = {"auth-service: 로그인 인증": [1.0, 0.0, 0.0],
            "cache-service: 캐시": [0.0, 1.0, 0.0],
            "web-01: 웹 서버": [0.0, 0.0, 1.0]}
    embedder = TableEmbedder(docs, default=query_vec)
    return asyncio.run(TargetResolver.create(embedder, CATALOG, min_score=min_score,
                                             margin=margin))


def test_all_named_systems_in_order():
    resolver = _resolver([0.0, 0.0, 0.0])

    out = asyncio.run(resolver.resolve("web-01 이 느리고 auth-service 도 이상해요"))

    assert out["targets"] == ["web-01", "auth-service"]
    assert out["method"] == "name-match"


def test_unknown_service_is_clarified():
    resolver = _resolver([1.0, 0.0, 0.0])   # 의미상 auth 와 가까워도 이름이 대상 밖이면 되묻는다

    out = asyncio.run(resolver.resolve("billing-service가 느려요"))

    assert out["targets"] == []
    assert out["method"] == "unknown-system"
    assert "billing-service" in out["reason"]


def test_semantic_match_above_threshold():
    resolver = _resolver([0.1, 0.9, 0.0])

    out = asyncio.run(resolver.resolve("캐시 적중률 이상"))

    assert out["targets"] == ["cache-service"]
    assert out["method"] == "semantic"


@pytest.mark.parametrize("query_vec", [
    [0.6, 0.55, 0.0],    # 1·2위 코사인 차이(약 0.06)가 margin(0.1) 미만
    [0.2, 0.0, 0.1],     # 1위 코사인(약 0.89)이 min_score(0.95) 미만
])
def test_ambiguous_question_is_clarified(query_vec):
    resolver = _resolver(query_vec, min_score=0.95, margin=0.1)

    out = asyncio.run(resolver.resolve("서버가 이상해요"))

    assert out["targets"] == []
    assert out["reason"]


def test_service_like_pattern_with_korean_particle():
    assert SERVICE_LIKE.findall("billing-service가 느리고 web-02도요") == ["billing-service", "web-02"]


def test_catalog_matches_monitoring_data():
    """카탈로그와 모니터링 데이터의 시스템이 어긋나면 진단할 수 없는 대상을 고르게 된다."""
    catalog = json.loads((DATA / "systems.json").read_text())
    monitoring = json.loads((DATA / "monitoring.json").read_text())

    assert [s["name"] for s in catalog] == list(monitoring)
    assert all(s["description"] for s in catalog)


class FlatEmbedder:
    """모든 문장을 같은 벡터로 — 의미로는 어느 시스템도 고를 수 없게 한다."""

    name = "flat-embedder"

    async def embed(self, texts, instruction=None):
        return [[1.0, 1.0] for _ in texts]


@pytest.fixture
def resolver_client(tmp_path, monkeypatch):
    """fake 백엔드 + TARGET_RESOLVER=semantic. 카탈로그는 실제 MCP 서버의 catalog://systems 로 읽는다."""
    import server
    from agent.session_store import SqliteSessionStore

    monkeypatch.setenv("TARGET_RESOLVER", "semantic")
    monkeypatch.setattr(server, "_make_embedder", FlatEmbedder)
    monkeypatch.setattr(server, "SqliteSessionStore",
                        lambda: SqliteSessionStore(tmp_path / "session.db"))
    with TestClient(server.app) as c:
        yield c


def test_graph_clarifies_instead_of_guessing(resolver_client):
    body = resolver_client.post("/chat", json={"message": "서버 장애가 난 것 같아요",
                                               "thread_id": "t-clarify"}).json()
    types = [e["type"] for e in body["events"]]

    assert "ClarifyRequested" in types
    assert "TaskCompleted" not in types            # 아무 시스템도 조사하지 않았다
    assert body["events"][-1] == {"type": "Finalize", "pipeline": "clarify"}
    assert body["metadata"]["task_count"] == 0
    assert "cache-service" in body["reply"]         # 카탈로그(MCP Resource)를 읽어 안내한다
    assert resolver_client.get("/health").json()["switches"]["TARGET_RESOLVER"] == "semantic"


def test_graph_diagnoses_named_system(resolver_client):
    body = resolver_client.post("/chat", json={"message": "web-01 CPU 급증 원인 진단해줘",
                                               "thread_id": "t-named"}).json()
    plan = next(e for e in body["events"] if e["type"] == "PlanCreated")

    assert plan["targets"] == ["web-01"]
    assert plan["method"] == "name-match"
    assert body["events"][-1] == {"type": "Finalize", "pipeline": "incident-v2"}
