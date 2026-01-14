import os
# Patch IO immediately to prevent Windows console crashes
# Patch IO immediately to prevent Windows console crashes
from utils import suppress_console_output, safe_print
# suppress_console_output()

import base64
import mesop as me
import mesop.labs as mel
from dataclasses import field
from dotenv import load_dotenv
from ai_engine import analyze_document
from slide_engine import create_pptx
import concurrent.futures
import time
import asyncio


# Re-import functions to update references
from ai_engine import analyze_document
from summarizer import summarize_document_v2, save_summary_to_pdf, summarize_book_deep_dive, review_book_syntopic, PartialCompletionError


load_dotenv()

# Global Cancellation Flag
GLOBAL_CANCEL_FLAG = False
CANCEL_SIGNAL_FILE = "cancel_signal.flag"

def set_cancel_signal():
    global GLOBAL_CANCEL_FLAG
    GLOBAL_CANCEL_FLAG = True
    with open(CANCEL_SIGNAL_FILE, "w") as f:
        f.write("CANCEL")

def clear_cancel_signal():
    global GLOBAL_CANCEL_FLAG
    GLOBAL_CANCEL_FLAG = False
    if os.path.exists(CANCEL_SIGNAL_FILE):
        os.remove(CANCEL_SIGNAL_FILE)

def check_cancel_signal():
    return os.path.exists(CANCEL_SIGNAL_FILE) or GLOBAL_CANCEL_FLAG

@me.stateclass
class State:
    # Processing State
    processing_status: str = "idle" # idle, analyzing, generating, done, error
    logs: list[str] = field(default_factory=list)
    error_message: str = ""
    
    # Input Data
    uploaded_file_bytes: bytes = b""
    uploaded_mime_type: str = ""
    uploaded_filename: str = ""
    user_topic: str = ""
    
    # Template Data
    template_file_bytes: bytes = b""
    template_filename: str = ""
    
    # Output Data
    pptx_filename: str = ""
    pptx_content_base64: str = ""
    
    # Summary Data
    pdf_filename: str = ""
    pdf_content_base64: str = ""
    
    # Detail Configuration
    is_detailed: bool = False
    
    # Custom Instructions
    # Custom Instructions
    user_instructions: str = ""
    
    # Cancellation State
    show_cancel_dialog: bool = False
    cancel_requested: bool = False

    # Advanced Config
    use_multi_key: bool = False
    user_api_keys_input: str = ""
    review_language: str = "Tiếng Việt"
    
    # Resume State
    resume_data: dict = field(default_factory=dict)

def on_load(e: me.LoadEvent):
    me.set_theme_mode("system")
    state = me.state(State)
    state.error_message = ""
    state.processing_status = "idle"
    # Ensure logs list exists
    if state.logs is None:
        state.logs = []
    state.logs.append("Hệ thống đã khởi động. Sẵn sàng xử lý.")

def handle_upload(event: me.UploadEvent):
    state = me.state(State)
    file = event.file
    
    # Store file in state
    state.uploaded_file_bytes = file.read()
    state.uploaded_mime_type = file.mime_type
    state.uploaded_filename = file.name
    
    # reset logs/status
    state.logs = [f"Đã tải lên: {file.name}", "System: Console Output Suppressed (v3)"]
    state.processing_status = "ready"
    state.error_message = ""

def handle_topic_input(e: me.InputEvent):
    state = me.state(State)
    state.user_topic = e.value

def handle_template_upload(event: me.UploadEvent):
    state = me.state(State)
    file = event.file
    
    # Store template in state
    state.template_file_bytes = file.read()
    state.template_filename = file.name
    
    state.logs.append(f"Đã tải lên mẫu: {file.name}")

def on_detail_change(e: me.CheckboxChangeEvent):
    state = me.state(State)
    state.is_detailed = e.checked

def on_multi_key_change(e: me.CheckboxChangeEvent):
    state = me.state(State)
    state.use_multi_key = e.checked

def on_language_change(e: me.SelectSelectionChangeEvent):
    state = me.state(State)
    state.review_language = e.value

def handle_api_keys_input(e: me.InputEvent):
    state = me.state(State)
    state.user_api_keys_input = e.value

def handle_user_instruction(e: me.InputEvent):
    state = me.state(State)
    state.user_instructions = e.value

def request_cancel(e: me.ClickEvent):
    state = me.state(State)
    print("DEBUG: Request Cancel Clicked") # Debug log
    state.show_cancel_dialog = True
    yield

def dismiss_cancel(e: me.ClickEvent):
    state = me.state(State)
    state.show_cancel_dialog = False

def confirm_cancel(e: me.ClickEvent):
    state = me.state(State)
    state.show_cancel_dialog = False
    state.cancel_requested = True
    set_cancel_signal() # Write to file
    state.logs.append("⚠️ Đang yêu cầu hủy bỏ... Vui lòng đợi bước hiện tại hoàn tất.")
    yield



async def generate_summary(e: me.ClickEvent):
    state = me.state(State)
    
    # 1. Clear Error & Set Status IMMEDIATE UPDATE
    state.error_message = ""
    state.cancel_requested = False 
    clear_cancel_signal() # Reset File Signal
    yield # FORCE UI UPDATE
    
    if not state.uploaded_file_bytes:
        state.error_message = "Vui lòng tải lên file tài liệu trước."
        yield
        return

    state.processing_status = "analyzing_summary"
    
    state.logs.append(f"Source Document: {state.uploaded_filename}")
    state.logs.append("Đang tóm tắt tài liệu với Gemini...")
    yield # Yield to update UI
    
    if state.cancel_requested or GLOBAL_CANCEL_FLAG:
        state.processing_status = "idle"
        state.logs.append("❌ Đã hủy bỏ lệnh.")
        yield
        return
        
    try:
        # 1. Summarize
        api_key_env = os.environ.get("GOOGLE_API_KEY")
        
        # Parse Multi-Key Input
        api_keys_list = []
        if state.use_multi_key and state.user_api_keys_input:
            import re
            # Split by comma or newline
            raw_keys = re.split(r'[,\n\r]+', state.user_api_keys_input)
            api_keys_list = [k.strip() for k in raw_keys if k.strip()]
            
            # Add default env key if exists
            if api_key_env and api_key_env not in api_keys_list:
                api_keys_list.append(api_key_env)
                
            if api_keys_list:
                state.logs.append(f"Using {len(api_keys_list)} API Keys (including default) with rotation.")
        
        # Run AI task in a separate thread
        executor = concurrent.futures.ThreadPoolExecutor()
        cancel_check_lambda = check_cancel_signal # Use file checker
        
        try:
            if state.is_detailed:
                state.logs.append("Đang chạy chế độ Deep Dive (4 bước)... Quá trình này có thể mất vài phút.")
                yield # Update UI
                
                future = executor.submit(
                    summarize_book_deep_dive,
                    state.uploaded_file_bytes,
                    state.uploaded_mime_type,
                    api_key=api_key_env,
                    api_keys=api_keys_list,
                    cancel_check=cancel_check_lambda
                )
            else:
                future = executor.submit(
                    summarize_document_v2,
                    state.uploaded_file_bytes, 
                    state.uploaded_mime_type, 
                    api_key=api_key_env,
                    api_keys=api_keys_list,
                    user_instructions=state.user_instructions,
                    cancel_check=cancel_check_lambda
                )
            
            # Poll loop
            while not future.done():
                if check_cancel_signal() or me.state(State).cancel_requested:
                    state.processing_status = "idle"
                    state.logs.append("❌ Đã hủy bỏ lệnh (Ngừng ngay lập tức).")
                    executor.shutdown(wait=False)
                    yield
                    return
                yield
                await asyncio.sleep(0.1)
                
            summary_data = future.result()
        finally:
            executor.shutdown(wait=False)

        if not summary_data:
             raise Exception("Result is None/Empty from executor (Possible silent failure)")

        if "used_model" in summary_data:
             state.logs.append(f"Model used: {summary_data['used_model']}")
        
        state.logs.append("Tóm tắt hoàn tất. Đang tạo file PDF...")
        state.processing_status = "generating_pdf"
        yield
        
        # Check Cancel again
        if me.state(State).cancel_requested:
             state.processing_status = "idle"
             state.logs.append("❌ Đã hủy bỏ lệnh.")
             yield
             return
        
        # 2. Generate PDF
        # Use a temporary filename
        import tempfile
        original_name = state.uploaded_filename
        name_no_ext = original_name.rsplit('.', 1)[0]
        pdf_out_name = f"{name_no_ext}_summary.pdf"
        
        # We need a temp path for reportlab to write to
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp_path = tmp.name
            
        final_path = save_summary_to_pdf(summary_data, tmp_path)
        
        with open(final_path, "rb") as f:
            pdf_bytes = f.read()
            
        state.pdf_content_base64 = base64.b64encode(pdf_bytes).decode('utf-8')
        state.pdf_filename = pdf_out_name
        
        # Cleanup
        try:
             os.remove(final_path)
        except:
             pass

        state.logs.append(f"Đã tạo xong file: {state.pdf_filename}")
        state.processing_status = "summary_done"
        yield

        yield
    except Exception as ex:
        safe_print(f"DEBUG MAIN EXCEPTION: {ex}") # Console log
        state.processing_status = "error"
        state.error_message = str(ex)
        state.logs.append(f"Lỗi hệ thống: {str(ex)}")
        yield


async def generate_slides(e: me.ClickEvent):
    state = me.state(State)

    # 1. Clear Error & Set Status IMMEDIATE UPDATE
    state.error_message = ""
    state.cancel_requested = False # Reset
    clear_cancel_signal()
    yield # FORCE UI UPDATE
    
    if not state.uploaded_file_bytes:
        state.error_message = "Vui lòng tải lên file tài liệu trước."
        yield
        return

    state.processing_status = "analyzing"
    
    state.logs.append(f"Source Document: {state.uploaded_filename}")
    if state.template_filename:
        state.logs.append(f"Using Template: {state.template_filename}")
        if state.template_filename == state.uploaded_filename:
             state.logs.append("Warning: Source and Template are the same file!")

    state.logs.append("Đang phân tích tài liệu với Gemini...")
    yield # Yield to update UI
    
    if state.cancel_requested or GLOBAL_CANCEL_FLAG:
        state.processing_status = "idle"
        state.logs.append("❌ Đã hủy bỏ lệnh.")
        yield
        return
    
    try:
        # 1. Analyze
        detail_mode = "Chi tiết" if state.is_detailed else "Tóm tắt"
        state.logs.append(f"Chế độ phân tích: {detail_mode}")
        
        if state.user_instructions:
            state.logs.append(f"Hướng dẫn người dùng: {state.user_instructions[:50]}...")

        # Explicitly pass API Key to avoid env var scope issues in sub-modules
        api_key_env = os.environ.get("GOOGLE_API_KEY")
        
        # Parse Multi-Key Input
        api_keys_list = []
        if state.use_multi_key and state.user_api_keys_input:
            import re
            # Split by comma or newline
            raw_keys = re.split(r'[,\n\r]+', state.user_api_keys_input)
            api_keys_list = [k.strip() for k in raw_keys if k.strip()]
            
            # Add default env key if exists
            if api_key_env and api_key_env not in api_keys_list:
                api_keys_list.append(api_key_env)

            if api_keys_list:
                state.logs.append(f"Using {len(api_keys_list)} API Keys (including default) with rotation.")

        # Run AI task in a separate thread
        executor = concurrent.futures.ThreadPoolExecutor()
        cancel_check_lambda = lambda: GLOBAL_CANCEL_FLAG
        try:
            future = executor.submit(
                analyze_document,
                state.uploaded_file_bytes, 
                state.uploaded_mime_type, 
                api_key=api_key_env,
                api_keys=api_keys_list,
                detail_level=detail_mode,
                user_instructions=state.user_instructions,
                cancel_check=cancel_check_lambda
            )
            
            # Poll loop
            while not future.done():
                if check_cancel_signal() or me.state(State).cancel_requested:
                    state.processing_status = "idle"
                    state.logs.append("❌ Đã hủy bỏ lệnh (Ngừng ngay lập tức).")
                    executor.shutdown(wait=False)
                    yield
                    return
                yield
                await asyncio.sleep(0.1)
            
            slide_json = future.result()
        finally:
            executor.shutdown(wait=False)

        state.logs.append("Phân tích hoàn tất. Đang tạo cấu trúc slide...")
        state.processing_status = "generating"
        yield
        
        if me.state(State).cancel_requested:
             state.processing_status = "idle"
             state.logs.append("❌ Đã hủy bỏ lệnh.")
             yield
             return
        
        # 2. Generate PPTX
        pptx_io = create_pptx(slide_json, template_pptx_bytes=state.template_file_bytes if state.template_file_bytes else None)
        pptx_bytes = pptx_io.read()
        
        # Prepare filename
        original_name = state.uploaded_filename
        name_no_ext = original_name.rsplit('.', 1)[0]
        state.pptx_filename = f"{name_no_ext}_presentation.pptx"
        
        state.pptx_content_base64 = base64.b64encode(pptx_bytes).decode('utf-8')
        state.logs.append(f"Đã tạo xong file: {state.pptx_filename}")
        state.processing_status = "done"
        yield

    except Exception as ex:
        safe_print(f"DEBUG MAIN EXCEPTION: {ex}")
        state.processing_status = "error"
        state.error_message = str(ex)
        state.logs.append(f"Lỗi: {str(ex)}")
        yield




async def generate_review(e: me.ClickEvent):
    global GLOBAL_CANCEL_FLAG
    state = me.state(State)
    
    # 1. Clear Error & Set Status IMMEDIATE UPDATE
    state.error_message = ""
    state.cancel_requested = False
    state.resume_data = {} # Clear previous resume data on fresh start
    clear_cancel_signal()
    yield # FORCE UI UPDATE
    
    if not state.uploaded_file_bytes:
        state.error_message = "Vui lòng tải lên file tài liệu trước."
        yield
        return

    state.processing_status = "analyzing_review"
    
    state.logs.append(f"Source Document: {state.uploaded_filename}")
    state.logs.append("Đang chạy Syntopic Book Review (3 Agents)...")
    yield 
    
    if state.cancel_requested or GLOBAL_CANCEL_FLAG:
        state.processing_status = "idle"
        state.logs.append("❌ Đã hủy bỏ lệnh.")
        yield
        return 

    try:
        api_key_env = os.environ.get("GOOGLE_API_KEY")
        
        # Parse Multi-Key Input
        api_keys_list = []
        if state.use_multi_key and state.user_api_keys_input:
            import re
            # Split by comma or newline
            raw_keys = re.split(r'[,\n\r]+', state.user_api_keys_input)
            api_keys_list = [k.strip() for k in raw_keys if k.strip()]
            
            # Add default env key if exists
            if api_key_env and api_key_env not in api_keys_list:
                api_keys_list.append(api_key_env)

            if api_keys_list:
                state.logs.append(f"Using {len(api_keys_list)} API Keys (including default) with rotation.")

        # Run AI task in a separate thread to allow UI to remain responsive (polling)
        try:
            # Note: Do not re-import time/concurrent as they are top-level now, but fine if safe
            executor = concurrent.futures.ThreadPoolExecutor()
            cancel_check_lambda = check_cancel_signal
            
            future = executor.submit(
                review_book_syntopic,
                state.uploaded_file_bytes,
                state.uploaded_mime_type,
                api_key=api_key_env,
                api_keys=api_keys_list,
                language=state.review_language,
                cancel_check=cancel_check_lambda
            )
            
            # Poll for completion or cancellation
            while not future.done():
                # Check for cancellation (Must re-fetch state to get updates)
                if check_cancel_signal() or me.state(State).cancel_requested:
                    state.processing_status = "idle"
                    state.logs.append("❌ Đã hủy bỏ lệnh (Ngừng ngay lập tức).")
                    executor.shutdown(wait=False)
                    yield
                    return
                
                yield # Yield control to allow other events (like Cancel click) to process
                await asyncio.sleep(0.1)
            
            # Get result
            review_data = future.result()
        finally:
            executor.shutdown(wait=False)

        if "used_model" in review_data:
             state.logs.append(f"Model used: {review_data['used_model']}")
             
        state.logs.append("Review hoàn tất. Đang tạo file PDF...")
        state.processing_status = "generating_pdf" # Re-use this status for PDF gen
        yield
        
        # Check cancellation again before PDF
        if me.state(State).cancel_requested:
             state.processing_status = "idle"
             state.logs.append("❌ Đã hủy bỏ lệnh.")
             yield
             return
        
        # Generate PDF (Review style)
        import tempfile
        original_name = state.uploaded_filename
        name_no_ext = original_name.rsplit('.', 1)[0]
        pdf_out_name = f"{name_no_ext}_expert_review.pdf"
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp_path = tmp.name
            
        final_path = save_summary_to_pdf(review_data, tmp_path)
        
        with open(final_path, "rb") as f:
            pdf_bytes = f.read()
            
        state.pdf_content_base64 = base64.b64encode(pdf_bytes).decode('utf-8')
        state.pdf_filename = pdf_out_name
        
        # Cleanup
        try:
             os.remove(final_path)
        except:
             pass

        state.logs.append(f"Đã tạo xong file: {state.pdf_filename}")
        state.processing_status = "review_done" # New Done State
        yield

    except PartialCompletionError as partial_ex:
        safe_print(f"DEBUG PARTIAL ERROR: {partial_ex}")
        state.processing_status = "error"
        state.error_message = f"{str(partial_ex)} (Có thể tiếp tục)"
        state.resume_data = partial_ex.partial_data
        state.logs.append(f"⚠️ Lỗi một phần: {str(partial_ex)}. Dữ liệu đã lưu để tiếp tục.")
        yield

    except Exception as ex:
        safe_print(f"DEBUG MAIN EXCEPTION: {ex}")
        state.processing_status = "error"
        state.error_message = str(ex)
        state.logs.append(f"Lỗi Review: {str(ex)}")
        yield


async def resume_review(e: me.ClickEvent):
    global GLOBAL_CANCEL_FLAG
    state = me.state(State)
    
    if not state.resume_data:
        state.error_message = "Không có dữ liệu để tiếp tục."
        yield
        return

    # 1. Clear Error & Set Status
    state.error_message = ""
    state.cancel_requested = False
    clear_cancel_signal()
    yield 

    state.processing_status = "analyzing_review"
    state.logs.append("🔄 Đang tiếp tục xử lý (Resume)...")
    yield 

    if state.cancel_requested or GLOBAL_CANCEL_FLAG:
        state.processing_status = "idle"
        state.logs.append("❌ Đã hủy bỏ lệnh.")
        yield
        return 

    try:
        api_key_env = os.environ.get("GOOGLE_API_KEY")
        
        # Parse Multi-Key Input
        api_keys_list = []
        if state.use_multi_key and state.user_api_keys_input:
            import re
            raw_keys = re.split(r'[,\n\r]+', state.user_api_keys_input)
            api_keys_list = [k.strip() for k in raw_keys if k.strip()]
            
            # Add default env key if exists
            if api_key_env and api_key_env not in api_keys_list:
                api_keys_list.append(api_key_env)

            if api_keys_list:
                state.logs.append(f"Using {len(api_keys_list)} API Keys (including default) with rotation.")

        # Run AI task
        try:
            executor = concurrent.futures.ThreadPoolExecutor()
            cancel_check_lambda = check_cancel_signal
            
            # PASS RESUME STATE HERE
            future = executor.submit(
                review_book_syntopic,
                state.uploaded_file_bytes,
                state.uploaded_mime_type,
                api_key=api_key_env,
                api_keys=api_keys_list,
                language=state.review_language,
                cancel_check=cancel_check_lambda,
                resume_state=state.resume_data # Pass the saved state
            )
            
            while not future.done():
                if check_cancel_signal() or me.state(State).cancel_requested:
                    state.processing_status = "idle"
                    state.logs.append("❌ Đã hủy bỏ lệnh.")
                    executor.shutdown(wait=False)
                    yield
                    return
                yield
                await asyncio.sleep(0.1)
            
            review_data = future.result()
        finally:
            executor.shutdown(wait=False)

        if "used_model" in review_data:
             state.logs.append(f"Model used: {review_data['used_model']}")
             
        state.logs.append("Review hoàn tất. Đang tạo file PDF...")
        state.processing_status = "generating_pdf"
        state.resume_data = {} # Clear resume data on success
        yield
        
        if me.state(State).cancel_requested:
             state.processing_status = "idle"
             yield
             return
        
        # Generate PDF
        import tempfile
        original_name = state.uploaded_filename
        name_no_ext = original_name.rsplit('.', 1)[0]
        pdf_out_name = f"{name_no_ext}_expert_review.pdf"
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp_path = tmp.name
            
        final_path = save_summary_to_pdf(review_data, tmp_path)
        
        with open(final_path, "rb") as f:
            pdf_bytes = f.read()
            
        state.pdf_content_base64 = base64.b64encode(pdf_bytes).decode('utf-8')
        state.pdf_filename = pdf_out_name
        
        try:
             os.remove(final_path)
        except:
             pass

        state.logs.append(f"Đã tạo xong file: {state.pdf_filename}")
        state.processing_status = "review_done"
        yield

    except PartialCompletionError as partial_ex:
        safe_print(f"DEBUG PARTIAL ERROR (RESUME): {partial_ex}")
        state.processing_status = "error"
        state.error_message = f"{str(partial_ex)} (Có thể tiếp tục)"
        state.resume_data = partial_ex.partial_data # Update progress even if failed again
        state.logs.append(f"⚠️ Lại gặp lỗi: {str(partial_ex)}. Đã cập nhật điểm dừng.")
        yield

    except Exception as ex:
        safe_print(f"DEBUG MAIN EXCEPTION: {ex}")
        state.processing_status = "error"
        state.error_message = str(ex)
        state.logs.append(f"Lỗi Review: {str(ex)}")
        yield


def set_topic(e: me.ClickEvent):
    state = me.state(State)
    state.user_topic = e.key

@me.page(
    path="/",
    stylesheets=[
        "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap",
    ],
    security_policy=me.SecurityPolicy(
        allowed_script_srcs=["https://fonts.googleapis.com", "https://fonts.gstatic.com"],
        allowed_connect_srcs=["https://fonts.googleapis.com", "https://fonts.gstatic.com"],
    ),
    on_load=on_load,
)
def main_page():
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
        # Header
        with me.box(
            style=me.Style(
                background="#ffffff",
                padding=me.Padding.symmetric(vertical=20, horizontal=32),
                border=me.Border(bottom=me.BorderSide(width=1, color="#e2e8f0")),
                display="flex",
                justify_content="space-between",
                align_items="center",
            )
        ):
            me.text(
                "SlideGenius",
                style=me.Style(
                    font_size=24,
                    font_weight=700,
                    color="#0f172a",
                ),
            )
            me.text("AI Powered Presentation Generator", style=me.Style(color="#64748b", font_size=14))

        # Main Layout: 2 Columns
        with me.box(
            style=me.Style(
                display="grid",
                grid_template_columns="1fr 1fr",
                gap=32,
                padding=me.Padding.all(32),
                height="calc(100vh - 80px)", # Adjust for header
                box_sizing="border-box",
            )
        ):
            # --- Left Column: Input ---
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
                
                # File Uploader
                with me.box(style=me.Style(width="100%")):
                     me.text("Upload Document (PDF/DOCX/EPUB)", style=me.Style(font_size=14, color="#475569", margin=me.Margin(bottom=8)))
                     me.uploader(
                        label="Choose File",
                        accepted_file_types=["application/pdf", ".docx", ".epub"],
                        on_upload=handle_upload,
                        type="flat",
                        style=me.Style(
                            font_weight="500",
                        )
                    )
                
                if state.uploaded_filename:
                     with me.box(style=me.Style(background="#f0f9ff", padding=me.Padding.all(12), border_radius=8, display="flex", align_items="center", gap=8)):
                         me.icon("description", style=me.Style(color="#0284c7"))
                         me.text(state.uploaded_filename, style=me.Style(font_size=14, color="#0c4a6e"))

                # Template Uploader (Optional)
                with me.box(style=me.Style(width="100%")):
                     me.text("Slide Template (Optional .pptx)", style=me.Style(font_size=14, color="#475569", margin=me.Margin(bottom=8)))
                     me.uploader(
                        label="Upload Template",
                        accepted_file_types=[".pptx"],
                        on_upload=handle_template_upload,
                        type="stroked",
                        style=me.Style(
                            font_weight="500",
                        )
                    )
                
                if state.template_filename:
                     with me.box(style=me.Style(background="#faf5ff", padding=me.Padding.all(12), border_radius=8, display="flex", align_items="center", gap=8)):
                         me.icon("slideshow", style=me.Style(color="#9333ea"))
                         me.text(state.template_filename, style=me.Style(font_size=14, color="#6b21a8"))

                # Topic Input
                with me.box(style=me.Style(width="100%")):
                    me.input(
                        label="Chủ đề mong muốn (Tùy chọn)",
                        on_blur=handle_topic_input,
                        style=me.Style(width="100%"),
                        value=state.user_topic
                    )
                    
                    # Topic Suggestions
                    me.text("Gợi ý chủ đề phổ biến:", style=me.Style(font_size=12, color="#94a3b8", margin=me.Margin(top=12, bottom=8), font_weight=500))
                    
                    suggestions = [
                        "Kế hoạch kinh doanh", 
                        "Báo cáo thị trường", 
                        "Giáo án điện tử", 
                        "Hồ sơ năng lực", 
                        "Startup Pitch",
                        "Phân tích tài chính"
                    ]
                    
                    with me.box(style=me.Style(display="flex", flex_wrap="wrap", gap=8)):
                        for topic in suggestions:
                            is_selected = state.user_topic == topic
                            me.button(
                                topic,
                                key=topic,
                                on_click=set_topic,
                                type="stroked" if not is_selected else "flat",
                                color="primary" if is_selected else "warn", 
                                style=me.Style(
                                    font_size=12,
                                    border_radius=20, 
                                    # Custom override for unselected state to look cleaner
                                    color="#2563eb" if is_selected else "#64748b",
                                    border=me.Border.all(me.BorderSide(width=1, color="#2563eb" if is_selected else "#cbd5e1")),
                                    background="#eff6ff" if is_selected else "#ffffff",
                                    padding=me.Padding.symmetric(vertical=4, horizontal=12) 
                                )
                            )

                # Custom User Instructions
                with me.box(style=me.Style(width="100%", margin=me.Margin(top=24))):
                     me.textarea(
                        label="Hướng dẫn đặc biệt cho AI (Tùy chọn)",
                        placeholder="Ví dụ: Chỉ tập trung vào chương 2, giải thích kỹ thuật ngữ...",
                        on_blur=handle_user_instruction,
                        value=state.user_instructions,
                        rows=3,
                        style=me.Style(width="100%")
                    )

                # Detail Level Selection
                with me.box(style=me.Style(width="100%", margin=me.Margin(top=24))):
                    me.checkbox(
                        label="Chế độ Chi tiết (Deep Dive)",
                        checked=state.is_detailed,
                        on_change=on_detail_change,
                    )
                    me.text(
                        "Nếu chọn: Tạo nhiều slide hơn, nội dung sâu hơn. Mặc định: Tổng quan ngắn gọn.", 
                        style=me.Style(font_size=12, color="#64748b", margin=me.Margin(top=4, left=32))
                    )

                # Advanced API Key Section
                with me.box(style=me.Style(width="100%", margin=me.Margin(top=24), padding=me.Padding.all(16), background="#f8fafc", border_radius=8, border=me.Border.all(me.BorderSide(width=1, color="#e2e8f0")))):
                    me.checkbox(
                        label="Sử dụng nhiều API Key (Dự phòng)",
                        checked=state.use_multi_key,
                        on_change=on_multi_key_change,
                    )
                    
                    if state.use_multi_key:
                        me.text("Nhập danh sách Key (Mỗi key một dòng hoặc cách nhau dấu phẩy)", style=me.Style(font_size=12, color="#64748b", margin=me.Margin(top=8, bottom=8)))
                        me.input(
                            label="Paste API Keys here",
                            value=state.user_api_keys_input,
                            on_blur=handle_api_keys_input,
                            type="password", # Masked input
                            # multiline=True removed as it is not supported with me.input or password type
                            style=me.Style(width="100%")
                        )
                        # Note on Copy: Browser default password field prevents copying clear text effectively? Or at least masks it.
                        # User requirement: "cho phép paste từ clipboard, không cho phép copy".
                        # Password field naturally satisfies "show as *". 
                        # Preventing copy is tricky in pure server-side UI framework, but password field usually treats `value` as write-only or masked.

                # Generate Button
                is_loading = state.processing_status in ["analyzing", "generating"]
                # Button Logic
                is_disabled = is_loading or not state.uploaded_filename
                btn_bg = "#e2e8f0" if is_disabled else "#2563eb"
                btn_color = "#94a3b8" if is_disabled else "#000000"

                with me.box(
                    on_click=generate_slides if not is_disabled else None,
                    style=me.Style(
                        width="100%",
                        padding=me.Padding.symmetric(vertical=16),
                        margin=me.Margin(top=32),
                        background=btn_bg,
                        border_radius=8, # Make it look like a button
                        cursor="not-allowed" if is_disabled else "pointer",
                        display="flex",
                        justify_content="center",
                        align_items="center",
                        box_shadow="0 2px 4px rgba(0,0,0,0.1)" if not is_disabled else "none",
                    )
                ):
                    me.text(
                        "Generate Slides",
                        style=me.Style(
                            color=btn_color,
                            font_size=16,
                            font_weight="bold",
                            text_align="center",
                            z_index=10, # Force text to top
                        )
                    )
                
                # Summary Button Logic
                su_bg = "transparent"
                su_border = "#ea580c" if not is_disabled else "#fed7aa"
                su_color = "#ea580c" if not is_disabled else "#fed7aa"
                
                with me.box(
                    on_click=generate_summary if not is_disabled else None,
                    style=me.Style(
                        width="100%",
                        padding=me.Padding.symmetric(vertical=16),
                        margin=me.Margin(top=16),
                        background=su_bg,
                        border=me.Border.all(me.BorderSide(width=1, color=su_border)),
                        border_radius=8,
                        cursor="not-allowed" if is_disabled else "pointer",
                        display="flex",
                        justify_content="center",
                        align_items="center",
                    )
                ):
                   me.text(
                        "Generate Summary (PDF)",
                        style=me.Style(
                            color=su_color,
                            font_size=16,
                            font_weight="bold",
                            text_align="center",
                            z_index=10,
                        )
                   )
                   
                # Expert Review Button
                rev_bg = "transparent"
                rev_border = "#7c3aed" if not is_disabled else "#ddd6fe"
                rev_color = "#7c3aed" if not is_disabled else "#ddd6fe"
                
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
                        style=me.Style(width="100%")
                    )

                with me.box(
                    on_click=generate_review if not is_disabled else None,
                    style=me.Style(
                        width="100%",
                        padding=me.Padding.symmetric(vertical=16),
                        margin=me.Margin(top=12),
                        background=rev_bg,
                        border=me.Border.all(me.BorderSide(width=1, color=rev_border)),
                        border_radius=8,
                        cursor="not-allowed" if is_disabled else "pointer",
                        display="flex",
                        justify_content="center",
                        align_items="center",
                    )
                ):
                   me.text(
                        "Generate Expert Review",
                        style=me.Style(
                            color=rev_color,
                            font_size=16,
                            font_weight="bold",
                            text_align="center",
                            z_index=10,
                        )
                   )

            # --- Right Column: Output/Preview ---
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
                
                # Logs Area
                with me.box(
                    style=me.Style(
                        background="#f1f5f9",
                        flex_grow=1,
                        border_radius=8,
                        padding=me.Padding.all(16),
                        overflow_y="auto",
                        font_family="monospace",
                    )
                ):
                    if not state.logs:
                        me.text("Waiting for input...", style=me.Style(color="#94a3b8", font_style="italic"))
                    
                    for log in state.logs:
                        me.text(f"> {log}", style=me.Style(color="#334155", font_size=13, margin=me.Margin(bottom=8)))
                    
                    if state.processing_status == "analyzing":
                        with me.box(style=me.Style(display="flex", align_items="center", gap=8, margin=me.Margin(top=16))):
                            me.progress_spinner(diameter=20, stroke_width=2)
                            me.text("Reading & Analyzing...", style=me.Style(color="#2563eb", font_weight=500))
                        
                        # Add Cancel Button
                        with me.box(style=me.Style(margin=me.Margin(left=16))):
                             me.button("Hủy lệnh", on_click=request_cancel, color="warn")

                    if state.processing_status == "generating":
                         with me.box(style=me.Style(display="flex", align_items="center", gap=8, margin=me.Margin(top=16))):
                            me.progress_spinner(diameter=20, stroke_width=2)
                            me.text("Designing Slides...", style=me.Style(color="#7c3aed", font_weight=500))
                        
                         with me.box(style=me.Style(margin=me.Margin(left=16))):
                             me.button("Hủy lệnh", on_click=request_cancel, color="warn")

                    if state.processing_status == "analyzing_summary":
                        with me.box(style=me.Style(display="flex", align_items="center", gap=8, margin=me.Margin(top=16))):
                            me.progress_spinner(diameter=20, stroke_width=2)
                            me.text("Summarizing...", style=me.Style(color="#ea580c", font_weight=500))
                            
                        with me.box(style=me.Style(margin=me.Margin(left=16))):
                             me.button("Hủy lệnh", on_click=request_cancel, color="warn")
                            
                    if state.processing_status == "analyzing_review":
                        with me.box(style=me.Style(display="flex", align_items="center", gap=8, margin=me.Margin(top=16))):
                            me.progress_spinner(diameter=20, stroke_width=2)
                            me.text("Expert Reviewing (3 Steps)...", style=me.Style(color="#7c3aed", font_weight=500))
                            
                        with me.box(style=me.Style(margin=me.Margin(left=16))):
                             me.button("Hủy lệnh", on_click=request_cancel, color="warn")

                    if state.processing_status == "generating_pdf":
                        with me.box(style=me.Style(display="flex", align_items="center", gap=8, margin=me.Margin(top=16))):
                            me.progress_spinner(diameter=20, stroke_width=2)
                            me.text("Creating PDF...", style=me.Style(color="#db2777", font_weight=500))
                            
                        with me.box(style=me.Style(margin=me.Margin(left=16))):
                             me.button("Hủy lệnh", on_click=request_cancel, color="warn")

                # Cancellation Dialog Overlay
                if state.show_cancel_dialog:
                    with me.box(
                        style=me.Style(
                            position="fixed", top=0, left=0, right=0, bottom=0,
                            background="rgba(0,0,0,0.5)", z_index=1000,
                            display="flex", justify_content="center", align_items="center"
                        )
                    ):
                        with me.box(
                            style=me.Style(
                                background="white", padding=me.Padding.all(24),
                                border_radius=12, width="400px",
                                box_shadow="0 10px 15px -3px rgba(0, 0, 0, 0.1)"
                            )
                        ):
                            me.text("Xác nhận hủy", style=me.Style(font_size=20, font_weight="bold", margin=me.Margin(bottom=16)))
                            me.text("Bạn có chắc chắn muốn hủy lệnh đang chạy không? Tiến trình hiện tại sẽ bị dừng lại.", 
                                    style=me.Style(margin=me.Margin(bottom=24), color="#4b5563"))
                            
                            with me.box(style=me.Style(display="flex", justify_content="flex-end", gap=16)):
                                me.button("Không, quay lại", on_click=dismiss_cancel)
                                me.button("Có, Hủy ngay", on_click=confirm_cancel, color="warn")

                # Error Message
                if state.error_message:
                     with me.box(
                        style=me.Style(
                            background="#fef2f2",
                            padding=me.Padding.all(12),
                            border_radius=8,
                            border=me.Border.all(me.BorderSide(width=1, color="#fecaca")),
                        )
                    ):
                        me.text(f"Error: {state.error_message}", style=me.Style(color="#991b1b", font_size=14))
                        
                        # Resume Button (Only if resume_data is present)
                        if state.resume_data:
                             with me.box(style=me.Style(margin=me.Margin(top=12), display="flex", align_items="center", gap=12)):
                                 me.button(
                                     "🔄 Chạy tiếp (Resume)",
                                     on_click=resume_review,
                                     color="primary",
                                     type="flat",
                                     style=me.Style(font_weight="bold")
                                 )
                                 me.text("Giữ lại tiến độ đã xong, chỉ chạy lại phần lỗi.", style=me.Style(font_size=12, color="#7f1d1d", font_style="italic"))

                # Download Section (Only show when done)
                if state.processing_status == "done":
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
                            text_align="center"
                        )
                    ):
                        me.icon("check_circle", style=me.Style(color="#059669", font_size=48))
                        me.text("Presentation Ready!", style=me.Style(font_size=20, font_weight=600, color="#065f46"))
                        
                        # Use me.html to create a download link with data URI
                        # since me.download isn't available/working as expected
                        data_uri = f"data:application/vnd.openxmlformats-officedocument.presentationml.presentation;base64,{state.pptx_content_base64}"
                        me.html(
                            f'<a href="{data_uri}" download="{state.pptx_filename}" '
                            'style="display: inline-block; background-color: #0284c7; color: white; '
                            'padding: 12px 24px; text-decoration: none; border-radius: 8px; font-weight: 600; font-family: Inter, sans-serif;">'
                            'Download PowerPoint'
                            '</a>'
                        )
                        
                        me.button(
                            "Create Another",
                            on_click=lambda e: setattr(state, "processing_status", "idle"),
                            style=me.Style(margin=me.Margin(top=16)),
                        )
                
                # Download Summary Section
                if state.processing_status == "summary_done":
                    with me.box(
                        style=me.Style(
                            background="#fff7ed",
                            padding=me.Padding.all(24),
                            border_radius=12,
                            border=me.Border.all(me.BorderSide(width=1, color="#fdba74")),
                            display="flex",
                            flex_direction="column",
                            align_items="center",
                            gap=16,
                            text_align="center"
                        )
                    ):
                        me.icon("description", style=me.Style(color="#ea580c", font_size=48))
                        me.text("Summary Ready!", style=me.Style(font_size=20, font_weight=600, color="#9a3412"))
                        
                        data_uri = f"data:application/pdf;base64,{state.pdf_content_base64}"
                        me.html(
                            f'<a href="{data_uri}" download="{state.pdf_filename}" '
                            'style="display: inline-block; background-color: #ea580c; color: white; '
                            'padding: 12px 24px; text-decoration: none; border-radius: 8px; font-weight: 600; font-family: Inter, sans-serif;">'
                            'Download Summary PDF'
                            '</a>'
                        )
                        
                        me.button(
                            "Start Over",
                            on_click=lambda e: setattr(state, "processing_status", "idle"),
                            style=me.Style(margin=me.Margin(top=16)),
                        )

                # Download Review Section
                if state.processing_status == "review_done":
                    with me.box(
                        style=me.Style(
                            background="#f5f3ff",
                            padding=me.Padding.all(24),
                            border_radius=12,
                            border=me.Border.all(me.BorderSide(width=1, color="#c4b5fd")),
                            display="flex",
                            flex_direction="column",
                            align_items="center",
                            gap=16,
                            text_align="center"
                        )
                    ):
                        me.icon("auto_stories", style=me.Style(color="#7c3aed", font_size=48))
                        me.text("Expert Review Ready!", style=me.Style(font_size=20, font_weight=600, color="#5b21b6"))
                        
                        data_uri = f"data:application/pdf;base64,{state.pdf_content_base64}"
                        me.html(
                            f'<a href="{data_uri}" download="{state.pdf_filename}" '
                            'style="display: inline-block; background-color: #7c3aed; color: white; '
                            'padding: 12px 24px; text-decoration: none; border-radius: 8px; font-weight: 600; font-family: Inter, sans-serif;">'
                            'Download Review PDF'
                            '</a>'
                        )
                        
                        me.button(
                            "Start Over",
                            on_click=lambda e: setattr(state, "processing_status", "idle"),
                            style=me.Style(margin=me.Margin(top=16)),
                        )
