# Testing Guide

SlideGenius uses **pytest** with 200+ tests and 87%+ coverage.

## Running Tests

```bash
# All tests
make test

# With coverage
make coverage

# Specific file
pytest tests/test_config.py -v

# Specific test
pytest tests/test_config.py::TestAppConfig::test_defaults -v

# Stop on first failure
pytest -x
```

## Test Structure

```
tests/
├── conftest.py              # Shared fixtures (PDF, DOCX, EPUB bytes)
├── test_config.py           # AppConfig validation + detection
├── test_json_parser.py      # JSON extraction from LLM output
├── test_cancellation.py     # Thread-safe cancel signal
├── test_log.py              # Logging, StructuredFormatter, timed()
├── test_document.py         # PDF/DOCX/EPUB extraction
├── test_slide_service.py    # Slide generation pipeline
├── test_summary.py          # Summarisation services
├── test_review.py           # 3-step book review
├── test_providers.py        # Provider base class + registry
├── test_gemini.py           # Gemini provider specifics
├── test_openai_provider.py  # OpenAI provider specifics
├── test_anthropic.py        # Anthropic provider specifics
├── test_litellm.py          # LiteLLM provider specifics
├── test_pptx.py             # PowerPoint rendering
├── test_pdf.py              # PDF rendering
├── test_prompts.py          # Prompt string validation
└── test_integration.py      # End-to-end pipeline tests
```

## Fixtures

Defined in `tests/conftest.py`:

| Fixture | Type | Description |
|---|---|---|
| `sample_pdf_bytes` | `bytes` | Minimal valid PDF created with ReportLab |
| `sample_docx_bytes` | `bytes` | Minimal valid DOCX created with python-docx |
| `sample_epub_bytes` | `bytes` | Minimal valid EPUB zip with OPF metadata |

## Writing Tests

### Naming Convention

```python
class TestClassName:
    def test_method_name_scenario(self):
        ...
    def test_method_name_edge_case(self):
        ...
```

### Mocking LLM Calls

Use `unittest.mock.patch` to mock provider calls:

```python
from unittest.mock import patch, MagicMock

def test_slide_generation(sample_pdf_bytes, tmp_path):
    pdf_path = tmp_path / "test.pdf"
    pdf_path.write_bytes(sample_pdf_bytes)

    mock_provider = MagicMock()
    mock_provider.generate.return_value = (
        '{"title": "Test", "slides": []}',
        "test-model"
    )

    with patch("app.services.slide.get_provider", return_value=mock_provider):
        result = analyze_document(str(pdf_path))
    
    assert result["title"] == "Test"
```

### Testing Error Paths

```python
def test_handles_llm_failure():
    mock_provider = MagicMock()
    mock_provider.generate.side_effect = RuntimeError("API down")

    with patch("app.services.slide.get_provider", return_value=mock_provider):
        with pytest.raises(RuntimeError, match="API down"):
            analyze_document("test.pdf")
```

## Coverage

Current coverage breakdown:

| Module | Coverage |
|---|---|
| `app/core/` | 92–94% |
| `app/services/` | 92–100% |
| `app/providers/` | 59–91% |
| `app/rendering/` | 79–91% |
| `app/config.py` | 90% |
| **Total** | **87.8%** |

To inspect detailed coverage:

```bash
pytest --cov=app --cov-report=html tests/
open htmlcov/index.html
```

## CI Integration

Tests run automatically on every push via GitHub Actions (`.github/workflows/ci.yml`). The pipeline:

1. Install dependencies
2. Run ruff linting
3. Run pytest with coverage
4. Report coverage percentage
