"""Mesop event handlers — on_load, uploads, generation flows, cancel.

All async generators that drive the progress UI live here.

v2.1 — Async optimisations:
  • Shared ``ThreadPoolExecutor`` (bounded, reused across requests)
  • Per-request ``CancelToken`` (safe under concurrent users)
  • ``run_in_executor`` helper for clean ``await`` syntax
  • PDF/PPTX rendering offloaded to thread pool
"""

from __future__ import annotations

import asyncio
import base64
import contextlib
import logging
import os
import re
import tempfile

import mesop as me

from app.config import settings
from app.core.cancellation import CancelToken, clear_cancel_signal, set_cancel_signal
from app.core.executor import get_executor, run_in_executor
from app.core.log import safe_print
from app.providers.ollama import OllamaProvider
from app.rendering.pdf import save_summary_to_pdf
from app.rendering.pptx import create_pptx
from app.services.review import PartialCompletionError, review_book_syntopic
from app.services.slide import analyze_document
from app.services.summary import summarize_book_deep_dive, summarize_document
from app.ui.state import State

# ── Lifecycle ────────────────────────────────────────────────────────────


def on_load(e: me.LoadEvent) -> None:
    me.set_theme_mode("system")
    state = me.state(State)
    state.error_message = ""
    state.processing_status = "idle"
    if state.logs is None:
        state.logs = []
    state.logs.append("Hệ thống đã khởi động. Sẵn sàng xử lý.")

    # Auto-detect provider
    if not state.ai_provider:
        ollama_url = os.environ.get("OLLAMA_BASE_URL", "")
        if ollama_url:
            ollama = OllamaProvider(base_url=ollama_url)
            if ollama.check_connectivity():
                state.ai_provider = "ollama"
                state.logs.append("🟢 Auto-detected Ollama server. Sử dụng Local LLM (miễn phí).")
            elif os.environ.get("GOOGLE_API_KEY"):
                state.ai_provider = "gemini"
            else:
                state.ai_provider = "ollama"
                state.logs.append("⚠️ Ollama server không phản hồi. Kiểm tra server đang chạy chưa.")
        elif os.environ.get("GOOGLE_API_KEY"):
            state.ai_provider = "gemini"
            state.logs.append("🔑 Sử dụng Google Gemini API.")
        elif os.environ.get("OPENAI_API_KEY"):
            state.ai_provider = "openai"
            state.logs.append("🔑 Sử dụng OpenAI API.")
        else:
            state.ai_provider = "ollama"
            state.logs.append("⚠️ Không tìm thấy API Key. Mặc định dùng Ollama (Local LLM).")


# ── Simple input handlers ────────────────────────────────────────────────


def handle_upload(event: me.UploadEvent) -> None:
    state = me.state(State)
    file = event.file
    file_bytes = file.read()
    size_mb = len(file_bytes) / (1024 * 1024)
    if size_mb > settings.max_upload_size_mb:
        state.error_message = f"File quá lớn ({size_mb:.1f} MB). Giới hạn: {settings.max_upload_size_mb} MB."
        return
    state.uploaded_file_bytes = file_bytes
    state.uploaded_mime_type = file.mime_type
    state.uploaded_filename = file.name
    state.logs = [f"Đã tải lên: {file.name}", "System: Console Output Suppressed (v3)"]
    state.processing_status = "ready"
    state.error_message = ""


def handle_topic_input(e: me.InputEvent) -> None:
    me.state(State).user_topic = e.value


def handle_template_upload(event: me.UploadEvent) -> None:
    state = me.state(State)
    state.template_file_bytes = event.file.read()
    state.template_filename = event.file.name
    state.logs.append(f"Đã tải lên mẫu: {event.file.name}")


def on_detail_change(e: me.CheckboxChangeEvent) -> None:
    me.state(State).is_detailed = e.checked


def on_multi_key_change(e: me.CheckboxChangeEvent) -> None:
    me.state(State).use_multi_key = e.checked


def on_language_change(e: me.SelectSelectionChangeEvent) -> None:
    me.state(State).review_language = e.value


def on_provider_change(e: me.SelectSelectionChangeEvent) -> None:
    me.state(State).ai_provider = e.value


def handle_openai_keys_input(e: me.InputEvent) -> None:
    me.state(State).openai_api_keys_input = e.value


def handle_ollama_url_input(e: me.InputEvent) -> None:
    me.state(State).ollama_base_url = e.value


def handle_api_keys_input(e: me.InputEvent) -> None:
    me.state(State).user_api_keys_input = e.value


def handle_user_instruction(e: me.InputEvent) -> None:
    me.state(State).user_instructions = e.value


def set_topic(e: me.ClickEvent) -> None:
    me.state(State).user_topic = e.key


# ── Cancel flow ──────────────────────────────────────────────────────────


async def request_cancel(e: me.ClickEvent):
    state = me.state(State)
    state.show_cancel_dialog = True
    yield


def dismiss_cancel(e: me.ClickEvent) -> None:
    me.state(State).show_cancel_dialog = False


# ── Active cancel token (per-request, set from generation flows) ──────────
_active_token: CancelToken | None = None


def confirm_cancel(e: me.ClickEvent) -> None:
    state = me.state(State)
    state.show_cancel_dialog = False
    state.cancel_requested = True
    set_cancel_signal()
    if _active_token is not None:
        _active_token.cancel()
    state.logs.append("⚠️ Đang yêu cầu hủy bỏ... Vui lòng đợi bước hiện tại hoàn tất.")


# ── Key resolution helper ────────────────────────────────────────────────


def _resolve_api_keys(state: State) -> tuple[list[str], str]:
    """Return ``(api_keys_list, provider_name)`` derived from state."""
    provider = state.ai_provider or "gemini"

    if provider == "openai":
        keys: list[str] = []
        if state.openai_api_keys_input:
            keys = [k.strip() for k in re.split(r"[,\n\r]+", state.openai_api_keys_input) if k.strip()]
        env = os.environ.get("OPENAI_API_KEY")
        if env and env not in keys:
            keys.append(env)
        return keys, provider

    if provider == "ollama":
        base_url = state.ollama_base_url or settings.ollama_base_url
        return [base_url], provider

    # Gemini
    keys = []
    env = os.environ.get("GOOGLE_API_KEY")
    if state.use_multi_key and state.user_api_keys_input:
        keys = [k.strip() for k in re.split(r"[,\n\r]+", state.user_api_keys_input) if k.strip()]
    if env and env not in keys:
        keys.append(env)
    return keys, provider


def _generate_pdf_and_store(state: State, data: dict, suffix: str) -> None:
    """Render PDF, encode to base64, store on *state*.

    Called from within the thread pool, so all I/O is non-blocking to the UI.
    """
    name_no_ext = state.uploaded_filename.rsplit(".", 1)[0]
    safe_name = re.sub(r"[^\w\s\-.]", "", name_no_ext)
    pdf_out_name = f"{safe_name}_{suffix}.pdf"

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp_path = tmp.name

    final_path = save_summary_to_pdf(data, tmp_path)
    with open(final_path, "rb") as f:
        state.pdf_content_base64 = base64.b64encode(f.read()).decode("utf-8")
    state.pdf_filename = pdf_out_name
    with contextlib.suppress(Exception):
        os.remove(final_path)
    state.logs.append(f"Đã tạo xong file: {state.pdf_filename}")


async def _poll_future(future, token: CancelToken, state: State):
    """Poll a future with cancel checks, yielding for Mesop UI updates.

    Returns the future result, or None if cancelled.
    """
    while not future.done():
        if token.is_set() or me.state(State).cancel_requested:
            state.processing_status = "idle"
            state.logs.append("❌ Đã hủy bỏ lệnh.")
            future.cancel()
            yield None
            return
        yield  # let Mesop re-render
        await asyncio.sleep(0.3)
    yield future.result()


# ── Async generation flows ──────────────────────────────────────────────


async def generate_summary(e: me.ClickEvent):
    global _active_token
    state = me.state(State)
    state.error_message = ""
    state.cancel_requested = False
    token = CancelToken()
    _active_token = token
    clear_cancel_signal()
    yield

    if not state.uploaded_file_bytes:
        state.error_message = "Vui lòng tải lên file tài liệu trước."
        yield
        return

    state.processing_status = "analyzing_summary"
    api_keys_list, provider = _resolve_api_keys(state)
    label = {"openai": "OpenAI", "ollama": "Ollama (Local)"}.get(provider, "Gemini")
    state.logs.append(f"Source: {state.uploaded_filename} | Provider: {label}")
    state.logs.append(f"Đang tóm tắt tài liệu với {label}...")
    yield

    if token.is_set():
        state.processing_status = "idle"
        state.logs.append("❌ Đã hủy bỏ lệnh.")
        yield
        return

    try:
        executor = get_executor()
        if state.is_detailed:
            state.logs.append("Đang chạy chế độ Deep Dive...")
            yield
            future = executor.submit(
                summarize_book_deep_dive,
                state.uploaded_file_bytes,
                state.uploaded_mime_type,
                api_keys=api_keys_list,
                cancel_check=token.is_set,
                provider=provider,
            )
        else:
            future = executor.submit(
                summarize_document,
                state.uploaded_file_bytes,
                state.uploaded_mime_type,
                api_keys=api_keys_list,
                user_instructions=state.user_instructions,
                cancel_check=token.is_set,
                provider=provider,
            )

        while not future.done():
            if token.is_set() or me.state(State).cancel_requested:
                state.processing_status = "idle"
                state.logs.append("❌ Đã hủy bỏ lệnh.")
                future.cancel()
                yield
                return
            yield
            await asyncio.sleep(0.3)

        summary_data = future.result()

        if not summary_data:
            raise Exception("Empty result from executor")

        if "used_model" in summary_data:
            state.logs.append(f"Model used: {summary_data['used_model']}")

        state.logs.append("Tóm tắt hoàn tất. Đang tạo PDF...")
        state.processing_status = "generating_pdf"
        yield

        if token.is_set():
            state.processing_status = "idle"
            state.logs.append("❌ Đã hủy bỏ lệnh.")
            yield
            return

        # Offload PDF rendering to thread pool
        await run_in_executor(_generate_pdf_and_store, state, summary_data, "summary")
        state.processing_status = "summary_done"
        yield
    except Exception as ex:
        safe_print(f"MAIN EXCEPTION: {ex}", logging.ERROR)
        state.processing_status = "error"
        state.error_message = str(ex)
        state.logs.append(f"Lỗi: {ex}")
        yield
    finally:
        _active_token = None


async def generate_slides(e: me.ClickEvent):
    global _active_token
    state = me.state(State)
    state.error_message = ""
    state.cancel_requested = False
    token = CancelToken()
    _active_token = token
    clear_cancel_signal()
    yield

    if not state.uploaded_file_bytes:
        state.error_message = "Vui lòng tải lên file tài liệu trước."
        yield
        return

    state.processing_status = "analyzing"
    api_keys_list, provider = _resolve_api_keys(state)
    label = {"openai": "OpenAI", "ollama": "Ollama (Local)"}.get(provider, "Gemini")
    state.logs.append(f"Source: {state.uploaded_filename} | Provider: {label}")
    if state.template_filename:
        state.logs.append(f"Template: {state.template_filename}")
    detail_mode = "Chi tiết" if state.is_detailed else "Tóm tắt"
    state.logs.append(f"Đang phân tích tài liệu ({detail_mode})...")
    yield

    if token.is_set():
        state.processing_status = "idle"
        state.logs.append("❌ Đã hủy bỏ lệnh.")
        yield
        return

    try:
        executor = get_executor()
        future = executor.submit(
            analyze_document,
            state.uploaded_file_bytes,
            state.uploaded_mime_type,
            api_keys=api_keys_list,
            detail_level=detail_mode,
            user_instructions=state.user_instructions,
            cancel_check=token.is_set,
            provider=provider,
        )

        while not future.done():
            if token.is_set() or me.state(State).cancel_requested:
                state.processing_status = "idle"
                state.logs.append("❌ Đã hủy bỏ lệnh.")
                future.cancel()
                yield
                return
            yield
            await asyncio.sleep(0.3)

        slide_json = future.result()

        if not slide_json:
            raise Exception("AI không trả về dữ liệu slide.")

        state.logs.append("Phân tích hoàn tất. Đang tạo slide...")
        state.processing_status = "generating"
        yield

        if token.is_set():
            state.processing_status = "idle"
            state.logs.append("❌ Đã hủy bỏ lệnh.")
            yield
            return

        # Offload PPTX rendering to thread pool
        pptx_io = await run_in_executor(
            create_pptx,
            slide_json,
            template_pptx_bytes=state.template_file_bytes if state.template_file_bytes else None,
        )
        pptx_bytes = pptx_io.read()
        name_no_ext = state.uploaded_filename.rsplit(".", 1)[0]
        safe_name = re.sub(r"[^\w\s\-.]", "", name_no_ext)
        state.pptx_filename = f"{safe_name}_presentation.pptx"
        state.pptx_content_base64 = base64.b64encode(pptx_bytes).decode("utf-8")
        state.logs.append(f"Đã tạo xong file: {state.pptx_filename}")
        state.processing_status = "done"
        yield
    except Exception as ex:
        safe_print(f"MAIN EXCEPTION: {ex}", logging.ERROR)
        state.processing_status = "error"
        state.error_message = str(ex)
        state.logs.append(f"Lỗi: {ex}")
        yield
    finally:
        _active_token = None


async def generate_review(e: me.ClickEvent):
    global _active_token
    state = me.state(State)
    state.error_message = ""
    state.cancel_requested = False
    state.resume_data = {}
    token = CancelToken()
    _active_token = token
    clear_cancel_signal()
    yield

    if not state.uploaded_file_bytes:
        state.error_message = "Vui lòng tải lên file tài liệu trước."
        yield
        return

    state.processing_status = "analyzing_review"
    api_keys_list, provider = _resolve_api_keys(state)
    label = {"openai": "OpenAI", "ollama": "Ollama (Local)"}.get(provider, "Gemini")
    state.logs.append(f"Source: {state.uploaded_filename} | Provider: {label}")
    state.logs.append("Đang chạy Syntopic Book Review (3 Agents)...")
    yield

    if token.is_set():
        state.processing_status = "idle"
        state.logs.append("❌ Đã hủy bỏ lệnh.")
        yield
        return

    try:
        executor = get_executor()
        future = executor.submit(
            review_book_syntopic,
            state.uploaded_file_bytes,
            state.uploaded_mime_type,
            api_keys=api_keys_list,
            language=state.review_language,
            cancel_check=token.is_set,
            provider=provider,
        )

        while not future.done():
            if token.is_set() or me.state(State).cancel_requested:
                state.processing_status = "idle"
                state.logs.append("❌ Đã hủy bỏ lệnh.")
                future.cancel()
                yield
                return
            yield
            await asyncio.sleep(0.3)

        review_data = future.result()

        if "used_model" in review_data:
            state.logs.append(f"Model used: {review_data['used_model']}")

        state.logs.append("Review hoàn tất. Đang tạo PDF...")
        state.processing_status = "generating_pdf"
        yield

        if token.is_set():
            state.processing_status = "idle"
            yield
            return

        # Offload PDF rendering to thread pool
        await run_in_executor(_generate_pdf_and_store, state, review_data, "expert_review")
        state.processing_status = "review_done"
        yield

    except PartialCompletionError as partial_ex:
        safe_print(f"PARTIAL ERROR: {partial_ex}", logging.WARNING)
        state.processing_status = "error"
        state.error_message = f"{partial_ex} (Có thể tiếp tục)"
        state.resume_data = partial_ex.partial_data
        state.logs.append(f"⚠️ Lỗi một phần: {partial_ex}. Dữ liệu đã lưu để tiếp tục.")
        yield
    except Exception as ex:
        safe_print(f"MAIN EXCEPTION: {ex}", logging.ERROR)
        state.processing_status = "error"
        state.error_message = str(ex)
        state.logs.append(f"Lỗi Review: {ex}")
        yield
    finally:
        _active_token = None


async def resume_review(e: me.ClickEvent):
    global _active_token
    state = me.state(State)
    if not state.resume_data:
        state.error_message = "Không có dữ liệu để tiếp tục."
        yield
        return

    state.error_message = ""
    state.cancel_requested = False
    token = CancelToken()
    _active_token = token
    clear_cancel_signal()
    yield

    state.processing_status = "analyzing_review"
    state.logs.append("🔄 Đang tiếp tục xử lý (Resume)...")
    yield

    if token.is_set():
        state.processing_status = "idle"
        state.logs.append("❌ Đã hủy bỏ lệnh.")
        yield
        return

    try:
        api_keys_list, provider = _resolve_api_keys(state)
        executor = get_executor()
        future = executor.submit(
            review_book_syntopic,
            state.uploaded_file_bytes,
            state.uploaded_mime_type,
            api_keys=api_keys_list,
            language=state.review_language,
            cancel_check=token.is_set,
            resume_state=state.resume_data,
            provider=provider,
        )

        while not future.done():
            if token.is_set() or me.state(State).cancel_requested:
                state.processing_status = "idle"
                state.logs.append("❌ Đã hủy bỏ lệnh.")
                future.cancel()
                yield
                return
            yield
            await asyncio.sleep(0.3)

        review_data = future.result()

        if "used_model" in review_data:
            state.logs.append(f"Model used: {review_data['used_model']}")

        state.logs.append("Review hoàn tất. Đang tạo PDF...")
        state.processing_status = "generating_pdf"
        state.resume_data = {}
        yield

        if token.is_set():
            state.processing_status = "idle"
            yield
            return

        await run_in_executor(_generate_pdf_and_store, state, review_data, "expert_review")
        state.processing_status = "review_done"
        yield

    except PartialCompletionError as partial_ex:
        safe_print(f"PARTIAL ERROR (RESUME): {partial_ex}", logging.WARNING)
        state.processing_status = "error"
        state.error_message = f"{partial_ex} (Có thể tiếp tục)"
        state.resume_data = partial_ex.partial_data
        state.logs.append(f"⚠️ Lại gặp lỗi: {partial_ex}. Đã cập nhật điểm dừng.")
        yield
    except Exception as ex:
        safe_print(f"MAIN EXCEPTION: {ex}", logging.ERROR)
        state.processing_status = "error"
        state.error_message = str(ex)
        state.logs.append(f"Lỗi Review: {ex}")
        yield
    finally:
        _active_token = None
