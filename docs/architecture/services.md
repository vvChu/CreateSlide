# Service Layer

Services contain the core business logic, orchestrating document processing, LLM calls, and output generation.

## Document Service (`app.services.document`)

Handles text extraction from uploaded files.

| Format | Library | Notes |
|---|---|---|
| PDF | `pypdf` | Concatenates all pages |
| DOCX | `python-docx` | Extracts paragraphs |
| EPUB | `ebooklib` + `beautifulsoup4` | Strips HTML, joins chapters |
| TXT | Built-in | Direct read |

```python
from app.services.document import load_document

text = load_document("/path/to/file.pdf")
```

## Slide Service (`app.services.slide`)

Converts a document into structured slide data via LLM analysis.

**Flow:**

1. Extract text via `load_document()`
2. Truncate to `max_input_chars` (default 30,000)
3. Send to LLM with slide generation prompt
4. Parse JSON response using robust `parse_json()` parser
5. Return structured dict with `title`, `slides[]`, `language`

**Observability:** The LLM call is wrapped in `timed("analyze_document")` for performance tracking.

## Summary Service (`app.services.summary`)

Two modes of operation:

### Standard Summary (`summarize_document`)

Single LLM call that produces a structured summary with title, sections, and key points. Wrapped in `timed()` and `request_context()` for observability.

### Deep Dive (`summarize_book_deep_dive`)

Multi-pass analysis for books and long documents:

1. **Chapter extraction** — identify structure
2. **Per-chapter analysis** — detailed summaries
3. **Cross-chapter synthesis** — themes and connections

Each pass uses the LLM with progressively refined prompts. All calls are timed and logged.

## Review Service (`app.services.review`)

Three-step syntopic book review:

| Step | Purpose | Output |
|---|---|---|
| 1. Analytical Reading | Deep content analysis | Core arguments, evidence |
| 2. Cross-Reference | Connect to broader literature | Comparisons, positioning |
| 3. Synthesis | Final structured review | Verdict, recommendations |

Supports:

- **Resume** — continue from a specific step
- **Cancel** — stop mid-review via cancellation signal
- **Language selection** — output in user's preferred language
- **Callback** — per-step progress reporting

## Error Handling

All services follow a consistent pattern:

```python
try:
    result = provider.generate(system, prompt, ...)
except Exception as e:
    logger.error("Operation failed: %s", e)
    return fallback_or_raise
```

Temporary LLM failures (rate limits, timeouts) are handled by the provider's retry loop. Services only see permanent failures or successful results.
