# HW4 Reflection: Building MiniClaude with Claude Code

## What I built

MiniClaude is a single-process coding agent for the terminal: a ReAct loop that sends messages and
tool schemas to the Anthropic API, runs the requested tools (`read_file`, `write_file`, `list_dir`,
`bash`) and gates every call through a permission policy. Before this write-up the repo had 35 commits, 279 offline
tests plus one live test, `ruff` and `mypy --strict` clean, and 100% line coverage on
`permissions/`, `loop.py` and `cli.py`. A live run against the real API in a sample repo
(screenshot 10) read `greet.py` freely, was blocked by policy from reading `.env`, and asked
`Allow write_file …? [y/N]` before editing the file.

## Part 1: CLAUDE.md as a contract, not a description

The `/init` output (`docs/hw4/init-output.md`) described the repo. What made it useful was turning
it into rules Claude could be held to: a "Done means" line (pytest, ruff, format, mypy), "wait for
explicit approval before every commit", a commit-message format for red/green/refactor, and
`@docs/PRD.md` / `@docs/architecture.md` imports so every session starts from the acceptance
criteria and the architecture decisions. Because of that, every commit in this repo was shown to me
as a staged diff plus a proposed message before it happened (screenshot 06-commit-0-4-confirm).

The permission config had to be iterated too. My first deny rule, `Read(./.env.*)`, would also have
blocked `.env.example`; and the CLI's startup check flagged that `Write(./.env)` never matches
(it has to be `Edit(./.env)`, screenshots 04b–04d). The lesson: permission rules are code and need
the same review as code. One limitation I documented instead of hiding: Claude Code v2.1.330 exposes
no Glob/Grep tools (screenshot 04e), so the Explore phase used `rg`/`find` through Bash, and
CLAUDE.md now says so.

## Part 2: Explore → Plan → Implement → Commit

Exploring read-only and then planning in Plan mode (screenshots 05a–05c) produced
`docs/plans/f1-agent-loop.md` with an AC-to-test table and a commit split. The plan was not perfect,
and I think the most useful habit was writing that down instead of quietly diverging: commit 3 added
a "Deviations from the plan" section. Thinking blocks are now preserved as opaque blocks,
`max_tokens` became 16,000, and refusal/`max_tokens` stop reasons end the run cleanly. Claude asked
me about each of these with concrete options (screenshots 06-commit-3-1/2), which is the right
division of labor: it found the gaps, I made the decisions.

The live demo of F1 (screenshot 07-live-2) is my favorite artifact of Part 2. The model guessed the
wrong path (`src/cli.py`), got an error `tool_result`, listed the directory and recovered. That is
AD6 ("tool errors become results, not exceptions") working exactly as designed.

## Part 3: What strict TDD caught that review alone would not

F2 took 22 commits from the first red (`a748253`) to the guard test (`52018be`), plus two refactor
commits at the end. The red step
earned its place several times:

- **A test that passed before any code existed.** For AC6, Claude's first "every part allowed" test
  used `bash(git status:*)`. That prefix rule matched the whole string `git status && git diff`, so
  the test passed without the command ever being split. Seeing it green during the red step was the
  only reason the problem was noticed; the test was rewritten with exact rules.
- **Code ahead of the tests.** In the AC4 green, Claude added a branch for leading `..` that no test
  required, and told me so. I chose to remove it and drive it with its own red. That new red then
  exposed a second, real gap: `read_file(**)` matched `../secret.txt`, because `**` compiles to `.*`.
  An extra red/green pair (`5dedac9`, `6e856e8`) fixed both.
- **A vacuous `all([])`.** In AC6, an empty or separator-only command split into no parts, and
  "every part is allowed" was vacuously true, so `""` was ALLOW even with no rules. Again a dedicated
  red (`c5dfe20`) came before the one-line fix.

Reviewing the plan before writing tests also mattered. Two security holes were caught before any
code: an absolute path inside the workspace (`/…/ws/.env`) would have bypassed a `read_file(.env)`
deny rule, and splitting only on `&& ; | ||` would have let `git status & rm -rf src`,
`git diff $(rm -rf src)` and `git diff > src/app.py` through a prefix allow rule. Both became
explicit tests and are recorded in `docs/plans/f2-permission-policy.md`, with the trade-off stated:
over-splitting is fail-safe, so `make test 2>&1` always asks.

Two process details I would keep: guard tests that pass immediately went into red commits (or their
own `test(...)` commit), never into green ones; and an isort quirk that moved imports back and forth
between red and green was fixed once with a separate `chore(ruff)` commit rather than tolerated.

The refactor step was checked after every green and skipped while there was nothing real to clean
up; I preferred no refactor commit to an empty one. One candidate after AC7, dropping the
docs URL from pydantic's config error messages, was deferred: it changes user-visible output, so it
is a behavior change for a later red/green, not a refactor. Once all eight criteria were green, two
behavior-preserving refactors were worth doing, each with the full suite green and no test changes:
`49ebcaa` extracts the bash splitting into a pure `split_command()`, and `9dcb501` compiles each
path rule's glob once when the rule is parsed instead of on every match (stored on the frozen
`Rule`, not in a module-level cache, as CLAUDE.md requires).

## Working with an AI pair: where oversight was needed

Claude was good at finding its own gaps when the process forced it to look: it reported untested
lines, wrote a throwaway pytest plugin in the scratchpad to see per-test results behind a collection
error, and asked before going beyond "minimum". It still needed oversight in three places: choosing
between options it proposed (I picked the stricter TDD path more than once), noticing what was *not*
tested (the string-instead-of-list config and invalid JSON cases in AC7 were added at my request),
and keeping the end-to-end picture (passing the resolved workspace root from the CLI to the policy,
without which the AC4 protection would have been inert in real runs). The auto-mode classifier also
blocked an edit to `.claude/settings.json` as "undermining oversight"; the right move was to make the
change in the CLI where I could see and approve it, not to work around the block.

## Context management

I used `/clear` between F1 and F2 (screenshots 08-clear-1/2) so F1 exploration would not steer F2;
CLAUDE.md and the imported docs reloaded automatically. Autocompact ran while idle during commit 4
(screenshot 06-commit-4-1). At the end, Claude saved a feedback memory about the TDD preference
("no defensive code a test doesn't need; propose a separate red", screenshot 11), so the rule carries
into Project 3. After exiting, `claude --continue` reopened the same session with its history
(screenshots 12), which is how I would resume a feature the next day instead of re-explaining it.
Durable decisions live in `docs/`, not only in chat.

## What I would do differently, and what is next

- **Rules are per tool, resources are not.** The demo model said it did not try `cat .env` through
  bash. If it had, the result would have been ASK, not DENY, because the deny rule names
  `read_file(.env)` only. Project 3 should support resource-level denies, or ship a default config
  that also denies the obvious bash readers.
- **Known limitations**, documented rather than fixed in HW4: case-insensitive file systems (`.ENV`),
  a symlink inside the workspace that points at a denied file (rules match the path as written;
  AD7 still blocks links that leave the workspace), and pydantic error messages that include a
  docs URL.
