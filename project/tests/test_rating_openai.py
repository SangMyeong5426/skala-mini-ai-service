"""과제 2 OpenAI 백엔드(시연용, 결정 0018) — 실제 API 는 부르지 않는다.

httpx.MockTransport 로 요청 모양(스키마·인증·스트림)과 응답 읽기만 확인한다. 프롬프트·파싱은
Ollama 등급 클래스에서 물려받으므로 test_rating_assess 등에서 이미 본다.
"""
import asyncio
import json

import httpx
import pytest

from agent.rating.llm import ROUTE_SCHEMA, OpenAIRatingFastLLM, OpenAIRatingQualityLLM


def _llm(cls, handler):
    return cls("gpt-test", usd_per_1k_tokens=0.001, transport=httpx.MockTransport(handler))


def test_route_sends_ollama_schema_and_reads_answer(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    seen = {}

    def handler(request):
        seen["body"] = json.loads(request.content)
        seen["auth"] = request.headers["authorization"]
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"route": "review"}'}}],
                                         "usage": {"total_tokens": 100}})

    result, usage = _llm(OpenAIRatingFastLLM, handler).route("좀비를 총으로 쏘는 PC FPS 몇 세예요?")

    assert result == {"route": "review", "needs_analysis": False}
    assert seen["body"]["model"] == "gpt-test"
    assert seen["body"]["response_format"]["json_schema"]["schema"] == ROUTE_SCHEMA
    assert seen["auth"] == "Bearer sk-test"
    assert "think" not in seen["body"]
    assert usage == {"model": "openai:gpt-test", "tokens": 100, "usd": 0.0001}


def test_broken_json_falls_back_like_ollama(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    def handler(request):
        return httpx.Response(200, json={"choices": [{"message": {"content": "모르겠어요"}}]})

    result, _ = _llm(OpenAIRatingQualityLLM, handler).judge_law("질문", [], "답")

    assert result["supported"] is False   # 검수 JSON 이 깨지면 답하지 않는 쪽(Ollama 와 같다)


def test_chat_streams_pieces_and_reads_usage(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    events = [{"choices": [{"delta": {"role": "assistant", "content": ""}}]},
              {"choices": [{"delta": {"content": "등급은 "}}]},
              {"choices": [{"delta": {"content": "네 가지예요."}}]},
              {"choices": [], "usage": {"total_tokens": 40}}]
    body = "".join(f"data: {json.dumps(e, ensure_ascii=False)}\n\n" for e in events) + "data: [DONE]\n\n"

    def handler(request):
        sent = json.loads(request.content)
        assert sent["stream"] is True and sent["stream_options"] == {"include_usage": True}
        return httpx.Response(200, text=body, headers={"content-type": "text/event-stream"})

    pieces: list[str] = []
    text, usage = asyncio.run(_llm(OpenAIRatingFastLLM, handler).chat("등급이 몇 개예요?", [], on_token=pieces.append))

    assert pieces == ["등급은 ", "네 가지예요."]
    assert text == "등급은 네 가지예요."
    assert usage["tokens"] == 40


def test_missing_key_stops_before_sending(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    sent = []

    def handler(request):
        sent.append(request)
        return httpx.Response(200, json={})

    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        _llm(OpenAIRatingFastLLM, handler).route("안녕")
    assert sent == []


def test_server_builds_openai_rating_llms(monkeypatch):
    import server

    monkeypatch.setenv("OPENAI_FAST_MODEL", "gpt-fast")
    monkeypatch.setenv("OPENAI_QUALITY_MODEL", "gpt-quality")

    backend, fast, quality = server._build_rating_llms("openai")

    assert backend == "openai"
    assert isinstance(fast, OpenAIRatingFastLLM) and fast.name == "openai:gpt-fast"
    assert isinstance(quality, OpenAIRatingQualityLLM) and quality.name == "openai:gpt-quality"


@pytest.mark.parametrize(("backend", "expected"), [("openai", "semantic"), ("ollama", "semantic"), ("fake", "llm")])
def test_rating_switches_default_to_agent_except_fake(monkeypatch, backend, expected):
    import server

    monkeypatch.delenv("ROUTER", raising=False)

    assert server._rating_switch("ROUTER", "semantic", "llm", backend, ("semantic", "llm")) == expected
