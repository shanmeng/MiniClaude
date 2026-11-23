"""PermissionPolicy: pure ALLOW / DENY / ASK decisions for tool calls (F2, AD4)."""

from __future__ import annotations

import enum
import re
from collections.abc import Mapping, Sequence
from pathlib import PurePath
from typing import Any

from miniclaude.permissions.rules import Rule, parse_rule

# Longest operators first, so "&&" and "||" are not read as two "&" or "|".
_COMMAND_SEPARATORS = re.compile(r"&&|\|\||[;&|\n]")
# Substitution and redirection can run or write anything, whatever the command prefix.
_UNSAFE_CONSTRUCTS = re.compile(r"\$\(|`|[<>]")


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
        command = tool_input.get("command")
        if tool_name == "bash" and isinstance(command, str):
            return self._decide_command(command)
        return self._decide_by_rules(tool_name, tool_input)

    def _decide_command(self, command: str) -> Decision:
        parts = [part.strip() for part in _COMMAND_SEPARATORS.split(command) if part.strip()]
        if not parts:
            # Otherwise "every part is allowed" would be vacuously true.
            return Decision.ASK
        decisions = [self._decide_command_part(part) for part in parts]
        if Decision.DENY in decisions:
            return Decision.DENY
        if all(decision is Decision.ALLOW for decision in decisions):
            return Decision.ALLOW
        return Decision.ASK

    def _decide_command_part(self, part: str) -> Decision:
        decision = self._decide_by_rules("bash", {"command": part})
        if decision is Decision.ALLOW and _UNSAFE_CONSTRUCTS.search(part):
            return Decision.ASK
        return decision

    def _decide_by_rules(self, tool_name: str, tool_input: Mapping[str, Any]) -> Decision:
        root = self._workspace_root
        for decision, rules in self._rules_by_decision:
            if any(rule.matches(tool_name, tool_input, workspace_root=root) for rule in rules):
                return decision
        return Decision.ASK
