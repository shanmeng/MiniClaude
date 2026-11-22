# MiniClaude — Product Requirements

## 1. Summary

MiniClaude is a minimal, single-process coding agent that runs in the terminal. The user gives it a goal ("add a `--verbose` flag to cli.py"). It runs a ReAct-style loop: the LLM thinks, calls tools (read, write, list, shell), gets the results back and repeats until it can answer. Every tool call goes through a permission policy first.

It is a learning project. The goal is to understand, by building it, the runtime mechanics behind tools like Claude Code: the agent loop, tool calling, permission gating and context management.

- **HW4 (this milestone):** agent loop + built-in tools + permission policy.
- **Project 3 (later):** sessions/memory, context compaction, skills.

## 2. Users & use cases

| User | Use case |
|---|---|
| Developer at a terminal | `miniclaude run "goal"`: one-shot task in the current repo |
| Developer, interactive | `miniclaude chat`: multi-turn REPL (P3) |
| Cautious developer | Configures allow/deny rules so the agent can read freely but must ask before writing or running shell commands |

## 3. Non-goals

- No daemon / multi-client IPC, no TUI, no web UI.
- No MCP or sub-agents in HW4.
- Not a production security sandbox: the permission policy is a guard against agent mistakes, not against a malicious user.

## 4. Features

### F1. Agent loop + built-in tools (HW4 Part 2: Explore → Plan → Implement → Commit)

The loop sends messages and tool schemas to the LLM. It executes any `tool_use` blocks and appends `tool_result` blocks, then stops when the model returns a plain answer or a step limit is hit.

Acceptance criteria:

1. `AgentLoop.run(goal)` returns the model's final text when the model answers without tools.
2. When the model requests a tool, the loop executes it and sends a `tool_result` with the matching `tool_use_id`, then continues.
3. Multiple tool calls in one model turn are all executed, in order.
4. An unknown tool name or a tool exception becomes an error `tool_result` (`is_error=True`). The loop does not crash.
5. The loop stops after `max_steps` (default 20) and reports that the step limit was reached.
6. Built-in tools: `read_file`, `write_file`, `list_dir` and `bash` (with a timeout). Each declares a JSON schema for its input.
7. File tools refuse paths outside the workspace root.
8. `miniclaude run "<goal>"` wires the loop to the Anthropic provider and prints tool activity and the final answer.
9. Tests use a scripted `FakeProvider`, so no network access or API key is needed.

### F2. Permission policy (HW4 Part 3: strict TDD)

Before any tool runs, `PermissionPolicy.decide(tool_name, tool_input)` returns `ALLOW`, `DENY` or `ASK`.

Rule syntax (string form, as in config files):

| Rule | Matches |
|---|---|
| `read_file` | every call to `read_file` |
| `bash(git status)` | `bash` whose command is exactly `git status` |
| `bash(git diff:*)` | `bash` whose command starts with `git diff` |
| `write_file(src/**)` | `write_file` whose `path` matches the glob `src/**` |

Acceptance criteria:

1. With no rules, every call is `ASK`.
2. A bare tool-name rule in `allow` makes every call to that tool `ALLOW`.
3. `bash(<cmd>)` matches the exact command only. `bash(<prefix>:*)` matches by prefix on a word boundary: `git diff:*` matches `git diff --stat` but not `git difftool`.
4. Path rules (`read_file(...)`, `write_file(...)`, `list_dir(...)`) match the `path` input with glob semantics, where `**` crosses directories. Paths are normalized first, so `src/../.env` is checked as `.env`.
5. `deny` beats `allow` when both match. `ask` beats `allow`.
6. A `bash` command chained with `&&`, `;`, `|` or `||` is `ALLOW` only if every sub-command is allowed. Any denied part makes the whole command `DENY`.
7. The policy loads from a JSON file shaped `{"permissions": {"allow": [], "deny": [], "ask": []}}`. A malformed rule raises `InvalidRuleError` naming the rule.
8. In the loop: `DENY` produces an error `tool_result` without running the tool. `ASK` calls an injected `approver` callback (the CLI prompts y/n).

### F3+. Project 3 backlog (not in HW4)

- Sessions persisted to `.miniclaude/sessions/*.jsonl`, plus `--continue`.
- Context budget tracking and `/compact` summarization.
- A project memory file (`MINICLAUDE.md`) loaded into the system prompt.
- Skills loaded from `.miniclaude/skills/`.

## 5. Success metrics

- `uv run pytest` is green and offline, with ≥ 90% line coverage on `permissions/` and `loop.py`.
- `ruff check` and `mypy --strict` are clean.
- A live demo: MiniClaude completes a small real edit in a sample repo, asking before writing.
