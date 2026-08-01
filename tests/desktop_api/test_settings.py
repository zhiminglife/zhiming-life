from __future__ import annotations

import sqlite3

import pytest

from zhiming_life.desktop_api.database import Database
from zhiming_life.desktop_api.secrets import MemorySecretStore
from zhiming_life.desktop_api.settings import SettingsError, SettingsService


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
    assert secrets.get(SettingsService.API_KEY_SECRET) == "top-secret-key"

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
    assert secrets.get(SettingsService.API_KEY_SECRET) == "existing-secret"


def test_empty_api_key_removes_secret(tmp_path) -> None:
    database = Database(tmp_path)
    secrets = MemorySecretStore({SettingsService.API_KEY_SECRET: "existing-secret"})
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
