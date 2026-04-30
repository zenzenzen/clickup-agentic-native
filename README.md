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
```

No ClickUp API key should ever be committed to this repo.
