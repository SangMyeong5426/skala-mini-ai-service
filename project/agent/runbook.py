"""항목 5 — 대응 매뉴얼(runbook) 선택을 키워드 규칙 → 의미 검색으로.

base 의 replan_check 는 수집한 모니터링 상태·알림 문구에서 키워드(latency·cpu·memory…)를 찾아
runbook 을 고르고, 하나도 안 맞으면 db-down 으로 폴백한다. 사용자가 말한 증상은 보지 않는다.
그래서 알림이 아직 없는 시스템("web-01 CPU 가 100%까지 올랐어요")은 db-down 을, 알림이 여러
종류 섞이면 규칙 순서상 먼저 걸리는 쪽을 고른다.

이 모듈은 runbook 6종을 기동 때 한 번 임베딩해 두고(메타데이터 = 파일 이름 = incident_type),
"질문 + 수집한 알림 문구"와 가장 가까운 runbook 을 고른다. 고른 runbook 의 본문 조회는 지금처럼
MCP Resource(runbook://incident-response/{type})로 한다 — 인덱싱만 파일을 직접 읽는다.
"""
from pathlib import Path

from langsmith import traceable

from .embedding import cosine

RUNBOOK_DIR = Path(__file__).resolve().parent.parent / "data" / "runbooks"
# 조정 데이터가 없어 고르지 않았다. 같은 "질문 ↔ 문서" 구조인 대상 추정에서 지시문 없이가 나아 그대로 따른다.
RUNBOOK_INSTRUCTION = "운영 장애 증상과 알림에 맞는 대응 매뉴얼을 찾는다"


def load_runbooks(path: Path = RUNBOOK_DIR) -> dict[str, str]:
    """incident_type(파일 이름) → 본문."""
    return {p.stem: p.read_text() for p in sorted(path.glob("*.md"))}


def symptom_text(query: str, collected: list[dict]) -> str:
    alerts = [a for c in collected if c["source"] == "monitoring" for a in c["data"].get("alerts", [])]
    return query + (f"\n알림: {'; '.join(alerts)}" if alerts else "")


class RunbookSelector:
    def __init__(self, embedder, types: list[str], runbook_vecs: list[list[float]],
                 instruction: str | None = None):
        self.embedder = embedder
        self.types = types
        self.runbook_vecs = runbook_vecs
        self.instruction = instruction

    @classmethod
    async def create(cls, embedder, runbooks: dict[str, str], **kwargs) -> "RunbookSelector":
        """서버 기동 때 한 번 — runbook 본문을 임베딩해 둔다. 문서 쪽이라 지시문은 붙이지 않는다."""
        return cls(embedder, list(runbooks), await embedder.embed(list(runbooks.values())), **kwargs)

    @traceable(name="runbook_selector.select")
    async def select(self, query: str, collected: list[dict]) -> dict:
        [vec] = await self.embedder.embed([symptom_text(query, collected)], self.instruction)
        ranked = sorted(((cosine(vec, v), t) for t, v in zip(self.types, self.runbook_vecs, strict=True)),
                        reverse=True)
        return {"incident_type": ranked[0][1], "method": "semantic",
                "scores": {t: round(s, 4) for s, t in ranked}}
