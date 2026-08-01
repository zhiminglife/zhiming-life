"""LLM 客户端 —— OpenAI、Anthropic 与 Gemini 协议统一入口。

这里只留最朴素的一条：任何 OpenAI 兼容端点（OpenAI / DeepSeek / 本地 Ollama /
各种中转）都能用，配好环境变量即可。我们想让你看清「多智能体怎么搭」，而不是替你
选模型——模型这层换谁都行，不是这个项目的重点。

环境变量：
  ZHIMING_LIFE_API_KEY     必填，你的 API key
  ZHIMING_LIFE_BASE_URL    可选，默认 https://api.openai.com/v1
  ZHIMING_LIFE_MODEL       可选，默认 gpt-4o-mini
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Iterator, Literal, cast


class LLMConfigError(RuntimeError):
    """缺 API key 等配置问题——给一句人话提示，不抛栈。"""


LLMProtocol = Literal["openai", "anthropic", "gemini"]


@dataclass(frozen=True)
class LLMConfig:
    """One provider endpoint configuration."""

    api_key: str
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-4o-mini"
    protocol: LLMProtocol = "openai"


_active_config: ContextVar[LLMConfig | None] = ContextVar(
    "zhiming_life_llm_config", default=None
)


@contextmanager
def use_config(config: LLMConfig) -> Iterator[None]:
    """Temporarily use a model config for the current request context."""

    token = _active_config.set(config)
    try:
        yield
    finally:
        _active_config.reset(token)


def current_config() -> LLMConfig:
    configured = _active_config.get()
    if configured is not None:
        return configured

    api_key = os.getenv("ZHIMING_LIFE_API_KEY")
    if not api_key:
        raise LLMConfigError(
            "未设置 API key。请在桌面端模型设置中填写，或设置 "
            "ZHIMING_LIFE_API_KEY。"
        )
    return LLMConfig(
        api_key=api_key,
        base_url=os.getenv("ZHIMING_LIFE_BASE_URL", "https://api.openai.com/v1"),
        model=os.getenv("ZHIMING_LIFE_MODEL", "gpt-4o-mini"),
        protocol=cast(
            LLMProtocol, os.getenv("ZHIMING_LIFE_PROTOCOL", "openai")
        ),
    )


def model_name() -> str:
    return current_config().model


def chat(system: str, messages: list[dict], *, temperature: float = 0.7) -> str:
    """一次性返回完整回复（非流式，开源版求简单）。

    Args:
        system: system prompt（人格 / 框架 / 输出格式都在这里）
        messages: [{"role": "user"|"assistant", "content": str}, ...] 对话历史
    """
    from zhiming_life.llm_protocols import chat_completion

    return chat_completion(current_config(), system, messages, temperature)
