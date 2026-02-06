"""Application-wide logging helpers.

``setup_logging()``  configures a :class:`RotatingFileHandler` and
redirects *stdout / stderr* to the log file so that noisy libraries
(Mesop, Colorama, Click) cannot crash the console.

``safe_print(msg, level)``  emits a log entry at the requested level.
"""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler

from app.config import settings

# Keep a reference so the open file is not GC'd
_log_file_obj = None


def setup_logging() -> None:
    """Initialise the root logger with a rotating file handler and redirect stdio."""
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
