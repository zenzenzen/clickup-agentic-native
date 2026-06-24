# Project Context

## Purpose

`clickup-agentic-native` builds `clickup-agent`, a local CLI and MCP server that lets agents operate on ClickUp work from the developer's normal environment. The project is independent of ClickUp, Inc. and should be described as a local integration, not an official ClickUp product.

The product goal is to make ClickUp feel like a native operational layer: agents should be able to inspect, create, update, comment on, organize, and review ClickUp work without forcing the operator to leave their coding or planning flow.

## Audience

- The primary operator is a developer or company operator who already manages work in ClickUp and wants agent assistance from a terminal, Codex, Cursor, or another MCP-capable client.
- The secondary audience is an agent implementing or using the repo; it needs precise command language, safe defaults, and clear distinctions between wrapper commands and raw generated API operations.
- The project is not a general SaaS front end, a hosted ClickUp replacement, or a broad automation platform.

## Product Shape

For ClickUp API execution, `clickup-agent run` exposes two command families:

- **Curated wrappers** are kebab-case commands for common workflows, such as `update-task`, `get-task`, `task-statuses`, `create-checklist`, and `sync-checklist`.
- **Generated OpenAPI operations** are raw ClickUp V2 operations from the committed catalog, such as `UpdateTask`, `GetTask`, and `CreateChecklist`.

Exact PascalCase OpenAPI operation IDs should run generated operations. Kebab-case names should run curated wrappers when a wrapper exists. When a wrapper cannot express a needed ClickUp field, agents should use the generated operation escape hatch and keep dry-run/live safety behavior intact.

Context loading should use a top-level `context` namespace with compact context manifests: agents see a small map of retrievable context surfaces and fetch only the slices they need. Retrieved context must not be written into the repository; any session cache belongs outside the repo and must be cleaned up when the main task goal completes, when the session ends, or when the operator says no further ClickUp access is needed.

When agents need to act through MCP, they should form an MCP action plan first: a compact ordered list of intended tool calls and decisions, then issue those calls deliberately with dry-run-before-live safety visible.

## Safety And Trust

- Write workflows should default to dry-run unless the caller explicitly requests live execution.
- `doctor --live-auth` is the preferred credential confidence check because it validates token/workspace authorization without exposing secrets.
- Real ClickUp API keys belong only in `$HOME/.config/clickup-agent/.env`.
- Error messages should be corrective, especially when ClickUp identifiers are easy to confuse.

## Current Capability Themes

- Generated ClickUp V2 operation catalog and registry-backed discovery.
- Curated wrappers for task search, hierarchy lookup, task creation/update, status transitions, descriptions, assignment, comments, checklists, tags, timers, and compact task fetches.
- Source metadata that identifies whether a run used a curated wrapper or generated OpenAPI operation.
- Checklist workflows that expose checklist item IDs plainly and support multi-item creation/sync from item files.
- Status discovery and validation using a task or list before applying wrapper status updates.
- Operational catch-up workflows that compose managed dev sync, task descriptions, work logs, decisions, PR managed blocks, and handoff context loading.
- `markdown_content` guidance because ClickUp may normalize stored rendered descriptions.

## Documentation Pointers

- Use `UBIQUITOUS_LANGUAGE.md` for canonical terms and ambiguity notes.
- Use `references/capabilities.md` for the current implemented CLI/MCP surface.
- Use `references/setup.md` and `references/mcp-cursor.md` for installation and client wiring.
