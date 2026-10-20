"""항목 2·3·5 — Ollama 임베딩 클라이언트 (기본 qwen3-embedding:0.6b).

의미 라우터(router.py)·대상 시스템 추정(target.py)·runbook 선택(runbook.py)이 같은 인스턴스를 나눠 쓴다. 서버 기동 때
예시 문장·시스템 설명을 한 번 임베딩해 두고, 요청마다 질문 하나만 임베딩한다
(2026-10-20 실측: 질문 하나 0.038초, 모델 첫 로드 1.4초, 1024차원).

Qwen3-Embedding 은 질의 앞에 과제 지시문을 붙이는 형식(Instruct: …\\nQuery:…)을 권한다. 붙일지와
어떤 문장을 붙일지는 각 사용처가 정한다 — tools/tune_embedding.py 로 비교해 보니 라우터·대상 추정 모두
지시문 없이가 나아, 지금은 어느 곳도 붙이지 않는다(비교용 문장은 각 모듈에 남겨 두었다).
"""
import math

import httpx
from langsmith import traceable

OLLAMA_EMBED_URL = "http://127.0.0.1:11434/api/embed"


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / norm if norm else 0.0


def with_instruction(texts: list[str], instruction: str | None) -> list[str]:
    if not instruction:
        return texts
    return [f"Instruct: {instruction}\nQuery:{t}" for t in texts]


class OllamaEmbedder:
    def __init__(self, model: str = "qwen3-embedding:0.6b"):
        self.name = f"ollama:{model}"
        self.model = model

    @traceable(run_type="embedding", name="ollama.embed")
    async def embed(self, texts: list[str], instruction: str | None = None) -> list[list[float]]:
        payload = {"model": self.model, "input": with_instruction(texts, instruction)}
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(OLLAMA_EMBED_URL, json=payload)
            resp.raise_for_status()
        return resp.json()["embeddings"]
