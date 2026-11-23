# MiniClaude

A minimal, single-process coding agent for the terminal: an LLM-driven ReAct loop with built-in file and shell tools, gated by a configurable permission policy.

> Status: HW4 milestone (agent loop + tools + permission policy). Project 3 will add sessions, context compaction and skills. See [docs/PRD.md](docs/PRD.md).

## Quick start

```bash
uv sync
cp .env.example .env      # add your ANTHROPIC_API_KEY
uv run pytest             # offline test suite
uv run miniclaude --version
uv run miniclaude run "add a --verbose flag to cli.py" --workspace path/to/repo
```

`miniclaude run` prints the model's text, a `→` line for each tool call and a `✓`/`✗` line for its result. It exits with 0 when the model finishes, and with 1 if it stops early (step limit, refusal, output token limit or API error). The model defaults to `claude-sonnet-5-5`; set `MINICLAUDE_MODEL` in `.env` to change it. Until the F2 permission policy lands, tools run without asking, so point `--workspace` at a repo you don't mind it editing.

## Docs

- [Product requirements](docs/PRD.md)
- [Architecture & decisions](docs/architecture.md)
- [Implementation plans](docs/plans/)
- [HW4 reflection & annotated session logs](docs/hw4/)

## Roadmap

* **Sprint 1 (Nov 21 – Nov 22): HW4, Claude Code workflow & TDD.** Project setup (CLAUDE.md, permissions), agent loop + built-in tools via Explore → Plan → Implement → Commit, permission policy via strict red-green-refactor TDD.
* **Sprint 2 (Nov 23 – Dec 6): HW5, custom skill + MCP integration.** Skills loaded from `.miniclaude/skills/`, an MCP client that exposes external MCP server tools to the agent loop, and a project-specific Claude Code skill for this repo.
* **Sprint 3 (Dec 7 – Dec 15): Project 3, production application.** P3 proposal, then sessions with `--continue`, context budget tracking and `/compact`, interactive `chat` REPL, packaging and an end-to-end demo.
* HW4 due date is Nov 22 at 11:59pm.
* Homework 5 due date is Dec 6 at 11:59pm.
* P3 Proposal due date is Dec 8 at 11:59pm.
* Project 3 due date is Dec 15 at 11:59pm.

## Acknowledgment

The overall architecture was informed by studying the open-source project [KamaClaude](https://github.com/youngyangyang04/KamaClaude) (MIT License). MiniClaude is an independent, simplified reimplementation: all code and tests in this repository were written from scratch for this project.
