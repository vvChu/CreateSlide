"""Thread-safe cancellation signalling via file + in-memory flag.

Supports both the legacy global signal and per-request ``CancelToken`` objects.
"""

from __future__ import annotations

import os
import threading

from app.config import settings

# ── Per-request CancelToken ──────────────────────────────────────────────


class CancelToken:
    """Lightweight, per-request cancellation token (thread-safe).

    Usage::

        token = CancelToken()
        future = executor.submit(service_fn, ..., cancel_check=token.is_set)
        # later:
        token.cancel()  # signal cancellation
        token.is_set()  # check from worker thread
    """

    __slots__ = ("_event",)

    def __init__(self) -> None:
        self._event = threading.Event()

    def cancel(self) -> None:
        """Request cancellation."""
        self._event.set()

    def is_set(self) -> bool:
        """Return ``True`` if cancellation has been requested."""
        return self._event.is_set()

    def reset(self) -> None:
        """Clear the cancellation flag for reuse."""
        self._event.clear()


# ── Legacy global signal (kept for backward-compat) ──────────────────────

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
