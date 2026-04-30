# clickup-agentic-native

`clickup-agentic-native` is a home for building a super agentic, native way to access and use ClickUp tooling.

The command name for the project will be `clickup-agent`.

## Vision

This project exists to make ClickUp feel like a native operational layer for my company workflow, not a separate place I have to manually visit and maintain.

The goal is an agent that can understand work context, resolve ClickUp entities, compose safe toolchains, and help me create, update, search, comment on, organize, and review ClickUp work from the places where I already operate.

## Command Shape

The initial CLI should grow around clear, memorable commands:

```bash
clickup-agent chat
clickup-agent tools list
clickup-agent hotkeys list
clickup-agent run <hotkey-or-toolchain>
clickup-agent doctor
```

## Install Your Own Agent

This repo is the starting point for a local ClickUp agent that an LLM client can run as a tool server.

Clone your own copy:

```bash
git clone https://github.com/zenzenzen/clickup-agentic-native.git
cd clickup-agentic-native
```

Create local secrets from the template:

```bash
cp .env.example .env.local
chmod 600 .env.local
```

Then edit `.env.local`:

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
      "env": {
        "CLICKUP_ENV_FILE": "/absolute/path/to/clickup-agentic-native/.env.local"
      }
    }
  }
}
```

For clients that do not support MCP yet, the fallback integration shape is to call focused CLI commands directly, such as `clickup-agent run search` or `clickup-agent run create-task`.

For Cursor, place the same server definition in `.cursor/mcp.json` for a project-specific install or `~/.cursor/mcp.json` for a global install. The installer can write this for you and preserves any existing MCP servers. A portable template lives at `.cursor/mcp.example.json`.

This repo includes a project-local `.cursor/mcp.json` that points Cursor at the installed `clickup-agent` command and this repo's `.env.local` file.

Check your local setup:

```bash
clickup-agent doctor --env-file .env.local
```

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

## Initial Roadmap

The first implementation pass should establish:

- A ClickUp API client with auth, pagination, rate-limit handling, and secret redaction.
- A tool registry for generated and curated ClickUp tools.
- A context/session layer for resolving workspace, list, task, doc, user, group, and channel references.
- Hotkey toolchains using `clickup-agent run`.
- Full comments capability for task, list, view, and threaded comments.
- Tasks, docs, users, guests, user groups, lists, attachments, webhooks, and time tracking coverage.

## Secret Handling

Copy `.env.example` to `.env.local` and fill in local values. Real credentials must stay in ignored env files.

```bash
CLICKUP_API_KEY=
CLICKUP_WORKSPACE_ID=
CLICKUP_WEBHOOK_SECRET=
```

No ClickUp API key should ever be committed to this repo.

## License

This project is licensed under the Apache License, Version 2.0. Keep the `NOTICE` file with redistributions so attribution is preserved.
