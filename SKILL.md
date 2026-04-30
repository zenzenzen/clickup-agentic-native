---
name: clickup-agentic-native
description: Use when working with the clickup-agentic-native repo or installed clickup-agent command; helps agents install, configure, expose through MCP/Cursor, inspect local setup, and understand current versus planned ClickUp capabilities.
---

# ClickUp Agentic Native

Use this skill when a user asks about the `clickup-agentic-native` repo, the `clickup-agent` command, ClickUp MCP setup, Cursor integration, local ClickUp env files, or planned agentic ClickUp tooling.

## First Checks

Prefer existing commands before inventing setup steps:

```bash
clickup-agent --version
clickup-agent doctor --env-file .env.local
uv tool install . --python 3.12 --reinstall
bash scripts/install.sh
clickup-agent mcp
```

If working from the repo, use the repo root as the working directory. If `clickup-agent` is not installed, reinstall with `uv tool install . --python 3.12 --reinstall`.

## Secret Safety

- Never commit `.env.local`, API tokens, webhook secrets, or generated local Cursor config containing machine paths.
- Never paste a real ClickUp token into tracked files, docs, examples, Git commits, or chat summaries.
- MCP/Cursor config should point to `CLICKUP_ENV_FILE`; it must not contain the token itself.
- Use `clickup-agent doctor --env-file .env.local` to report configured/missing status without revealing values.

## Common Workflows

- **Install or repair local CLI**: read `references/setup.md`, then use `uv tool install . --python 3.12 --reinstall`.
- **Create `.env.local` safely**: use `bash scripts/install.sh` or follow `references/setup.md`.
- **Connect Cursor or another LLM client**: read `references/mcp-cursor.md`; use `clickup-agent mcp` as the stdio server command.
- **Explain capabilities**: read `references/capabilities.md` and distinguish implemented scaffolding from planned ClickUp API tools.
- **Back-link development work**: read `references/development-links.md`; if a GitHub PR already exists for the current branch, include its URL when updating the related ClickUp task.
- **Install this skill for Codex discovery**: run `bash scripts/install-skill.sh`.

## Current Truth

Implemented today: Python 3.12 CLI scaffold, `doctor`, interactive installer, MCP bootstrap server, Cursor MCP config support, and skill installation.

Planned: native ClickUp API tools for comments, tasks, docs, users, guests, user groups, lists, time tracking, attachments, webhooks, and hotkey toolchains.

## Validation

After changes, prefer focused checks:

```bash
bash -n scripts/install.sh
bash -n scripts/install-skill.sh
clickup-agent --version
clickup-agent doctor --env-file .env.example || true
```
