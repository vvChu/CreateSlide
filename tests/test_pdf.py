"""Tests for app.rendering.pdf — PDF summary generation."""

from __future__ import annotations

import os

from app.rendering.pdf import _markdown_to_xml, save_summary_to_pdf


class TestMarkdownToXml:
    """Test markdown → ReportLab XML conversion helper."""

    def test_bold_conversion(self):
        result = _markdown_to_xml("This is **bold** text")
        assert "<b>bold</b>" in result

    def test_bold_only(self):
        """_markdown_to_xml only converts **bold**, not *italic*."""
        result = _markdown_to_xml("**important**")
        assert "<b>important</b>" in result

    def test_inline_code(self):
        result = _markdown_to_xml("Use `print()` function")
        assert "print()" in result

    def test_no_markdown(self):
        result = _markdown_to_xml("Plain text")
        assert "Plain text" in result

    def test_empty_string(self):
        result = _markdown_to_xml("")
        assert result == ""

    def test_special_xml_chars_escaped(self):
        result = _markdown_to_xml("x < y & z > w")
        assert "&amp;" in result
        assert "&lt;" in result
        assert "&gt;" in result


class TestSaveSummaryToPdf:
    """Test PDF generation — save_summary_to_pdf expects a dict, returns a filepath."""

    def _make_data(self, text: str = "Sample text", mode: str = "standard") -> dict:
        return {
            "mode": mode,
            "title": "Test Doc",
            "overview": text,
            "key_points": ["Point 1", "Point 2"],
            "conclusion": "Final thoughts.",
        }

    def test_returns_filepath(self, tmp_path):
        out = str(tmp_path / "test.pdf")
        result = save_summary_to_pdf(self._make_data(), out)
        assert isinstance(result, str)
        assert os.path.isfile(result)

    def test_pdf_file_starts_with_header(self, tmp_path):
        out = str(tmp_path / "test.pdf")
        save_summary_to_pdf(self._make_data(), out)
        with open(out, "rb") as f:
            assert f.read(5) == b"%PDF-"

    def test_empty_overview(self, tmp_path):
        out = str(tmp_path / "empty.pdf")
        data = self._make_data(text="")
        result = save_summary_to_pdf(data, out)
        assert os.path.isfile(result)

    def test_unicode_content(self, tmp_path):
        out = str(tmp_path / "vn.pdf")
        data = self._make_data(text="Trí tuệ nhân tạo là chủ đề quan trọng.")
        result = save_summary_to_pdf(data, out)
        assert os.path.isfile(result)

    def test_deep_dive_mode(self, tmp_path):
        out = str(tmp_path / "deep.pdf")
        data = {
            "mode": "deep_dive",
            "metadata": {"title": "Book", "author": "Author", "slogan": "Read more"},
            "big_ideas": ["Idea 1"],
            "introduction": {"text": "Intro text", "best_quote": "A quote"},
            "core_ideas": [{"title": "Core", "quote": "Q", "commentary": "C"}],
            "about_author": "Bio",
            "about_creator": "Me",
        }
        result = save_summary_to_pdf(data, out)
        assert os.path.isfile(result)

    def test_review_mode(self, tmp_path):
        out = str(tmp_path / "review.pdf")
        data = {
            "mode": "syntopic_review",
            "review_markdown": "# Review\n\nGood book.",
            "genre": "Non-Fiction",
            "category": "Science",
        }
        result = save_summary_to_pdf(data, out)
        assert os.path.isfile(result)
