"""Tests for AgentLoop, driven by the scripted FakeProvider (no network)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pytest

from miniclaude.events import AssistantText, Event, ToolCallFinished, ToolCallStarted
from miniclaude.llm.fake import FakeProvider, text_response, tool_response, tool_use
from miniclaude.llm.types import Message, ModelResponse, TextBlock, ToolResultBlock, ToolSpec
from miniclaude.loop import AgentLoop, RunResult
from miniclaude.tools.base import Tool, ToolOutput
from miniclaude.tools.builtin.read_file import ReadFileTool
from miniclaude.tools.registry import ToolRegistry


class _RecordingTool:
    """A Tool that records its inputs into a shared log and echoes them back."""

    def __init__(self, name: str, log: list[tuple[str, dict[str, Any]]]) -> None:
        self.name = name
        self.description = f"{name} test tool"
        self.input_schema: dict[str, Any] = {"type": "object"}
        self._log = log

    def run(self, raw_input: Mapping[str, Any]) -> ToolOutput:
        self._log.append((self.name, dict(raw_input)))
        return ToolOutput(content=f"{self.name} ok")


class _ExplodingTool:
    """A Tool whose run() raises, to simulate a bug in a tool."""

    name = "explode"
    description = "Always raises."
    input_schema: dict[str, Any] = {"type": "object"}

    def run(self, raw_input: Mapping[str, Any]) -> ToolOutput:
        raise RuntimeError("boom")


class _FailingProvider:
    """A provider that fails like a network error would."""

    def complete(
        self, *, system: str, messages: Sequence[Message], tools: Sequence[ToolSpec]
    ) -> ModelResponse:
        raise ConnectionError("network down")


def _run(
    script: list[ModelResponse],
    tools: Sequence[Tool] = (),
    *,
    max_steps: int = 20,
    on_event: list[Event] | None = None,
) -> tuple[RunResult, FakeProvider]:
    provider = FakeProvider(script)
    events = on_event if on_event is not None else []
    loop = AgentLoop(
        provider, ToolRegistry(tools), system="SYS", max_steps=max_steps, on_event=events.append
    )
    return loop.run("the goal"), provider


def _results_sent_in_call(provider: FakeProvider, call: int) -> list[ToolResultBlock]:
    last = provider.calls[call].messages[-1]
    assert last.role == "user"
    return [block for block in last.content if isinstance(block, ToolResultBlock)]


# --- AC1: plain answer -------------------------------------------------------


def test_returns_final_text_when_model_answers_without_tools() -> None:  # F1-AC1
    result, _ = _run([text_response("all done")])
    assert (result.text, result.stop_reason) == ("all done", "end_turn")


def test_end_turn_result_reports_one_step() -> None:  # F1-AC1
    result, _ = _run([text_response("all done")])
    assert result.steps == 1


def test_goal_is_sent_as_the_first_user_message() -> None:
    _, provider = _run([text_response("ok")])
    assert provider.calls[0].messages == [
        Message(role="user", content=[TextBlock(text="the goal")])
    ]


def test_system_prompt_and_tool_specs_are_sent() -> None:
    _, provider = _run([text_response("ok")], [_RecordingTool("echo", [])])
    call = provider.calls[0]
    assert (call.system, [spec.name for spec in call.tools]) == ("SYS", ["echo"])


# --- AC2: one tool call ------------------------------------------------------


def test_tool_is_executed_with_model_input() -> None:  # F1-AC2
    log: list[tuple[str, dict[str, Any]]] = []
    _run(
        [tool_response(tool_use("tu_1", "echo", {"x": 1})), text_response("ok")],
        [_RecordingTool("echo", log)],
    )
    assert log == [("echo", {"x": 1})]


def test_tool_result_carries_matching_tool_use_id() -> None:  # F1-AC2
    _, provider = _run(
        [tool_response(tool_use("tu_1", "echo")), text_response("ok")],
        [_RecordingTool("echo", [])],
    )
    assert _results_sent_in_call(provider, 1) == [
        ToolResultBlock(tool_use_id="tu_1", content="echo ok")
    ]


def test_loop_continues_after_tool_result_until_final_answer() -> None:  # F1-AC2
    result, provider = _run(
        [tool_response(tool_use("tu_1", "echo")), text_response("finished")],
        [_RecordingTool("echo", [])],
    )
    assert (result.text, result.stop_reason, result.steps) == ("finished", "end_turn", 2)
    assert len(provider.calls) == 2


def test_assistant_turn_is_kept_in_history() -> None:  # F1-AC2
    script = [tool_response(tool_use("tu_1", "echo"), text="looking"), text_response("ok")]
    _, provider = _run(script, [_RecordingTool("echo", [])])
    expected = Message(role="assistant", content=list(script[0].content))
    assert provider.calls[1].messages[1] == expected


def test_result_messages_hold_the_full_transcript() -> None:
    result, _ = _run(
        [tool_response(tool_use("tu_1", "echo")), text_response("ok")],
        [_RecordingTool("echo", [])],
    )
    assert [m.role for m in result.messages] == ["user", "assistant", "user", "assistant"]


# --- AC3: several tool calls in one turn ------------------------------------


def test_multiple_tool_calls_execute_in_order() -> None:  # F1-AC3
    log: list[tuple[str, dict[str, Any]]] = []
    _run(
        [
            tool_response(tool_use("tu_1", "b", {"n": 1}), tool_use("tu_2", "a", {"n": 2})),
            text_response("ok"),
        ],
        [_RecordingTool("a", log), _RecordingTool("b", log)],
    )
    assert log == [("b", {"n": 1}), ("a", {"n": 2})]


def test_all_tool_results_sent_in_one_user_message() -> None:  # F1-AC3
    _, provider = _run(
        [
            tool_response(tool_use("tu_1", "echo"), tool_use("tu_2", "echo")),
            text_response("ok"),
        ],
        [_RecordingTool("echo", [])],
    )
    assert len(provider.calls[1].messages) == 3
    assert [r.tool_use_id for r in _results_sent_in_call(provider, 1)] == ["tu_1", "tu_2"]


# --- AC4: errors become error tool_results ----------------------------------


def test_unknown_tool_becomes_error_result() -> None:  # F1-AC4
    result, provider = _run([tool_response(tool_use("tu_1", "nope")), text_response("ok")])
    assert _results_sent_in_call(provider, 1) == [
        ToolResultBlock(tool_use_id="tu_1", content="Unknown tool: nope", is_error=True)
    ]
    assert result.stop_reason == "end_turn"


def test_tool_exception_becomes_error_result() -> None:  # F1-AC4 (AD6)
    result, provider = _run(
        [tool_response(tool_use("tu_1", "explode")), text_response("ok")], [_ExplodingTool()]
    )
    assert _results_sent_in_call(provider, 1) == [
        ToolResultBlock(tool_use_id="tu_1", content="RuntimeError: boom", is_error=True)
    ]
    assert result.stop_reason == "end_turn"


def test_invalid_tool_input_becomes_error_result(tmp_path: Path) -> None:  # F1-AC4 (D3)
    _, provider = _run(
        [tool_response(tool_use("tu_1", "read_file", {})), text_response("ok")],
        [ReadFileTool(tmp_path)],
    )
    [result] = _results_sent_in_call(provider, 1)
    assert result.is_error
    assert "Invalid input for read_file" in result.content


def test_failed_tool_does_not_stop_later_tools_in_same_turn() -> None:  # F1-AC4
    log: list[tuple[str, dict[str, Any]]] = []
    _run(
        [
            tool_response(tool_use("tu_1", "explode"), tool_use("tu_2", "echo")),
            text_response("ok"),
        ],
        [_ExplodingTool(), _RecordingTool("echo", log)],
    )
    assert log == [("echo", {})]


def test_provider_error_propagates() -> None:  # AD6 contrast: provider errors are fatal
    loop = AgentLoop(_FailingProvider(), ToolRegistry([]), system="SYS")
    with pytest.raises(ConnectionError):
        loop.run("the goal")


# --- AC5: step limit ---------------------------------------------------------


def test_stops_after_max_steps() -> None:  # F1-AC5
    script = [tool_response(tool_use(f"tu_{i}", "echo")) for i in range(5)]
    result, provider = _run(script, [_RecordingTool("echo", [])], max_steps=3)
    assert (result.stop_reason, result.steps) == ("max_steps", 3)
    assert len(provider.calls) == 3


def test_max_steps_result_keeps_last_text() -> None:  # F1-AC5
    script = [tool_response(tool_use("tu_1", "echo"), text="still working")]
    result, _ = _run(script, [_RecordingTool("echo", [])], max_steps=1)
    assert result.text == "still working"


def test_default_max_steps_is_20() -> None:  # F1-AC5
    provider = FakeProvider([tool_response(tool_use(f"tu_{i}", "echo")) for i in range(25)])
    result = AgentLoop(provider, ToolRegistry([_RecordingTool("echo", [])]), system="S").run("g")
    assert (result.stop_reason, len(provider.calls)) == ("max_steps", 20)


def test_max_steps_below_one_is_rejected() -> None:
    with pytest.raises(ValueError, match="max_steps"):
        AgentLoop(FakeProvider([]), ToolRegistry([]), system="S", max_steps=0)


# --- Events (D6) -------------------------------------------------------------


def test_events_report_text_and_tool_calls_in_order() -> None:
    events: list[Event] = []
    _run(
        [
            tool_response(tool_use("tu_1", "echo", {"x": 1}), text="let me look"),
            text_response("done"),
        ],
        [_RecordingTool("echo", [])],
        on_event=events,
    )
    assert events == [
        AssistantText(text="let me look"),
        ToolCallStarted(tool_use_id="tu_1", name="echo", input={"x": 1}),
        ToolCallFinished(tool_use_id="tu_1", name="echo", output=ToolOutput(content="echo ok")),
        AssistantText(text="done"),
    ]


def test_blank_text_is_not_reported_as_an_event() -> None:
    events: list[Event] = []
    _run([text_response("  ")], on_event=events)
    assert events == []
