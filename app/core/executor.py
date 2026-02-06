"""Shared thread-pool executor and async helpers.

Provides a bounded ``ThreadPoolExecutor`` reused across all requests
and an ``run_in_executor`` helper that wraps sync callables for
``await``-able usage from Mesop async generators.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import functools
import os
from collections.abc import Callable
from typing import Any, TypeVar

T = TypeVar("T")

_MAX_WORKERS = int(os.environ.get("SLIDEGENIUS_MAX_WORKERS", "4"))
_executor: concurrent.futures.ThreadPoolExecutor | None = None


def get_executor() -> concurrent.futures.ThreadPoolExecutor:
    """Return the shared executor, creating it lazily."""
    global _executor
    if _executor is None or _executor._shutdown:
        _executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=_MAX_WORKERS,
            thread_name_prefix="slidegenius",
        )
    return _executor


async def run_in_executor(fn: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    """Run *fn* in the shared thread pool and ``await`` the result.

    Usage::

        result = await run_in_executor(summarize_document, fb, mime, api_keys=keys)
    """
    loop = asyncio.get_running_loop()
    bound = functools.partial(fn, *args, **kwargs)
    return await loop.run_in_executor(get_executor(), bound)


def shutdown_executor(wait: bool = False) -> None:
    """Shut down the shared executor (e.g. on app teardown)."""
    global _executor
    if _executor is not None:
        _executor.shutdown(wait=wait, cancel_futures=True)
        _executor = None
