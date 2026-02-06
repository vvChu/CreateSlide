"""Summary & deep-dive service.

Orchestrates: provider.generate() + prompt templates + JSON parsing.
Does *not* do any PDF rendering (that's in app.rendering.pdf).
"""

from __future__ import annotations

from collections.abc import Callable

from app.core.json_parser import robust_json_parse
from app.core.log import request_context, safe_print, timed
from app.prompts.summary import (
    PROMPT_DEEP_DIVE_FULL,
    PROMPT_SUMMARIZE_DOCUMENT,
    SUMMARIZER_SYSTEM_INSTRUCTION,
)
from app.providers.registry import get_provider, resolve_provider_keys
from app.services.document import load_document


def summarize_document(
    file_bytes: bytes,
    mime_type: str,
    *,
    api_key: str | None = None,
    api_keys: list[str] | None = None,
    user_instructions: str = "",
    cancel_check: Callable[[], bool] | None = None,
    provider: str = "gemini",
) -> dict:
    """Standard document summarisation → dict with mode='standard'."""

    keys = resolve_provider_keys(provider, api_key, api_keys)

    with request_context() as rid:
        safe_print(f"[{rid}] Starting standard summarisation (provider={provider})")

    full_prompt = f"{PROMPT_SUMMARIZE_DOCUMENT}\n{user_instructions}"

    # Pre-extract text for text-only providers
    if provider in ("openai", "ollama") and file_bytes and mime_type:
        doc_text = load_document(file_bytes, mime_type)
        full_prompt = f"Nội dung tài liệu:\n{doc_text}\n\n{full_prompt}"

    llm = get_provider(
        provider,
        api_keys=keys,
        base_url=keys[0] if provider == "ollama" and keys and keys[0].startswith("http") else None,
    )

    with timed("summarize_document", provider=provider):
        response_text, model_name = llm.generate(
            system=SUMMARIZER_SYSTEM_INSTRUCTION,
            prompt=full_prompt,
            cancel_check=cancel_check,
            response_format_json=True,
            temperature=0.4,
            file_bytes=file_bytes if provider == "gemini" else None,
            mime_type=mime_type if provider == "gemini" else None,
        )

    data = robust_json_parse(response_text)
    if isinstance(data, list):
        data = data[0] if data and isinstance(data[0], dict) else {"overview": str(data)}

    safe_print("Summarization Completed.")
    return {
        "mode": "standard",
        "title": data.get("title", "Document Summary"),
        "overview": data.get("overview", ""),
        "key_points": data.get("key_points", []),
        "conclusion": data.get("conclusion", ""),
        "used_model": model_name,
    }


def summarize_book_deep_dive(
    file_bytes: bytes,
    mime_type: str,
    *,
    api_key: str | None = None,
    api_keys: list[str] | None = None,
    cancel_check: Callable[[], bool] | None = None,
    provider: str = "gemini",
) -> dict:
    """Deep-dive 'Big Ideas' summarisation → dict with mode='deep_dive'."""

    keys = resolve_provider_keys(provider, api_key, api_keys)

    prompt = PROMPT_DEEP_DIVE_FULL
    if provider in ("openai", "ollama") and file_bytes and mime_type:
        doc_text = load_document(file_bytes, mime_type)
        prompt = f"Nội dung tài liệu:\n{doc_text}\n\n{prompt}"

    llm = get_provider(
        provider,
        api_keys=keys,
        base_url=keys[0] if provider == "ollama" and keys and keys[0].startswith("http") else None,
    )

    with timed("summarize_book_deep_dive", provider=provider):
        response_text, model_name = llm.generate(
            system="",
            prompt=prompt,
            cancel_check=cancel_check,
            response_format_json=True,
            temperature=0.4,
            file_bytes=file_bytes if provider == "gemini" else None,
            mime_type=mime_type if provider == "gemini" else None,
        )

    data = robust_json_parse(response_text)

    safe_print("Deep Dive Completed.")
    return {
        "mode": "deep_dive",
        "metadata": data.get("metadata", {}),
        "big_ideas": data.get("big_ideas", []),
        "introduction": data.get("introduction", {}),
        "core_ideas": data.get("core_ideas", []),
        "about_author": data.get("about_author", ""),
        "about_creator": data.get("about_creator", ""),
        "used_model": model_name,
    }
