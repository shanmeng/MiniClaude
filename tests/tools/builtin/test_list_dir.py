"""Tests for the list_dir tool."""

from __future__ import annotations

from pathlib import Path

from miniclaude.tools.builtin.list_dir import ListDirTool


def test_lists_entries_sorted_with_dir_suffix(workspace: Path) -> None:  # F1-AC6
    (workspace / "b.txt").touch()
    (workspace / "a").mkdir()
    (workspace / "c.py").touch()
    output = ListDirTool(workspace).run({"path": "."})
    assert output.content == "a/\nb.txt\nc.py"


def test_path_defaults_to_workspace_root(workspace: Path) -> None:
    (workspace / "a.txt").touch()
    assert ListDirTool(workspace).run({}).content == "a.txt"


def test_lists_subdirectory_without_recursing(workspace: Path) -> None:
    (workspace / "sub" / "deep").mkdir(parents=True)
    (workspace / "sub" / "deep" / "x.txt").touch()
    assert ListDirTool(workspace).run({"path": "sub"}).content == "deep/"


def test_empty_directory_says_so(workspace: Path) -> None:
    output = ListDirTool(workspace).run({"path": "."})
    assert (output.content, output.is_error) == ("(empty directory)", False)


def test_missing_directory_is_error(workspace: Path) -> None:
    output = ListDirTool(workspace).run({"path": "nope"})
    assert output.is_error
    assert "not found" in output.content


def test_file_path_is_error(workspace: Path) -> None:
    (workspace / "a.txt").touch()
    output = ListDirTool(workspace).run({"path": "a.txt"})
    assert output.is_error
    assert "Not a directory" in output.content


def test_refuses_path_outside_workspace(workspace: Path) -> None:  # F1-AC7
    output = ListDirTool(workspace).run({"path": ".."})
    assert output.is_error
    assert "outside the workspace" in output.content
