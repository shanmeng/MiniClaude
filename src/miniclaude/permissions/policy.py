"""PermissionPolicy: pure ALLOW / DENY / ASK decisions for tool calls (F2, AD4)."""

from __future__ import annotations

import enum
from collections.abc import Mapping
from typing import Any


class Decision(enum.Enum):
    """Outcome of a permission check."""

    ALLOW = "allow"
    DENY = "deny"
    ASK = "ask"


class PermissionPolicy:
    """Decides, without I/O, whether a tool call may run."""

    def decide(self, tool_name: str, tool_input: Mapping[str, Any]) -> Decision:
        """Return the decision for calling `tool_name` with `tool_input`."""
        return Decision.ASK
