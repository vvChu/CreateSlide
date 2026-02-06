"""Syntopic Book Review service — 3-step agent pipeline.

Steps:
  1. Librarian  — classify genre / category.
  2. Analyst    — deep analysis (fiction vs non-fiction prompt).
  3. Editor     — synthesise into formatted Markdown review.

Supports resume via ``resume_state`` dict.
"""

from __future__ import annotations

import json
from collections.abc import Callable

from app.core.json_parser import robust_json_parse
from app.core.log import safe_print
from app.prompts.review import (
    PROMPT_REVIEW_ANALYST_FICTION,
    PROMPT_REVIEW_ANALYST_NON_FICTION,
    PROMPT_REVIEW_EDITOR,
    PROMPT_REVIEW_LIBRARIAN,
)
from app.providers.registry import get_provider, resolve_provider_keys
from app.services.document import load_document


class PartialCompletionError(Exception):
    """Raised when some (but not all) review steps completed successfully."""

    def __init__(self, message: str, partial_data: dict):
        super().__init__(message)
        self.partial_data = partial_data


def review_book_syntopic(
    file_bytes: bytes,
    mime_type: str,
    *,
    api_key: str | None = None,
    api_keys: list[str] | None = None,
    language: str = "Tiếng Việt",
    cancel_check: Callable[[], bool] | None = None,
    resume_state: dict | None = None,
    provider: str = "gemini",
) -> dict:
    """Execute the 3-step Syntopic Layered Analysis.

    Returns dict with ``mode='syntopic_review'`` on success.
    Raises ``PartialCompletionError`` with checkpoint data if a step fails.
    """
    keys = resolve_provider_keys(provider, api_key, api_keys)
    state = dict(resume_state) if resume_state else {}

    def _make_llm():
        return get_provider(
            provider,
            api_keys=keys,
            base_url=keys[0] if provider == "ollama" and keys and keys[0].startswith("http") else None,
        )

    def _prepare_prompt(prompt_text: str) -> str:
        """Prepend document text for text-only providers."""
        if provider in ("openai", "ollama") and file_bytes and mime_type:
            doc_text = load_document(file_bytes, mime_type)
            return f"Nội dung tài liệu:\n{doc_text}\n\n{prompt_text}"
        return prompt_text

    # ── Step 1: Librarian ───────────────────────────────────────────────
    librarian_data = state.get("librarian_data")
    model1 = state.get("model1_name", "skipped")

    if not librarian_data:
        try:
            safe_print("Step 1: Librarian Agent (Classifying)...")
            llm = _make_llm()
            resp, model1 = llm.generate(
                system="",
                prompt=_prepare_prompt(PROMPT_REVIEW_LIBRARIAN),
                cancel_check=cancel_check,
                response_format_json=True,
                temperature=0.3,
                file_bytes=file_bytes if provider == "gemini" else None,
                mime_type=mime_type if provider == "gemini" else None,
            )
            try:
                librarian_data = robust_json_parse(resp)
            except Exception:
                librarian_data = {"category": "Non-Fiction", "genre": "General"}
                safe_print("-> Librarian JSON parse failed. Defaulting.")
            state["librarian_data"] = librarian_data
            state["model1_name"] = model1
            safe_print(f"-> Classified: {librarian_data.get('category')} / {librarian_data.get('genre')}")
        except Exception as exc:
            raise PartialCompletionError(f"Lỗi ở Bước 1 (Librarian): {exc}", state) from exc
    else:
        safe_print("Skipping Step 1 (Already Done).")

    # ── Step 2: Analyst ─────────────────────────────────────────────────
    analyst_output = state.get("analyst_output")
    model2 = state.get("model2_name", "skipped")

    if not analyst_output:
        try:
            safe_print("Step 2: Analyst Agent (Deep Analysis)...")
            prompt_analyst = (
                PROMPT_REVIEW_ANALYST_FICTION
                if librarian_data.get("category") == "Fiction"
                else PROMPT_REVIEW_ANALYST_NON_FICTION
            )
            llm = _make_llm()
            analyst_output, model2 = llm.generate(
                system="",
                prompt=_prepare_prompt(prompt_analyst),
                cancel_check=cancel_check,
                response_format_json=False,
                temperature=0.6,
                file_bytes=file_bytes if provider == "gemini" else None,
                mime_type=mime_type if provider == "gemini" else None,
            )
            state["analyst_output"] = analyst_output
            state["model2_name"] = model2
        except Exception as exc:
            raise PartialCompletionError(f"Lỗi ở Bước 2 (Analyst): {exc}", state) from exc
    else:
        safe_print("Skipping Step 2 (Already Done).")

    # ── Step 3: Editor ──────────────────────────────────────────────────
    safe_print(f"Step 3: Editor Agent (Writing Review in {language})...")
    try:
        final_prompt = PROMPT_REVIEW_EDITOR.format(
            librarian_output=json.dumps(librarian_data, ensure_ascii=False),
            analyst_output=analyst_output,
            language=language,
        )
        llm = _make_llm()
        review_markdown, model3 = llm.generate(
            system="",
            prompt=final_prompt,
            cancel_check=cancel_check,
            response_format_json=False,
            temperature=0.6,
        )
    except Exception as exc:
        raise PartialCompletionError(f"Lỗi ở Bước 3 (Editor): {exc}", state) from exc

    safe_print("Syntopic Review Completed.")
    return {
        "mode": "syntopic_review",
        "category": librarian_data.get("category"),
        "genre": librarian_data.get("genre"),
        "review_markdown": review_markdown,
        "used_model": f"{model1}->{model2}->{model3}",
    }
