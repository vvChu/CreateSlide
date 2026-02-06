"""Tests for app.core.executor — shared thread pool and async helpers."""

from __future__ import annotations

import concurrent.futures
import time

import pytest

from app.core.executor import get_executor, run_in_executor, shutdown_executor


class TestGetExecutor:
    """get_executor() returns a reusable ThreadPoolExecutor."""

    def test_returns_executor(self):
        ex = get_executor()
        assert isinstance(ex, concurrent.futures.ThreadPoolExecutor)

    def test_same_instance(self):
        """Consecutive calls return the same object."""
        a = get_executor()
        b = get_executor()
        assert a is b

    def test_recreates_after_shutdown(self):
        """After shutdown, a fresh pool is created."""
        old = get_executor()
        shutdown_executor(wait=True)
        new = get_executor()
        assert new is not old

    def test_submit_and_result(self):
        """Can submit work and get a result."""
        ex = get_executor()
        future = ex.submit(lambda x: x * 2, 21)
        assert future.result(timeout=5) == 42


class TestRunInExecutor:
    """run_in_executor() bridges sync → async."""

    @pytest.mark.asyncio
    async def test_basic_call(self):
        result = await run_in_executor(lambda: 42)
        assert result == 42

    @pytest.mark.asyncio
    async def test_with_args(self):
        def add(a, b):
            return a + b

        result = await run_in_executor(add, 3, 7)
        assert result == 10

    @pytest.mark.asyncio
    async def test_with_kwargs(self):
        def greet(name, greeting="Hello"):
            return f"{greeting}, {name}!"

        result = await run_in_executor(greet, "World", greeting="Hi")
        assert result == "Hi, World!"

    @pytest.mark.asyncio
    async def test_propagates_exception(self):
        def boom():
            raise ValueError("test error")

        with pytest.raises(ValueError, match="test error"):
            await run_in_executor(boom)

    @pytest.mark.asyncio
    async def test_runs_in_background_thread(self):
        """The callable runs in a different thread."""
        import threading

        main_thread = threading.current_thread().ident

        def get_thread():
            return threading.current_thread().ident

        worker_thread = await run_in_executor(get_thread)
        assert worker_thread != main_thread


class TestShutdownExecutor:
    """shutdown_executor() cleans up the pool."""

    def test_shutdown_clears_reference(self):
        get_executor()  # ensure one exists
        shutdown_executor(wait=True)
        # After shutdown, get_executor creates a new one
        new = get_executor()
        assert new is not None

    def test_double_shutdown_safe(self):
        """Calling shutdown twice doesn't raise."""
        shutdown_executor(wait=True)
        shutdown_executor(wait=True)  # no-op


class TestCancelToken:
    """CancelToken provides per-request cancellation."""

    def test_initial_state(self):
        from app.core.cancellation import CancelToken

        token = CancelToken()
        assert not token.is_set()

    def test_cancel(self):
        from app.core.cancellation import CancelToken

        token = CancelToken()
        token.cancel()
        assert token.is_set()

    def test_reset(self):
        from app.core.cancellation import CancelToken

        token = CancelToken()
        token.cancel()
        token.reset()
        assert not token.is_set()

    def test_thread_safe(self):
        """Multiple threads can check/set the token safely."""
        from app.core.cancellation import CancelToken

        token = CancelToken()
        results = []

        def worker():
            time.sleep(0.05)
            results.append(token.is_set())

        import threading

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        token.cancel()
        for t in threads:
            t.join()

        # All threads should have seen the cancellation (set before they check)
        assert all(results)
