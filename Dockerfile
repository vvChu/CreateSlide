# ── Build stage ──────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Runtime stage ───────────────────────────────────────────────────
FROM python:3.12-slim

# System fonts for PDF generation (DejaVu)
RUN apt-get update && \
    apt-get install -y --no-install-recommends fonts-dejavu-core && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application code
COPY main.py .
COPY app/ app/

# Non-root user for security
RUN useradd --create-home appuser && chown -R appuser:appuser /app
USER appuser

# Environment defaults (override at runtime via docker run -e ...)
ENV DEFAULT_PROVIDER=auto \
    OLLAMA_BASE_URL=http://host.docker.internal:11444/v1 \
    OLLAMA_API_KEY=ollama \
    SERVER_PORT=32123

EXPOSE 32123

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:32123')" || exit 1

CMD ["mesop", "main.py", "--port", "32123", "--host", "0.0.0.0"]
