"""Tests for app.config — Pydantic-based configuration."""

from __future__ import annotations

import pytest

from app.config import AppConfig, get_settings


class TestAppConfig:
    """Validate AppConfig defaults and validators."""

    def test_defaults(self):
        cfg = get_settings()
        assert cfg.default_provider == "ollama"  # overridden by env in conftest
        assert cfg.ai_retry_cycles >= 1
        assert cfg.default_temperature == 0.7
        assert cfg.max_upload_size_mb == 50
        assert cfg.server_port == 32123

    def test_ollama_url_validation(self):
        """Valid URLs should pass; invalid should raise."""
        cfg = get_settings()
        assert cfg.ollama_base_url.startswith("http")

    def test_ollama_url_rejects_invalid(self):
        with pytest.raises(Exception):
            AppConfig(ollama_base_url="not-a-url")

    def test_provider_validation_rejects_unknown(self):
        with pytest.raises(Exception):
            AppConfig(default_provider="nonexistent_provider")

    def test_provider_validation_normalises(self):
        cfg = AppConfig(default_provider="  OLLAMA  ")
        assert cfg.default_provider == "ollama"

    def test_detect_provider_explicit(self):
        cfg = AppConfig(default_provider="gemini")
        assert cfg.detect_provider() == "gemini"

    def test_detect_provider_auto_ollama_fallback(self):
        cfg = AppConfig(default_provider="auto", ollama_base_url="http://localhost:11444/v1")
        assert cfg.detect_provider() == "ollama"

    def test_detect_provider_auto_with_gemini_key(self):
        """When provider=auto and google_api_key is set, ollama still wins (it's free/local)."""
        cfg = AppConfig(
            default_provider="auto",
            ollama_base_url="http://localhost:11444/v1",
            google_api_key="AIza-test-key",
        )
        # auto prefers ollama (free, local) when ollama_base_url is set
        assert cfg.detect_provider() == "ollama"

    def test_detect_provider_explicit_gemini(self):
        cfg = AppConfig(default_provider="gemini")
        assert cfg.detect_provider() == "gemini"

    def test_detect_provider_explicit_openai(self):
        cfg = AppConfig(default_provider="openai")
        assert cfg.detect_provider() == "openai"

    def test_temperature_bounds(self):
        with pytest.raises(Exception):
            AppConfig(default_temperature=3.0)
        with pytest.raises(Exception):
            AppConfig(default_temperature=-0.1)

    def test_retry_cycles_bounds(self):
        with pytest.raises(Exception):
            AppConfig(ai_retry_cycles=0)

    def test_ollama_url_trailing_slash_stripped(self):
        cfg = AppConfig(ollama_base_url="http://localhost:11444/v1/")
        assert not cfg.ollama_base_url.endswith("/")
