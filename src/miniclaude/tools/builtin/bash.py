"""bash tool: run a shell command from the workspace root with a timeout."""

from __future__ import annotations

import os
import signal
import subprocess
from pathlib import Path

from pydantic import BaseModel, Field

from miniclaude.tools.base import BaseTool, ToolOutput
from miniclaude.tools.output import truncate

DEFAULT_TIMEOUT_SECONDS = 30.0


class BashInput(BaseModel):
    """Input for bash."""

    command: str = Field(description="Shell command to run from the workspace root.")


class BashTool(BaseTool[BashInput]):
    """Runs a shell command with cwd set to the workspace root (D8).

    The command can still `cd` out of the root or touch absolute paths: workspace
    confinement (AD7) only covers the file tools, and the F2 permission policy is the guard here.
    """

    name = "bash"
    description = (
        "Run a shell command from the workspace root and return its combined stdout and stderr. "
        "Non-zero exit codes are reported as errors."
    )
    input_model = BashInput

    def __init__(self, root: Path, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> None:
        self._root = root
        self._timeout = timeout

    def execute(self, params: BashInput) -> ToolOutput:
        """Run the command; a non-zero exit or a timeout becomes an error output."""
        # start_new_session puts the shell in its own process group so a timeout can kill
        # every child it spawned, not just the shell (otherwise communicate() can hang).
        with subprocess.Popen(
            params.command,
            shell=True,
            cwd=self._root,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            start_new_session=True,
        ) as proc:
            try:
                output, _ = proc.communicate(timeout=self._timeout)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.communicate()
                return ToolOutput(
                    content=f"Command timed out after {self._timeout:g}s", is_error=True
                )
        output = truncate(output)
        if proc.returncode != 0:
            separator = "" if not output or output.endswith("\n") else "\n"
            return ToolOutput(
                content=f"{output}{separator}[exit code: {proc.returncode}]", is_error=True
            )
        return ToolOutput(content=output or "(no output)")
