# CLAUDE.md

Guidance for Claude Code when working in this repository.

## Project context

MiniClaude is a minimal, single-process, synchronous coding agent for the terminal. A ReAct loop sends messages and tool schemas to an LLM, runs the requested tools behind a permission policy, and repeats until the model answers or hits a step limit. It is a learning project: HW4 is the first milestone and it grows into Project 3 (see the Roadmap in `README.md`).

Requirements, acceptance criteria and architecture decisions are imported below. Read them before designing any feature:

@docs/PRD.md
@docs/architecture.md

**Current state:** F1 has landed: `cli.py` (`miniclaude run`), `loop.py`, `events.py`, `prompt.py`, `llm/` (types, `AnthropicProvider`, `FakeProvider`) and `tools/` (registry, workspace confinement, the four built-in tools). See `docs/plans/f1-agent-loop.md`, including its "Deviations from the plan" section. F2 has landed: `permissions/` (`rules.py`, `policy.py`, `approval.py`), gating in `AgentLoop`, and the CLI's y/n `terminal_approver`, with rules loaded from `<workspace>/.miniclaude/settings.json` (an empty, all-`ASK` policy if absent). See `docs/plans/f2-permission-policy.md`. Next: Project 3 (F3+). When a planned module lands, update this line.

## Tech stack

| Area | Choice |
|---|---|
| Language | Python 3.12+ (`.python-version` pins 3.13 locally) |
| Packaging / env | uv (`pyproject.toml` + `uv.lock`), hatchling build, src layout |
| LLM | `anthropic` SDK, behind our own `LLMProvider` Protocol |
| Data models | pydantic v2 |
| Config | `python-dotenv` (`.env`, never committed) |
| Tests | pytest, pytest-cov |
| Quality | ruff (lint + format), mypy `--strict` |

## Commands

```bash
uv sync                                   # install deps (incl. dev group)
uv run pytest                             # full offline suite (live tests auto-skip without a key)
uv run pytest tests/test_cli.py::test_version_flag_prints_version   # single test
uv run pytest --cov=miniclaude --cov-report=term-missing
uv run ruff check . && uv run ruff format .
uv run mypy src tests
uv run miniclaude --version
```

**Done means:** pytest green, `ruff check` clean, `ruff format --check` clean, `mypy --strict` clean. Coverage target is ≥ 90% on `permissions/` and `loop.py`.

## Architecture decisions (summary; full rationale in docs/architecture.md)

Flow: `cli.py` → `AgentLoop` (`loop.py`) → `LLMProvider` / `ToolRegistry` / `PermissionPolicy` / injected `Approver` → `Tool.run()`.

- **AD1 Single process, synchronous.** No asyncio, no daemon, no threads.
- **AD2/AD3 Provider boundary.** `LLMProvider` is a Protocol. `AnthropicProvider` converts SDK objects to and from our pydantic types in `llm/types.py`. The loop never sees raw SDK dicts. Tests use the scripted `FakeProvider`.
- **AD4 Pure permission logic.** `PermissionPolicy.decide()` does no I/O and returns `ALLOW` / `DENY` / `ASK`. Approval is a separate callback supplied by the CLI.
- **AD5 Precedence.** deny > ask > allow > default `ASK`. A chained bash command (`&&`, `;`, `|`, `||`) is `ALLOW` only if every part is allowed. Rule syntax and matching semantics are in PRD §F2.
- **AD6 Errors.** Tool errors, unknown tools and permission denials become `tool_result(is_error=True)` and never raise out of the loop. Provider/network errors propagate. Bad rules raise `InvalidRuleError` at startup.
- **AD7 Workspace confinement.** File tools always refuse paths outside the workspace root, independent of the permission policy.

## Coding conventions

- Every function and method is fully type-annotated. Code must pass `mypy --strict` with no `# type: ignore` unless it has a comment explaining why.
- Start each module with `from __future__ import annotations` and a one-line module docstring.
- Public functions and classes get a one-line docstring saying *what* they do. Use comments only for a non-obvious *why*.
- Use `typing.Protocol` for interfaces (`LLMProvider`, `Tool`, `Approver`) and pydantic models for data that crosses a boundary (messages, tool inputs, config). Use plain `@dataclass(frozen=True)` for small internal values such as a parsed `Rule`.
- Use `enum.Enum` for closed sets (`Decision.ALLOW`), not string literals.
- Use `pathlib.Path`, not `os.path`. Resolve paths before comparing them.
- No module-level mutable state and no singletons. Dependencies are passed into constructors so tests can inject fakes.
- Names: `snake_case` for functions and modules, `PascalCase` for classes, `UPPER_CASE` for constants. A tool's `name` is `snake_case` and matches its module (`tools/builtin/read_file.py` → `read_file`).
- Line length is 100. Let `ruff format` decide layout; don't hand-format.

## Testing strategy

- **Offline by default.** Unit tests never touch the network. The loop is tested with `FakeProvider` (scripted responses). File tools use pytest's `tmp_path`, and `bash` tests run harmless commands (`echo`, `false`) with a short timeout.
- **Live tests.** Anything that calls the real Anthropic API is marked `@pytest.mark.live`. `tests/conftest.py` skips these unless `ANTHROPIC_API_KEY` is set.
- **Layout.** `tests/` mirrors `src/miniclaude/` (`permissions/policy.py` → `tests/permissions/test_policy.py`). Test names describe behavior: `test_deny_rule_beats_allow_rule`.
- **One behavior per test.** Prefer several small tests or `pytest.mark.parametrize` over one test with many asserts. Each PRD acceptance criterion maps to at least one test, named or commented with its ID (for example `# F2-AC3`).
- **TDD for F2 (permission policy).** Strict red → green → refactor, one acceptance criterion at a time:
  1. **Red:** write the failing test(s) only, run them, confirm they fail for the right reason, then commit with `test(permissions): red - <criterion>`.
  2. **Green:** write the minimum code to pass, run the full suite, then commit with `feat(permissions): green - <criterion>`.
  3. **Refactor:** clean up with all tests still green, then commit with `refactor(permissions): <what>` (skip if there is nothing to clean up).
- **Explore → Plan → Implement → Commit for F1 (agent loop + tools).** Explore read-only: find files and search content with the Glob/Grep tools when the session has them, otherwise with `rg`/`find`/`grep` through Bash (Claude Code v2.1.330 exposes no Glob/Grep tools), and inspect files with Read. Write no code during Explore. Plan in Plan mode and save the approved plan to `docs/plans/<feature>.md`. Implement in small steps with tests alongside. Use at least three focused commits (`feat(tools): ...`, `feat(loop): ...`, `feat(cli): ...`).

## Do's

- Do read `docs/PRD.md` and `docs/architecture.md` before proposing a design, and cite the AC or AD you are satisfying.
- Do run the full "done" check (tests, ruff, mypy) before proposing a commit.
- Do show the staged diff summary and the proposed commit message, then **wait for explicit approval before every commit**. Approval for one commit does not cover the next.
- Do use Conventional Commit prefixes: `feat`, `fix`, `test`, `refactor`, `docs`, `chore`.
- Do update this file when a decision, command or convention changes, and update "Current state" when modules land.
- Do keep HW4 artifacts in `docs/hw4/` (session logs, reflection) and plans in `docs/plans/`.

## Don'ts

- Don't write implementation code for F2 before its failing test is committed.
- Don't call the real API in unit tests, and don't add network-dependent tests without the `live` marker.
- Don't read, print or edit `.env` (denied in `.claude/settings.json`). Use `.env.example` as the reference.
- Don't `git push`, force-push, rewrite published history or amend an approved commit.
- Don't add dependencies (`uv add`) without asking first.
- Don't add asyncio, threads, a daemon or a TUI. These are out of scope (PRD §3).
- Don't use `shell=True` anywhere except inside the `bash` tool, which must always set a timeout.

## Context management

- Run `/clear` between features (after F1 lands, before starting F2) so stale exploration doesn't steer new work. This file and the imported docs reload automatically.
- Run `/compact` mid-feature when the conversation gets long, with a focus hint, for example `/compact keep the F2 acceptance-criteria checklist and current red/green state`.
- Use `claude --continue` to resume yesterday's session for the same feature instead of re-explaining.
- Durable decisions belong in this file or `docs/`, not only in chat history.
