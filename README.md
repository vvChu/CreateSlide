# SlideGenius v2.0 — AI Presentation & Analysis Platform

SlideGenius is an AI-powered platform that transforms documents (PDF, DOCX, EPUB) into professional assets. It supports **Google Gemini**, **OpenAI**, and **Ollama (Local LLM / DGX Spark)** to generate **PowerPoint presentations**, **Deep Dive Summaries**, and **Expert Book Reviews**.

Built with **Python** and **Mesop**, featuring a modular Strategy-Pattern architecture with 103 unit tests.

## Key Features

### 1. AI Presentation Generator
- **Automatic Slide Creation**: Converts raw text into structured slides.
- **Smart Layout Engine**: Dynamically calculates text sizing and spacing.
- **Template Support**: Upload your own `.pptx` template to maintain brand identity.

### 2. Syntopic Book Review (Multi-Agent)
A 3-step "Chain-of-Thought" pipeline with specialized AI agents:
- **The Librarian**: Classifies the book's DNA (Genre, Tone, Audience).
- **The Analyst**: Deep-dive analysis (distinct logic for Fiction vs. Non-Fiction).
- **The Editor**: Synthesizes a premium review with scoring, similar books, and key mental models.
- **Resumable**: If interrupted, resumes from the last completed step.

### 3. Deep Dive Summarizer
- **Chain of Density**: High-signal summaries dense with information but easy to read.
- **PDF Report**: Professional PDF export with branded layout.

### 4. Multi-Provider AI Engine ("Smart Switch")
- **3 Providers**: Google Gemini, OpenAI, Ollama (local/remote LLM).
- **Auto-Detection**: On startup, automatically detects available Ollama server.
- **Cyclic Model Fallback**: Rotates through models with automatic retry on failure.
- **Key Rotation**: Multiple API keys supported per provider.
- **Smart Delay**: Enforces cooldown between retries to prevent rate-limit errors.
- **Extensible**: Add new providers via `register_provider()` (e.g. LiteLLM, Anthropic).

---

## System Architecture (v2.0)

```
app/
├── __init__.py              # Package v2.0.0
├── config.py                # Pydantic BaseSettings — single source of truth
├── core/
│   ├── json_parser.py       # 6-strategy robust JSON/dict parser
│   ├── cancellation.py      # Thread-safe cancel signal (file + memory)
│   └── log.py               # Logging setup with rotation
├── prompts/
│   ├── slide.py             # Slide generation prompt templates
│   ├── summary.py           # Summarization prompt templates
│   └── review.py            # 3-agent review prompt templates
├── providers/
│   ├── base.py              # Abstract LLMProvider with shared retry loop
│   ├── gemini.py            # Google Gemini (native multimodal PDF)
│   ├── openai_provider.py   # OpenAI Chat Completions
│   ├── ollama.py            # Local LLM via OpenAI-compatible API
│   └── registry.py          # Factory + discovery pattern
├── services/
│   ├── document.py          # Text extraction (PDF, DOCX, EPUB)
│   ├── slide.py             # Slide analysis orchestration
│   ├── summary.py           # Standard + deep-dive summarization
│   └── review.py            # 3-agent syntopic review pipeline
├── rendering/
│   ├── pdf.py               # PDF report generation (ReportLab)
│   └── pptx.py              # PowerPoint generation (python-pptx)
└── ui/
    ├── state.py             # Mesop reactive state
    ├── handlers.py          # Event handlers + async generators
    └── page.py              # UI layout (345 lines)

main.py                      # Slim entry point (39 lines)
tests/                       # 103 unit tests + integration tests
```

Key architectural decisions:
- **Strategy Pattern** for LLM providers — all share a common `_retry_loop()` via ABC inheritance
- **Pydantic Settings** for centralised, validated configuration with env-file support
- **Prompt templates** extracted into dedicated modules (not embedded in logic)
- **Service layer** separates business logic from UI and AI calls
- **Registry pattern** allows runtime provider registration

---

## Installation

### Prerequisites
- **Python**: 3.10+ (Recommended 3.12)
- **AI Provider** (at least one):
  - [Ollama](https://ollama.com/) locally or on DGX Spark (free, no API key)
  - [Google AI Studio](https://aistudio.google.com/) API key
  - [OpenAI](https://platform.openai.com/) API key

### Steps

```bash
# 1. Clone
git clone https://github.com/anhtrtHN/CreateSlide.git
cd CreateSlide

# 2. Create virtual environment
python -m venv .venv
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env with your settings (see below)

# 5. Run
mesop main.py --port 32123
```

Access at: `http://localhost:32123`

### Environment Variables

```env
# Provider selection: auto, gemini, openai, ollama
DEFAULT_PROVIDER=auto

# Ollama (Local/DGX Spark — free)
OLLAMA_BASE_URL=http://localhost:11434/v1
OLLAMA_API_KEY=ollama
OLLAMA_TIMEOUT=600

# Google Gemini
# GOOGLE_API_KEY=your_key_here

# OpenAI
# OPENAI_API_KEY=your_key_here

# Generation settings
AI_RETRY_CYCLES=3
DEFAULT_TEMPERATURE=0.7
```

For DGX Spark setups, see [dgx-spark-toolkit/playbooks/](../dgx-spark-toolkit/playbooks/) for detailed LLM API guides.

---

## Running Tests

```bash
# Unit tests (no external services needed)
pytest tests/ -v

# Integration tests (requires live Ollama server)
pytest tests/ -v --run-integration
```

**Test coverage**: 103 unit tests across 9 test files covering:
- Configuration & validation (`test_config.py`)
- JSON parser — all 6 strategies (`test_json_parser.py`)
- Cancellation signal — thread safety (`test_cancellation.py`)
- Provider registry & factory (`test_providers.py`)
- Retry/fallback logic via stub provider (`test_providers.py`)
- Document extraction — PDF, DOCX (`test_document.py`)
- Slide service — mocked LLM (`test_slide_service.py`)
- PPTX generation (`test_pptx.py`)
- PDF generation (`test_pdf.py`)
- Prompt templates (`test_prompts.py`)

---

## User Guide

### A. Generating Slides
1. **Upload**: Drag & drop your source file (PDF/Word/Ebook).
2. **Template (Optional)**: Upload a `.pptx` to use as a base.
3. **Topic**: Enter a specific focus topic.
4. **Mode**: Choose "Chi tiết" for longer presentations.
5. Click **"Generate Slides"**.
6. When done, click **"Download PowerPoint"**.

### B. Creating an Expert Review
1. **Upload** your book file.
2. Click **"Generate Expert Review"**.
3. The system activates the 3 agents (Librarian → Analyst → Editor).
4. Once complete, **"Download Review PDF"** appears.

### C. Summarizing Documents
1. **Upload** your document.
2. Click **"Generate Summary"** or **"Deep Dive Summary"**.
3. Download the resulting PDF.

---

## Troubleshooting

- **429 Resource Exhausted**: The Smart Switch handles this automatically. "Sleeping..." logs are normal.
- **Ollama Connection Error**: Ensure Ollama is running (`ollama serve`) and `OLLAMA_BASE_URL` in `.env` is correct.
- **Stuck Spinner**: Refresh the browser (F5).
- **Cancel**: Click "Cancel" to abort any long-running generation.

---

## Adding a Custom Provider

```python
from app.providers.base import LLMProvider
from app.providers.registry import register_provider

class MyProvider(LLMProvider):
    name = "my_provider"
    default_model_list = ["my-model-v1", "my-model-v2"]

    def _call_model(self, *, key, model, system, prompt, **kwargs) -> str:
        # Your API call here
        return response_text

    def _resolve_env_keys(self) -> list[str]:
        return [os.environ.get("MY_PROVIDER_KEY", "")]

register_provider("my_provider", MyProvider)
```

---

*Powered by Google Gemini, OpenAI, and Ollama. Built with Mesop.*
