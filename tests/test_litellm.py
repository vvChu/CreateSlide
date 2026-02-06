"""Tests for app.providers.litellm_provider — LiteLLM universal provider."""

from __future__ import annotations

import pytest

from app.providers.base import _AbortAllError, _PermanentModelError, _SkipModelError
from app.providers.litellm_provider import LiteLLMProvider, _classify_litellm_error


class TestLiteLLMProvider:
    """Test LiteLLM provider properties."""

    def test_name(self):
        p = LiteLLMProvider(api_keys=["test"])
        assert p.name == "litellm"

    def test_default_models_non_empty(self):
        assert len(LiteLLMProvider.default_model_list) > 0

    def test_custom_models(self):
        p = LiteLLMProvider(models=["groq/llama3-70b", "together/mistral-7b"])
        assert p.default_model_list == ["groq/llama3-70b", "together/mistral-7b"]

    def test_resolve_env_keys_fallback(self, monkeypatch):
        monkeypatch.setenv("LITELLM_API_KEY", "")
        monkeypatch.setenv("OPENAI_API_KEY", "")
        p = LiteLLMProvider()
        keys = p._resolve_env_keys()
        assert len(keys) == 1
        assert keys[0] == "litellm"  # fallback

    def test_resolve_env_keys_litellm(self, monkeypatch):
        monkeypatch.setenv("LITELLM_API_KEY", "my-litellm-key")
        p = LiteLLMProvider()
        assert p._resolve_env_keys() == ["my-litellm-key"]


class TestLiteLLMErrorClassification:
    """Test _classify_litellm_error maps exceptions correctly."""

    def test_rate_limit(self):
        with pytest.raises(_SkipModelError, match="Rate limited"):
            _classify_litellm_error(Exception("rate_limit_error 429"), "openai/gpt-4o")

    def test_not_found(self):
        with pytest.raises(_PermanentModelError, match="not found"):
            _classify_litellm_error(Exception("not_found_error 404"), "openai/gpt-99")

    def test_does_not_exist(self):
        with pytest.raises(_PermanentModelError, match="not found"):
            _classify_litellm_error(Exception("model does not exist"), "fake/model")

    def test_auth_error(self):
        with pytest.raises(_AbortAllError, match="không hợp lệ"):
            _classify_litellm_error(Exception("invalid_api_key 401"), "openai/gpt-4o")

    def test_timeout(self):
        with pytest.raises(_SkipModelError, match="Timeout"):
            _classify_litellm_error(Exception("timeout error"), "openai/gpt-4o")

    def test_generic_error(self):
        with pytest.raises(_SkipModelError):
            _classify_litellm_error(Exception("some random"), "model-x")
