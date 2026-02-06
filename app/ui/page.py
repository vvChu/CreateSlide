"""Mesop page layout — the full ``main_page()`` UI component tree.

Separated from handlers so that layout changes won't touch logic and vice-versa.

v2.1 — UI polish:
  • Anthropic / LiteLLM in provider dropdown
  • Version badge in header
  • Color-coded log entries
  • Step indicators for multi-step flows
  • Improved action buttons with icons
"""

from __future__ import annotations

import mesop as me

from app import __version__
from app.ui.handlers import (
    confirm_cancel,
    dismiss_cancel,
    generate_review,
    generate_slides,
    generate_summary,
    handle_api_keys_input,
    handle_ollama_url_input,
    handle_openai_keys_input,
    handle_template_upload,
    handle_topic_input,
    handle_upload,
    handle_user_instruction,
    on_detail_change,
    on_language_change,
    on_multi_key_change,
    on_provider_change,
    request_cancel,
    resume_review,
    set_topic,
)
from app.ui.state import State


def main_page() -> None:
    state = me.state(State)

    with me.box(
        style=me.Style(
            background="#f8fafc",
            height="100vh",
            display="flex",
            flex_direction="column",
            font_family="Inter, sans-serif",
            padding=me.Padding.all(0),
        )
    ):
        # ── Header ──────────────────────────────────────────────────────
        with me.box(
            style=me.Style(
                background="linear-gradient(135deg, #ffffff 0%, #f8fafc 100%)",
                padding=me.Padding.symmetric(vertical=16, horizontal=32),
                border=me.Border(bottom=me.BorderSide(width=2, color="#e2e8f0")),
                display="flex",
                justify_content="space-between",
                align_items="center",
            )
        ):
            with me.box(style=me.Style(display="flex", align_items="center", gap=12)):
                me.icon("auto_awesome", style=me.Style(color="#2563eb", font_size=28))
                me.text("SlideGenius", style=me.Style(font_size=24, font_weight=700, color="#0f172a"))
                with me.box(
                    style=me.Style(
                        background="#dbeafe",
                        padding=me.Padding.symmetric(vertical=2, horizontal=10),
                        border_radius=12,
                    )
                ):
                    me.text(f"v{__version__}", style=me.Style(font_size=11, color="#2563eb", font_weight=600))
            me.text(
                "AI-Powered Presentation & Document Intelligence",
                style=me.Style(color="#64748b", font_size=13),
            )

        # ── 2-Column layout ─────────────────────────────────────────────
        with me.box(
            style=me.Style(
                display="grid",
                grid_template_columns="1fr 1fr",
                gap=32,
                padding=me.Padding.all(32),
                height="calc(100vh - 80px)",
                box_sizing="border-box",
            )
        ):
            _left_column(state)
            _right_column(state)


# ── Left Column: Inputs ─────────────────────────────────────────────────


def _left_column(state: State) -> None:
    with me.box(
        style=me.Style(
            background="#ffffff",
            padding=me.Padding.all(24),
            border_radius=16,
            box_shadow="0 4px 6px -1px rgb(0 0 0 / 0.1)",
            display="flex",
            flex_direction="column",
            gap=24,
        )
    ):
        me.text("Input Documents", style=me.Style(font_size=18, font_weight=600, color="#1e293b"))

        # File upload
        with me.box(style=me.Style(width="100%")):
            me.text(
                "Upload Document (PDF/DOCX/EPUB)",
                style=me.Style(font_size=14, color="#475569", margin=me.Margin(bottom=8)),
            )
            me.uploader(
                label="Choose File",
                accepted_file_types=["application/pdf", ".docx", ".epub"],
                on_upload=handle_upload,
                type="flat",
                style=me.Style(font_weight="500"),
            )

        if state.uploaded_filename:
            with me.box(
                style=me.Style(
                    background="#f0f9ff",
                    padding=me.Padding.all(12),
                    border_radius=8,
                    display="flex",
                    align_items="center",
                    gap=8,
                )
            ):
                me.icon("description", style=me.Style(color="#0284c7"))
                me.text(state.uploaded_filename, style=me.Style(font_size=14, color="#0c4a6e"))

        # Template upload
        with me.box(style=me.Style(width="100%")):
            me.text(
                "Slide Template (Optional .pptx)",
                style=me.Style(font_size=14, color="#475569", margin=me.Margin(bottom=8)),
            )
            me.uploader(
                label="Upload Template",
                accepted_file_types=[".pptx"],
                on_upload=handle_template_upload,
                type="stroked",
                style=me.Style(font_weight="500"),
            )

        if state.template_filename:
            with me.box(
                style=me.Style(
                    background="#faf5ff",
                    padding=me.Padding.all(12),
                    border_radius=8,
                    display="flex",
                    align_items="center",
                    gap=8,
                )
            ):
                me.icon("slideshow", style=me.Style(color="#9333ea"))
                me.text(state.template_filename, style=me.Style(font_size=14, color="#6b21a8"))

        # Topic input + suggestions
        with me.box(style=me.Style(width="100%")):
            me.input(
                label="Chủ đề mong muốn (Tùy chọn)",
                on_blur=handle_topic_input,
                style=me.Style(width="100%"),
                value=state.user_topic,
            )
            me.text(
                "Gợi ý chủ đề:",
                style=me.Style(font_size=12, color="#94a3b8", margin=me.Margin(top=12, bottom=8), font_weight=500),
            )
            _topic_suggestions(state)

        # Custom instructions
        with me.box(style=me.Style(width="100%", margin=me.Margin(top=24))):
            me.textarea(
                label="Hướng dẫn đặc biệt cho AI (Tùy chọn)",
                placeholder="Ví dụ: Chỉ tập trung vào chương 2...",
                on_blur=handle_user_instruction,
                value=state.user_instructions,
                rows=3,
                style=me.Style(width="100%"),
            )

        # Detail checkbox
        with me.box(style=me.Style(width="100%", margin=me.Margin(top=24))):
            me.checkbox(label="Chế độ Chi tiết (Deep Dive)", checked=state.is_detailed, on_change=on_detail_change)
            me.text(
                "Deep Dive: tạo nhiều slide / phân tích sâu hơn.",
                style=me.Style(font_size=12, color="#64748b", margin=me.Margin(top=4, left=32)),
            )

        # Provider config panel
        _provider_config(state)

        # Action buttons
        _action_buttons(state)


def _topic_suggestions(state: State) -> None:
    suggestions = [
        "Kế hoạch kinh doanh",
        "Báo cáo thị trường",
        "Giáo án điện tử",
        "Hồ sơ năng lực",
        "Startup Pitch",
        "Phân tích tài chính",
    ]
    with me.box(style=me.Style(display="flex", flex_wrap="wrap", gap=8)):
        for topic in suggestions:
            sel = state.user_topic == topic
            me.button(
                topic,
                key=topic,
                on_click=set_topic,
                type="stroked" if not sel else "flat",
                color="primary" if sel else "warn",
                style=me.Style(
                    font_size=12,
                    border_radius=20,
                    color="#2563eb" if sel else "#64748b",
                    border=me.Border.all(me.BorderSide(width=1, color="#2563eb" if sel else "#cbd5e1")),
                    background="#eff6ff" if sel else "#ffffff",
                    padding=me.Padding.symmetric(vertical=4, horizontal=12),
                ),
            )


def _provider_config(state: State) -> None:
    with me.box(
        style=me.Style(
            width="100%",
            margin=me.Margin(top=24),
            padding=me.Padding.all(16),
            background="#f8fafc",
            border_radius=8,
            border=me.Border.all(me.BorderSide(width=1, color="#e2e8f0")),
        )
    ):
        me.text(
            "AI Provider", style=me.Style(font_size=14, font_weight=600, color="#1e293b", margin=me.Margin(bottom=8))
        )
        me.select(
            label="Chọn AI Provider",
            options=[
                me.SelectOption(label="Google Gemini (Mặc định)", value="gemini"),
                me.SelectOption(label="OpenAI (GPT-4o, o4-mini, ...)", value="openai"),
                me.SelectOption(label="Anthropic (Claude Sonnet/Haiku)", value="anthropic"),
                me.SelectOption(label="Local LLM - Ollama (Miễn phí)", value="ollama"),
                me.SelectOption(label="LiteLLM (100+ providers)", value="litellm"),
            ],
            value=state.ai_provider,
            on_selection_change=on_provider_change,
            style=me.Style(width="100%", margin=me.Margin(bottom=16)),
        )

        if state.ai_provider == "openai":
            with me.box(
                style=me.Style(
                    background="#fef3c7", padding=me.Padding.all(12), border_radius=8, margin=me.Margin(bottom=12)
                )
            ):
                me.text("OpenAI yêu cầu API Key có billing.", style=me.Style(font_size=12, color="#92400e"))
            me.input(
                label="OpenAI API Key(s) (cách nhau dấu phẩy)",
                value=state.openai_api_keys_input,
                on_blur=handle_openai_keys_input,
                type="password",
                style=me.Style(width="100%", margin=me.Margin(bottom=12)),
            )

        if state.ai_provider == "ollama":
            with me.box(
                style=me.Style(
                    background="#d1fae5", padding=me.Padding.all(12), border_radius=8, margin=me.Margin(bottom=12)
                )
            ):
                me.text("🟢 Ollama chạy local, hoàn toàn miễn phí.", style=me.Style(font_size=12, color="#065f46"))
                me.text(
                    "Models: qwen2.5:72b, gemma3:27b, qwen2.5-coder:32b, deepseek-coder-v2, qwen2.5:14b",
                    style=me.Style(font_size=11, color="#047857", margin=me.Margin(top=4)),
                )
            me.input(
                label="Ollama Base URL",
                value=state.ollama_base_url,
                on_blur=handle_ollama_url_input,
                style=me.Style(width="100%", margin=me.Margin(bottom=12)),
            )

        if state.ai_provider == "gemini":
            me.checkbox(
                label="Sử dụng nhiều API Key (Dự phòng)", checked=state.use_multi_key, on_change=on_multi_key_change
            )
            if state.use_multi_key:
                me.text(
                    "Mỗi key một dòng hoặc cách nhau dấu phẩy",
                    style=me.Style(font_size=12, color="#64748b", margin=me.Margin(top=8, bottom=8)),
                )
                me.input(
                    label="Paste Gemini API Keys",
                    value=state.user_api_keys_input,
                    on_blur=handle_api_keys_input,
                    type="password",
                    style=me.Style(width="100%"),
                )


def _action_buttons(state: State) -> None:
    is_loading = state.processing_status in (
        "analyzing",
        "generating",
        "analyzing_summary",
        "analyzing_review",
        "generating_pdf",
    )
    is_disabled = is_loading or not state.uploaded_filename

    # Generate Slides
    _action_box(
        generate_slides if not is_disabled else None,
        "Generate Slides",
        bg="#e2e8f0" if is_disabled else "#2563eb",
        color="#94a3b8" if is_disabled else "#000000",
        disabled=is_disabled,
        margin_top=32,
    )

    # Generate Summary
    border_c = "#ea580c" if not is_disabled else "#fed7aa"
    _action_box(
        generate_summary if not is_disabled else None,
        "Generate Summary (PDF)",
        bg="transparent",
        color=border_c,
        border_color=border_c,
        disabled=is_disabled,
        margin_top=16,
    )

    # Language selector + Expert Review
    with me.box(style=me.Style(margin=me.Margin(top=16))):
        me.text("Ngôn ngữ Review:", style=me.Style(font_size=12, color="#64748b", margin=me.Margin(bottom=4)))
        me.select(
            label="Chọn ngôn ngữ",
            options=[
                me.SelectOption(label="Tiếng Việt (Vietnamese)", value="Tiếng Việt"),
                me.SelectOption(label="Tiếng Anh (English)", value="English"),
            ],
            value=state.review_language,
            on_selection_change=on_language_change,
            style=me.Style(width="100%"),
        )

    rev_c = "#7c3aed" if not is_disabled else "#ddd6fe"
    _action_box(
        generate_review if not is_disabled else None,
        "Generate Expert Review",
        bg="transparent",
        color=rev_c,
        border_color=rev_c,
        disabled=is_disabled,
        margin_top=12,
    )


def _action_box(
    on_click, text: str, *, bg: str, color: str, border_color: str | None = None, disabled: bool, margin_top: int
) -> None:
    style_kwargs: dict = dict(
        width="100%",
        padding=me.Padding.symmetric(vertical=16),
        margin=me.Margin(top=margin_top),
        background=bg,
        border_radius=8,
        cursor="not-allowed" if disabled else "pointer",
        display="flex",
        justify_content="center",
        align_items="center",
    )
    if border_color:
        style_kwargs["border"] = me.Border.all(me.BorderSide(width=1, color=border_color))
    if not disabled and not border_color:
        style_kwargs["box_shadow"] = "0 2px 4px rgba(0,0,0,0.1)"

    with me.box(on_click=on_click, style=me.Style(**style_kwargs)):
        me.text(text, style=me.Style(color=color, font_size=16, font_weight="bold", text_align="center", z_index=10))


# ── Right Column: Output ────────────────────────────────────────────────


def _right_column(state: State) -> None:
    with me.box(
        style=me.Style(
            background="#ffffff",
            padding=me.Padding.all(24),
            border_radius=16,
            box_shadow="0 4px 6px -1px rgb(0 0 0 / 0.1)",
            display="flex",
            flex_direction="column",
            gap=24,
        )
    ):
        me.text("Status & Output", style=me.Style(font_size=18, font_weight=600, color="#1e293b"))
        _logs_area(state)

        if state.show_cancel_dialog:
            _cancel_dialog()

        if state.error_message:
            _error_box(state)

        if state.processing_status == "done":
            _download_pptx(state)
        if state.processing_status == "summary_done":
            _download_pdf(state, "Summary", "#fff7ed", "#fdba74", "#ea580c", "#9a3412", "description")
        if state.processing_status == "review_done":
            _download_pdf(state, "Expert Review", "#f5f3ff", "#c4b5fd", "#7c3aed", "#5b21b6", "auto_stories")


def _logs_area(state: State) -> None:
    with me.box(
        style=me.Style(
            background="#f1f5f9",
            flex_grow=1,
            border_radius=8,
            padding=me.Padding.all(16),
            overflow_y="auto",
            font_family="'JetBrains Mono', 'Fira Code', monospace",
        )
    ):
        if not state.logs:
            me.text("Waiting for input...", style=me.Style(color="#94a3b8", font_style="italic"))
        for log in state.logs:
            colour = _log_colour(log)
            me.text(f"> {log}", style=me.Style(color=colour, font_size=12, margin=me.Margin(bottom=6)))

        _progress_indicator(state)


def _log_colour(text: str) -> str:
    """Return a colour based on log content for visual scanning."""
    if "❌" in text or "Lỗi" in text or "ERROR" in text:
        return "#dc2626"
    if "⚠️" in text or "WARNING" in text:
        return "#d97706"
    if "✅" in text or "hoàn tất" in text.lower() or "completed" in text.lower():
        return "#059669"
    if "🟢" in text or "🔑" in text:
        return "#2563eb"
    if "🔄" in text:
        return "#7c3aed"
    if text.startswith("> Source:") or text.startswith("> Model"):
        return "#6366f1"
    return "#334155"


def _progress_indicator(state: State) -> None:
    status_map = {
        "analyzing": ("Reading & Analyzing Document...", "#2563eb", "auto_stories"),
        "generating": ("Designing Slides...", "#7c3aed", "slideshow"),
        "analyzing_summary": ("Summarizing Content...", "#ea580c", "summarize"),
        "analyzing_review": ("Expert Review in Progress (3-Step Agent Pipeline)...", "#7c3aed", "psychology"),
        "generating_pdf": ("Rendering PDF...", "#db2777", "picture_as_pdf"),
    }
    item = status_map.get(state.processing_status)
    if item:
        label, colour, icon_name = item
        with me.box(
            style=me.Style(
                display="flex",
                align_items="center",
                gap=12,
                margin=me.Margin(top=16),
                background="#f0f9ff",
                padding=me.Padding.all(12),
                border_radius=8,
                border=me.Border.all(me.BorderSide(width=1, color="#bfdbfe")),
            )
        ):
            me.progress_spinner(diameter=20, stroke_width=2)
            me.icon(icon_name, style=me.Style(color=colour, font_size=20))
            me.text(label, style=me.Style(color=colour, font_weight=600, font_size=14))
        with me.box(style=me.Style(margin=me.Margin(left=16, top=8))):
            me.button("Hủy lệnh", on_click=request_cancel, color="warn", type="stroked")


def _cancel_dialog() -> None:
    with (
        me.box(
            style=me.Style(
                position="fixed",
                top=0,
                left=0,
                right=0,
                bottom=0,
                background="rgba(0,0,0,0.5)",
                z_index=1000,
                display="flex",
                justify_content="center",
                align_items="center",
            )
        ),
        me.box(
            style=me.Style(
                background="white",
                padding=me.Padding.all(24),
                border_radius=12,
                width="400px",
                box_shadow="0 10px 15px -3px rgba(0, 0, 0, 0.1)",
            )
        ),
    ):
        me.text("Xác nhận hủy", style=me.Style(font_size=20, font_weight="bold", margin=me.Margin(bottom=16)))
        me.text("Bạn có chắc muốn hủy lệnh đang chạy?", style=me.Style(margin=me.Margin(bottom=24), color="#4b5563"))
        with me.box(style=me.Style(display="flex", justify_content="flex-end", gap=16)):
            me.button("Không, quay lại", on_click=dismiss_cancel)
            me.button("Có, Hủy ngay", on_click=confirm_cancel, color="warn")


def _error_box(state: State) -> None:
    with me.box(
        style=me.Style(
            background="#fef2f2",
            padding=me.Padding.all(12),
            border_radius=8,
            border=me.Border.all(me.BorderSide(width=1, color="#fecaca")),
        )
    ):
        me.text(f"Error: {state.error_message}", style=me.Style(color="#991b1b", font_size=14))
        if state.resume_data:
            with me.box(style=me.Style(margin=me.Margin(top=12), display="flex", align_items="center", gap=12)):
                me.button(
                    "🔄 Chạy tiếp (Resume)",
                    on_click=resume_review,
                    color="primary",
                    type="flat",
                    style=me.Style(font_weight="bold"),
                )
                me.text(
                    "Giữ lại tiến độ, chỉ chạy lại phần lỗi.",
                    style=me.Style(font_size=12, color="#7f1d1d", font_style="italic"),
                )


def _download_pptx(state: State) -> None:
    with me.box(
        style=me.Style(
            background="#ecfdf5",
            padding=me.Padding.all(24),
            border_radius=12,
            border=me.Border.all(me.BorderSide(width=1, color="#6ee7b7")),
            display="flex",
            flex_direction="column",
            align_items="center",
            gap=16,
            text_align="center",
        )
    ):
        me.icon("check_circle", style=me.Style(color="#059669", font_size=48))
        me.text("Presentation Ready!", style=me.Style(font_size=20, font_weight=600, color="#065f46"))
        data_uri = f"data:application/vnd.openxmlformats-officedocument.presentationml.presentation;base64,{state.pptx_content_base64}"
        me.html(
            f'<a href="{data_uri}" download="{state.pptx_filename}" '
            'style="display:inline-block;background:#0284c7;color:white;padding:12px 24px;'
            'text-decoration:none;border-radius:8px;font-weight:600;font-family:Inter,sans-serif;">'
            "Download PowerPoint</a>"
        )
        me.button(
            "Create Another",
            on_click=lambda e: setattr(state, "processing_status", "idle"),
            style=me.Style(margin=me.Margin(top=16)),
        )


def _download_pdf(state: State, label: str, bg: str, border_c: str, btn_c: str, txt_c: str, icon_name: str) -> None:
    with me.box(
        style=me.Style(
            background=bg,
            padding=me.Padding.all(24),
            border_radius=12,
            border=me.Border.all(me.BorderSide(width=1, color=border_c)),
            display="flex",
            flex_direction="column",
            align_items="center",
            gap=16,
            text_align="center",
        )
    ):
        me.icon(icon_name, style=me.Style(color=btn_c, font_size=48))
        me.text(f"{label} Ready!", style=me.Style(font_size=20, font_weight=600, color=txt_c))
        data_uri = f"data:application/pdf;base64,{state.pdf_content_base64}"
        me.html(
            f'<a href="{data_uri}" download="{state.pdf_filename}" '
            f'style="display:inline-block;background:{btn_c};color:white;padding:12px 24px;'
            'text-decoration:none;border-radius:8px;font-weight:600;font-family:Inter,sans-serif;">'
            f"Download {label} PDF</a>"
        )
        me.button(
            "Start Over",
            on_click=lambda e: setattr(state, "processing_status", "idle"),
            style=me.Style(margin=me.Margin(top=16)),
        )
