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
clickup-agent doctor
clickup-agent doctor --live-auth
uv tool install . --python 3.12 --reinstall
bash scripts/install.sh
clickup-agent mcp
```

If working from the repo, use the repo root as the working directory. If `clickup-agent` is not installed, reinstall with `uv tool install . --python 3.12 --reinstall`.

The canonical local secret file is `$HOME/.config/clickup-agent/.env`. That is the only native `clickup-agent` env file; do not search workspaces, do not use `CLICKUP_ENV_FILE`, and do not use `CLICKUP_API_TOKEN`.

## Secret Safety

- Never commit `.env.local`, API tokens, webhook secrets, or generated local Cursor config containing machine paths.
- Never paste a real ClickUp token into tracked files, docs, examples, Git commits, or chat summaries.
- MCP/Cursor config should not include a token or `CLICKUP_ENV_FILE`; `clickup-agent` reads `$HOME/.config/clickup-agent/.env` itself.
- Use `clickup-agent doctor` to report configured/missing status without revealing values.
- Use `clickup-agent doctor --live-auth` when you need a safe read-only token/workspace authorization check.

## Common Workflows

- **Install or repair local CLI**: read `references/setup.md`, then use `uv tool install . --python 3.12 --reinstall`.
- **Create local secrets safely**: use `bash scripts/install.sh` or follow `references/setup.md`; the installer always writes `$HOME/.config/clickup-agent/.env`.
- **Connect Cursor or another LLM client**: read `references/mcp-cursor.md`; use `clickup-agent mcp` as the stdio server command.
- **Explain capabilities**: read `references/capabilities.md` and distinguish implemented scaffolding from planned ClickUp API tools.
- **Use an uncovered generated operation**: run `clickup-agent tools list --format json`, then `clickup-agent run <operation-id-or-name> --dry-run ...`; only add `--live` when the user explicitly wants the mutation.
- **Back-link development work**: read `references/development-links.md`; if a GitHub PR already exists for the current branch, include its URL when updating the related ClickUp task.
- **Install this skill for Codex discovery**: run `bash scripts/install-skill.sh`.

## Current Truth

Implemented today: Python 3.12 CLI, generated ClickUp V2 tool catalog, `tools list`, `hotkeys list`, task/search/comment/checklist/timer `run` toolchains, generated-operation fallback through `clickup-agent run <operation-id-or-name>`, `doctor --live-auth`, MCP bootstrap/status tools, direct MCP wrappers for the implemented run toolchains, `clickup_agent_run_operation`, Cursor MCP config support, and skill installation.

Planned: broader ClickUp API workflows for docs, users, guests, user groups, lists, attachments, webhooks, admin surfaces, richer entity resolution, and expanded hotkey toolchains.

## Validation

After changes, prefer focused checks:

```bash
bash -n scripts/install.sh
bash -n scripts/install-skill.sh
clickup-agent --version
clickup-agent tools list --format json
clickup-agent hotkeys list
clickup-agent doctor || true
clickup-agent run create-task --dry-run --list-id 123 --name "Smoke test"
clickup-agent run list-hierarchy --dry-run --team-id 123
clickup-agent run update-task --dry-run --task-id abc --name "Smoke rename"
clickup-agent run create-checklist --dry-run --task-id abc --name "Smoke checklist"
clickup-agent run CreateChecklist --dry-run --task-id abc --name "Smoke generated op"
```
