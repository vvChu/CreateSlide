"""Tests for app.services.summary — document summarisation."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.services.summary import summarize_book_deep_dive, summarize_document


class TestSummarizeDocument:
    """Test standard document summarisation with mocked LLM."""

    VALID_SUMMARY_JSON = """{
        "title": "AI Overview",
        "overview": "A comprehensive summary",
        "key_points": ["Point 1", "Point 2"],
        "conclusion": "Final thoughts"
    }"""

    @patch("app.services.summary.get_provider")
    @patch("app.services.summary.resolve_provider_keys")
    def test_returns_standard_mode(self, mock_keys, mock_get_prov, sample_pdf_bytes):
        mock_keys.return_value = ["test-key"]
        mock_provider = MagicMock()
        mock_provider.generate.return_value = (self.VALID_SUMMARY_JSON, "test-model")
        mock_get_prov.return_value = mock_provider

        result = summarize_document(
            sample_pdf_bytes,
            "application/pdf",
            provider="ollama",
            api_keys=["test-key"],
        )

        assert result["mode"] == "standard"
        assert result["title"] == "AI Overview"
        assert len(result["key_points"]) == 2
        assert result["used_model"] == "test-model"

    @patch("app.services.summary.get_provider")
    @patch("app.services.summary.resolve_provider_keys")
    def test_list_response_wrapped(self, mock_keys, mock_get_prov, sample_pdf_bytes):
        """When AI returns a list, first element should be used."""
        mock_keys.return_value = ["test-key"]
        mock_provider = MagicMock()
        mock_provider.generate.return_value = (
            '[{"title": "List Title", "overview": "Listed"}]',
            "m",
        )
        mock_get_prov.return_value = mock_provider

        result = summarize_document(
            sample_pdf_bytes,
            "application/pdf",
            provider="ollama",
            api_keys=["test-key"],
        )

        assert result["mode"] == "standard"
        assert result["title"] == "List Title"

    @patch("app.services.summary.get_provider")
    @patch("app.services.summary.resolve_provider_keys")
    def test_user_instructions_included(self, mock_keys, mock_get_prov, sample_pdf_bytes):
        """Custom user instructions should be appended to prompt."""
        mock_keys.return_value = ["test-key"]
        mock_provider = MagicMock()
        mock_provider.generate.return_value = (self.VALID_SUMMARY_JSON, "m")
        mock_get_prov.return_value = mock_provider

        summarize_document(
            sample_pdf_bytes,
            "application/pdf",
            provider="ollama",
            api_keys=["test-key"],
            user_instructions="Focus on chapter 2",
        )

        call_kwargs = mock_provider.generate.call_args[1]
        assert "Focus on chapter 2" in call_kwargs["prompt"]

    @patch("app.services.summary.get_provider")
    @patch("app.services.summary.resolve_provider_keys")
    def test_gemini_sends_file_bytes(self, mock_keys, mock_get_prov, sample_pdf_bytes):
        mock_keys.return_value = ["test-key"]
        mock_provider = MagicMock()
        mock_provider.generate.return_value = (self.VALID_SUMMARY_JSON, "m")
        mock_get_prov.return_value = mock_provider

        summarize_document(
            sample_pdf_bytes,
            "application/pdf",
            provider="gemini",
            api_keys=["test-key"],
        )

        call_kwargs = mock_provider.generate.call_args[1]
        assert call_kwargs.get("file_bytes") is not None
        assert call_kwargs.get("mime_type") == "application/pdf"

    @patch("app.services.summary.get_provider")
    @patch("app.services.summary.resolve_provider_keys")
    def test_ollama_prepends_doc_text(self, mock_keys, mock_get_prov, sample_pdf_bytes):
        """For ollama, document text should be prepended to prompt."""
        mock_keys.return_value = ["http://localhost:11444/v1"]
        mock_provider = MagicMock()
        mock_provider.generate.return_value = (self.VALID_SUMMARY_JSON, "m")
        mock_get_prov.return_value = mock_provider

        summarize_document(
            sample_pdf_bytes,
            "application/pdf",
            provider="ollama",
            api_keys=["http://localhost:11444/v1"],
        )

        call_kwargs = mock_provider.generate.call_args[1]
        assert "Nội dung tài liệu" in call_kwargs["prompt"]
        assert call_kwargs.get("file_bytes") is None

    @patch("app.services.summary.get_provider")
    @patch("app.services.summary.resolve_provider_keys")
    def test_missing_fields_get_defaults(self, mock_keys, mock_get_prov, sample_pdf_bytes):
        mock_keys.return_value = ["test-key"]
        mock_provider = MagicMock()
        mock_provider.generate.return_value = ('{"overview": "just overview"}', "m")
        mock_get_prov.return_value = mock_provider

        result = summarize_document(
            sample_pdf_bytes,
            "application/pdf",
            provider="ollama",
            api_keys=["test-key"],
        )

        assert result["title"] == "Document Summary"
        assert result["key_points"] == []
        assert result["conclusion"] == ""


class TestSummarizeBookDeepDive:
    """Test deep dive summarisation with mocked LLM."""

    VALID_DEEP_DIVE_JSON = """{
        "metadata": {"title": "Book Title", "author": "Author Name", "slogan": "Read more"},
        "big_ideas": ["Idea 1", "Idea 2"],
        "introduction": {"text": "Book intro", "best_quote": "A great quote"},
        "core_ideas": [{"title": "Core 1", "quote": "Q1", "commentary": "C1"}],
        "about_author": "About the author",
        "about_creator": "Note creator info"
    }"""

    @patch("app.services.summary.get_provider")
    @patch("app.services.summary.resolve_provider_keys")
    def test_returns_deep_dive_mode(self, mock_keys, mock_get_prov, sample_pdf_bytes):
        mock_keys.return_value = ["test-key"]
        mock_provider = MagicMock()
        mock_provider.generate.return_value = (self.VALID_DEEP_DIVE_JSON, "test-model")
        mock_get_prov.return_value = mock_provider

        result = summarize_book_deep_dive(
            sample_pdf_bytes,
            "application/pdf",
            provider="ollama",
            api_keys=["test-key"],
        )

        assert result["mode"] == "deep_dive"
        assert result["metadata"]["title"] == "Book Title"
        assert len(result["big_ideas"]) == 2
        assert len(result["core_ideas"]) == 1
        assert result["used_model"] == "test-model"

    @patch("app.services.summary.get_provider")
    @patch("app.services.summary.resolve_provider_keys")
    def test_missing_fields_get_defaults(self, mock_keys, mock_get_prov, sample_pdf_bytes):
        mock_keys.return_value = ["test-key"]
        mock_provider = MagicMock()
        mock_provider.generate.return_value = ('{"metadata": {}}', "m")
        mock_get_prov.return_value = mock_provider

        result = summarize_book_deep_dive(
            sample_pdf_bytes,
            "application/pdf",
            provider="ollama",
            api_keys=["test-key"],
        )

        assert result["mode"] == "deep_dive"
        assert result["big_ideas"] == []
        assert result["core_ideas"] == []
        assert result["about_author"] == ""

    @patch("app.services.summary.get_provider")
    @patch("app.services.summary.resolve_provider_keys")
    def test_ollama_prepends_doc_text(self, mock_keys, mock_get_prov, sample_pdf_bytes):
        mock_keys.return_value = ["http://localhost:11444/v1"]
        mock_provider = MagicMock()
        mock_provider.generate.return_value = (self.VALID_DEEP_DIVE_JSON, "m")
        mock_get_prov.return_value = mock_provider

        summarize_book_deep_dive(
            sample_pdf_bytes,
            "application/pdf",
            provider="ollama",
            api_keys=["http://localhost:11444/v1"],
        )

        call_kwargs = mock_provider.generate.call_args[1]
        assert "Nội dung tài liệu" in call_kwargs["prompt"]

    @patch("app.services.summary.get_provider")
    @patch("app.services.summary.resolve_provider_keys")
    def test_cancel_check_passed_through(self, mock_keys, mock_get_prov, sample_pdf_bytes):
        mock_keys.return_value = ["test-key"]
        mock_provider = MagicMock()
        mock_provider.generate.return_value = (self.VALID_DEEP_DIVE_JSON, "m")
        mock_get_prov.return_value = mock_provider

        cancel_fn = lambda: False  # noqa: E731

        summarize_book_deep_dive(
            sample_pdf_bytes,
            "application/pdf",
            provider="ollama",
            api_keys=["test-key"],
            cancel_check=cancel_fn,
        )

        call_kwargs = mock_provider.generate.call_args[1]
        assert call_kwargs["cancel_check"] is cancel_fn
