"""Abstract base class for all LLM providers.

Every provider must implement :meth:`_call_model`.  The shared retry /
fallback logic in :meth:`generate` is inherited by all concrete providers
— eliminating the previous duplication of ~300 lines across
``generate_with_retry_v2`` and ``generate_with_retry_openai``.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import ClassVar

from app.config import settings
from app.core.log import safe_print


class LLMProvider(ABC):
    """Strategy interface + shared retry/fallback loop."""

    name: str = "base"

    # Subclasses must set these
    default_model_list: ClassVar[list[str]] = []

    def __init__(self, api_keys: list[str] | None = None):
        self.api_keys = api_keys or []

    # ── Public API ──────────────────────────────────────────────────────

    def generate(
        self,
        *,
        system: str,
        prompt: str,
        model_list: list[str] | None = None,
        cancel_check: Callable[[], bool] | None = None,
        response_format_json: bool = False,
        temperature: float | None = None,
        file_bytes: bytes | None = None,
        mime_type: str | None = None,
    ) -> tuple[str, str]:
        """Generate text.  Routes through key-rotation → retry loop → _call_model.

        Returns:
            ``(response_text, model_name_used)``
        """
        temperature = temperature if temperature is not None else settings.default_temperature
        models = model_list or self.default_model_list
        if not models:
            raise ValueError(f"[{self.name}] No models configured.")

        keys = self.api_keys or self._resolve_env_keys()
        if not keys:
            raise ValueError(
                f"[{self.name}] No API keys / endpoints configured.  "
                "Set the corresponding environment variable or pass keys explicitly."
            )

        last_exc: Exception | None = None
        for idx, key in enumerate(keys):
            safe_print(f"🔑 [{self.name}] Key {idx + 1}/{len(keys)}")
            try:
                return self._retry_loop(
                    key=key,
                    system=system,
                    prompt=prompt,
                    models=models,
                    cancel_check=cancel_check,
                    response_format_json=response_format_json,
                    temperature=temperature,
                    file_bytes=file_bytes,
                    mime_type=mime_type,
                )
            except Exception as exc:
                safe_print(f"⚠️ [{self.name}] Key {idx + 1} failed: {str(exc)[:120]}")
                last_exc = exc

        raise ValueError(f"[{self.name}] All keys exhausted. Last error: {last_exc}")

    # ── Internals ───────────────────────────────────────────────────────

    def _retry_loop(
        self,
        *,
        key: str,
        system: str,
        prompt: str,
        models: list[str],
        cancel_check: Callable[[], bool] | None,
        response_format_json: bool,
        temperature: float,
        file_bytes: bytes | None,
        mime_type: str | None,
    ) -> tuple[str, str]:
        """Cyclic model fallback with smart delay, shared by every provider."""
        permanently_failed: set[str] = set()
        model_last_used: dict[str, float] = {}
        min_delay = self._min_retry_delay()
        total_cycles = settings.ai_retry_cycles
        last_error: Exception | None = None

        for cycle in range(1, total_cycles + 1):
            self._check_cancel(cancel_check)
            safe_print(f"\n--- [{self.name}] CYCLE {cycle}/{total_cycles} ---")

            available = [m for m in models if m not in permanently_failed]
            if not available:
                safe_print(f"⚠️ [{self.name}] All models exhausted. Stopping.")
                break

            for model_name in models:
                if model_name in permanently_failed:
                    continue

                # Smart delay
                self._smart_wait(model_name, model_last_used, min_delay, cancel_check)
                model_last_used[model_name] = time.time()

                try:
                    text = self._call_model(
                        key=key,
                        model=model_name,
                        system=system,
                        prompt=prompt,
                        response_format_json=response_format_json,
                        temperature=temperature,
                        file_bytes=file_bytes,
                        mime_type=mime_type,
                    )
                    if text and text.strip():
                        safe_print(f"✅ [{self.name}] Success with {model_name}.")
                        return text.strip(), model_name
                    else:
                        safe_print(f"[{model_name}] Empty response. Skipping...")
                        continue
                except _PermanentModelError as pme:
                    safe_print(f"[{model_name}] Permanent failure: {pme}. Removing.")
                    permanently_failed.add(model_name)
                    last_error = pme
                except _SkipModelError as sme:
                    safe_print(f"[{model_name}] Temporary failure: {sme}. Skipping.")
                    last_error = sme
                except _AbortAllError as aae:
                    raise ValueError(str(aae)) from aae
                except Exception as exc:
                    safe_print(f"[{model_name}] Unexpected: {str(exc)[:150]}. Skipping.")
                    last_error = exc

            if cycle < total_cycles:
                safe_print(f"Cycle {cycle} done with NO SUCCESS. Next cycle...")
                time.sleep(1)

        raise ValueError(f"[{self.name}] All models failed after {total_cycles} cycles. Last error: {last_error}")

    # ── Subclass contract ───────────────────────────────────────────────

    @abstractmethod
    def _call_model(
        self,
        *,
        key: str,
        model: str,
        system: str,
        prompt: str,
        response_format_json: bool,
        temperature: float,
        file_bytes: bytes | None,
        mime_type: str | None,
    ) -> str:
        """Execute a single model call.  Return the response text.

        Raise:
            _PermanentModelError – model should never be retried (404, quota=0).
            _SkipModelError      – try the next model in this cycle (rate-limit, content filter).
            _AbortAllError       – stop all retries immediately (invalid API key).
        """

    @abstractmethod
    def _resolve_env_keys(self) -> list[str]:
        """Return API keys from environment when none were passed explicitly."""

    def _min_retry_delay(self) -> float:
        """Seconds to wait between retries.  Override for local providers."""
        return settings.min_retry_delay_remote

    # ── Helpers ─────────────────────────────────────────────────────────

    @staticmethod
    def _check_cancel(cancel_check: Callable[[], bool] | None) -> None:
        if cancel_check and cancel_check():
            safe_print("⚠️ Cancel requested. Aborting.")
            raise ValueError("Operation cancelled by user.")

    @staticmethod
    def _smart_wait(
        model: str,
        timestamps: dict[str, float],
        min_delay: float,
        cancel_check: Callable[[], bool] | None,
    ) -> None:
        last = timestamps.get(model, 0)
        if last == 0:
            return
        elapsed = time.time() - last
        if elapsed >= min_delay:
            return
        wait = min_delay - elapsed
        safe_print(f"[{model}] Smart Wait: {wait:.1f}s...")
        waited = 0.0
        step = 0.5
        while waited < wait:
            if cancel_check and cancel_check():
                raise ValueError("Operation cancelled by user.")
            time.sleep(step)
            waited += step


# ── Sentinel exception hierarchy (internal only) ───────────────────────


class _PermanentModelError(Exception):
    """Model should be removed from the retry list (404, limit=0)."""


class _SkipModelError(Exception):
    """Skip to the next model in this cycle (429, content filter)."""


class _AbortAllError(Exception):
    """Stop all retries immediately (invalid API key)."""
