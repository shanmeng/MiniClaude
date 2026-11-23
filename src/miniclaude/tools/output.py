"""Helpers for keeping tool output small enough for the model's context."""

from __future__ import annotations

DEFAULT_OUTPUT_LIMIT = 10_000
TRUNCATION_MARKER = "\n[truncated]"


def truncate(text: str, limit: int = DEFAULT_OUTPUT_LIMIT) -> str:
    """Return `text` cut to `limit` characters, with a marker appended if it was cut."""
    if len(text) <= limit:
        return text
    return text[:limit] + TRUNCATION_MARKER
