"""기능 8 — 법령 근거 제도 안내: 인용·수치를 코드가 검사하고, 어기면 답할 수 없다고 한다(결정 0015)."""
import asyncio

from agent.rating.law import REFUSAL, SMALLTALK_REPLY, LawAnswerer, ungrounded_numbers

ARTICLES = [
    {"key": "게임산업법 제21조", "law": "게임산업진흥에 관한 법률", "article": "제21조", "title": "등급분류",
     "text": "제21조(등급분류) ②게임물의 등급은 다음 각 호와 같다. 2. 12세이용가 : 12세 미만은 이용할 수 없는 게임물"},
    {"key": "게임산업법 제2조", "law": "게임산업진흥에 관한 법률", "article": "제2조", "title": "정의",
     "text": "제2조(정의) 10. “청소년”이란 「청소년 보호법」 제2조 제1호 에 따른 청소년을 말한다."},
]


class Embedder:
    name = "fake-embed"

    async def embed(self, texts, instruction=None):
        return [[float("등급" in t), float("청소년" in t), 0.1] for t in texts]


class LLM:
    def __init__(self, raw):
        self.raw = raw

    def answer_law(self, question, articles):
        return self.raw, {"usd": 0.001}


def _answer(raw, question="청소년이용불가 게임은 몇 살부터 할 수 있어요?"):
    answerer = asyncio.run(LawAnswerer.create(Embedder(), LLM(raw), ARTICLES, k=2, cache_dir=None))
    result, _ = asyncio.run(answerer.answer(question))
    return result


def test_grounded_answer_lists_cited_articles():
    result = _answer({"kind": "law", "answerable": True, "citations": ["게임산업법 제21조"],
                      "answer": "12세이용가는 12세 미만이 이용할 수 없습니다."}, "12세이용가가 뭐예요?")

    assert result["answerable"]
    assert "근거:\n- 게임산업법 제21조(등급분류)" in result["text"]


def test_number_not_in_cited_article_is_refused():
    """게임산업법에는 청소년 나이가 없다 — 19세라고 답하면 지어낸 수치로 보고 답하지 않는다."""
    result = _answer({"kind": "law", "answerable": True, "citations": ["게임산업법 제2조"],
                      "answer": "청소년이용불가는 19세 이상부터 이용할 수 있습니다."})

    assert not result["answerable"]
    assert result["text"].startswith(REFUSAL)
    assert "19" in result["reason"]


def test_citation_outside_search_or_missing_is_refused():
    outside = _answer({"kind": "law", "answerable": True, "citations": ["청소년 보호법 제2조"], "answer": "법에 있습니다."})
    missing = _answer({"kind": "law", "answerable": True, "citations": [], "answer": "법에 있습니다."})
    declined = _answer({"kind": "law", "answerable": False, "citations": [], "answer": ""})

    assert "검색하지 않은 조문" in outside["reason"]
    assert missing["reason"] == "근거 조문을 밝히지 않았습니다"
    assert not declined["answerable"] and "찾아본 조문:" in declined["text"]


def test_smalltalk_gets_the_fixed_introduction():
    result = _answer({"kind": "smalltalk", "answerable": False, "citations": [], "answer": ""}, "안녕하세요")

    assert result["text"] == SMALLTALK_REPLY


def test_article_references_are_not_numbers():
    assert ungrounded_numbers("제21조 제2항 제2호에 따르면 12세 미만은 안 됩니다", [ARTICLES[0]["text"]]) == []
    assert "36" in ungrounded_numbers("수수료는 36,000원입니다", [ARTICLES[0]["text"]])
