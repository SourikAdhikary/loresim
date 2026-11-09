"""Pluggable zero-dependency LLMProvider adapters (Ollama, OpenAI, Anthropic, Gemini, Callable)."""

from __future__ import annotations

import json
import os
import urllib.request
from collections.abc import Callable
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class LLMProvider(Protocol):
    """Protocol for pluggable LLM providers used by SceneSimulator and ManuscriptIngester."""

    @property
    def provider_name(self) -> str:
        """Human-readable identifier for this LLM provider."""
        ...

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        temperature: float = 0.2,
        json_mode: bool = False,
    ) -> str:
        """Execute a completion given a system prompt and user prompt."""
        ...


class CallableLLMProvider:
    """Adapter wrapping a Python callable `(system_prompt, user_prompt) -> str`."""

    def __init__(
        self,
        fn: Callable[[str, str], str],
        name: str = "callable-llm",
    ) -> None:
        self._fn = fn
        self._name = name

    @property
    def provider_name(self) -> str:
        return self._name

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        temperature: float = 0.2,
        json_mode: bool = False,
    ) -> str:
        _ = (temperature, json_mode)
        return self._fn(system_prompt, user_prompt)


class OllamaLLMProvider:
    """Zero-dependency local Ollama HTTP adapter (`/api/chat`)."""

    def __init__(
        self,
        model: str = "llama3.2",
        base_url: str = "http://127.0.0.1:11434",
        timeout_sec: float = 30.0,
    ) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout_sec = timeout_sec

    @property
    def provider_name(self) -> str:
        return f"ollama:{self.model}"

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        temperature: float = 0.2,
        json_mode: bool = False,
    ) -> str:
        payload: dict[str, Any] = {
            "model": self.model,
            "stream": False,
            "options": {"temperature": temperature},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        if json_mode:
            payload["format"] = "json"
        req = urllib.request.Request(
            f"{self.base_url}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=self.timeout_sec) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        return str(body.get("message", {}).get("content", "")).strip()


class OpenAICompatibleLLMProvider:
    """Zero-dependency OpenAI / OpenRouter / vLLM / Groq chat completions adapter."""

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        api_key: str | None = None,
        base_url: str = "https://api.openai.com/v1",
        timeout_sec: float = 30.0,
    ) -> None:
        self.model = model
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.base_url = base_url.rstrip("/")
        self.timeout_sec = timeout_sec

    @property
    def provider_name(self) -> str:
        return f"openai:{self.model}"

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        temperature: float = 0.2,
        json_mode: bool = False,
    ) -> str:
        payload: dict[str, Any] = {
            "model": self.model,
            "temperature": temperature,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=self.timeout_sec) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        choices = body.get("choices", [])
        if not choices:
            return ""
        return str(choices[0].get("message", {}).get("content", "")).strip()


class AnthropicLLMProvider:
    """Zero-dependency Anthropic Messages API adapter."""

    def __init__(
        self,
        model: str = "claude-3-5-haiku-latest",
        api_key: str | None = None,
        base_url: str = "https://api.anthropic.com/v1",
        timeout_sec: float = 30.0,
    ) -> None:
        self.model = model
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self.base_url = base_url.rstrip("/")
        self.timeout_sec = timeout_sec

    @property
    def provider_name(self) -> str:
        return f"anthropic:{self.model}"

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        temperature: float = 0.2,
        json_mode: bool = False,
    ) -> str:
        sys_text = (
            f"{system_prompt}\nRespond strictly with valid JSON."
            if json_mode
            else system_prompt
        )
        payload: dict[str, Any] = {
            "model": self.model,
            "max_tokens": 1024,
            "temperature": temperature,
            "system": sys_text,
            "messages": [{"role": "user", "content": user_prompt}],
        }
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
        }
        req = urllib.request.Request(
            f"{self.base_url}/messages",
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=self.timeout_sec) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        blocks = body.get("content", [])
        if not blocks:
            return ""
        return str(blocks[0].get("text", "")).strip()


class GeminiLLMProvider:
    """Zero-dependency Google Gemini `generateContent` REST adapter."""

    def __init__(
        self,
        model: str = "gemini-2.5-flash",
        api_key: str | None = None,
        timeout_sec: float = 30.0,
    ) -> None:
        self.model = model
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY", "")
        self.timeout_sec = timeout_sec

    @property
    def provider_name(self) -> str:
        return f"gemini:{self.model}"

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        temperature: float = 0.2,
        json_mode: bool = False,
    ) -> str:
        gen_cfg: dict[str, Any] = {"temperature": temperature}
        if json_mode:
            gen_cfg["responseMimeType"] = "application/json"
        payload: dict[str, Any] = {
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
            "generationConfig": gen_cfg,
        }
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:generateContent?key={self.api_key}"
        )
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=self.timeout_sec) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        candidates = body.get("candidates", [])
        if not candidates:
            return ""
        parts = candidates[0].get("content", {}).get("parts", [])
        return str(parts[0].get("text", "")).strip() if parts else ""


def resolve_llm_provider_from_env() -> LLMProvider | None:
    """Auto-resolve an LLMProvider from environment variables if configured, else None."""
    provider_kind = os.environ.get("LORESIM_LLM_PROVIDER", "").strip().lower()
    model = os.environ.get("LORESIM_LLM_MODEL", "").strip()
    if provider_kind == "ollama":
        return OllamaLLMProvider(
            model=model or "llama3.2",
            base_url=os.environ.get("LORESIM_LLM_BASE_URL", "http://127.0.0.1:11434"),
        )
    if provider_kind == "openai" or (not provider_kind and os.environ.get("OPENAI_API_KEY")):
        return OpenAICompatibleLLMProvider(
            model=model or "gpt-4o-mini",
            base_url=os.environ.get("LORESIM_LLM_BASE_URL", "https://api.openai.com/v1"),
        )
    if provider_kind == "anthropic" or (not provider_kind and os.environ.get("ANTHROPIC_API_KEY")):
        return AnthropicLLMProvider(model=model or "claude-3-5-haiku-latest")
    if provider_kind == "gemini" or (not provider_kind and os.environ.get("GEMINI_API_KEY")):
        return GeminiLLMProvider(model=model or "gemini-2.5-flash")
    return None
