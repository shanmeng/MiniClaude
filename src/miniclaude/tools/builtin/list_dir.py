"""list_dir tool: list the entries of a directory inside the workspace."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from miniclaude.tools.base import BaseTool, ToolOutput
from miniclaude.tools.output import truncate
from miniclaude.tools.workspace import OutsideWorkspaceError, resolve_in_workspace


class ListDirInput(BaseModel):
    """Input for list_dir."""

    path: str = Field(default=".", description="Directory to list, relative to the workspace root.")


class ListDirTool(BaseTool[ListDirInput]):
    """Lists one directory (not recursive), sorted by name, with directories suffixed by '/'."""

    name = "list_dir"
    description = (
        "List the entries of a directory in the workspace (not recursive). "
        "Directories end with '/'."
    )
    input_model = ListDirInput

    def __init__(self, root: Path) -> None:
        self._root = root

    def execute(self, params: ListDirInput) -> ToolOutput:
        """List the directory, or return an error output if it can't be listed."""
        try:
            path = resolve_in_workspace(self._root, params.path)
        except OutsideWorkspaceError as exc:
            return ToolOutput(content=str(exc), is_error=True)
        if not path.exists():
            return ToolOutput(content=f"Directory not found: {params.path}", is_error=True)
        if not path.is_dir():
            return ToolOutput(content=f"Not a directory: {params.path}", is_error=True)
        entries = sorted(path.iterdir(), key=lambda entry: entry.name)
        lines = [entry.name + ("/" if entry.is_dir() else "") for entry in entries]
        return ToolOutput(content=truncate("\n".join(lines)) if lines else "(empty directory)")
