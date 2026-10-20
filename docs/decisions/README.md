# 결정 기록

되돌리기 어렵거나, 발표에서 "왜 이렇게 했나"를 물을 만한 결정을 하나에 한 파일로 남긴다.
개선 항목마다 하나씩 쓰는 것이 기본이다 — 평가 기준 "한계·트레이드오프 설명(20점)"의
근거가 각 파일의 해당 절이다.

새 결정은 [`template.md`](template.md)를 복사해 다음 번호로 만든다.

| 번호 | 제목 | 상태 | 날짜 |
| --- | --- | --- | --- |
| [0001](0001-repository-layout-and-tooling.md) | 저장소 구조와 개발 도구 | Accepted | 2026-10-20 |
| [0002](0002-ollama-think-control.md) | Ollama thinking 출력 제어 (항목 1) | Accepted | 2026-10-20 |
| [0003](0003-semantic-router.md) | 질문 분류를 임베딩 기반 의미 라우터로 (항목 2) | Accepted | 2026-10-20 |
| [0004](0004-target-resolver.md) | 대상 시스템 추정과 되묻기 (항목 3) | Accepted | 2026-10-20 |
| [0005](0005-grounded-validator.md) | 검수에 수치 대조와 LLM-as-judge (항목 4) | Accepted | 2026-10-20 |
| [0006](0006-runbook-selector.md) | runbook 선택을 의미 검색으로 (선택 항목 5) | Accepted — 효과 불확실 | 2026-10-20 |
| [0007](0007-chat-keeps-thinking.md) | 대화 경로만 thinking 유지 (항목 1 보완) | Accepted | 2026-10-20 |
| [0008](0008-smaller-models-rejected.md) | 작성·검수를 작은 모델로 바꾸는 시도 | **Rejected** — 기준 미달 | 2026-10-20 |
| [0009](0009-rating-domain.md) | 과제 2 — 등급 점검 도메인을 새 패키지로, LLM 단독을 Before로 (항목 7 제외) | Accepted | 2026-10-20 |
| [0010](0010-rating-data-and-evalsets.md) | 등급분류 데이터 — 공개 API, 기간 분할, 사행성 게임물 제외, 평가셋을 먼저 | Accepted | 2026-10-20 |
| [0011](0011-case-search-and-item-levels.md) | 유사 사례 검색 + 항목별 단계 판정 — 등급은 코드가 최댓값으로, 근거 없는 항목은 지운다 | Accepted | 2026-10-20 |
