"""기능 8 — 법령에 근거한 제도 안내. 근거를 못 찾으면 답할 수 없다고 한다(결정 0015).

LLM 단독(0.6b 대화)은 제도 질문에 근거 없이 답하다 틀렸다 — "청소년이용불가는 14세 이상"(2026-10-20 회귀 쿼리).
게임산업법은 청소년을 「청소년 보호법」에 따른다고만 정하고 나이를 적지 않는다. 그래서 이 모듈은

  1. 조문 검색 — 게임산업법·시행령·시행규칙 조문(MCP Resource law://game-industry/articles)을 임베딩해 두고
     질문과 가까운 K개를 고른다. 사례 검색(cases.py)과 같은 방식·같은 캐시를 쓴다.
  2. 답변 — quality 모델이 검색된 조문만 보고 {kind, answerable, answer, citations} JSON 을 낸다.
  3. 코드 검사 — 인용한 조문이 검색된 조문인가, 답의 수치(나이·금액·기간)가 인용 조문이나 질문에 있는가.
     하나라도 어기면 답하지 않는다 — "답할 수 없습니다" + 찾아본 조문 + 위원회 안내.

인사·감사 같은 잡담(kind=smalltalk)은 법령 근거가 필요 없어 정해진 소개 문장으로 답한다.
"""
import hashlib
import re

from langsmith import traceable

from ..embedding import cosine
from ..validator import NUMBER
from .cases import CACHE_DIR, _read_cache, _write_cache

DEFAULT_K = 4
REFERENCE = re.compile(r"제\s*\d+\s*(?:조|항|호|목)(?:의\s*\d+)?")   # 조문 가리킴 — 수치가 아니다
SMALLTALK_REPLY = ("안녕하세요. 저는 출시 전 게임의 등급을 점검하고, 게임산업진흥에 관한 법률·시행령·시행규칙에 근거해 "
                   "등급분류 제도를 안내합니다. 점검할 게임의 내용(장르, 플랫폼, 폭력·선정·사행 표현의 수위)을 알려 주세요.")
REFUSAL = "제공된 법령(게임산업진흥에 관한 법률·시행령·시행규칙)에서 이 질문에 답할 근거를 찾지 못해 답할 수 없습니다"
GUIDE = "정확한 내용은 게임물관리위원회 안내를 확인해 주세요."


def article_text(article: dict) -> str:
    return f"{article['key']}({article['title']}) {article['text']}"


def ungrounded_numbers(answer: str, sources: list[str]) -> list[str]:
    """답의 수치 중 근거 글(인용 조문·질문)에 없는 것. 조문을 가리키는 "제21조 제2항"의 숫자는 수치로 보지 않는다."""
    allowed = {float(n) for s in sources for n in NUMBER.findall(REFERENCE.sub(" ", s))}
    unknown: list[str] = []
    for token in NUMBER.findall(REFERENCE.sub(" ", answer)):
        if float(token) not in allowed and token not in unknown:
            unknown.append(token)
    return unknown


class LawAnswerer:
    def __init__(self, embedder, llm, articles: list[dict], vectors: list[list[float]], k: int = DEFAULT_K):
        self.embedder = embedder
        self.llm = llm   # answer_law(question, articles) -> (raw, usage) 를 가진 quality 모델
        self.articles = articles
        self.vectors = vectors
        self.k = k

    @classmethod
    async def create(cls, embedder, llm, articles: list[dict], k: int = DEFAULT_K,
                     cache_dir=CACHE_DIR) -> "LawAnswerer":
        """서버 기동 때 한 번 — 조문을 임베딩해 둔다(사례 검색과 같은 캐시)."""
        texts = [article_text(a) for a in articles]
        digest = hashlib.sha1("\n".join([embedder.name, "law", *texts]).encode()).hexdigest()[:16]
        path = cache_dir / f"{digest}.json" if cache_dir else None
        vectors = _read_cache(path) if path else None
        if vectors is None:
            vectors = []
            for i in range(0, len(texts), 32):
                vectors += await embedder.embed(texts[i:i + 32])
            if path:
                _write_cache(path, vectors)
        return cls(embedder, llm, articles, vectors, k)

    async def search(self, question: str) -> list[dict]:
        [vec] = await self.embedder.embed([question])
        ranked = sorted(((cosine(vec, v), i) for i, v in enumerate(self.vectors)), reverse=True)[:self.k]
        return [{**self.articles[i], "score": round(score, 4)} for score, i in ranked]

    @traceable(name="law_answerer.answer")
    async def answer(self, question: str) -> tuple[dict, dict]:
        """{"kind", "answerable", "text"(사용자에게 보일 답), "citations", "searched", "reason"} 와 비용."""
        found = await self.search(question)
        raw, usage = self.llm.answer_law(question, found)
        searched = [a["key"] for a in found]
        if raw.get("kind") == "smalltalk":
            return {"kind": "smalltalk", "answerable": False, "text": SMALLTALK_REPLY, "citations": [],
                    "searched": searched, "reason": None}, usage
        by_key = {a["key"]: a for a in found}
        citations = [c for c in dict.fromkeys(raw.get("citations") or []) if isinstance(c, str)]
        reason = None
        if not raw.get("answerable") or not str(raw.get("answer", "")).strip():
            reason = "법령에서 답을 찾지 못했습니다"
        elif not citations:
            reason = "근거 조문을 밝히지 않았습니다"
        elif any(c not in by_key for c in citations):
            reason = f"검색하지 않은 조문을 인용했습니다({', '.join(c for c in citations if c not in by_key)})"
        else:
            unknown = ungrounded_numbers(raw["answer"], [question, *(article_text(by_key[c]) for c in citations)])
            if unknown:
                reason = f"인용 조문에 없는 수치를 썼습니다({', '.join(unknown)})"
        if reason:
            listed = ", ".join(f"{a['key']}({a['title']})" for a in found)
            return {"kind": "law", "answerable": False, "citations": [], "searched": searched, "reason": reason,
                    "text": f"{REFUSAL}. {GUIDE}\n\n찾아본 조문: {listed}"}, usage
        grounds = "\n".join(f"- {c}({by_key[c]['title']})" for c in citations)
        return {"kind": "law", "answerable": True, "citations": citations, "searched": searched, "reason": None,
                "text": f"{raw['answer'].strip()}\n\n근거:\n{grounds}\n\n※ 법령 원문을 요약한 안내입니다. {GUIDE}"}, usage
