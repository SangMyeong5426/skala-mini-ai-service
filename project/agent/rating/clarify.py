"""기능 6 — 정보가 모자라면 등급을 찍지 않고 되묻는다.

두 번 본다.
  ① 판정 전(plan_node): 설명이 MIN_CHARS 글자(띄어쓰기 뺀)보다 짧으면 LLM 을 부르지 않고 바로 되묻는다.
     "등급 예상해 줘", "우리 게임 몇 세야?"처럼 요청 문구뿐인 경우다.
  ② 판정 후(analysis_node): 판정 LLM 이 described=false(무엇을 하는 게임인지 알 수 없음)라고 하면 되묻는다.
     "저희 회사 신작 PC 게임이 심의를 받으면…"처럼 길어도 내용이 없는 질문은 ②가 잡는다.
②는 판정 부품(RATING_ASSESSOR=criteria)이 켜져 있을 때만 있다 — LLM 단독은 described 를 내지 않는다.
다음 턴의 보충 설명은 되묻기 직전의 질문과 이어 붙여 판정한다(profile.description_with_history).
"""
import re

# 요청 문구 한 문장("우리 게임 몇 세 등급 받을까요?" — 띄어쓰기 빼고 13자)은 걸리고, 짧아도 내용이 있는 설명
# ("고양이가 상자에 숨어 생선을 모으는 퍼즐" — 18자)은 지나가는 길이. 짧은 쪽에서 ①이 잡지 못한 것은 ②가 본다.
MIN_CHARS = 15


class ClarifyRule:
    def __init__(self, min_chars: int = MIN_CHARS):
        self.min_chars = min_chars

    def check(self, description: str) -> str | None:
        """되물을 이유. 되묻지 않으면 None."""
        if len(re.sub(r"\s+", "", description)) < self.min_chars:
            return "판정할 게임 설명이 없습니다"
        return None
