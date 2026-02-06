"""Tests for app.prompts — template modules."""

from __future__ import annotations

from app.prompts.review import (
    PROMPT_REVIEW_ANALYST_FICTION,
    PROMPT_REVIEW_ANALYST_NON_FICTION,
    PROMPT_REVIEW_EDITOR,
    PROMPT_REVIEW_LIBRARIAN,
)
from app.prompts.slide import (
    DETAIL_MODE_INSTRUCTION,
    OVERVIEW_MODE_INSTRUCTION,
    SYSTEM_INSTRUCTION,
    build_custom_instruction_block,
)
from app.prompts.summary import (
    PROMPT_DEEP_DIVE_FULL,
    PROMPT_SUMMARIZE_DOCUMENT,
    SUMMARIZER_SYSTEM_INSTRUCTION,
)


class TestSlidePrompts:
    """Validate slide prompt templates."""

    def test_system_instruction_non_empty(self):
        assert len(SYSTEM_INSTRUCTION) > 100

    def test_detail_mode_different_from_overview(self):
        assert DETAIL_MODE_INSTRUCTION != OVERVIEW_MODE_INSTRUCTION

    def test_custom_instruction_block_empty(self):
        result = build_custom_instruction_block("")
        assert result == ""

    def test_custom_instruction_block_with_content(self):
        result = build_custom_instruction_block("Focus on AI ethics")
        assert "AI ethics" in result
        assert len(result) > len("Focus on AI ethics")


class TestSummaryPrompts:
    """Validate summary prompt templates."""

    def test_summarizer_system_instruction_non_empty(self):
        assert len(SUMMARIZER_SYSTEM_INSTRUCTION) > 50

    def test_summarize_prompt_non_empty(self):
        assert len(PROMPT_SUMMARIZE_DOCUMENT) > 10

    def test_deep_dive_prompt_non_empty(self):
        assert len(PROMPT_DEEP_DIVE_FULL) > 50


class TestReviewPrompts:
    """Validate review prompt templates."""

    def test_all_review_prompts_exist(self):
        for prompt in [
            PROMPT_REVIEW_LIBRARIAN,
            PROMPT_REVIEW_ANALYST_NON_FICTION,
            PROMPT_REVIEW_ANALYST_FICTION,
            PROMPT_REVIEW_EDITOR,
        ]:
            assert isinstance(prompt, str)
            assert len(prompt) > 20

    def test_review_roles_different(self):
        prompts = {
            PROMPT_REVIEW_LIBRARIAN,
            PROMPT_REVIEW_ANALYST_NON_FICTION,
            PROMPT_REVIEW_ANALYST_FICTION,
            PROMPT_REVIEW_EDITOR,
        }
        assert len(prompts) == 4  # all unique
