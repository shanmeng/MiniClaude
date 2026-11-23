"""Tests for tool output truncation."""

from __future__ import annotations

from miniclaude.tools.output import TRUNCATION_MARKER, truncate


def test_short_text_is_unchanged() -> None:
    assert truncate("hello", limit=10) == "hello"


def test_text_at_limit_is_unchanged() -> None:
    assert truncate("x" * 10, limit=10) == "x" * 10


def test_long_text_is_cut_with_marker() -> None:  # F1-AC6 (D8)
    assert truncate("x" * 11, limit=10) == "x" * 10 + TRUNCATION_MARKER
