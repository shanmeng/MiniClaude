"""LLMProvider protocol and AnthropicProvider, which converts to and from SDK types (AD2, AD3)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, cast

import anthropic
from anthropic.types import (
    AssistantMessageParam,
    ContentBlockParam,
    MessageParam,
    TextBlockParam,
    ToolParam,
    ToolResultBlockParam,
    ToolUseBlockParam,
    UserMessageParam,
)
from anthropic.types import Message as SDKMessage
from anthropic.types import TextBlock as SDKTextBlock
from anthropic.types import ToolUseBlock as SDKToolUseBlock

from miniclaude.llm.types import (
    ContentBlock,
    Message,
    ModelResponse,
    OpaqueBlock,
    ResponseBlock,
    TextBlock,
    ToolResultBlock,
    ToolSpec,
    ToolUseBlock,
)

# Thinking tokens count toward max_tokens on current models; 16k leaves room for thinking plus a
# full write_file payload while staying under the SDK's non-streaming timeout guard.
DEFAULT_MAX_TOKENS = 16_000


class LLMProvider(Protocol):
    """Sends a conversation and tool specs to a model and returns its reply."""

    def complete(
        self, *, system: str, messages: Sequence[Message], tools: Sequence[ToolSpec]
    ) -> ModelResponse: ...


class AnthropicProvider:
    """LLMProvider backed by the Anthropic Messages API."""

    def __init__(
        self, client: anthropic.Anthropic, model: str, max_tokens: int = DEFAULT_MAX_TOKENS
    ) -> None:
        self._client = client
        self._model = model
        self._max_tokens = max_tokens

    def complete(
        self, *, system: str, messages: Sequence[Message], tools: Sequence[ToolSpec]
    ) -> ModelResponse:
        """Call messages.create and convert the reply; API errors propagate (AD6)."""
        response = self._client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            system=system,
            messages=to_message_params(messages),
            tools=to_tool_params(tools) if tools else anthropic.omit,
        )
        return from_sdk_message(response)


def to_message_params(messages: Sequence[Message]) -> list[MessageParam]:
    """Convert our messages to the SDK's request shape."""
    return [_to_message_param(message) for message in messages]


def to_tool_params(specs: Sequence[ToolSpec]) -> list[ToolParam]:
    """Convert our tool specs to the SDK's tool definitions."""
    return [
        {"name": spec.name, "description": spec.description, "input_schema": spec.input_schema}
        for spec in specs
    ]


def from_sdk_message(message: SDKMessage) -> ModelResponse:
    """Convert an SDK reply; blocks other than text/tool_use are kept as OpaqueBlocks."""
    content: list[ResponseBlock] = []
    for block in message.content:
        if isinstance(block, SDKTextBlock):
            content.append(TextBlock(text=block.text))
        elif isinstance(block, SDKToolUseBlock):
            content.append(ToolUseBlock(id=block.id, name=block.name, input=dict(block.input)))
        else:
            # Thinking blocks must be sent back unchanged on the next request, or the API can
            # reject the turn; exclude_unset keeps exactly the fields the API returned.
            content.append(OpaqueBlock(data=block.to_dict(mode="json")))
    return ModelResponse(content=content, stop_reason=message.stop_reason or "unknown")


def _to_message_param(message: Message) -> MessageParam:
    content = [_to_block_param(block) for block in message.content]
    if message.role == "user":
        user: UserMessageParam = {"role": "user", "content": content}
        return user
    assistant: AssistantMessageParam = {"role": "assistant", "content": content}
    return assistant


def _to_block_param(block: ContentBlock) -> ContentBlockParam:
    if isinstance(block, TextBlock):
        text: TextBlockParam = {"type": "text", "text": block.text}
        return text
    if isinstance(block, ToolUseBlock):
        tool_use: ToolUseBlockParam = {
            "type": "tool_use",
            "id": block.id,
            "name": block.name,
            "input": block.input,
        }
        return tool_use
    if isinstance(block, ToolResultBlock):
        result: ToolResultBlockParam = {
            "type": "tool_result",
            "tool_use_id": block.tool_use_id,
            "content": block.content,
            "is_error": block.is_error,
        }
        return result
    # OpaqueBlock data came from the API's own response, so it is a valid block param.
    return cast(ContentBlockParam, block.data)
