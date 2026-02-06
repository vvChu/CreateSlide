"""Tests for app.services.slide — slide generation orchestration."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.services.slide import analyze_document


class TestAnalyzeDocument:
    """Test the slide analysis service with mocked LLM."""

    VALID_SLIDE_JSON = '{"title": "AI Overview", "slides": [{"title": "Intro", "content": ["What is AI?"]}]}'

    @patch("app.services.slide.get_provider")
    @patch("app.services.slide.resolve_provider_keys")
    def test_returns_parsed_slides(self, mock_keys, mock_get_prov, sample_pdf_bytes):
        mock_keys.return_value = ["test-key"]
        mock_provider = MagicMock()
        mock_provider.generate.return_value = (self.VALID_SLIDE_JSON, "test-model")
        mock_get_prov.return_value = mock_provider

        result = analyze_document(
            sample_pdf_bytes,
            "application/pdf",
            provider="ollama",
            api_keys=["test-key"],
        )
        assert "title" in result
        assert "slides" in result
        assert len(result["slides"]) == 1

    @patch("app.services.slide.get_provider")
    @patch("app.services.slide.resolve_provider_keys")
    def test_list_response_wrapped_in_dict(self, mock_keys, mock_get_prov, sample_pdf_bytes):
        """When AI returns a list instead of dict, it should be wrapped."""
        mock_keys.return_value = ["test-key"]
        mock_provider = MagicMock()
        mock_provider.generate.return_value = (
            '[{"title": "Slide 1", "content": ["Point A"]}]',
            "test-model",
        )
        mock_get_prov.return_value = mock_provider

        result = analyze_document(
            sample_pdf_bytes,
            "application/pdf",
            provider="ollama",
            api_keys=["test-key"],
        )
        assert isinstance(result, dict)
        assert "slides" in result

    @patch("app.services.slide.get_provider")
    @patch("app.services.slide.resolve_provider_keys")
    def test_empty_content_gets_placeholder(self, mock_keys, mock_get_prov, sample_pdf_bytes):
        """Slides with empty content should get a placeholder."""
        mock_keys.return_value = ["test-key"]
        mock_provider = MagicMock()
        mock_provider.generate.return_value = (
            '{"title": "Test", "slides": [{"title": "Empty", "content": []}]}',
            "test-model",
        )
        mock_get_prov.return_value = mock_provider

        result = analyze_document(
            sample_pdf_bytes,
            "application/pdf",
            provider="ollama",
            api_keys=["test-key"],
        )
        slide = result["slides"][0]
        assert len(slide["content"]) > 0

    @patch("app.services.slide.get_provider")
    @patch("app.services.slide.resolve_provider_keys")
    def test_empty_ai_response_raises(self, mock_keys, mock_get_prov, sample_pdf_bytes):
        mock_keys.return_value = ["test-key"]
        mock_provider = MagicMock()
        mock_provider.generate.return_value = ("", "test-model")
        mock_get_prov.return_value = mock_provider

        with pytest.raises(ValueError, match="không trả về"):
            analyze_document(
                sample_pdf_bytes,
                "application/pdf",
                provider="ollama",
                api_keys=["test-key"],
            )

    @patch("app.services.slide.get_provider")
    @patch("app.services.slide.resolve_provider_keys")
    def test_detail_mode(self, mock_keys, mock_get_prov, sample_pdf_bytes):
        """Detail mode should produce a longer system instruction."""
        mock_keys.return_value = ["test-key"]
        mock_provider = MagicMock()
        mock_provider.generate.return_value = (self.VALID_SLIDE_JSON, "m")
        mock_get_prov.return_value = mock_provider

        analyze_document(
            sample_pdf_bytes,
            "application/pdf",
            provider="ollama",
            api_keys=["test-key"],
            detail_level="Chi tiết",
        )
        # Verify the system instruction includes detail mode
        call_kwargs = mock_provider.generate.call_args[1]
        assert "Chi tiết" in call_kwargs.get("system", "") or len(call_kwargs.get("system", "")) > 100
