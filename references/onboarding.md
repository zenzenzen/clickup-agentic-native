# Onboarding

`clickup-agent` is a local, dry-run-first CLI and MCP server for agentic
ClickUp work. It reads secrets from one user config file and lets agents preview
ClickUp mutations before applying them.

## Setup

Store local configuration only in:

```bash
~/.config/clickup-agent/.env
```

Check configuration without printing secrets:

```bash
clickup-agent doctor
clickup-agent doctor --live-auth
```

## Curated Toolchains

Generated operations expose the broad ClickUp API surface. Curated wrappers
combine common operations into safer, smaller commands:

```bash
clickup-agent tools list --format json
clickup-agent tools find task comments
clickup-agent hotkeys list
clickup-agent run create-task --dry-run --list-id 123 --name "Draft brief"
```

Write wrappers preview by default. Use `--live` only when the ClickUp mutation
is intended.

## Macro Movesets

| Trigger phrase | Move |
|---|---|
| "sync this task", "update the task for this branch", "link the PR" | `dev-sync` |
| "audit my branches", "which branches are merged", "reconcile ClickUp with git" | `dev audit` then `dev-sync` |
| "log this hotfix", "document PR #N as a hotfix task" | `hotfix-doc` |

Examples:

```bash
clickup-agent dev audit
clickup-agent run dev-sync --dry-run --task-id abc --branch feature/demo
clickup-agent run hotfix-doc \
  --dry-run \
  --list-id 123 \
  --title "Fix docs" \
  --pr-url https://github.com/org/repo/pull/1 \
  --problem "What broke" \
  --fix "What changed"
```

`hotfix-doc` creates a completed documentation task shape plus a resolved
`Hotfix tracking` checklist. It is still dry-run-first.
