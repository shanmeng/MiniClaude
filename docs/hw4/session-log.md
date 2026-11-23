# HW4 Annotated Session Log

Each row links a step of the workflow to its evidence: a screenshot in
[`screenshots/`](screenshots/) and, where there is one, the commit it produced. Annotations say what
the step shows and why it matters for the assignment.

## Part 1: Project setup and context

| Step | Evidence | Commit | Annotation |
|---|---|---|---|
| Scaffold | — | `0b31423` | uv, src layout, pytest/ruff/mypy configured before any feature code. |
| `/init` | 01-init-output, 02-init-steps | `97a1cdd` | Raw output kept in [`init-output.md`](init-output.md) as the baseline. |
| Iterate CLAUDE.md | — | `b51346e` | Added tech stack, AD summary, conventions, testing strategy, do's/don'ts and the `@docs/PRD.md` / `@docs/architecture.md` imports. |
| Live-test marker | — | `07b1391` | `@pytest.mark.live` tests skip without `ANTHROPIC_API_KEY`, so the default suite stays offline. |
| `/clear` before Explore | 03-clear | — | Fresh context so `/init` chatter does not steer exploration. |
| Permission review | 04a-cli-start, 04b-settings-review, 04c-settings-fix, 04d-cli-no-warning | `508e8c0` | The CLI flagged `Write(./.env)` as never matching; fixed to `Edit(./.env)` and kept `.env.example` readable. |
| No Glob/Grep tools | 04e-no-glob-grep | `e35b554` | Claude Code v2.1.330 exposes no Glob/Grep; CLAUDE.md now says to search with `rg`/`find` through Bash. |

## Part 2: F1 agent loop (Explore → Plan → Implement → Commit)

| Step | Evidence | Commit | Annotation |
|---|---|---|---|
| Explore (read-only) | 04-explore-summary, 04-explore-questions | — | No code written; questions surfaced before planning. |
| Plan mode | 05a-plan-mode-start, 05b-plan-review-1/2/3, 05c-plan-revised | `1d53993` | Plan reviewed and revised, then saved to [`docs/plans/f1-agent-loop.md`](../plans/f1-agent-loop.md). |
| Commit approval | 06-commit-0-1/2/3, 06-commit-0-4-confirm, 06-commit-0-5-done | — | Shows the CLAUDE.md rule in action: staged diff and message first, commit only after "yes". |
| Tools | 06-commit-1-1 | `0b93f12` | Tool protocol, registry, workspace confinement (AD7), four built-in tools. |
| Loop | 06-commit-2-1 | `e456e14` | `AgentLoop` tested with the scripted `FakeProvider`; tool errors become error results (AD6). |
| Provider | 06-commit-3-1-thinking-question, 06-commit-3-2-decisions, 06-commit-3-3-staged | `0d97e9c` | Three plan gaps found during implementation; options shown, I chose; recorded under "Deviations from the plan". |
| CLI | 06-commit-4-1, 06-commit-4-2-done | `15ab2a4` | `miniclaude run`. 06-commit-4-1 also shows idle autocompaction. |
| Live smoke test | 07-live-1-smoke | `b3f484a` | One real API round trip through `AnthropicProvider`. |
| Live demo | 07-live-2-demo | `b3f484a` | The model guessed a wrong path, got an error result and recovered. |

## Part 3: F2 permission policy (strict TDD)

| Step | Evidence | Commits (red → green) | Annotation |
|---|---|---|---|
| `/clear` between features | 08-clear-1-before, 08-clear-2-after | — | CLAUDE.md asks for this so F1 exploration does not steer F2. |
| Plan | 09-f2-0-plan | — | My review added two security requirements before any code: absolute paths inside the workspace, and `&`/newline/`$(`/redirect handling. |
| AC1 default ASK | 09-f2-ac1-red, 09-f2-ac1-green | `a748253` → `d0a7541` | Red fails with `ModuleNotFoundError`; green is one line. Plan doc added. |
| AC2 bare allow rule | 09-f2-ac2-red, 09-f2-ac2-green | `11da74e` → `c5cf40e` | Rule parsing deliberately not written yet: no test needed it. |
| AC3 bash rules | 09-f2-ac3-red, 09-f2-ac3-green | `13ab231` → `d041d63` | Word-boundary tests (`git difftool` must not match `git diff:*`). |
| Tooling fix | 09-f2-chore-isort | `e5a1125` | `known-first-party` stops imports moving between red and green. |
| AC4 path rules | 09-f2-ac4-red, 09-f2-ac4-green-question | `de648a9` → `217bb0f` | Claude flagged an untested `..` branch in its green; I chose to remove it and test first. |
| AC4 escape (extra) | 09-f2-ac4b-escape-red, 09-f2-ac4b-escape-green | `5dedac9` → `6e856e8` | The new red also exposed `read_file(**)` matching `../secret.txt`. |
| AC5 precedence | 09-f2-ac5-red, 09-f2-ac5-green | `ab3220e` → `55e1c50` | deny > ask > allow, including the absolute-path deny case. |
| AC6 chained bash | 09-f2-ac6-red, 09-f2-ac6-green | `d5606ac` → `db3a089` | A first test passed with no code (prefix rule matched the whole string); rewritten with exact rules. |
| AC6 empty command (extra) | 09-f2-ac6b-empty-red, 09-f2-ac6b-empty-green | `c5dfe20` → `0460a02` | `all([])` was vacuously ALLOW; fixed by a dedicated red/green. |
| AC7 JSON config | 09-f2-ac7-red, 09-f2-ac7-green | `051af11` → `c2ebc99` | String-instead-of-list and invalid-JSON cases added at my request before the red was committed. |
| AC8 loop + CLI | 09-f2-ac8-plan, 09-f2-ac8-red-1/2, 09-f2-ac8-green-1/2 | `8434db1` → `2161b94` | End-to-end test: an absolute path to `.env` is denied with `--workspace .`. |
| Guard test | 09-f2-guard | `52018be` | Passes immediately, so committed as its own `test(loop)` commit, not as a red. |
| F2 done | 09-f2-done | `38e662a` | 279 tests, 100% coverage on `permissions/`, `loop.py`, `cli.py`. |

## Final demo and memory

| Step | Evidence | Commit | Annotation |
|---|---|---|---|
| Ask before write | 10-demo-1-ask-before-write | `38e662a` | Real API, sample repo: `.env` denied by policy, `write_file` asked first and ran after "y". Meets PRD §5. |
| Saved preference | 11-cli-memory-tdd-preference | — | Claude saved the TDD rule ("no defensive code a test doesn't need") to memory for Project 3. |
| `claude --continue` | 12-continue-1-command, 12-continue-2-resumed | — | After `/exit`, `claude --continue` reopened the F2 session with its history intact, ending on the last commit (`38e662a`) and the recap. |
