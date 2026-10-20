"""기능 3 — 유사 사례 검색: 범위 필터, 범위 넓히기, 임베딩 캐시. 가짜 임베더로 ollama 없이 본다."""
import asyncio

from agent.rating.cases import CaseRetriever, effective_scope

WORDS = ["좀비", "퍼즐", "연애", "총"]
CASES = [
    {"id": f"C{i}", "title": t, "rating": r, "descriptors": d, "genre": g, "platform": p, "summary": s}
    for i, (t, r, d, g, p, s) in enumerate([
        ("좀비 헌터", "청소년이용불가", ["폭력성"], "FPS/TPS", "PC/온라인 게임", "좀비를 총으로 쏘는 게임"),
        ("좀비 농장", "12세이용가", ["폭력성"], "캐주얼", "PC/온라인 게임", "좀비로부터 농장을 지키는 게임"),
        ("블록 퍼즐", "전체이용가", [], "퍼즐", "모바일 게임", "같은 색 블록을 맞추는 퍼즐"),
        ("러브 데이트", "15세이용가", ["선정성"], "시뮬레이션", "모바일 게임", "연애 시뮬레이션"),
    ])
]


class FakeEmbedder:
    name = "fake-embed"

    def __init__(self):
        self.calls = 0

    async def embed(self, texts, instruction=None):
        self.calls += 1
        return [[float(t.count(w)) for w in WORDS] + [0.1] for t in texts]


def _create(embedder, tmp_path):
    return asyncio.run(CaseRetriever.create(embedder, CASES, k=2, cache_dir=tmp_path))


def test_search_ranks_by_similarity_within_scope(tmp_path):
    retriever = _create(FakeEmbedder(), tmp_path)

    found, scope = asyncio.run(retriever.search("좀비를 총으로 쏘는 PC 게임", "FPS/TPS", "PC/온라인 게임"))

    assert scope == "genre+platform"
    assert [c["id"] for c in found] == ["C0"]   # 장르·플랫폼이 둘 다 맞는 사례만
    assert found[0]["score"] > 0


def test_wider_scope_finds_more(tmp_path):
    retriever = _create(FakeEmbedder(), tmp_path)

    found, scope = asyncio.run(retriever.search("좀비 게임", "FPS/TPS", "PC/온라인 게임", "platform"))

    assert scope == "platform"
    assert {c["id"] for c in found} == {"C0", "C1"}


def test_missing_profile_starts_wide():
    assert effective_scope("genre+platform", None, "모바일 게임") == "platform"
    assert effective_scope("genre+platform", "퍼즐", None) == "all"
    assert effective_scope("platform", None, None) == "all"


def test_cache_is_reused_for_same_model_and_cases(tmp_path):
    first = FakeEmbedder()
    _create(first, tmp_path)
    second = FakeEmbedder()
    retriever = _create(second, tmp_path)

    assert first.calls == 1     # 사례 4건 — 한 묶음
    assert second.calls == 0    # 캐시에서 읽었다
    assert retriever.vectors[0][:2] == [2.0, 0.0]   # 제목·개요에 "좀비"가 두 번
