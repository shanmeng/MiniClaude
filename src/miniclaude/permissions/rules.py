"""Permission rules: parse strings like "bash(git diff:*)" and match them against tool calls."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import PurePath, PurePosixPath
from typing import Any

_PREFIX_SUFFIX = ":*"
_PATH_TOOLS = frozenset({"read_file", "write_file", "list_dir"})
# Only these tools take a specifier; anything else in parentheses is a typo to report.
_SPECIFIER_TOOLS = _PATH_TOOLS | {"bash"}
# list_dir's `path` input is optional and defaults to the workspace root.
_DEFAULT_PATH = "."
# A snake_case tool name, optionally followed by a non-empty "(specifier)".
_RULE_SYNTAX = re.compile(r"([a-z_][a-z0-9_]*)(?:\((.+)\))?")


class InvalidRuleError(ValueError):
    """Raised when a permission rule string cannot be parsed."""


@dataclass(frozen=True)
class Rule:
    """A parsed rule: a tool name plus an optional specifier from inside the parentheses."""

    tool: str
    specifier: str | None = None
    # Compiled once per rule from a path specifier; None for bare and bash rules.
    path_regex: re.Pattern[str] | None = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        regex = None
        if self.specifier is not None and self.tool in _PATH_TOOLS:
            regex = glob_to_regex(self.specifier)
        # The dataclass is frozen, so set the derived field the way dataclasses do.
        object.__setattr__(self, "path_regex", regex)

    def matches(
        self,
        tool_name: str,
        tool_input: Mapping[str, Any],
        *,
        workspace_root: PurePath | None = None,
    ) -> bool:
        """Return True if this rule applies to calling `tool_name` with `tool_input`."""
        if tool_name != self.tool:
            return False
        if self.specifier is None:
            return True
        if self.tool == "bash":
            return _matches_command(self.specifier, tool_input.get("command"))
        # parse_rule() only accepts a specifier on bash and the path tools.
        assert self.path_regex is not None
        path = tool_input.get("path", _DEFAULT_PATH)
        return _matches_path(self.specifier, self.path_regex, path, workspace_root)


def parse_rule(text: str) -> Rule:
    """Parse a rule string such as "read_file" or "bash(git diff:*)"; raise InvalidRuleError."""
    match = _RULE_SYNTAX.fullmatch(text)
    if match is None:
        raise InvalidRuleError(
            f"Invalid permission rule {text!r}: expected 'tool_name' or 'tool_name(specifier)'"
        )
    tool, specifier = match.group(1), match.group(2)
    if specifier is not None and tool not in _SPECIFIER_TOOLS:
        raise InvalidRuleError(
            f"Invalid permission rule {text!r}: {tool!r} does not take a specifier"
        )
    return Rule(tool=tool, specifier=specifier)


def normalize_path(path: str, workspace_root: PurePath | None = None) -> str:
    """Collapse "." and ".." lexically; make absolute paths inside `workspace_root` relative."""
    pure = PurePosixPath(path)
    parts: list[str] = []
    for part in pure.parts[1:] if pure.is_absolute() else pure.parts:
        if part == "..":
            if parts and parts[-1] != "..":
                parts.pop()
            elif not pure.is_absolute():
                # Keep a leading ".." so a path that climbs out of the workspace stays visible.
                parts.append(part)
        elif part != ".":
            parts.append(part)
    normalized = PurePosixPath(pure.anchor, *parts)
    if workspace_root is not None and normalized.is_relative_to(workspace_root):
        normalized = normalized.relative_to(workspace_root)
    return str(normalized)


def glob_to_regex(pattern: str) -> re.Pattern[str]:
    """Compile a glob where `**` crosses directories and `*` and `?` stay within one segment."""
    pieces: list[str] = []
    i = 0
    while i < len(pattern):
        if pattern.startswith("**", i):
            pieces.append(".*")
            i += 2
        elif pattern[i] == "*":
            pieces.append("[^/]*")
            i += 1
        elif pattern[i] == "?":
            pieces.append("[^/]")
            i += 1
        else:
            pieces.append(re.escape(pattern[i]))
            i += 1
    return re.compile("".join(pieces))


def _matches_command(specifier: str, command: object) -> bool:
    if not isinstance(command, str):
        return False
    if specifier.endswith(_PREFIX_SUFFIX):
        prefix = specifier.removesuffix(_PREFIX_SUFFIX)
        # Word boundary: "git diff:*" covers "git diff --stat" but not "git difftool".
        return command == prefix or command.startswith(prefix + " ")
    return command == specifier


def _matches_path(
    pattern: str, regex: re.Pattern[str], path: object, workspace_root: PurePath | None
) -> bool:
    if not isinstance(path, str):
        return False
    normalized = normalize_path(path, workspace_root)
    candidate = PurePosixPath(normalized)
    outside_workspace = candidate.is_absolute() or candidate.parts[:1] == ("..",)
    # A relative pattern such as "**" covers only paths inside the workspace.
    if outside_workspace and not PurePosixPath(pattern).is_absolute():
        return False
    return regex.fullmatch(normalized) is not None
