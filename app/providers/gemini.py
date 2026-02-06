"""Google Gemini provider (via google-genai SDK)."""

from __future__ import annotations

import logging
import os
from typing import ClassVar

from google import genai
from google.genai import types

from app.core.log import safe_print
from app.providers.base import (
    LLMProvider,
    _AbortAllError,
    _PermanentModelError,
    _SkipModelError,
)


class GeminiProvider(LLMProvider):
    """Google Gemini — supports native multimodal PDF input."""

    name = "gemini"
    default_model_list: ClassVar[list[str]] = [
        "gemini-3-pro-preview",
        "gemini-3-flash-preview",
        "gemini-2.5-pro",
        "gemini-2.5-flash",
        "gemini-exp-1206",
        "gemini-2.0-flash",
        "gemini-1.5-pro",
        "gemini-1.5-flash",
    ]

    # ── Subclass hooks ──────────────────────────────────────────────────

    def _resolve_env_keys(self) -> list[str]:
        key = os.environ.get("GOOGLE_API_KEY", "")
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
        safe_print(f"DEBUG: Gemini calling model: {model}", logging.DEBUG)

        client = genai.Client(api_key=key)

        # Build content parts
        parts: list[types.Part] = []
        if file_bytes and mime_type and mime_type == "application/pdf":
            parts.append(types.Part.from_bytes(data=file_bytes, mime_type="application/pdf"))
            parts.append(types.Part.from_text(text=prompt))
        elif file_bytes and mime_type:
            # Non-PDF binary → must extract text upstream (done by services layer)
            parts.append(types.Part.from_text(text=prompt))
        else:
            parts.append(types.Part.from_text(text=prompt))

        config = types.GenerateContentConfig(
            system_instruction=system if system else None,
            response_mime_type="application/json" if response_format_json else "text/plain",
            temperature=temperature,
        )

        try:
            response = client.models.generate_content(
                model=model,
                contents=[types.Content(role="user", parts=parts)],
                config=config,
            )
            try:
                return response.text or ""
            except Exception as val_err:
                safe_print(f"[{model}] Invalid response (Safety/Block): {val_err}")
                return ""
        except Exception as exc:
            self._classify_error(exc, model)
            return ""  # unreachable — classify always raises

    # ── Error classification ────────────────────────────────────────────

    @staticmethod
    def _classify_error(exc: Exception, model: str) -> None:
        msg = str(exc)
        if "RESOURCE_EXHAUSTED" in msg or "429" in msg:
            if "limit: 0" in msg or "limit:0" in msg:
                raise _PermanentModelError(f"Quota=0 for {model}")
            raise _SkipModelError(f"Rate limited (429) for {model}")
        if "NOT_FOUND" in msg or "404" in msg:
            raise _PermanentModelError(f"Model {model} not found (404)")
        if "INVALID_ARGUMENT" in msg and "API key not valid" in msg:
            raise _AbortAllError("API Key không hợp lệ")
        if "model output must contain" in msg or "Tool use is not expected" in msg:
            raise _SkipModelError("Empty/blocked output")
        raise _SkipModelError(str(exc)[:150])
