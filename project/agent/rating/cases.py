"""기능 3 — 유사 사례 검색. 사례 개요를 임베딩해 두고 게임 설명과 가까운 실제 결정 k건을 고른다(RAG).

사례 DB 는 MCP Resource(ratings://cases)로 받는다. 서버 기동 때 한 번 임베딩하고, 같은 모델·같은 사례면 파일
캐시(data/ratings/.embed-cache/, git 에 넣지 않는다)를 다시 쓴다 — 측정(scripts/measure-at)은 질문마다 서버를
새로 띄우기 때문이다. 질의 쪽 지시문은 붙이지 않는다(과제 1 대상 추정에서 지시문 없이가 나았다).

검색 범위(scope)는 넓은 쪽으로만 바뀐다: genre+platform → platform → all. 장르·플랫폼을 질문에서 못 뽑았으면
처음부터 넓은 범위로 찾는다. 사례가 모자라 범위를 넓히는 판단은 그래프의 replan_check 가 한다.
"""
import base64
import hashlib
import json
import re
from array import array
from pathlib import Path

from langsmith import traceable

from ..embedding import cosine
from .data import DATA_DIR

CACHE_DIR = DATA_DIR / ".embed-cache"
DEFAULT_K = 5
BATCH = 64


def case_text(case: dict) -> str:
    """색인에 넣는 글 — 제목도 넣는다. 사용자가 시리즈·원작 이름을 말하면 같은 계열의 결정을 찾게.
    개요가 없는 결정(간소화 등급분류)은 제목·장르·플랫폼만으로 찾힌다."""
    tail = f" — {case['summary']}" if case["summary"] else ""
    return f"{case['title']} — {case['genre']} · {case['platform']}{tail}"


def effective_scope(scope: str, genre: str | None, platform: str | None) -> str:
    if scope == "genre+platform" and not (genre and platform):
        scope = "platform" if platform else "all"
    if scope == "platform" and not platform:
        scope = "all"
    return scope


def _norm_title(title: str) -> str:
    return re.sub(r"[\W_]+", "", title).casefold()


def _in_scope(case: dict, scope: str, genre: str | None, platform: str | None) -> bool:
    if scope == "genre+platform":
        return case["genre"] == genre and case["platform"] == platform
    if scope == "platform":
        return case["platform"] == platform
    return True


def _read_cache(path: Path) -> list[list[float]] | None:
    if not path.exists():
        return None
    meta = json.loads(path.read_text())
    flat = array("f")
    flat.frombytes(base64.b64decode(meta["data"]))
    dim = meta["dim"]
    return [flat[i * dim:(i + 1) * dim].tolist() for i in range(meta["n"])]


def _write_cache(path: Path, vectors: list[list[float]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    flat = array("f", [x for v in vectors for x in v])
    path.write_text(json.dumps({"n": len(vectors), "dim": len(vectors[0]),
                                "data": base64.b64encode(flat.tobytes()).decode()}))


class CaseRetriever:
    def __init__(self, embedder, cases: list[dict], vectors: list[list[float]], k: int = DEFAULT_K):
        self.embedder = embedder
        self.cases = cases
        self.vectors = vectors
        self.k = k
        self.excluded: set[int] = set()

    @classmethod
    async def create(cls, embedder, cases: list[dict], k: int = DEFAULT_K,
                     cache_dir: Path | None = CACHE_DIR) -> "CaseRetriever":
        """서버 기동 때 한 번 — 사례를 임베딩해 둔다. 모델 이름과 사례 글이 같으면 캐시를 쓴다."""
        texts = [case_text(c) for c in cases]
        digest = hashlib.sha1("\n".join([embedder.name, *texts]).encode()).hexdigest()[:16]
        path = cache_dir / f"{digest}.json" if cache_dir else None
        vectors = _read_cache(path) if path else None
        if vectors is None:
            vectors = []
            for i in range(0, len(texts), BATCH):
                vectors += await embedder.embed(texts[i:i + BATCH])
            if path:
                _write_cache(path, vectors)
        return cls(embedder, cases, vectors, k)

    def exclude(self, case_id: str | None = None, title: str | None = None) -> None:
        """평가 전용 — 다음 검색부터 이 결정(같은 번호, 또는 띄어쓰기·대소문자를 무시하고 같은 제목)을 뺀다.

        평가셋 B 의 게임은 사례 DB 기간에 있어 자기 자신이 검색되면 답이 샌다. 인자 없이 부르면 되돌린다.
        """
        key = _norm_title(title) if title else None
        self.excluded = {i for i, c in enumerate(self.cases)
                         if case_id and (c["id"] == case_id or (key and _norm_title(c["title"]) == key))}

    @traceable(name="case_retriever.search")
    async def search(self, text: str, genre: str | None = None, platform: str | None = None,
                     scope: str = "genre+platform") -> tuple[list[dict], str]:
        """(가까운 사례 k건 — 각 사례에 score, 실제로 쓴 범위)."""
        scope = effective_scope(scope, genre, platform)
        candidates = [i for i, c in enumerate(self.cases)
                      if i not in self.excluded and _in_scope(c, scope, genre, platform)]
        if not candidates:
            return [], scope
        [query_vec] = await self.embedder.embed([text])
        ranked = sorted(((cosine(query_vec, self.vectors[i]), i) for i in candidates), reverse=True)[:self.k]
        return [{**self.cases[i], "score": round(score, 4)} for score, i in ranked], scope
