"""Tests for app.core.cancellation — thread-safe cancel signal."""

from __future__ import annotations

import os

from app.core.cancellation import (
    check_cancel_signal,
    clear_cancel_signal,
    set_cancel_signal,
)


class TestCancellation:
    """Test the cancel signal mechanism."""

    def test_initial_state_is_clear(self):
        clear_cancel_signal()
        assert check_cancel_signal() is False

    def test_set_then_check(self):
        clear_cancel_signal()
        set_cancel_signal()
        assert check_cancel_signal() is True

    def test_set_then_clear_then_check(self):
        set_cancel_signal()
        clear_cancel_signal()
        assert check_cancel_signal() is False

    def test_flag_file_created(self, tmp_path):
        """set_cancel_signal creates a file; clear removes it.

        The cancellation module uses the module-level `settings` import,
        so we test by checking the actual file it writes to.
        """
        import importlib

        import app.config
        import app.core.cancellation as cancel_mod

        # Force config.py to recreate settings with monkeypatched env
        app.config.get_settings.cache_clear()
        app.config.settings = app.config.get_settings()
        importlib.reload(cancel_mod)
        cfg = app.config.settings

        cancel_mod.clear_cancel_signal()
        cancel_mod.set_cancel_signal()
        assert os.path.exists(cfg.cancel_signal_file)

        cancel_mod.clear_cancel_signal()
        assert not os.path.exists(cfg.cancel_signal_file)

    def test_multiple_sets_idempotent(self):
        clear_cancel_signal()
        set_cancel_signal()
        set_cancel_signal()
        set_cancel_signal()
        assert check_cancel_signal() is True
        clear_cancel_signal()
        assert check_cancel_signal() is False

    def test_thread_safety(self):
        """Concurrent set/clear should not raise."""
        import threading

        clear_cancel_signal()
        errors: list[Exception] = []

        def toggle(n: int):
            try:
                for _ in range(n):
                    set_cancel_signal()
                    check_cancel_signal()
                    clear_cancel_signal()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=toggle, args=(50,)) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        clear_cancel_signal()
