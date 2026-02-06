"""Thread-safe cancellation signalling via file + in-memory flag."""

from __future__ import annotations

import os
import threading

from app.config import settings

_lock = threading.Lock()
_cancel_flag = False


def set_cancel_signal() -> None:
    """Raise the cancel flag (file + memory)."""
    global _cancel_flag
    with _lock:
        _cancel_flag = True
    try:
        with open(settings.cancel_signal_file, "w") as f:
            f.write("CANCEL")
    except OSError:
        pass  # rely on in-memory flag


def clear_cancel_signal() -> None:
    """Reset the cancel flag (file + memory)."""
    global _cancel_flag
    with _lock:
        _cancel_flag = False
    try:
        if os.path.exists(settings.cancel_signal_file):
            os.remove(settings.cancel_signal_file)
    except OSError:
        pass


def check_cancel_signal() -> bool:
    """Return ``True`` if cancellation has been requested."""
    if _cancel_flag:
        return True
    return os.path.exists(settings.cancel_signal_file)
