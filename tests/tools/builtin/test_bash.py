"""Tests for the bash tool. Commands are harmless and use short timeouts."""

from __future__ import annotations

import time
from pathlib import Path

from miniclaude.tools.builtin.bash import DEFAULT_TIMEOUT_SECONDS, BashTool
from miniclaude.tools.output import DEFAULT_OUTPUT_LIMIT, TRUNCATION_MARKER


def _bash(workspace: Path, timeout: float = 5.0) -> BashTool:
    return BashTool(workspace, timeout=timeout)


def test_returns_stdout(workspace: Path) -> None:  # F1-AC6
    output = _bash(workspace).run({"command": "echo hello"})
    assert (output.content, output.is_error) == ("hello\n", False)


def test_combines_stdout_and_stderr(workspace: Path) -> None:  # D8
    output = _bash(workspace).run({"command": "echo out; echo err 1>&2"})
    assert output.content == "out\nerr\n"


def test_runs_in_workspace_root(workspace: Path) -> None:  # D7
    _bash(workspace).run({"command": "echo x > marker.txt"})
    assert (workspace / "marker.txt").exists()


def test_nonzero_exit_is_error_with_code(workspace: Path) -> None:  # F1-AC6 (D8)
    output = _bash(workspace).run({"command": "echo failing; exit 3"})
    assert output.is_error
    assert output.content == "failing\n[exit code: 3]"


def test_exit_code_on_its_own_line_when_output_lacks_newline(workspace: Path) -> None:
    output = _bash(workspace).run({"command": "printf partial; false"})
    assert output.content == "partial\n[exit code: 1]"


def test_success_without_output_says_so(workspace: Path) -> None:
    assert _bash(workspace).run({"command": "true"}).content == "(no output)"


def test_timeout_returns_error(workspace: Path) -> None:  # F1-AC6 (D8)
    started = time.monotonic()
    output = _bash(workspace, timeout=0.3).run({"command": "sleep 5; echo done"})
    assert output.is_error
    assert "timed out after 0.3s" in output.content
    assert time.monotonic() - started < 3


def test_stdin_is_closed_so_reading_commands_do_not_hang(workspace: Path) -> None:
    output = _bash(workspace, timeout=2).run({"command": "cat"})
    assert (output.content, output.is_error) == ("(no output)", False)


def test_output_truncated_with_marker(workspace: Path) -> None:  # F1-AC6 (D8)
    output = _bash(workspace).run({"command": "yes x | head -n 20000"})
    assert output.content.endswith(TRUNCATION_MARKER)
    assert len(output.content) == DEFAULT_OUTPUT_LIMIT + len(TRUNCATION_MARKER)


def test_default_timeout_is_30_seconds() -> None:  # D8
    assert DEFAULT_TIMEOUT_SECONDS == 30.0
