"""Anthropic Claude provider — Claude 3.5, Claude 3, etc.

Uses the Anthropic Python SDK (``anthropic`` package).
Supports system messages, JSON mode, and temperature.
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
    import anthropic

    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False


class AnthropicProvider(LLMProvider):
    """Anthropic Claude — cloud API, strong reasoning & analysis."""

    name = "anthropic"
    default_model_list: ClassVar[list[str]] = [
        "claude-sonnet-4-20250514",
        "claude-3-7-sonnet-20250219",
        "claude-3-5-haiku-20241022",
    ]

    # ── Subclass hooks ──────────────────────────────────────────────────

    def _resolve_env_keys(self) -> list[str]:
        key = os.environ.get("ANTHROPIC_API_KEY", "")
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
        if not HAS_ANTHROPIC:
            raise _AbortAllError("Thư viện anthropic chưa được cài đặt. Chạy: pip install anthropic")

        safe_print(f"DEBUG: Anthropic calling model: {model}", logging.DEBUG)

        client = anthropic.Anthropic(api_key=key)

        # Build messages
        user_content = prompt
        if response_format_json:
            user_content += "\n\nIMPORTANT: Respond with valid JSON only. No markdown, no explanation."

        messages = [{"role": "user", "content": user_content}]

        kwargs: dict = {
            "model": model,
            "max_tokens": 8192,
            "messages": messages,
            "temperature": temperature,
        }
        if system:
            kwargs["system"] = system

        try:
            response = client.messages.create(**kwargs)
            text = response.content[0].text if response.content else ""
            return (text or "").strip()
        except Exception as exc:
            _classify_anthropic_error(exc, model)
            return ""  # unreachable


def _classify_anthropic_error(exc: Exception, model: str) -> None:
    """Map Anthropic errors to the sentinel hierarchy."""
    msg = str(exc)
    low = msg.lower()

    if "rate_limit" in low or "429" in msg:
        raise _SkipModelError(f"Rate limited (429) for {model}")
    if "not_found" in low or "404" in msg:
        raise _PermanentModelError(f"Model {model} not found (404)")
    if "authentication" in low or ("invalid" in low and "api" in low):
        raise _AbortAllError("Anthropic API Key không hợp lệ")
    if "overloaded" in low:
        raise _SkipModelError(f"Server overloaded for {model}")
    raise _SkipModelError(str(exc)[:150])
