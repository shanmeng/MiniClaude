"""Tests for BaseTool input validation and schema export."""

from __future__ import annotations

from pydantic import BaseModel

from miniclaude.tools.base import BaseTool, ToolOutput


class _EchoInput(BaseModel):
    text: str
    times: int = 1


class _EchoTool(BaseTool[_EchoInput]):
    name = "echo"
    description = "Echo text back."
    input_model = _EchoInput

    def execute(self, params: _EchoInput) -> ToolOutput:
        return ToolOutput(content=params.text * params.times)


def test_valid_input_is_passed_to_execute() -> None:
    assert _EchoTool().run({"text": "ab", "times": 2}) == ToolOutput(content="abab")


def test_invalid_input_becomes_error_output() -> None:  # F1-AC4 (D3)
    output = _EchoTool().run({"times": "many"})
    assert output.is_error


def test_invalid_input_error_names_the_tool_and_field() -> None:
    output = _EchoTool().run({})
    assert "echo" in output.content
    assert "text" in output.content


def test_input_schema_comes_from_input_model() -> None:  # F1-AC6
    schema = _EchoTool().input_schema
    assert schema["type"] == "object"
    assert set(schema["properties"]) == {"text", "times"}
    assert schema["required"] == ["text"]
