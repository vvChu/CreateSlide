"""Tests for app.providers.openai_provider — OpenAI provider and error classification."""

from __future__ import annotations

import pytest

from app.providers.base import _AbortAllError, _PermanentModelError, _SkipModelError
from app.providers.openai_provider import OpenAIProvider, _classify_openai_error


class TestOpenAIProvider:
    """Test OpenAI provider properties."""

    def test_name(self):
        p = OpenAIProvider(api_keys=["sk-test"])
        assert p.name == "openai"

    def test_default_models_non_empty(self):
        assert len(OpenAIProvider.default_model_list) > 0

    def test_resolve_env_keys_empty(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "")
        p = OpenAIProvider()
        assert p._resolve_env_keys() == []

    def test_resolve_env_keys_present(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-my-key")
        p = OpenAIProvider()
        assert p._resolve_env_keys() == ["sk-my-key"]


class TestOpenAIErrorClassification:
    """Test _classify_openai_error maps exceptions to correct sentinel types."""

    def test_rate_limit_429(self):
        with pytest.raises(_SkipModelError, match="Rate limited"):
            _classify_openai_error(Exception("Error 429 rate_limit_exceeded"), "gpt-4o")

    def test_insufficient_quota(self):
        with pytest.raises(_PermanentModelError, match="No quota"):
            _classify_openai_error(Exception("429 insufficient_quota"), "gpt-4o")

    def test_model_not_found_404(self):
        with pytest.raises(_PermanentModelError, match="not found"):
            _classify_openai_error(Exception("404 model_not_found"), "gpt-99")

    def test_invalid_api_key(self):
        with pytest.raises(_AbortAllError, match="không hợp lệ"):
            _classify_openai_error(Exception("invalid_api_key: incorrect key"), "gpt-4o")

    def test_authentication_error(self):
        with pytest.raises(_AbortAllError, match="không hợp lệ"):
            _classify_openai_error(Exception("Authentication failed"), "gpt-4o")

    def test_content_filter(self):
        with pytest.raises(_SkipModelError, match="Content filtered"):
            _classify_openai_error(Exception("content_filter triggered"), "gpt-4o")

    def test_content_policy(self):
        with pytest.raises(_SkipModelError, match="Content filtered"):
            _classify_openai_error(Exception("content_policy violation"), "gpt-4o")

    def test_generic_error_becomes_skip(self):
        with pytest.raises(_SkipModelError):
            _classify_openai_error(Exception("some random error"), "gpt-4o")


class TestOpenAIChatCompletion:
    """Test the _chat_completion static method with mocked client."""

    def test_reasoning_model_uses_developer_role(self):
        """o-series models should use 'developer' role for system messages."""
        from unittest.mock import MagicMock

        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.choices = [MagicMock()]
        mock_resp.choices[0].message.content = "Response text"
        mock_client.chat.completions.create.return_value = mock_resp

        result = OpenAIProvider._chat_completion(mock_client, "o3-mini", "system msg", "prompt", False, 0.7)

        assert result == "Response text"
        call_kwargs = mock_client.chat.completions.create.call_args[1]
        # o-series: system becomes "developer" role
        assert call_kwargs["messages"][0]["role"] == "developer"
        # o-series: no temperature
        assert "temperature" not in call_kwargs

    def test_regular_model_uses_system_role(self):
        """Non-o-series models should use 'system' role."""
        from unittest.mock import MagicMock

        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.choices = [MagicMock()]
        mock_resp.choices[0].message.content = "Hello"
        mock_client.chat.completions.create.return_value = mock_resp

        result = OpenAIProvider._chat_completion(mock_client, "gpt-4o", "system msg", "prompt", False, 0.7)

        assert result == "Hello"
        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert call_kwargs["messages"][0]["role"] == "system"
        assert call_kwargs["temperature"] == 0.7

    def test_json_response_format(self):
        """response_format_json=True should set response_format."""
        from unittest.mock import MagicMock

        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.choices = [MagicMock()]
        mock_resp.choices[0].message.content = '{"key": "value"}'
        mock_client.chat.completions.create.return_value = mock_resp

        OpenAIProvider._chat_completion(mock_client, "gpt-4o", "", "prompt", True, 0.7)

        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert call_kwargs["response_format"] == {"type": "json_object"}

    def test_no_system_message(self):
        """Empty system string should not add system message."""
        from unittest.mock import MagicMock

        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.choices = [MagicMock()]
        mock_resp.choices[0].message.content = "Result"
        mock_client.chat.completions.create.return_value = mock_resp

        OpenAIProvider._chat_completion(mock_client, "gpt-4o", "", "prompt", False, 0.7)

        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert len(call_kwargs["messages"]) == 1
        assert call_kwargs["messages"][0]["role"] == "user"
