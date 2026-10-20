# 진행 계획 (초안)

Google Spread에 등록하는 계획의 원본이다. 진행 중에 고칠 수 있다.
양식과 예시는 [`00-assignment.md`](00-assignment.md#진행-계획-양식).

## 과제 선택

| 항목 | 값 |
| --- | --- |
| 과제 | TBD — 1(Base AI Agent 개선/추가) 또는 2(신규 프로젝트) |
| 주제 (과제 2일 때) | TBD |
| 선택 이유 | TBD |
| Google Spread 등록 | TBD |

## 개선/추가 포인트

항목 하나가 끝나면 상태를 바꾸고, Before/After 수치를 [`02-measurement.md`](02-measurement.md)에,
결정과 한계를 [`decisions/`](decisions/)에 남긴다.

| 순번 | 영역 | 무엇을 바꾸나 | 추가 설명 | 기술 요소 | Before/After 지표 | 결정 기록 | 상태 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | TBD | TBD | TBD | TBD | TBD | — | 미착수 |

## 코드에서 확인한 사실

계획을 세울 재료다. 선택이 아니다. Base 코드(`project/`)를 읽고 **직접 확인한 것만** 적는다.

| 위치 | 현재 동작 | 연결되는 예시 영역 |
| --- | --- | --- |
| [`agent/fake_llm.py`](../project/agent/fake_llm.py) `FastLLM.route` | route 판정이 정규식 키워드(`장애·진단·다운·지연·급증·incident·티켓`)뿐이다. fake 백엔드로 회귀 쿼리 10개를 돌리면 **5번만 incident로 간다**(2026-10-20 실측). | 측정 시 주의 |
| [`agent/ollama_llm.py`](../project/agent/ollama_llm.py) · [`openai_llm.py`](../project/agent/openai_llm.py) `route` | LLM이 JSON으로 분류하고, JSON이 깨지면 위 정규식으로 폴백한다. | 하드코딩 |
| [`agent/graph.py`](../project/agent/graph.py) `_classify_incident_type` | 모니터링 status·alerts 문자열에서 키워드로 incident_type(runbook)을 고르고, 안 맞으면 `db-down`으로 폴백한다. | RAG, 데이터 보강 |
| [`agent/graph.py`](../project/agent/graph.py) `_extract_system_name` | 시스템명이 없으면 `auth-service`로 폴백한다. | 하드코딩 |
| [`agent/graph.py`](../project/agent/graph.py) `research_node` | 노드 하나가 모니터링 Tool과 runbook Resource를 병렬로 부른다. | Multi-Agent |
| [`agent/graph.py`](../project/agent/graph.py) | 노드 10개와 라우팅 함수가 한 파일(338줄)에 있다. | 모듈화 |
| [`agent/ollama_llm.py`](../project/agent/ollama_llm.py) · [`openai_llm.py`](../project/agent/openai_llm.py) `chat` | chat 경로는 이력의 **마지막 10개 메시지**만 프롬프트에 넣는다. incident 경로는 이력을 쓰지 않는다. | 메모리 |
| [`agent/mcp_client.py`](../project/agent/mcp_client.py) `call_tool` | 프로세스 첫 `get_monitoring_status` 호출을 일부러 한 번 실패시킨다(재시도 데모). | 측정 시 주의 |
| 테스트 | 원본에는 테스트가 없다. 이 저장소 세팅에서 스모크 테스트 6개를 더했다([`project/tests/`](../project/tests/)). | 단위 테스트 |
| 평가 | 안내 자료가 언급한 `eval/run_eval.py`는 학생 배포본에 없다. | 평가 |
