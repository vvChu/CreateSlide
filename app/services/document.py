"""Document loading service — text extraction from PDF, DOCX, EPUB."""

from __future__ import annotations

import contextlib
import io
import os
import tempfile
import warnings

import docx
import ebooklib
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
from ebooklib import epub

warnings.filterwarnings("ignore", category=UserWarning, module="ebooklib")
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract text from PDF bytes using pypdf."""
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(file_bytes))
    pages = [p.extract_text() for p in reader.pages if p.extract_text()]
    result = "\n\n".join(pages)
    if not result.strip():
        raise ValueError("PDF không chứa text (có thể là PDF dạng ảnh/scan). Hãy dùng Gemini provider.")
    return result


def extract_text_from_docx(file_bytes: bytes) -> str:
    """Extract text from DOCX bytes."""
    doc = docx.Document(io.BytesIO(file_bytes))
    result = "\n".join(p.text for p in doc.paragraphs)
    if not result.strip():
        raise ValueError("DOCX không chứa text có thể trích xuất.")
    return result


def extract_text_from_epub(file_bytes: bytes) -> str:
    """Extract text from EPUB bytes (via temp file)."""
    tmp_path = ""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".epub") as tmp:
            tmp.write(file_bytes)
            tmp_path = tmp.name

        book = epub.read_epub(tmp_path)
        chunks: list[str] = []
        for item in book.get_items():
            is_doc = item.get_type() == ebooklib.ITEM_DOCUMENT
            is_html = item.media_type and ("html" in item.media_type or "xml" in item.media_type)
            if not (is_doc or is_html):
                continue
            content = item.get_content()
            if not content:
                continue
            soup = BeautifulSoup(content, "html.parser")
            text = soup.get_text(separator=" ", strip=True)
            if len(text) > 50:
                chunks.append(text)

        result = "\n\n".join(chunks)
        if not result.strip():
            raise ValueError("EPUB không chứa text có thể trích xuất.")
        return result
    finally:
        if tmp_path:
            with contextlib.suppress(OSError):
                os.remove(tmp_path)


def load_document(file_bytes: bytes, mime_type: str) -> str:
    """Dispatch to the correct extractor based on *mime_type*."""
    if not file_bytes:
        raise ValueError("File rỗng, không có dữ liệu.")

    extractors = {
        "application/pdf": extract_text_from_pdf,
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": extract_text_from_docx,
        "application/epub+zip": extract_text_from_epub,
    }
    fn = extractors.get(mime_type)
    if fn is None:
        raise ValueError(f"Định dạng file không được hỗ trợ: {mime_type}")
    return fn(file_bytes)
