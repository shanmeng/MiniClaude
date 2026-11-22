"""Shared pytest configuration: skip `live` tests unless an API key is available."""

from __future__ import annotations

import os

import pytest


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Mark every `@pytest.mark.live` test as skipped when ANTHROPIC_API_KEY is unset."""
    if os.environ.get("ANTHROPIC_API_KEY"):
        return
    skip_live = pytest.mark.skip(reason="live test: set ANTHROPIC_API_KEY to run")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip_live)
