"""사례 검색 방식 비교 — 임베딩(지금 방식) vs BM25(키워드). LLM 없이 사례 등급만 본다.

    project/.venv/bin/python tools/compare_retrieval.py

개발용 문항(tools/evalsets/rating_dev.json, 38개)만 쓴다. 평가셋 A·B 는 읽지 않는다 — 검색 방식을 평가셋으로
고르지 않기 위해서다(CLAUDE.md "판정 기준을 평가 세트로 고르지 않는다").

절차는 eval_rating.py rbase(기준선)와 같다. 문항의 message 로 찾고, 장르·플랫폼은 extract_profile 로 뽑고,
사례가 MIN_CASES(3)건보다 적으면 그래프와 같은 순서(장르+플랫폼 → 플랫폼 → 전체)로 범위를 넓힌다.
찾은 5건에서 가장 가까운 1건의 등급(nn1)과 5건 다수결(vote5, 동률이면 더 가까운 사례의 등급)을 정답과 비교한다.
바뀌는 것은 범위 안 사례의 순위를 매기는 방법뿐이다.

방법 (결과를 보기 전에 정한 설정)
- embedding : agent.rating.cases.CaseRetriever 그대로(qwen3-embedding, 코사인, 파일 캐시).
- bm25-bigram : BM25(k1=1.2, b=0.75). 한글은 형태소 분석기 없이 글자 2개씩 자른 조각(bigram), 영문·숫자는 단어.
                주 비교 대상이다 — 한국어는 조사·어미가 붙어 띄어쓰기 단어로는 같은 말이 잘 안 맞는다.
- bm25-word : 같은 BM25, 띄어쓰기 단어 그대로. 토큰 방식에 따라 결과가 얼마나 흔들리는지 보려고 함께 낸다.
BM25 의 색인 글은 임베딩과 같은 case_text(제목 — 장르 · 플랫폼 — 개요)이고, IDF 는 사례 DB 전체로 계산한다.
질문 토큰은 중복을 뺀다(문항 앞의 고정 문구가 여러 번 세지지 않게). 점수가 같으면 임베딩과 같은 규칙(번호가 큰 쪽)으로 줄 세운다.

결과는 runs/compare-retrieval_dev_<시각>.json 에 남긴다. 38문항이라 몇 문항 차이는 우연일 수 있다 — 두 방법이 엇갈린
문항 수(한쪽만 맞힘)를 함께 낸다.
"""
import asyncio
import json
import math
import os
import re
import sys
from collections import Counter
from datetime import datetime

from measure_queries import ROOT, _display, _git_state

sys.path.insert(0, str(ROOT / "project"))
from agent.embedding import OllamaEmbedder  # noqa: E402
from agent.rating import graph as rating_graph  # noqa: E402
from agent.rating.cases import CaseRetriever, case_text, effective_scope  # noqa: E402
from agent.rating.cases import _in_scope as in_scope  # noqa: E402
from agent.rating.data import RATINGS, load_cases  # noqa: E402
from agent.rating.profile import extract_profile  # noqa: E402

DEV_SET = ROOT / "tools" / "evalsets" / "rating_dev.json"
K = 5
K1, B = 1.2, 0.75


def tokens_bigram(text: str) -> list[str]:
    out = []
    for word in re.findall(r"[0-9a-z]+|[가-힣]+", text.lower()):
        if word[0] >= "가" and len(word) > 1:
            out += [word[i:i + 2] for i in range(len(word) - 1)]
        else:
            out.append(word)
    return out


def tokens_word(text: str) -> list[str]:
    return re.findall(r"[0-9a-z가-힣]+", text.lower())


class BM25Retriever:
    """CaseRetriever.search 와 같은 모양 — (사례 k건, 실제로 쓴 범위)."""

    def __init__(self, cases: list[dict], tokenize, k: int = K):
        self.cases, self.tokenize, self.k = cases, tokenize, k
        docs = [tokenize(case_text(c)) for c in cases]
        self.tf = [Counter(d) for d in docs]
        self.length = [len(d) for d in docs]
        self.avg = sum(self.length) / len(docs)
        df = Counter(t for tf in self.tf for t in tf)
        n = len(docs)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def score(self, query: set[str], i: int) -> float:
        tf, norm = self.tf[i], K1 * (1 - B + B * self.length[i] / self.avg)
        return sum(self.idf[t] * tf[t] * (K1 + 1) / (tf[t] + norm) for t in query if t in tf)

    async def search(self, text: str, genre: str | None, platform: str | None,
                     scope: str = "genre+platform") -> tuple[list[dict], str]:
        scope = effective_scope(scope, genre, platform)
        candidates = [i for i, c in enumerate(self.cases) if in_scope(c, scope, genre, platform)]
        query = set(self.tokenize(text))
        ranked = sorted(((self.score(query, i), i) for i in candidates), reverse=True)[:self.k]
        return [{**self.cases[i], "score": round(s, 4)} for s, i in ranked], scope


async def run(retriever, items: list[dict]) -> list[dict]:
    rows = []
    for item in items:
        profile = extract_profile(item["message"])
        scope = "genre+platform"
        while True:
            found, used = await retriever.search(item["message"], profile["genre"], profile["platform"], scope)
            if len(found) >= rating_graph.MIN_CASES or rating_graph.WIDER.get(used) is None:
                break
            scope = rating_graph.WIDER[used]
        votes = Counter(c["rating"] for c in found)
        top = max(votes.values(), default=0)
        vote = next((c["rating"] for c in found if votes[c["rating"]] == top), None)
        rows.append({"id": item["id"], "label": item["label"]["rating"], "scope": used,
                     "nn1": found[0]["rating"] if found else None, "vote": vote,
                     "nn1_no_summary": bool(found) and not found[0]["summary"],
                     "top_score": found[0]["score"] if found else None,
                     "cases": [c["id"] for c in found]})
    return rows


def summarize(rows: list[dict]) -> dict:
    n = len(rows)

    def under(pred: str | None, gold: str) -> bool:
        return pred is not None and RATINGS.index(pred) < RATINGS.index(gold)
    return {"n": n,
            "nn1": f"{sum(r['nn1'] == r['label'] for r in rows)}/{n}",
            "vote5": f"{sum(r['vote'] == r['label'] for r in rows)}/{n}",
            "nn1_under": sum(under(r["nn1"], r["label"]) for r in rows),
            "vote5_under": sum(under(r["vote"], r["label"]) for r in rows),
            "nn1_no_summary": sum(r["nn1_no_summary"] for r in rows),
            "zero_top_score": sum(r["top_score"] == 0 for r in rows),
            "widened": sum(r["scope"] != "genre+platform" for r in rows)}


def versus(a: list[dict], b: list[dict], key: str) -> dict:
    """같은 문항에서 a 만 맞힌 수, b 만 맞힌 수 — 차이가 우연인지 가늠하는 엇갈린 문항."""
    return {"only_first": sum(x[key] == x["label"] != y[key] for x, y in zip(a, b, strict=True)),
            "only_second": sum(y[key] == y["label"] != x[key] for x, y in zip(a, b, strict=True))}


async def main() -> None:
    git_state, stamp = _git_state(), datetime.now().strftime("%Y%m%d-%H%M%S")
    items = json.loads(DEV_SET.read_text())
    cases = load_cases()
    embedder = OllamaEmbedder(os.environ.get("OLLAMA_EMBED_MODEL", "qwen3-embedding:0.6b"))
    methods = {"embedding": await CaseRetriever.create(embedder, cases, k=K),
               "bm25-bigram": BM25Retriever(cases, tokens_bigram),
               "bm25-word": BM25Retriever(cases, tokens_word)}
    results = {name: await run(r, items) for name, r in methods.items()}
    summary = {name: summarize(rows) for name, rows in results.items()}
    emb = results["embedding"]
    for name in ("bm25-bigram", "bm25-word"):
        other = results[name]
        summary[name]["vs_embedding"] = {
            "nn1": versus(other, emb, "nn1"), "vote5": versus(other, emb, "vote"),
            "same_top1_case": sum(x["cases"][:1] == y["cases"][:1] for x, y in zip(other, emb, strict=True)),
            "mean_top5_overlap": round(sum(len(set(x["cases"]) & set(y["cases"])) for x, y in zip(other, emb, strict=True))
                                       / len(items), 2)}
    report = {"started_at": stamp, "git": git_state, "evalset": _display(DEV_SET), "n": len(items),
              "cases": len(cases), "embedder": embedder.name, "k": K, "bm25": {"k1": K1, "b": B},
              "summary": summary, "rows": results}
    out = ROOT / "runs" / f"compare-retrieval_dev_{stamp}.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(f"개발용 {len(items)}문항 · 사례 {len(cases)}건 · k={K}")
    print(f"{'방법':<13} {'1건':>6} {'5건 다수결':>9} {'낮게(1건/5건)':>12} {'1위가 개요 없음':>13} {'범위 넓힘':>8}")
    for name, s in summary.items():
        print(f"{name:<13} {s['nn1']:>6} {s['vote5']:>9} {s['nn1_under']:>6}/{s['vote5_under']:<5} "
              f"{s['nn1_no_summary']:>13} {s['widened']:>8}")
    for name in ("bm25-bigram", "bm25-word"):
        v = summary[name]["vs_embedding"]
        print(f"{name} vs embedding — 1건: {name}만 {v['nn1']['only_first']} · 임베딩만 {v['nn1']['only_second']}, "
              f"5건: {name}만 {v['vote5']['only_first']} · 임베딩만 {v['vote5']['only_second']}, "
              f"1위 사례 같음 {v['same_top1_case']}/{len(items)}, 5건 겹침 평균 {v['mean_top5_overlap']}")
    print(f"\n저장: {_display(out)}")


if __name__ == "__main__":
    asyncio.run(main())
