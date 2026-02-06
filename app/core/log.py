"""Application-wide logging helpers.

``setup_logging()``  configures a :class:`RotatingFileHandler` and
redirects *stdout / stderr* to the log file so that noisy libraries
(Mesop, Colorama, Click) cannot crash the console.

``safe_print(msg, level)``  emits a log entry at the requested level.

``StructuredFormatter`` outputs JSON log lines for machine-readable logs.

``request_context`` / ``timed`` provide observability helpers for tracing
and performance measurement.
"""

from __future__ import annotations

import contextlib
import json
import logging
import sys
import time
import uuid
from collections.abc import Generator
from logging.handlers import RotatingFileHandler
from typing import Any

from app.config import settings

# Keep a reference so the open file is not GC'd
_log_file_obj = None

# Thread-local-like request context (simple module-level for Mesop)
_request_id: str = ""


# ── Structured JSON Formatter ───────────────────────────────────────────


class StructuredFormatter(logging.Formatter):
    """Emit each log record as a single JSON line.

    Fields: timestamp, level, logger, message, request_id, and any extras
    passed via the ``extra`` kwarg on the logging call.
    """

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if _request_id:
            log_entry["request_id"] = _request_id

        # Merge any extras the caller attached
        for key in ("duration_ms", "provider", "model", "step", "error"):
            val = getattr(record, key, None)
            if val is not None:
                log_entry[key] = val

        if record.exc_info and record.exc_info[1]:
            log_entry["exception"] = str(record.exc_info[1])

        return json.dumps(log_entry, ensure_ascii=False, default=str)


# ── Setup ───────────────────────────────────────────────────────────────


def setup_logging(*, json_format: bool = True) -> None:
    """Initialise the root logger with a rotating file handler and redirect stdio.

    Args:
        json_format: If True (default), use StructuredFormatter (JSON lines).
                     If False, use the classic human-readable format.
    """
    global _log_file_obj

    root = logging.getLogger()
    for h in root.handlers[:]:
        root.removeHandler(h)

    handler = RotatingFileHandler(
        settings.log_file,
        mode="a",
        encoding="utf-8",
        maxBytes=settings.log_max_bytes,
        backupCount=settings.log_backup_count,
    )

    if json_format:
        handler.setFormatter(StructuredFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))

    root.addHandler(handler)
    root.setLevel(logging.INFO)

    # Redirect stdout/stderr to log file
    try:
        sys.stdout.flush()
        sys.stderr.flush()
    except Exception:
        pass

    _log_file_obj = open(settings.log_file, "a", encoding="utf-8", buffering=1)  # noqa: SIM115
    sys.stdout = _log_file_obj
    sys.stderr = _log_file_obj

    # Neutralise Colorama if present
    try:
        import colorama

        colorama.deinit()
        colorama.init = lambda *a, **kw: None  # type: ignore[assignment]
    except ImportError:
        pass


def safe_print(text: str, level: int = logging.INFO) -> None:
    """Emit *text* through the logging system (or fallback to print)."""
    try:
        if logging.getLogger().handlers:
            logging.log(level, text)
        else:
            print(text)
    except Exception:
        pass


# ── Observability helpers ───────────────────────────────────────────────


def set_request_id(rid: str | None = None) -> str:
    """Set a correlation ID for the current request.  Returns the ID."""
    global _request_id
    _request_id = rid or uuid.uuid4().hex[:12]
    return _request_id


def get_request_id() -> str:
    """Return the current request correlation ID (empty if unset)."""
    return _request_id


def clear_request_id() -> None:
    """Clear the current request ID."""
    global _request_id
    _request_id = ""


@contextlib.contextmanager
def request_context(rid: str | None = None) -> Generator[str, None, None]:
    """Context manager that sets and clears a request correlation ID.

    Usage::

        with request_context() as rid:
            safe_print(f"Processing request {rid}")
            # all log lines within will include request_id
    """
    token = set_request_id(rid)
    try:
        yield token
    finally:
        clear_request_id()


@contextlib.contextmanager
def timed(operation: str, **extra: Any) -> Generator[None, None, None]:
    """Context manager that logs the duration of an operation.

    Usage::

        with timed("summarize_document", provider="ollama"):
            result = do_work()

    Emits an INFO log with ``duration_ms`` at the end.
    """
    start = time.perf_counter()
    safe_print(f"[START] {operation}", logging.INFO)
    try:
        yield
    except Exception:
        elapsed = (time.perf_counter() - start) * 1000
        logger = logging.getLogger("app.timing")
        logger.error(
            f"[FAILED] {operation} after {elapsed:.0f}ms",
            extra={"duration_ms": round(elapsed), "step": operation, **extra},
        )
        raise
    else:
        elapsed = (time.perf_counter() - start) * 1000
        logger = logging.getLogger("app.timing")
        logger.info(
            f"[DONE] {operation} in {elapsed:.0f}ms",
            extra={"duration_ms": round(elapsed), "step": operation, **extra},
        )
