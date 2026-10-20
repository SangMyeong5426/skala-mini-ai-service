"""항목 1 — Ollama 요청에 think 옵션이 실리는지. ollama 없이 httpx 를 가짜로 바꿔 payload 만 본다."""
import asyncio
import contextlib
import json

import pytest

from agent import ollama_llm
from agent.ollama_llm import OllamaFastLLM, OllamaQualityLLM


class _FakeResponse:
    def raise_for_status(self):
        pass

    def json(self):
        return {"message": {"content": "{}"}, "prompt_eval_count": 3, "eval_count": 2}


def _capture_post(monkeypatch) -> list[dict]:
    sent = []

    def fake_post(url, json, timeout):
        sent.append(json)
        return _FakeResponse()

    monkeypatch.setattr(ollama_llm.httpx, "post", fake_post)
    return sent


def _capture_stream(monkeypatch, lines: list[dict]) -> list[dict]:
    sent = []

    class FakeStream:
        def raise_for_status(self):
            pass

        async def aiter_lines(self):
            for line in lines:
                yield json.dumps(line)

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        @contextlib.asynccontextmanager
        async def stream(self, method, url, json):
            sent.append(json)
            yield FakeStream()

    monkeypatch.setattr(ollama_llm.httpx, "AsyncClient", FakeAsyncClient)
    return sent


def test_chat_sends_think_false(monkeypatch):
    sent = _capture_post(monkeypatch)

    OllamaFastLLM("qwen3:0.6b", usd_per_1k_tokens=0.0, think=False).route("안녕")

    assert sent[0]["think"] is False


def test_chat_omits_think_when_none(monkeypatch):
    """None 은 원본 동작 — 옵션 자체를 보내지 않아 모델 기본값(생각함)을 따른다."""
    sent = _capture_post(monkeypatch)

    OllamaFastLLM("qwen3:0.6b", usd_per_1k_tokens=0.0).route("안녕")

    assert "think" not in sent[0]


def test_stream_sends_think_and_ignores_thinking_field(monkeypatch):
    sent = _capture_stream(monkeypatch, [
        {"message": {"thinking": "생각 중…", "content": ""}, "done": False},
        {"message": {"content": "1) 확인"}, "done": False},
        {"message": {"content": ""}, "done": True, "prompt_eval_count": 5, "eval_count": 4},
    ])
    llm = OllamaQualityLLM("qwen3:8b", usd_per_1k_tokens=0.0, think=False)

    text, usage = asyncio.run(llm.write("질문", [], 1, None))

    assert sent[0]["think"] is False
    assert text == "1) 확인"          # 생각은 message.thinking 으로 와서 답변에 섞이지 않는다
    assert usage["tokens"] == 9


@pytest.mark.parametrize(("value", "expected"), [
    (None, False), ("false", False), ("FALSE", False), ("true", True), ("default", None),
])
def test_ollama_think_env(monkeypatch, value, expected):
    import server

    if value is None:
        monkeypatch.delenv("OLLAMA_THINK", raising=False)
    else:
        monkeypatch.setenv("OLLAMA_THINK", value)

    assert server._ollama_think() is expected


def test_ollama_think_env_rejects_unknown(monkeypatch):
    import server

    monkeypatch.setenv("OLLAMA_THINK", "maybe")

    with pytest.raises(ValueError):
        server._ollama_think()


def test_chat_uses_its_own_think_setting(monkeypatch):
    """대화만 생각을 켜고 분류·계획은 끈다 — 같은 모델 인스턴스에서 경로마다 다른 값이 실린다."""
    sent = _capture_stream(monkeypatch, [
        {"message": {"content": "민수님이라고 하셨어요."}, "done": False},
        {"message": {"content": ""}, "done": True, "prompt_eval_count": 3, "eval_count": 2},
    ])
    posted = _capture_post(monkeypatch)
    llm = OllamaFastLLM("qwen3:0.6b", usd_per_1k_tokens=0.0, think=False, chat_think=True)

    asyncio.run(llm.chat("제 이름이 뭐였죠?", []))
    llm.route("안녕")

    assert sent[0]["think"] is True
    assert posted[0]["think"] is False


@pytest.mark.parametrize(("general", "env", "expected"), [
    (False, None, True),        # 개선 쪽 기본 — 대화만 생각한다
    (None, None, None),         # OLLAMA_THINK=default(원본)이면 대화도 원본 그대로
    (True, None, True),
    (False, "false", False),    # 명시하면 그 값
    (False, "default", None),
])
def test_ollama_think_chat_env(monkeypatch, general, env, expected):
    import server

    if env is None:
        monkeypatch.delenv("OLLAMA_THINK_CHAT", raising=False)
    else:
        monkeypatch.setenv("OLLAMA_THINK_CHAT", env)

    assert server._ollama_think_chat(general) is expected
