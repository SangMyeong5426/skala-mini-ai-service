"""기능 6 — 되묻기: 짧은 요청은 판정 전에, 내용 없는 요청은 판정 뒤에 되묻고, 다음 턴은 이어 붙여 판정한다."""
from agent.rating.clarify import ClarifyRule
from agent.rating.profile import (
    CLARIFY_MARK,
    description_with_history,
    extract_profile,
    follows_clarify,
)


def test_rule_catches_request_only_messages():
    rule = ClarifyRule()

    assert rule.check("등급 예상해 줘")
    assert rule.check("우리 게임 몇 세 등급 받을까요?")
    assert rule.check("고양이가 상자에 숨어 생선을 모으는 퍼즐") is None


def test_follow_up_is_joined_with_the_question_before_clarify():
    history = [{"role": "user", "content": "이번에 출시할 FPS 게임 등급 점검해 주세요"},
               {"role": "assistant", "content": f"{CLARIFY_MARK} — 판정할 게임 설명이 없습니다."}]

    assert follows_clarify(history)
    assert description_with_history("피가 사실적으로 튀어요", history) == \
        "이번에 출시할 FPS 게임 등급 점검해 주세요\n피가 사실적으로 튀어요"
    assert description_with_history("피가 튀어요", history[:1]) == "피가 튀어요"


def test_profile_prefers_explicit_api_names_then_keywords():
    assert extract_profile("장르: 롤플레잉, 플랫폼: 모바일 게임. 게임 내용: 검으로 싸우는 MMORPG") == \
        {"genre": "롤플레잉", "platform": "모바일 게임"}
    assert extract_profile("스팀에 낼 판타지 MMORPG") == {"genre": "MMORPG", "platform": "PC/온라인 게임"}
    assert extract_profile("고양이가 생선을 모아요") == {"genre": None, "platform": None}


def test_clarify_then_follow_up_reaches_assessment(rating_app):
    """첫 턴은 되묻고, 다음 턴은 라우터를 거치지 않고 점검으로 간다(직전 답이 되묻기)."""
    with rating_app(RATING_CLARIFY="rule", RATING_ASSESSOR="criteria") as client:
        first = client.post("/chat", json={"message": "등급 예상해 줘", "thread_id": "t-k"}).json()
        second = client.post("/chat", json={"message": "좀비를 총으로 쏘면 피가 튀는 게임이에요",
                                             "thread_id": "t-k"}).json()

    assert first["reply"].startswith(CLARIFY_MARK)
    assert first["events"][-1] == {"type": "Finalize", "pipeline": "clarify"}
    route = next(e for e in second["events"] if e["type"] == "RouteDecided")
    assert route == {"type": "RouteDecided", "route": "review", "method": "clarify-followup"}
    assert second["reply"].startswith("예상 등급: 15세이용가")


def test_assessor_says_not_described_then_clarify(rating_app):
    """규칙을 지나간 질문도 판정 LLM 이 described=false 면 되묻는다(fake 판정은 15자 미만이면 false — 규칙 ①을 낮춰 ②만 본다)."""
    with rating_app(RATING_CLARIFY="rule", RATING_ASSESSOR="criteria") as client:
        client.app.state.deps.clarifier.min_chars = 1   # 규칙 ①을 사실상 끄고 ②만 본다
        body = client.post("/chat", json={"message": "몇 세 나와요?", "thread_id": "t-k2"}).json()

    clarify = [e for e in body["events"] if e["type"] == "ClarifyRequested"]
    assert clarify and clarify[0]["method"] == "assess"
    assert body["events"][-1] == {"type": "Finalize", "pipeline": "clarify"}
