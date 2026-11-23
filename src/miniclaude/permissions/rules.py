"""Permission rules: parse strings like "bash(git diff:*)" and match them against tool calls."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

_PREFIX_SUFFIX = ":*"


@dataclass(frozen=True)
class Rule:
    """A parsed rule: a tool name plus an optional specifier from inside the parentheses."""

    tool: str
    specifier: str | None = None

    def matches(self, tool_name: str, tool_input: Mapping[str, Any]) -> bool:
        """Return True if this rule applies to calling `tool_name` with `tool_input`."""
        if tool_name != self.tool:
            return False
        if self.specifier is None:
            return True
        if self.tool == "bash":
            return _matches_command(self.specifier, tool_input.get("command"))
        return False


def parse_rule(text: str) -> Rule:
    """Parse a rule string such as "read_file" or "bash(git diff:*)"."""
    tool, paren, rest = text.partition("(")
    if not paren:
        return Rule(tool=tool)
    return Rule(tool=tool, specifier=rest.removesuffix(")"))


def _matches_command(specifier: str, command: object) -> bool:
    if not isinstance(command, str):
        return False
    if specifier.endswith(_PREFIX_SUFFIX):
        prefix = specifier.removesuffix(_PREFIX_SUFFIX)
        # Word boundary: "git diff:*" covers "git diff --stat" but not "git difftool".
        return command == prefix or command.startswith(prefix + " ")
    return command == specifier
