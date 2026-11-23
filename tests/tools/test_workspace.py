"""Tests for workspace-root confinement (F1-AC7, AD7)."""

from __future__ import annotations

from pathlib import Path

import pytest

from miniclaude.tools.workspace import OutsideWorkspaceError, resolve_in_workspace


def test_relative_path_resolves_inside_root(workspace: Path) -> None:
    assert resolve_in_workspace(workspace, "src/a.py") == workspace.resolve() / "src" / "a.py"


def test_dotdot_that_stays_inside_is_normalized(workspace: Path) -> None:
    assert resolve_in_workspace(workspace, "src/../a.py") == workspace.resolve() / "a.py"


def test_absolute_path_inside_root_is_accepted(workspace: Path) -> None:
    target = workspace / "a.py"
    assert resolve_in_workspace(workspace, str(target)) == target.resolve()


def test_root_itself_is_accepted(workspace: Path) -> None:
    assert resolve_in_workspace(workspace, ".") == workspace.resolve()


def test_rejects_parent_traversal(workspace: Path) -> None:  # F1-AC7
    with pytest.raises(OutsideWorkspaceError):
        resolve_in_workspace(workspace, "../secret.txt")


def test_rejects_absolute_outside(workspace: Path) -> None:  # F1-AC7
    with pytest.raises(OutsideWorkspaceError):
        resolve_in_workspace(workspace, "/etc/passwd")


def test_rejects_symlink_escaping_root(workspace: Path, tmp_path: Path) -> None:  # F1-AC7
    outside = tmp_path / "outside"
    outside.mkdir()
    (workspace / "link").symlink_to(outside)
    with pytest.raises(OutsideWorkspaceError):
        resolve_in_workspace(workspace, "link/secret.txt")


def test_error_is_a_value_error(workspace: Path) -> None:
    with pytest.raises(ValueError, match="outside the workspace"):
        resolve_in_workspace(workspace, "..")
