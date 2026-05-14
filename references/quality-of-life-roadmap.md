# Quality Of Life Roadmap

Use this roadmap for the remaining work that would make `clickup-agent` useful as a daily professional operating layer, not just a ClickUp API wrapper.

## Current Baseline

The native surface already supports task search, hierarchy/list discovery, task creation and updates, subtasks, assignment, due and start dates, points, time estimates, comments, checklists, tags, running timers, dry-run previews, and direct MCP wrappers.

The main gaps are now higher-level workflow quality: installation confidence, entity resolution, assigned-work audits, task documentation upkeep, decision capture, metadata backfill, time entry management, and durable links to external work.

## Milestone 1: Installation Confidence

Goal: make a fresh install feel boring, inspectable, and recoverable.

- Add `clickup-agent setup` as a guided first-run command over the existing installer script.
- Add a redacted `doctor --repair-plan` mode that explains missing PATH, Python, `uv`, env file, Cursor MCP config, and token/workspace access fixes.
- Add an MCP smoke-test command that starts the server, calls status/tooling-plan, and reports whether an LLM client can safely discover tools.
- Add shell completion or `clickup-agent help workflows` for the most common run commands.
- Document upgrade, uninstall, and reinstall flows for both global tool installs and editable development installs.

Acceptance:

- A new user can install, configure, verify live auth, and connect Cursor without reading source files.
- Troubleshooting output never prints tokens, local secret values, or machine-specific config that should not be committed.

## Milestone 2: Identity And Entity Resolution

Goal: let agents act on human references without forcing users to paste every numeric ID.

- Add user/member lookup: authorized user, workspace users, list members, task members, guests, and groups.
- Add an alias cache for common people, lists, spaces, folders, tags, custom fields, and task IDs.
- Resolve tasks from ClickUp URLs, custom task IDs, raw IDs, names within a list, and recently returned search results.
- Add disambiguation output that is compact enough for LLM clients: candidate IDs, names, locations, and confidence.
- Add default workspace/list context with explicit override flags.

Acceptance:

- Commands such as "assign this to Sarah", "move this into next sprint", or "find my overdue review tasks" can be translated into safe toolchain calls with a preview before mutation.

## Milestone 3: Assigned-Work Audit

Goal: give a working professional a quick, actionable audit of what needs attention.

- Add `audit-assigned` for tasks assigned to the authorized user, another user, a group, or all users in a list/view.
- Flag overdue work, missing assignees, missing due dates, stale tasks, unclear status, empty descriptions, absent acceptance criteria, missing checklists, unresolved comments, missing points or time estimates, and tasks without development links.
- Use view/list filters where possible, with pagination helpers and rate-limit-aware batching.
- Add compact output modes: summary table, JSON for agents, and `--comment-plan` for proposed ClickUp updates.
- Keep mutation separate: an audit should recommend comments, field updates, checklist changes, or date changes, but require explicit `--live` for writes.

Acceptance:

- A user can ask "what assigned tasks need cleanup?" and get a prioritized list with concrete next actions.

## Milestone 4: Task Documentation Maintenance

Goal: make task descriptions and checklists reliable enough to hand to another human or agent.

- Add `apply-task-template` to create or update standard description sections such as Context, Decision Log, Acceptance Criteria, Implementation Notes, External Links, and Review Notes.
- Preserve user-written content by updating named sections instead of replacing the whole description.
- Add `capture-decision` to append explicit decisions with date, source, rationale, and affected task/checklist items.
- Add checklist reconciliation: create missing checklist items, rename stale ones, mark completed items, and avoid duplicates.
- Add a git-history audit mode that can summarize commits, changed files, branch/PR context, and test evidence into proposed task documentation or checklist updates.

Acceptance:

- A task can be brought from "vague placeholder" to "actionable work record" through a dry-run diff, then applied live by explicit approval.

## Milestone 5: Planning Metadata Backfill

Goal: make dates, estimates, points, and ownership easy to repair in batches.

- Add higher-level date commands for start date, due date, clearing dates, relative dates, and batch updates across search results.
- Add sprint-point and time-estimate backfill flows using the existing task update primitives.
- Add custom-field discovery and updates for workspace-specific fields such as sprint, team, client, severity, blocked-by, or release.
- Add templates for common planning passes: "triage unplanned tasks", "prepare sprint", "close stale tasks", and "make my week legible".
- Add preview output that groups changes by task and highlights risky updates.

Acceptance:

- The agent can repair planning metadata across a list or view without forcing one manual command per task.

## Milestone 6: Time Tracking And Time Segments

Goal: cover both live timer usage and retroactive time record cleanup.

- Expand the current timer command into create, update, delete, range-query, and tag-management toolchains.
- Add `time-backfill` for retroactive time entries with task, start/end, duration, description, tags, billable flag, and assignee.
- Add `time-audit` for missing or suspicious time entries across a date range.
- Support importing a simple local work log into proposed ClickUp time entries.
- Keep destructive edits and deletes confirmation-gated.

Acceptance:

- A user can fill in yesterday's work, inspect the current timer, and audit a week of tracked time from the CLI or MCP server.

## Milestone 7: External Links And Work Graph

Goal: connect ClickUp tasks to the real artifacts where work happens.

- Add `link-resource` for GitHub PRs, commits, branches, docs, URLs, screenshots, and other external references.
- Prefer a workspace custom field when configured, otherwise use a task comment or description section.
- Detect and avoid duplicate links.
- Add task link and dependency commands using the generated task relationship operations.
- Add attachment upload for local files and generated artifacts when the user explicitly requests it.

Acceptance:

- A task can show its PR, branch, design link, external doc, dependency task, and supporting artifacts without duplicate comments or manual copy/paste.

## Milestone 8: Broader Collaboration Surface

Goal: extend beyond single-task maintenance once the daily workflow core is reliable.

- Add full comments coverage for task, list, view, and threaded comments.
- Add list/view helpers for creating operational dashboards and "my work" views.
- Add docs support when the available ClickUp API surface is sufficient; otherwise document the limitation clearly.
- Add guests, user groups, roles, and admin workflows behind conservative confirmations.
- Add webhook setup and signed webhook verification for event-driven sync.

Acceptance:

- The agent can support team-level operating rituals while keeping admin and destructive actions explicit.

## Smallest Coherent Next Slice

Build these in order:

1. `resolve-user` and `resolve-task` read-only helpers with MCP wrappers.
2. `inspect-task` read-only helper that returns description sections, assignees, dates, points, comments summary, checklists, tags, subtasks, and links.
3. `audit-assigned` dry-run helper built on search, user resolution, pagination, and `inspect-task`.
4. `link-resource` with GitHub PR detection, duplicate avoidance, and comment fallback.
5. `apply-task-template` dry-run diff for description sections and checklist reconciliation.

This slice turns the current primitives into a useful daily review loop without requiring broad admin coverage first.
