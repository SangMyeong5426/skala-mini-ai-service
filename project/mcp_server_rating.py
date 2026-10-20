"""과제 2 — 게임 등급분류 MCP 서버 (Tool / Resource).

FastAPI 백엔드(server.py)가 AGENT_DOMAIN=rating 일 때 이 파일을 subprocess(stdio)로 띄운다(mcp_server.py 와 같은 방식).
data/ratings/ 의 파일만 읽는다 — 실행 중에는 게임물관리위원회 API 를 부르지 않는다(결정 0010).

- Tool     rating_stats                : 장르·플랫폼으로 사례 DB 를 집계 — 인자마다 결과가 달라지는 조회라 Tool
- Resource criteria://descriptors      : 내용정보 7항목 × 4단계 기준표(사례집 요약표)
- Resource law://game-industry/rule-8  : 시행규칙 제8조(등급분류기준) 원문
- Resource ratings://cases             : 사례 DB 전체 — 에이전트가 기동 때 한 번 읽어 유사 사례 검색 색인을 만든다
"""
from fastmcp import FastMCP
from pydantic import BaseModel, Field

from agent.rating.data import CASES_PATH, CRITERIA_PATH, RULE8_PATH, compute_stats, load_cases

mcp = FastMCP(name="game-rating")


class RatingStats(BaseModel):
    filter: dict[str, str | None] = Field(description="실제로 적용한 조건 — 사례가 적으면 장르 조건을 뺀다")
    total: int = Field(description="조건에 맞는 사례 수")
    by_rating: dict[str, int] = Field(description="등급별 사례 수")
    descriptors: dict[str, int] = Field(description="내용정보 항목별 사례 수")
    period: str | None = Field(description="사례 DB 의 결정일 범위")


@mcp.tool()
def rating_stats(genre: str = "", platform: str = "") -> RatingStats:
    """같은 장르·플랫폼의 등급분류 사례 수, 등급 분포, 내용정보 빈도를 센다. 5건보다 적으면 장르 조건을 뺀다."""
    return RatingStats(**compute_stats(load_cases(), genre, platform))


@mcp.resource("criteria://descriptors")
def get_descriptor_criteria() -> str:
    """내용정보 7항목 × 4단계 기준표(JSON). 단계 0~3 = 전체이용가 · 12세 · 15세 · 청소년이용불가."""
    return CRITERIA_PATH.read_text()


@mcp.resource("law://game-industry/rule-8")
def get_rule_8() -> str:
    """게임산업진흥에 관한 법률 시행규칙 제8조(등급분류기준 등) 원문."""
    return RULE8_PATH.read_text()


@mcp.resource("ratings://cases")
def get_rating_cases() -> str:
    """사례 DB(JSON) — 2026-06-30까지 게임물관리위원회 결정 중 개요가 있는 연령 등급(사행성 게임물 제외)."""
    return CASES_PATH.read_text()


if __name__ == "__main__":
    try:
        mcp.run(show_banner=False)
    except TypeError:   # 구버전 fastmcp 호환
        mcp.run()
