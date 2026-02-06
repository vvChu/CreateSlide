"""Ollama provider — local LLM via OpenAI-compatible API.

Reuses the OpenAI chat-completions helper but with:
  * Custom base_url (DGX Spark default: ``http://localhost:11444/v1``).
  * Dummy API key (``"ollama"``).
  * Shorter retry delays (``min_retry_delay_local``).
  * Long timeout for large models (72B can be slow).
  * Dynamic model discovery via ``/api/tags``.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.request
from typing import ClassVar

from app.config import settings
from app.core.log import safe_print
from app.providers.base import (
    LLMProvider,
    _AbortAllError,
    _PermanentModelError,
    _SkipModelError,
)

try:
    from openai import OpenAI as OpenAIClient

    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False


class OllamaProvider(LLMProvider):
    """Ollama (local / DGX Spark) — free, no external API key required."""

    name = "ollama"

    # Static fallback list (used when server is unreachable)
    default_model_list: ClassVar[list[str]] = [
        "qwen2.5:14b",
        "gemma3:27b",
        "qwen2.5:72b",
        "qwen2.5-coder:32b",
        "deepseek-coder-v2:latest",
    ]

    def __init__(self, api_keys: list[str] | None = None, base_url: str | None = None):
        super().__init__(api_keys)
        self.base_url = base_url or settings.ollama_base_url

    # ── Subclass hooks ──────────────────────────────────────────────────

    def _resolve_env_keys(self) -> list[str]:
        # For Ollama the "key" slot holds the base_url
        return [self.base_url]

    def _min_retry_delay(self) -> float:
        return settings.min_retry_delay_local

    def _call_model(
        self,
        *,
        key: str,  # actually the base_url for Ollama
        model: str,
        system: str,
        prompt: str,
        response_format_json: bool,
        temperature: float,
        file_bytes: bytes | None,
        mime_type: str | None,
    ) -> str:
        if not HAS_OPENAI:
            raise _AbortAllError("Thư viện openai chưa được cài đặt. Chạy: pip install openai")

        base = key if key.startswith("http") else self.base_url
        api_key = os.environ.get("OLLAMA_API_KEY", settings.ollama_api_key)

        safe_print(f"🏠 Ollama @ {base} → model {model}", logging.DEBUG)

        client = OpenAIClient(
            base_url=base,
            api_key=api_key,
            timeout=settings.ollama_timeout,
        )

        return self._chat_completion(client, model, system, prompt, response_format_json, temperature)

    # ── Chat completion (mirrors OpenAI logic, no o-series quirks) ─────

    @staticmethod
    def _chat_completion(
        client,
        model: str,
        system: str,
        prompt: str,
        response_format_json: bool,
        temperature: float,
    ) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        kwargs: dict = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        if response_format_json:
            kwargs["response_format"] = {"type": "json_object"}

        try:
            resp = client.chat.completions.create(**kwargs)
            text = resp.choices[0].message.content
            return (text or "").strip()
        except Exception as exc:
            _classify_ollama_error(exc, model)
            return ""  # unreachable

    # ── Dynamic model discovery ─────────────────────────────────────────

    def list_models(self) -> list[str]:
        """Query the Ollama ``/api/tags`` endpoint for available models."""
        # Strip /v1 suffix to get raw Ollama API root
        raw_base = self.base_url.rstrip("/")
        if raw_base.endswith("/v1"):
            raw_base = raw_base[:-3]

        url = f"{raw_base}/api/tags"
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode())
                models = [m["name"] for m in data.get("models", [])]
                if models:
                    safe_print(f"Ollama models discovered: {models}")
                    return models
        except Exception as exc:
            safe_print(f"Could not query Ollama models: {exc}")

        return self.default_model_list

    def check_connectivity(self) -> bool:
        """Return ``True`` if the Ollama server responds to ``/v1/models``."""
        try:
            req = urllib.request.Request(f"{self.base_url}/models", method="GET")
            with urllib.request.urlopen(req, timeout=3) as resp:
                return resp.status == 200
        except Exception:
            return False


def _classify_ollama_error(exc: Exception, model: str) -> None:
    msg = str(exc)
    low = msg.lower()
    if "connection" in low or "connect" in low:
        raise _AbortAllError(
            "Không thể kết nối tới Ollama server. Kiểm tra: 1) Ollama đang chạy? 2) Port đúng chưa? 3) Firewall?"
        )
    if "404" in msg or ("model" in low and "not found" in low):
        raise _PermanentModelError(f"Model {model} not found on Ollama server")
    if "429" in msg or "rate" in low:
        raise _SkipModelError(f"Rate limited for {model}")
    raise _SkipModelError(str(exc)[:150])
