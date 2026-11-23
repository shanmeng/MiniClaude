"""PermissionPolicy: pure ALLOW / DENY / ASK decisions for tool calls (F2, AD4)."""

from __future__ import annotations

import enum
from collections.abc import Mapping, Sequence
from typing import Any

from miniclaude.permissions.rules import parse_rule


class Decision(enum.Enum):
    """Outcome of a permission check."""

    ALLOW = "allow"
    DENY = "deny"
    ASK = "ask"


class PermissionPolicy:
    """Decides, without I/O, whether a tool call may run."""

    def __init__(self, *, allow: Sequence[str] = ()) -> None:
        self._allow = tuple(parse_rule(text) for text in allow)

    def decide(self, tool_name: str, tool_input: Mapping[str, Any]) -> Decision:
        """Return the decision for calling `tool_name` with `tool_input`."""
        if any(rule.matches(tool_name, tool_input) for rule in self._allow):
            return Decision.ALLOW
        return Decision.ASK
