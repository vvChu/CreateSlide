# Configuration

All configuration is managed via environment variables (`.env` file) and validated with **Pydantic Settings**.

## Environment Variables

### LLM Provider Selection

| Variable | Default | Description |
|----------|---------|-------------|
| `DEFAULT_PROVIDER` | `auto` | LLM provider: `auto`, `gemini`, `openai`, `ollama`, `anthropic`, `litellm` |

### Provider API Keys

| Variable | Default | Description |
|----------|---------|-------------|
| `GOOGLE_API_KEY` | *(empty)* | Google Gemini API key |
| `OPENAI_API_KEY` | *(empty)* | OpenAI API key |
| `ANTHROPIC_API_KEY` | *(empty)* | Anthropic Claude API key |
| `LITELLM_API_KEY` | *(empty)* | LiteLLM proxy API key |
| `OLLAMA_BASE_URL` | `http://localhost:11444/v1` | Ollama server endpoint |
| `OLLAMA_API_KEY` | `ollama` | Ollama auth token (dummy) |
| `OLLAMA_TIMEOUT` | `600` | Timeout in seconds for Ollama requests |

### Generation Parameters

| Variable | Default | Description |
|----------|---------|-------------|
| `AI_RETRY_CYCLES` | `3` | Number of retry cycles across models |
| `DEFAULT_TEMPERATURE` | `0.7` | LLM temperature (0.0–2.0) |
| `MIN_RETRY_DELAY_REMOTE` | `15.0` | Seconds between retries for cloud APIs |
| `MIN_RETRY_DELAY_LOCAL` | `1.0` | Seconds between retries for local LLMs |

### Application Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `MAX_UPLOAD_SIZE_MB` | `50` | Maximum upload file size |
| `SERVER_PORT` | `32123` | Mesop server port |
| `LOG_FILE` | `app.log` | Log file path |
| `LOG_MAX_BYTES` | `5242880` | Max log file size (5 MB) |
| `LOG_BACKUP_COUNT` | `3` | Number of rotated log backups |

## Auto-Detection

When `DEFAULT_PROVIDER=auto` (the default), the system auto-detects the best provider:

1. **Ollama** — if `OLLAMA_BASE_URL` is set and the server responds
2. **Gemini** — if `GOOGLE_API_KEY` is set
3. **Anthropic** — if `ANTHROPIC_API_KEY` is set
4. **OpenAI** — if `OPENAI_API_KEY` is set
5. **Ollama** — fallback (user will see connection error if server is down)

## Example `.env`

```env
# Provider (auto-detected or explicit)
DEFAULT_PROVIDER=ollama

# Ollama (DGX Spark)
OLLAMA_BASE_URL=http://localhost:11444/v1
OLLAMA_API_KEY=ollama

# Or use a cloud provider:
# GOOGLE_API_KEY=your-gemini-key
# OPENAI_API_KEY=sk-your-openai-key
# ANTHROPIC_API_KEY=sk-ant-your-key
```
