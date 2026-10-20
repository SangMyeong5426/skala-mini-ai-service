"""게임산업진흥에 관한 법률·시행령·시행규칙 원문을 국가법령정보센터에서 받아 조문 단위로 저장한다 — 기능 8.

    project/.venv/bin/python tools/fetch_laws.py

결과: project/data/ratings/law/articles.json — [{"key": "게임산업법 제2조", "law", "article", "title", "text"}, ...]
제도 문의에 답할 때 에이전트가 이 조문만 근거로 쓴다(MCP Resource law://game-industry/articles, 결정 0015).
법령은 저작권 보호 대상이 아니다(저작권법 제7조). 부칙과 삭제된 조문, 개정·신설 표시는 넣지 않는다.

본문은 lsInfoR.do 가 돌려주는 HTML 이다(lsInfoP.do 는 그 껍데기). 시행일(efYd)이 바뀌면 아래 표를 고친다.
"""
import html
import json
import re
import time
from datetime import datetime

import httpx
from measure_queries import ROOT, _display

OUT = ROOT / "project" / "data" / "ratings" / "law" / "articles.json"
BODY = "https://www.law.go.kr/LSW/lsInfoR.do"
HEADERS = {"User-Agent": "Mozilla/5.0"}
LAWS = [  # (짧은 이름, 법령명, lsiSeq, 시행일)
    ("게임산업법", "게임산업진흥에 관한 법률", "265811", "20251023"),
    ("게임산업법 시행령", "게임산업진흥에 관한 법률 시행령", "284663", "20260324"),
    ("게임산업법 시행규칙", "게임산업진흥에 관한 법률 시행규칙", "279203", "20251009"),
]
ARTICLE = re.compile(r"^\s*(제\d+조(?:의\d+)?)\(([^)\n]{1,60})\)", re.M)
# 개정·신설 표시 — "<개정 2007. 1. 19., 2016. 2. 3.>", "[본조신설 2016. 12. 20.]". 답의 근거가 아니고, 날짜 숫자가
# 수치 대조(지어낸 나이·금액 잡기)를 덮어 준다.
AMENDMENT = re.compile(r"<(?:개정|신설|전문개정|타법개정|본조신설|제목개정|종전)[^>]*>|\[(?:본조신설|제목개정|전문개정|종전)[^\]]*\]")
CHAPTER = re.compile(r"^\s*제\d+(?:장|절)(?:의\d+)?\s.*$", re.M)


def to_text(page: str) -> str:
    page = re.sub(r"(?s)<(script|style)[^>]*>.*?</\1>", "", page)
    text = html.unescape(re.sub(r"<[^>]+>", " ", re.sub(r"(?i)<br\s*/?>|</(p|div|li|tr)>", "\n", page)))
    text = re.sub(r"[ \t\xa0]+", " ", text)
    return re.sub(r"\n\s*\n+", "\n", text)


def split_articles(text: str, short: str, law: str) -> list[dict]:
    """조문 머리("제N조(제목)")가 줄 첫머리에 오는 곳마다 자른다. 부칙부터는 버린다."""
    body = re.split(r"\n\s*부칙\s*(?:<|\n)", text, maxsplit=1)[0]
    heads = list(ARTICLE.finditer(body))
    articles, seen = [], set()
    for head, nxt in zip(heads, [*heads[1:], None], strict=True):
        chunk = body[head.start():nxt.start() if nxt else len(body)]
        chunk = re.sub(r"\s*\n\s*", "\n", AMENDMENT.sub("", CHAPTER.sub("", chunk))).strip()
        number, title = head.group(1), head.group(2)
        if number in seen or title.startswith("삭제") or len(chunk) < len(head.group(0)) + 5:
            continue
        seen.add(number)
        articles.append({"key": f"{short} {number}", "law": law, "article": number, "title": title, "text": chunk})
    return articles


def main() -> None:
    articles = []
    with httpx.Client(headers=HEADERS, timeout=60.0) as client:
        for short, law, seq, ef in LAWS:
            resp = client.get(BODY, params={"lsiSeq": seq, "chrClsCd": "010202", "urlMode": "lsInfoP",
                                            "efYd": ef, "ancYnChk": "0"})
            resp.raise_for_status()
            found = split_articles(to_text(resp.text), short, law)
            print(f"{law} (시행 {ef}): 조문 {len(found)}개")
            articles += found
            time.sleep(0.5)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"source": "국가법령정보센터 https://www.law.go.kr",
                               "fetched_at": datetime.now().isoformat(timespec="seconds"),
                               "laws": [{"short": s, "name": n, "lsiSeq": q, "efYd": e} for s, n, q, e in LAWS],
                               "articles": articles}, ensure_ascii=False, indent=1) + "\n")
    print(f"→ {_display(OUT)} ({len(articles)}개)")


if __name__ == "__main__":
    main()
