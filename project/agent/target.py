"""항목 3 — 질문에서 진단할 대상 시스템을 정한다. 정하지 못하면 되묻는다.

base 는 시스템명이 없으면 auth-service 로 채운다(graph._extract_system_name, plan 프롬프트,
_guess_target 세 곳). 그래서 "캐시 히트율이 떨어졌어요"도 "서버가 이상한데?"도 auth-service 를
진단했다(대상 평가 6/15, 엉뚱한 진단 7건). 이 모듈은 아래 순서로 본다.

  1. 카탈로그의 시스템명이 질문에 있다     → 등장한 전부, 등장 순서대로        (name-match)
  2. 'xxx-service' 꼴인데 카탈로그에 없다  → 되묻기 — 모니터링 대상이 아니다     (unknown-system)
  3. 질문 ↔ 시스템 설명 유사도 1위가 min_score 이상이고 2위보다 margin 이상 높다
                                          → 1위 하나                         (semantic)
  4. 그 밖                                 → 되묻기 — 특정할 수 없다           (semantic)

카탈로그는 MCP Resource(catalog://systems)로 받는다. 시스템 목록의 출처를 MCP 서버 하나로 둔다.
min_score·margin 은 평가 세트가 아닌 별도 조정용 문장으로 정했다(tools/tune_embedding.py).
"""
import re

from langsmith import traceable

from .embedding import cosine

TARGET_INSTRUCTION = "운영 장애 신고 문장이 어느 시스템의 문제인지 찾는다"
DEFAULT_MIN_SCORE = 0.3   # 임시값 — tools/tune_embedding.py 결과로 갱신한다
DEFAULT_MARGIN = 0.03     # 임시값
# 시스템 이름처럼 생긴 토큰. 한글 조사가 바로 붙어도("billing-service가") 잡히도록 \b 를 쓰지 않는다.
SERVICE_LIKE = re.compile(r"(?<![a-z0-9-])[a-z][a-z0-9]*(?:-[a-z0-9]+)*-(?:service|\d+)(?![a-z0-9-])")


class TargetResolver:
    def __init__(self, embedder, catalog: list[dict], system_vecs: list[list[float]],
                 min_score: float = DEFAULT_MIN_SCORE, margin: float = DEFAULT_MARGIN,
                 instruction: str | None = TARGET_INSTRUCTION):
        self.embedder = embedder
        self.catalog = catalog
        self.system_vecs = system_vecs
        self.min_score = min_score
        self.margin = margin
        self.instruction = instruction

    @classmethod
    async def create(cls, embedder, catalog: list[dict], **kwargs) -> "TargetResolver":
        """서버 기동 때 한 번 — 시스템 설명을 임베딩해 둔다. 문서 쪽이라 지시문은 붙이지 않는다."""
        system_vecs = await embedder.embed([f"{s['name']}: {s['description']}" for s in catalog])
        return cls(embedder, catalog, system_vecs, **kwargs)

    @property
    def names(self) -> list[str]:
        return [s["name"] for s in self.catalog]

    @traceable(name="target_resolver.resolve")
    async def resolve(self, query: str) -> dict:
        found = sorted((query.index(n), n) for n in self.names if n in query)
        if found:
            return {"targets": [n for _, n in found], "method": "name-match", "reason": None}

        unknown = [m for m in SERVICE_LIKE.findall(query) if m not in self.names]
        if unknown:
            return {"targets": [], "method": "unknown-system",
                    "reason": f"{', '.join(unknown)}는 모니터링 대상이 아닙니다"}

        [query_vec] = await self.embedder.embed([query], self.instruction)
        ranked = sorted(((cosine(query_vec, v), s["name"])
                         for s, v in zip(self.catalog, self.system_vecs, strict=True)), reverse=True)
        (best_score, best), (second_score, _) = ranked[0], ranked[1]
        scores = {name: round(score, 4) for score, name in ranked}
        if best_score >= self.min_score and best_score - second_score >= self.margin:
            return {"targets": [best], "method": "semantic", "reason": None, "scores": scores}
        return {"targets": [], "method": "semantic", "scores": scores,
                "reason": "질문만으로는 어느 시스템의 문제인지 특정할 수 없습니다"}
