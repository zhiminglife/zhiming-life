"""Desktop settings service with write-only API key handling."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

from zhiming_life.llm import LLMConfig

from .database import Database
from .secrets import SecretStore


class SettingsError(ValueError):
    """A desktop model setting is missing or invalid."""


@dataclass(frozen=True)
class ModelSettings:
    base_url: str
    model: str
    has_api_key: bool


class SettingsService:
    BASE_URL_SETTING = "model.base_url"
    MODEL_SETTING = "model.name"
    API_KEY_SECRET = "model.api_key"
    DEFAULT_BASE_URL = "https://api.deepseek.com/v1"
    DEFAULT_MODEL = "deepseek-chat"

    def __init__(self, database: Database, secrets: SecretStore) -> None:
        self.database = database
        self.secrets = secrets

    def get_model_settings(self) -> ModelSettings:
        return ModelSettings(
            base_url=self.database.get_setting(self.BASE_URL_SETTING)
            or self.DEFAULT_BASE_URL,
            model=self.database.get_setting(self.MODEL_SETTING) or self.DEFAULT_MODEL,
            has_api_key=bool(self.secrets.get(self.API_KEY_SECRET)),
        )

    def save_model_settings(
        self, *, base_url: str, model: str, api_key: str | None
    ) -> ModelSettings:
        base_url = base_url.strip().rstrip("/")
        model = model.strip()
        parsed = urlparse(base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise SettingsError("模型地址必须是有效的 HTTP(S) URL")
        if not model:
            raise SettingsError("模型名称不能为空")

        self.database.set_setting(self.BASE_URL_SETTING, base_url)
        self.database.set_setting(self.MODEL_SETTING, model)
        if api_key is not None:
            if api_key.strip():
                self.secrets.set(self.API_KEY_SECRET, api_key.strip())
            else:
                self.secrets.delete(self.API_KEY_SECRET)
        return self.get_model_settings()

    def require_llm_config(self) -> LLMConfig:
        settings = self.get_model_settings()
        api_key = self.secrets.get(self.API_KEY_SECRET)
        if not api_key:
            raise SettingsError("请先配置 API key")
        return LLMConfig(
            api_key=api_key,
            base_url=settings.base_url,
            model=settings.model,
        )
