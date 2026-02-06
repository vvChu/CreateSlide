"""OpenAI provider (GPT-4, GPT-4o, o-series, etc.)."""

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

# Lazy import — openai is an optional dependency
try:
    from openai import OpenAI as OpenAIClient

    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False


class OpenAIProvider(LLMProvider):
    """OpenAI (cloud) — text-only, OpenAI chat-completions API."""

    name = "openai"
    default_model_list: ClassVar[list[str]] = [
        "gpt-4.1",
        "gpt-4.1-mini",
        "gpt-4.1-nano",
        "gpt-4o",
        "gpt-4o-mini",
        "o4-mini",
        "o3-mini",
        "gpt-3.5-turbo",
    ]

    # ── Subclass hooks ──────────────────────────────────────────────────

    def _resolve_env_keys(self) -> list[str]:
        key = os.environ.get("OPENAI_API_KEY", "")
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
        if not HAS_OPENAI:
            raise _AbortAllError("Thư viện openai chưa được cài đặt. Chạy: pip install openai")

        safe_print(f"DEBUG: OpenAI calling model: {model}", logging.DEBUG)
        client = OpenAIClient(api_key=key)
        return self._chat_completion(client, model, system, prompt, response_format_json, temperature)

    # ── Shared chat-completions helper ──────────────────────────────────

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
        is_reasoning = model.startswith("o")

        if system:
            role = "developer" if is_reasoning else "system"
            messages.append({"role": role, "content": system})
        messages.append({"role": "user", "content": prompt})

        kwargs: dict = {"model": model, "messages": messages}
        if not is_reasoning:
            kwargs["temperature"] = temperature
        if response_format_json:
            kwargs["response_format"] = {"type": "json_object"}

        try:
            resp = client.chat.completions.create(**kwargs)
            text = resp.choices[0].message.content
            return (text or "").strip()
        except Exception as exc:
            _classify_openai_error(exc, model)
            return ""  # unreachable


def _classify_openai_error(exc: Exception, model: str) -> None:
    """Map OpenAI errors to the sentinel hierarchy."""
    msg = str(exc)
    low = msg.lower()
    if "429" in msg or "rate_limit" in low:
        if "insufficient_quota" in low:
            raise _PermanentModelError(f"No quota for {model}")
        raise _SkipModelError(f"Rate limited (429) for {model}")
    if "404" in msg or "model_not_found" in low:
        raise _PermanentModelError(f"Model {model} not found (404)")
    if "invalid_api_key" in low or "authentication" in low:
        raise _AbortAllError("OpenAI API Key không hợp lệ")
    if "content_filter" in low or "content_policy" in low:
        raise _SkipModelError("Content filtered")
    raise _SkipModelError(str(exc)[:150])
