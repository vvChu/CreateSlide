"""Provider registry — factory + discovery.

Usage:
    from app.providers import get_provider, list_providers

    provider = get_provider("ollama")
    text, model = provider.generate(system="…", prompt="…")

    for name in list_providers():
        print(name)
"""

from __future__ import annotations

from app.providers.base import LLMProvider
from app.providers.gemini import GeminiProvider
from app.providers.ollama import OllamaProvider
from app.providers.openai_provider import OpenAIProvider

# ── Static registry ─────────────────────────────────────────────────────

_PROVIDERS: dict[str, type[LLMProvider]] = {
    "gemini": GeminiProvider,
    "openai": OpenAIProvider,
    "ollama": OllamaProvider,
}


def register_provider(name: str, cls: type[LLMProvider]) -> None:
    """Register a custom provider at runtime (e.g. LiteLLM proxy)."""
    _PROVIDERS[name.lower()] = cls


def get_provider(
    name: str,
    *,
    api_keys: list[str] | None = None,
    base_url: str | None = None,
) -> LLMProvider:
    """Instantiate a provider by name.

    Args:
        name: ``"gemini"``, ``"openai"``, ``"ollama"`` (or any registered name).
        api_keys: Explicit API keys (optional — env vars used as fallback).
        base_url: Override base URL (only relevant for Ollama / proxies).
    """
    key = name.lower().strip()
    cls = _PROVIDERS.get(key)
    if cls is None:
        available = ", ".join(sorted(_PROVIDERS))
        raise ValueError(f"Unknown provider '{name}'. Available: {available}")

    # OllamaProvider has an extra base_url kwarg
    if key == "ollama":
        return cls(api_keys=api_keys, base_url=base_url)  # type: ignore[call-arg]
    return cls(api_keys=api_keys)


def list_providers() -> list[str]:
    """Return sorted list of registered provider names."""
    return sorted(_PROVIDERS)


def resolve_provider_keys(provider: str, api_key: str | None = None, api_keys: list[str] | None = None) -> list[str]:
    """Resolve API keys for a given provider.

    Priority: explicit api_keys list > explicit single api_key > environment variable.
    Returns a non-empty list of keys/URLs, or raises ValueError.

    Backward-compatible helper used by services layer.
    """
    import os

    from app.config import settings

    keys_to_use: list[str] = []
    if api_keys and len(api_keys) > 0:
        keys_to_use = [k.strip() for k in api_keys if k.strip()]
    elif api_key:
        keys_to_use = [api_key.strip()]
    else:
        if provider == "ollama":
            keys_to_use = [settings.ollama_base_url]
        elif provider == "openai":
            env_key = os.environ.get("OPENAI_API_KEY", settings.openai_api_key)
            if env_key:
                keys_to_use = [env_key]
        else:
            env_key = os.environ.get("GOOGLE_API_KEY", settings.google_api_key)
            if env_key:
                keys_to_use = [env_key]

    if not keys_to_use:
        provider_names = {"openai": "OpenAI", "ollama": "Ollama", "gemini": "Google"}
        raise ValueError(
            f"Thiếu {provider_names.get(provider, provider)} API Key. "
            "Vui lòng thiết lập biến môi trường hoặc nhập vào giao diện."
        )

    # Deduplicate preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for k in keys_to_use:
        if k not in seen:
            unique.append(k)
            seen.add(k)
    return unique
