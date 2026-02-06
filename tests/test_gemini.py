"""Tests for app.providers.gemini — Gemini provider error classification."""

from __future__ import annotations

import pytest

from app.providers.base import _AbortAllError, _PermanentModelError, _SkipModelError
from app.providers.gemini import GeminiProvider


class TestGeminiProvider:
    """Test Gemini provider properties and error classification."""

    def test_name(self):
        p = GeminiProvider(api_keys=["test-key"])
        assert p.name == "gemini"

    def test_default_models_non_empty(self):
        assert len(GeminiProvider.default_model_list) > 0

    def test_resolve_env_keys_empty(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_API_KEY", "")
        p = GeminiProvider()
        assert p._resolve_env_keys() == []

    def test_resolve_env_keys_present(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_API_KEY", "my-api-key")
        p = GeminiProvider()
        assert p._resolve_env_keys() == ["my-api-key"]


class TestGeminiErrorClassification:
    """Test _classify_error maps exceptions to correct sentinel types."""

    def test_rate_limit_429(self):
        with pytest.raises(_SkipModelError, match="Rate limited"):
            GeminiProvider._classify_error(Exception("RESOURCE_EXHAUSTED 429"), "model-x")

    def test_quota_zero_permanent(self):
        with pytest.raises(_PermanentModelError, match="Quota=0"):
            GeminiProvider._classify_error(Exception("RESOURCE_EXHAUSTED limit: 0"), "model-x")

    def test_not_found_404(self):
        with pytest.raises(_PermanentModelError, match="not found"):
            GeminiProvider._classify_error(Exception("NOT_FOUND 404"), "model-x")

    def test_invalid_api_key(self):
        with pytest.raises(_AbortAllError, match="không hợp lệ"):
            GeminiProvider._classify_error(Exception("INVALID_ARGUMENT API key not valid"), "model-x")

    def test_blocked_output(self):
        with pytest.raises(_SkipModelError, match="blocked"):
            GeminiProvider._classify_error(Exception("model output must contain"), "model-x")

    def test_tool_use_error(self):
        with pytest.raises(_SkipModelError, match="blocked"):
            GeminiProvider._classify_error(Exception("Tool use is not expected"), "model-x")

    def test_generic_error_becomes_skip(self):
        with pytest.raises(_SkipModelError):
            GeminiProvider._classify_error(Exception("some unknown error"), "model-x")
