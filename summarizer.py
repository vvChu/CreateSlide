
import os
import json
import time
import random
import concurrent.futures
from google import genai
from google.genai import types
from document_loader import load_document
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.utils import simpleSplit
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle
from reportlab.lib.enums import TA_JUSTIFY, TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib import colors
from reportlab.lib import colors
import re
from utils import safe_print
from ai_engine import generate_with_retry_v2, generate_content_v2

# Try to register a font that supports Vietnamese if possible
# Typically Arial or Times New Roman. 
# In a Windows environment, we might find them in Windows/Fonts
# For portability, we might need a bundled font, but for now let's try standard fonts.
# ReportLab standard fonts (Helvetica) don't support full Vietnamese unicode well without custom fonts.
# We will check common paths.

HAS_UNICODE_FONT = False
FONT_PATH = "C:\\Windows\\Fonts\\arial.ttf"

def register_fonts():
    global HAS_UNICODE_FONT
    if HAS_UNICODE_FONT: return # Already done

    if os.path.exists(FONT_PATH):
        try:
            # Check if already registered to avoid error
            from reportlab.pdfbase import pdfmetrics
            if 'Arial' not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont('Arial', FONT_PATH))
            
            # Try to register Bold and Italic for Rich Text
            arial_bold = "C:\\Windows\\Fonts\\arialbd.ttf"
            arial_italic = "C:\\Windows\\Fonts\\ariali.ttf"
            
            if os.path.exists(arial_bold) and 'Arial-Bold' not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont('Arial-Bold', arial_bold))
                
            if os.path.exists(arial_italic) and 'Arial-Italic' not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont('Arial-Italic', arial_italic))
                
            # Register Family
            pdfmetrics.registerFontFamily(
                'Arial', 
                normal='Arial', 
                bold='Arial-Bold', 
                italic='Arial-Italic', 
                boldItalic='Arial-Bold' # Fallback for now
            )
            
            HAS_UNICODE_FONT = True
        except:
            pass

SUMMARIZER_SYSTEM_INSTRUCTION = """
Bạn là một trợ lý AI chuyên nghiệp về tóm tắt văn bản. Nhiệm vụ của bạn là đọc nội dung tài liệu và tạo ra một bản tóm tắt súc tích, đầy đủ ý chính.

Cấu trúc bản tóm tắt mong muốn (trả về JSON):
{
  "title": "Tiêu đề tài liệu (hoặc tiêu đề đề xuất)",
  "overview": "Tóm tắt tổng quan (khoảng 100-200 từ)",
  "key_points": [
    "Điểm chính 1: ...",
    "Điểm chính 2: ...",
    "Điểm chính 3: ...",
    ...
  ],
  "conclusion": "Kết luận hoặc ý nghĩa chính rút ra."
}

Yêu cầu:
1. Ngôn ngữ: Tiếng Việt.
2. Văn phong: Chuyên nghiệp, khách quan.
3. Không bịa đặt thông tin không có trong tài liệu.
4. Đảm bảo JSON hợp lệ.
"""

PROMPT_SUMMARIZE_DOCUMENT = "Hãy tóm tắt tài liệu này theo cấu trúc JSON đã yêu cầu."

# New Prompts for Deep Dive (Single Shot)
# New Prompts for Deep Dive (Single Shot)
# New Prompts for Deep Dive (Single Shot)
PROMPT_DEEP_DIVE_FULL = """
Hãy đóng vai một "Người Sưu Tầm Trí Tuệ" (Wisdom Collector) và tạo ra bản tóm tắt sách theo phong cách "Big Ideas" đầy cảm hứng.
Mục tiêu: Ngắn gọn, súc tích nhưng cực kỳ sâu sắc (More Wisdom in Less Time).

Bạn PHẢI trả về kết quả dưới dạng JSON hợp lệ với cấu trúc sau:

{
  "metadata": {
    "title": "Tên sách",
    "slogan": "Một câu slogan ngắn gọn hoặc mô tả thu hút về sách",
    "author": "Tên tác giả"
  },
  "big_ideas": [
    "Ý tưởng lớn 1 (3-5 từ, giật gân)",
    "Ý tưởng lớn 2...",
    ... (5-7 ý)"
  ],
  "introduction": {
    "text": "Đoạn giới thiệu 100-150 từ. Bối cảnh, tầm quan trọng, giọng văn hào hứng.",
    "best_quote": "Trích dẫn hay nhất hoặc bao quát nhất của cuốn sách"
  },
  "core_ideas": [
    {
      "title": "TÊN Ý TƯỞNG LỚN 1",
      "quote": "Trích dẫn nguyên văn đắt giá nhất liên quan đến ý tưởng này.",
      "commentary": "Phân tích chuyên sâu (200-300 từ): Đây là phần quan trọng nhất. Hãy viết thành một bài tiểu luận ngắn. 1. Giải thích cơ chế/nguyên lý của ý tưởng dưới góc độ khoa học/tâm lý học. 2. So sánh với các học thuyết khác. 3. Đưa ra ví dụ áp dụng cụ thể và các bẫy tư duy cần tránh. Tuyệt đối không viết sơ sài."
    },
    {
      "title": "TÊN Ý TƯỞNG LỚN 2",
      "quote": "...",
      "commentary": "Phân tích logic, mở rộng vấn đề, đào sâu vào bản chất (First Principles)."
    },
    ... (Tạo khoảng 5-7 ý tưởng cốt lõi)
    {
      "title": "TÊN Ý TƯỞNG LỚN CUỐI CÙNG - HÀNH ĐỘNG",
      "quote": "Trích dẫn về sự kiên trì/kỷ luật.",
      "commentary": "Kêu gọi hành động mạnh mẽ."
    }
  ],
  "about_author": "Tóm tắt tiểu sử tác giả ngắn gọn.",
  "about_creator": "SlideGenius AI: Chúng tôi cam kết chắt lọc những tinh hoa tri thức để giúp bạn tiết kiệm thời gian."
}

LƯU Ý:
- Ngôn ngữ: Tiếng Việt (trừ các tên riêng).
- Giọng văn: Truyền cảm hứng, sâu sắc, trực diện.
- JSON: Không được lỗi cú pháp.
"""

def robust_json_parse(text):
    """Parses JSON robustly (reused logic)."""
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()
    try:
        return json.loads(text)
    except:
        import re
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise



# ... (Previous code remains, skipping to function)

def summarize_document(file_bytes: bytes, mime_type: str, api_key: str = None, api_keys: list[str] = None, user_instructions: str = "", cancel_check=None) -> dict:
    """
    Summarizes the document using Gemini.
    Returns a dict with title, overview, key_points, conclusion.
    """
    # 1. Prepare Key List
    keys_to_use = []
    if api_keys and len(api_keys) > 0:
        keys_to_use = api_keys
    elif api_key:
        keys_to_use = [api_key]
    else:
        env_key = os.environ.get("GOOGLE_API_KEY")
        if env_key:
            keys_to_use = [env_key]

    if not keys_to_use:
        raise ValueError("Missing API Key.")

    # Prepare Context
    parts = []
    
    # Construct base prompt
    base_prompt = "Hãy tóm tắt tài liệu này theo cấu trúc JSON đã yêu cầu."
    if user_instructions and user_instructions.strip():
        base_prompt += f"\n\nLƯU Ý CỦA NGƯỜI DÙNG (Cực kỳ quan trọng, hãy tuân thủ): {user_instructions}"

    # Check if PDF (Multimodal) or Text
    if mime_type == "application/pdf":
        parts.append(types.Part.from_bytes(data=file_bytes, mime_type="application/pdf"))
        parts.append(types.Part.from_text(text=base_prompt))
    else:
        # Load text for DOCX/EPUB
        text_content = load_document(file_bytes, mime_type)
        full_prompt = f"Nội dung tài liệu:\n{text_content}\n\n{base_prompt}"
        parts.append(types.Part.from_text(text=full_prompt))

    config = types.GenerateContentConfig(
        system_instruction=SUMMARIZER_SYSTEM_INSTRUCTION,
        response_mime_type="application/json",
        temperature=0.5
    )

    try:
        response_text, _ = generate_content_v2(keys_to_use, parts, config, cancel_check=cancel_check)
        return robust_json_parse(response_text)
    except Exception as e:
        raise ValueError(f"Tóm tắt thất bại: {str(e)}")

def save_summary_to_pdf(summary_data: dict, output_filename: str = "summary.pdf") -> str:
    """
    Generates a PDF file from the summary data.
    """
    register_fonts()
    c = canvas.Canvas(output_filename, pagesize=A4)
    width, height = A4
    
    
    # Margin
    margin = 50
    header_margin = 50 
    y = height - margin
    text_width = width - 2 * margin
    
    # Font Settings (Global for this function scope)
    title_font = 'Arial' if HAS_UNICODE_FONT else 'Helvetica'
    body_font = 'Arial' if HAS_UNICODE_FONT else 'Helvetica'
    
    def draw_footer():
        c.saveState()
        # Ensure font is set for footer even if not defined yet
        footer_font = 'Arial' if HAS_UNICODE_FONT else 'Helvetica' 
        try:
            c.setFont(footer_font, 10)
        except:
             pass # Fallback
             
        footer_y = 30
        c.drawString(margin, footer_y, "\u00A9 2026 Truong Tuan Anh | Document Summary")
        page_num_text = f"Page {c.getPageNumber()}"
        c.drawRightString(width - margin, footer_y, page_num_text)
        c.restoreState()

    def check_page_break(current_y, font_name, font_size):
        if current_y < 80: 
            draw_footer()
            c.showPage()
            current_y = height - header_margin
            c.setFont(font_name, font_size)
        return current_y
    
    # --- SYNTOPIC REVIEW RENDER (PLATYPUS / HIGH QUALITY) ---
    if summary_data.get("mode") == "syntopic_review" and "review_markdown" in summary_data:
        doc = SimpleDocTemplate(
            output_filename, 
            pagesize=A4,
            rightMargin=50, leftMargin=50, 
            topMargin=50, bottomMargin=50
        )
        
        styles = getSampleStyleSheet()
        
        # --- CUSTOM STYLES (MATCHING DEEP DIVE) ---
        title_style = ParagraphStyle('CustomTitle', parent=styles['Title'], fontName='Arial-Bold', fontSize=24, leading=30, spaceAfter=20, alignment=TA_CENTER, textColor=colors.darkblue)
        header_style = ParagraphStyle('CustomHeader', parent=styles['Heading1'], fontName='Arial-Bold', fontSize=16, spaceBefore=16, spaceAfter=10, textColor=colors.black, backColor=colors.whitesmoke, borderPadding=5)
        sub_header_style = ParagraphStyle('CustomSubHeader', parent=styles['Heading2'], fontName='Arial-Bold', fontSize=14, spaceBefore=12, spaceAfter=8, textColor=colors.darkslategray)
        body_style = ParagraphStyle('CustomBody', parent=styles['Normal'], fontName='Arial', fontSize=12, leading=16, spaceAfter=8, alignment=TA_JUSTIFY)
        quote_style = ParagraphStyle('CustomQuote', parent=styles['Normal'], fontName='Arial-Italic', fontSize=12, leading=16, leftIndent=20, rightIndent=20, spaceBefore=10, spaceAfter=10, textColor=colors.darkgreen)
        
        story = []
        
        # --- TITLE PAGE INFO ---
        # Try to parse title from markdown if possible, else generic
        review_text = summary_data["review_markdown"]
        genre = summary_data.get("genre", "Book Review")
        category = summary_data.get("category", "General")
        
        story.append(Spacer(1, 20))
        story.append(Paragraph("EXPERT BOOK REVIEW", 
            ParagraphStyle('Brand', parent=styles['Normal'], alignment=TA_CENTER, fontSize=10, textColor=colors.grey)))
        story.append(Paragraph(f"{category} | {genre}", 
            ParagraphStyle('SubBrand', parent=styles['Normal'], alignment=TA_CENTER, fontSize=9, textColor=colors.grey)))
        story.append(Spacer(1, 10))
        
        # --- PARSE MARKDOWN CONTENT ---
        # Simple parser to convert Markdown lines to ReportLab Paragraphs
        lines = review_text.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                story.append(Spacer(1, 6))
                continue
                
            # Headers
            if line.startswith("# "):
                text = line[2:].strip()
                story.append(Paragraph(text, title_style))
                story.append(Paragraph("---", ParagraphStyle('Line', parent=body_style, alignment=TA_CENTER, textColor=colors.lightgrey)))
                story.append(Spacer(1, 10))
            elif line.startswith("## "):
                text = line[3:].strip()
                story.append(Paragraph(text, header_style))
            elif line.startswith("### "):
                text = line[4:].strip()
                story.append(Paragraph(text, sub_header_style))
            
            # Quotes
            elif line.startswith("> "):
                text = line[2:].strip().strip('"')
                story.append(Paragraph(f"<i>“{text}”</i>", quote_style))
            
            # List Items
            elif line.startswith("- ") or line.startswith("* "):
                text = line[2:].strip()
                # Bold handling **text** -> <b>text</b>
                text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
                story.append(Paragraph(f"&bull;  {text}", body_style))
            
            # Separators
            elif line == "---":
                story.append(Spacer(1, 10))
                story.append(Paragraph("---", ParagraphStyle('Line', parent=body_style, alignment=TA_CENTER, textColor=colors.lightgrey)))
                story.append(Spacer(1, 10))
                
            # Normal Text
            else:
                # Bold handling
                text = line
                text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
                # Italic handling *text* -> <i>text</i>
                text = re.sub(r'\*(.*?)\*', r'<i>\1</i>', text)
                
                story.append(Paragraph(text, body_style))

        # --- FOOTER FUNCTION ---
        def add_footer(canvas, doc):
            canvas.saveState()
            canvas.setFont('Arial', 9)
            canvas.setFillColor(colors.grey)
            canvas.drawString(50, 20, "© 2026 Truong Tuan Anh | Expert Review")
            canvas.drawRightString(A4[0] - 50, 20, f"Page {doc.page}")
            canvas.restoreState()

        # Build PDF
        doc.build(story, onFirstPage=add_footer, onLaterPages=add_footer)
        return os.path.abspath(output_filename)

    # --- STANDARD SUMMARY RENDER ---
    # Register Fonts (Attempt to find system fonts or fallback)
    # header_margin already defined above
    y = height - header_margin
    
    # Font Settings already defined above

    # Helper for basic Markdown -> ReportLab XML
    def markdown_to_xml(text):
        if not isinstance(text, str):
            import json
            text = json.dumps(text, ensure_ascii=False)
        
        # Escape basic XML chars first
        text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        
        # Replace **bold** with <b>bold</b>
        text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
        
        # Replace ## Headings with bold and breaks
        text = re.sub(r'##\s*(.*?)\n', r'<b>\1</b><br/>', text)
        
        # Replace lists
        lines = text.split('\n')
        processed_lines = []
        for line in lines:
            line = line.strip()
            if line.startswith("- "):
                 processed_lines.append(f"&bull; {line[2:]}<br/>")
            elif line.startswith("* "): # alternative bullet
                 processed_lines.append(f"&bull; {line[2:]}<br/>")
            else:
                 processed_lines.append(line)
        
        return "<br/>".join(processed_lines)

    # Initialize Doc Template for ALL modes
    doc = SimpleDocTemplate(
        output_filename, 
        pagesize=A4,
        rightMargin=50, leftMargin=50, 
        topMargin=50, bottomMargin=50
    )
    
    styles = getSampleStyleSheet()
    # Custom Styles
    title_style = ParagraphStyle(
        'CustomTitle', 
        parent=styles['Title'], 
        fontName='Arial-Bold', 
        fontSize=26, 
        leading=36,
        spaceAfter=12,
        alignment=TA_CENTER,
        textColor=colors.darkblue
    )
    slogan_style = ParagraphStyle(
        'CustomSlogan', 
        parent=styles['Normal'],
        fontName='Arial',
        fontSize=14,
        spaceAfter=24,
        alignment=TA_CENTER,
        textColor=colors.grey
    )
    header_style = ParagraphStyle(
        'CustomHeader', 
        parent=styles['Heading1'], 
        fontName='Arial', 
        fontSize=16, 
        spaceBefore=12, 
        spaceAfter=12,
        textColor=colors.black,
        borderPadding=5,
        backColor=colors.lightgrey
    )
    sub_header_style = ParagraphStyle(
        'CustomSubHeader', 
        parent=styles['Heading2'], 
        fontName='Arial', 
        fontSize=14, 
        spaceBefore=10, 
        spaceAfter=10, 
        textColor=colors.black
    )
    quote_style = ParagraphStyle(
        'CustomQuote', 
        parent=styles['Normal'], 
        fontName='Arial', 
        fontSize=12, 
        leading=18,
        leftIndent=20,
        rightIndent=20,
        spaceBefore=6,
        spaceAfter=6,
        textColor=colors.darkgreen,
        fontName_Italic='Arial',
        alignment=TA_JUSTIFY
    )
    body_style = ParagraphStyle(
        'CustomBody', 
        parent=styles['Normal'], 
        fontName='Arial', 
        fontSize=12, 
        leading=18, 
        spaceAfter=8,
        alignment=TA_JUSTIFY
    )
        
    from reportlab.platypus import KeepTogether

    story = []
    mode = summary_data.get("mode", "standard")

    # --- FOOTER FUNCTION ---
    def add_footer(canvas, doc):
        canvas.saveState()
        canvas.setFont('Arial', 9)
        canvas.setFillColor(colors.grey)
        
        # Left Footer: Copyright
        canvas.drawString(50, 20, "© 2026 Truong Tuan Anh | Document Summary")
        
        # Right Footer: Page Number
        page_num_text = f"Page {doc.page}"
        canvas.drawRightString(A4[0] - 50, 20, page_num_text)
        
        canvas.restoreState()

    # ==========================================
    # MODE: DEEP DIVE (Book Summary)
    # ==========================================
    if mode == "deep_dive":
        metadata = summary_data.get("metadata", {})
        doc_title = metadata.get("title", "BOOK SUMMARY")
        doc_author = metadata.get("author", "Unknown Author")
        doc_slogan = metadata.get("slogan", "More Wisdom in Less Time")
        
        # --- TITLE PAGE ---
        story.append(Spacer(1, 30))
        story.append(Paragraph("TUAN ANH'S NOTES", 
            ParagraphStyle('Brand', parent=styles['Normal'], alignment=TA_CENTER, fontSize=10, textColor=colors.grey)))
        story.append(Paragraph("More Wisdom in Less Time", 
            ParagraphStyle('SubBrand', parent=styles['Normal'], alignment=TA_CENTER, fontSize=8, textColor=colors.grey)))
        story.append(Spacer(1, 15))
        
        story.append(Paragraph(doc_title.upper(), title_style))
        story.append(Paragraph(doc_slogan, slogan_style))
        story.append(Paragraph(f"<b>By {doc_author}</b>", 
            ParagraphStyle('Author', parent=body_style, alignment=TA_CENTER, fontSize=12)))
        story.append(Spacer(1, 15))
        story.append(Paragraph("---", ParagraphStyle('Line', parent=body_style, alignment=TA_CENTER)))
        
        # --- THE BIG IDEAS ---
        story.append(Paragraph("THE BIG IDEAS (CÁC Ý TƯỞNG LỚN)", header_style))
        big_ideas = summary_data.get("big_ideas", [])
        if isinstance(big_ideas, list):
            for idea in big_ideas:
                story.append(Paragraph(f"&bull; <b>{idea}</b>", body_style))
        story.append(Spacer(1, 15))
        story.append(Paragraph("---", ParagraphStyle('Line', parent=body_style, alignment=TA_CENTER)))
        
        # --- INTRODUCTION ---
        intro_data = summary_data.get("introduction", {})
        story.append(Paragraph("GIỚI THIỆU", header_style))
        if intro_data.get("text"):
                story.append(Paragraph(intro_data["text"], body_style))
        
        if intro_data.get("best_quote"):
                story.append(Spacer(1, 8))
                story.append(Paragraph(f"<i>“{intro_data['best_quote']}”</i>", quote_style))
                story.append(Paragraph(f"— {doc_author}", 
                ParagraphStyle('QuoteAuthor', parent=body_style, alignment=TA_RIGHT, fontSize=10)))

        story.append(PageBreak())

        # --- CORE IDEAS ---
        core_ideas = summary_data.get("core_ideas", [])
        for idea in core_ideas:
            elements = []
            title = idea.get("title", "BIG IDEA")
            quote = idea.get("quote", "")
            commentary = idea.get("commentary", "")
            
            elements.append(Paragraph(title.upper(), 
                ParagraphStyle('IdeaTitle', parent=styles['Heading2'], fontName='Arial', fontSize=14, spaceBefore=6, textColor=colors.darkblue)))
            
            if quote:
                elements.append(Paragraph(f"<i>“{quote}”</i>", quote_style))
            
            if commentary:
                # User requested "Key Insight" with yellow lamp icon
                elements.append(Paragraph("<b>💡 Key Insight:</b>", 
                    ParagraphStyle('AIHeader', parent=body_style, fontSize=10, textColor=colors.darkorange, spaceBefore=4)))
                # Render HTML/XML formatting in commentary
                xml_commentary = markdown_to_xml(commentary)
                elements.append(Paragraph(xml_commentary, body_style))
                
            elements.append(Spacer(1, 10))
            elements.append(Paragraph("---", ParagraphStyle('Line', parent=body_style, alignment=TA_CENTER)))
            elements.append(Spacer(1, 10))
            
            story.append(KeepTogether(elements))

        story.append(PageBreak())

        # --- ABOUT AUTHOR & CREATOR ---
        story.append(Paragraph("ABOUT THE AUTHOR (VỀ TÁC GIẢ)", header_style))
        story.append(Paragraph(summary_data.get("about_author", ""), body_style))
        story.append(Spacer(1, 20))
        
        story.append(Paragraph("ABOUT THE NOTE CREATOR (VỀ NGƯỜI TẠO NOTE)", header_style))
        story.append(Paragraph(summary_data.get("about_creator", ""), body_style))

    # ==========================================
    # MODE: STANDARD SUMMARY
    # ==========================================
    elif mode == "standard":
            # 1. Title
        title = summary_data.get("title", "Document Summary")
        story.append(Spacer(1, 20))
        story.append(Paragraph(title, title_style))
        story.append(Spacer(1, 20))
        story.append(Paragraph("---", ParagraphStyle('Line', parent=body_style, alignment=TA_CENTER)))
        
        # 2. Overview
        story.append(Paragraph("TỔNG QUAN", header_style))
        overview = summary_data.get("overview", "")
        story.append(Paragraph(markdown_to_xml(overview), body_style))
        story.append(Spacer(1, 10))

        # 3. Key Points
        story.append(Paragraph("ĐIỂM CHÍNH", header_style))
        key_points = summary_data.get("key_points", [])
        if isinstance(key_points, list):
            for point in key_points:
                story.append(Paragraph(f"&bull; {markdown_to_xml(str(point))}", body_style))
        story.append(Spacer(1, 10))

        # 4. Conclusion
        story.append(Paragraph("KẾT LUẬN", header_style))
        conclusion = summary_data.get("conclusion", "")
        story.append(Paragraph(markdown_to_xml(conclusion), body_style))
        
    # ==========================================
    # MODE: SYNTOPIC / EXPERT REVIEW
    # ==========================================
    elif mode == "syntopic_review":
            review_text = summary_data.get("review_markdown", "")
            
            story.append(Spacer(1, 20))
            story.append(Paragraph("EXPERT REVIEW", title_style))
            category = summary_data.get("category", "")
            genre = summary_data.get("genre", "")
            if category:
                story.append(Paragraph(f"{category} | {genre}", slogan_style))
            
            story.append(Spacer(1, 20))
            
            # Simple formatting: Replace Markdown headers with Paragraph styles
            lines = review_text.split('\n')
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                if line.startswith("# "):
                    story.append(Paragraph(line[2:], title_style))
                elif line.startswith("## "):
                    story.append(Paragraph(line[3:], header_style))
                elif line.startswith("### "):
                    story.append(Paragraph(line[4:], sub_header_style)) 
                elif line.startswith("> "):
                    story.append(Paragraph(f"<i>{line[2:]}</i>", quote_style))
                elif line.startswith("* ") or line.startswith("- "):
                    story.append(Paragraph(f"&bull; {line[2:]}", body_style))
                else:
                    # Bold conversion hack
                    line = line.replace("**", "<b>").replace("**", "</b>") 
                    story.append(Paragraph(line, body_style))

    # Build PDF with Footer
    doc.build(story, onFirstPage=add_footer, onLaterPages=add_footer)
    return os.path.abspath(output_filename)

def summarize_document_v2(file_bytes, mime_type, api_key=None, api_keys=None, user_instructions="", cancel_check=None):
    """
    Summarizes document content using Gemini.
    """
    # 1. Prepare Key List
    keys_to_use = []
    if api_keys and len(api_keys) > 0:
        keys_to_use = api_keys
    elif api_key:
        keys_to_use = [api_key]
    else:
        env_key = os.environ.get("GOOGLE_API_KEY")
        if env_key:
            keys_to_use = [env_key]

    if not keys_to_use:
        raise ValueError("Missing API Key.")

    # Prepare Context
    parts = []
    if mime_type == "application/pdf":
        parts.append(types.Part.from_bytes(data=file_bytes, mime_type="application/pdf"))
    elif mime_type == "text/plain":
         try:
            text_content = file_bytes.decode('utf-8')
         except:
            text_content = file_bytes.decode('latin-1') # Fallback
         parts.append(types.Part.from_text(text=f"Content:\n{text_content}"))
    else:
        text_content = load_document(file_bytes, mime_type)
        parts.append(types.Part.from_text(text=f"Content:\n{text_content}"))

    # Add the system instruction and prompt
    full_prompt = f"{PROMPT_SUMMARIZE_DOCUMENT}\n{user_instructions}"
    parts.append(types.Part.from_text(text=full_prompt))

    # Config
    config = types.GenerateContentConfig(
        system_instruction=SUMMARIZER_SYSTEM_INSTRUCTION,
        response_mime_type="application/json",
        temperature=0.4
    )

    try:
        # Use rotation function which handles client creation internally
        response_text, model_name = generate_content_v2(keys_to_use, parts, config, cancel_check=cancel_check)
    except Exception as e:
        raise ValueError(f"Summarization failed: {str(e)}")

    # Parse JSON
    try:
        data = robust_json_parse(response_text)
        if isinstance(data, list):
            if data and isinstance(data[0], dict):
                data = data[0]
            else:
                 safe_print("Warning: JSON response is a list. Wrapping in dict.")
                 data = {"overview": str(data)}
                 
    except Exception as e:
        safe_print(f"JSON Parsing Failed: {e}")
        safe_print(f"Raw Output: {response_text[:200]}")
        raise ValueError("Could not parse JSON response.")

    safe_print("Summarization Completed.")
    return {
        "mode": "standard",
        "title": data.get("title", "Document Summary"),
        "overview": data.get("overview", ""),
        "key_points": data.get("key_points", []),
        "conclusion": data.get("conclusion", ""),
        "used_model": model_name
    }

def summarize_book_deep_dive(file_bytes: bytes, mime_type: str, api_key: str = None, api_keys: list[str] = None, cancel_check=None) -> dict:
    """
    Executes the 4-step deep dive summarization workflow.
    """
    # 1. Prepare Key List
    keys_to_use = []
    if api_keys and len(api_keys) > 0:
        keys_to_use = api_keys
    elif api_key:
        keys_to_use = [api_key]
    else:
        env_key = os.environ.get("GOOGLE_API_KEY")
        if env_key:
            keys_to_use = [env_key]

    if not keys_to_use:
        raise ValueError("Missing API Key.")

    # Prepare Context
    parts = []
    if mime_type == "application/pdf":
        parts.append(types.Part.from_bytes(data=file_bytes, mime_type="application/pdf"))
    elif mime_type == "text/plain":
         try:
            text_content = file_bytes.decode('utf-8')
         except:
            text_content = file_bytes.decode('latin-1') # Fallback
         parts.append(types.Part.from_text(text=f"Content:\n{text_content}"))
    else:
        text_content = load_document(file_bytes, mime_type)
        parts.append(types.Part.from_text(text=f"Content:\n{text_content}"))

    # Add the single shot prompt
    parts.append(types.Part.from_text(text=PROMPT_DEEP_DIVE_FULL))

    # Config
    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        temperature=0.4
    )

    try:
        response_text, model_name = generate_content_v2(keys_to_use, parts, config, cancel_check=cancel_check)
    except Exception as e:
        raise ValueError(f"Deep Dive failed: {str(e)}")

    # Parse JSON
    try:
        data = robust_json_parse(response_text)
    except Exception as e:
        safe_print(f"JSON Parsing Failed: {e}")
        safe_print(f"Raw Output: {response_text[:200]}")
        raise ValueError("Could not parse Deep Dive JSON response.")

    safe_print("Deep Dive Completed.")
    return {
        "mode": "deep_dive",
        "metadata": data.get("metadata", {}),
        "big_ideas": data.get("big_ideas", []),
        "introduction": data.get("introduction", {}),
        "core_ideas": data.get("core_ideas", []),
        "about_author": data.get("about_author", ""),
        "about_creator": data.get("about_creator", ""),
        "used_model": model_name 
    }

# --- SYNTOPIC REVIEW MODULE PROMPTS ---

PROMPT_REVIEW_LIBRARIAN = """
### ROLE
You are an expert Literary Taxonomist and Librarian.

### TASK
Analyze the provided book content/summary.
Determine the comprehensive metadata of the book to guide further analysis.

### OUTPUT FORMAT
Return a JSON object with the following fields:
1. "category": Strictly "Fiction" or "Non-Fiction".
2. "genre": The specific sub-genre (e.g., Hard Sci-Fi, Self-Help, Memoir, Financial Thriller).
3. "target_audience": A specific persona description of who should read this.
4. "core_theme": A single sentence summarizing the central theme.
5. "complexity_level": "Beginner", "Intermediate", or "Advanced".
"""

PROMPT_REVIEW_ANALYST_NON_FICTION = """
### ROLE
You are a Senior Research Analyst and Subject Matter Expert.

### TASK
Perform a deep-dive analysis on the Non-Fiction book.
Focus on extracting value, logic, and utility. Avoid generic summaries.

### INSTRUCTIONS
1. **The Big Idea:** Articulate the one main argument the author is trying to prove.
2. **Key Mental Models:** Extract 3-5 specific concepts, frameworks, or methodologies introduced in the book. Explain them clearly.
3. **Critical Assessment:** Evaluate the strength of the arguments. Are they backed by data? Where does the logic fail?
4. **Actionable Takeaways:** List 3 concrete steps a reader can apply immediately after reading.
5. **Comparison:** Briefly compare this book to 2 other famous books in the same niche.

### CONSTRAINT
Maintain an objective, analytical, and professional tone.
"""

PROMPT_REVIEW_ANALYST_FICTION = """
### ROLE
You are a Professional Literary Critic (like New York Times Book Review).

### TASK
Critique the Fiction book.
Focus on the narrative craft, emotional resonance, and artistic merit.

### INSTRUCTIONS
1. **World Building & Atmosphere:** Describe the setting and the mood. Is it immersive?
2. **Character Arc Analysis:** Analyze the protagonist's journey. Is the development earned and believable?
3. **Thematic Depth:** Explore the underlying messages (hidden meanings) beyond the surface plot.
4. **Writing Style:** Comment on the prose (e.g., lyrical, sparse, fast-paced). Quote a memorable line if possible.
5. **The "Page-Turner" Factor:** Rate the pacing and suspense. Does the ending resolve the conflict satisfactorily?

### CONSTRAINT
Avoid major spoilers. Use evocative and engaging language.
"""

PROMPT_REVIEW_EDITOR = """
### ROLE
You are the Editor-in-Chief of a premium book review app.

### TASK
Synthesize the analysis provided above into a final, highly readable, and professionally formatted book review using Markdown.

### LANGUAGE
Write the final output in {language}.

### SOURCE DATA
- Basic Info: {librarian_output}
- Deep Analysis: {analyst_output}

### FORMATTING GUIDELINES (STRICT)
Create the review using the following structure. Use icons/emojis where appropriate to enhance UI appeal.

# [Book Title] - Review
**Author:** [Author Name] | **Rating:** [Score]/10 | **Reading Time:** [Est. Hours]

---
## 🚀 The Verdict in 30 Seconds
[A punchy, 2-sentence summary of whether this book is worth reading and why.]

## 🧐 Deep Dive
[Synthesize the "Deep Analysis" here. Use sub-headers like "The Core Argument" or "The Narrative" depending on genre. Break text into short paragraphs.]

## 💎 Key Gems (Quotes or Concepts)
> "[Insert a powerful quote or concept from the analysis]"

## ✅ Who Is This For?
* [Persona 1]
* [Persona 2]

## ⚠️ The Caveat (Cons)
[What might readers dislike? e.g., "Too academic," "Slow middle section."]

## 🛠 Action Plan (If Non-Fiction) / 🎭 Mood (If Fiction)
[Insert Actionable Steps OR Mood Keywords]

---
## 🏆 Scoring & Extras
* **Originality:** [Score/10] | **Utility/Plot:** [Score/10] | **Readability:** [Score/10]
* **Similar Books:** If you like this, try [Book A] or [Book B].

*Generated by SlideGenius Expert Review Engine*
"""

class PartialCompletionError(Exception):
    def __init__(self, message, partial_data):
        super().__init__(message)
        self.partial_data = partial_data

def review_book_syntopic(file_bytes: bytes, mime_type: str, api_key: str = None, api_keys: list[str]=None, language: str = "Tiếng Việt", cancel_check=None, resume_state: dict = None) -> dict:
    """
    Executes the 3-step Syntopic Layered Analysis for Book Review.
    Supports RESUME functionality via resume_state.
    """
    # 1. Prepare Key List
    keys_to_use = []
    if api_keys and len(api_keys) > 0:
        keys_to_use = api_keys
    elif api_key:
        keys_to_use = [api_key]
    else:
        env_key = os.environ.get("GOOGLE_API_KEY")
        if env_key:
            keys_to_use = [env_key]

    if not keys_to_use:
        raise ValueError("Missing API Key.")
    
    # Load Content (Only if we need it for steps not yet done)
    # Metadata for efficiency: If we are at Step 3, we technically don't need the book content if we trust Step 1/2 outputs. 
    # But Step 2 needs it.
    
    parts = None
    if not resume_state or not resume_state.get("analyst_output"):
        if mime_type == "application/pdf":
            parts = [types.Part.from_bytes(data=file_bytes, mime_type="application/pdf")]
        else:
            text_content = load_document(file_bytes, mime_type)
            parts = [types.Part.from_text(text=f"Content:\n{text_content}")]

    # Recover State
    current_state = resume_state.copy() if resume_state else {}
    
    # --- STEP 1: LIBRARIAN (Classification) ---
    librarian_data = current_state.get("librarian_data")
    model1 = current_state.get("model1_name", "skipped")
    
    if not librarian_data:
        try:
            safe_print("Step 1: Librarian Agent (Classifying)...")
            config_json = types.GenerateContentConfig(response_mime_type="text/plain", temperature=0.3)
            
            parts_step1 = parts + [types.Part.from_text(text=PROMPT_REVIEW_LIBRARIAN)]
            resp1_text, model1 = generate_content_v2(keys_to_use, parts_step1, config_json, cancel_check=cancel_check)
            
            try:
                librarian_data = robust_json_parse(resp1_text)
                category = librarian_data.get("category", "Non-Fiction") 
                genre = librarian_data.get("genre", "General")
                safe_print(f"-> Classified as: {category} / {genre}")
            except:
                librarian_data = {"category": "Non-Fiction", "genre": "General"}
                safe_print("-> Librarian failed to JSON. Defaulting.")
            
            # Save Checkpoint
            current_state["librarian_data"] = librarian_data
            current_state["model1_name"] = model1
            
        except Exception as e:
            raise PartialCompletionError(f"Lỗi ở Bước 1 (Librarian): {str(e)}", current_state)

    else:
        safe_print("Skipping Step 1 (Already Done).")

    # --- STEP 2: ANALYST (Deep Dive) ---
    analyst_output = current_state.get("analyst_output")
    model2 = current_state.get("model2_name", "skipped")
    
    if not analyst_output:
        try:
            safe_print("Step 2: Analyst Agent (Deep Analysis)...")
            
            if librarian_data.get("category") == "Fiction":
                prompt_analyst = PROMPT_REVIEW_ANALYST_FICTION
            else:
                prompt_analyst = PROMPT_REVIEW_ANALYST_NON_FICTION
                
            parts_step2 = parts + [types.Part.from_text(text=prompt_analyst)]
            
            config_text = types.GenerateContentConfig(response_mime_type="text/plain", temperature=0.6)
            resp2_text, model2 = generate_content_v2(keys_to_use, parts_step2, config_text, cancel_check=cancel_check)
            analyst_output = resp2_text
            
            # Save Checkpoint
            current_state["analyst_output"] = analyst_output
            current_state["model2_name"] = model2
            
        except Exception as e:
            raise PartialCompletionError(f"Lỗi ở Bước 2 (Analyst): {str(e)}", current_state)
    else:
         safe_print("Skipping Step 2 (Already Done).")

    # --- STEP 3: EDITOR (Synthesis) ---
    # Editor uses the partials, not the raw book (as decided previously to save tokens/context)
    safe_print(f"Step 3: Editor Agent (Writing Review in {language})...")
    
    try:
        final_prompt = PROMPT_REVIEW_EDITOR.format(
            librarian_output=json.dumps(librarian_data, ensure_ascii=False),
            analyst_output=analyst_output,
            language=language
        )
        
        parts_step3 = [types.Part.from_text(text=final_prompt)] 
        
        config_text = types.GenerateContentConfig(response_mime_type="text/plain", temperature=0.6)
        review_markdown, model3 = generate_content_v2(keys_to_use, parts_step3, config_text, cancel_check=cancel_check)
        
    except Exception as e:
         # Even if Step 3 fails, we have Step 1 and 2.
         raise PartialCompletionError(f"Lỗi ở Bước 3 (Editor): {str(e)}", current_state)
    
    safe_print("Syntopic Review Completed.")
    
    return {
        "mode": "syntopic_review",
        "category": librarian_data.get("category"),
        "genre": librarian_data.get("genre"),
        "review_markdown": review_markdown,
        "used_model": f"{model1}->{model2}->{model3}"
    }

