"""LLM provider abstraction layer.

Usage:
    from app.providers import get_provider, list_providers

    provider = get_provider("ollama")
    text, model = provider.generate(system="...", prompt="...", cancel_check=fn)
"""

from app.providers.registry import get_provider, list_providers

__all__ = ["get_provider", "list_providers"]
