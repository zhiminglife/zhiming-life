from __future__ import annotations

import pytest

from zhiming_life import llm


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
