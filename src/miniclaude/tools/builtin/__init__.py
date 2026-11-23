"""Built-in tools: read_file, write_file, list_dir and bash."""

from __future__ import annotations

from pathlib import Path

from miniclaude.tools.base import Tool
from miniclaude.tools.builtin.bash import DEFAULT_TIMEOUT_SECONDS, BashTool
from miniclaude.tools.builtin.list_dir import ListDirTool
from miniclaude.tools.builtin.read_file import ReadFileTool
from miniclaude.tools.builtin.write_file import WriteFileTool


def default_tools(root: Path, *, bash_timeout: float = DEFAULT_TIMEOUT_SECONDS) -> list[Tool]:
    """Return the four built-in tools, all rooted at `root`."""
    return [
        ReadFileTool(root),
        WriteFileTool(root),
        ListDirTool(root),
        BashTool(root, timeout=bash_timeout),
    ]
