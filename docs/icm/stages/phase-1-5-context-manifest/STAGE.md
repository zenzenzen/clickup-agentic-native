# Stage: Context Manifest

## Purpose

Add a static, manifest-first context surface so agents can understand operational catch-up actions quickly without loading repository-wide or ClickUp-wide context.

## Inputs

| Layer | Path | Required? | Use |
| --- | --- | --- | --- |
| 3 | `CONTEXT.md` | required | Context namespace and cleanup rules. |
| 3 | `UBIQUITOUS_LANGUAGE.md` | required | Context manifest, pinned action, and sync topology terms. |
| 3 | `docs/adr/0001-ephemeral-context-manifests-outside-the-repo.md` | required | Boundary decision for ephemeral context. |
| 3 | `src/clickup_agent/cli.py` | required | Top-level CLI namespace. |
| 3 | `src/clickup_agent/mcp_server.py` | optional | MCP action-plan guidance alignment. |

## Do Not Load

- Live ClickUp data by default.
- Git branch or PR state by default.
- Retrieved context files under the repository.

## Process

1. Add `clickup-agent context manifest` as a static/catalog-like command.
2. Include concise verbosity steering, context surfaces, loader commands, freshness/cost hints, pinned actions, and MCP action templates.
3. Keep pinned actions focused on `dev-sync`, `get-task`, and planned `catch-up-docs`.
4. Keep action-plan guidance inspectable; do not create a hidden execution queue.
5. Add tests proving manifest output is compact and deterministic.

## Outputs

| Path | Description |
| --- | --- |
| CLI context namespace | Static manifest command. |
| tests | Manifest contract tests. |

## Verify

- `pytest` focused on CLI/context manifest tests.
- Manifest command does not inspect git, ClickUp, or current branch by default.
- Manifest includes no repo-resident generated context path.

## Review Gate

Human or agent reviewer confirms the manifest is useful for operational catch-up and still cheap to inspect.

## Transitions

- forward: `phase-1-6-catch-up-docs`
- revisit: update manifest labels/templates if pinned actions are unclear
- abort: preserve manifest output and write a resume note

## Provenance

Commit message should mention Phase 1.5 context manifest and include the focused validation run.
