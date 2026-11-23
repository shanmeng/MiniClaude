# MiniClaude — Architecture

## Data flow

```
user goal
  → cli.py                (argparse; builds everything, prints events)
  → AgentLoop             (loop.py: messages ↔ provider, tool dispatch, step limit)
      → LLMProvider       (llm/: Protocol; AnthropicProvider for real, FakeProvider for tests)
      → ToolRegistry      (tools/registry.py: name → Tool, exports JSON schemas)
      → PermissionPolicy  (permissions/policy.py: ALLOW / DENY / ASK)
      → Approver          (permissions/approval.py: callback; CLI prompts y/n on ASK)
      → Tool.run(input)   (tools/builtin/*.py)
  → final answer
```

## Planned layout

```
src/miniclaude/
  cli.py                  # entry point: `miniclaude run|chat`
  loop.py                 # AgentLoop, RunResult
  events.py               # typed loop events (AssistantText, ToolCallStarted, ToolCallFinished)
  prompt.py               # SYSTEM_PROMPT constant
  llm/
    types.py              # Message, Text/ToolUse/ToolResult/OpaqueBlock, ToolSpec, ModelResponse
    provider.py           # LLMProvider Protocol + AnthropicProvider
    fake.py               # FakeProvider: replays scripted responses (tests)
  tools/
    base.py               # Tool Protocol, ToolOutput, BaseTool (pydantic input validation)
    registry.py           # ToolRegistry
    workspace.py          # resolve_in_workspace(): workspace-root confinement (AD7)
    output.py             # truncate(): caps tool output with a "[truncated]" marker
    builtin/              # read_file, write_file, list_dir, bash
  permissions/
    rules.py              # Rule parsing: "bash(git diff:*)" → Rule
    policy.py             # PermissionPolicy.decide(), PermissionPolicy.from_file()
    approval.py           # Approver Protocol: the injected y/n callback for ASK
tests/                    # mirrors src/; pure unit tests, no network
```

## Architecture decisions

| # | Decision | Why | Trade-off |
|---|---|---|---|
| AD1 | **Single process, synchronous.** No daemon, no asyncio. | Smallest thing that teaches the agent loop. Easy to test and debug. | Can't stream to multiple clients. Revisit in P3 if needed. |
| AD2 | **`LLMProvider` is a Protocol with a `FakeProvider`.** | The loop is tested deterministically and offline. The real API is only touched in `@pytest.mark.live` tests. | The fake can drift from real API behavior. Mitigated by keeping our own `types.py` and converting at the provider boundary. |
| AD3 | **Our own pydantic message types**, not raw SDK dicts, inside the loop. | Decouples the loop from the SDK and gives typed, validated data. | A small conversion layer in `AnthropicProvider`. |
| AD4 | **Permission policy is pure logic** (no I/O in `decide()`). Approval is a separate injected callback. | Pure functions are ideal for strict TDD. UI concerns stay in the CLI. | Two objects instead of one. |
| AD5 | **Precedence deny > ask > allow > default ASK.** | Fail safe: an explicit deny can never be overridden by a broad allow. | Users must write narrower denies when they want exceptions. |
| AD6 | **Tool errors become `tool_result(is_error=True)`, never exceptions out of the loop.** | The model can see the failure and recover, as real agents do. | Bugs in tools can be masked. Mitigated by logging. |
| AD7 | **Workspace root confinement** in the file tools, separate from the permission policy. | Defense in depth. Path rules are user config, but the root check is always on. | Slight duplication of path logic. |

## Error handling

- Provider/network errors propagate out of `AgentLoop.run` (fatal for the run).
- Tool and permission errors become error `tool_result`s (recoverable by the model).
- Config errors (`InvalidRuleError`) fail fast at startup.
