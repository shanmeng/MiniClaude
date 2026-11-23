"""Tests for the scripted FakeProvider (F1-AC9)."""

from __future__ import annotations

import pytest

from miniclaude.llm.fake import (
    FakeProvider,
    ScriptExhaustedError,
    text_response,
    tool_response,
    tool_use,
)
from miniclaude.llm.types import Message, TextBlock, ToolSpec, ToolUseBlock

_USER = Message(role="user", content=[TextBlock(text="hi")])
_SPEC = ToolSpec(name="echo", description="Echo.", input_schema={"type": "object"})


def _complete(provider: FakeProvider, messages: list[Message]) -> None:
    provider.complete(system="sys", messages=messages, tools=[_SPEC])


def test_replays_scripted_responses_in_order() -> None:  # F1-AC9
    provider = FakeProvider([text_response("one"), text_response("two")])
    first = provider.complete(system="s", messages=[_USER], tools=[])
    second = provider.complete(system="s", messages=[_USER], tools=[])
    assert (first, second) == (text_response("one"), text_response("two"))


def test_records_calls() -> None:  # F1-AC9
    provider = FakeProvider([text_response("ok")])
    _complete(provider, [_USER])
    call = provider.calls[0]
    assert (call.system, call.messages, call.tools) == ("sys", [_USER], [_SPEC])


def test_recorded_messages_are_copies() -> None:
    provider = FakeProvider([text_response("ok")])
    messages = [_USER.model_copy(deep=True)]
    _complete(provider, messages)
    messages.append(_USER)
    assert len(provider.calls[0].messages) == 1


def test_raises_when_script_exhausted() -> None:  # F1-AC9
    provider = FakeProvider([])
    with pytest.raises(ScriptExhaustedError):
        _complete(provider, [_USER])


def test_tool_response_puts_text_before_tool_uses() -> None:
    response = tool_response(tool_use("tu_1", "echo", {"x": 1}), text="thinking")
    assert response.content == [
        TextBlock(text="thinking"),
        ToolUseBlock(id="tu_1", name="echo", input={"x": 1}),
    ]
    assert response.stop_reason == "tool_use"
