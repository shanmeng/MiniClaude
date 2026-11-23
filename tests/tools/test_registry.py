"""Tests for ToolRegistry and the built-in tool set."""

from __future__ import annotations

from pathlib import Path

import pytest

from miniclaude.tools.builtin import default_tools
from miniclaude.tools.builtin.read_file import ReadFileTool
from miniclaude.tools.registry import ToolRegistry


def test_get_returns_registered_tool(workspace: Path) -> None:
    tool = ReadFileTool(workspace)
    assert ToolRegistry([tool]).get("read_file") is tool


def test_get_unknown_name_returns_none(workspace: Path) -> None:
    assert ToolRegistry([ReadFileTool(workspace)]).get("nope") is None


def test_duplicate_tool_name_raises(workspace: Path) -> None:
    with pytest.raises(ValueError, match="read_file"):
        ToolRegistry([ReadFileTool(workspace), ReadFileTool(workspace)])


def test_default_tools_are_the_four_builtins(workspace: Path) -> None:  # F1-AC6
    names = [spec.name for spec in ToolRegistry(default_tools(workspace)).specs()]
    assert names == ["read_file", "write_file", "list_dir", "bash"]


@pytest.mark.parametrize(
    ("name", "required"),
    [
        ("read_file", ["path"]),
        ("write_file", ["path", "content"]),
        ("list_dir", []),
        ("bash", ["command"]),
    ],
)
def test_specs_export_json_schema_per_tool(
    workspace: Path, name: str, required: list[str]
) -> None:  # F1-AC6
    specs = {spec.name: spec for spec in ToolRegistry(default_tools(workspace)).specs()}
    schema = specs[name].input_schema
    assert schema["type"] == "object"
    assert schema.get("required", []) == required
    assert specs[name].description
