# SlideGenius - Nền tảng Phân tích & Tạo Slide bằng AI

SlideGenius là ứng dụng mạnh mẽ sử dụng trí tuệ nhân tạo để chuyển đổi tài liệu (PDF, DOCX, EPUB) thành các sản phẩm chuyên nghiệp. Hệ thống hỗ trợ **Google Gemini**, **OpenAI**, và **Ollama (LLM cục bộ - miễn phí)** để tạo **Slide PowerPoint**, **Tóm tắt chuyên sâu**, và **Review Sách chuẩn chuyên gia**.

Được xây dựng trên nền tảng **Python** và **Mesop**, ứng dụng sở hữu giao diện hiện đại với khả năng xử lý lỗi thông minh.

## 🚀 Tính Năng Nổi Bật

### 1. Tạo Slide Tự Động (AI Presentation)
*   **Chuyển đổi thông minh**: Biến văn bản thô thành các slide có cấu trúc logic.
*   **Smart Layout**: Tự động căn chỉnh kích thước, khoảng cách text để đảm bảo tính thẩm mỹ.
*   **Hỗ trợ Template**: Tải lên file `.pptx` mẫu của bạn để giữ đúng nhận diện thương hiệu.

### 2. Expert Book Review (Review Sách Đa Tầng)
Hệ thống "Multi-Agent Chain-of-Thought" tiên tiến sử dụng 3 AI Agents riêng biệt:
*   **The Librarian (Thủ thư)**: Phân loại "DNA" của sách (Thể loại, Giọng văn, Độc giả mục tiêu).
*   **The Analyst (Nhà phân tích)**: Phân tích sâu theo từng nhánh (Logic thực tế cho Non-Fiction hoặc Cốt truyện/Cảm xúc cho Fiction).
*   **The Editor (Biên tập viên)**: Tổng hợp bài review chuẩn tạp chí với **Hệ thống chấm điểm (0-10)**, **Sách tương tự**, và **Các mô hình tư duy (Mental Models)**.

### 3. Tóm Tắt Chuyên Sâu (Deep Dive)
*   **Chain of Density**: Kỹ thuật tóm tắt nhiều lớp giúp nội dung cô đọng nhưng giàu thông tin.
*   **Xuất PDF**: Trả về file báo cáo PDF chuyên nghiệp.

### 4. Động Cơ AI Đa Nhà Cung Cấp ("Smart Switch")
*   **3 Nhà cung cấp**: Google Gemini, OpenAI, và Ollama (LLM cục bộ — miễn phí, không cần API key).
*   **Tự động phát hiện**: Khi khởi động, tự động phát hiện Ollama server khả dụng.
*   **Ưu tiên Nghiêm ngặt**: Thứ tự ưu tiên model với cơ chế fallback tự động.
*   **Thử lại với xoay vòng Key**: Nếu model gặp lỗi hoặc hết quota, hệ thống tự động thử model/key tiếp theo.
*   **Smart Delay (Trễ thông minh)**: Tự động ngủ (sleep) giữa các lần thử để tránh lỗi `429 Resource Exhausted`.

---

## 🛠 Kiến Trúc Hệ Thống

Ứng dụng được module hóa thành 5 module chính:

1.  **`ai_engine.py`**: "Bộ não" trung tâm. Quản lý việc gọi API, chọn model, vòng lặp thử lại, và định tuyến đa nhà cung cấp.
2.  **`summarizer.py`**: Xử lý logic Review 3-Agent, tóm tắt chuyên sâu, và tạo file PDF.
3.  **`slide_engine.py`**: Xử lý thao tác file PPTX và tính toán bố cục (Layout).
4.  **`document_loader.py`**: Xử lý phân tích tài liệu (PDF, DOCX, EPUB) và trích xuất văn bản.
5.  **`utils.py`**: Tiện ích dùng chung — logging, console output, và các hàm hỗ trợ.

**Giao diện**: Sử dụng **Mesop** (`main.py`) quản lý trạng thái (State) theo thời gian thực.

---

## 📦 Hướng Dẫn Cài Đặt

### Yêu cầu
*   **Hệ điều hành**: Windows 10/11, macOS, hoặc Linux.
*   **Python**: 3.10 trở lên (Khuyên dùng Python 3.12).
*   **AI Provider** (một trong các lựa chọn):
    *   [Ollama](https://ollama.com/) chạy cục bộ (miễn phí, không cần API key)
    *   [Google AI Studio Key](https://aistudio.google.com/)
    *   [OpenAI API Key](https://platform.openai.com/)

### Các bước
1.  **Tải Mã Nguồn**:
    ```bash
    git clone https://github.com/anhtrtHN/CreateSlide.git
    cd CreateSlide
    ```

2.  **Cài Đặt Thư Viện**:
    ```bash
    pip install -r requirements.txt
    ```

3.  **Cấu Hình Môi Trường**:
    Sao chép `.env.example` thành `.env` và điền thông tin:
    ```env
    # Lựa chọn A: Ollama (LLM cục bộ — miễn phí)
    OLLAMA_BASE_URL=http://localhost:11434/v1

    # Lựa chọn B: Google Gemini
    # GOOGLE_API_KEY=ma_api_key_cua_ban

    # Lựa chọn C: OpenAI
    # OPENAI_API_KEY=ma_api_key_cua_ban

    # Tùy chọn
    AI_RETRY_CYCLES=3
    ```

4.  **Chạy Ứng Dụng**:
    ```bash
    mesop main.py --port 32123
    ```
    Truy cập tại: `http://localhost:32123`

---

## 📖 Hướng Dẫn Sử Dụng

### A. Tạo Slide Thuyết Trình
1.  **Upload**: Tải lên tài liệu nguồn (PDF/Word/Ebook).
2.  **Template (Tùy chọn)**: Tải lên file `.pptx` mẫu.
3.  **Topic**: Nhập chủ đề chính.
4.  **Chế độ**: Chọn "Chi tiết" nếu muốn bài thuyết trình dài hơn.
5.  Nhấn **"Generate Slides"**.
6.  Theo dõi Log trạng thái. Khi xong, nhấn nút **"Download PowerPoint"** màu xanh lá.

### B. Tạo Expert Review (Review Sách)
1.  **Upload**: Tải lên file sách.
2.  Nhấn nút **"Generate Expert Review"**.
3.  Hệ thống sẽ kích hoạt 3 Agents. Quá trình gồm 3 bước (Classify -> Analyze -> Edit).
4.  Khi hoàn tất, nút **"Download Review PDF"** màu tím sẽ xuất hiện ở cột trạng thái.

### C. Tóm Tắt Tài Liệu
1.  **Upload**: Tải lên tài liệu.
2.  Nhấn **"Generate Summary"**.
3.  Tải về file PDF kết quả.

---

## ⚠️ Xử Lý Sự Cố

*   **Thông báo lỗi màu đỏ**: Chỉ cần thực hiện một lệnh mới, hệ thống sẽ tự động xóa lỗi cũ.
*   **Lỗi 429 (Hết Quota)**: Hệ thống "Smart Switch" sẽ tự xử lý. Nếu bạn thấy log báo "Sleeping...", đó là tính năng bảo vệ quota đang hoạt động.
*   **Lỗi kết nối Ollama**: Đảm bảo Ollama server đang chạy (`ollama serve`) và `OLLAMA_BASE_URL` trong `.env` đúng.
*   **Spinner quay mãi không dừng**: Hãy Refresh (F5) trình duyệt.

---
*Được hỗ trợ bởi Google Gemini, OpenAI, và Ollama.*
