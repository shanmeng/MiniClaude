"""Tests for the read_file tool."""

from __future__ import annotations

from pathlib import Path

from miniclaude.tools.builtin.read_file import ReadFileTool
from miniclaude.tools.output import DEFAULT_OUTPUT_LIMIT, TRUNCATION_MARKER


def test_returns_file_contents(workspace: Path) -> None:  # F1-AC6
    (workspace / "a.txt").write_text("hello\n", encoding="utf-8")
    output = ReadFileTool(workspace).run({"path": "a.txt"})
    assert (output.content, output.is_error) == ("hello\n", False)


def test_missing_file_is_error(workspace: Path) -> None:
    output = ReadFileTool(workspace).run({"path": "missing.txt"})
    assert output.is_error
    assert "not found" in output.content


def test_directory_is_error(workspace: Path) -> None:
    (workspace / "sub").mkdir()
    output = ReadFileTool(workspace).run({"path": "sub"})
    assert output.is_error
    assert "directory" in output.content


def test_non_utf8_file_is_error(workspace: Path) -> None:
    (workspace / "blob.bin").write_bytes(b"\xff\xfe\x00\x80")
    output = ReadFileTool(workspace).run({"path": "blob.bin"})
    assert output.is_error
    assert "UTF-8" in output.content


def test_large_file_truncated_with_marker(workspace: Path) -> None:  # F1-AC6
    (workspace / "big.txt").write_text("x" * (DEFAULT_OUTPUT_LIMIT + 500), encoding="utf-8")
    output = ReadFileTool(workspace).run({"path": "big.txt"})
    assert output.content == "x" * DEFAULT_OUTPUT_LIMIT + TRUNCATION_MARKER


def test_refuses_path_outside_workspace(workspace: Path, tmp_path: Path) -> None:  # F1-AC7
    (tmp_path / "secret.txt").write_text("secret", encoding="utf-8")
    output = ReadFileTool(workspace).run({"path": "../secret.txt"})
    assert output.is_error
    assert "outside the workspace" in output.content
