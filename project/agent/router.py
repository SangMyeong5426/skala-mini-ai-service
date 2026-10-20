"""항목 2 — 질문 분류(route)를 임베딩 기반 의미 라우터로.

base 는 fast 모델(qwen3:0.6b)이 chat/incident 를 고르는데, 개념 설명 요청을 장애로 보내는 오분류가
평가 세트 30문항 중 7건이었다(일반 질문 15개 중 6개). 분류 예시 문장(data/router_examples.json)과의
유사도로 먼저 판정하고, 두 클래스 점수 차가 작을 때만 기존 LLM 분류로 넘긴다.

    점수(클래스) = 질문과 가장 가까운 예시 k개의 코사인 유사도 평균
    차이 = 점수(incident) - 점수(chat)
    |차이| >= margin  → 그 클래스 (method=semantic)
    |차이| <  margin  → LLMRouter (method=llm-fallback)

margin 과 지시문은 평가 세트가 아니라 예시 문장 안의 leave-one-out 으로 정했다
(tools/tune_embedding.py, docs/decisions/0003-semantic-router.md).
"""
import json
from pathlib import Path

from langsmith import traceable

from .embedding import cosine

EXAMPLES_PATH = Path(__file__).resolve().parent.parent / "data" / "router_examples.json"
# 비교용 지시문. 예시 문장 LOO 에서 지시문 없이(0.95)가 붙일 때(0.925)보다 나아 기본은 쓰지 않는다.
ROUTE_INSTRUCTION = "운영 지원 에이전트에 들어온 메시지가 지금 일어난 장애 신고인지 일반 대화인지 분류한다"
# LOO 에서 틀린 예시의 |gap| 최댓값(0.024) + 0.005 — 예시끼리도 헷갈린 영역은 LLM 에 넘긴다.
DEFAULT_MARGIN = 0.029
DEFAULT_K = 3


def load_examples(path: Path = EXAMPLES_PATH) -> dict[str, list[str]]:
    data = json.loads(path.read_text())
    return {"chat": data["chat"], "incident": data["incident"]}


def class_scores(query_vec: list[float], example_vecs: dict[str, list[list[float]]],
                 k: int) -> dict[str, float]:
    """클래스별로 가장 가까운 예시 k개의 유사도 평균."""
    out = {}
    for label, vectors in example_vecs.items():
        sims = sorted((cosine(query_vec, v) for v in vectors), reverse=True)[:k]
        out[label] = sum(sims) / len(sims)
    return out


class LLMRouter:
    """base 동작 그대로 — fast 모델의 route(). 의미 라우터가 판정을 미룰 때 쓴다."""

    def __init__(self, fast_llm):
        self.fast_llm = fast_llm

    async def route(self, query: str) -> tuple[dict, dict]:
        result, usage = self.fast_llm.route(query)
        return {**result, "method": "llm"}, usage


class SemanticRouter:
    def __init__(self, embedder, fallback: LLMRouter, example_vecs: dict[str, list[list[float]]],
                 margin: float = DEFAULT_MARGIN, k: int = DEFAULT_K,
                 instruction: str | None = None):
        self.embedder = embedder
        self.fallback = fallback
        self.example_vecs = example_vecs
        self.margin = margin
        self.k = k
        self.instruction = instruction

    @classmethod
    async def create(cls, embedder, fallback: LLMRouter, examples: dict[str, list[str]],
                     **kwargs) -> "SemanticRouter":
        """서버 기동 때 한 번 — 예시 문장을 클래스별로 임베딩해 메모리에 둔다."""
        instruction = kwargs.get("instruction")
        example_vecs = {label: await embedder.embed(texts, instruction)
                        for label, texts in examples.items()}
        return cls(embedder, fallback, example_vecs, **kwargs)

    @traceable(name="semantic_router.route")
    async def route(self, query: str) -> tuple[dict, dict]:
        [query_vec] = await self.embedder.embed([query], self.instruction)
        scores = class_scores(query_vec, self.example_vecs, self.k)
        gap = scores["incident"] - scores["chat"]
        if abs(gap) >= self.margin:
            # incident 경로에서는 plan_node 가 needs_analysis 를 자기 판단으로 덮어쓴다 — 여기서 정하지 않는다.
            result = {"route": "incident" if gap > 0 else "chat", "needs_analysis": False,
                      "method": "semantic"}
            usage = {"model": self.embedder.name, "tokens": 0, "usd": 0.0}
        else:
            result, usage = await self.fallback.route(query)
            result = {**result, "method": "llm-fallback"}
        result["gap"] = round(gap, 4)
        result["scores"] = {label: round(s, 4) for label, s in scores.items()}
        return result, usage
