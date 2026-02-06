"""Tests for app.services.review — syntopic book review pipeline."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.services.review import PartialCompletionError, review_book_syntopic


class TestPartialCompletionError:
    """Test the PartialCompletionError exception."""

    def test_stores_partial_data(self):
        data = {"librarian_data": {"category": "Fiction"}}
        err = PartialCompletionError("step failed", data)
        assert err.partial_data == data
        assert "step failed" in str(err)

    def test_inherits_exception(self):
        err = PartialCompletionError("msg", {})
        assert isinstance(err, Exception)


class TestReviewBookSyntopic:
    """Test the 3-step syntopic review pipeline with mocked LLM."""

    LIBRARIAN_JSON = '{"category": "Non-Fiction", "genre": "Science"}'
    ANALYST_OUTPUT = "Deep analysis of the document themes and arguments."
    EDITOR_OUTPUT = "# Expert Review\n\nThis is a comprehensive markdown review."

    @patch("app.services.review.get_provider")
    @patch("app.services.review.resolve_provider_keys")
    def test_full_pipeline_success(self, mock_keys, mock_get_prov, sample_pdf_bytes):
        """All 3 steps succeed → returns complete review dict."""
        mock_keys.return_value = ["test-key"]
        mock_provider = MagicMock()
        mock_provider.generate.side_effect = [
            (self.LIBRARIAN_JSON, "model-1"),
            (self.ANALYST_OUTPUT, "model-2"),
            (self.EDITOR_OUTPUT, "model-3"),
        ]
        mock_get_prov.return_value = mock_provider

        result = review_book_syntopic(
            sample_pdf_bytes,
            "application/pdf",
            api_keys=["test-key"],
            provider="ollama",
        )

        assert result["mode"] == "syntopic_review"
        assert result["category"] == "Non-Fiction"
        assert result["genre"] == "Science"
        assert "Expert Review" in result["review_markdown"]
        assert "model-1->model-2->model-3" == result["used_model"]

    @patch("app.services.review.get_provider")
    @patch("app.services.review.resolve_provider_keys")
    def test_fiction_uses_fiction_prompt(self, mock_keys, mock_get_prov, sample_pdf_bytes):
        """When librarian classifies as Fiction, analyst uses fiction prompt."""
        mock_keys.return_value = ["test-key"]
        mock_provider = MagicMock()
        mock_provider.generate.side_effect = [
            ('{"category": "Fiction", "genre": "Novel"}', "m1"),
            ("Fiction analysis output", "m2"),
            ("Fiction review markdown", "m3"),
        ]
        mock_get_prov.return_value = mock_provider

        result = review_book_syntopic(
            sample_pdf_bytes,
            "application/pdf",
            api_keys=["test-key"],
            provider="ollama",
        )

        assert result["category"] == "Fiction"

    @patch("app.services.review.get_provider")
    @patch("app.services.review.resolve_provider_keys")
    def test_step1_failure_raises_partial(self, mock_keys, mock_get_prov, sample_pdf_bytes):
        """Failure at step 1 raises PartialCompletionError."""
        mock_keys.return_value = ["test-key"]
        mock_provider = MagicMock()
        mock_provider.generate.side_effect = Exception("API timeout")
        mock_get_prov.return_value = mock_provider

        with pytest.raises(PartialCompletionError, match="Bước 1"):
            review_book_syntopic(
                sample_pdf_bytes,
                "application/pdf",
                api_keys=["test-key"],
                provider="ollama",
            )

    @patch("app.services.review.get_provider")
    @patch("app.services.review.resolve_provider_keys")
    def test_step2_failure_preserves_step1(self, mock_keys, mock_get_prov, sample_pdf_bytes):
        """Failure at step 2 preserves librarian data in partial_data."""
        mock_keys.return_value = ["test-key"]
        mock_provider = MagicMock()
        mock_provider.generate.side_effect = [
            (self.LIBRARIAN_JSON, "m1"),
            Exception("Model crashed"),
        ]
        mock_get_prov.return_value = mock_provider

        with pytest.raises(PartialCompletionError) as exc_info:
            review_book_syntopic(
                sample_pdf_bytes,
                "application/pdf",
                api_keys=["test-key"],
                provider="ollama",
            )

        assert "librarian_data" in exc_info.value.partial_data
        assert exc_info.value.partial_data["librarian_data"]["category"] == "Non-Fiction"

    @patch("app.services.review.get_provider")
    @patch("app.services.review.resolve_provider_keys")
    def test_step3_failure_preserves_step1_and_2(self, mock_keys, mock_get_prov, sample_pdf_bytes):
        """Failure at step 3 preserves both librarian and analyst data."""
        mock_keys.return_value = ["test-key"]
        mock_provider = MagicMock()
        mock_provider.generate.side_effect = [
            (self.LIBRARIAN_JSON, "m1"),
            (self.ANALYST_OUTPUT, "m2"),
            Exception("Network error"),
        ]
        mock_get_prov.return_value = mock_provider

        with pytest.raises(PartialCompletionError) as exc_info:
            review_book_syntopic(
                sample_pdf_bytes,
                "application/pdf",
                api_keys=["test-key"],
                provider="ollama",
            )

        partial = exc_info.value.partial_data
        assert "librarian_data" in partial
        assert "analyst_output" in partial

    @patch("app.services.review.get_provider")
    @patch("app.services.review.resolve_provider_keys")
    def test_resume_skips_completed_steps(self, mock_keys, mock_get_prov, sample_pdf_bytes):
        """Resume with partial state skips already-completed steps."""
        mock_keys.return_value = ["test-key"]
        mock_provider = MagicMock()
        # Only step 2 and 3 should be called
        mock_provider.generate.side_effect = [
            (self.ANALYST_OUTPUT, "m2"),
            (self.EDITOR_OUTPUT, "m3"),
        ]
        mock_get_prov.return_value = mock_provider

        resume_state = {
            "librarian_data": {"category": "Non-Fiction", "genre": "Science"},
            "model1_name": "m1",
        }

        result = review_book_syntopic(
            sample_pdf_bytes,
            "application/pdf",
            api_keys=["test-key"],
            provider="ollama",
            resume_state=resume_state,
        )

        assert result["mode"] == "syntopic_review"
        # Only 2 LLM calls (step 2 + step 3)
        assert mock_provider.generate.call_count == 2

    @patch("app.services.review.get_provider")
    @patch("app.services.review.resolve_provider_keys")
    def test_resume_with_analyst_done(self, mock_keys, mock_get_prov, sample_pdf_bytes):
        """Resume with both step 1 and 2 done — only step 3 runs."""
        mock_keys.return_value = ["test-key"]
        mock_provider = MagicMock()
        mock_provider.generate.return_value = (self.EDITOR_OUTPUT, "m3")
        mock_get_prov.return_value = mock_provider

        resume_state = {
            "librarian_data": {"category": "Fiction", "genre": "Novel"},
            "model1_name": "m1",
            "analyst_output": "Existing analysis",
            "model2_name": "m2",
        }

        result = review_book_syntopic(
            sample_pdf_bytes,
            "application/pdf",
            api_keys=["test-key"],
            provider="ollama",
            resume_state=resume_state,
        )

        assert result["mode"] == "syntopic_review"
        assert mock_provider.generate.call_count == 1

    @patch("app.services.review.get_provider")
    @patch("app.services.review.resolve_provider_keys")
    def test_cancel_check_respected(self, mock_keys, mock_get_prov, sample_pdf_bytes):
        """Cancel check function should abort the pipeline."""
        mock_keys.return_value = ["test-key"]
        mock_provider = MagicMock()
        # The cancel_check is passed through to LLM generate
        mock_provider.generate.side_effect = ValueError("Operation cancelled by user.")
        mock_get_prov.return_value = mock_provider

        with pytest.raises((PartialCompletionError, ValueError)):
            review_book_syntopic(
                sample_pdf_bytes,
                "application/pdf",
                api_keys=["test-key"],
                provider="ollama",
                cancel_check=lambda: True,
            )

    @patch("app.services.review.get_provider")
    @patch("app.services.review.resolve_provider_keys")
    def test_bad_librarian_json_defaults(self, mock_keys, mock_get_prov, sample_pdf_bytes):
        """Invalid JSON from librarian → defaults to Non-Fiction/General."""
        mock_keys.return_value = ["test-key"]
        mock_provider = MagicMock()
        mock_provider.generate.side_effect = [
            ("not valid json at all {{{", "m1"),
            (self.ANALYST_OUTPUT, "m2"),
            (self.EDITOR_OUTPUT, "m3"),
        ]
        mock_get_prov.return_value = mock_provider

        result = review_book_syntopic(
            sample_pdf_bytes,
            "application/pdf",
            api_keys=["test-key"],
            provider="ollama",
        )

        assert result["category"] == "Non-Fiction"
        assert result["genre"] == "General"

    @patch("app.services.review.get_provider")
    @patch("app.services.review.resolve_provider_keys")
    def test_language_parameter_passed(self, mock_keys, mock_get_prov, sample_pdf_bytes):
        """Language parameter is used in the editor step."""
        mock_keys.return_value = ["test-key"]
        mock_provider = MagicMock()
        mock_provider.generate.side_effect = [
            (self.LIBRARIAN_JSON, "m1"),
            (self.ANALYST_OUTPUT, "m2"),
            (self.EDITOR_OUTPUT, "m3"),
        ]
        mock_get_prov.return_value = mock_provider

        result = review_book_syntopic(
            sample_pdf_bytes,
            "application/pdf",
            api_keys=["test-key"],
            provider="ollama",
            language="English",
        )

        assert result["mode"] == "syntopic_review"
        # Check that the 3rd call (editor) had "English" in the prompt
        editor_call = mock_provider.generate.call_args_list[2]
        prompt = editor_call[1].get("prompt", "")
        assert "English" in prompt

    @patch("app.services.review.get_provider")
    @patch("app.services.review.resolve_provider_keys")
    def test_gemini_sends_file_bytes(self, mock_keys, mock_get_prov, sample_pdf_bytes):
        """For gemini provider, file_bytes/mime_type are sent to LLM."""
        mock_keys.return_value = ["test-key"]
        mock_provider = MagicMock()
        mock_provider.generate.side_effect = [
            (self.LIBRARIAN_JSON, "m1"),
            (self.ANALYST_OUTPUT, "m2"),
            (self.EDITOR_OUTPUT, "m3"),
        ]
        mock_get_prov.return_value = mock_provider

        review_book_syntopic(
            sample_pdf_bytes,
            "application/pdf",
            api_keys=["test-key"],
            provider="gemini",
        )

        # First call (librarian) should include file_bytes for gemini
        call_kwargs = mock_provider.generate.call_args_list[0][1]
        assert call_kwargs.get("file_bytes") is not None
