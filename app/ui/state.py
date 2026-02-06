"""Mesop UI state definition.

Single ``@me.stateclass`` holding all reactive fields for the Mesop page.
"""

from __future__ import annotations

from dataclasses import field

import mesop as me

from app.config import settings


@me.stateclass
class State:
    # ── Processing ──────────────────────────────────────────────────────
    processing_status: str = "idle"
    logs: list[str] = field(default_factory=list)
    error_message: str = ""

    # ── Input ───────────────────────────────────────────────────────────
    uploaded_file_bytes: bytes = b""
    uploaded_mime_type: str = ""
    uploaded_filename: str = ""
    user_topic: str = ""

    # ── Template ────────────────────────────────────────────────────────
    template_file_bytes: bytes = b""
    template_filename: str = ""

    # ── Slide output ────────────────────────────────────────────────────
    pptx_filename: str = ""
    pptx_content_base64: str = ""

    # ── Summary/Review output ───────────────────────────────────────────
    pdf_filename: str = ""
    pdf_content_base64: str = ""

    # ── Config toggles ──────────────────────────────────────────────────
    is_detailed: bool = False
    user_instructions: str = ""

    # ── Cancellation ────────────────────────────────────────────────────
    show_cancel_dialog: bool = False
    cancel_requested: bool = False

    # ── Advanced ────────────────────────────────────────────────────────
    use_multi_key: bool = False
    user_api_keys_input: str = ""
    review_language: str = "Tiếng Việt"

    # ── AI Provider (auto-detected in on_load) ──────────────────────────
    ai_provider: str = ""
    openai_api_keys_input: str = ""
    ollama_base_url: str = settings.ollama_base_url

    # ── Resume state for review pipeline ────────────────────────────────
    resume_data: dict = field(default_factory=dict)
