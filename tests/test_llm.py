from __future__ import annotations

import httpx
import pytest

from zhiming_life import llm
from zhiming_life.llm_protocols import chat_completion


def test_request_config_is_scoped_and_restored(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ZHIMING_LIFE_API_KEY", "env-secret")
    monkeypatch.setenv("ZHIMING_LIFE_BASE_URL", "https://env.example/v1")
    monkeypatch.setenv("ZHIMING_LIFE_MODEL", "env-model")

    assert llm.current_config().model == "env-model"

    first = llm.LLMConfig(
        api_key="first-secret",
        base_url="https://first.example/v1",
        model="first-model",
    )
    second = llm.LLMConfig(
        api_key="second-secret",
        base_url="https://second.example/v1",
        model="second-model",
    )

    with llm.use_config(first):
        assert llm.current_config() == first
        with llm.use_config(second):
            assert llm.current_config() == second
        assert llm.current_config() == first

    assert llm.current_config().model == "env-model"


def test_missing_api_key_is_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ZHIMING_LIFE_API_KEY", raising=False)

    with pytest.raises(llm.LLMConfigError, match="API key"):
        llm.current_config()


def test_openai_protocol_uses_chat_completions_contract() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/chat/completions"
        assert request.headers["authorization"] == "Bearer openai-secret"
        assert request.read()
        assert request.headers["content-type"] == "application/json"
        assert request.extensions["timeout"]
        payload = __import__("json").loads(request.content)
        assert payload == {
            "model": "deepseek-chat",
            "temperature": 0.2,
            "messages": [
                {"role": "system", "content": "system prompt"},
                {"role": "user", "content": "hello"},
            ],
        }
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "openai answer"}}]},
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = chat_completion(
            llm.LLMConfig(
                api_key="openai-secret",
                base_url="https://gateway.example/v1",
                model="deepseek-chat",
                protocol="openai",
            ),
            "system prompt",
            [{"role": "user", "content": "hello"}],
            0.2,
            client=client,
        )

    assert result == "openai answer"


def test_anthropic_protocol_uses_messages_contract() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/messages"
        assert request.headers["x-api-key"] == "anthropic-secret"
        assert request.headers["anthropic-version"] == "2023-06-01"
        payload = __import__("json").loads(request.content)
        assert payload == {
            "model": "claude-opus-4-6",
            "max_tokens": 4096,
            "temperature": 0.3,
            "system": "system prompt",
            "messages": [
                {"role": "user", "content": "hello"},
                {"role": "assistant", "content": "prior answer"},
            ],
        }
        return httpx.Response(
            200,
            json={"content": [{"type": "text", "text": "anthropic answer"}]},
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = chat_completion(
            llm.LLMConfig(
                api_key="anthropic-secret",
                base_url="https://gateway.example",
                model="claude-opus-4-6",
                protocol="anthropic",
            ),
            "system prompt",
            [
                {"role": "user", "content": "hello"},
                {"role": "assistant", "content": "prior answer"},
            ],
            0.3,
            client=client,
        )

    assert result == "anthropic answer"


def test_gemini_protocol_uses_generate_content_contract() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1beta/models/gemini-3.6-flash:generateContent"
        assert request.headers["x-goog-api-key"] == "gemini-secret"
        payload = __import__("json").loads(request.content)
        assert payload == {
            "systemInstruction": {"parts": [{"text": "system prompt"}]},
            "contents": [
                {"role": "user", "parts": [{"text": "hello"}]},
                {"role": "model", "parts": [{"text": "prior answer"}]},
            ],
            "generationConfig": {"temperature": 0.4},
        }
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {"content": {"parts": [{"text": "gemini answer"}]}}
                ]
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = chat_completion(
            llm.LLMConfig(
                api_key="gemini-secret",
                base_url="https://gateway.example/v1beta",
                model="gemini-3.6-flash",
                protocol="gemini",
            ),
            "system prompt",
            [
                {"role": "user", "content": "hello"},
                {"role": "assistant", "content": "prior answer"},
            ],
            0.4,
            client=client,
        )

    assert result == "gemini answer"


@pytest.mark.parametrize(
    ("protocol", "response"),
    [
        ("openai", {"choices": [{"message": {"content": ""}}]}),
        ("anthropic", {"content": [{"type": "thinking", "thinking": "x"}]}),
        ("gemini", {"candidates": [{"content": {"parts": []}}]}),
    ],
)
def test_protocols_reject_successful_responses_without_text(
    protocol: llm.LLMProtocol, response: dict
) -> None:
    client = httpx.Client(
        transport=httpx.MockTransport(lambda _request: httpx.Response(200, json=response))
    )
    with client, pytest.raises(llm.LLMConfigError, match="没有返回文本"):
        chat_completion(
            llm.LLMConfig(
                api_key="secret",
                base_url="https://gateway.example/v1",
                model="model-name",
                protocol=protocol,
            ),
            "system",
            [{"role": "user", "content": "hello"}],
            0,
            client=client,
        )
