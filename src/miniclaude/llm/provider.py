"""LLMProvider protocol: the agent loop's only view of a language model (AD2)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from miniclaude.llm.types import Message, ModelResponse, ToolSpec


class LLMProvider(Protocol):
    """Sends a conversation and tool specs to a model and returns its reply."""

    def complete(
        self, *, system: str, messages: Sequence[Message], tools: Sequence[ToolSpec]
    ) -> ModelResponse: ...
