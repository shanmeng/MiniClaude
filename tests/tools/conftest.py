"""Fixtures shared by the tool tests."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    """A workspace root nested in tmp_path, so tmp_path itself is 'outside' the workspace."""
    root = tmp_path / "workspace"
    root.mkdir()
    return root
