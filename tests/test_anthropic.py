"""Tests for app.providers.anthropic_provider — Anthropic Claude provider."""

from __future__ import annotations

import pytest

from app.providers.anthropic_provider import AnthropicProvider, _classify_anthropic_error
from app.providers.base import _AbortAllError, _PermanentModelError, _SkipModelError


class TestAnthropicProvider:
    """Test Anthropic provider properties."""

    def test_name(self):
        p = AnthropicProvider(api_keys=["sk-ant-test"])
        assert p.name == "anthropic"

    def test_default_models_non_empty(self):
        assert len(AnthropicProvider.default_model_list) > 0

    def test_resolve_env_keys_empty(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "")
        p = AnthropicProvider()
        assert p._resolve_env_keys() == []

    def test_resolve_env_keys_present(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-my-key")
        p = AnthropicProvider()
        assert p._resolve_env_keys() == ["sk-ant-my-key"]


class TestAnthropicErrorClassification:
    """Test _classify_anthropic_error maps exceptions correctly."""

    def test_rate_limit(self):
        with pytest.raises(_SkipModelError, match="Rate limited"):
            _classify_anthropic_error(Exception("rate_limit_error 429"), "claude-3")

    def test_not_found(self):
        with pytest.raises(_PermanentModelError, match="not found"):
            _classify_anthropic_error(Exception("not_found_error 404"), "claude-99")

    def test_auth_error(self):
        with pytest.raises(_AbortAllError, match="không hợp lệ"):
            _classify_anthropic_error(Exception("authentication_error invalid api key"), "claude-3")

    def test_overloaded(self):
        with pytest.raises(_SkipModelError, match="overloaded"):
            _classify_anthropic_error(Exception("overloaded_error"), "claude-3")

    def test_generic_error(self):
        with pytest.raises(_SkipModelError):
            _classify_anthropic_error(Exception("some unknown"), "claude-3")
