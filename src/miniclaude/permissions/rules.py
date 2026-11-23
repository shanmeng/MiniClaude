"""Permission rules: parse strings like "bash(git diff:*)" and match them against tool calls."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import PurePath, PurePosixPath
from typing import Any

_PREFIX_SUFFIX = ":*"
_PATH_TOOLS = frozenset({"read_file", "write_file", "list_dir"})
# list_dir's `path` input is optional and defaults to the workspace root.
_DEFAULT_PATH = "."


@dataclass(frozen=True)
class Rule:
    """A parsed rule: a tool name plus an optional specifier from inside the parentheses."""

    tool: str
    specifier: str | None = None

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
        if self.tool in _PATH_TOOLS:
            path = tool_input.get("path", _DEFAULT_PATH)
            return _matches_path(self.specifier, path, workspace_root)
        return False


def parse_rule(text: str) -> Rule:
    """Parse a rule string such as "read_file" or "bash(git diff:*)"."""
    tool, paren, rest = text.partition("(")
    if not paren:
        return Rule(tool=tool)
    return Rule(tool=tool, specifier=rest.removesuffix(")"))


def normalize_path(path: str, workspace_root: PurePath | None = None) -> str:
    """Collapse "." and ".." lexically; make absolute paths inside `workspace_root` relative."""
    pure = PurePosixPath(path)
    parts: list[str] = []
    for part in pure.parts[1:] if pure.is_absolute() else pure.parts:
        if part == "..":
            if parts:
                parts.pop()
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


def _matches_path(pattern: str, path: object, workspace_root: PurePath | None) -> bool:
    if not isinstance(path, str):
        return False
    normalized = normalize_path(path, workspace_root)
    # A relative pattern such as "**" must never match an absolute path outside the workspace.
    if PurePosixPath(normalized).is_absolute() != PurePosixPath(pattern).is_absolute():
        return False
    return glob_to_regex(pattern).fullmatch(normalized) is not None
