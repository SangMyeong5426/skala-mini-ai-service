"""과제 2 — 게임 등급분류 사전 점검 도메인 (docs/03-design.md, 결정 0009).

AGENT_DOMAIN=rating 일 때 server.py 가 이 패키지의 그래프와 부품을 조립한다. 인시던트 도메인
(agent/graph.py)과 같은 노드 이름·이벤트 타입을 쓰고, 의존성 주입(SupervisorDeps)·의미 라우터·
검수의 수치 대조·MCP 클라이언트는 그대로 다시 쓴다.
"""
