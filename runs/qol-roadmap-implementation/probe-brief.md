# Probe Brief: QOL Roadmap Implementation

## BVP

```text
v: do=3 rig=2 wid=3 crit=2 nov=1 q=0
out: diff
stop: tests_green
esc: scope_breach | evidence<2
on_uncertain: probe
note: implement quality-of-life roadmap with milestone commits and separate PRs
```

## Problem

Implement the quality-of-life roadmap for `clickup-agentic-native` as a milestone conveyor: one scoped milestone, one validation gate, one commit, one branch/PR, then the next milestone.

## Stage

Building and hardening. The roadmap has been drafted; implementation now needs controlled slices.

## Evidence

- Current CLI supports `doctor`, `mcp`, `tools list`, `hotkeys list`, and `run`.
- Current toolchains include task search, hierarchy/list discovery, task creation/update, subtasks, assignment, due/start dates, points, time estimates, comments, checklists, tags, and timers.
- Current MCP server exposes bootstrap/status tools and direct wrappers for implemented run toolchains.
- Generated catalog contains relevant operations for users, members, tasks, comments, custom fields, relationships, attachments, and time tracking.

## Constraints

- Do not expose ClickUp tokens, env values, or local machine-specific secrets.
- Do not touch unrelated dirty `SKILL.md` changes unless explicitly assigned.
- Keep each milestone branch narrow enough for a separate PR.
- Prefer existing CLI/toolchain/MCP patterns over new architecture.
- Generated catalog changes must keep `scripts/generate_tool_catalog.py` and `src/clickup_agent/catalog/tool_catalog.json` aligned.

## Topology Snapshot

- `src/clickup_agent/cli.py`: public CLI parser and top-level command handlers.
- `src/clickup_agent/toolchains.py`: curated run toolchain parser/executor registry.
- `src/clickup_agent/mcp_server.py`: direct MCP wrappers over toolchains.
- `src/clickup_agent/requests.py`: generated-operation request builder.
- `src/clickup_agent/registry.py`: catalog and toolchain metadata models.
- `scripts/generate_tool_catalog.py`: generated catalog source of truth.
- `tests/test_run_toolchains.py`, `tests/test_mcp_server.py`, `tests/test_cli_discovery.py`: behavior gates.
- `references/`: documentation and roadmap references.

## Core Dependencies

The CLI command shape, toolchain runner, generated catalog schema, and MCP wrapper behavior are public API surfaces for this repo. Changes to these areas require targeted tests and `git diff --check`; full `uv run pytest` is preferred before each PR.

## Out Of Scope

No live ClickUp mutation, no admin/destructive workflows, no broad formatting sweep, no token/config disclosure, and no editing user-owned `SKILL.md` changes.

## Pattern

Universal pattern: `orchestrator-workers`, because implementation spans public CLI, toolchains, MCP wrappers, docs, and tests.

Hotkey pattern: `agent-milestone-conveyor`, explicitly requested by the user. Run one active milestone at a time in the integration worktree, with worker/critic review before commit.

Execution mode: `multi-agent execution`. The user explicitly requested a team of 2-3, the work spans multiple public modules, and implementation/critique have cleanly separable ownership.

## Initial Milestones

1. M0: publish roadmap/runbook docs and stale-reference cleanup.
2. M1: installation confidence baseline (`setup`, redacted repair plan, MCP smoke test or equivalent).
3. M2: identity/entity resolution baseline (`resolve-user`, `resolve-task`, MCP wrappers).
4. M3: assigned-work audit and inspect-task baseline.
5. M4: development resource linking and task documentation maintenance baseline.

Later roadmap items continue the same conveyor after these foundational slices.
