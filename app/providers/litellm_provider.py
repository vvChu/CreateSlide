"""LiteLLM universal provider — routes to 100+ LLM providers.

LiteLLM acts as a universal adapter: specify any model string
(e.g. ``"openai/gpt-4o"``, ``"anthropic/claude-3-sonnet"``,
``"ollama/qwen2.5:14b"``, ``"groq/llama3-70b"``) and LiteLLM
handles the API translation.

Requires: ``pip install litellm``
"""

from __future__ import annotations

import logging
import os
from typing import ClassVar

from app.core.log import safe_print
from app.providers.base import (
    LLMProvider,
    _AbortAllError,
    _PermanentModelError,
    _SkipModelError,
)

try:
    import litellm

    HAS_LITELLM = True
except ImportError:
    HAS_LITELLM = False


class LiteLLMProvider(LLMProvider):
    """Universal LLM proxy via LiteLLM — supports 100+ providers."""

    name = "litellm"
    default_model_list: ClassVar[list[str]] = [
        "openai/gpt-4o",
        "anthropic/claude-sonnet-4-20250514",
        "groq/llama-3.3-70b-versatile",
    ]

    def __init__(self, api_keys: list[str] | None = None, models: list[str] | None = None):
        super().__init__(api_keys)
        if models:
            self.default_model_list = models  # type: ignore[assignment]

    # ── Subclass hooks ──────────────────────────────────────────────────

    def _resolve_env_keys(self) -> list[str]:
        # LiteLLM uses the provider-specific env vars (OPENAI_API_KEY, etc.)
        # We just need a non-empty key list to pass validation
        key = os.environ.get("LITELLM_API_KEY", "") or os.environ.get("OPENAI_API_KEY", "") or "litellm"
        return [key] if key else []

    def _call_model(
        self,
        *,
        key: str,
        model: str,
        system: str,
        prompt: str,
        response_format_json: bool,
        temperature: float,
        file_bytes: bytes | None,
        mime_type: str | None,
    ) -> str:
        if not HAS_LITELLM:
            raise _AbortAllError("Thư viện litellm chưa được cài đặt. Chạy: pip install litellm")

        safe_print(f"DEBUG: LiteLLM calling model: {model}", logging.DEBUG)

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

        # LiteLLM picks up API keys from env vars automatically
        # but we can also pass them explicitly
        if key and key != "litellm":
            kwargs["api_key"] = key

        try:
            # Suppress LiteLLM's verbose logging
            litellm.suppress_debug_info = True
            response = litellm.completion(**kwargs)
            text = response.choices[0].message.content  # type: ignore[union-attr]
            return (text or "").strip()
        except Exception as exc:
            _classify_litellm_error(exc, model)
            return ""  # unreachable


def _classify_litellm_error(exc: Exception, model: str) -> None:
    """Map LiteLLM errors to the sentinel hierarchy."""
    msg = str(exc)
    low = msg.lower()

    if "rate_limit" in low or "429" in msg:
        raise _SkipModelError(f"Rate limited (429) for {model}")
    if "not_found" in low or "404" in msg or "does not exist" in low:
        raise _PermanentModelError(f"Model {model} not found")
    if "authentication" in low or "invalid_api_key" in low or "401" in msg:
        raise _AbortAllError("API Key không hợp lệ")
    if "timeout" in low:
        raise _SkipModelError(f"Timeout for {model}")
    raise _SkipModelError(str(exc)[:150])
