"""게임물관리위원회 Open API로 등급분류 결과를 받아 두고, 사례 DB를 만든다 — 과제 2 데이터.

    project/.venv/bin/python tools/fetch_ratings.py fetch --start 2024-01 --end 2026-09
    project/.venv/bin/python tools/fetch_ratings.py build

fetch : 월 단위로 API(https://www.grac.or.kr/WebService/GameSearchSvc.asmx/game)를 불러
        project/data/ratings/raw/YYYY-MM.json 에 저장한다. 인증키 없이 호출되고, 하루 1,000회·한 번에
        1,000건 제한이 있다. 이미 받은 달은 건너뛴다(--force 로 다시 받는다). 에이전트는 실행 중에 API를
        부르지 않는다 — 받아 둔 파일만 읽는다(호출 제한, 시연 안정성, 측정 재현성).
build : raw 에서 사례 DB(project/data/ratings/cases.json)를 만든다. 기준은 agent/rating/data.py 에 있다
        (CASES_UNTIL 까지 · 개요 있음 · 연령 등급 · 아케이드 제외 · 취소 아님). 달마다 개요·내용정보 채움률을 찍는다.

이용 조건: 공공데이터포털 표기 "이용허락범위 제한 없음"(게임물관리위원회_게임 정보, 15120667).
"""
import argparse
import calendar
import json
import sys
import time
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime

import httpx
from measure_queries import ROOT, _display

sys.path.insert(0, str(ROOT / "project"))
from agent.rating.data import CASES_PATH, RAW_DIR, build_cases, load_raw  # noqa: E402

API_URL = "https://www.grac.or.kr/WebService/GameSearchSvc.asmx/game"
# 기본 User-Agent(python-httpx)는 기관 웹 방화벽에 막힌다. 브라우저와 같은 값을 쓴다.
HEADERS = {"User-Agent": "Mozilla/5.0"}
PAGE_SIZE = 1000


def _months(start: str, end: str) -> list[str]:
    y, m = map(int, start.split("-"))
    out = []
    while f"{y:04d}-{m:02d}" <= end:
        out.append(f"{y:04d}-{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def _text(item: ET.Element, tag: str) -> str:
    return (item.findtext(tag) or "").strip()


def parse_items(xml_text: str) -> tuple[int, list[dict]]:
    """API 응답 XML → (전체 건수, 행 목록). 행의 키는 에이전트 쪽 이름으로 바꾼다."""
    root = ET.fromstring(xml_text)
    rows = []
    for it in root.findall("item"):
        rows.append({
            "id": _text(it, "rateno"),
            "date": _text(it, "rateddate"),
            "title": _text(it, "gametitle"),
            "org": _text(it, "orgname"),
            "applicant": _text(it, "entname"),
            "summary": _text(it, "summary"),
            "rating": _text(it, "givenrate"),
            "genre": _text(it, "genre"),
            "platform": _text(it, "platform"),
            "descriptors": [d.strip() for d in _text(it, "descriptors").split(",") if d.strip()],
            "canceled": _text(it, "cancelstatus").lower() == "true",
        })
    return int(root.findtext("tcount") or 0), rows


def fetch_month(client: httpx.Client, month: str) -> list[dict]:
    y, m = map(int, month.split("-"))
    last = calendar.monthrange(y, m)[1]
    rows, page, total = [], 1, None
    while total is None or len(rows) < total:
        resp = client.get(API_URL, params={
            "op": "game", "display": PAGE_SIZE, "pageno": page,
            "startdate": f"{month}-01", "enddate": f"{month}-{last:02d}"})
        resp.raise_for_status()
        total, items = parse_items(resp.text)
        if not items:
            break
        rows += items
        page += 1
        time.sleep(0.5)   # 기관 서버에 몰아서 보내지 않는다
    # 등급거부는 번호가 비어 있다 — 날짜·제목으로 정렬해 파일 내용이 늘 같게 한다.
    return sorted(rows, key=lambda r: (r["date"], r["id"], r["title"]))


def cmd_fetch(args: argparse.Namespace) -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    with httpx.Client(headers=HEADERS, timeout=60.0) as client:
        for month in _months(args.start, args.end):
            out = RAW_DIR / f"{month}.json"
            if out.exists() and not args.force:
                print(f"{month}: 이미 있음 — 건너뜀")
                continue
            rows = fetch_month(client, month)
            out.write_text(json.dumps({
                "source": API_URL, "month": month,
                "fetched_at": datetime.now().isoformat(timespec="seconds"),
                "count": len(rows), "items": rows}, ensure_ascii=False, indent=1) + "\n")
            print(f"{month}: {len(rows)}건 → {_display(out)}")


def cmd_build(args: argparse.Namespace) -> None:
    rows = load_raw()
    by_month: dict[str, Counter] = {}
    for r in rows:
        c = by_month.setdefault(r["date"][:7], Counter())
        c["all"] += 1
        c["summary"] += bool(r["summary"])
        c["descriptors"] += bool(r["descriptors"])
    print("월        전체  개요 있음  내용정보 있음")
    for month, c in sorted(by_month.items()):
        print(f"{month}  {c['all']:5d}  {c['summary']:9d}  {c['descriptors']:13d}")
    cases = build_cases(rows)
    CASES_PATH.write_text(json.dumps(cases, ensure_ascii=False, indent=1) + "\n")
    ratings = Counter(c["rating"] for c in cases)
    print(f"\n사례 DB: {len(cases)}건 ({cases[0]['date']} ~ {cases[-1]['date']}) → {_display(CASES_PATH)}")
    print("등급별:", dict(ratings))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_fetch = sub.add_parser("fetch")
    p_fetch.add_argument("--start", default="2024-01")
    p_fetch.add_argument("--end", default="2026-09")
    p_fetch.add_argument("--force", action="store_true")
    sub.add_parser("build")
    args = parser.parse_args()
    {"fetch": cmd_fetch, "build": cmd_build}[args.cmd](args)


if __name__ == "__main__":
    main()
