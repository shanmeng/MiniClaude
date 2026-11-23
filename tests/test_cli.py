"""Tests for the CLI: argument parsing, wiring, event output and stop messages (no network)."""

from __future__ import annotations

import io
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import anthropic
import httpx2
import pytest

from miniclaude import __version__, cli
from miniclaude.cli import (
    build_parser,
    describe_api_error,
    describe_stop,
    format_event,
    main,
    run_command,
)
from miniclaude.events import AssistantText, ToolCallFinished, ToolCallStarted
from miniclaude.llm.fake import FakeProvider, text_response, tool_response, tool_use
from miniclaude.llm.types import Message, ModelResponse, TextBlock, ToolSpec
from miniclaude.loop import RunResult
from miniclaude.tools.base import ToolOutput

_ENV_VARS = ("ANTHROPIC_API_KEY", "MINICLAUDE_MODEL")


@pytest.fixture
def clean_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[Path]:
    """Run in an empty cwd with no API key or model in the environment; restore both after."""
    for name in _ENV_VARS:
        # setenv first so monkeypatch records the original value and restores it afterwards,
        # even if load_dotenv() sets the variable during the test.
        monkeypatch.setenv(name, "placeholder")
        monkeypatch.delenv(name)
    monkeypatch.chdir(tmp_path)
    yield tmp_path


def _run(
    provider: FakeProvider | Any, workspace: Path, max_steps: int = 20
) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    code = run_command(
        "the goal", provider, workspace=workspace, max_steps=max_steps, out=out, err=err
    )
    return code, out.getvalue(), err.getvalue()


# --- argument parsing --------------------------------------------------------


def test_version_flag_prints_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_no_args_prints_help_and_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([]) == 0
    assert "usage: miniclaude" in capsys.readouterr().out


def test_run_parses_goal_workspace_and_max_steps(tmp_path: Path) -> None:
    args = build_parser().parse_args(
        ["run", "fix it", "--workspace", str(tmp_path), "--max-steps", "5"]
    )
    assert (args.goal, args.workspace, args.max_steps) == ("fix it", tmp_path, 5)


def test_run_max_steps_defaults_to_20() -> None:  # F1-AC5
    assert build_parser().parse_args(["run", "goal"]).max_steps == 20


@pytest.mark.parametrize("value", ["0", "-3", "many"])
def test_run_rejects_invalid_max_steps(value: str) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["run", "goal", "--max-steps", value])
    assert exc.value.code == 2


# --- main(): environment and wiring (F1-AC8) ---------------------------------


def test_run_without_api_key_exits_2(
    clean_env: Path, capsys: pytest.CaptureFixture[str]
) -> None:  # F1-AC8
    assert main(["run", "goal"]) == 2
    assert "ANTHROPIC_API_KEY" in capsys.readouterr().err


def test_run_with_missing_workspace_exits_2(
    clean_env: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["run", "goal", "--workspace", str(clean_env / "nope")]) == 2
    assert "not a directory" in capsys.readouterr().err


class _ProviderSpy:
    """Stands in for AnthropicProvider: records the model and replays a scripted answer."""

    models: list[str] = []

    def __init__(self, client: anthropic.Anthropic, model: str) -> None:
        _ProviderSpy.models.append(model)
        self._fake = FakeProvider([text_response("All done.")])

    def complete(
        self, *, system: str, messages: list[Message], tools: list[ToolSpec]
    ) -> ModelResponse:
        return self._fake.complete(system=system, messages=messages, tools=tools)


@pytest.fixture
def provider_spy(monkeypatch: pytest.MonkeyPatch) -> type[_ProviderSpy]:
    _ProviderSpy.models = []
    monkeypatch.setattr(cli, "AnthropicProvider", _ProviderSpy)
    return _ProviderSpy


def test_run_uses_default_model(
    clean_env: Path, monkeypatch: pytest.MonkeyPatch, provider_spy: type[_ProviderSpy]
) -> None:  # F1-AC8
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    assert main(["run", "goal"]) == 0
    assert provider_spy.models == ["claude-sonnet-5-5"]


def test_run_reads_key_and_model_from_dotenv_in_cwd(
    clean_env: Path, provider_spy: type[_ProviderSpy]
) -> None:  # D10
    (clean_env / ".env").write_text(
        "ANTHROPIC_API_KEY=from-dotenv\nMINICLAUDE_MODEL=claude-test-model\n", encoding="utf-8"
    )
    assert main(["run", "goal"]) == 0
    assert provider_spy.models == ["claude-test-model"]


def test_main_prints_final_answer(
    clean_env: Path,
    monkeypatch: pytest.MonkeyPatch,
    provider_spy: type[_ProviderSpy],
    capsys: pytest.CaptureFixture[str],
) -> None:  # F1-AC8
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    main(["run", "goal", "--workspace", str(clean_env)])
    assert capsys.readouterr().out == "All done.\n"


# --- run_command(): output and stop messages ---------------------------------


def test_run_prints_tool_activity_and_final_answer(tmp_path: Path) -> None:  # F1-AC8
    (tmp_path / "a.txt").touch()
    provider = FakeProvider(
        [
            tool_response(tool_use("tu_1", "list_dir", {"path": "."}), text="Looking."),
            text_response("Done."),
        ]
    )
    code, out, err = _run(provider, tmp_path)
    assert out.splitlines() == [
        "Looking.",
        '→ list_dir {"path": "."}',
        "✓ list_dir (5 chars)",
        "Done.",
    ]
    assert (code, err) == (0, "")


def test_run_prints_tool_errors(tmp_path: Path) -> None:
    provider = FakeProvider(
        [tool_response(tool_use("tu_1", "read_file", {"path": "nope.txt"})), text_response("Ok.")]
    )
    _, out, _ = _run(provider, tmp_path)
    assert "✗ read_file: File not found: nope.txt" in out.splitlines()


def test_run_reports_step_limit(tmp_path: Path) -> None:  # F1-AC5
    provider = FakeProvider([tool_response(tool_use("tu_1", "list_dir"))])
    code, _, err = _run(provider, tmp_path, max_steps=1)
    assert code == 1
    assert "step limit (1) reached" in err


def test_run_reports_refusal(tmp_path: Path) -> None:
    provider = FakeProvider([ModelResponse(content=[], stop_reason="refusal")])
    code, _, err = _run(provider, tmp_path)
    assert code == 1
    assert "declined" in err


def test_run_reports_max_tokens(tmp_path: Path) -> None:
    provider = FakeProvider(
        [ModelResponse(content=[TextBlock(text="I'll wr")], stop_reason="max_tokens")]
    )
    code, _, err = _run(provider, tmp_path)
    assert code == 1
    assert "output token limit" in err


class _FailingProvider:
    def __init__(self, exc: anthropic.APIError) -> None:
        self._exc = exc

    def complete(
        self, *, system: str, messages: list[Message], tools: list[ToolSpec]
    ) -> ModelResponse:
        raise self._exc


_REQUEST = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")


def test_run_api_error_exits_1_with_message(tmp_path: Path) -> None:  # AD6
    code, _, err = _run(_FailingProvider(anthropic.APIConnectionError(request=_REQUEST)), tmp_path)
    assert code == 1
    assert err.startswith("error: could not reach the Anthropic API")


def _status_error(cls: type[anthropic.APIStatusError], status: int) -> anthropic.APIStatusError:
    response = httpx2.Response(status, request=_REQUEST)
    return cls("boom", response=response, body=None)


@pytest.mark.parametrize(
    ("exc", "expected"),
    [
        (_status_error(anthropic.AuthenticationError, 401), "rejected the API key"),
        (_status_error(anthropic.RateLimitError, 429), "rate limited"),
        (_status_error(anthropic.InternalServerError, 500), "Anthropic API error 500: boom"),
        (anthropic.APIConnectionError(request=_REQUEST), "could not reach"),
        (anthropic.APIError("odd response", request=_REQUEST, body=None), "odd response"),
    ],
)
def test_describe_api_error(exc: anthropic.APIError, expected: str) -> None:
    assert expected in describe_api_error(exc)


def test_describe_stop_is_none_on_end_turn() -> None:
    result = RunResult(text="done", stop_reason="end_turn", steps=1, messages=[])
    assert describe_stop(result, max_steps=20) is None


# --- format_event() ----------------------------------------------------------


def test_format_event_assistant_text_is_printed_as_is() -> None:  # F1-AC8
    assert format_event(AssistantText(text="Hello\nworld")) == "Hello\nworld"


def test_format_event_tool_started_shows_name_and_input() -> None:  # F1-AC8
    event = ToolCallStarted(tool_use_id="tu_1", name="read_file", input={"path": "a.py"})
    assert format_event(event) == '→ read_file {"path": "a.py"}'


def test_format_event_long_input_is_shortened() -> None:
    event = ToolCallStarted(tool_use_id="tu_1", name="write_file", input={"content": "x" * 500})
    line = format_event(event)
    assert len(line) < 140
    assert line.endswith("…")


def test_format_event_tool_success_shows_size() -> None:  # F1-AC8
    event = ToolCallFinished(tool_use_id="tu_1", name="bash", output=ToolOutput(content="hello\n"))
    assert format_event(event) == "✓ bash (6 chars)"


def test_format_event_tool_error_shows_last_line() -> None:  # F1-AC8
    output = ToolOutput(content="some output\n[exit code: 1]", is_error=True)
    event = ToolCallFinished(tool_use_id="tu_1", name="bash", output=output)
    assert format_event(event) == "✗ bash: [exit code: 1]"
