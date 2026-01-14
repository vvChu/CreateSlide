import os
import json
from google import genai
from google.genai import types
import time
import random
from utils import safe_print
import docx
import io
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
import warnings
import ast
import re

# Suppress ebooklib warnings about future features if any
warnings.filterwarnings("ignore", category=UserWarning, module='ebooklib')

# Suppress BS4 XML/HTML warning for EPUBs
from bs4 import XMLParsedAsHTMLWarning
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

def robust_json_parse(text):
    """
    Parses JSON robustly, handling Markdown code blocks, single quotes (Python dicts),
    and common syntax errors.
    """
    # 1. Clean Markdown code blocks
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()

    # 2. Try standard JSON first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 3. Try AST literal_eval (handles single quotes/Python dicts)
    try:
        # ast.literal_eval is safe for standard python literals
        return ast.literal_eval(text)
    except (ValueError, SyntaxError):
        pass

    # 4. Try finding JSON content within the text (substring search)
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        subset_text = match.group(0)
        try:
            return json.loads(subset_text)
        except:
            try:
                return ast.literal_eval(subset_text)
            except:
                pass
        # Update text to the found subset for further repair attempts
        text = subset_text

    # 5. Fix common issues: Trailing commas
    # Remove trailing comma before ] or }
    text_fixed = re.sub(r',\s*([\]}])', r'\1', text)
    try:
        return json.loads(text_fixed)
    except:
        pass
    
    try:
        return ast.literal_eval(text_fixed)
    except:
        pass
        
    # 6. Aggressive fallback for unquoted keys (JavaScript style)
    # This is risky but useful for basic keys. 
    # { title: "Foo" } -> { "title": "Foo" }
    try:
        # Regex to quote unquoted keys
        # Find word followed by colon, not in quotes
        # This is a simplified regex and might break complex strings
        text_quoted = re.sub(r'(\w+):', r'"\1":', text_fixed)
        return json.loads(text_quoted)
    except:
        pass

    raise ValueError(f"Failed to parse JSON/Dict from response. Raw text: {text}")


SYSTEM_INSTRUCTION = """
Bạn là chuyên gia thiết kế bài thuyết trình chuyên nghiệp. Nhiệm vụ của bạn là trích xuất nội dung từ tài liệu và tạo cấu trúc JSON cho bài thuyết trình.

Yêu cầu QUAN TRỌNG:
1. TIÊU ĐỀ NGẮN GỌN: Tiêu đề mỗi slide phải cực kỳ ngắn gọn, KHÔNG QUÁ 10 TỪ. Tránh tiêu đề 2 dòng.
2. NỘI DUNG VỪA PHẢI (QUAN TRỌNG): 
   - Mỗi slide chứa khoảng 5-7 ý chính.
   - ƯU TIÊN TUYỆT ĐỐI: **Viết câu đơn, trọn vẹn ý nghĩa, nhưng vẫn ngắn gọn.**
   - Đảm bảo mỗi ý đều truyền tải được thông điệp rõ ràng, không viết cụt lủn (như chỉ viết từ khóa).
   - Có thể dùng động từ mạnh ở đầu câu hoặc câu khẳng định.
   - **VÍ DỤ PHONG CÁCH MONG MUỐN (HÃY BẮT CHƯỚC STYLE NÀY):**
     + "Manifesting là một bài thực hành phát triển bản thân."
     + "Giúp giải phóng toàn bộ tiềm năng bên trong bạn."
     + "Yêu cầu thực hiện đồng thời cả 7 bước."
     + "Mỗi ngày là một cơ hội để củng cố sức mạnh nội tại."
     + "Bạn có quyền lựa chọn và kiến tạo cuộc sống tốt nhất."
   - NẾU NỘI DUNG QUÁ DÀI: Hãy chia thành nhiều slide thay vì cố nhồi nhét.
   - **TẤT CẢ** các ý quan trọng trong tài liệu PHẢI được đưa vào slide. Không được tự ý cắt bỏ nội dung chính.
   - **KHÔNG ĐƯỢC ĐỂ TRỐNG NỘI DUNG**: Nếu không tìm thấy ý chính, hãy tóm tắt đoạn văn bản đó. Không bao giờ trả về mảng "content" rỗng `[]`.
   - **PHÂN LOẠI NGỮ CẢNH THÔNG MINH (SEMANTIC MAPPING):**
     Đừng chỉ copy-paste nội dung. Hãy hiểu ý nghĩa câu để gán nhãn chính xác:
     + **Chiến lược/Định hướng**: Áp dụng cho các quyết định vĩ mô, chọn phương án, giai đoạn đầu (Stage 0). -> Bắt đầu bằng **Chiến lược**: hoặc **Định hướng**:
     + **Rủi ro/Hậu quả/Cảnh báo**: Áp dụng cho các câu chỉ kết quả xấu, cảnh báo, hoặc mối quan hệ nguyên nhân-hệ quả tiêu cực (A -> B). -> Bắt đầu bằng **Rủi ro**: hoặc **Cảnh báo**:
     + **Giải pháp/Cải tiến/Thay đổi**: Áp dụng cho các yêu cầu thay đổi (A thay vì B), đề xuất mới, hoặc giải quyết vấn đề cũ. -> Bắt đầu bằng **Giải pháp**: hoặc **Cải tiến**:
     + **Mục tiêu/Kết quả (Outcome)**: Áp dụng cho các mong muốn đạt được. -> Bắt đầu bằng **Mục tiêu**:
     + **Lưu ý quan trọng**: Những điều cần ghi nhớ đặc biệt. -> Bắt đầu bằng **Lưu ý**:
     
     *Ví dụ 1*: "Làm vội phần Briefing dẫn đến phải sửa thiết kế nhiều." -> **Rủi ro**: Làm vội Briefing gây hậu quả sửa thiết kế nhiều lần.
     *Ví dụ 2*: "Yêu cầu dùng dữ liệu số thay vì 2D cũ kỹ." -> **Cải tiến**: Chuyển đổi sang dữ liệu số (BIM) thay vì bản vẽ 2D.
     
     **QUAN TRỌNG**: Nếu không thuộc các loại trên, HÃY GIỮ NGUYÊN nội dung gốc và tóm tắt lại cho ngắn gọn. ĐỪNG BỎ SÓT thông tin chỉ vì không phân loại được.
3. CÚ PHÁP (BẮT BUỘC): Sử dụng markdown `**từ khóa**` để làm nổi bật (in đậm & màu) các ý quan trọng. Ít nhất 1-2 từ khóa mỗi dòng.
   - **LƯU Ý ĐẶC BIỆT VỀ JSON**: KHÔNG sử dụng dấu ngoặc kép `"` bên trong nội dung văn bản (content) vì sẽ làm hỏng cấu trúc JSON. Hãy dùng dấu ngoặc đơn `'` hoặc escape `\"` nếu bắt buộc.
4. NGÔN NGỮ: Chuyên nghiệp, trang trọng.

JSON Schema bắt buộc:
{
  "title": "TÊN BÀI THUYẾT TRÌNH (VIẾT HOA)",
  "slides": [
    {
      "title": "Tiêu Đề Ngắn (Max 10 chữ)",
      "content": ["Ý 1 (Ngắn gọn)", "Ý 2...", "Ý 3...", "Ý 4...", "Ý 5..."],
      "notes": "Ghi chú chi tiết..."
    },
    {
       "title": "Tiêu Đề Ngắn (Phần 2)",
       "content": ["Ý tiếp theo..."]
    }
  ]
}
"""


# GLOBAL CONSTANTS FOR MODEL SELECTION
# STRICT PRIORITY ORDER per User Request
ROBUST_MODEL_LIST = [
    "gemini-3-pro-preview",       # 1. 3.0 Pro
    "gemini-3-flash-preview",     # 2. 3.0 Flash
    "gemini-2.5-pro",             # 3. 2.5 Pro
    "gemini-2.5-flash",           # 4. 2.5 Flash
    "gemini-exp-1206",            # 5. 2.0 Pro (Approximate using best available Exp)
    "gemini-2.0-flash",           # 6. 2.0 Flash
    "gemini-1.5-pro",             # 7. 1.5 Pro
    "gemini-1.5-flash"            # 8. 1.5 Flash
]

def generate_with_retry_v2(client, parts, config, model_list=None, cancel_check=None):
    """
    Unified function for generating content with advanced cyclic fallback logic.
    Refactored to support 5 full cycles with smart delays.
    
    Args:
        client: genai.Client instance
        parts: List of content parts
        config: types.GenerateContentConfig
        model_list: Optional list. Defaults to ROBUST_MODEL_LIST.
        cancel_check: Optional callable that returns True if cancellation is requested.
        
    Returns:
        response object, model_name used.
        
    Raises:
        ValueError: If all models fail after 5 cycles or if cancelled.
    """
    models_to_try = model_list or ROBUST_MODEL_LIST
    
    # Tracking for Smart Delay & Permanent Failures
    model_last_used_time = {} # {model_name: timestamp}
    permanently_failed_models = set()
    MIN_RETRY_DELAY_SECONDS = 20.0 
    
    TOTAL_CYCLES = 2
    last_error = None
    
    for cycle in range(1, TOTAL_CYCLES + 1):
        if cancel_check and cancel_check():
             safe_print("⚠️ Cancel requested. Aborting retry loop.")
             raise ValueError("Operation cancelled by user.")

        safe_print(f"\n--- CYCLE {cycle}/{TOTAL_CYCLES} ---")
        
        cycle_success = False
        
        # Check if we have any models left to try
        available_models = [m for m in models_to_try if m not in permanently_failed_models]
        if not available_models:
             safe_print("⚠️ No available models left to try (All quota exhausted or not found). Stopping immediately.")
             break
        
        for model_name in models_to_try:
            # Skip models that permanently failed previously
            if model_name in permanently_failed_models:
                continue

            # Check if this was the last model and we have no more to try in this cycle
            # Optimization: If all models are in permanently_failed_models, we should stop immediately
            # But the outer loop handles cycles. 
            # We can check available models at start of cycle, or here.


            # --- Smart Delay Logic ---
            now = time.time()
            last_used = model_last_used_time.get(model_name, 0)
            elapsed = now - last_used
            
            if elapsed < MIN_RETRY_DELAY_SECONDS and last_used > 0:
                wait_needed = MIN_RETRY_DELAY_SECONDS - elapsed
                safe_print(f"[{model_name}] Smart Wait: Sleeping {wait_needed:.1f}s to respect rate limits...")
                
                # Interruptible Sleep Loop
                waited = 0.0
                step = 0.5
                while waited < wait_needed:
                    if cancel_check and cancel_check():
                        safe_print("⚠️ Cancel requested during sleep. Aborting.")
                        raise ValueError("Operation cancelled by user.")
                    time.sleep(step)
                    waited += step
                # End Interruptible Sleep
            
            # Update timestamp usage (marking start of attempt usually safest)
            model_last_used_time[model_name] = time.time()
            
            try:
                safe_print(f"DEBUG: V2 Calling generate_content for model: {model_name}")
                safe_print(f"DEBUG: Config: {config}")
                
                response = client.models.generate_content(
                    model=model_name,
                    contents=[types.Content(role="user", parts=parts)],
                    config=config
                )
                
                try:
                    text_content = response.text
                    if text_content:
                        safe_print(f"Success with {model_name}.")
                        return text_content, model_name
                    else:
                        safe_print(f"[{model_name}] Returned empty text (No error but no content). Skipping...")
                except Exception as val_err:
                    safe_print(f"[{model_name}] Invalid Response (Safety/Block): {str(val_err)}. Skipping...")
                    # Treat as failure, continue to next model
                    continue
                    
            except Exception as e:
                last_error = e
                error_str = str(e)
                
                # Handling Rate Limits (429) & Resource Exhausted
                if "RESOURCE_EXHAUSTED" in error_str or "429" in error_str:
                    if "limit: 0" in error_str or "limit:0" in error_str:
                         safe_print(f"[{model_name}] FAIL: Limit 0 (No Quota). Permanently removing from retry list...")
                         permanently_failed_models.add(model_name) 
                         continue

                    # Standard Quota Exceeded
                    safe_print(f"[{model_name}] FAIL: Quota exceeded (429). Skipping to next model immediately...")
                    continue
                
                elif "NOT_FOUND" in error_str or "404" in error_str:
                     safe_print(f"[{model_name}] FAIL: Model Not found (404). Permanently removing from retry list...")
                     permanently_failed_models.add(model_name)
                     continue
                
                elif "model output must contain" in error_str or "Tool use is not expected" in error_str:
                     safe_print(f"[{model_name}] FAIL: Empty/Blocked Output (Safety or filtered). Skipping...")
                     continue
                
                else:
                    safe_print(f"[{model_name}] FAIL: Unexpected Error: {str(e)[:150]}... Skipping...")
                    continue
        
        # If we finish the list without success, loop to next cycle.
        if not cycle_success and cycle < TOTAL_CYCLES:
            safe_print(f"Cycle {cycle} completed with NO SUCCESS. Preparing for Cycle {cycle+1}...")
            # Optional: Add small breather between full cycles if desired, 
            # but Smart Delay handles per-model wait.
            time.sleep(1)

    safe_print("All models failed after 10 cycles.")
    
    error_msg = str(last_error)
    if "RESOURCE_EXHAUSTED" in error_msg or "429" in error_msg:
         raise ValueError("Hệ thống AI đang quá tải (Hết hạn mức Free Tier). Vui lòng thử lại sau 1 phút.")
    elif "model output must contain" in error_msg:
         raise ValueError("Nội dung bị AI chặn do vi phạm quy tắc an toàn hoặc không trả về kết quả.")
    else:
         raise ValueError(f"Hệ thống AI gặp lỗi không xác định. Chi tiết: {error_msg[:100]}...")


def generate_content_v2(api_keys: list[str], parts, config, model_list=None, cancel_check=None):
    """
    Wrapper around generate_with_retry that rotates through a list of API keys.
    If a key hits a quota error, it switches to the next key.
    """
    if not api_keys or len(api_keys) == 0:
        raise ValueError("No API keys provided for rotation.")

    # Deduplicate keys while preserving order
    unique_keys = []
    seen = set()
    for k in api_keys:
        k_clean = k.strip()
        if k_clean and k_clean not in seen:
            unique_keys.append(k_clean)
            seen.add(k_clean)
    
    if not unique_keys:
        raise ValueError("List of API keys is empty after cleaning.")

    last_exception = None
    
    for i, key in enumerate(unique_keys):
        safe_print(f"🔑 Using API Key {i+1}/{len(unique_keys)}: ...{key[-4:] if len(key)>4 else key}")
        try:
            client = genai.Client(api_key=key)
            return generate_with_retry_v2(client, parts, config, model_list, cancel_check)
        except Exception as e:
            error_msg = str(e)
            # Check for Quota Exceeded / Resource Exhausted
            is_quota_error = "RESOURCE_EXHAUSTED" in error_msg or "429" in error_msg
            
            if is_quota_error:
                safe_print(f"⚠️ Key {i+1} Exhausted/Rate Limited. Switching to next key...")
                last_exception = e
                continue # Try next key
            else:
                # If it's a non-quota error (like validation, safety), rotation might not help, 
                # but let's be robust and try if it looks like a permission issue. 
                # For now, let's treat other 4xx as potentially key-related, but 5xx as server error.
                # However, the user specifically asked for "out of quota" handling.
                # Let's re-raise if it's clearly not a quota issue to avoid wasting cycles?
                # Actually, sometimes "permission denied" or "invalid key" implies we should try another.
                if "API_KEY_INVALID" in error_msg or "PERMISSION_DENIED" in error_msg:
                     safe_print(f"⚠️ Key {i+1} Invalid/Denied. Switching...")
                     last_exception = e
                     continue
                
                # If it's a model error (generate_with_retry raises ValueError generally), 
                # generate_with_retry already retried internal models. 
                # If it bubbled up here, it means ALL models failed for THIS key.
                # It is possible another KEY has different quota? Yes.
                safe_print(f"⚠️ Error with Key {i+1}: {error_msg}. Switching key to be safe...")
                last_exception = e
                continue

    # If we get here, all keys failed
    raise ValueError(f"All API Keys failed. Last error: {last_exception}")


from document_loader import load_document, extract_text_from_docx, extract_text_from_epub

def analyze_document(file_bytes, mime_type, api_key=None, api_keys: list[str] = None, detail_level="Tóm tắt", user_instructions="", cancel_check=None):
    """
    Analyzes the document using Gemini to extract key ideas
    and structure them into a slide presentation format.
    Uses centralized robust retry logic with KEY ROTATION.
    """
    # 1. Prepare Key List
    keys_to_use = []
    
    # Priority: explicit api_keys list > explicit single api_key > env var
    if api_keys and len(api_keys) > 0:
        keys_to_use = api_keys
    elif api_key:
        keys_to_use = [api_key]
    else:
        env_key = os.environ.get("GOOGLE_API_KEY")
        if env_key:
            keys_to_use = [env_key]
            
    if not keys_to_use:
        raise ValueError("Thiếu Google API Key. Vui lòng thiết lập biến môi trường hoặc nhập vào giao diện.")

    # Import safe_print...
    from utils import safe_print

    # Dynamic System Instruction...
    base_instruction = SYSTEM_INSTRUCTION
    
    # ... (Logic for detail_level and user_instructions)
    
    # 1. Detail Level Logic
    if detail_level == "Chi tiết":
        safe_print("Using DETAILED mode prompt...")
        specific_instruction = """
        YÊU CẦU CHI TIẾT (QUAN TRỌNG):
        - Bạn đang ở chế độ 'Chi tiết'. Người dùng muốn các slide đi sâu vào nội dung, số liệu và phân tích.
        - ĐỪNG tóm tắt qua loa. Hãy trích xuất tối đa thông tin quan trọng.
        - Số lượng slide: Có thể tạo nhiều slide hơn bình thường để chứa hết thông tin chi tiết. 
        - Vẫn phải tuân thủ quy tắc: Max 5 bullet/slide. Nếu nội dung dài, hãy TÁCH thành nhiều slide (Phần 1, Phần 2, Phần 3...).
        """
    else:
        safe_print("Using OVERVIEW mode prompt...")
        specific_instruction = """
        YÊU CẦU TỔNG QUAN:
        - Bạn đang ở chế độ 'Tổng quan'. Hãy tập trung vào các ý chính, cốt lõi nhất.
        - Phù hợp cho bài giới thiệu ngắn gọn.
        """
    
    # 2. Custom User Instructions Logic
    custom_instruction_block = ""
    if user_instructions and len(user_instructions.strip()) > 2:
        safe_print(f"Adding User Instructions: {user_instructions}")
        custom_instruction_block = f"""
        \n--------------------------------------------------
        HƯỚNG DẪN ĐẶC BIỆT TỪ NGƯỜI DÙNG (ƯU TIÊN TUYỆT ĐỐI):
        "{user_instructions}"
        
        Hãy tuân thủ nghiêm ngặt hướng dẫn trên của người dùng khi tạo nội dung.
        Nếu người dùng yêu cầu tập trung vào chương nào, hãy chỉ tập trung vào đó.
        --------------------------------------------------\n
        """
        
    final_instruction = base_instruction + "\n" + specific_instruction + custom_instruction_block

    try:
        parts = []
        prompt = f"Hãy phân tích tài liệu này và tạo cấu trúc bài thuyết trình ({detail_level})."

        if mime_type == "application/pdf":
            parts.append(types.Part.from_bytes(data=file_bytes, mime_type="application/pdf"))
            parts.append(types.Part.from_text(text=prompt))
        
        elif mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            text_content = extract_text_from_docx(file_bytes)
            parts.append(types.Part.from_text(text=f"{prompt}\n\nNội dung tài liệu:\n{text_content}"))
            
        elif mime_type == "application/epub+zip":
            safe_print("Processing EPUB file...")
            text_content = extract_text_from_epub(file_bytes)
            parts.append(types.Part.from_text(text=f"{prompt}\n\nNội dung tài liệu:\n{text_content}"))
        
        else:
            raise ValueError(f"Định dạng file không được hỗ trợ: {mime_type}")
        
        # Config
        # Execute with Rotation
        generated_text, used_model = generate_content_v2(
            api_keys=keys_to_use, 
            parts=parts,
            config=types.GenerateContentConfig(
                system_instruction=final_instruction,
                response_mime_type="application/json",
                temperature=0.7 # Creative but structured
            ),
            cancel_check=cancel_check
        )
        
        if not generated_text:
            raise ValueError("Gemini không trả về nội dung.")
            
        try:
            parsed_data = robust_json_parse(generated_text)
            
            # Critical Fix for "list object has no attribute get"
            if isinstance(parsed_data, list):
                safe_print("AI returned a LIST. Wrapping into standard schema...")
                parsed_data = {
                    "title": "Slide Generated by AI", 
                    "slides": parsed_data
                }
            
            # --- VALIDATION STEP ---
            if "slides" in parsed_data:
                for i, slide in enumerate(parsed_data["slides"]):
                    content = slide.get("content", [])
                    if not content or (isinstance(content, list) and len(content) == 0):
                        safe_print(f"WARNING: Slide {i+1} ('{slide.get('title', 'Untitled')}') has EMPTY content.")
                        if slide.get("notes"):
                            safe_print("-> Movings 'notes' to 'content' as fallback.")
                            slide["content"] = [slide["notes"]]
                        else:
                            slide["content"] = ["(Nội dung chưa được trích xuất - Vui lòng kiểm tra lại tài liệu gốc)"]
            
            return parsed_data
            
        except Exception as e:
            safe_print(f"JSON Parsing Failed: {e}")
            raise ValueError(f"Lỗi đọc dữ liệu từ AI: {str(e)}")

    except Exception as e:
        # Catch-all for top level errors
        raise RuntimeError(f"{str(e)}")
