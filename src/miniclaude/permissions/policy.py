"""PermissionPolicy: pure ALLOW / DENY / ASK decisions for tool calls (F2, AD4)."""

from __future__ import annotations

import enum
from collections.abc import Mapping, Sequence
from pathlib import PurePath
from typing import Any

from miniclaude.permissions.rules import Rule, parse_rule


class Decision(enum.Enum):
    """Outcome of a permission check."""

    ALLOW = "allow"
    DENY = "deny"
    ASK = "ask"


class PermissionPolicy:
    """Decides, without I/O, whether a tool call may run."""

    def __init__(
        self,
        *,
        allow: Sequence[str] = (),
        deny: Sequence[str] = (),
        ask: Sequence[str] = (),
        workspace_root: PurePath | None = None,
    ) -> None:
        # Checked in this order, so deny > ask > allow (AD5).
        self._rules_by_decision: tuple[tuple[Decision, tuple[Rule, ...]], ...] = (
            (Decision.DENY, tuple(parse_rule(text) for text in deny)),
            (Decision.ASK, tuple(parse_rule(text) for text in ask)),
            (Decision.ALLOW, tuple(parse_rule(text) for text in allow)),
        )
        self._workspace_root = workspace_root

    def decide(self, tool_name: str, tool_input: Mapping[str, Any]) -> Decision:
        """Return the decision for calling `tool_name` with `tool_input`."""
        root = self._workspace_root
        for decision, rules in self._rules_by_decision:
            if any(rule.matches(tool_name, tool_input, workspace_root=root) for rule in rules):
                return decision
        return Decision.ASK
