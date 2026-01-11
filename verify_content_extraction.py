import io
import docx
from ai_engine import analyze_document
import os
import sys

# Ensure UTF-8 output for Windows Console
sys.stdout.reconfigure(encoding='utf-8')

def create_dummy_docx(text):
    doc = docx.Document()
    doc.add_paragraph(text)
    f = io.BytesIO()
    doc.save(f)
    f.seek(0)
    return f.read()

text = """
1. Bối cảnh Chiến lược:
   • Stage 0 là giai đoạn the chốt để quyết định nên xây mới hay cải tạo.
   • Cần xác định rõ suất đầu tư ngay từ đầu để tránh vượt ngân sách.

2. Vấn đề thực tế:
   • Làm qua loa giai đoạn khảo sát -> Hậu quả: Phát sinh chi phí xử lý nền móng yếu.
   • Quy trình duyệt thiết kế quá lâu gây chậm tiến độ tổng thể.

3. Yêu cầu Cải tiến:
   • Dùng công nghệ VR để khách hàng hình dung thay vì chỉ xem bản vẽ 2D.
   • Áp dụng quy trình Agile thay cho Waterfall trong quản lý dự án.
"""

print("--- Data Input ---")
print(text)
print("------------------")

docx_bytes = create_dummy_docx(text)

try:
    print("Running analyze_document...")
    # ai_engine looks for GOOGLE_API_KEY in env
    # If not present, this will raise ValueError
    result = analyze_document(docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document", detail_level="Chi tiết")
    
    import json
    print("\n--- AI Result ---")
    print(json.dumps(result, indent=2, ensure_ascii=False))
except Exception as e:
    print(f"\nError: {e}")
    if "API Key" in str(e):
        print("Please set GOOGLE_API_KEY environment variable to run this test.")
