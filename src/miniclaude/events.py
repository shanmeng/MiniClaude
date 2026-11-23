"""Typed events the agent loop emits so callers (the CLI) can show progress (D6)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from miniclaude.tools.base import ToolOutput


@dataclass(frozen=True)
class AssistantText:
    """The model produced text in a turn."""

    text: str


@dataclass(frozen=True)
class ToolCallStarted:
    """A tool call is about to run."""

    tool_use_id: str
    name: str
    input: dict[str, Any]


@dataclass(frozen=True)
class ToolCallFinished:
    """A tool call finished (successfully or with an error output)."""

    tool_use_id: str
    name: str
    output: ToolOutput


Event = AssistantText | ToolCallStarted | ToolCallFinished
