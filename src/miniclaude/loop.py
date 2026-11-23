"""AgentLoop: the ReAct loop that alternates model calls and tool execution (F1)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from miniclaude.events import AssistantText, Event, ToolCallFinished, ToolCallStarted
from miniclaude.llm.provider import LLMProvider
from miniclaude.llm.types import (
    ContentBlock,
    Message,
    ModelResponse,
    TextBlock,
    ToolResultBlock,
    ToolUseBlock,
)
from miniclaude.permissions.approval import Approver
from miniclaude.permissions.policy import Decision, PermissionPolicy
from miniclaude.tools.base import ToolOutput
from miniclaude.tools.registry import ToolRegistry

DEFAULT_MAX_STEPS = 20

StopReason = Literal["end_turn", "max_steps", "refusal", "max_tokens"]

# Model stop reasons that end the run even if the reply contains tool_use blocks: a refusal
# has nothing to act on, and a max_tokens cut-off can leave a truncated tool_use input.
_TERMINAL_MODEL_STOPS: dict[str, StopReason] = {"refusal": "refusal", "max_tokens": "max_tokens"}


@dataclass(frozen=True)
class RunResult:
    """How a run ended: final text, why it stopped, model calls made, and the transcript."""

    text: str
    stop_reason: StopReason
    steps: int
    messages: list[Message]


def _ignore_event(event: Event) -> None:
    """Default event handler: do nothing."""


class AgentLoop:
    """Sends the conversation to the model, runs requested tools, and repeats until done."""

    def __init__(
        self,
        provider: LLMProvider,
        registry: ToolRegistry,
        *,
        system: str,
        max_steps: int = DEFAULT_MAX_STEPS,
        on_event: Callable[[Event], None] = _ignore_event,
        policy: PermissionPolicy | None = None,
        approver: Approver | None = None,
    ) -> None:
        """Create a loop; with `policy=None` tool calls are not permission-gated."""
        if max_steps < 1:
            raise ValueError(f"max_steps must be at least 1, got {max_steps}")
        self._provider = provider
        self._registry = registry
        self._system = system
        self._max_steps = max_steps
        self._on_event = on_event
        self._policy = policy
        self._approver = approver

    def run(self, goal: str) -> RunResult:
        """Run the loop for `goal`; provider errors propagate, tool errors do not (AD6)."""
        messages: list[Message] = [Message(role="user", content=[TextBlock(text=goal)])]
        tools = self._registry.specs()
        text = ""
        for step in range(1, self._max_steps + 1):
            response = self._provider.complete(system=self._system, messages=messages, tools=tools)
            assistant_content: list[ContentBlock] = list(response.content)
            messages.append(Message(role="assistant", content=assistant_content))
            text = self._report_text(response)

            terminal = _TERMINAL_MODEL_STOPS.get(response.stop_reason)
            if terminal is not None:
                return RunResult(text=text, stop_reason=terminal, steps=step, messages=messages)

            tool_uses = [block for block in response.content if isinstance(block, ToolUseBlock)]
            if not tool_uses:
                return RunResult(text=text, stop_reason="end_turn", steps=step, messages=messages)

            # All results from one assistant turn go back in a single user message (AC3).
            results: list[ContentBlock] = [self._execute(tool_use) for tool_use in tool_uses]
            messages.append(Message(role="user", content=results))

        return RunResult(
            text=text, stop_reason="max_steps", steps=self._max_steps, messages=messages
        )

    def _report_text(self, response: ModelResponse) -> str:
        texts = [block.text for block in response.content if isinstance(block, TextBlock)]
        for text in texts:
            if text.strip():
                self._on_event(AssistantText(text=text))
        return "\n".join(texts)

    def _execute(self, tool_use: ToolUseBlock) -> ToolResultBlock:
        self._on_event(
            ToolCallStarted(tool_use_id=tool_use.id, name=tool_use.name, input=tool_use.input)
        )
        output = self._run_tool(tool_use)
        self._on_event(ToolCallFinished(tool_use_id=tool_use.id, name=tool_use.name, output=output))
        return ToolResultBlock(
            tool_use_id=tool_use.id, content=output.content, is_error=output.is_error
        )

    def _run_tool(self, tool_use: ToolUseBlock) -> ToolOutput:
        tool = self._registry.get(tool_use.name)
        if tool is None:
            return ToolOutput(content=f"Unknown tool: {tool_use.name}", is_error=True)
        refusal = self._check_permission(tool_use)
        if refusal is not None:
            return refusal
        try:
            return tool.run(tool_use.input)
        except Exception as exc:  # AD6: a buggy tool becomes an error result the model can see.
            return ToolOutput(content=f"{type(exc).__name__}: {exc}", is_error=True)

    def _check_permission(self, tool_use: ToolUseBlock) -> ToolOutput | None:
        """Return an error output if the call may not run, or None if it may (F2-AC8)."""
        if self._policy is None:
            return None
        decision = self._policy.decide(tool_use.name, tool_use.input)
        if decision is Decision.ALLOW:
            return None
        # Distinct texts so the model can tell a fixed rule from a one-off human "no".
        if decision is Decision.DENY:
            return ToolOutput(
                content=f"Permission denied by policy: {tool_use.name} was not run.",
                is_error=True,
            )
        if self._approver is not None and self._approver(tool_use.name, tool_use.input):
            return None
        return ToolOutput(
            content=f"The user declined this {tool_use.name} call; it was not run.",
            is_error=True,
        )
