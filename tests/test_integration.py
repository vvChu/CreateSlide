"""Integration tests — require a live Ollama server.

Run explicitly:
    pytest tests/test_integration.py -v --run-integration

These tests verify the full pipeline from document → LLM → output
using the actual Ollama server at the configured endpoint.
"""

from __future__ import annotations

import pytest

# ── Custom marker ───────────────────────────────────────────────────────


def pytest_configure(config):
    config.addinivalue_line("markers", "integration: requires live Ollama server")


def pytest_collection_modifyitems(config, items):
    if not config.getoption("--run-integration", default=False):
        skip = pytest.mark.skip(reason="Need --run-integration to run")
        for item in items:
            if "integration" in item.keywords:
                item.add_marker(skip)


def pytest_addoption(parser):
    parser.addoption(
        "--run-integration", action="store_true", default=False, help="Run integration tests against live Ollama"
    )


# ── Live Ollama fixture ─────────────────────────────────────────────────


@pytest.fixture
def live_ollama():
    """Skip if Ollama is not reachable."""
    from app.providers.ollama import OllamaProvider

    p = OllamaProvider()
    if not p.check_connectivity():
        pytest.skip("Ollama server not reachable")
    return p


# ── Tests ────────────────────────────────────────────────────────────────


@pytest.mark.integration
class TestOllamaIntegration:
    """End-to-end tests with live Ollama."""

    def test_connectivity(self, live_ollama):
        assert live_ollama.check_connectivity() is True

    def test_list_models(self, live_ollama):
        models = live_ollama.list_models()
        assert isinstance(models, list)
        assert len(models) > 0

    def test_simple_generation(self, live_ollama):
        """Generate a short response from Ollama."""
        text, model = live_ollama.generate(
            system="You are a helpful assistant. Reply briefly.",
            prompt="What is 2+2? Answer with just the number.",
        )
        assert "4" in text
        assert model  # model name should be non-empty

    def test_json_generation(self, live_ollama):
        """Generate a JSON response from Ollama."""
        text, _model = live_ollama.generate(
            system="You output valid JSON only.",
            prompt='Return a JSON object with keys "name" and "age". Use any values.',
            response_format_json=True,
        )
        from app.core.json_parser import robust_json_parse

        result = robust_json_parse(text)
        assert "name" in result
        assert "age" in result


@pytest.mark.integration
class TestFullPipeline:
    """End-to-end pipeline: document → LLM → slides → PPTX."""

    def test_pdf_to_slides_to_pptx(self, live_ollama, sample_pdf_bytes):
        """Full pipeline: PDF → extract text → generate slides → create PPTX."""
        from app.services.slide import analyze_document

        result = analyze_document(
            sample_pdf_bytes,
            "application/pdf",
            provider="ollama",
            api_keys=[live_ollama.api_keys[0] if live_ollama.api_keys else "ollama"],
        )
        assert "slides" in result
        assert len(result["slides"]) > 0

        from app.rendering.pptx import create_pptx

        pptx_buf = create_pptx(result)
        assert pptx_buf.tell() > 0 or pptx_buf.getbuffer().nbytes > 0

    def test_document_summary(self, live_ollama, sample_pdf_bytes):
        """Full pipeline: PDF → extract text → summarize."""
        from app.services.summary import summarize_document

        result = summarize_document(
            sample_pdf_bytes,
            "application/pdf",
            provider="ollama",
            api_keys=["ollama"],
        )
        assert isinstance(result, dict)
        assert result.get("mode") == "standard"
        assert result.get("used_model")
