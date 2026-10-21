# 발표·코드 학습 가이드 — 과제 2 (게임 등급분류 사전 점검)

과제 안내 자료의 요구에 맞춰 **무엇을 발표하고, 코드를 어떻게 설명할지**를 공부하는 문서다.
과제 안내는 두 가지를 분명히 요구한다.

- 발표는 **문제 → 개선/추가 포인트 → Before/After 수치 → 한계 및 추가 개선** 순서로 한다(평가 "발표 PPT 작성 및 발표" 20점).
- AI 도구를 써도 되지만 **작성된 코드와 내용을 직접 설명할 수 있어야 한다.**

다른 문서와의 역할은 이렇다.

| 문서 | 역할 |
| --- | --- |
| **이 문서** | 공부용 — 장표 구성안, 코드를 따라 읽는 순서, 외울 숫자, 자기 점검 문제 |
| [`05-presentation-notes.md`](05-presentation-notes.md) | 발표 준비 노트 — 쉬운 용어 풀이, 기능별 설명, 시연 순서, 예상 질문 |
| [`04-report.md`](04-report.md) | 제출용 결과 보고서 |
| [`02-measurement.md`](02-measurement.md) · [`decisions/`](decisions/) | 수치 원본 · 기능마다 "왜"의 원본 |

---

## 0. 발표·보고서에서 요구하는 것

**발표 방법** — 1인 **5분**, 앉은 자리에서 Zoom. 앞 **2분**은 주제와 세부 task, 그리고 결과. 뒤 **3분**은 새로 작성한 코드에서 **Agent Graph 구성과 MCP·RAG 관련 코드**를 설명한다.
1시 10분부터 6조 → 5조 → … → 1조 순서.

**보고서 작성 방법** — ① 진행 사항 소개(과제 2: 주제와 주요 task, **맨 앞에 번호와 성함**) ② 사용한 기술 요소(Multi-Agent·MCP·RAG·의존성 주입·LangSmith·모듈화·단위 테스트)와
**구현 기능 화면 캡처·최종 실행 화면 캡처** ③ 선택 사항: 같은 입력의 Before/After 수치(**화면 캡처 필수**) ④ 느낀점 또는 이후 개선 포인트.
→ [`04-report.md`](04-report.md)가 이 순서와 캡처를 모두 담았다(`docs/images/`).

| 평가 항목 (배점) | 이 프로젝트에서 보여 줄 것 | 발표 장 |
| --- | --- | --- |
| 기능 구현 완성도 (30) | 실제 실행 화면(판정 과정·근거), 테스트 122개 통과 — 화면 캡처는 보고서에 | 4 |
| Before/After 실측 비교 (10, 보너스) | 같은 커밋에서 스위치만 바꾼 LLM 단독 vs 에이전트 — 같은 질문의 실행 화면은 보고서 3-2 | 5 |
| 기술 요소 (30) | Agent Graph · MCP · RAG 코드, 의존성 주입(partial), Multi-Agent 를 뺀 이유 | 4·7·8·9 |
| 한계·트레이드오프 (20) | 짧은 설명의 정확도, 과소↔과대평가, 느림(임베딩·LLM), 재조사·재작성 횟수 제한 | 6 |
| 발표 (20) | 5분 안에 2분 + 3분, 게임을 모르는 청중에게 제도와 문제부터 | 전체 (2·3장) |

---

## 1. 발표 덱 — 10장, 5분

덱 파일: `presentation/game-rating-deck.pptx`(Google Slides 로 가져오기 가능). **장마다 발표자 노트에 시간 표시가 붙은 대본**이 있고, 2~9장 왼쪽 위에는 아래 표의 장 이름이 붙어 있다(코드 장은 "코드 1 · Agent Graph"처럼). 아래는 요약이다.

| 장 | 시간 | 넣은 것 | 말할 것 (요약) |
| --- | --- | --- | --- |
| 1. 표지 | 0:00~0:08 | 제목, G080 박상명 | 과제 2, 출시 전 등급을 미리 점검하는 에이전트 |
| 2. 제도 | 0:08~0:25 | 4개 등급, 출시 전 의무·처벌, 심의 방식 3단계, 기준 문구 | 위원회에서 연구원 보고서를 보고 위원 9명이 다수결로 정한다. 모바일은 앱마켓이 먼저 매기고 위원회가 다시 본다. 기준 문구가 추상적이다 |
| 3. Pain Point | 0:25~0:55 | 어려움 3가지(같은 게임도 등급이 바뀜 · 비슷한 게임인데 판단이 다름 · 왜 그 등급인지 알기 어려움), 잘못 예상했을 때의 손해, LLM 의 지어낸 답 | 「블루 아카이브」 상향과 민원 2만2천 건, 같은 시리즈인데 갈린 판단과 위원장 발언, 결정 3,190건에 이유가 없고 결정서는 167건뿐. 낮게 보면 출시 직전 계획 변경, LLM 은 "청불은 14세"처럼 지어냄 |
| 4. 주제와 세부 task | 0:55~1:20 | 하는 일, task 6개, 실제 실행 화면 | 실제 결정·기준표·법령을 근거로 판정. 멀티에이전트는 얻을 게 없어 뺐다 |
| 5. 결과 | 1:20~1:45 | Before/After 막대, 과소평가 25→15, 느려짐, OpenAI 에서도 유지 | 같은 LLM·같은 질문, 스위치만 바꿔 측정 |
| 6. 한계와 다음 단계 | 1:45~2:00 | 부족한 점 3개, 다음 단계 3개 | 짧은 설명은 절반 정도, 높게 보는 실수 증가, 느림 → 근거가 확실한 사례만, 설명 길이에 맞춘 판단 |
| 7. Agent Graph | 2:00~3:00 | 노드 10개 그림, `build_rating_graph` 코드 | 갈림길 5곳(`add_conditional_edges` 5줄), 되돌아가는 길은 최대 2번·3번, `partial` 로 의존성 주입 |
| 8. MCP | 3:00~4:00 | 서버 Tool 1·Resource 4, 서버 코드·에이전트 코드 | `@mcp.tool`/`@mcp.resource` 로 등록, 에이전트는 `find_tool` → `call_tool` |
| 9. RAG | 4:00~5:00 | 사례 검색 코드(임베딩·코사인 상위 5), 법령 근거 검사 코드 | 찾은 자료만 보고 판단, 등급은 코드가 최댓값으로 |
| 10. 마무리 | — | 감사합니다, GitHub | 질문 받기 |

3장의 논란과 출처는 [`04-report.md`](04-report.md) 1-1(링크 표)과 [`05-presentation-notes.md`](05-presentation-notes.md) 0-1에 있다.
질문이 오면 쓸 자료(시연 화면, 같은 질문의 Before/After 화면, 사례 5건 다수결 비교, OpenAI 비교, 데이터 쏠림)는 덱에 넣지 않고 [`04-report.md`](04-report.md)에 있다.

연습 팁: 앞 여섯 장을 2분 안에 끝내야 코드 3분이 확보된다(2·3장 합쳐 47초). 3장은 오른쪽 설명을 다 읽지 말고 왼쪽 제목 세 줄("바뀐다 → 다르다 → 이유가 안 보인다")을 말한 뒤 숫자 하나씩만 붙인다.
코드 장은 "그림 → 코드 한 줄씩 짚기 → 왜 이렇게 했나" 순서로 말한다.

### 1-1. 게임을 모르는 청중에게 쓸 쉬운 말

| 처음 나올 때 | 이렇게 풀어 말한다 |
| --- | --- |
| 등급분류 | 게임의 "몇 세 이용가"를 정하는 심사 — 영화 관람등급과 같은 제도 |
| 게임물관리위원회 | 게임 등급을 정하는 공공기관 — 영화의 영상물등급위원회와 비슷한 역할 |
| 자체등급분류 | 정부가 지정한 사업자(큰 앱 마켓 등)가 직접 등급을 매기는 방식 |
| 사후관리 · 등급 재분류 권고 | 앱 마켓이 매긴 등급을 위원회가 나중에 다시 보고 바꾸라고 하는 것 — 「블루 아카이브」 논란이 여기서 나왔다 |
| 국민감사 청구 | 국민 300명 이상이 서명해 감사원에 공공기관 감사를 요구하는 제도 |
| 간소화 등급분류 | 신청자가 온라인 시스템에 내용과 등급을 직접 입력하는 간단한 절차 — 청소년이용불가 게임은 쓸 수 없다(제21조의10) |
| 내용정보 | 등급 옆에 붙는 표시 — "폭력성", "선정성"처럼 왜 그 등급인지 알려 준다 |
| 사행성 | 도박을 흉내 낸 요소(슬롯머신, 룰렛 등) |
| 플랫폼 · 장르 | 어디서 하는 게임인지(PC · 모바일 · 콘솔) · 어떤 종류의 게임인지(퍼즐 · 액션 · 롤플레잉 등) |
| 과소평가 · 과대평가 | 실제 등급보다 낮게 예상 · 높게 예상 |

---

## 2. 코드 따라 읽기 — 요청 하나가 지나가는 길

코드를 설명할 때는 **"요청이 들어와서 답이 나갈 때까지"** 순서로 따라가면 막히지 않는다. 각 단계마다 위치 · 하는 일 · 왜 · 질문받으면.

### 2-1. 서버가 켜질 때 — 부품 조립 (의존성 주입 · 스위치)

위치: [`server.py` `_build_rating_components`](../project/server.py#L197), [`agent/deps.py` `SupervisorDeps`](../project/agent/deps.py#L15)

```python
if switches["CASE_SEARCH"] == "semantic":   # 기능 3 — 사례 DB 는 MCP Resource 로 받는다
    cases_server = await mcp.find_resource("ratings://cases")
    cases = json.loads(await mcp.read_resource("ratings://cases", server=cases_server))
    parts["case_retriever"] = await CaseRetriever.create(parts["embedder"], cases)
if switches["RATING_ASSESSOR"] == "criteria":
    parts["assessor"] = CriteriaAssessor(quality_llm)
```

- 하는 일: 스위치 6개(`ROUTER`·`RATING_CLARIFY`·`CASE_SEARCH`·`RATING_ASSESSOR`·`VALIDATOR`·`CHAT_GROUNDING`)를 읽어 켜진 부품만 만들고 `SupervisorDeps` 에 넣는다.
- 왜: 부품 칸이 비어 있으면(`None`) 각 단계가 LLM 단독으로 동작한다. 그래서 **같은 프로그램에서 스위치만 바꿔 Before/After 를 잴 수 있다.**
- 질문받으면: "의존성 주입이 뭔가요?" → "단계가 필요한 부품을 스스로 만들지 않고 밖에서 넣어 받는 구조입니다. 그래서 부품을 빼거나 테스트용 가짜로 바꾸기 쉽습니다."

### 2-2. 그래프 — 노드와 연결, 무한 루프 방지

위치: [`agent/rating/graph.py` `build_rating_graph`](../project/agent/rating/graph.py#L282)

```python
g.add_conditional_edges("route", _after_route, {"chat_answer": "chat_answer", "plan": "plan"})
g.add_conditional_edges("plan", _after_plan, {"clarify": "clarify", "research": "research"})
g.add_edge("research", "replan_check")
g.add_conditional_edges("replan_check", _after_replan_check, {"analysis": "analysis", "research": "research"})
g.add_conditional_edges("analysis", _after_analysis, {"clarify": "clarify", "write": "write"})
g.add_edge("write", "validate")
g.add_conditional_edges("validate", _after_validate, {"finalize": "finalize", "write": "write"})
```

- 하는 일: LangGraph 순서도. 노드 이름은 Base 와 같게 둬서 화면·측정 도구를 그대로 쓴다.
- 루프는 두 곳이고 둘 다 상한이 있다.
  - research ↔ replan_check: 사례가 3건(`MIN_CASES`)보다 적으면 범위를 넓힌다. 넓힐 곳이 `WIDER = {"genre+platform": "platform", "platform": "all"}` 뿐이라 최대 두 번이면 끝난다.
  - write ↔ validate: `MAX_ATTEMPTS = 3` — 세 번째도 떨어지면 경고를 붙여 내보낸다.
- 질문받으면: "그래프가 무한 루프에 빠질 수 없나요?" → 위 두 상한.

### 2-3. 질문 분류 — 과제 1 의미 라우터 다시 쓰기 (RAG)

위치: [`agent/router.py` `SemanticRouter`](../project/agent/router.py#L57), 예시 문장 `project/data/ratings/router_examples.json`(대화 15 · 점검 15)

- 하는 일: 질문을 임베딩해 예시 문장들과의 비슷한 정도를 비교한다. 두 분류의 차이가 0.04 보다 작으면 애매하다고 보고 작은 LLM 에 넘긴다.
- 왜: 작은 LLM(0.6b) 혼자서는 점검 요청을 모두 대화로 보냈다(15/30). 라우터는 과제 1 코드를 고치지 않고 **라벨 이름만 인자로** 바꿔 다시 썼다.
- 질문받으면: "0.04 는 어떻게 정했나요?" → "평가셋이 아니라 예시 문장으로 정했습니다(결정 0013)."

### 2-4. 조사 — MCP 와 유사 사례 검색 (MCP · RAG)

위치: [`mcp_server_rating.py`](../project/mcp_server_rating.py#L35), [`agent/rating/cases.py` `search`](../project/agent/rating/cases.py#L105)

```python
[query_vec] = await self.embedder.embed([text])
ranked = sorted(((cosine(query_vec, self.vectors[i]), i) for i in candidates), reverse=True)[:self.k]
```

- 하는 일: MCP 서버가 Tool 1개(`rating_stats` — 같은 장르·플랫폼 등급 분포)와 Resource 4개(기준표·시행규칙 제8조·법령 조문·사례 DB)를 내준다.
  사례 검색은 사례 1,751건을 미리 임베딩해 두고(파일 캐시), 질문과 코사인 유사도가 높은 5건을 고른다.
- 왜 MCP: Base 방식 그대로 — 에이전트가 "어느 서버에 무슨 도구가 있는지" 가정하지 않고 `find_tool`·`find_resource` 로 찾아 쓴다. 자료를 바꿔도 에이전트 코드는 그대로다.
- 질문받으면: "Tool 과 Resource 차이는?" → "Tool 은 인자를 받아 계산해 주는 기능(통계), Resource 는 읽기만 하는 자료(기준표·법령·사례)입니다."

### 2-5. 판정 — LLM 은 항목만, 등급은 코드가 (핵심)

위치: [`agent/rating/assess.py`](../project/agent/rating/assess.py#L33)

```python
def rating_from_items(items: dict) -> str:
    """해당 항목 단계의 최댓값 → 등급. 해당 항목이 없으면 전체이용가."""
    return RATINGS[max((item["level"] for item in items.values() if item["present"]), default=0)]
```

```python
nn1 = case_ratings[0]                                   # 가장 비슷한 사례의 등급
higher = max(items_rating, nn1, key=RATINGS.index)      # R1 case-floor: 둘 중 높은 쪽
```

- 하는 일
  1. LLM(8b)이 7개 항목마다 `{있다/없다, 단계 0~3, 근거}`를 JSON 으로 낸다.
  2. `quote_found` 가 근거 구절이 정말 설명에 있는지(그대로 또는 2글자 조각 80% 이상) 확인하고, 근거 없는 항목은 지운다.
  3. `rating_from_items` 가 단계 최댓값으로 등급을 정한다.
  4. `combine` 이 결합 규칙 R1 로 "가장 비슷한 실제 사례의 등급"을 하한으로 쓴다.
- 왜: LLM 에게 등급을 바로 물으면 등급과 근거가 어긋났다. 계산을 코드로 옮기면 **보고서의 등급과 근거가 늘 맞는다.**
  R1 은 과소평가(더 위험한 오류)를 줄이려고, 결과를 보기 전에 적은 후보 5개 중 개발용 문항으로 골랐다.
- 질문받으면: "왜 평균이 아니라 최댓값인가요?" → "사례집 요약표에서 항목마다 4단계가 곧 전체·12·15·청불에 대응합니다. 폭력성 하나가 청불 수준이면
  나머지가 전체이용가 수준이어도 그 게임은 청불 기준에 해당하니 가장 높은 단계가 등급이 됩니다. 다만 실제 위원회는 주제·맥락까지 보므로
  이것은 요약 규칙이고, 한계로 밝혔습니다(결정 0011)."

### 2-6. 검수 — 싼 검사부터, 뜻은 마지막에 LLM 이

위치: [`agent/rating/check.py` `check`](../project/agent/rating/check.py#L93)

| 단계 | 누가 | 보는 것 |
| --- | --- | --- |
| format | 코드 | 30자 이상, "예상 등급:" 줄 |
| rating | 코드 | 보고서의 등급 = 코드가 계산한 등급 |
| cases | 코드 | 「제목」(등급)으로 든 사례가 찾아온 사례이고 등급이 맞는가 |
| numbers | 코드 | 숫자가 통계·사례·설명에 있는가 |
| judge | LLM | 질문한 그 게임 이야기인가, 판정과 맞는가 |

- 왜: 숫자·제목 대조처럼 정답이 정해진 일은 코드가 싸고 정확하다. 앞에서 떨어지면 LLM 판정을 부르지 않는다.
- 에피소드: 처음엔 보고서 6개 중 3개가 경고로 나갔다 — AI 가 사례 번호와 사례 개요의 숫자("블럭 3개")를 옮겨 써서 숫자 검사에 걸렸다. **검사 규칙은 실제 답을 보고 다듬어야 한다.**
- 질문받으면: "LLM-as-judge 가 틀리면?" → "그래서 코드 검사를 앞에 두었습니다. 그래도 놓친 경우가 있고(법령 답변 1건), 한계로 밝혔습니다."

### 2-7. 제도 문의 — 근거 없으면 답하지 않는다

위치: [`agent/rating/law.py` `answer`](../project/agent/rating/law.py#L77)

```python
if not raw.get("answerable") or not str(raw.get("answer", "")).strip():
    reason = "법령에서 답을 찾지 못했습니다"
elif not citations:
    reason = "근거 조문을 밝히지 않았습니다"
elif any(c not in by_key for c in citations):
    reason = "검색하지 않은 조문을 인용했습니다(...)"
else:   # 숫자가 인용 조문에 있는가 → LLM 이 조문 원문과 대조
```

- 하는 일: 조문 148개 중 비슷한 4개를 찾아 그것만 보고 답하게 하고, 네 가지 검사 중 하나라도 걸리면 "답할 수 없습니다" + 찾아본 조문을 보여 준다. 답 끝의 근거 목록은 코드가 붙인다.
- 왜: LLM 단독은 "청소년이용불가는 14세 이상"을 지어냈다. 친절함을 조금 포기하고 **틀린 안내를 막는 쪽**을 택했다.

### 2-8. OpenAI 연결 — 보내는 곳만 바꾸기

위치: [`agent/rating/llm.py` `OpenAITransport`](../project/agent/rating/llm.py#L238)

```python
class OpenAIRatingQualityLLM(OpenAITransport, OllamaRatingQualityLLM):
    """판정·보고서 작성·검수·법령 답변 — 기본 gpt-4o."""
```

- 하는 일: qwen 용 클래스를 물려받고 요청을 보내는 두 메서드(`_chat`, `_chat_stream`)만 OpenAI 로 바꿨다. 프롬프트·JSON 스키마·파싱은 그대로다.
- 왜: 프롬프트가 두 벌이면 판정 규칙이 모델마다 달라진다. 측정은 qwen 으로 했고 OpenAI 는 시연·보조 측정용이다(결정 0018).

### 2-9. 테스트와 측정

- 단위·스모크 테스트 122개(과제 2 파일 8개, 56개). 진짜 AI 없이 가짜 LLM·가짜 임베더로 돈다 — 예: 근거 없는 항목은 지워지는가, 스위치를 끄면 LLM 단독이 되는가, OpenAI 요청 모양은 맞는가.
- 측정은 `scripts/measure-at <커밋> <이름>` — 잴 커밋을 따로 꺼내 그 코드로 평가셋을 돌린다. 원자료는 `runs/` 에 남고 손으로 고치지 않는다.
- 질문받으면: "평가셋을 보고 맞춘 것 아닌가요?" → "평가셋은 기능 코드보다 먼저 커밋했고(`4e3a976`), 규칙은 개발용 문항으로만 골랐습니다."

---

## 3. 기술 요소 지도 (평가 30점)

| 기술 요소 | 어디에 | 한 줄 설명 |
| --- | --- | --- |
| Multi-Agent | — (검토 후 제외, 결정 0009) | 등급 = 가장 높은 항목 하나라 나눠 심사해도 이득이 없고 과대평가·지연(약 7배 추정)만 커진다 |
| MCP | [`mcp_server_rating.py`](../project/mcp_server_rating.py), [`agent/mcp_client.py` `find_tool`](../project/agent/mcp_client.py#L91) | Tool 1(통계) + Resource 4(기준표·시행규칙·법령·사례). 서버를 찾아서 쓴다 |
| RAG | `agent/rating/cases.py`(사례), `agent/rating/law.py`(조문), `agent/router.py`(분류 예시) | 임베딩 검색으로 찾은 자료만 보고 판단·답변 |
| 의존성 주입 | `agent/deps.py`, `server._build_rating_components`, 노드에 `partial(fn, deps=deps)` | 부품을 밖에서 넣고, 비면 LLM 단독 |
| LangSmith | `@traceable` 30곳(등급 모듈) | 노드·LLM 호출마다 추적 기록 |
| 모듈화 | `agent/rating/` 10개 모듈(graph·llm·assess·cases·check·law·clarify·profile·facts·data) | 도메인 분리 — `AGENT_DOMAIN=incident` 면 과제 1 그대로 |
| 단위 테스트 | `project/tests/test_rating_*.py` 8개 파일 · 전체 122개 | 가짜 LLM·임베더로 결정론적으로 |
| 평가(LLM-as-judge) | `agent/rating/check.py`, `law.py` 의 `judge_law` | 코드 검사 뒤 뜻만 LLM 이 |

---

## 4. 외울 숫자 카드

| 무엇 | 숫자 |
| --- | --- |
| 제도 논란 | 민원 약 3주 2만2천 건(평소 1년 2천 건 안팎) · 국민감사 청구 5,489명 · 감사원 지적 7억 원 이상 낭비 · 등급위원 9명 다수결 |
| 사유 공개 | Open API 결정 3,190건에 사유 칸 없음 · 사유가 담긴 결정서 파일 167건(2026년 2분기) |
| 데이터 | 위원회 결정 3,190건 (2024-01~2026-09) · 사례 DB 1,751건 · 법령 148개 조문 |
| 등급 정확도 A (한 문장, 40) | LLM 단독 14 → 에이전트 **19** (사례 5건 다수결 22) |
| 등급 정확도 B (상세, 39) | 24 → **27** (기준표만 28) |
| 과소평가 A · B | 25 → 15 · 11 → 2 |
| 분류 · 되묻기 | 15 → 29 / 30 · 6 → 10 / 12 |
| 검수 | 오염 0 → 7 / 7, 정상 오탐 0 / 5 |
| 제도 문의 | 2 → 15 / 17 |
| 데이터 쏠림 | 모바일 사례 청불 77% → 35% |
| 지연 · 비용 | 판정 4.7 → 16초, 회귀 쿼리 11턴 13.6 → 319초(3회 중앙값), 가상 비용 $0.065 → $0.303 (A 40문항) |
| OpenAI 보조 상승폭 | A +2 · B +6 · 분류 −1 · 제도 문의 +13 · 평범한 게임 −4 |

---

## 5. 자기 점검 문제

답을 가리고 소리 내어 답해 본 뒤 펼쳐 확인한다.

<details><summary>0-1. 게임 등급분류 제도를 게임을 모르는 사람에게 한 문장으로 설명해 보세요.</summary>

"영화의 관람등급처럼 게임에도 전체이용가·12세·15세·청소년이용불가 등급이 있고, 한국에서 게임을 팔려면 출시 전에 게임물관리위원회(또는 지정 사업자)에서 반드시 받아야 합니다."
근거: 게임산업법 제21조(등급분류·4등급), 제16조(위원회), 제32조·제44조(안 받고 유통하면 금지·처벌).
</details>

<details><summary>0-2. 왜 출시 전에 등급을 미리 알아야 하나요? 그리고 왜 미리 알기 어렵나요?</summary>

등급에 따라 누구에게 팔고 어떻게 광고할지가 달라지고, 결과가 예상보다 높으면 내용을 고치거나 대상을 바꿔야 한다(「블루 아카이브」는 서비스 중에 등급이 올라 청소년용 버전을 따로 냈다).
그런데 기준 문구("유해한 표현이 없는", "사실적으로 표현된")가 추상적이고, 판단 재료(실제 결정·기준표·법령)는 흩어져 있으며, 사유까지 공개된 결정은 일부다.
</details>

<details><summary>0-3. 이 제도의 페인 포인트를 근거와 함께 말해 보세요.</summary>

결과를 미리 알기 어렵고, 왜 그렇게 정했는지 밖에서 확인하기도 어렵다. 덱 3장의 세 줄 순서로 말한다.
① 같은 게임도 서비스 중에 등급이 바뀐다 — 15세이던 「블루 아카이브」에 청소년이용불가 상향 권고(2022), 개발사는 청소년용 버전을 따로 냈고 약 3주에 민원 2만2천 건.
② 비슷한 게임인데 판단이 다르다 — 같은 시리즈 전작은 통과, 후속작은 거부(2024 공개 회의록). 위원장도 객관적이냐는 질문에 "그렇다고 답은 못하겠다"(2022-11).
③ 왜 그 등급인지 알기 어렵다 — Open API 결정 3,190건에 사유 칸이 없고, 사유가 담긴 결정서는 167건(2026년 2분기)만 받을 수 있었다.
덱에는 없지만 질문이 오면: 이용자 5,489명 국민감사 청구(2022), 감사원의 관리 시스템 사업 비위 지적(2023), 기준이 모호하다는 헌법소원(2024 국정감사).
출처는 [`04-report.md`](04-report.md) 1-1.
</details>

<details><summary>0-4. "그럼 위원회가 틀렸다는 건가요?"라고 물으면?</summary>

아니다. 객관적인지 **밖에서 확인하기 어렵다**는 것이다. 에이전트는 심의를 대신하지 않고, 실제 결정·기준표·법령을 근거와 함께 보여 줘 미리 가늠하게 돕는다.
정답이 위원회 결정이라 일관되지 않은 판단도 그대로 들어온다는 점은 한계로 인정한다.
</details>

<details><summary>1. 이 에이전트에서 LLM 이 하는 일과 코드가 하는 일을 나눠 말해 보세요.</summary>

LLM: 질문이 애매할 때 분류, 7항목의 단계와 근거 판단, 보고서 작성, 검수의 뜻 판정, 법령 답변.
코드: 근거 구절 확인, 등급 계산(단계 최댓값 + 사례 하한), 사례·숫자 대조, 법령 인용 검사, 되묻기 규칙.
</details>

<details><summary>2. Before 와 After 는 무엇이 다르고, 왜 공정한 비교인가요?</summary>

같은 프로그램·같은 모델·같은 입력에서 에이전트 부품 스위치만 끈 것이 Before(LLM 단독), 켠 것이 After 다.
같은 커밋에서 쟀으므로 차이는 에이전트 구조 때문이라고 말할 수 있다.
</details>

<details><summary>3. 등급을 왜 "가장 높은 단계"로 정하나요?</summary>

사례집 요약표의 4단계가 곧 연령 등급이라, 한 항목이라도 청불 수준이면 그 게임은 청불 기준에 해당한다. 평균을 내면 청불 수준의 폭력이 다른 항목에 묻힌다.
다만 실제 심의는 맥락까지 보므로 요약 규칙이다(결정 0011 한계).
</details>

<details><summary>4. 결합 규칙 R1 은 무엇이고, 어떻게 골랐나요?</summary>

기준표 판정과 가장 비슷한 실제 사례의 등급 중 높은 쪽을 쓰는 규칙. 후보 5개와 고르는 기준(정확도 → 과소평가 적음 → 단순함)을
결과 전에 커밋하고, 평가셋과 겹치지 않는 개발용 38문항으로 골랐다(18/38, 지금 방식 14).
</details>

<details><summary>5. R1 의 대가는?</summary>

과대평가가 늘었다 — 평가셋 B 4 → 10, 평범한 요리 경영 게임을 청불로(가장 비슷한 사례가 선정성 때문에 청불). 과소평가가 더 위험해서 감수했다.
</details>

<details><summary>6. 데이터 쏠림의 원인과 수정, 그리고 부작용은?</summary>

"개요 있음" 필터가 간소화 등급분류(제21조의10, 청불 제외) 결정을 지워 모바일 사례의 77%가 청불이 됐다. 개요 없는 결정도 넣어 35%로 고쳤다.
부작용: 개요 없는 사례가 제목·장르·플랫폼만으로 "가장 비슷한 사례"로 뽑혀 평가셋 A 가 22 → 19 로 내려갔다.
</details>

<details><summary>7. MCP 에서 Tool 과 Resource 를 하나씩 예로 들어 보세요.</summary>

Tool: `rating_stats(genre, platform)` — 같은 장르·플랫폼의 등급 분포를 계산해 준다. Resource: `criteria://descriptors`(기준표), `law://game-industry/articles`(법령 조문) 등 읽기 전용 자료.
</details>

<details><summary>8. 그래프가 무한 루프에 빠지지 않는 이유는?</summary>

재조사는 범위를 장르+플랫폼 → 플랫폼 → 전체로만 넓혀 최대 두 번, 재작성은 `MAX_ATTEMPTS = 3` 으로 끝난다.
</details>

<details><summary>9. 제도 문의에서 "답할 수 없음"이 나오는 조건 네 가지는?</summary>

① 모델이 답할 수 없다고 하거나 답이 비었다 ② 근거 조문을 밝히지 않았다 ③ 검색하지 않은 조문을 인용했다 ④ 답의 숫자가 인용 조문에 없거나, LLM 대조에서 조문과 맞지 않는다고 나왔다.
</details>

<details><summary>10. 에이전트가 단순한 방법보다 못한 경우는?</summary>

한 문장 설명에서는 비슷한 사례 5건의 다수결(22/40)이 에이전트(19/40)보다 높다. 평범한 게임에서는 LLM 단독이 하나 더 맞혔다(9 vs 8).
</details>

<details><summary>11. 더 강한 모델(OpenAI)이면 에이전트가 필요 없나요?</summary>

분류처럼 단순한 보조의 이득은 사라졌지만(30/30 → 29/30), 근거·검증 구조(제도 문의 +13)와 기준표 판정(상세 설명 +6)의 이득은 남았다.
다만 되묻기 조건이 qwen 기준이라 gpt-4o 에서는 평범한 게임도 되물었다(10 → 6).
</details>

<details><summary>12. 평가셋을 보고 결과를 맞춘 것 아닌가요?</summary>

평가셋은 기능 코드보다 먼저 커밋했고, 판정 기준(라우터 0.04)은 예시 문장으로, 결합 규칙은 개발용 문항으로 골랐다. 데이터 수정 뒤 평가셋을 두 번째로 본 것은 한계로 밝혔다.
</details>

<details><summary>13. Multi-Agent 를 왜 넣지 않았나요?</summary>

항목별 심사 에이전트 7개로 나눠도 등급은 최댓값 하나로 정해져 정보가 늘지 않는다. 판정을 7번 따로 하면 그중 하나라도 높게 볼 확률이 커져 과대평가가 늘고,
로컬 모델은 요청을 하나씩 처리해 지연이 약 7배가 된다(추정). 정답 데이터에 항목별 단계가 없어 효과를 잴 수도 없다.
</details>

<details><summary>14. 임베딩을 도입해서 생긴 비용은?</summary>

기동 때 사례 1,751건·조문 148개·예시 문장을 임베딩한다(파일 캐시로 두 번째부터 빠름). 임베딩 모델용 Ollama 가 늘 떠 있어야 하고, OpenAI 로 띄워도 필요하다.
</details>

<details><summary>15. 보고서 검수에서 코드 검사를 LLM 판정보다 앞에 둔 이유는?</summary>

등급·사례 제목·숫자 대조는 정답이 정해진 일이라 코드가 싸고 정확하다. 앞에서 떨어지면 LLM 판정 호출을 아낀다.
</details>
