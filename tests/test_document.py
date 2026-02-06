"""Tests for app.services.document — text extraction from files."""

from __future__ import annotations

import pytest

from app.services.document import (
    extract_text_from_docx,
    extract_text_from_pdf,
    load_document,
)


class TestLoadDocument:
    """Test the document loader dispatcher."""

    def test_unsupported_mime_raises(self):
        with pytest.raises(ValueError, match="không được hỗ trợ"):
            load_document(b"data", "text/plain")

    def test_empty_bytes_raises(self):
        with pytest.raises(ValueError, match="rỗng"):
            load_document(b"", "application/pdf")

    def test_load_pdf(self, sample_pdf_bytes):
        text = load_document(sample_pdf_bytes, "application/pdf")
        assert "Artificial Intelligence" in text or "test document" in text.lower()

    def test_load_docx(self, sample_docx_bytes):
        mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        text = load_document(sample_docx_bytes, mime)
        assert "machine learning" in text.lower()


class TestExtractPdf:
    """Test PDF text extraction."""

    def test_valid_pdf(self, sample_pdf_bytes):
        text = extract_text_from_pdf(sample_pdf_bytes)
        assert len(text) > 10
        assert "Artificial Intelligence" in text or "test document" in text.lower()

    def test_invalid_pdf_raises(self):
        with pytest.raises(Exception):
            extract_text_from_pdf(b"not a pdf file")


class TestExtractDocx:
    """Test DOCX text extraction."""

    def test_valid_docx(self, sample_docx_bytes):
        text = extract_text_from_docx(sample_docx_bytes)
        assert "machine learning" in text.lower()

    def test_invalid_docx_raises(self):
        with pytest.raises(Exception):
            extract_text_from_docx(b"not a docx file")
