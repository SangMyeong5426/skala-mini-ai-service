"""항목 2 — 의미 라우터. 가짜 embedder 로 판정 규칙만 본다(ollama 없이)."""
import asyncio
import json
import re
from pathlib import Path

import pytest

from agent.deps import SupervisorDeps
from agent.graph import route_node
from agent.router import LLMRouter, SemanticRouter, class_scores, load_examples

ROUTE_EVALSET = Path(__file__).resolve().parents[2] / "tools" / "evalsets" / "route.json"
EXAMPLE_VECS = {"c1": [1.0, 0.0], "c2": [0.9, 0.1], "i1": [0.0, 1.0], "i2": [0.1, 0.9]}


class StubEmbedder:
    """문장마다 정해 둔 벡터를 돌려준다."""

    name = "stub-embedder"

    def __init__(self, table: dict[str, list[float]]):
        self.table = table

    async def embed(self, texts, instruction=None):
        return [self.table[t] for t in texts]


class StubFastLLM:
    def __init__(self):
        self.calls = []

    def route(self, query):
        self.calls.append(query)
        return ({"route": "incident", "needs_analysis": False},
                {"model": "stub", "tokens": 1, "usd": 0.001})


def _router(query_vec: list[float], margin: float):
    fast = StubFastLLM()
    examples = {"chat": ["c1", "c2"], "incident": ["i1", "i2"]}
    embedder = StubEmbedder({**EXAMPLE_VECS, "q": query_vec})
    router = asyncio.run(SemanticRouter.create(embedder, LLMRouter(fast), examples,
                                               margin=margin, k=1))
    return router, fast


def test_clear_question_is_decided_by_embedding():
    router, fast = _router([1.0, 0.05], margin=0.1)

    result, usage = asyncio.run(router.route("q"))

    assert (result["route"], result["method"]) == ("chat", "semantic")
    assert result["gap"] < -0.1
    assert fast.calls == []           # LLM 을 부르지 않았다
    assert usage["usd"] == 0.0


def test_ambiguous_question_falls_back_to_llm():
    router, fast = _router([1.0, 1.0], margin=0.1)

    result, _ = asyncio.run(router.route("q"))

    assert (result["route"], result["method"]) == ("incident", "llm-fallback")
    assert abs(result["gap"]) < 0.1
    assert fast.calls == ["q"]


def test_class_scores_average_top_k():
    vecs = {"chat": [[1.0, 0.0], [0.0, 1.0]], "incident": [[0.0, 1.0]]}

    scores = class_scores([1.0, 0.0], vecs, k=2)

    assert scores == {"chat": pytest.approx(0.5), "incident": pytest.approx(0.0)}


def test_route_node_uses_router_and_records_method():
    class FixedRouter:
        async def route(self, query):
            return ({"route": "chat", "needs_analysis": False, "method": "semantic",
                     "gap": -0.2, "scores": {}}, {"usd": 0.0})

    deps = SupervisorDeps(fast_llm=None, quality_llm=None, mcp=None, session_store=None,
                          version="v2", router=FixedRouter())

    out = asyncio.run(route_node({"query": "q", "events": [], "cost_usd": 0.0}, deps))

    assert out["route"] == "chat"
    assert out["events"][-1] == {"type": "RouteDecided", "route": "chat",
                                 "method": "semantic", "gap": -0.2}


def _normalize(text: str) -> str:
    return re.sub(r"[\s,.?!~]", "", text).lower()


def test_examples_do_not_overlap_evalset():
    """예시가 평가 질문과 같으면 정답을 외운 것이 된다 (tools/evalsets/README.md)."""
    examples = load_examples()
    texts = examples["chat"] + examples["incident"]
    evalset = {_normalize(item["query"]) for item in json.loads(ROUTE_EVALSET.read_text())}

    assert not evalset & {_normalize(t) for t in texts}
    assert len(texts) == len({_normalize(t) for t in texts})
    assert min(len(examples["chat"]), len(examples["incident"])) >= 15


@pytest.mark.parametrize(("backend", "env", "expected"), [
    ("ollama", None, "semantic"), ("fake", None, "llm"), ("openai", None, "llm"),
    ("ollama", "llm", "llm"), ("fake", "SEMANTIC", "semantic"),
])
def test_router_switch_defaults(monkeypatch, backend, env, expected):
    import server

    if env is None:
        monkeypatch.delenv("ROUTER", raising=False)
    else:
        monkeypatch.setenv("ROUTER", env)

    assert server._switch("ROUTER", "semantic", "llm", backend, ("semantic", "llm")) == expected


def test_router_switch_rejects_unknown(monkeypatch):
    import server

    monkeypatch.setenv("ROUTER", "keyword")

    with pytest.raises(ValueError):
        server._switch("ROUTER", "semantic", "llm", "ollama", ("semantic", "llm"))
