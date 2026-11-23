"""Tests for permission rule parsing and matching (F2)."""

from __future__ import annotations

import pytest

from miniclaude.permissions.rules import InvalidRuleError, parse_rule


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


# F2-AC4: a path that climbs out of the workspace never matches a relative rule.
@pytest.mark.parametrize(
    ("rule_text", "path"),
    [("read_file(.env)", "../.env"), ("read_file(**)", "../secret.txt")],
)
def test_path_escaping_the_workspace_never_matches_a_relative_rule(
    rule_text: str, path: str
) -> None:
    rule = parse_rule(rule_text)

    assert not rule.matches("read_file", {"path": path})


# F2-AC7
@pytest.mark.parametrize(
    "text",
    [
        "",
        "   ",
        "bash(",
        "bash(git status",
        "bash)",
        "(git status)",
        "read_file()",
        "bash git status",
        "bash(git status) extra",
        "Read_File",
        "readfile(.env)",
    ],
)
def test_malformed_rule_raises_invalid_rule_error_naming_the_rule(text: str) -> None:
    with pytest.raises(InvalidRuleError) as excinfo:
        parse_rule(text)

    assert repr(text) in str(excinfo.value)


# F2-AC7
@pytest.mark.parametrize(
    "text", ["read_file", "some_future_tool", "bash(git diff:*)", "list_dir(src/**)"]
)
def test_well_formed_rule_parses(text: str) -> None:
    parse_rule(text)


# F2-AC7 guard: malformed tool input never matches.
@pytest.mark.parametrize("tool_input", [{}, {"command": 1}, {"command": None}])
def test_bash_rule_does_not_match_a_missing_or_non_string_command(
    tool_input: dict[str, object],
) -> None:
    assert not parse_rule("bash(git status)").matches("bash", tool_input)


# F2-AC7 guard: malformed tool input never matches.
def test_path_rule_does_not_match_a_non_string_path() -> None:
    assert not parse_rule("read_file(**)").matches("read_file", {"path": 3})
