# Capabilities Reference

Use this when explaining what the agent can do today versus what is planned.

Read `../CONTEXT.md` for product intent and `../UBIQUITOUS_LANGUAGE.md` for canonical domain language before renaming CLI/MCP concepts.

## Implemented

- `clickup-agent --version`
- `clickup-agent doctor`
- `clickup-agent doctor --live-auth`
- `clickup-agent onboard`
- `clickup-agent guide`
- `clickup-agent welcome`
- `clickup-agent mcp`
- Generated ClickUp V2 OpenAPI catalog with 137 normalized operations
- `clickup-agent tools list [--format table|json] [--tag <tag>] [--write-only]`
- `clickup-agent tools find <query...> [--format table|json]`
- `clickup-agent hotkeys list [--format table|json]`
- `clickup-agent context manifest`
- `clickup-agent dev pr`
- `clickup-agent dev audit`
- `clickup-agent run search`
- `clickup-agent run list-hierarchy`
- `clickup-agent run create-task`
- `clickup-agent run create-subtask`
- `clickup-agent run set-status`
- `clickup-agent run task-statuses`
- `clickup-agent run set-description`
- `clickup-agent run update-task`
- `clickup-agent run get-task`
- `clickup-agent run assign`
- `clickup-agent run assign-me`
- `clickup-agent run set-due-date`
- `clickup-agent run comment`
- `clickup-agent run comments`
- `clickup-agent run edit-comment`
- `clickup-agent run create-checklist`
- `clickup-agent run sync-checklist`
- `clickup-agent run create-checklist-item`
- `clickup-agent run check-item`
- `clickup-agent run subtasks`
- `clickup-agent run tags`
- `clickup-agent run timer`
- `clickup-agent run dev-sync`
- `clickup-agent run work-log`
- `clickup-agent run decision-log`
- `clickup-agent run hotfix-doc`
- `clickup-agent run <generated operation name or ID>`
- `scripts/install.sh` for env file, local install, and Cursor MCP config
- `scripts/install-skill.sh` for Codex skill discovery
- Cursor project/global MCP config shape
- Agent guidance for discovering an existing GitHub PR for the current branch and carrying that PR URL into planned ClickUp task updates
- Bootstrap MCP tools:
  - `clickup_agent_status`
  - `clickup_agent_tooling_plan`
  - `clickup_agent_run_operation`
  - `clickup_agent_dev_pr`
- Direct MCP tools:
  - `clickup_agent_search`
  - `clickup_agent_list_hierarchy`
  - `clickup_agent_create_task`
  - `clickup_agent_create_subtask`
  - `clickup_agent_set_status`
  - `clickup_agent_task_statuses`
  - `clickup_agent_set_description`
  - `clickup_agent_update_task`
  - `clickup_agent_get_task`
  - `clickup_agent_assign`
  - `clickup_agent_assign_me`
  - `clickup_agent_set_due_date`
  - `clickup_agent_comment`
  - `clickup_agent_edit_comment`
  - `clickup_agent_create_checklist`
  - `clickup_agent_sync_checklist`
  - `clickup_agent_create_checklist_item`
  - `clickup_agent_check_item`
  - `clickup_agent_subtasks`
  - `clickup_agent_tags`
  - `clickup_agent_timer`
  - `clickup_agent_dev_sync`
  - `clickup_agent_work_log`
  - `clickup_agent_decision_log`
  - `clickup_agent_hotfix_doc`

## CLI Command Shape

These commands exist as stable contracts:

```bash
clickup-agent chat
clickup-agent tools list
clickup-agent hotkeys list
clickup-agent run <curated-wrapper-or-generated-operation>
clickup-agent onboard
clickup-agent doctor
clickup-agent mcp
```

`chat` remains a placeholder. `tools list` discovers generated OpenAPI operations; `tools find` searches generated operation names, operation IDs, summaries, and tags; `hotkeys list` discovers curated wrapper commands. `dev pr` and `dev audit` are read-only GitHub/git helpers for branch and PR context. The first `run` commands, generated operation fallback, and direct MCP wrappers execute real generated or curated workflows. MCP write wrappers default to dry-run unless the caller explicitly sets `live` to true.

## Generated Toolsets

The committed catalog is generated from the official ClickUp V2 OpenAPI spec and grouped by tags such as Tasks, Comments, Tags, Time Tracking, Lists, Spaces, Members, Views, Webhooks, and Workspaces.

Agents can call generated operations directly through `clickup-agent run <operation>` or the MCP `clickup_agent_run_operation` tool. Exact PascalCase operation IDs such as `UpdateTask` run raw/generated operations. Kebab-case names such as `update-task` run curated wrappers when a wrapper exists, and otherwise fall through to generated catalog names. Write operations still preview by default unless `--live` or `live: true` is explicit.

## Implemented Curated Wrappers

- `search`: task search/filter using `GetFilteredTeamTasks` or `GetTasks`
- `list-hierarchy`: hierarchy and list discovery using workspace, space, folder, and list read operations
- `create-task`: task creation using `CreateTask`
- `create-subtask`: subtask creation using `CreateTask`
- `set-status`: task status update using `UpdateTask`, with wrapper-level status validation
- `task-statuses`: valid status discovery for a task or list using `GetTask` and `GetList`
- `set-description`: task description update using `UpdateTask`; prefer `markdown_content` for rich formatting
- `update-task`: broad task update using `UpdateTask`, including validated status updates
- `get-task`: task fetch using `GetTask`, with summary and field projection modes
- `assign`: add, remove, or replace assignees using `GetTask` and `UpdateTask`
- `assign-me`: assign the authorized user using `GetAuthorizedUser` and `UpdateTask`
- `set-due-date`: task due date update using `UpdateTask`
- `comment`: task comment creation using `CreateTaskComment`
- `comments`: task comment listing or creation using `GetTaskComments` and `CreateTaskComment`
- `edit-comment`: comment editing using `UpdateComment`
- `create-checklist`: checklist creation using `CreateChecklist`, optionally followed by initial checklist item creation
- `sync-checklist`: non-destructive checklist item create/update using `GetTask`, `CreateChecklist`, `CreateChecklistItem`, and `EditChecklistItem`
- `create-checklist-item`: checklist item creation using `CreateChecklistItem`
- `check-item`: checklist item editing using `EditChecklistItem`
- `subtasks`: subtask retrieval using `GetTask`
- `tags`: add or remove task tags using `AddTagToTask` and `RemoveTagFromTask`
- `timer`: current, start, and stop timer actions using time-entry operations
- `dev-sync`: GitHub branch/PR state sync using `GetTask`, `GetTaskComments`, task/comment updates, non-destructive checklist item convergence, and optional managed GitHub PR-body updates via `--mode clickup-to-github|bidirectional`
- `work-log`: mutable `Action Items` or `Verification` checklist state using non-destructive checklist item convergence
- `decision-log`: append-only decision record comments using visible `[dev-sync:decision]` markers
- `hotfix-doc`: completed documentation task creation for a hotfix PR using `CreateTask`, `CreateChecklist`, and `CreateChecklistItem`

## Still Planned

- Automatic extraction of decisions from PR review threads via `dev-sync --capture-decisions`
- Full comments coverage for list/view/threaded comments
- Docs, chat, attachments, webhooks, admin workflows, and broader hierarchy/entity resolution

## Formatting Notes

Use `markdown_content`/`--markdown-content` when rich task descriptions matter. ClickUp may normalize markdown into rendered or plain description fields when returning task data, so fetched descriptions can differ from the submitted markdown.

## Accuracy Rule

Do not claim full ClickUp API integration is implemented. Describe current status as generated V2 catalog discovery plus the first curated wrappers.
