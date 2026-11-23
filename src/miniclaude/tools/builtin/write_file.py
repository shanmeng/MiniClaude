"""write_file tool: create or fully overwrite a file inside the workspace."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from miniclaude.tools.base import BaseTool, ToolOutput
from miniclaude.tools.workspace import OutsideWorkspaceError, resolve_in_workspace


class WriteFileInput(BaseModel):
    """Input for write_file."""

    path: str = Field(description="Path of the file to write, relative to the workspace root.")
    content: str = Field(description="Full new content of the file.")


class WriteFileTool(BaseTool[WriteFileInput]):
    """Writes a UTF-8 text file, replacing any existing content and creating parent dirs (D9)."""

    name = "write_file"
    description = (
        "Write content to a file in the workspace. Overwrites the whole file and creates "
        "missing parent directories."
    )
    input_model = WriteFileInput

    def __init__(self, root: Path) -> None:
        self._root = root

    def execute(self, params: WriteFileInput) -> ToolOutput:
        """Write the file, or return an error output if the path is not writable."""
        try:
            path = resolve_in_workspace(self._root, params.path)
        except OutsideWorkspaceError as exc:
            return ToolOutput(content=str(exc), is_error=True)
        if path.is_dir():
            return ToolOutput(content=f"Is a directory, not a file: {params.path}", is_error=True)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(params.content, encoding="utf-8")
        return ToolOutput(content=f"Wrote {len(params.content)} chars to {params.path}")
