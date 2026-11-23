"""Command-line entry point for MiniClaude."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, TextIO

import anthropic
from dotenv import find_dotenv, load_dotenv

from miniclaude import __version__
from miniclaude.events import AssistantText, Event, ToolCallFinished, ToolCallStarted
from miniclaude.llm.provider import AnthropicProvider, LLMProvider
from miniclaude.loop import DEFAULT_MAX_STEPS, AgentLoop, RunResult
from miniclaude.permissions.approval import Approver
from miniclaude.permissions.policy import PermissionPolicy
from miniclaude.prompt import SYSTEM_PROMPT
from miniclaude.tools.builtin import default_tools
from miniclaude.tools.registry import ToolRegistry

DEFAULT_MODEL = "claude-sonnet-5-5"
EXIT_OK = 0
EXIT_STOPPED = 1
EXIT_USAGE = 2
_MAX_INPUT_PREVIEW = 120
_MAX_ERROR_PREVIEW = 200
_SETTINGS_FILE = Path(".miniclaude") / "settings.json"
_YES_ANSWERS = frozenset({"y", "yes"})


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level argument parser."""
    parser = argparse.ArgumentParser(prog="miniclaude", description=__doc__)
    parser.add_argument("--version", action="version", version=f"miniclaude {__version__}")
    subcommands = parser.add_subparsers(dest="command")
    run = subcommands.add_parser("run", help="run the agent once on a goal")
    run.add_argument("goal", help="what you want the agent to do")
    run.add_argument(
        "--workspace",
        type=Path,
        default=None,
        help="workspace root the tools are confined to (default: current directory)",
    )
    run.add_argument(
        "--max-steps",
        type=_positive_int,
        default=DEFAULT_MAX_STEPS,
        help=f"maximum number of model calls (default: {DEFAULT_MAX_STEPS})",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Parse arguments and run the requested command; returns a process exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command != "run":
        parser.print_help()
        return EXIT_OK

    workspace: Path = (args.workspace or Path.cwd()).resolve()
    if not workspace.is_dir():
        print(f"error: workspace is not a directory: {workspace}", file=sys.stderr)
        return EXIT_USAGE

    # Config errors fail fast, before any API call (AD6).
    try:
        policy = load_policy(workspace)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_USAGE

    # Search from the user's cwd, not from this module's location.
    load_dotenv(find_dotenv(usecwd=True))
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print(
            "error: ANTHROPIC_API_KEY is not set. Copy .env.example to .env and add your key.",
            file=sys.stderr,
        )
        return EXIT_USAGE

    model = os.environ.get("MINICLAUDE_MODEL") or DEFAULT_MODEL
    provider = AnthropicProvider(anthropic.Anthropic(), model=model)
    return run_command(
        args.goal,
        provider,
        workspace=workspace,
        max_steps=args.max_steps,
        out=sys.stdout,
        err=sys.stderr,
        policy=policy,
        approver=terminal_approver(sys.stdin, sys.stderr),
    )


def load_policy(workspace: Path) -> PermissionPolicy:
    """Load `<workspace>/.miniclaude/settings.json`, or an empty (all-ASK) policy if absent."""
    settings = workspace / _SETTINGS_FILE
    if settings.is_file():
        return PermissionPolicy.from_file(settings, workspace_root=workspace)
    return PermissionPolicy(workspace_root=workspace)


def terminal_approver(inp: TextIO, out: TextIO) -> Approver:
    """Build an approver that prints the call to `out` and reads y/N from `inp`."""

    def approve(tool_name: str, tool_input: Mapping[str, Any]) -> bool:
        # The full input, unshortened: the user should see exactly what they approve.
        args = json.dumps(dict(tool_input), ensure_ascii=False)
        print(f"Allow {tool_name} {args}? [y/N] ", end="", file=out, flush=True)
        return inp.readline().strip().lower() in _YES_ANSWERS

    return approve


def run_command(
    goal: str,
    provider: LLMProvider,
    *,
    workspace: Path,
    max_steps: int,
    out: TextIO,
    err: TextIO,
    policy: PermissionPolicy | None = None,
    approver: Approver | None = None,
) -> int:
    """Run the agent loop on `goal`, printing progress to `out`; returns an exit code."""

    def show(event: Event) -> None:
        print(format_event(event), file=out, flush=True)

    loop = AgentLoop(
        provider,
        ToolRegistry(default_tools(workspace)),
        system=SYSTEM_PROMPT,
        max_steps=max_steps,
        on_event=show,
        policy=policy,
        approver=approver,
    )
    try:
        result = loop.run(goal)
    except anthropic.APIError as exc:
        print(f"error: {describe_api_error(exc)}", file=err)
        return EXIT_STOPPED

    stop_message = describe_stop(result, max_steps)
    if stop_message is None:
        return EXIT_OK
    print(stop_message, file=err)
    return EXIT_STOPPED


def format_event(event: Event) -> str:
    """Render one loop event as a line (or block) of terminal output."""
    if isinstance(event, AssistantText):
        return event.text
    if isinstance(event, ToolCallStarted):
        args = _shorten(json.dumps(event.input, ensure_ascii=False), _MAX_INPUT_PREVIEW)
        return f"→ {event.name} {args}"
    return _format_finished(event)


def _format_finished(event: ToolCallFinished) -> str:
    if event.output.is_error:
        return f"✗ {event.name}: {_shorten(_last_line(event.output.content), _MAX_ERROR_PREVIEW)}"
    return f"✓ {event.name} ({len(event.output.content)} chars)"


def describe_stop(result: RunResult, max_steps: int) -> str | None:
    """Explain why a run stopped early, or return None if the model finished normally."""
    if result.stop_reason == "max_steps":
        return (
            f"Stopped: step limit ({max_steps}) reached before the model finished. "
            "Try a narrower goal or a higher --max-steps."
        )
    if result.stop_reason == "refusal":
        return "Stopped: the model declined to continue with this request (refusal)."
    if result.stop_reason == "max_tokens":
        return (
            "Stopped: the model's reply hit the output token limit and was cut off; "
            "any tool calls in that reply were not run."
        )
    return None


def describe_api_error(exc: anthropic.APIError) -> str:
    """Turn an Anthropic SDK error into a one-line message for the terminal."""
    if isinstance(exc, anthropic.AuthenticationError):
        return "the Anthropic API rejected the API key (check ANTHROPIC_API_KEY)."
    if isinstance(exc, anthropic.RateLimitError):
        return "rate limited by the Anthropic API; wait a moment and try again."
    if isinstance(exc, anthropic.APIStatusError):
        return f"Anthropic API error {exc.status_code}: {exc.message}"
    if isinstance(exc, anthropic.APIConnectionError):
        return "could not reach the Anthropic API (check your network connection)."
    return f"Anthropic API error: {exc}"


def _positive_int(value: str) -> int:
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError(f"must be at least 1, got {number}")
    return number


def _shorten(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _last_line(text: str) -> str:
    lines = [line for line in text.splitlines() if line.strip()]
    return lines[-1] if lines else ""
