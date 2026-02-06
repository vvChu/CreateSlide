"""Tests for app.providers — registry, base class, and concrete providers."""

from __future__ import annotations

import pytest

from app.providers.base import LLMProvider, _AbortAllError, _PermanentModelError, _SkipModelError
from app.providers.registry import get_provider, list_providers, register_provider, resolve_provider_keys

# ── Registry tests ──────────────────────────────────────────────────────


class TestRegistry:
    """Test provider discovery and instantiation."""

    def test_list_providers_returns_expected(self):
        providers = list_providers()
        assert "gemini" in providers
        assert "openai" in providers
        assert "ollama" in providers

    def test_list_providers_is_sorted(self):
        providers = list_providers()
        assert providers == sorted(providers)

    def test_get_provider_ollama(self):
        provider = get_provider("ollama", api_keys=["test-key"])
        assert provider.name == "ollama"

    def test_get_provider_gemini(self):
        provider = get_provider("gemini", api_keys=["test-key"])
        assert provider.name == "gemini"

    def test_get_provider_openai(self):
        provider = get_provider("openai", api_keys=["test-key"])
        assert provider.name == "openai"

    def test_get_provider_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown provider"):
            get_provider("nonexistent_provider")

    def test_get_provider_case_insensitive(self):
        provider = get_provider("OLLAMA", api_keys=["test-key"])
        assert provider.name == "ollama"

    def test_register_custom_provider(self):
        class DummyProvider(LLMProvider):
            name = "dummy"
            default_model_list = ["dummy-1"]

            def _call_model(self, **kwargs):
                return "hello"

            def _resolve_env_keys(self):
                return ["key"]

        register_provider("dummy", DummyProvider)
        assert "dummy" in list_providers()
        p = get_provider("dummy", api_keys=["key"])
        assert p.name == "dummy"


# ── resolve_provider_keys tests ─────────────────────────────────────────


class TestResolveProviderKeys:
    """Test key resolution logic."""

    def test_explicit_api_keys_list(self):
        keys = resolve_provider_keys("gemini", api_keys=["key1", "key2"])
        assert keys == ["key1", "key2"]

    def test_explicit_single_key(self):
        keys = resolve_provider_keys("openai", api_key="sk-test")
        assert keys == ["sk-test"]

    def test_explicit_keys_strip_whitespace(self):
        keys = resolve_provider_keys("gemini", api_keys=["  key1  ", "  key2  "])
        assert keys == ["key1", "key2"]

    def test_deduplication(self):
        keys = resolve_provider_keys("gemini", api_keys=["a", "b", "a", "b"])
        assert keys == ["a", "b"]

    def test_ollama_fallback_to_base_url(self):
        keys = resolve_provider_keys("ollama")
        assert len(keys) >= 1
        assert keys[0].startswith("http")

    def test_missing_key_raises(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_API_KEY", "")
        from app.config import get_settings

        get_settings.cache_clear()
        with pytest.raises(ValueError, match="API Key"):
            resolve_provider_keys("gemini")

    def test_empty_strings_filtered(self):
        keys = resolve_provider_keys("gemini", api_keys=["", "   ", "valid"])
        assert keys == ["valid"]


# ── Base provider retry logic ───────────────────────────────────────────


class TestBaseProviderRetry:
    """Test the shared _retry_loop via a concrete stub."""

    class StubProvider(LLMProvider):
        name = "stub"
        default_model_list = ["model-a", "model-b"]

        def __init__(self, responses=None, **kwargs):
            super().__init__(**kwargs)
            self._responses = responses or {}
            self._call_log: list[str] = []

        def _call_model(
            self, *, key, model, system, prompt, response_format_json, temperature, file_bytes, mime_type
        ) -> str:
            self._call_log.append(model)
            if model in self._responses:
                result = self._responses[model]
                if isinstance(result, Exception):
                    raise result
                return result
            raise _SkipModelError(f"{model} not configured")

        def _resolve_env_keys(self):
            return ["test-key"]

    def test_success_first_model(self):
        p = self.StubProvider(responses={"model-a": "Hello!"})
        text, model = p.generate(system="sys", prompt="hi")
        assert text == "Hello!"
        assert model == "model-a"

    def test_fallback_to_second_model(self):
        p = self.StubProvider(
            responses={
                "model-a": _SkipModelError("rate limited"),
                "model-b": "Fallback OK",
            }
        )
        text, model = p.generate(system="sys", prompt="hi")
        assert text == "Fallback OK"
        assert model == "model-b"

    def test_permanent_model_excluded(self):
        p = self.StubProvider(
            responses={
                "model-a": _PermanentModelError("gone"),
                "model-b": "survived",
            }
        )
        _text, model = p.generate(system="sys", prompt="hi")
        assert model == "model-b"
        # model-a should only appear once (permanently excluded after)
        assert p._call_log.count("model-a") == 1

    def test_all_models_fail_raises(self, monkeypatch):
        monkeypatch.setenv("AI_RETRY_CYCLES", "1")
        from app.config import get_settings

        get_settings.cache_clear()

        p = self.StubProvider(
            responses={
                "model-a": _SkipModelError("fail-a"),
                "model-b": _SkipModelError("fail-b"),
            }
        )
        with pytest.raises(ValueError, match="All models failed"):
            p.generate(system="sys", prompt="hi")

    def test_cancel_check_aborts(self):
        p = self.StubProvider(responses={"model-a": "ok"})
        with pytest.raises(ValueError, match="cancelled"):
            p.generate(system="sys", prompt="hi", cancel_check=lambda: True)

    def test_empty_response_skipped(self):
        p = self.StubProvider(
            responses={
                "model-a": "",  # empty
                "model-b": "valid",
            }
        )
        _text, model = p.generate(system="sys", prompt="hi")
        assert model == "model-b"

    def test_abort_all_error_stops_immediately(self, monkeypatch):
        monkeypatch.setenv("AI_RETRY_CYCLES", "5")
        from app.config import get_settings

        get_settings.cache_clear()

        p = self.StubProvider(
            responses={
                "model-a": _AbortAllError("invalid API key"),
            }
        )
        with pytest.raises(ValueError, match="invalid API key"):
            p.generate(system="sys", prompt="hi")
        # Should only have tried model-a once
        assert p._call_log == ["model-a"]


# ── Ollama-specific tests ──────────────────────────────────────────────


class TestOllamaProvider:
    """Test Ollama provider specifics."""

    def test_ollama_min_retry_delay_is_local(self):
        from app.providers.ollama import OllamaProvider

        p = OllamaProvider(api_keys=["test"])
        assert p._min_retry_delay() <= 2.0  # local delay should be short

    def test_ollama_name(self):
        from app.providers.ollama import OllamaProvider

        p = OllamaProvider(api_keys=["test"])
        assert p.name == "ollama"

    def test_ollama_default_models_non_empty(self):
        from app.providers.ollama import OllamaProvider

        p = OllamaProvider()
        assert len(p.default_model_list) > 0
