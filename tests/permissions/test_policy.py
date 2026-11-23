"""Tests for PermissionPolicy.decide(): pure ALLOW / DENY / ASK decisions (F2)."""

from __future__ import annotations

from pathlib import Path
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


WORKSPACE = Path("/abs/workspace")


# F2-AC4
@pytest.mark.parametrize(
    ("path", "expected"),
    [("src/pkg/app.py", Decision.ALLOW), ("tests/test_app.py", Decision.ASK)],
)
def test_path_rule_in_allow_matches_with_glob_semantics(path: str, expected: Decision) -> None:
    policy = PermissionPolicy(allow=["write_file(src/**)"])

    assert policy.decide("write_file", {"path": path, "content": "x"}) is expected


# F2-AC4
@pytest.mark.parametrize("path", ["/abs/workspace/.env", "/abs/workspace/src/../.env"])
def test_absolute_path_inside_workspace_is_matched_relative_to_the_root(path: str) -> None:
    policy = PermissionPolicy(allow=["read_file(.env)"], workspace_root=WORKSPACE)

    assert policy.decide("read_file", {"path": path}) is Decision.ALLOW


# F2-AC4
@pytest.mark.parametrize("path", ["/elsewhere/.env", "/abs/workspace-other/.env"])
def test_absolute_path_outside_workspace_is_not_relativized(path: str) -> None:
    policy = PermissionPolicy(allow=["read_file(**)"], workspace_root=WORKSPACE)

    assert policy.decide("read_file", {"path": path}) is Decision.ASK


# F2-AC5
def test_deny_rule_denies_a_matching_call() -> None:
    policy = PermissionPolicy(deny=["write_file"])

    assert policy.decide("write_file", {"path": "a.txt", "content": "x"}) is Decision.DENY


# F2-AC5
def test_deny_rule_beats_allow_rule() -> None:
    policy = PermissionPolicy(allow=["read_file"], deny=["read_file(.env)"])

    assert policy.decide("read_file", {"path": ".env"}) is Decision.DENY


# F2-AC5
def test_narrow_deny_rule_leaves_other_allowed_calls_allowed() -> None:
    policy = PermissionPolicy(allow=["read_file"], deny=["read_file(.env)"])

    assert policy.decide("read_file", {"path": "README.md"}) is Decision.ALLOW


# F2-AC5
def test_ask_rule_beats_allow_rule() -> None:
    policy = PermissionPolicy(allow=["bash(git:*)"], ask=["bash(git push:*)"])

    assert policy.decide("bash", {"command": "git push origin main"}) is Decision.ASK


# F2-AC5
def test_deny_rule_beats_ask_rule() -> None:
    policy = PermissionPolicy(ask=["read_file"], deny=["read_file(.env)"])

    assert policy.decide("read_file", {"path": ".env"}) is Decision.DENY


# F2-AC5 with the AC4 workspace root: an absolute path cannot slip past a relative deny rule.
@pytest.mark.parametrize("path", ["/abs/workspace/.env", "/abs/workspace/src/../.env"])
def test_relative_deny_rule_catches_absolute_path_inside_workspace(path: str) -> None:
    policy = PermissionPolicy(
        allow=["read_file"], deny=["read_file(.env)"], workspace_root=WORKSPACE
    )

    assert policy.decide("read_file", {"path": path}) is Decision.DENY
