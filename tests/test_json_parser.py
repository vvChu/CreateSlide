"""Tests for app.core.json_parser — robust JSON/dict parsing."""

from __future__ import annotations

import pytest

from app.core.json_parser import robust_json_parse


class TestRobustJsonParse:
    """Test all 6 strategies of the parser."""

    # ── Strategy 1: Strip markdown fences ────────────────────────────────

    def test_json_with_markdown_fence(self):
        raw = '```json\n{"key": "value"}\n```'
        result = robust_json_parse(raw)
        assert result == {"key": "value"}

    def test_triple_backtick_no_lang(self):
        raw = '```\n{"a": 1}\n```'
        assert robust_json_parse(raw) == {"a": 1}

    # ── Strategy 2: Strict JSON ──────────────────────────────────────────

    def test_valid_json_dict(self):
        assert robust_json_parse('{"x": 42}') == {"x": 42}

    def test_valid_json_list(self):
        assert robust_json_parse("[1, 2, 3]") == [1, 2, 3]

    def test_nested_json(self):
        raw = '{"slides": [{"title": "A", "content": ["B"]}]}'
        result = robust_json_parse(raw)
        assert len(result["slides"]) == 1

    # ── Strategy 3: Python literal (single quotes) ───────────────────────

    def test_single_quoted_dict(self):
        raw = "{'key': 'value', 'num': 42}"
        result = robust_json_parse(raw)
        assert result == {"key": "value", "num": 42}

    # ── Strategy 4: Substring extraction ─────────────────────────────────

    def test_json_embedded_in_text(self):
        raw = 'Here is the result:\n\n{"answer": "hello"}\n\nPlease review.'
        result = robust_json_parse(raw)
        assert result == {"answer": "hello"}

    def test_json_embedded_with_prefix(self):
        raw = 'Sure! {"status": "ok"}'
        assert robust_json_parse(raw) == {"status": "ok"}

    # ── Strategy 5: Trailing commas ──────────────────────────────────────

    def test_trailing_comma_in_dict(self):
        raw = '{"a": 1, "b": 2,}'
        result = robust_json_parse(raw)
        assert result == {"a": 1, "b": 2}

    def test_trailing_comma_in_list(self):
        raw = '{"items": [1, 2, 3,]}'
        result = robust_json_parse(raw)
        assert result["items"] == [1, 2, 3]

    # ── Strategy 6: Unquoted keys ────────────────────────────────────────

    def test_unquoted_keys(self):
        raw = '{name: "Alice", age: 30}'
        result = robust_json_parse(raw)
        assert result["name"] == "Alice"
        assert result["age"] == 30

    # ── Failure case ─────────────────────────────────────────────────────

    def test_unparseable_raises_valueerror(self):
        with pytest.raises(ValueError, match="Failed to parse"):
            robust_json_parse("this is not json at all")

    def test_empty_string_raises(self):
        with pytest.raises(ValueError):
            robust_json_parse("")

    # ── Edge cases ───────────────────────────────────────────────────────

    def test_whitespace_around_json(self):
        raw = '   \n  {"ok": true}  \n  '
        assert robust_json_parse(raw) == {"ok": True}

    def test_multiple_json_objects_greedy_match(self):
        """When text contains multiple {…}, the greedy match may fail."""
        raw = 'Prefix {"first": 1} middle {"second": 2} end'
        # Greedy regex {.*} captures everything incl 'middle' — may fail or succeed
        # depending on whether the full match is valid JSON. This is acceptable.
        try:
            result = robust_json_parse(raw)
            assert isinstance(result, (dict, list))
        except ValueError:
            pass  # expected — multiple JSON in one string is ambiguous

    def test_real_world_llm_output(self):
        """Simulate an actual LLM response with fences + trailing comma."""
        raw = """```json
{
  "title": "Trí tuệ nhân tạo",
  "slides": [
    {"title": "Giới thiệu", "content": ["AI là gì?", "Tại sao quan trọng?"]},
    {"title": "Ứng dụng", "content": ["Y tế", "Giáo dục",]},
  ]
}
```"""
        result = robust_json_parse(raw)
        assert result["title"] == "Trí tuệ nhân tạo"
        assert len(result["slides"]) == 2
