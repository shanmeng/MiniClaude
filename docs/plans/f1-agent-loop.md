# F1 — Agent loop + built-in tools: implementation plan

## Context

PRD F1 is the first feature of HW4. It covers a ReAct loop that sends messages and tool schemas to an LLM, runs the requested tools, feeds `tool_result`s back and stops on a plain answer or at `max_steps`. The plan builds on the 12 design decisions (D1–D12) made in the earlier Explore session. Following CLAUDE.md's F1 workflow (Explore → Plan → Implement → Commit), this plan is saved to `docs/plans/f1-agent-loop.md` and implemented in small commits, each green on pytest + ruff + mypy --strict.

### Explore findings (read-only pass, confirmed)

- **Only the scaffold exists.** `src/miniclaude/` has `__init__.py` (`__version__`), `cli.py` (`build_parser()` + `main(argv)` with `--version` only) and `py.typed`. `tests/` has `conftest.py` (skips `live` tests without `ANTHROPIC_API_KEY`) and `test_cli.py` (2 tests). `docs/plans/` is empty.
- **Locked versions:** anthropic **2.12.0**, pydantic 2.14.4, python-dotenv 1.2.4. Nothing new needs to be added.
- **SDK tool-use shapes (D11), checked in `.venv/.../anthropic/types/`:**
  - Response `Message.content: list[ContentBlock]` is a large union (text, tool_use, thinking, server-tool blocks, …). We convert only `TextBlock(text)` and `ToolUseBlock(id, name, input: Dict[str, object])` and ignore the rest.
  - `StopReason` = `end_turn | max_tokens | stop_sequence | tool_use | pause_turn | refusal | model_context_window_exceeded`.
  - Request: `MessageParam = UserMessageParam | AssistantMessageParam | SystemMessageParam` (2.x adds a `system` role). We still pass the system prompt through the `system=` kwarg of `messages.create`, and our `Message.role` stays `user | assistant`.
  - `ToolResultBlockParam{tool_use_id, type, content: str | ..., is_error}`, `ToolUseBlockParam{id, input, name, type}` and `ToolParam{name, description, input_schema}`. All of them are TypedDicts, so the conversion builds plain dicts that mypy checks against them.

## Design (cites D1–D12 and AD1–AD7)

### `llm/types.py` (AD3): pydantic, mirrors the Anthropic shape (D4)
- `TextBlock(type: Literal["text"], text)`, `ToolUseBlock(type: Literal["tool_use"], id, name, input: dict[str, Any])`, `ToolResultBlock(type: Literal["tool_result"], tool_use_id, content: str, is_error: bool = False)`
- `ContentBlock = Annotated[TextBlock | ToolUseBlock | ToolResultBlock, Field(discriminator="type")]`
- `Message(role: Literal["user", "assistant"], content: list[ContentBlock])`
- `ToolSpec(name, description, input_schema: dict[str, Any])`
- `ModelResponse(content: list[TextBlock | ToolUseBlock], stop_reason: str)`

### `llm/provider.py` (AD2)
- `class LLMProvider(Protocol)`: `complete(*, system: str, messages: Sequence[Message], tools: Sequence[ToolSpec]) -> ModelResponse`.
- `AnthropicProvider(client: anthropic.Anthropic, model: str, max_tokens: int = 4096)` (D10). `complete()` calls `client.messages.create(...)`.
- Pure conversion functions that can be tested offline: `to_message_params()`, `to_tool_params()` and `from_sdk_message()`. The last one drops unknown block types.

### `llm/fake.py` (AD2, AC9)
- `FakeProvider(responses: Sequence[ModelResponse])` replays the responses in order and records a deep copy of each call in `self.calls`, so tests can assert on what was sent. Raises if the script runs out.
- Helper constructors `text_response(text)` and `tool_response(*tool_uses, text=None)` keep tests short.

### `tools/` (D1, D3, D7, D8, D9, AD7)
- `tools/base.py`
  - `ToolOutput(content: str, is_error: bool = False)` (pydantic).
  - `class Tool(Protocol)`: `name`, `description`, `input_schema: dict[str, Any]`, `run(raw_input: Mapping[str, Any]) -> ToolOutput`.
  - `BaseTool[InputT: BaseModel]`: a generic helper class. It derives `input_schema` from `input_model.model_json_schema()`. Its `run()` validates the input, turns a `ValidationError` into `ToolOutput(is_error=True)` (D3), then calls the abstract `execute(params: InputT)`. The loop and registry depend only on the Protocol.
- `tools/workspace.py`
  - `resolve_in_workspace(root, path) -> Path` resolves the path against `root`, then runs `.resolve()` to follow symlinks (D7).
  - It raises `OutsideWorkspaceError(ValueError)` unless `resolved.is_relative_to(root.resolve())`. Absolute paths inside the root are accepted.
- `tools/registry.py`: `ToolRegistry(tools)` raises `ValueError` on a duplicate name. It provides `get(name) -> Tool | None` and `specs() -> list[ToolSpec]`.
- `tools/output.py`: `truncate(text, limit=10_000)` appends `"\n[truncated]"` when it cuts (D8).
- `tools/builtin/`: each tool takes `root: Path` in its constructor and turns expected failures into `is_error=True`.
  - `read_file(path)` reads UTF-8 text and passes the output through `truncate()` so a large file can't flood the context. Not found, is a directory, decode error and outside-root cases are errors.
  - `write_file(path, content)` does a full overwrite and runs `mkdir(parents=True)` (D9). It returns `"Wrote N chars to <path>"`.
  - `list_dir(path=".")` lists entries sorted by name, with directories suffixed `/`. It is not recursive.
  - `bash(command)` uses `subprocess.run(shell=True, cwd=root, stdout=PIPE, stderr=STDOUT, text=True, timeout=self.timeout)`. The default timeout is 30s and can be set in the constructor. Output is truncated. A non-zero exit appends `[exit code: N]` and sets `is_error=True`. A timeout returns `is_error=True` with "timed out after Ns". The docstring notes that the command can still `cd` out of the root and that F2's policy is the guard (D7).
- `tools/builtin/__init__.py`: `default_tools(root, *, bash_timeout=30.0) -> list[Tool]`.

### `events.py` (D6)
- Frozen dataclasses `AssistantText(text)`, `ToolCallStarted(tool_use_id, name, input)` and `ToolCallFinished(tool_use_id, name, output: ToolOutput)`.
- `Event = AssistantText | ToolCallStarted | ToolCallFinished`.

### `loop.py` (AD1, AD6, D2, D4, D5)
- `RunResult(text: str, stop_reason: Literal["end_turn", "max_steps"], steps: int, messages: list[Message])`. Returning the transcript makes tests easier and leaves room for P3 sessions.
- `AgentLoop(provider, registry, *, system: str, max_steps: int = 20, on_event: Callable[[Event], None] = _noop)`. It holds no policy or approver (D2).
- `run(goal)`:
  1. `messages = [user(goal)]`.
  2. Each step makes one `provider.complete` call and appends the assistant message.
  3. Emit `AssistantText` for each text block.
  4. If there are no `tool_use` blocks, return `end_turn` with the joined text.
  5. Otherwise run every `tool_use` in order (AC3) and append **one** user message holding all the `ToolResultBlock`s.
  6. After `max_steps` steps, return `stop_reason="max_steps"` with the text from the last response (AC5).
- `_execute(tool_use)` emits `ToolCallStarted`.
  - Unknown tool → `is_error` with "unknown tool: X".
  - `tool.run()` is wrapped in `except Exception`, which becomes `is_error` with `"{type}: {msg}"` (AC4, AD6).
  - Emits `ToolCallFinished`.
  - Provider exceptions are **not** caught and propagate (AD6).

### `prompt.py` + `cli.py` (D10, AC8)
- `prompt.py`: `SYSTEM_PROMPT` constant, a few lines long: coding agent, workspace-relative paths, be concise.
- `cli.py`:
  - Adds a `run` subcommand with `goal`, `--workspace PATH` (default cwd), `--max-steps N` (default 20). Bare `miniclaude` still prints help.
  - `main()` loads `.env` (`load_dotenv()`), reads `MINICLAUDE_MODEL` (fallback `claude-sonnet-5-5`), exits 2 with a clear message if `ANTHROPIC_API_KEY` is missing, builds `AnthropicProvider`, then calls `run_command(...)`.
  - `run_command(args, provider, out: TextIO) -> int` is separate so it can be tested with `FakeProvider`.
  - `format_event(event) -> str` is a pure function:
    - `→ read_file {"path": ...}`
    - `✓ read_file (123 chars)`, or `✗ bash: [exit code: 1]` (first line)
  - The final answer prints at the end. On `max_steps` the CLI prints "Stopped: step limit (N) reached." and exits 1.
  - `anthropic.APIError` is caught at the CLI only: it prints a one-line error and exits 1. The loop itself still propagates it (AD6).

## Commits (each one green on pytest + ruff check + ruff format --check + mypy --strict; each shown to you for approval first)

0. `docs(plans): add F1 agent loop plan`
   - Copies this plan to `docs/plans/f1-agent-loop.md`.
   - Updates "Planned layout" in `docs/architecture.md` to add `events.py`, `prompt.py`, `tools/workspace.py` and `tools/output.py`.
1. `feat(tools): add Tool protocol, registry, workspace confinement and built-in tools`
   - Adds `llm/types.py` (`ToolSpec` only is used here; the full types file lands now so `registry.specs()` has its type), `tools/base.py`, `workspace.py`, `registry.py`, `output.py`, `builtin/*`.
   - Tests: `tests/tools/test_base.py`, `test_workspace.py`, `test_registry.py`, `builtin/test_{read_file,write_file,list_dir,bash}.py`.
2. `feat(loop): add AgentLoop with FakeProvider and typed events`
   - Adds `llm/provider.py` (Protocol only), `llm/fake.py`, `events.py`, `loop.py`.
   - Tests: `tests/llm/test_fake.py`, `tests/test_loop.py`.
3. `feat(llm): add AnthropicProvider with SDK conversion layer`
   - Adds `AnthropicProvider` and the conversion functions.
   - Tests: `tests/llm/test_provider.py`, which runs offline (it builds SDK `Message` objects with `model_validate`) plus one `@pytest.mark.live` smoke test (D12).
4. `feat(cli): add run subcommand wired to AnthropicProvider`
   - Adds `prompt.py` and the `cli.py` changes.
   - Tests: extended `tests/test_cli.py`.
   - Updates CLAUDE.md "Current state" and the README if needed.

## Acceptance criteria → tests

| AC | Test(s) (each commented `# F1-ACn`) |
|---|---|
| AC1 final text without tools | `test_loop.py::test_returns_final_text_when_model_answers_without_tools`, `::test_end_turn_result_reports_one_step` |
| AC2 tool executed, result has matching id, loop continues | `test_loop.py::test_tool_result_carries_matching_tool_use_id`, `::test_loop_continues_after_tool_result_until_final_answer` |
| AC3 multiple calls in order, single user message | `test_loop.py::test_multiple_tool_calls_execute_in_order`, `::test_all_tool_results_sent_in_one_user_message` |
| AC4 unknown tool / exception / bad input → error result, no crash | `test_loop.py::test_unknown_tool_becomes_error_result`, `::test_tool_exception_becomes_error_result`, `test_base.py::test_invalid_input_becomes_error_output`, plus `test_loop.py::test_provider_error_propagates` (AD6 contrast) |
| AC5 step limit | `test_loop.py::test_stops_after_max_steps`, `::test_default_max_steps_is_20`, `test_cli.py::test_run_reports_step_limit` |
| AC6 four tools + JSON schemas + bash timeout | `test_registry.py::test_specs_export_json_schema_per_tool` (parametrized over the 4), `builtin/test_*` happy/error paths, `test_bash.py::test_timeout_returns_error`, `::test_nonzero_exit_is_error_with_code`, `::test_output_truncated_with_marker`, `test_read_file.py::test_large_file_truncated_with_marker`, `test_write_file.py::test_creates_parent_dirs` |
| AC7 outside-root refused | `test_workspace.py::test_rejects_parent_traversal`, `::test_rejects_absolute_outside`, `::test_rejects_symlink_escaping_root`, and `test_{read,write,list}*.py::test_refuses_path_outside_workspace` (parametrized) |
| AC8 `miniclaude run` wiring + output | `test_cli.py::test_run_prints_tool_activity_and_final_answer` (FakeProvider via `run_command`), `::test_format_event_*`, `::test_run_without_api_key_exits_2`, `test_provider.py::test_live_smoke` (live) |
| AC9 offline with FakeProvider | the whole suite passes with no key. `test_fake.py::test_replays_scripted_responses_in_order`, `::test_records_calls`, `::test_raises_when_script_exhausted` |

Provider conversion tests (`test_provider.py`): text/tool_use round-trip, tool_result with `is_error`, unknown SDK block dropped, `ToolSpec` → `ToolParam`.

## Verification

- After every commit, run `uv run pytest && uv run ruff check . && uv run ruff format --check . && uv run mypy src tests`.
- `uv run pytest --cov=miniclaude --cov-report=term-missing` must show `loop.py` ≥ 90%.
- Manual demo, which needs a key in `.env`: `uv run miniclaude run "list the files in src and summarize cli.py" --workspace .` should show `→`/`✓` tool lines and a final answer. `uv run pytest -m live` runs the smoke test.

## Out of scope for F1

- Permission policy / approver (F2-AC8).
- `chat` REPL, sessions, compaction (P3).
