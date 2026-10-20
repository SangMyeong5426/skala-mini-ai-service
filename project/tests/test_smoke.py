"""베이스 에이전트 스모크 테스트 — 개선 작업 전후로 깨지면 안 되는 동작.

fake 백엔드는 결정론이라 응답 문장 자체가 아니라 '어느 경로를 탔는가'를 본다.
"""
from agent.graph import _extract_system_name


def test_health_reports_singleton_and_fake_backend(client):
    body = client.get("/health").json()

    assert body["status"] == "ok"
    assert body["creation_count"] == 1
    assert body["llm_backend"] == "fake"
    assert body["supervisor_version"] == "v2"


def test_greeting_goes_straight_to_chat(client):
    body = client.post("/chat", json={"message": "안녕, 너는 누구야?",
                                      "thread_id": "t-chat"}).json()

    assert body["reply"]
    assert body["metadata"]["route"] == "chat"
    assert body["metadata"]["task_count"] == 0


def test_incident_runs_full_pipeline(client):
    body = client.post("/chat", json={"message": "web-01 CPU 급증 원인 진단해줘",
                                      "thread_id": "t-incident"}).json()
    types = [e["type"] for e in body["events"]]

    assert body["reply"]
    assert body["metadata"]["route"] == "incident"
    assert body["metadata"]["task_count"] > 0
    assert types[0] == "RouteDecided"
    assert {"PlanCreated", "GateApplied", "Validation"} <= set(types)
    assert body["events"][-1] == {"type": "Finalize", "pipeline": "incident-v2"}


def test_session_history_is_kept_per_thread(client):
    client.post("/chat", json={"message": "제 이름은 민수입니다", "thread_id": "t-mem"})
    client.post("/chat", json={"message": "제 이름이 뭐였죠?", "thread_id": "t-mem"})
    store = client.app.state.deps.session_store

    history = store.load("t-mem")

    assert [m["role"] for m in history] == ["user", "assistant", "user", "assistant"]
    assert history[0]["content"] == "제 이름은 민수입니다"
    assert store.load("t-other") == []


def test_stream_ends_with_final_answer_and_done(client):
    text = client.get("/chat/stream", params={"message": "안녕하세요",
                                              "thread_id": "t-sse"}).text
    chunks = [c for c in text.split("\n\n") if c]

    assert chunks[-1] == "data: [DONE]"
    assert '"type": "FinalAnswer"' in chunks[-2]


def test_extract_system_name_picks_first_known_system():
    assert _extract_system_name(
        "gateway-service에서 payments-service로 가는 요청이 타임아웃") == "gateway-service"
    assert _extract_system_name("로그인 응답이 느려요") == "auth-service"
