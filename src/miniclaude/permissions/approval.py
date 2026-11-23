"""Approver: the injected callback that decides an ASK-ed tool call (F2-AC8, AD4)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol


class Approver(Protocol):
    """Asks whether `tool_name` may run with `tool_input`; returns True to approve."""

    def __call__(self, tool_name: str, tool_input: Mapping[str, Any]) -> bool: ...
