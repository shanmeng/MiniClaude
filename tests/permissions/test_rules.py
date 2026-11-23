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


# F2-AC4
@pytest.mark.parametrize("path", ["src/app.py", "src/pkg/mod.py", "src/a/b/c/d.txt"])
def test_double_star_path_rule_crosses_directories(path: str) -> None:
    rule = parse_rule("write_file(src/**)")

    assert rule.matches("write_file", {"path": path, "content": "x"})


# F2-AC4
@pytest.mark.parametrize("path", ["tests/app.py", "srcfoo/app.py", "lib/src/app.py"])
def test_double_star_path_rule_rejects_paths_outside_its_prefix(path: str) -> None:
    rule = parse_rule("write_file(src/**)")

    assert not rule.matches("write_file", {"path": path, "content": "x"})


# F2-AC4
def test_single_star_path_rule_matches_within_one_directory() -> None:
    rule = parse_rule("read_file(src/*.py)")

    assert rule.matches("read_file", {"path": "src/app.py"})


# F2-AC4
def test_single_star_path_rule_does_not_cross_directories() -> None:
    rule = parse_rule("read_file(src/*.py)")

    assert not rule.matches("read_file", {"path": "src/pkg/app.py"})


# F2-AC4
@pytest.mark.parametrize(("path", "expected"), [("a1.txt", True), ("a12.txt", False)])
def test_question_mark_path_rule_matches_exactly_one_character(path: str, expected: bool) -> None:
    rule = parse_rule("read_file(a?.txt)")

    assert rule.matches("read_file", {"path": path}) is expected


# F2-AC4
@pytest.mark.parametrize("path", [".env", "./.env", "src/../.env", "a/b/../../.env"])
def test_path_is_normalized_before_matching(path: str) -> None:
    rule = parse_rule("read_file(.env)")

    assert rule.matches("read_file", {"path": path})


# F2-AC4
def test_path_rule_does_not_match_a_file_with_the_same_name_elsewhere() -> None:
    rule = parse_rule("read_file(.env)")

    assert not rule.matches("read_file", {"path": "src/.env"})


# F2-AC4
def test_list_dir_path_rule_matches_the_path_input() -> None:
    rule = parse_rule("list_dir(src/**)")

    assert rule.matches("list_dir", {"path": "src/pkg"})


# F2-AC4
def test_list_dir_without_a_path_is_checked_as_the_workspace_root() -> None:
    rule = parse_rule("list_dir(.)")

    assert rule.matches("list_dir", {})


# F2-AC4
def test_path_rule_does_not_match_another_tool() -> None:
    rule = parse_rule("read_file(src/**)")

    assert not rule.matches("write_file", {"path": "src/app.py", "content": "x"})
