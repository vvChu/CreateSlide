"""PDF rendering — font registration, styles, story builders, and export.

Centralises all ReportLab logic that was previously scattered in summarizer.py.
"""

from __future__ import annotations

import json
import os
import re

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
)

# ── Font state (module-level singletons) ─────────────────────────────────

HAS_UNICODE_FONT = False
FONT_FAMILY = "Helvetica"
FONT_REGULAR = "Helvetica"
FONT_BOLD = "Helvetica-Bold"
FONT_ITALIC = "Helvetica-Oblique"


def register_fonts() -> None:
    """Try to register a Unicode-capable font (Arial → DejaVu → Liberation)."""
    global HAS_UNICODE_FONT, FONT_FAMILY, FONT_REGULAR, FONT_BOLD, FONT_ITALIC

    if HAS_UNICODE_FONT:
        return

    def _first(paths: list[str]) -> str:
        for p in paths:
            if os.path.exists(p):
                return p
        return ""

    candidates = [
        {
            "family": "Arial",
            "regular": [
                "C:\\Windows\\Fonts\\arial.ttf",
                "/Library/Fonts/Arial.ttf",
                "/System/Library/Fonts/Supplemental/Arial.ttf",
            ],
            "bold": [
                "C:\\Windows\\Fonts\\arialbd.ttf",
                "/Library/Fonts/Arial Bold.ttf",
                "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
            ],
            "italic": [
                "C:\\Windows\\Fonts\\ariali.ttf",
                "/Library/Fonts/Arial Italic.ttf",
                "/System/Library/Fonts/Supplemental/Arial Italic.ttf",
            ],
        },
        {
            "family": "DejaVuSans",
            "regular": ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/local/share/fonts/DejaVuSans.ttf"],
            "bold": [
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                "/usr/local/share/fonts/DejaVuSans-Bold.ttf",
            ],
            "italic": [
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf",
                "/usr/local/share/fonts/DejaVuSans-Oblique.ttf",
            ],
        },
        {
            "family": "LiberationSans",
            "regular": [
                "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
                "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
            ],
            "bold": [
                "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
                "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
            ],
            "italic": [
                "/usr/share/fonts/truetype/liberation/LiberationSans-Italic.ttf",
                "/usr/share/fonts/truetype/liberation2/LiberationSans-Italic.ttf",
            ],
        },
    ]

    for cand in candidates:
        regular_path = _first(cand["regular"])
        if not regular_path:
            continue
        try:
            family = cand["family"]
            bold_name = f"{family}-Bold"
            italic_name = f"{family}-Italic"

            if family not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont(family, regular_path))

            bold_path = _first(cand["bold"])
            if bold_path and bold_name not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont(bold_name, bold_path))
            else:
                bold_name = family

            italic_path = _first(cand["italic"])
            if italic_path and italic_name not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont(italic_name, italic_path))
            else:
                italic_name = family

            pdfmetrics.registerFontFamily(
                family, normal=family, bold=bold_name, italic=italic_name, boldItalic=bold_name
            )

            FONT_FAMILY = family
            FONT_REGULAR = family
            FONT_BOLD = bold_name
            FONT_ITALIC = italic_name
            HAS_UNICODE_FONT = True
            return
        except Exception:
            continue


# ── XML / Markdown helpers ───────────────────────────────────────────────


def _markdown_to_xml(text: str) -> str:
    if not isinstance(text, str):
        text = json.dumps(text, ensure_ascii=False)
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    text = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"##\s*(.*?)\n", r"<b>\1</b><br/>", text)
    lines = text.split("\n")
    processed = []
    for line in lines:
        line = line.strip()
        if line.startswith("- ") or line.startswith("* "):
            processed.append(f"&bull; {line[2:]}<br/>")
        else:
            processed.append(line)
    return "<br/>".join(processed)


def _parse_markdown_lines(lines: list[str], story: list, styles: dict) -> None:
    for line in lines:
        line = line.strip()
        if not line:
            story.append(Spacer(1, 6))
            continue
        try:
            if line.startswith("# "):
                story.append(Paragraph(line[2:].strip(), styles["title"]))
                story.append(
                    Paragraph(
                        "---",
                        ParagraphStyle("Line", parent=styles["body"], alignment=TA_CENTER, textColor=colors.lightgrey),
                    )
                )
                story.append(Spacer(1, 10))
            elif line.startswith("## "):
                story.append(Paragraph(line[3:].strip(), styles["header"]))
            elif line.startswith("### "):
                story.append(Paragraph(line[4:].strip(), styles["sub_header"]))
            elif line.startswith("> "):
                text = line[2:].strip().strip('"')
                story.append(Paragraph(f"<i>\u201c{text}\u201d</i>", styles["quote"]))
            elif line.startswith("- ") or line.startswith("* "):
                text = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", line[2:].strip())
                story.append(Paragraph(f"&bull;  {text}", styles["body"]))
            elif line == "---":
                story.append(Spacer(1, 10))
                story.append(
                    Paragraph(
                        "---",
                        ParagraphStyle("Line", parent=styles["body"], alignment=TA_CENTER, textColor=colors.lightgrey),
                    )
                )
                story.append(Spacer(1, 10))
            else:
                text = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", line)
                text = re.sub(r"\*(.*?)\*", r"<i>\1</i>", text)
                story.append(Paragraph(text, styles["body"]))
        except Exception:
            story.append(Paragraph(line, styles["body"]))


# ── PDF styles ───────────────────────────────────────────────────────────


def _create_pdf_styles(font_regular: str, font_bold: str, font_italic: str) -> dict:
    base = getSampleStyleSheet()
    return {
        "base": base,
        "title": ParagraphStyle(
            "CustomTitle",
            parent=base["Title"],
            fontName=font_bold,
            fontSize=26,
            leading=36,
            spaceAfter=12,
            alignment=TA_CENTER,
            textColor=colors.darkblue,
        ),
        "slogan": ParagraphStyle(
            "CustomSlogan",
            parent=base["Normal"],
            fontName=font_regular,
            fontSize=14,
            spaceAfter=24,
            alignment=TA_CENTER,
            textColor=colors.grey,
        ),
        "header": ParagraphStyle(
            "CustomHeader",
            parent=base["Heading1"],
            fontName=font_bold,
            fontSize=16,
            spaceBefore=12,
            spaceAfter=12,
            textColor=colors.black,
            borderPadding=5,
            backColor=colors.whitesmoke,
        ),
        "sub_header": ParagraphStyle(
            "CustomSubHeader",
            parent=base["Heading2"],
            fontName=font_bold,
            fontSize=14,
            spaceBefore=10,
            spaceAfter=10,
            textColor=colors.darkslategray,
        ),
        "body": ParagraphStyle(
            "CustomBody",
            parent=base["Normal"],
            fontName=font_regular,
            fontSize=12,
            leading=18,
            spaceAfter=8,
            alignment=TA_JUSTIFY,
        ),
        "quote": ParagraphStyle(
            "CustomQuote",
            parent=base["Normal"],
            fontName=font_italic,
            fontSize=12,
            leading=18,
            leftIndent=20,
            rightIndent=20,
            spaceBefore=6,
            spaceAfter=6,
            textColor=colors.darkgreen,
            alignment=TA_JUSTIFY,
        ),
    }


def _make_footer(font_regular: str, label: str = "Document Summary"):
    def _footer(canvas_obj, doc):
        canvas_obj.saveState()
        canvas_obj.setFont(font_regular, 9)
        canvas_obj.setFillColor(colors.grey)
        canvas_obj.drawString(50, 20, f"\u00a9 2026 Truong Tuan Anh | {label}")
        canvas_obj.drawRightString(A4[0] - 50, 20, f"Page {doc.page}")
        canvas_obj.restoreState()

    return _footer


# ── Per-mode story builders ──────────────────────────────────────────────


def _build_review_story(data: dict, styles: dict) -> list:
    story = []
    review_text = data.get("review_markdown", "")
    genre = data.get("genre", "Book Review")
    category = data.get("category", "General")
    story.append(Spacer(1, 20))
    story.append(
        Paragraph(
            "EXPERT BOOK REVIEW",
            ParagraphStyle(
                "Brand", parent=styles["base"]["Normal"], alignment=TA_CENTER, fontSize=10, textColor=colors.grey
            ),
        )
    )
    story.append(
        Paragraph(
            f"{category} | {genre}",
            ParagraphStyle(
                "SubBrand", parent=styles["base"]["Normal"], alignment=TA_CENTER, fontSize=9, textColor=colors.grey
            ),
        )
    )
    story.append(Spacer(1, 10))
    _parse_markdown_lines(review_text.split("\n"), story, styles)
    return story


def _build_deep_dive_story(data: dict, styles: dict) -> list:
    story = []
    base = styles["base"]
    body = styles["body"]
    metadata = data.get("metadata", {})
    doc_title = metadata.get("title", "BOOK SUMMARY")
    doc_author = metadata.get("author", "Unknown Author")
    doc_slogan = metadata.get("slogan", "More Wisdom in Less Time")

    story.append(Spacer(1, 30))
    story.append(
        Paragraph(
            "BOOK NOTES",
            ParagraphStyle("Brand", parent=base["Normal"], alignment=TA_CENTER, fontSize=10, textColor=colors.grey),
        )
    )
    story.append(
        Paragraph(
            "More Wisdom in Less Time",
            ParagraphStyle("SubBrand", parent=base["Normal"], alignment=TA_CENTER, fontSize=8, textColor=colors.grey),
        )
    )
    story.append(Spacer(1, 15))
    story.append(Paragraph(doc_title.upper(), styles["title"]))
    story.append(Paragraph(doc_slogan, styles["slogan"]))
    story.append(
        Paragraph(f"<b>By {doc_author}</b>", ParagraphStyle("Author", parent=body, alignment=TA_CENTER, fontSize=12))
    )
    story.append(Spacer(1, 15))
    story.append(Paragraph("---", ParagraphStyle("Line", parent=body, alignment=TA_CENTER)))

    story.append(Paragraph("THE BIG IDEAS (CÁC Ý TƯỞNG LỚN)", styles["header"]))
    big_ideas = data.get("big_ideas", [])
    if isinstance(big_ideas, list):
        for idea in big_ideas:
            story.append(Paragraph(f"&bull; <b>{idea}</b>", body))
    story.append(Spacer(1, 15))
    story.append(Paragraph("---", ParagraphStyle("Line", parent=body, alignment=TA_CENTER)))

    intro_data = data.get("introduction", {})
    story.append(Paragraph("GIỚI THIỆU", styles["header"]))
    if intro_data.get("text"):
        story.append(Paragraph(intro_data["text"], body))
    if intro_data.get("best_quote"):
        story.append(Spacer(1, 8))
        story.append(Paragraph(f"<i>\u201c{intro_data['best_quote']}\u201d</i>", styles["quote"]))
        story.append(
            Paragraph(
                f"\u2014 {doc_author}", ParagraphStyle("QuoteAuthor", parent=body, alignment=TA_RIGHT, fontSize=10)
            )
        )
    story.append(PageBreak())

    for idea in data.get("core_ideas", []):
        elements = []
        title = idea.get("title", "BIG IDEA")
        quote = idea.get("quote", "")
        commentary = idea.get("commentary", "")
        elements.append(
            Paragraph(
                title.upper(),
                ParagraphStyle(
                    "IdeaTitle",
                    parent=base["Heading2"],
                    fontName=FONT_BOLD,
                    fontSize=14,
                    spaceBefore=6,
                    textColor=colors.darkblue,
                ),
            )
        )
        if quote:
            elements.append(Paragraph(f"<i>\u201c{quote}\u201d</i>", styles["quote"]))
        if commentary:
            elements.append(
                Paragraph(
                    "<b>\U0001f4a1 Key Insight:</b>",
                    ParagraphStyle("AIHeader", parent=body, fontSize=10, textColor=colors.darkorange, spaceBefore=4),
                )
            )
            elements.append(Paragraph(_markdown_to_xml(commentary), body))
        elements.append(Spacer(1, 10))
        elements.append(Paragraph("---", ParagraphStyle("Line", parent=body, alignment=TA_CENTER)))
        elements.append(Spacer(1, 10))
        story.append(KeepTogether(elements))
    story.append(PageBreak())

    story.append(Paragraph("ABOUT THE AUTHOR (VỀ TÁC GIẢ)", styles["header"]))
    story.append(Paragraph(data.get("about_author", ""), body))
    story.append(Spacer(1, 20))
    story.append(Paragraph("ABOUT THE NOTE CREATOR (VỀ NGƯỜI TẠO NOTE)", styles["header"]))
    story.append(Paragraph(data.get("about_creator", ""), body))
    return story


def _build_standard_story(data: dict, styles: dict) -> list:
    story = []
    body = styles["body"]
    title = data.get("title", "Document Summary")
    story.append(Spacer(1, 20))
    story.append(Paragraph(title, styles["title"]))
    story.append(Spacer(1, 20))
    story.append(Paragraph("---", ParagraphStyle("Line", parent=body, alignment=TA_CENTER)))
    story.append(Paragraph("TỔNG QUAN", styles["header"]))
    story.append(Paragraph(_markdown_to_xml(data.get("overview", "")), body))
    story.append(Spacer(1, 10))
    story.append(Paragraph("ĐIỂM CHÍNH", styles["header"]))
    for point in data.get("key_points", []):
        story.append(Paragraph(f"&bull; {_markdown_to_xml(str(point))}", body))
    story.append(Spacer(1, 10))
    story.append(Paragraph("KẾT LUẬN", styles["header"]))
    story.append(Paragraph(_markdown_to_xml(data.get("conclusion", "")), body))
    return story


# ── Public API ───────────────────────────────────────────────────────────


def save_summary_to_pdf(summary_data: dict, output_filename: str = "summary.pdf") -> str:
    """Render *summary_data* to a PDF file and return the absolute path."""
    register_fonts()
    styles = _create_pdf_styles(FONT_REGULAR, FONT_BOLD, FONT_ITALIC)
    mode = summary_data.get("mode", "standard")

    if mode == "syntopic_review":
        story = _build_review_story(summary_data, styles)
        footer_label = "Expert Review"
    elif mode == "deep_dive":
        story = _build_deep_dive_story(summary_data, styles)
        footer_label = "Document Summary"
    else:
        story = _build_standard_story(summary_data, styles)
        footer_label = "Document Summary"

    doc = SimpleDocTemplate(
        output_filename,
        pagesize=A4,
        rightMargin=50,
        leftMargin=50,
        topMargin=50,
        bottomMargin=50,
    )
    footer = _make_footer(FONT_REGULAR, footer_label)
    try:
        doc.build(story, onFirstPage=footer, onLaterPages=footer)
    except Exception as exc:
        raise ValueError(f"Lỗi tạo PDF: {exc}") from exc
    return os.path.abspath(output_filename)
