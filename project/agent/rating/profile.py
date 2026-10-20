"""질문에서 장르·플랫폼을 코드로 뽑고, 되묻기 다음 턴을 이어 붙인다 — 기능 3·6.

장르·플랫폼은 통계 Tool(rating_stats)과 유사 사례 검색의 필터로만 쓴다. 이름은 게임물관리위원회 API 의
값(예: "PC/온라인 게임", "롤플레잉")으로 맞춘다. 못 찾으면 None — 필터 없이 넓게 찾을 뿐 틀리지는 않는다.
"""
import re

# 앞에 있는 것부터 본다 — "MMORPG" 를 "RPG"(롤플레잉)보다, "전략 시뮬레이션"을 "시뮬레이션"보다 먼저.
GENRE_KEYWORDS = [
    ("MMORPG", ["MMORPG", "MMO"]),
    ("전략시뮬레이션", ["전략시뮬레이션", "전략 시뮬레이션", "실시간 전략", "RTS", "전략 게임"]),
    ("FPS/TPS", ["FPS/TPS", "FPS", "TPS", "1인칭 슈팅", "3인칭 슈팅"]),
    ("비행슈팅", ["비행슈팅", "비행 슈팅", "슈팅 게임"]),
    ("롤플레잉", ["롤플레잉", "RPG", "알피지"]),
    ("격투게임", ["격투게임", "격투"]),
    ("레이싱", ["레이싱", "레이스", "자동차 경주"]),
    ("스포츠", ["스포츠", "축구", "야구", "농구", "골프"]),
    ("퍼즐", ["퍼즐"]),
    ("캐주얼", ["캐주얼"]),
    ("교육용", ["교육용"]),
    ("보드게임", ["보드게임", "보드 게임", "카드 게임"]),
    ("어드벤처", ["어드벤처"]),
    ("시뮬레이션", ["시뮬레이션", "경영", "육성"]),
    ("액션", ["액션"]),
    ("기타", ["기타"]),
]
PLATFORM_KEYWORDS = [
    ("PC/온라인 게임", ["PC/온라인", "PC", "온라인 게임", "스팀", "Steam"]),
    ("모바일 게임", ["모바일", "스마트폰", "안드로이드", "iOS", "아이폰", "구글 플레이", "앱스토어", "원스토어"]),
    ("비디오 게임", ["비디오 게임", "콘솔", "닌텐도", "스위치", "Switch", "플레이스테이션", "PS5", "PS4", "엑스박스", "Xbox"]),
    ("아케이드 게임", ["아케이드"]),
]
# 평가셋·사용자가 API 이름을 그대로 쓰면 그것을 먼저 믿는다("장르: 액션, 플랫폼: PC/온라인 게임").
EXPLICIT = re.compile(r"(장르|플랫폼)\s*[:：]\s*([^,.\n]+)")

# clarify 노드가 내는 답의 첫머리. 다음 턴에 이 답이 직전에 있으면 되묻기에 대한 보충으로 본다.
CLARIFY_MARK = "등급을 판단하려면 게임 내용을 조금 더 알려 주세요"


def _match(text: str, table: list[tuple[str, list[str]]]) -> str | None:
    lowered = text.lower()
    for name, words in table:
        if any(w.lower() in lowered for w in words):
            return name
    return None


def extract_profile(text: str) -> dict:
    explicit = {k: v.strip() for k, v in EXPLICIT.findall(text)}
    names = {n for n, _ in GENRE_KEYWORDS}
    genre = explicit.get("장르") if explicit.get("장르") in names else _match(text, GENRE_KEYWORDS)
    platforms = {n for n, _ in PLATFORM_KEYWORDS}
    platform = (explicit.get("플랫폼") if explicit.get("플랫폼") in platforms
                else _match(text, PLATFORM_KEYWORDS))
    return {"genre": genre, "platform": platform}


def follows_clarify(history: list[dict]) -> bool:
    """직전 답이 되묻기였는가."""
    return bool(history) and history[-1]["role"] == "assistant" and history[-1]["content"].startswith(CLARIFY_MARK)


def description_with_history(query: str, history: list[dict]) -> str:
    """되묻기 다음 턴이면 되묻기 직전의 사용자 질문과 이어 붙인다 — 보충 설명만으로 판정하지 않게."""
    if follows_clarify(history) and len(history) >= 2 and history[-2]["role"] == "user":
        return f"{history[-2]['content']}\n{query}"
    return query
