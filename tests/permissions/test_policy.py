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
