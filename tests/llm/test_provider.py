"""Tests for AnthropicProvider and its SDK conversion layer.

Offline tests build SDK objects directly or serve canned JSON through an httpx2 MockTransport.
The one `live` test calls the real API and is skipped unless ANTHROPIC_API_KEY is set.
"""

from __future__ import annotations

import json
import os
from typing import Any

import anthropic
import httpx2
import pytest
from anthropic.types import Message as SDKMessage

from miniclaude.llm.provider import (
    DEFAULT_MAX_TOKENS,
    AnthropicProvider,
    from_sdk_message,
    to_message_params,
    to_tool_params,
)
from miniclaude.llm.types import (
    Message,
    OpaqueBlock,
    TextBlock,
    ToolResultBlock,
    ToolSpec,
    ToolUseBlock,
)

_THINKING = {"type": "thinking", "thinking": "", "signature": "sig-abc"}
_SPEC = ToolSpec(
    name="read_file",
    description="Read a file.",
    input_schema={"type": "object", "properties": {"path": {"type": "string"}}},
)


def _sdk_message_json(content: list[dict[str, Any]], stop_reason: str | None) -> dict[str, Any]:
    return {
        "id": "msg_1",
        "type": "message",
        "role": "assistant",
        "model": "test-model",
        "content": content,
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "usage": {"input_tokens": 1, "output_tokens": 1},
    }


def _sdk_message(content: list[dict[str, Any]], stop_reason: str | None = "end_turn") -> SDKMessage:
    return SDKMessage.model_validate(_sdk_message_json(content, stop_reason))


# --- request conversion ------------------------------------------------------


def test_tool_spec_becomes_tool_param() -> None:
    assert to_tool_params([_SPEC]) == [
        {
            "name": "read_file",
            "description": "Read a file.",
            "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}},
        }
    ]


def test_user_text_message_becomes_param() -> None:
    message = Message(role="user", content=[TextBlock(text="hi")])
    assert to_message_params([message]) == [
        {"role": "user", "content": [{"type": "text", "text": "hi"}]}
    ]


def test_assistant_tool_use_becomes_param() -> None:
    message = Message(
        role="assistant", content=[ToolUseBlock(id="tu_1", name="read_file", input={"path": "a"})]
    )
    assert to_message_params([message]) == [
        {
            "role": "assistant",
            "content": [
                {"type": "tool_use", "id": "tu_1", "name": "read_file", "input": {"path": "a"}}
            ],
        }
    ]


def test_tool_result_keeps_id_content_and_error_flag() -> None:  # F1-AC2, F1-AC4
    message = Message(
        role="user",
        content=[ToolResultBlock(tool_use_id="tu_1", content="File not found", is_error=True)],
    )
    assert to_message_params([message])[0]["content"] == [
        {
            "type": "tool_result",
            "tool_use_id": "tu_1",
            "content": "File not found",
            "is_error": True,
        }
    ]


def test_opaque_block_is_sent_back_unchanged() -> None:
    message = Message(role="assistant", content=[OpaqueBlock(data=_THINKING)])
    assert to_message_params([message])[0]["content"] == [_THINKING]


# --- response conversion -----------------------------------------------------


def test_text_and_tool_use_blocks_are_converted() -> None:
    sdk = _sdk_message(
        [
            {"type": "text", "text": "Let me look."},
            {"type": "tool_use", "id": "tu_1", "name": "read_file", "input": {"path": "a"}},
        ],
        stop_reason="tool_use",
    )
    assert from_sdk_message(sdk).content == [
        TextBlock(text="Let me look."),
        ToolUseBlock(id="tu_1", name="read_file", input={"path": "a"}),
    ]


def test_thinking_block_becomes_opaque_with_exact_fields() -> None:
    assert from_sdk_message(_sdk_message([_THINKING])).content == [OpaqueBlock(data=_THINKING)]


def test_stop_reason_is_passed_through() -> None:
    assert from_sdk_message(_sdk_message([], stop_reason="refusal")).stop_reason == "refusal"


def test_missing_stop_reason_becomes_unknown() -> None:
    assert from_sdk_message(_sdk_message([], stop_reason=None)).stop_reason == "unknown"


def test_thinking_round_trips_through_assistant_history() -> None:
    response = from_sdk_message(_sdk_message([_THINKING, {"type": "text", "text": "ok"}]))
    history = Message(role="assistant", content=list(response.content))
    assert to_message_params([history])[0]["content"] == [
        _THINKING,
        {"type": "text", "text": "ok"},
    ]


# --- complete() over a mock HTTP transport ------------------------------------


class _Recorder:
    """Captures request bodies and answers with a canned Messages API response."""

    def __init__(self, response_json: dict[str, Any]) -> None:
        self.bodies: list[dict[str, Any]] = []
        self._response_json = response_json

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.bodies.append(json.loads(request.content))
        return httpx2.Response(200, json=self._response_json)


def _provider(recorder: _Recorder, max_tokens: int = DEFAULT_MAX_TOKENS) -> AnthropicProvider:
    client = anthropic.Anthropic(
        api_key="test-key",
        max_retries=0,
        http_client=anthropic.DefaultHttpxClient(transport=httpx2.MockTransport(recorder)),
    )
    return AnthropicProvider(client, model="test-model", max_tokens=max_tokens)


_HELLO = [Message(role="user", content=[TextBlock(text="hello")])]


def test_complete_sends_model_system_tools_and_messages() -> None:
    recorder = _Recorder(_sdk_message_json([{"type": "text", "text": "hi"}], "end_turn"))
    _provider(recorder).complete(system="SYS", messages=_HELLO, tools=[_SPEC])
    body = recorder.bodies[0]
    assert (body["model"], body["max_tokens"], body["system"]) == ("test-model", 16_000, "SYS")
    assert body["messages"] == [{"role": "user", "content": [{"type": "text", "text": "hello"}]}]
    assert [tool["name"] for tool in body["tools"]] == ["read_file"]


def test_complete_omits_tools_when_there_are_none() -> None:
    recorder = _Recorder(_sdk_message_json([{"type": "text", "text": "hi"}], "end_turn"))
    _provider(recorder).complete(system="SYS", messages=_HELLO, tools=[])
    assert "tools" not in recorder.bodies[0]


def test_complete_returns_converted_response() -> None:
    recorder = _Recorder(_sdk_message_json([{"type": "text", "text": "hi"}], "end_turn"))
    response = _provider(recorder).complete(system="SYS", messages=_HELLO, tools=[])
    assert (response.content, response.stop_reason) == ([TextBlock(text="hi")], "end_turn")


def test_api_error_propagates() -> None:  # AD6: provider errors are fatal for the run
    def fail(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(
            500, json={"type": "error", "error": {"type": "api_error", "message": "boom"}}
        )

    client = anthropic.Anthropic(
        api_key="test-key",
        max_retries=0,
        http_client=anthropic.DefaultHttpxClient(transport=httpx2.MockTransport(fail)),
    )
    with pytest.raises(anthropic.APIStatusError):
        AnthropicProvider(client, model="m").complete(system="S", messages=_HELLO, tools=[])


def test_default_max_tokens_is_16000() -> None:  # D10, revised (see plan: Deviations)
    assert DEFAULT_MAX_TOKENS == 16_000


# --- live smoke test (D12) -----------------------------------------------------


@pytest.mark.live
def test_live_smoke() -> None:  # F1-AC8
    """One real tool round trip: tool_use out, tool_result (with thinking blocks) back in."""
    model = os.environ.get("MINICLAUDE_MODEL", "claude-sonnet-5-5")
    provider = AnthropicProvider(anthropic.Anthropic(), model=model)
    spec = ToolSpec(
        name="get_secret_word",
        description="Return the secret word.",
        input_schema={"type": "object", "properties": {}},
    )
    messages = [
        Message(role="user", content=[TextBlock(text="Use the tool to get the secret word.")])
    ]
    first = provider.complete(system="Be brief.", messages=messages, tools=[spec])
    tool_uses = [b for b in first.content if isinstance(b, ToolUseBlock)]
    assert [b.name for b in tool_uses] == ["get_secret_word"]

    messages.append(Message(role="assistant", content=list(first.content)))
    messages.append(
        Message(
            role="user", content=[ToolResultBlock(tool_use_id=tool_uses[0].id, content="pineapple")]
        )
    )
    second = provider.complete(system="Be brief.", messages=messages, tools=[spec])
    text = " ".join(b.text for b in second.content if isinstance(b, TextBlock))
    assert "pineapple" in text.lower()
