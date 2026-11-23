"""ToolRegistry: maps tool names to tools and exports their specs for the model."""

from __future__ import annotations

from collections.abc import Iterable

from miniclaude.llm.types import ToolSpec
from miniclaude.tools.base import Tool


class ToolRegistry:
    """Holds the tools available to the agent, keyed by unique name."""

    def __init__(self, tools: Iterable[Tool]) -> None:
        self._tools: dict[str, Tool] = {}
        for tool in tools:
            if tool.name in self._tools:
                raise ValueError(f"Duplicate tool name: {tool.name}")
            self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        """Return the tool called `name`, or None if there is none."""
        return self._tools.get(name)

    def specs(self) -> list[ToolSpec]:
        """Return a ToolSpec (name, description, JSON schema) for every tool, in order."""
        return [
            ToolSpec(name=tool.name, description=tool.description, input_schema=tool.input_schema)
            for tool in self._tools.values()
        ]
