"""Centralised application configuration using pydantic-settings.

All environment variables, defaults, and validation live here.
Usage:
    from app.config import settings
    print(settings.ollama_base_url)
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppConfig(BaseSettings):
    """Single source of truth for every tuneable parameter."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # silently ignore unknown env vars
        case_sensitive=False,
    )

    # ── LLM Provider Selection ──────────────────────────────────────────
    default_provider: str = Field(
        default="auto",
        description="Default LLM provider: 'auto', 'gemini', 'openai', 'ollama'",
    )

    # ── Google Gemini ───────────────────────────────────────────────────
    google_api_key: str = Field(default="", description="Google Gemini API key")

    # ── OpenAI ──────────────────────────────────────────────────────────
    openai_api_key: str = Field(default="", description="OpenAI API key")

    # ── Anthropic Claude ────────────────────────────────────────────────
    anthropic_api_key: str = Field(default="", description="Anthropic API key")

    # ── Ollama (local / DGX Spark) ──────────────────────────────────────
    ollama_base_url: str = Field(
        default="http://localhost:11444/v1",
        description="Ollama OpenAI-compatible endpoint (DGX Spark default port 11444)",
    )
    ollama_api_key: str = Field(
        default="ollama",
        description="Ollama API key (any string — dummy auth)",
    )
    ollama_timeout: float = Field(
        default=600.0,
        description="Timeout in seconds for Ollama requests (large models need long timeout)",
    )

    # ── Generation parameters ───────────────────────────────────────────
    ai_retry_cycles: int = Field(default=3, ge=1, le=50)
    default_temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    min_retry_delay_remote: float = Field(default=15.0, description="Seconds between retries for cloud APIs")
    min_retry_delay_local: float = Field(default=1.0, description="Seconds between retries for local LLMs")

    # ── Application limits ──────────────────────────────────────────────
    max_upload_size_mb: int = Field(default=50, ge=1)
    server_port: int = Field(default=32123)

    # ── Cancellation ────────────────────────────────────────────────────
    cancel_signal_file: str = Field(default="cancel_signal.flag")

    # ── Logging ─────────────────────────────────────────────────────────
    log_file: str = Field(default="app.log")
    log_max_bytes: int = Field(default=5 * 1024 * 1024)  # 5 MB
    log_backup_count: int = Field(default=3)

    # ── Validators ──────────────────────────────────────────────────────
    @field_validator("default_provider")
    @classmethod
    def _validate_provider(cls, v: str) -> str:
        allowed = {"auto", "gemini", "openai", "ollama", "anthropic", "litellm"}
        v = v.strip().lower()
        if v not in allowed:
            raise ValueError(f"default_provider must be one of {allowed}, got '{v}'")
        return v

    @field_validator("ollama_base_url")
    @classmethod
    def _validate_ollama_url(cls, v: str) -> str:
        v = v.strip().rstrip("/")
        if not v.startswith(("http://", "https://")):
            raise ValueError(f"ollama_base_url must start with http(s)://, got '{v}'")
        return v

    # ── Helper: auto-detect best provider ───────────────────────────────
    def detect_provider(self) -> str:
        """Return the best available provider name based on configured keys."""
        if self.default_provider != "auto":
            return self.default_provider

        # Priority: Ollama (free, local) > Gemini > Anthropic > OpenAI
        if self.ollama_base_url:
            return "ollama"
        if self.google_api_key:
            return "gemini"
        if self.anthropic_api_key:
            return "anthropic"
        if self.openai_api_key:
            return "openai"
        return "ollama"  # ultimate fallback — user will see connection error


@lru_cache(maxsize=1)
def get_settings() -> AppConfig:
    """Return the cached singleton settings instance."""
    return AppConfig()


# Module-level shortcut for convenience
settings = get_settings()
