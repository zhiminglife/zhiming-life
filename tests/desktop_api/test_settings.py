from __future__ import annotations

import sqlite3

import pytest

from zhiming_life.desktop_api.database import Database
from zhiming_life.desktop_api.secrets import MemorySecretStore
from zhiming_life.desktop_api.settings import SettingsError, SettingsService


def test_model_protocol_defaults_to_openai_compatible_deepseek(tmp_path) -> None:
    service = SettingsService(Database(tmp_path), MemorySecretStore())

    settings = service.get_model_settings()

    assert settings.protocol == "openai"
    assert settings.base_url == "https://api.deepseek.com/v1"
    assert settings.model == "deepseek-chat"
    assert settings.has_api_key is False


def test_model_protocol_uses_a_separate_secret_for_each_format(tmp_path) -> None:
    database = Database(tmp_path)
    secrets = MemorySecretStore()
    service = SettingsService(database, secrets)
    service.save_model_settings(
        protocol="openai",
        base_url="https://api.deepseek.com/v1",
        model="deepseek-chat",
        api_key="openai-secret",
    )

    anthropic = service.save_model_settings(
        protocol="anthropic",
        base_url="https://api.anthropic.com",
        model="claude-opus-4-6",
        api_key="anthropic-secret",
    )

    assert anthropic.protocol == "anthropic"
    assert anthropic.has_api_key is True
    assert service.require_llm_config().api_key == "anthropic-secret"
    assert service.require_llm_config().protocol == "anthropic"
    assert secrets.get("model.api_key.openai") == "openai-secret"
    assert secrets.get("model.api_key.anthropic") == "anthropic-secret"


def test_legacy_openai_secret_is_still_read_without_copying_it_to_sqlite(tmp_path) -> None:
    database = Database(tmp_path)
    secrets = MemorySecretStore({SettingsService.API_KEY_SECRET: "legacy-secret"})
    service = SettingsService(database, secrets)

    settings = service.get_model_settings()

    assert settings.protocol == "openai"
    assert settings.has_api_key is True
    assert service.require_llm_config().api_key == "legacy-secret"


def test_model_settings_keep_api_key_out_of_sqlite(tmp_path) -> None:
    database = Database(tmp_path)
    secrets = MemorySecretStore()
    service = SettingsService(database, secrets)

    saved = service.save_model_settings(
        base_url="https://gateway.example/v1",
        model="example-model",
        api_key="top-secret-key",
    )

    assert saved.base_url == "https://gateway.example/v1"
    assert saved.model == "example-model"
    assert saved.has_api_key is True
    assert not hasattr(saved, "api_key")
    assert secrets.get("model.api_key.openai") == "top-secret-key"

    with sqlite3.connect(database.path) as connection:
        stored_values = [row[0] for row in connection.execute("SELECT value FROM settings")]
    assert "top-secret-key" not in "\n".join(stored_values)

    config = service.require_llm_config()
    assert config.api_key == "top-secret-key"
    assert config.model == "example-model"


def test_omitted_api_key_preserves_existing_secret(tmp_path) -> None:
    database = Database(tmp_path)
    secrets = MemorySecretStore()
    service = SettingsService(database, secrets)
    service.save_model_settings(
        base_url="https://first.example/v1",
        model="first-model",
        api_key="existing-secret",
    )

    updated = service.save_model_settings(
        base_url="https://second.example/v1",
        model="second-model",
        api_key=None,
    )

    assert updated.has_api_key is True
    assert secrets.get("model.api_key.openai") == "existing-secret"


def test_empty_api_key_removes_secret(tmp_path) -> None:
    database = Database(tmp_path)
    secrets = MemorySecretStore({"model.api_key.openai": "existing-secret"})
    service = SettingsService(database, secrets)

    result = service.save_model_settings(
        base_url="https://gateway.example/v1",
        model="example-model",
        api_key="",
    )

    assert result.has_api_key is False
    with pytest.raises(SettingsError, match="API key"):
        service.require_llm_config()


@pytest.mark.parametrize(
    ("base_url", "model"),
    [("gateway.example/v1", "model"), ("https://gateway.example/v1", "")],
)
def test_invalid_model_settings_are_rejected(tmp_path, base_url: str, model: str) -> None:
    service = SettingsService(Database(tmp_path), MemorySecretStore())

    with pytest.raises(SettingsError):
        service.save_model_settings(base_url=base_url, model=model, api_key=None)
