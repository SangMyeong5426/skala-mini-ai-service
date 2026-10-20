"""항목 4 — 검수 근거 검증. 수치 대조는 평가 세트(judge.json)로, 판정 순서는 가짜 판정기로 본다(ollama 없이)."""
import asyncio
import json
from pathlib import Path

import pytest

from agent.deps import SupervisorDeps
from agent.graph import validate_node
from agent.validator import GroundedValidator, parse_verdict, ungrounded_numbers

PROJECT = Path(__file__).resolve().parents[1]
JUDGE_SET = PROJECT.parent / "tools" / "evalsets" / "judge.json"


def _cases() -> dict[str, dict]:
    cases = {}
    for item in json.loads(JUDGE_SET.read_text()):
        collected = []
        for e in item["collected"]:
            if e["source"] == "runbook":
                text = (PROJECT / "data" / "runbooks" / f"{e['ref']}.md").read_text()
                collected.append({"source": "runbook", "data": text})
            else:
                collected.append(e)
        cases[item["id"]] = {**item, "collected": collected}
    return cases


CASES = _cases()


@pytest.mark.parametrize("case_id", ["g1", "g2", "g3", "g4", "g5"])
def test_number_check_accepts_every_good_draft(case_id):
    """정상 초안을 떨어뜨리면 재작성이 늘어 느려진다 — 오탐 0 이 먼저다."""
    c = CASES[case_id]

    assert ungrounded_numbers(c["draft"], c["collected"], c["query"]) == []


@pytest.mark.parametrize(("case_id", "expected"), [
    ("b2", ["99.8", "71.4"]),            # 수치 조작
    ("b3", ["1.8", "3.2", "12"]),        # 수집하지 않은 지표
    ("b4", ["34.0", "48.0"]),            # 다른 시스템 진단
])
def test_number_check_catches_invented_numbers(case_id, expected):
    c = CASES[case_id]

    assert ungrounded_numbers(c["draft"], c["collected"], c["query"]) == expected


@pytest.mark.parametrize("case_id", ["b1", "b5", "b6", "b7"])
def test_number_check_cannot_catch_judgement_errors(case_id):
    """수치는 맞고 판단이 틀린 경우 — LLM 판정의 몫이라는 경계를 테스트로 남긴다."""
    c = CASES[case_id]

    assert ungrounded_numbers(c["draft"], c["collected"], c["query"]) == []


class StubJudge:
    def __init__(self, relevant=True, faithful=True):
        self.verdict = {"relevant": relevant, "faithful": faithful, "reason": "근거"}
        self.calls = 0

    def judge(self, query, facts, draft):
        self.calls += 1
        return self.verdict, {"usd": 0.001}


def test_stages_run_cheapest_first():
    c = CASES["b2"]
    judge = StubJudge()

    short = GroundedValidator(judge).check(c["query"], c["collected"], "짧다")
    invented = GroundedValidator(judge).check(c["query"], c["collected"], c["draft"])

    assert short["stage"] == "format"
    assert invented["stage"] == "numbers"
    assert "99.8" in invented["feedback"]
    assert judge.calls == 0                      # 싼 검사에서 떨어지면 LLM 을 부르지 않는다


def test_judge_rejects_irrelevant_answer():
    c = CASES["b1"]

    out = GroundedValidator(StubJudge(relevant=False)).check(c["query"], c["collected"], c["draft"])

    assert (out["ok"], out["stage"]) == (False, "judge")
    assert out["reason"].startswith("질문과 관련 없는 답변")


def test_good_draft_passes_all_stages():
    c = CASES["g1"]
    judge = StubJudge()

    out = GroundedValidator(judge).check(c["query"], c["collected"], c["draft"])

    assert out["ok"] and out["stage"] is None
    assert judge.calls == 1


def test_broken_verdict_json_passes_open():
    assert parse_verdict("not json")["relevant"] is True
    assert parse_verdict('{"relevant": false, "faithful": true, "reason": "무관"}') == {
        "relevant": False, "faithful": True, "reason": "무관"}


def _validate(draft: str, attempts: int, validator) -> dict:
    deps = SupervisorDeps(fast_llm=None, quality_llm=None, mcp=None, session_store=None,
                          version="v2", validator=validator)
    state = {"query": "q", "collected": [], "draft": draft, "validation_attempts": attempts,
             "events": [], "cost_usd": 0.0}
    return asyncio.run(validate_node(state, deps))


def test_rejection_sends_feedback_for_rewrite():
    out = _validate("1) 자세한 내용은 담당자에게 문의하세요. 추가 조치는 없습니다.", 0,
                    GroundedValidator(StubJudge(faithful=False)))

    assert out["validation_feedback"]
    assert out["events"][-1]["stage"] == "judge"
    assert out["cost_usd"] == pytest.approx(0.001)


def test_third_failure_is_delivered_with_warning():
    draft = "1) 자세한 내용은 담당자에게 문의하세요. 추가 조치는 없습니다."

    out = _validate(draft, 2, GroundedValidator(StubJudge(relevant=False)))

    assert out["validation_feedback"] is None    # 무한 재작성 방지 — base 와 같이 3회째에 끝낸다
    assert out["draft"].startswith("⚠️ 검수를 통과하지 못한 답변입니다")
    assert out["draft"].endswith(draft)


@pytest.fixture
def grounded_client(tmp_path, monkeypatch):
    """fake 백엔드 + VALIDATOR=grounded — 실제 그래프가 쓴 초안을 수치 대조가 잘못 떨어뜨리지 않는지."""
    from fastapi.testclient import TestClient

    import server
    from agent.session_store import SqliteSessionStore

    monkeypatch.setenv("VALIDATOR", "grounded")
    monkeypatch.setattr(server, "SqliteSessionStore",
                        lambda: SqliteSessionStore(tmp_path / "session.db"))
    with TestClient(server.app) as c:
        yield c


def test_graph_rewrites_short_draft_then_passes(grounded_client):
    body = grounded_client.post("/chat", json={"message": "web-01 CPU 급증 원인 진단해줘",
                                               "thread_id": "t-grounded"}).json()
    checks = [e for e in body["events"] if e["type"] == "Validation"]

    assert [c["verdict"] for c in checks] == ["불합격", "합격"]
    assert checks[0]["stage"] == "format"        # fake 1차 초안은 일부러 짧다 (Wave 8)
    assert not body["reply"].startswith("⚠️")
