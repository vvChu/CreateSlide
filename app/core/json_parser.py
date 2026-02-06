"""Robust JSON / Python-dict parser for LLM output.

Handles Markdown code-blocks, single quotes, trailing commas,
unquoted keys, and substring extraction as graceful fallbacks.
"""

from __future__ import annotations

import ast
import json
import re


def robust_json_parse(text: str) -> dict | list:
    """Parse *text* into a Python dict/list, tolerating common LLM quirks.

    Strategy (ordered from safest to most aggressive):
        1. Strip Markdown fences.
        2. ``json.loads`` (strict).
        3. ``ast.literal_eval`` (handles single-quoted Python dicts).
        4. Substring extraction ``{…}`` then re-try 2 & 3.
        5. Fix trailing commas, then re-try.
        6. Quote bare JS-style keys, then re-try.

    Raises ``ValueError`` if every strategy fails.
    """
    text = text.strip()

    # 1. Strip Markdown code fences
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()

    # 2. Strict JSON
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 3. Python literal (single quotes, tuples, …)
    try:
        return ast.literal_eval(text)
    except (ValueError, SyntaxError):
        pass

    # 4. Substring extraction
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        subset = match.group(0)
        try:
            return json.loads(subset)
        except Exception:
            pass
        try:
            return ast.literal_eval(subset)
        except Exception:
            pass
        text = subset  # narrow scope for remaining repairs

    # 5. Fix trailing commas before ] or }
    text_fixed = re.sub(r",\s*([\]}])", r"\1", text)
    try:
        return json.loads(text_fixed)
    except Exception:
        pass
    try:
        return ast.literal_eval(text_fixed)
    except Exception:
        pass

    # 6. Quote unquoted JavaScript-style keys
    try:
        text_quoted = re.sub(r"(\w+):", r'"\1":', text_fixed)
        return json.loads(text_quoted)
    except Exception:
        pass

    raise ValueError(f"Failed to parse JSON/Dict from response. Raw text: {text[:300]}")
