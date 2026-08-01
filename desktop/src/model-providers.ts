import type { ModelProtocol } from "./types";

export const MODEL_PROVIDER_DEFAULTS: Record<
  ModelProtocol,
  { label: string; hint: string; base_url: string; model: string }
> = {
  openai: {
    label: "OpenAI 兼容",
    hint: "默认 DeepSeek，也支持 OpenAI、Ollama 与兼容中转",
    base_url: "https://api.deepseek.com/v1",
    model: "deepseek-chat",
  },
  anthropic: {
    label: "Anthropic 原生",
    hint: "Anthropic Messages API",
    base_url: "https://api.anthropic.com",
    model: "claude-opus-4-6",
  },
  gemini: {
    label: "Gemini 原生",
    hint: "Google Gemini generateContent",
    base_url: "https://generativelanguage.googleapis.com/v1beta",
    model: "gemini-3.6-flash",
  },
};
