"""Tests for permission rule parsing and matching (F2)."""

from __future__ import annotations

import pytest
from miniclaude.permissions.rules import parse_rule


# F2-AC3
def test_exact_bash_rule_matches_the_exact_command() -> None:
    rule = parse_rule("bash(git status)")

    assert rule.matches("bash", {"command": "git status"})


# F2-AC3
@pytest.mark.parametrize("command", ["git status -s", "git statuses", "git", "echo git status"])
def test_exact_bash_rule_rejects_any_other_command(command: str) -> None:
    rule = parse_rule("bash(git status)")

    assert not rule.matches("bash", {"command": command})


# F2-AC3
@pytest.mark.parametrize("command", ["git diff", "git diff --stat", "git diff HEAD~1 -- src"])
def test_prefix_bash_rule_matches_the_prefix_on_a_word_boundary(command: str) -> None:
    rule = parse_rule("bash(git diff:*)")

    assert rule.matches("bash", {"command": command})


# F2-AC3
@pytest.mark.parametrize("command", ["git difftool", "git dif", "git", "echo git diff"])
def test_prefix_bash_rule_rejects_commands_without_the_word_prefix(command: str) -> None:
    rule = parse_rule("bash(git diff:*)")

    assert not rule.matches("bash", {"command": command})


# F2-AC3
def test_bash_rule_does_not_match_another_tool() -> None:
    rule = parse_rule("bash(git status)")

    assert not rule.matches("read_file", {"command": "git status"})
