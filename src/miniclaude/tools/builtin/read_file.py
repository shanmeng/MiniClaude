"""read_file tool: return the text of a file inside the workspace."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from miniclaude.tools.base import BaseTool, ToolOutput
from miniclaude.tools.output import truncate
from miniclaude.tools.workspace import OutsideWorkspaceError, resolve_in_workspace


class ReadFileInput(BaseModel):
    """Input for read_file."""

    path: str = Field(description="Path of the file to read, relative to the workspace root.")


class ReadFileTool(BaseTool[ReadFileInput]):
    """Reads a UTF-8 text file in the workspace; long files are truncated."""

    name = "read_file"
    description = "Read a UTF-8 text file in the workspace and return its contents."
    input_model = ReadFileInput

    def __init__(self, root: Path) -> None:
        self._root = root

    def execute(self, params: ReadFileInput) -> ToolOutput:
        """Read the file, or return an error output if it can't be read."""
        try:
            path = resolve_in_workspace(self._root, params.path)
            text = path.read_text(encoding="utf-8")
        except OutsideWorkspaceError as exc:
            return ToolOutput(content=str(exc), is_error=True)
        except FileNotFoundError:
            return ToolOutput(content=f"File not found: {params.path}", is_error=True)
        except IsADirectoryError:
            return ToolOutput(content=f"Is a directory, not a file: {params.path}", is_error=True)
        except UnicodeDecodeError:
            return ToolOutput(content=f"Not a UTF-8 text file: {params.path}", is_error=True)
        return ToolOutput(content=truncate(text))
