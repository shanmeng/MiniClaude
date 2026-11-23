"""FakeProvider: replays scripted model responses so the loop can be tested offline (AC9)."""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any

from miniclaude.llm.types import Message, ModelResponse, TextBlock, ToolSpec, ToolUseBlock


class ScriptExhaustedError(RuntimeError):
    """Raised when the loop asks FakeProvider for more responses than were scripted."""


@dataclass(frozen=True)
class ProviderCall:
    """What the loop sent on one `complete` call, captured for assertions."""

    system: str
    messages: list[Message]
    tools: list[ToolSpec]


class FakeProvider:
    """An LLMProvider that returns scripted responses in order and records every call."""

    def __init__(self, responses: Iterable[ModelResponse]) -> None:
        self._responses = deque(responses)
        self.calls: list[ProviderCall] = []

    def complete(
        self, *, system: str, messages: Sequence[Message], tools: Sequence[ToolSpec]
    ) -> ModelResponse:
        """Record the call, then return the next scripted response."""
        # Deep copies, because the loop keeps appending to the same message list.
        self.calls.append(
            ProviderCall(
                system=system,
                messages=[message.model_copy(deep=True) for message in messages],
                tools=list(tools),
            )
        )
        if not self._responses:
            raise ScriptExhaustedError(
                f"FakeProvider has no response left for call {len(self.calls)}"
            )
        return self._responses.popleft()


def text_response(text: str) -> ModelResponse:
    """A scripted final answer: one text block, stop_reason end_turn."""
    return ModelResponse(content=[TextBlock(text=text)], stop_reason="end_turn")


def tool_use(tool_use_id: str, name: str, tool_input: dict[str, Any] | None = None) -> ToolUseBlock:
    """A scripted tool_use block."""
    return ToolUseBlock(id=tool_use_id, name=name, input=tool_input or {})


def tool_response(*tool_uses: ToolUseBlock, text: str | None = None) -> ModelResponse:
    """A scripted tool-calling turn: optional leading text, then the tool_use blocks."""
    content: list[TextBlock | ToolUseBlock] = [TextBlock(text=text)] if text else []
    content.extend(tool_uses)
    return ModelResponse(content=content, stop_reason="tool_use")
