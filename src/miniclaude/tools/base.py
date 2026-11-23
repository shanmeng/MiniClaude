"""Tool protocol, tool output type and a base class that validates input with pydantic."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import Any, Protocol

from pydantic import BaseModel, ValidationError


class ToolOutput(BaseModel):
    """The result of running a tool; `is_error` marks a failure the model should see."""

    content: str
    is_error: bool = False


class Tool(Protocol):
    """Interface every tool implements; the loop and registry depend only on this."""

    @property
    def name(self) -> str: ...

    @property
    def description(self) -> str: ...

    @property
    def input_schema(self) -> dict[str, Any]: ...

    def run(self, raw_input: Mapping[str, Any]) -> ToolOutput: ...


class BaseTool[InputT: BaseModel](ABC):
    """Validates raw input against `input_model`, then calls `execute` with the typed model."""

    name: str
    description: str
    input_model: type[InputT]

    @property
    def input_schema(self) -> dict[str, Any]:
        """JSON schema for the tool input, derived from `input_model`."""
        return self.input_model.model_json_schema()

    def run(self, raw_input: Mapping[str, Any]) -> ToolOutput:
        """Validate `raw_input` and execute; invalid input becomes an error output (D3)."""
        try:
            params = self.input_model.model_validate(dict(raw_input))
        except ValidationError as exc:
            return ToolOutput(content=_format_validation_error(self.name, exc), is_error=True)
        return self.execute(params)

    @abstractmethod
    def execute(self, params: InputT) -> ToolOutput:
        """Run the tool with validated input."""


def _format_validation_error(tool_name: str, exc: ValidationError) -> str:
    problems = "; ".join(
        f"{'.'.join(str(part) for part in err['loc']) or '<input>'}: {err['msg']}"
        for err in exc.errors(include_url=False)
    )
    return f"Invalid input for {tool_name}: {problems}"
