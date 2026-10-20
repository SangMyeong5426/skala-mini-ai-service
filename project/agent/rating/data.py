"""등급분류 데이터의 약속 — 등급·내용정보 이름, 사례 DB 기간, 걸러 내는 규칙.

수집 도구(tools/fetch_ratings.py), MCP 서버(mcp_server_rating.py), 에이전트, 테스트가 같은 정의를 쓴다.
원자료는 게임물관리위원회 Open API(GameSearchSvc.asmx/game)다 — 결정 0010.
"""
import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "ratings"
RAW_DIR = DATA_DIR / "raw"
CASES_PATH = DATA_DIR / "cases.json"
CRITERIA_PATH = DATA_DIR / "criteria.json"
RULE8_PATH = DATA_DIR / "rule-8.md"

# 단계 0~3. 사례집 요약표의 열 순서와 같다(전체 · 12 · 15 · 청소년이용불가).
RATINGS = ["전체이용가", "12세이용가", "15세이용가", "청소년이용불가"]
# 내용정보 항목 — API descriptors 에 실제로 나오는 이름 그대로(가이드의 "선전성"·"언어의부적절성"이 아니다).
ITEMS = ["폭력성", "선정성", "공포", "언어", "약물", "범죄", "사행성"]
# 사행성 게임물은 범위 밖이다 — 별도 규제를 받고, 장르·플랫폼만으로 등급이 거의 정해져 판단할 여지가 없다.
# 아케이드(2024-01~2026-09 원자료 580건)와 베팅성 보드게임(사례 기간 328건 중 327건이 청소년이용불가).
EXCLUDED_PLATFORMS = {"아케이드 게임"}
EXCLUDED_GENRES = {"보드게임(베팅성)"}
# 사례 DB 의 마지막 결정일. 평가 기간(그 뒤)을 넣으면 평가 게임이 사례로 검색돼 답이 샌다.
CASES_UNTIL = "2026-06-30"
EVAL_FROM, EVAL_UNTIL = "2026-07-01", "2026-09-30"


def usable(row: dict) -> bool:
    """사례·평가에 쓸 수 있는 결정인가 — 개요 있음 · 연령 등급(거부 아님) · 사행성 게임물 아님 · 취소 아님."""
    return (bool(row["summary"].strip()) and row["rating"] in RATINGS
            and row["platform"] not in EXCLUDED_PLATFORMS and row["genre"] not in EXCLUDED_GENRES
            and not row["canceled"])


def load_raw(raw_dir: Path = RAW_DIR) -> list[dict]:
    rows: list[dict] = []
    for path in sorted(raw_dir.glob("*.json")):
        rows += json.loads(path.read_text())["items"]
    return rows


def build_cases(rows: list[dict], until: str = CASES_UNTIL) -> list[dict]:
    """사례 DB — until 까지 결정분 중 usable 한 것. 날짜·번호 순으로 정렬해 결과가 늘 같게 한다."""
    keep = ("id", "date", "title", "applicant", "rating", "genre", "platform", "descriptors", "summary")
    cases = [{k: r[k] for k in keep} for r in rows if r["date"] <= until and usable(r)]
    return sorted(cases, key=lambda c: (c["date"], c["id"]))


def compute_stats(cases: list[dict], genre: str = "", platform: str = "", min_total: int = 5) -> dict:
    """같은 장르·플랫폼 사례의 등급 분포와 내용정보 빈도 — MCP Tool rating_stats 의 본체.

    장르·플랫폼이 둘 다 맞는 사례가 min_total 건보다 적으면 장르 조건을 빼고 플랫폼만으로 센다.
    실제로 적용한 조건을 filter 에 남긴다 — 답변이 "같은 장르·플랫폼"이라고 잘못 말하지 않게.
    """
    def pick(g: str, p: str) -> list[dict]:
        return [c for c in cases if (not g or c["genre"] == g) and (not p or c["platform"] == p)]

    applied = {"genre": genre or None, "platform": platform or None}
    chosen = pick(genre, platform)
    if len(chosen) < min_total and genre:
        applied["genre"] = None
        chosen = pick("", platform)
    by_rating = {r: sum(c["rating"] == r for c in chosen) for r in RATINGS}
    descriptors = {i: sum(i in c["descriptors"] for c in chosen) for i in ITEMS}
    dates = [c["date"] for c in cases]
    return {"filter": applied, "total": len(chosen), "by_rating": by_rating, "descriptors": descriptors,
            "period": f"{min(dates)} ~ {max(dates)}" if dates else None}


def load_cases(path: Path = CASES_PATH) -> list[dict]:
    return json.loads(path.read_text())


def load_criteria(path: Path = CRITERIA_PATH) -> dict:
    return json.loads(path.read_text())
