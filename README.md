# clickup-agentic-native

`clickup-agentic-native` is a home for building a super agentic, native way to access and use ClickUp tooling.

The command name for the project will be `clickup-agent`.

## Attribution

This project is based on interfacing with ClickUp, the work management platform and APIs provided by ClickUp, Inc. ClickUp is a trademark of ClickUp, Inc.

`clickup-agentic-native` is an independent integration project and is not affiliated with, sponsored by, or endorsed by ClickUp, Inc.

## Vision

This project exists to make ClickUp feel like a native operational layer for my company workflow, not a separate place I have to manually visit and maintain.

The goal is an agent that can understand work context, resolve ClickUp entities, compose safe toolchains, and help me create, update, search, comment on, organize, and review ClickUp work from the places where I already operate.

## Command Shape

The CLI grows around clear, memorable commands:

```bash
clickup-agent chat
clickup-agent tools list
clickup-agent hotkeys list
clickup-agent run <hotkey-or-toolchain>
clickup-agent doctor
```

Discovery commands are backed by a committed catalog generated from ClickUp's official V2 OpenAPI spec:

```bash
clickup-agent tools list --tag Tasks --write-only
clickup-agent hotkeys list --format json
```

The first practical run toolchains support dry-run previews and live execution when `CLICKUP_API_KEY` is configured:

```bash
clickup-agent run search --dry-run --team-id 123 --query roadmap
clickup-agent run list-hierarchy --dry-run --team-id 123
clickup-agent run create-task --dry-run --list-id 456 --name "Write launch notes"
clickup-agent run create-subtask --dry-run --list-id 456 --parent abc --name "Draft outline"
clickup-agent run set-status --dry-run --task-id abc --status "in progress"
clickup-agent run set-description --dry-run --task-id abc --markdown-content "## Updated brief"
clickup-agent run update-task --dry-run --task-id abc --name "Rename task" --priority 2
clickup-agent run assign --dry-run --task-id abc --assignee 182 --mode add
clickup-agent run assign-me --dry-run --task-id abc
clickup-agent run set-due-date --dry-run --task-id abc --due-date 2026-05-01
clickup-agent run comment --dry-run --task-id abc --text "PR is ready"
clickup-agent run edit-comment --dry-run --comment-id 123 --text "Updated" --assignee 182 --resolved
clickup-agent run create-checklist --dry-run --task-id abc --name "Launch"
clickup-agent run create-checklist-item --dry-run --checklist-id chk --name "Verify" --assignee 182
clickup-agent run check-item --dry-run --checklist-id chk --item-id item --resolved
clickup-agent run subtasks --dry-run --task-id abc
clickup-agent run tags --dry-run --task-id abc --add review --remove stale
clickup-agent run timer --dry-run --action start --team-id 123 --task-id abc
```

## Install Your Own Agent

This repo is the starting point for a local ClickUp agent that an LLM client can run as a tool server.

Clone your own copy:

```bash
git clone https://github.com/zenzenzen/clickup-agentic-native.git
cd clickup-agentic-native
```

Create local secrets from the template in the default user config location:

```bash
mkdir -p "$HOME/.config/clickup-agent"
cp .env.example "$HOME/.config/clickup-agent/.env"
chmod 600 "$HOME/.config/clickup-agent/.env"
```

Then edit `$HOME/.config/clickup-agent/.env`:

```bash
CLICKUP_API_KEY=your_clickup_personal_token
CLICKUP_WORKSPACE_ID=your_default_workspace_id
CLICKUP_WEBHOOK_SECRET=optional_future_webhook_signing_secret
```

Or let the installer walk you through it:

```bash
bash scripts/install.sh
```

The installer can also add `clickup-agent` to Cursor as an MCP server. Choose project config for this repo only, or global config for every Cursor workspace.

Install the Python package:

```bash
uv tool install . --python 3.12 --reinstall
```

During early development, use editable mode instead:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

Once installed, your LLM client should call the agent through the `clickup-agent` command. The MCP-style entrypoint is reserved as:

```bash
clickup-agent mcp
```

Example LLM client server configuration:

```json
{
  "mcpServers": {
    "clickup-agent": {
      "command": "clickup-agent",
      "args": ["mcp"],
      "env": {}
    }
  }
}
```

For clients that do not support MCP yet, the fallback integration shape is to call focused CLI commands directly, such as `clickup-agent run search` or `clickup-agent run create-task`.

For Cursor, place the same server definition in `.cursor/mcp.json` for a project-specific install or `~/.cursor/mcp.json` for a global install. The installer can write this for you and preserves any existing MCP servers. A portable template lives at `.cursor/mcp.example.json`.

The native agent always reads `$HOME/.config/clickup-agent/.env`. Do not set `CLICKUP_ENV_FILE`; it is ignored by `clickup-agent`.

Check your local setup:

```bash
clickup-agent doctor
clickup-agent doctor --live-auth
```

## Install Agent Skill

Install the repo's agent-facing skill into Codex discovery:

```bash
bash scripts/install-skill.sh
```

The skill installs to `~/.codex/skills/clickup-agentic-native` by default, or to `$CODEX_HOME/skills/clickup-agentic-native` when `CODEX_HOME` is set. Agents can then use `clickup-agentic-native` to discover setup commands, MCP/Cursor configuration, local scripts, secret-handling rules, and current/planned ClickUp capabilities.

## Architecture Direction

The repo should favor agentic atomic primitives that can be composed into larger workflows:

- Native ClickUp API coverage across tasks, comments, docs, users, lists, time tracking, and workspace hierarchy.
- Atomic tools with typed inputs, safe outputs, and consistent error handling.
- Toolchains for common workflows such as task creation, triage, status updates, comments, due dates, assignments, and search.
- Context-aware execution that remembers the active workspace, user intent, source channel, and recently resolved ClickUp entities.
- Secure local secret handling, with real API keys kept out of Git.
- Hotkey-inspired workflows for the most common ClickUp actions.

## Workflow Principles

Development should move in small, easy-to-review steps.

- Create frequent commits for each major task or file group.
- Keep commit messages short, direct, and descriptive.
- Add concise comments to major source files that explain each file's role.
- Prefer clear primitives over large, tangled helpers.
- Treat destructive or admin ClickUp operations as confirmation-gated by default.

## Implemented Native Surface

- Typed registry models for generated operations and curated toolchains.
- `scripts/generate_tool_catalog.py` for generating `src/clickup_agent/catalog/tool_catalog.json`.
- ClickUp HTTP client with auth, redacted errors, and JSON response handling.
- Registry-backed `tools list` and `hotkeys list` discovery.
- `run` toolchains for search, hierarchy/list discovery, task creation/update, subtasks, checklists, comments, assignment, due dates, tags, and timers.
- `doctor --live-auth` for safe read-only token and workspace authorization checks.
- Direct MCP wrappers for the first run toolchains, with write workflows defaulting to dry-run unless live execution is requested.
- Dry-run output for every first-pass write workflow.

## Roadmap

Future implementation passes should expand:

- A context/session layer for resolving workspace, list, task, doc, user, group, and channel references.
- Quality-of-life workflows for assigned-work audits, task documentation upkeep, decision capture, planning metadata backfill, time entry management, and external work links.
- Full comments capability for task, list, view, and threaded comments.
- Tasks, docs, users, guests, user groups, lists, attachments, webhooks, and time tracking coverage.
- Pagination helpers, richer rate-limit handling, and broader generated-operation execution.

See `references/quality-of-life-roadmap.md` for the professional workflow roadmap.

## Secret Handling

Copy `.env.example` to `$HOME/.config/clickup-agent/.env` and fill in local values. Real credentials must stay in that local env file outside tracked workspaces.

```bash
CLICKUP_API_KEY=
CLICKUP_WORKSPACE_ID=
CLICKUP_WEBHOOK_SECRET=
```

No ClickUp API key should ever be committed to this repo.

## License

This project is licensed under the Apache License, Version 2.0. Keep the `NOTICE` file with redistributions so attribution is preserved.
