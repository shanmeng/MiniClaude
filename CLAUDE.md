# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

MiniClaude: a minimal, single-process, synchronous coding agent (Python 3.12, uv). A ReAct loop sends messages and tool schemas to an LLM, runs the requested tools behind a permission policy, and repeats until the model answers or hits a step limit. It is a learning project (HW4, growing into Project 3). Requirements and acceptance criteria are in `docs/PRD.md`. Data flow, planned module layout and architecture decisions (AD1–AD7) are in `docs/architecture.md`. Read both before designing a feature.

Current state: only the scaffold exists (`src/miniclaude/cli.py` with `--version`). Everything else in the architecture doc is planned, not yet written.

## Commands

```bash
uv sync                                   # install deps (incl. dev group)
uv run pytest                             # full offline suite
uv run pytest tests/test_cli.py::test_version_flag_prints_version   # single test
uv run pytest -m "not live"               # exclude tests that hit the real API
uv run pytest --cov=miniclaude --cov-report=term-missing
uv run ruff check . && uv run ruff format .
uv run mypy src tests                     # strict mode
uv run miniclaude --version
```

Done means: pytest green, `ruff check` clean, `mypy --strict` clean. Target coverage is at least 90% on `permissions/` and `loop.py`.

## Architecture (planned, see docs/architecture.md)

`cli.py` builds and wires everything → `AgentLoop` (`loop.py`) → `LLMProvider` / `ToolRegistry` / `PermissionPolicy` / injected `Approver` → `Tool.run()`.

Rules from the architecture decisions:

- **Provider boundary:** `LLMProvider` is a Protocol. `AnthropicProvider` converts SDK objects to and from our own pydantic types in `llm/types.py`. The loop never handles raw SDK dicts. Tests use a scripted `FakeProvider` and never touch the network. Real-API tests must be marked `@pytest.mark.live`. Nothing skips them automatically yet, so add a skip when `ANTHROPIC_API_KEY` is unset.
- **Errors:** tool errors, unknown tools and permission denials become `tool_result(is_error=True)` and never raise out of the loop. Provider/network errors do propagate. Bad permission rules raise `InvalidRuleError` at startup.
- **Permissions:** `PermissionPolicy.decide()` is pure (no I/O) and returns ALLOW / DENY / ASK. Approval is a separate callback that the CLI supplies. Precedence: deny > ask > allow > default ASK. Chained bash commands (`&&`, `;`, `|`, `||`) are ALLOW only if every part is allowed. Rule syntax and the exact matching semantics (prefix `:*` on a word boundary, `**` globs, path normalization) are in PRD §F2.
- **Workspace confinement:** file tools always refuse paths outside the workspace root, independent of the permission policy (defense in depth).

## Workflow conventions

- Permission policy (PRD F2) is built with strict red-green-refactor TDD: a failing test first, committed separately from the code that makes it pass. The commit history is graded.
- The agent loop and tools (PRD F1) follow Explore → Plan → Implement → Commit. Plans go in `docs/plans/`. HW4 reflection and session logs go in `docs/hw4/`.
- Show the diff and proposed commit message and wait for approval before every commit. Never push (`git push` is denied in `.claude/settings.json`).
- `.env` holds `ANTHROPIC_API_KEY` and `MINICLAUDE_MODEL`. Claude Code is denied access to it, so use `.env.example` for reference.
- All code is written from scratch. The design was informed by KamaClaude (MIT), so don't copy code from it. Keep the acknowledgment in the README.
