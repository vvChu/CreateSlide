from slide_engine import create_pptx
import json
import os

# Mock Data resembling the user's report
# User said: "Slide 2 chỉ ra title nội dung: ISO ..." and implied no content body.
mock_data = {
    "title": "TEST PRESENTATION",
    "slides": [
        {
            "title": "SLIDE 1: INTRODUCTION",
            "content": ["Bullet 1", "Bullet 2", "Bullet 3"]
        },
        {
            "title": "ISO 19650-6:2025 - QUẢN LÝ THÔNG TIN",
            "content": [
                "**Mục tiêu**: Đảm bảo an toàn thông tin.",
                "**Rủi ro**: Mất mát dữ liệu quan trọng.",
                "**Giải pháp**: Áp dụng chuẩn ISO mới."
            ]
        }
    ]
}

print("Generating PPTX with mock data...")
pptx_io = create_pptx(mock_data)

with open("debug_output.pptx", "wb") as f:
    f.write(pptx_io.read())

print("PPTX generated: debug_output.pptx")
print("Please open this file. If content is visible, the bug is in AI extraction.")
print("If content is missing/invisible, the bug is in slide_engine.py logic.")
