"""Tests for the write_file tool."""

from __future__ import annotations

from pathlib import Path

from miniclaude.tools.builtin.write_file import WriteFileTool


def test_writes_content(workspace: Path) -> None:  # F1-AC6
    WriteFileTool(workspace).run({"path": "a.txt", "content": "hello"})
    assert (workspace / "a.txt").read_text(encoding="utf-8") == "hello"


def test_reports_chars_written(workspace: Path) -> None:
    output = WriteFileTool(workspace).run({"path": "a.txt", "content": "hello"})
    assert (output.content, output.is_error) == ("Wrote 5 chars to a.txt", False)


def test_overwrites_existing_file(workspace: Path) -> None:  # D9
    (workspace / "a.txt").write_text("old content", encoding="utf-8")
    WriteFileTool(workspace).run({"path": "a.txt", "content": "new"})
    assert (workspace / "a.txt").read_text(encoding="utf-8") == "new"


def test_creates_parent_dirs(workspace: Path) -> None:  # F1-AC6 (D9)
    WriteFileTool(workspace).run({"path": "src/pkg/mod.py", "content": "x = 1\n"})
    assert (workspace / "src" / "pkg" / "mod.py").read_text(encoding="utf-8") == "x = 1\n"


def test_directory_target_is_error(workspace: Path) -> None:
    (workspace / "sub").mkdir()
    output = WriteFileTool(workspace).run({"path": "sub", "content": "x"})
    assert output.is_error


def test_refuses_path_outside_workspace(workspace: Path, tmp_path: Path) -> None:  # F1-AC7
    output = WriteFileTool(workspace).run({"path": "../escape.txt", "content": "x"})
    assert output.is_error
    assert not (tmp_path / "escape.txt").exists()
