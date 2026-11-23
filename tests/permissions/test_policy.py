"""Tests for PermissionPolicy.decide(): pure ALLOW / DENY / ASK decisions (F2)."""

from __future__ import annotations

from typing import Any

import pytest

from miniclaude.permissions.policy import Decision, PermissionPolicy


# F2-AC1
@pytest.mark.parametrize(
    ("tool_name", "tool_input"),
    [
        ("read_file", {"path": "README.md"}),
        ("write_file", {"path": "src/app.py", "content": "x"}),
        ("list_dir", {"path": "."}),
        ("bash", {"command": "ls"}),
        ("some_unknown_tool", {}),
    ],
)
def test_no_rules_means_every_call_is_ask(tool_name: str, tool_input: dict[str, Any]) -> None:
    assert PermissionPolicy().decide(tool_name, tool_input) is Decision.ASK


# F2-AC2
@pytest.mark.parametrize(
    ("tool_name", "tool_input"),
    [
        ("read_file", {"path": "README.md"}),
        ("read_file", {"path": "src/deep/nested/file.py"}),
        ("list_dir", {}),
        ("bash", {"command": "rm -rf build"}),
    ],
)
def test_bare_tool_name_allow_rule_allows_every_call_to_that_tool(
    tool_name: str, tool_input: dict[str, Any]
) -> None:
    policy = PermissionPolicy(allow=[tool_name])

    assert policy.decide(tool_name, tool_input) is Decision.ALLOW


# F2-AC2
def test_bare_tool_name_allow_rule_does_not_affect_other_tools() -> None:
    policy = PermissionPolicy(allow=["read_file"])

    assert policy.decide("write_file", {"path": "README.md", "content": "x"}) is Decision.ASK


# F2-AC3
@pytest.mark.parametrize(
    ("rule", "command"),
    [("bash(git status)", "git status"), ("bash(git diff:*)", "git diff --stat")],
)
def test_bash_command_rule_in_allow_allows_matching_command(rule: str, command: str) -> None:
    policy = PermissionPolicy(allow=[rule])

    assert policy.decide("bash", {"command": command}) is Decision.ALLOW


# F2-AC3
@pytest.mark.parametrize(
    ("rule", "command"),
    [("bash(git status)", "git status -s"), ("bash(git diff:*)", "git difftool")],
)
def test_bash_command_rule_in_allow_leaves_other_commands_ask(rule: str, command: str) -> None:
    policy = PermissionPolicy(allow=[rule])

    assert policy.decide("bash", {"command": command}) is Decision.ASK
