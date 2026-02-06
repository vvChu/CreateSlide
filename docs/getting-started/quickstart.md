# Quick Start

## 1. Upload a document

Open `http://localhost:32123` and upload a PDF, DOCX, or EPUB document.

## 2. Choose an action

| Button | Description |
|--------|-------------|
| **Generate Slides** | Create a PowerPoint presentation from the document |
| **Generate Summary** | Create a PDF summary (standard or deep dive) |
| **Generate Expert Review** | Run the 3-agent syntopic review pipeline |

## 3. Configure options

- **Detail Mode** — Toggle for deeper analysis (more slides / longer summaries)
- **AI Provider** — Select Ollama (free local), Gemini, OpenAI, etc.
- **Language** — Choose review output language (Vietnamese or English)
- **Custom Instructions** — Guide the AI with specific focus areas

## 4. Download output

Once processing completes, download your generated PowerPoint (.pptx) or PDF file.

## Programmatic Usage

```python
from app.providers.registry import get_provider
from app.services.slide import analyze_document
from app.services.summary import summarize_document
from app.rendering.pptx import create_pptx

# Generate slides from a PDF
with open("document.pdf", "rb") as f:
    pdf_bytes = f.read()

slides = analyze_document(
    pdf_bytes, "application/pdf",
    provider="ollama", api_keys=["http://localhost:11444/v1"]
)

pptx_buffer = create_pptx(slides)
with open("output.pptx", "wb") as f:
    f.write(pptx_buffer.read())
```
