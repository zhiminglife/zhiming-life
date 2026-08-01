"""Desktop settings service with write-only API key handling."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

from zhiming_life.llm import LLMConfig, LLMProtocol

from .database import Database
from .secrets import SecretStore


class SettingsError(ValueError):
    """A desktop model setting is missing or invalid."""


@dataclass(frozen=True)
class ModelSettings:
    protocol: LLMProtocol
    base_url: str
    model: str
    has_api_key: bool


class SettingsService:
    PROTOCOL_SETTING = "model.protocol"
    BASE_URL_SETTING = "model.base_url"
    MODEL_SETTING = "model.name"
    API_KEY_SECRET = "model.api_key"
    DEFAULT_BASE_URL = "https://api.deepseek.com/v1"
    DEFAULT_MODEL = "deepseek-chat"

    def __init__(self, database: Database, secrets: SecretStore) -> None:
        self.database = database
        self.secrets = secrets

    def get_model_settings(self) -> ModelSettings:
        protocol = self.database.get_setting(self.PROTOCOL_SETTING) or "openai"
        return ModelSettings(
            protocol=protocol,
            base_url=self.database.get_setting(self.BASE_URL_SETTING)
            or self.DEFAULT_BASE_URL,
            model=self.database.get_setting(self.MODEL_SETTING) or self.DEFAULT_MODEL,
            has_api_key=bool(self._get_api_key(protocol)),
        )

    @staticmethod
    def _protocol_secret(protocol: LLMProtocol) -> str:
        return f"model.api_key.{protocol}"

    def _get_api_key(self, protocol: LLMProtocol) -> str | None:
        key = self.secrets.get(self._protocol_secret(protocol))
        if key is None and protocol == "openai":
            return self.secrets.get(self.API_KEY_SECRET)
        return key

    def save_model_settings(
        self,
        *,
        base_url: str,
        model: str,
        api_key: str | None,
        protocol: LLMProtocol = "openai",
    ) -> ModelSettings:
        base_url = base_url.strip().rstrip("/")
        model = model.strip()
        parsed = urlparse(base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise SettingsError("模型地址必须是有效的 HTTP(S) URL")
        if not model:
            raise SettingsError("模型名称不能为空")

        self.database.set_setting(self.PROTOCOL_SETTING, protocol)
        self.database.set_setting(self.BASE_URL_SETTING, base_url)
        self.database.set_setting(self.MODEL_SETTING, model)
        secret_name = self._protocol_secret(protocol)
        if api_key is not None:
            if api_key.strip():
                self.secrets.set(secret_name, api_key.strip())
            else:
                self.secrets.delete(secret_name)
                if protocol == "openai":
                    self.secrets.delete(self.API_KEY_SECRET)
        return self.get_model_settings()

    def require_llm_config(self) -> LLMConfig:
        settings = self.get_model_settings()
        api_key = self._get_api_key(settings.protocol)
        if not api_key:
            raise SettingsError("请先配置 API key")
        return LLMConfig(
            api_key=api_key,
            base_url=settings.base_url,
            model=settings.model,
            protocol=settings.protocol,
        )
