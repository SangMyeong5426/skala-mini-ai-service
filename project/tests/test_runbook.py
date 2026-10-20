"""항목 5 — runbook 의미 검색. 가짜 embedder 로 선택 규칙과 노드 연결만 본다(ollama 없이)."""
import asyncio

from agent.deps import SupervisorDeps
from agent.graph import replan_check_node
from agent.runbook import RunbookSelector, load_runbooks, symptom_text

RUNBOOKS = {"cpu-spike": "CPU 급증", "db-down": "DB 장애", "network-timeout": "타임아웃"}
MONITORING = {"source": "monitoring", "data": {"system_name": "web-01", "status": "healthy",
                                               "alerts": ["upstream timeout (504)"]}}


class KeywordEmbedder:
    """문장에 들어 있는 단어로 3차원 벡터를 만든다 — 순서: CPU, DB, 타임아웃."""

    name = "keyword-embedder"

    async def embed(self, texts, instruction=None):
        def vec(t):
            return [float("CPU" in t), float("DB" in t), float("타임아웃" in t or "timeout" in t)]
        return [vec(t) for t in texts]


def _selector() -> RunbookSelector:
    return asyncio.run(RunbookSelector.create(KeywordEmbedder(), RUNBOOKS))


def test_symptom_text_combines_question_and_alerts():
    assert symptom_text("느려요", [MONITORING]) == "느려요\n알림: upstream timeout (504)"
    assert symptom_text("느려요", []) == "느려요"


def test_selects_runbook_closest_to_question_symptom():
    picked = asyncio.run(_selector().select("DB 연결이 안 돼요", []))

    assert picked["incident_type"] == "db-down"
    assert picked["method"] == "semantic"


def test_alert_text_is_part_of_the_search():
    picked = asyncio.run(_selector().select("응답이 이상해요", [MONITORING]))

    assert picked["incident_type"] == "network-timeout"


def _replan(selector) -> dict:
    """알림이 아직 없는 시스템에 사용자가 CPU 급증을 알린 상황 (평가 세트 r07)."""
    deps = SupervisorDeps(fast_llm=None, quality_llm=None, mcp=None, session_store=None,
                          version="v2", runbook_selector=selector)
    quiet = {"source": "monitoring", "data": {"system_name": "web-01", "status": "healthy",
                                              "alerts": []}}
    state = {"query": "web-01 CPU가 100%예요", "collected": [quiet], "events": [],
             "tasks": [], "replan_rounds": 0}
    return asyncio.run(replan_check_node(state, deps))


def test_replan_check_uses_selector_and_records_method():
    out = _replan(_selector())

    assert out["tasks"][-1]["target"] == "cpu-spike"
    assert out["events"][-1]["method"] == "semantic"


def test_replan_check_without_selector_keeps_base_behavior():
    out = _replan(None)

    assert out["tasks"][-1]["target"] == "db-down"   # base 는 질문을 안 보고, 맞는 알림이 없으면 db-down
    assert "method" not in out["events"][-1]


def test_runbook_files_load_with_type_names():
    assert set(load_runbooks()) == {"cpu-spike", "db-down", "disk-full", "high-latency",
                                    "memory-leak", "network-timeout"}
