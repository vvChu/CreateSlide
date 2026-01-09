import os
import json
from google import genai
from google.genai import types
import docx
import io

# Define the schema explicitly for clarity, though Gemini's response_mime_type="application/json"
# combined with system instructions is often enough. For stricter control, we could use
# schema constraints, but prompt instructions are usually sufficient for this use case.

SYSTEM_INSTRUCTION = """
Bạn là chuyên gia thiết kế bài thuyết trình chuyên nghiệp. Nhiệm vụ của bạn là trích xuất nội dung từ tài liệu và tạo cấu trúc JSON cho bài thuyết trình.

Yêu cầu QUAN TRỌNG:
1. TIÊU ĐỀ NGẮN GỌN: Tiêu đề mỗi slide phải cực kỳ ngắn gọn, KHÔNG QUÁ 10 TỪ. Tránh tiêu đề 2 dòng.
2. NỘI DUNG VỪA PHẢI (QUAN TRỌNG): Mỗi slide chỉ chứa tối đa 5 bullet point.
   - NẾU NỘI DUNG DÀI: BẮT BUỘC phải tách thành nhiều slide (Ví dụ: "Chiến lược (Phần 1)", "Chiến lược (Phần 2)"). Đừng cố nhồi nhét vào 1 slide.
3. CÚ PHÁP: Sử dụng markdown `**từ khóa**` để nhấn mạnh.
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

def extract_text_from_docx(file_bytes: bytes) -> str:
    """Extracts text from a DOCX file bytes."""
    try:
        doc = docx.Document(io.BytesIO(file_bytes))
        full_text = []
        for para in doc.paragraphs:
            full_text.append(para.text)
        return '\n'.join(full_text)
    except Exception as e:
        raise ValueError(f"Lỗi khi đọc file DOCX: {str(e)}")

def analyze_document(file_bytes: bytes, mime_type: str, api_key: str = None, detail_level: str = "Tóm tắt", user_instructions: str = "") -> dict:
    """
    Sends document content to Gemini and returns parsed JSON.
    detail_level: "Tóm tắt" (Overview) or "Chi tiết" (Detailed)
    user_instructions: Optional specific requests from user behavior.
    """
    # Use provided key or env var
    key = api_key or os.environ.get("GOOGLE_API_KEY")
    
    if not key:
        raise ValueError("Thiếu Google API Key. Vui lòng thiết lập biến môi trường hoặc nhập vào giao diện.")

    # Import safe_print locally or at top (local is safer for circular imports if any, but top is cleaner)
    from utils import safe_print

    # Dynamic System Instruction based on Detail Level
    base_instruction = SYSTEM_INSTRUCTION
    
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
        client = genai.Client(api_key=key)
        
        parts = []
        prompt = f"Hãy phân tích tài liệu này và tạo cấu trúc bài thuyết trình ({detail_level})."

        if mime_type == "application/pdf":
            # Multimodal for PDF
            parts.append(types.Part.from_bytes(data=file_bytes, mime_type="application/pdf"))
            parts.append(types.Part.from_text(text=prompt))
        
        elif mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            # Text extraction for DOCX
            text_content = extract_text_from_docx(file_bytes)
            parts.append(types.Part.from_text(text=f"{prompt}\n\nNội dung tài liệu:\n{text_content}"))
        
        else:
            raise ValueError(f"Định dạng file không được hỗ trợ: {mime_type}")
        
        # List of models to try in order of preference (expanded for resilience)
        # Nuclear Option: Confirmed Available Models Only
        models_to_try = [
            # High Priority (User Requested / Newest)
            "gemini-3-flash-preview", 
            "gemini-3-pro-preview",
            "gemini-2.5-flash",
            "gemini-2.5-pro",
            
            # Fallbacks (Older / Lite)
            "gemini-2.0-flash-lite",
            "gemini-2.0-flash",

             # Last resort generic aliases
            "gemini-flash-latest",
            "gemini-pro-latest"
        ]
        
        last_exception = None
        import time
        import random

        retry_count = 0
        
        for model_name in models_to_try:
            try:
                safe_print(f"Trying model: {model_name}...")
                response = client.models.generate_content(
                    model=model_name,
                    contents=[types.Content(role="user", parts=parts)],
                    config=types.GenerateContentConfig(
                        system_instruction=final_instruction,
                        response_mime_type="application/json",
                        temperature=0.7
                    )
                )
                # If successful, break the loop
                break
            except Exception as e:
                last_exception = e
                error_str = str(e)
                
                # Handling Rate Limits (429) and Resource Exhausted
                if "RESOURCE_EXHAUSTED" in error_str or "429" in error_str:
                    # Exponential Backoff + Jitter
                    retry_count += 1
                    wait_time = min(60, (2 ** retry_count)) + random.uniform(0, 1)
                    safe_print(f"Quota exceeded for {model_name}. Waiting {wait_time:.1f}s before trying next...")
                    time.sleep(wait_time)
                    continue
                    
                # Handling Not Found (404)
                elif "NOT_FOUND" in error_str or "404" in error_str:
                    safe_print(f"Model {model_name} not found (or not available). Skipping immediately...")
                    continue
                    
                else:
                    safe_print(f"Error with {model_name}: {error_str}. Trying next...")
                    continue
        else:
            raise last_exception if last_exception else RuntimeError("All models failed.")

        # Parse JSON with robust cleaning
        if not response.text:
            raise ValueError("Gemini không trả về nội dung.")
            
        import re
        text = response.text.strip()
        
        # 1. Try to find JSON block explicitly
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            text = match.group(0)
            
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            # Fallback: Try strict cleaning for unescaped characters if needed
            safe_print(f"JSON Parse Error: {e}")
            safe_print(f"Raw Text: {response.text}") 
            
            # Attempt basic repair: remove trailing commas
            text = re.sub(r',\s*([\]}])', r'\1', text)
            try:
                return json.loads(text)
            except:
                raise ValueError(f"Lỗi cú pháp JSON từ AI: {str(e)} - Check console logs API raw response.")

    except Exception as e:
        raise RuntimeError(f"Lỗi xử lý AI: {str(e)}")
