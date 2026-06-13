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

For repo orientation, read `CONTEXT.md` first, then `UBIQUITOUS_LANGUAGE.md` for canonical terms and ambiguity notes. Use those local files instead of the workspace-level glossary when working in this repo.

The canonical local secret file is `$HOME/.config/clickup-agent/.env`. That is the only native `clickup-agent` env file; do not search workspaces, do not use `CLICKUP_ENV_FILE`, and do not use `CLICKUP_API_TOKEN`.

## Secret Safety

- Never commit `.env.local`, API tokens, webhook secrets, or generated local Cursor config containing machine paths.
- Never paste a real ClickUp token into tracked files, docs, examples, Git commits, or chat summaries.
- MCP/Cursor config should not include a token or `CLICKUP_ENV_FILE`; `clickup-agent` reads `$HOME/.config/clickup-agent/.env` itself.
- Use `clickup-agent doctor` to report configured/missing status without revealing values.
- Use `clickup-agent doctor --live-auth` when you need a safe read-only token/workspace authorization check.

## Common Workflows

- **Orient a future agent**: read `CONTEXT.md`, `UBIQUITOUS_LANGUAGE.md`, and `references/capabilities.md` before changing public CLI/MCP language.
- **Install or repair local CLI**: read `references/setup.md`, then use `uv tool install . --python 3.12 --reinstall`.
- **Create local secrets safely**: use `bash scripts/install.sh` or follow `references/setup.md`; the installer always writes `$HOME/.config/clickup-agent/.env`.
- **Connect Cursor or another LLM client**: read `references/mcp-cursor.md`; use `clickup-agent mcp` as the stdio server command.
- **Explain capabilities**: read `references/capabilities.md` and distinguish implemented scaffolding from planned ClickUp API tools.
- **Use an uncovered generated operation**: run `clickup-agent tools list --format json`, then `clickup-agent run <PascalCaseOperationId> --dry-run ...`; only add `--live` when the user explicitly wants the mutation.
- **Use a curated wrapper**: run `clickup-agent hotkeys list`, then `clickup-agent run <kebab-case-wrapper> --dry-run ...`. Exact PascalCase operation IDs select generated operations; kebab-case names select curated wrappers when available.
- **Work with task descriptions**: prefer `markdown_content`/`--markdown-content` for rich descriptions, and expect ClickUp to normalize rendered text when task data is fetched later.
- **Back-link development work**: read `references/development-links.md`; if a GitHub PR already exists for the current branch, include its URL when updating the related ClickUp task.
- **Keep the task as a second brain**: for any non-trivial change, start or update `work-log` checklists, check off completed work and verification, and append decisions with `decision-log`.
- **Install this skill for Codex discovery**: run `bash scripts/install-skill.sh`.

## Current Truth

Implemented today: Python 3.12 CLI, generated ClickUp V2 tool catalog, `tools list` for generated OpenAPI operations, `hotkeys list` for curated wrappers, task/search/comment/checklist/timer `run` wrappers, compact task fetches, task status discovery, checklist sync, dev sync, work-log and decision-log second-brain wrappers, generated-operation fallback through `clickup-agent run <operation-id-or-name>`, `doctor --live-auth`, MCP bootstrap/status tools, direct MCP wrappers for the implemented run wrappers, `clickup_agent_run_operation`, Cursor MCP config support, and skill installation.

Planned: broader ClickUp API workflows for docs, users, guests, user groups, lists, attachments, webhooks, admin surfaces, richer entity resolution, and expanded curated wrappers.

## Validation

After changes, prefer focused checks:

```bash
bash -n scripts/install.sh
bash -n scripts/install-skill.sh
clickup-agent --version
clickup-agent tools list --format json
clickup-agent tools find task comments
clickup-agent hotkeys list
clickup-agent doctor || true
clickup-agent dev pr
clickup-agent run create-task --dry-run --list-id 123 --name "Smoke test"
clickup-agent run list-hierarchy --dry-run --team-id 123
clickup-agent run update-task --dry-run --task-id abc --name "Smoke rename"
clickup-agent run update-task --dry-run --task-id abc --status "in progress"
clickup-agent run get-task --dry-run --task-id abc --summary
clickup-agent run task-statuses --dry-run --task-id abc
clickup-agent run create-checklist --dry-run --task-id abc --name "Smoke checklist" --items checklist.json --resolved
clickup-agent run sync-checklist --dry-run --task-id abc --name "Smoke checklist" --items checklist.json --resolve-all
clickup-agent run dev-sync --dry-run --task-id abc --branch feature/demo --pr-url https://github.com/org/repo/pull/1
clickup-agent run work-log --dry-run --task-id abc --add-item "Implement change"
clickup-agent run decision-log --dry-run --task-id abc --decision "Switched X to Y"
clickup-agent run CreateChecklist --dry-run --task-id abc --name "Smoke generated op"
```

## Sync A Task With Its Branch PR

When the user asks to sync this task, update the task for this branch, or link
the PR, use the native workflow:

```bash
clickup-agent dev pr
clickup-agent run dev-sync --dry-run --task-id <task-id> --branch <branch> --pr-url <url> --pr-title <title> --pr-number <n> --pr-state <state>
```

Only add `--live` after the user explicitly wants ClickUp mutations. `dev-sync`
reads the task and task comments first, avoids duplicate PR backlinks, updates
only its visible `[dev-sync]` comment/description block, and manages the
`Development Sync` checklist by item name.

## Second-Brain Work Journal

For any major or minor complicated change, use the task as the durable work
record without waiting for the operator to ask:

```bash
clickup-agent run work-log --dry-run --task-id <task-id> --add-item "Implement change"
clickup-agent run work-log --dry-run --task-id <task-id> --check "Implement change"
clickup-agent run work-log --dry-run --task-id <task-id> --checklist verification --add-item "Run focused tests"
clickup-agent run decision-log --dry-run --task-id <task-id> --decision "Switched X to Y" --context "Why the direction changed"
```

`work-log` is mutable checklist state: `Action Items` and `Verification`.
`decision-log` is append-only journal state: one new comment per decision,
pivot, or key conversation. Automatic extraction from PR review threads is out
of scope for now; the agent should summarize and append the decision itself.
