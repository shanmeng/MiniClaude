"""Provider-neutral message types used inside the agent loop (AD3)."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field


class TextBlock(BaseModel):
    """Plain text from the user or the model."""

    type: Literal["text"] = "text"
    text: str


class ToolUseBlock(BaseModel):
    """A request from the model to run a tool with the given input."""

    type: Literal["tool_use"] = "tool_use"
    id: str
    name: str
    input: dict[str, Any]


class ToolResultBlock(BaseModel):
    """The outcome of a tool call, sent back to the model under its tool_use_id."""

    type: Literal["tool_result"] = "tool_result"
    tool_use_id: str
    content: str
    is_error: bool = False


ContentBlock = Annotated[TextBlock | ToolUseBlock | ToolResultBlock, Field(discriminator="type")]
ResponseBlock = Annotated[TextBlock | ToolUseBlock, Field(discriminator="type")]


class Message(BaseModel):
    """One conversation turn: a role plus its content blocks."""

    role: Literal["user", "assistant"]
    content: list[ContentBlock]


class ToolSpec(BaseModel):
    """A tool definition as advertised to the model."""

    name: str
    description: str
    input_schema: dict[str, Any]


class ModelResponse(BaseModel):
    """One model reply: text and tool_use blocks plus the provider's stop reason."""

    content: list[ResponseBlock]
    stop_reason: str
