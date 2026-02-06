"""Tests for app.core.log — logging setup, safe_print, and observability."""

from __future__ import annotations

import logging
import sys
from unittest.mock import patch

import pytest

from app.core.log import (
    StructuredFormatter,
    clear_request_id,
    get_request_id,
    request_context,
    safe_print,
    set_request_id,
    setup_logging,
    timed,
)


class TestSetupLogging:
    """Test the logging initialization."""

    def test_adds_file_handler(self, tmp_path, monkeypatch):
        """setup_logging should add a RotatingFileHandler."""
        log_file = str(tmp_path / "test.log")
        monkeypatch.setenv("LOG_FILE", log_file)
        from app.config import get_settings

        get_settings.cache_clear()

        setup_logging()

        root = logging.getLogger()
        handler_types = [type(h).__name__ for h in root.handlers]
        assert "RotatingFileHandler" in handler_types

        # Restore
        get_settings.cache_clear()

    def test_redirects_stdout(self, tmp_path, monkeypatch):
        """After setup_logging, sys.stdout should point to the log file."""
        log_file = str(tmp_path / "test.log")
        monkeypatch.setenv("LOG_FILE", log_file)
        from app.config import get_settings

        get_settings.cache_clear()

        original_stdout = sys.stdout
        setup_logging()

        # stdout should now be redirected
        assert sys.stdout is not original_stdout

        # Restore
        sys.stdout = original_stdout
        sys.stderr = sys.__stderr__
        get_settings.cache_clear()

    def test_clears_existing_handlers(self, tmp_path, monkeypatch):
        """setup_logging should clear any previous handlers."""
        log_file = str(tmp_path / "test.log")
        monkeypatch.setenv("LOG_FILE", log_file)
        from app.config import get_settings

        get_settings.cache_clear()

        # Add a dummy handler
        root = logging.getLogger()
        dummy = logging.StreamHandler()
        root.addHandler(dummy)

        setup_logging()

        # Should have exactly one handler (the RotatingFileHandler)
        assert len(root.handlers) == 1

        # Restore
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__
        get_settings.cache_clear()


class TestSafePrint:
    """Test the safe_print helper."""

    def test_logs_message(self, caplog):
        """safe_print should emit a log message."""
        with caplog.at_level(logging.INFO):
            safe_print("Hello test")
        assert "Hello test" in caplog.text

    def test_custom_level(self, caplog):
        """safe_print accepts custom log level."""
        with caplog.at_level(logging.WARNING):
            safe_print("Warning msg", logging.WARNING)
        assert "Warning msg" in caplog.text

    def test_no_handlers_fallback(self, monkeypatch):
        """When no handlers exist, safe_print should not crash."""
        root = logging.getLogger()
        original_handlers = root.handlers.copy()
        root.handlers.clear()

        try:
            # Should not raise
            safe_print("Fallback test")
        finally:
            root.handlers = original_handlers

    def test_exception_in_logging_handled(self):
        """safe_print should suppress exceptions gracefully."""
        with patch("logging.log", side_effect=RuntimeError("broken")):
            # Should not raise
            safe_print("This should not crash")


class TestStructuredFormatter:
    """Test JSON log formatting."""

    def test_produces_valid_json(self):
        import json

        fmt = StructuredFormatter()
        record = logging.LogRecord("test", logging.INFO, "test.py", 1, "Hello world", (), None)
        output = fmt.format(record)
        parsed = json.loads(output)
        assert parsed["message"] == "Hello world"
        assert parsed["level"] == "INFO"
        assert "timestamp" in parsed

    def test_includes_request_id(self):
        import json

        set_request_id("abc123")
        try:
            fmt = StructuredFormatter()
            record = logging.LogRecord("test", logging.INFO, "test.py", 1, "msg", (), None)
            output = fmt.format(record)
            parsed = json.loads(output)
            assert parsed["request_id"] == "abc123"
        finally:
            clear_request_id()

    def test_includes_extras(self):
        import json

        fmt = StructuredFormatter()
        record = logging.LogRecord("test", logging.INFO, "test.py", 1, "msg", (), None)
        record.duration_ms = 150  # type: ignore[attr-defined]
        record.provider = "ollama"  # type: ignore[attr-defined]
        output = fmt.format(record)
        parsed = json.loads(output)
        assert parsed["duration_ms"] == 150
        assert parsed["provider"] == "ollama"


class TestRequestContext:
    """Test request correlation ID management."""

    def test_set_and_get(self):
        clear_request_id()
        rid = set_request_id("test-123")
        assert rid == "test-123"
        assert get_request_id() == "test-123"
        clear_request_id()

    def test_auto_generated_id(self):
        clear_request_id()
        rid = set_request_id()
        assert len(rid) == 12  # hex[:12]
        clear_request_id()

    def test_context_manager(self):
        clear_request_id()
        with request_context("ctx-456") as rid:
            assert rid == "ctx-456"
            assert get_request_id() == "ctx-456"
        assert get_request_id() == ""

    def test_context_manager_auto_id(self):
        clear_request_id()
        with request_context() as rid:
            assert len(rid) == 12
            assert get_request_id() == rid
        assert get_request_id() == ""


class TestTimed:
    """Test performance timing context manager."""

    def test_logs_duration(self, caplog):
        with caplog.at_level(logging.INFO), timed("test_operation"):
            pass
        assert "[START] test_operation" in caplog.text
        assert "[DONE] test_operation" in caplog.text

    def test_logs_failure(self, caplog):
        with caplog.at_level(logging.ERROR):
            try:
                with timed("failing_op"):
                    raise ValueError("boom")
            except ValueError:
                pass
        assert "[FAILED] failing_op" in caplog.text

    def test_reraises_exception(self):
        with pytest.raises(RuntimeError, match="test error"), timed("error_op"):
            raise RuntimeError("test error")
