"""과제 2 등급 점검 그래프 스모크 테스트 — fake 백엔드로 경로를 본다(결정 0009).

fake 의 판정은 낱말 규칙이라(agent/rating/llm.py) 등급 자체가 아니라 '어느 경로를 탔는가'와
'부품을 끄면 LLM 단독이 되는가'를 확인한다.
"""
REVIEW = "칼로 적을 베고 피가 튀는 PC 액션 게임인데 몇 세 등급 받을까요?"


def _types(body: dict) -> list[str]:
    return [e["type"] for e in body["events"]]


def test_health_reports_rating_domain_with_all_parts_off(rating_client):
    body = rating_client.get("/health").json()

    assert body["domain"] == "rating"
    assert body["switches"]["ROUTER"] == "llm"
    assert body["switches"]["CASE_SEARCH"] == "off"
    assert body["switches"]["RATING_ASSESSOR"] == "direct"
    assert body["switches"]["VALIDATOR"] == "format"
    assert body["switches"]["RATING_CLARIFY"] == "off"


def test_policy_question_goes_to_chat(rating_client):
    body = rating_client.post("/chat", json={"message": "자체등급분류 사업자가 뭐예요?",
                                             "thread_id": "t-chat"}).json()

    assert body["metadata"]["route"] == "chat"
    assert body["events"][-1] == {"type": "Finalize", "pipeline": "chat-direct"}


def test_review_with_all_parts_off_is_llm_only(rating_client):
    """Before — 조사 task 가 없고, LLM 이 등급을 바로 답하고, 형식만 검수한다."""
    body = rating_client.post("/chat", json={"message": REVIEW, "thread_id": "t-before"}).json()
    analysis = next(e for e in body["events"] if e["type"] == "AnalysisCompleted")

    assert body["metadata"]["route"] == "review"
    assert body["metadata"]["task_count"] == 0
    assert "ResearchSkipped" in _types(body)
    assert analysis["method"] == "direct"
    assert body["reply"].startswith("예상 등급: 15세이용가")
    assert body["events"][-1] == {"type": "Finalize", "pipeline": "rating-v2"}


def test_stream_ends_with_final_answer_and_done(rating_client):
    text = rating_client.get("/chat/stream", params={"message": REVIEW, "thread_id": "t-sse"}).text
    chunks = [c for c in text.split("\n\n") if c]

    assert chunks[-1] == "data: [DONE]"
    assert '"type": "FinalAnswer"' in chunks[-2]


def test_rating_stats_tool_is_found_by_lookup(rating_client):
    """rating_stats 는 'ops' 가 아닌 rating 서버에 있다 — 서버를 미리 가정하지 않고 찾아서 부른다."""
    mcp = rating_client.app.state.deps.mcp
    server = rating_client.portal.call(mcp.find_tool, "rating_stats")
    stats = rating_client.portal.call(mcp.call_tool, "rating_stats",
                                      {"genre": "FPS/TPS", "platform": "PC/온라인 게임"}, server)

    assert server == "rating"
    assert stats["filter"] == {"genre": "FPS/TPS", "platform": "PC/온라인 게임"}
    assert stats["total"] == sum(stats["by_rating"].values())


def test_criteria_assessor_reads_criteria_through_mcp(rating_app):
    """RATING_ASSESSOR=criteria — 기준표를 MCP Resource 로 받아 항목별로 판정하고, 등급은 코드가 계산한다."""
    with rating_app(RATING_ASSESSOR="criteria") as client:
        body = client.post("/chat", json={"message": REVIEW, "thread_id": "t-criteria"}).json()
    tasks = [e for e in body["events"] if e["type"] == "TaskCompleted"]
    analysis = next(e for e in body["events"] if e["type"] == "AnalysisCompleted")

    assert [t["source"] for t in tasks] == ["criteria"]
    assert analysis["method"] == "criteria"
    assert analysis["rating"] == "15세이용가"   # fake 규칙: 피 → 폭력성 2단계
    assert body["reply"].startswith("예상 등급: 15세이용가")
