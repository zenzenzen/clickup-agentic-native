# Capabilities Reference

Use this when explaining what the agent can do today versus what is planned.

## Implemented

- `clickup-agent --version`
- `clickup-agent doctor`
- `clickup-agent doctor --live-auth`
- `clickup-agent mcp`
- Generated ClickUp V2 OpenAPI catalog with 137 normalized operations
- `clickup-agent tools list [--format table|json] [--tag <tag>] [--write-only]`
- `clickup-agent hotkeys list [--format table|json]`
- `clickup-agent run search`
- `clickup-agent run list-hierarchy`
- `clickup-agent run create-task`
- `clickup-agent run create-subtask`
- `clickup-agent run set-status`
- `clickup-agent run set-description`
- `clickup-agent run update-task`
- `clickup-agent run assign`
- `clickup-agent run assign-me`
- `clickup-agent run set-due-date`
- `clickup-agent run comment`
- `clickup-agent run edit-comment`
- `clickup-agent run create-checklist`
- `clickup-agent run create-checklist-item`
- `clickup-agent run check-item`
- `clickup-agent run subtasks`
- `clickup-agent run tags`
- `clickup-agent run timer`
- `clickup-agent run <generated operation name or ID>`
- `scripts/install.sh` for env file, local install, and Cursor MCP config
- `scripts/install-skill.sh` for Codex skill discovery
- Cursor project/global MCP config shape
- Agent guidance for discovering an existing GitHub PR for the current branch and carrying that PR URL into planned ClickUp task updates
- Bootstrap MCP tools:
  - `clickup_agent_status`
  - `clickup_agent_tooling_plan`
  - `clickup_agent_run_operation`
- Direct MCP tools:
  - `clickup_agent_search`
  - `clickup_agent_list_hierarchy`
  - `clickup_agent_create_task`
  - `clickup_agent_create_subtask`
  - `clickup_agent_set_status`
  - `clickup_agent_set_description`
  - `clickup_agent_update_task`
  - `clickup_agent_assign`
  - `clickup_agent_assign_me`
  - `clickup_agent_set_due_date`
  - `clickup_agent_comment`
  - `clickup_agent_edit_comment`
  - `clickup_agent_create_checklist`
  - `clickup_agent_create_checklist_item`
  - `clickup_agent_check_item`
  - `clickup_agent_subtasks`
  - `clickup_agent_tags`
  - `clickup_agent_timer`

## CLI Command Shape

These commands exist as stable contracts:

```bash
clickup-agent chat
clickup-agent tools list
clickup-agent hotkeys list
clickup-agent run <hotkey-or-toolchain-or-generated-operation>
clickup-agent doctor
clickup-agent mcp
```

`chat` remains a placeholder. The discovery commands, first `run` commands, generated operation fallback, and direct MCP wrappers execute real generated or curated toolchains. MCP write wrappers default to dry-run unless the caller explicitly sets `live` to true.

## Generated Toolsets

The committed catalog is generated from the official ClickUp V2 OpenAPI spec and grouped by tags such as Tasks, Comments, Tags, Time Tracking, Lists, Spaces, Members, Views, Webhooks, and Workspaces.

Agents can call generated operations directly through `clickup-agent run <operation>` or the MCP `clickup_agent_run_operation` tool. Operation IDs such as `CreateChecklist` and catalog names such as `delete-checklist` both work. Write operations still preview by default unless `--live` or `live: true` is explicit.

## Implemented Hotkey Toolchains

- `search`: task search/filter using `GetFilteredTeamTasks` or `GetTasks`
- `list-hierarchy`: hierarchy and list discovery using workspace, space, folder, and list read operations
- `create-task`: task creation using `CreateTask`
- `create-subtask`: subtask creation using `CreateTask`
- `set-status`: task status update using `UpdateTask`
- `set-description`: task description update using `UpdateTask`
- `update-task`: broad task update using `UpdateTask`
- `assign`: add, remove, or replace assignees using `GetTask` and `UpdateTask`
- `assign-me`: assign the authorized user using `GetAuthorizedUser` and `UpdateTask`
- `set-due-date`: task due date update using `UpdateTask`
- `comment`: task comment creation using `CreateTaskComment`
- `edit-comment`: comment editing using `UpdateComment`
- `create-checklist`: checklist creation using `CreateChecklist`
- `create-checklist-item`: checklist item creation using `CreateChecklistItem`
- `check-item`: checklist item editing using `EditChecklistItem`
- `subtasks`: subtask retrieval using `GetTask`
- `tags`: add or remove task tags using `AddTagToTask` and `RemoveTagFromTask`
- `timer`: current, start, and stop timer actions using time-entry operations

## Still Planned

- Full comments coverage for list/view/threaded comments
- Link an existing branch PR into the related ClickUp task for development-reference parity
- Docs, chat, attachments, webhooks, admin workflows, and broader hierarchy/entity resolution

## Accuracy Rule

Do not claim full ClickUp API integration is implemented. Describe current status as generated V2 catalog discovery plus the first curated run toolchains.
