# F2 — Permission policy plan

Built with strict TDD (red → green → refactor), one acceptance criterion at a time, in the order
AC1 → AC8. See PRD §F2 and AD4/AD5.

## Layout

- `src/miniclaude/permissions/rules.py`: `Rule` (frozen dataclass), `parse_rule()`, `InvalidRuleError`.
- `src/miniclaude/permissions/policy.py`: `Decision` enum, `PermissionPolicy` (pure `decide()`,
  `from_file()`).
- Tests: `tests/permissions/test_rules.py`, `tests/permissions/test_policy.py`; loop integration in
  `tests/test_loop.py`, CLI approver in `tests/test_cli.py`.

## Order and red tests

| AC | Red test asserts |
|---|---|
| AC1 | Empty policy → `ASK` for every tool, including unknown ones |
| AC2 | `allow=["read_file"]` → `ALLOW` for any `read_file` input; other tools stay `ASK` |
| AC3 | `bash(git status)` exact only; `bash(git diff:*)` matches `git diff`, `git diff --stat`, not `git difftool` |
| AC4 | `src/**` crosses directories, `*` does not; `src/../.env` and `./.env` are checked as `.env`; absolute paths inside the workspace are matched as workspace-relative |
| AC5 | deny > allow, ask > allow, deny > ask |
| AC6 | Chained commands: all parts allowed → `ALLOW`; any denied → `DENY`; else `ASK`. Unsafe sub-commands never `ALLOW` (see decisions) |
| AC7 | `from_file()` loads `{"permissions": {...}}`; malformed rule → `InvalidRuleError` naming it |
| AC8 | Loop: `DENY` → error result, tool not run; `ASK` → approver decides; `ALLOW` → approver not called |

## Decisions

1. **Absolute paths are relativized to the workspace root (AC4).** The file tools accept absolute
   paths inside the workspace, so `read_file {"path": "/abs/ws/.env"}` would otherwise slip past a
   `read_file(.env)` deny rule. `PermissionPolicy` takes the workspace root. Before matching, it
   collapses `.`/`..` lexically and, if an absolute path lies inside the root, rewrites it relative
   to the root. This is pure `PurePath` logic with no `resolve()` and no filesystem access (AD4).
   Symlink escapes remain the job of workspace confinement (AD7).
2. **Bash chaining and unsafe constructs (AC6).** Commands are split on `&&`, `||`, `;`, `|`, a
   single `&` and newlines. Splitting ignores quoting. That can only over-split, which is
   fail-safe: the worst case is an extra `ASK`. A sub-command containing `$(`, a backtick, `>` or
   `<` can never be `ALLOW`ed by a bash rule, because a prefix rule like `git diff:*` would
   otherwise approve `git diff $(rm -rf src)` or `git diff > src/app.py`. Such a sub-command is
   `ASK` unless a deny rule matches, in which case it is `DENY`.
3. **Own glob-to-regex for path rules (AC4).** `PurePath.full_match()` (where `**` crosses
   directories) exists only from Python 3.13, and the project supports 3.12. A small converter
   maps `**` to "any characters including `/`", `*` to "any characters except `/`" and `?` to
   "one character except `/`". Everything else is matched literally.
4. **Loop wiring (AC8).** `AgentLoop` gets keyword args `policy` and `approver`. When `policy` is
   `None` the loop is ungated, which keeps the F1 tests unchanged. The CLI always passes a policy:
   one loaded from `<workspace>/.miniclaude/settings.json` if that file exists, otherwise an empty
   policy, under which every call is `ASK`.
