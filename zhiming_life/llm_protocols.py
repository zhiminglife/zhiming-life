"""Small synchronous adapters for the three supported chat API formats."""

from __future__ import annotations

from urllib.parse import quote

import httpx

from zhiming_life.llm import LLMConfig, LLMConfigError


def _endpoint(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


def _post_json(
    client: httpx.Client, url: str, *, headers: dict[str, str], payload: dict
) -> dict:
    try:
        response = client.post(url, headers=headers, json=payload)
    except httpx.HTTPError as exc:
        raise LLMConfigError("无法连接模型服务，请检查接口地址和网络") from exc

    if response.status_code in {401, 403}:
        raise LLMConfigError("API key 无效或没有访问权限")
    if response.status_code == 404:
        raise LLMConfigError("模型或接口地址不存在")
    if response.status_code == 429:
        raise LLMConfigError("模型服务请求过于频繁，请稍后再试")
    if response.is_error:
        raise LLMConfigError(f"模型服务返回错误（HTTP {response.status_code}）")
    try:
        return response.json()
    except ValueError as exc:
        raise LLMConfigError("模型服务返回了无法识别的响应") from exc


def _openai_chat(
    client: httpx.Client,
    config: LLMConfig,
    system: str,
    messages: list[dict],
    temperature: float,
) -> str:
    payload = _post_json(
        client,
        _endpoint(config.base_url, "chat/completions"),
        headers={"Authorization": f"Bearer {config.api_key}"},
        payload={
            "model": config.model,
            "temperature": temperature,
            "messages": [{"role": "system", "content": system}, *messages],
        },
    )
    try:
        return str(payload["choices"][0]["message"]["content"] or "").strip()
    except (KeyError, IndexError, TypeError):
        return ""


def _anthropic_chat(
    client: httpx.Client,
    config: LLMConfig,
    system: str,
    messages: list[dict],
    temperature: float,
) -> str:
    payload = _post_json(
        client,
        _endpoint(config.base_url, "v1/messages"),
        headers={
            "x-api-key": config.api_key,
            "anthropic-version": "2023-06-01",
        },
        payload={
            "model": config.model,
            "max_tokens": 4096,
            "temperature": temperature,
            "system": system,
            "messages": messages,
        },
    )
    blocks = payload.get("content", [])
    return "\n".join(
        str(block.get("text", "")).strip()
        for block in blocks
        if isinstance(block, dict) and block.get("type") == "text"
    ).strip()


def _gemini_chat(
    client: httpx.Client,
    config: LLMConfig,
    system: str,
    messages: list[dict],
    temperature: float,
) -> str:
    contents = [
        {
            "role": "model" if message.get("role") == "assistant" else "user",
            "parts": [{"text": str(message.get("content", ""))}],
        }
        for message in messages
    ]
    payload = _post_json(
        client,
        _endpoint(
            config.base_url,
            f"models/{quote(config.model, safe='')}:generateContent",
        ),
        headers={"x-goog-api-key": config.api_key},
        payload={
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": contents,
            "generationConfig": {"temperature": temperature},
        },
    )
    try:
        parts = payload["candidates"][0]["content"]["parts"]
    except (KeyError, IndexError, TypeError):
        return ""
    return "\n".join(
        str(part.get("text", "")).strip()
        for part in parts
        if isinstance(part, dict) and part.get("text")
    ).strip()


def chat_completion(
    config: LLMConfig,
    system: str,
    messages: list[dict],
    temperature: float,
    *,
    client: httpx.Client | None = None,
) -> str:
    """Return one complete text response using the selected wire protocol."""

    owns_client = client is None
    http = client or httpx.Client(timeout=120)
    try:
        if config.protocol == "openai":
            text = _openai_chat(http, config, system, messages, temperature)
        elif config.protocol == "anthropic":
            text = _anthropic_chat(http, config, system, messages, temperature)
        elif config.protocol == "gemini":
            text = _gemini_chat(http, config, system, messages, temperature)
        else:  # pragma: no cover - settings and type checking constrain this value
            raise LLMConfigError("不支持的模型 API 格式")
    finally:
        if owns_client:
            http.close()

    if not text:
        raise LLMConfigError("模型服务没有返回文本")
    return text
