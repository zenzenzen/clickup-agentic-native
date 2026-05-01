# Capabilities Reference

Use this when explaining what the agent can do today versus what is planned.

## Implemented

- `clickup-agent --version`
- `clickup-agent doctor --env-file <path>`
- `clickup-agent mcp`
- Generated ClickUp V2 OpenAPI catalog with 137 normalized operations
- `clickup-agent tools list [--format table|json] [--tag <tag>] [--write-only]`
- `clickup-agent hotkeys list [--format table|json]`
- `clickup-agent run search`
- `clickup-agent run create-task`
- `clickup-agent run set-status`
- `clickup-agent run assign`
- `clickup-agent run set-due-date`
- `clickup-agent run comment`
- `clickup-agent run tags`
- `clickup-agent run timer`
- `scripts/install.sh` for env file, local install, and Cursor MCP config
- `scripts/install-skill.sh` for Codex skill discovery
- Cursor project/global MCP config shape
- Agent guidance for discovering an existing GitHub PR for the current branch and carrying that PR URL into planned ClickUp task updates
- Bootstrap MCP tools:
  - `clickup_agent_status`
  - `clickup_agent_tooling_plan`

## CLI Command Shape

These commands exist as stable contracts:

```bash
clickup-agent chat
clickup-agent tools list
clickup-agent hotkeys list
clickup-agent run <hotkey-or-toolchain>
clickup-agent doctor
clickup-agent mcp
```

`chat` remains a placeholder. The discovery and first `run` commands execute real generated or curated toolchains.

## Generated Toolsets

The committed catalog is generated from the official ClickUp V2 OpenAPI spec and grouped by tags such as Tasks, Comments, Tags, Time Tracking, Lists, Spaces, Members, Views, Webhooks, and Workspaces.

## Implemented Hotkey Toolchains

- `search`: task search/filter using `GetFilteredTeamTasks` or `GetTasks`
- `create-task`: task creation using `CreateTask`
- `set-status`: task status update using `UpdateTask`
- `assign`: add, remove, or replace assignees using `GetTask` and `UpdateTask`
- `set-due-date`: task due date update using `UpdateTask`
- `comment`: task comment creation using `CreateTaskComment`
- `tags`: add or remove task tags using `AddTagToTask` and `RemoveTagFromTask`
- `timer`: current, start, and stop timer actions using time-entry operations

## Still Planned

- Full comments coverage for list/view/threaded comments
- Create subtasks
- Set priority
- Link an existing branch PR into the related ClickUp task for development-reference parity
- Docs, chat, attachments, webhooks, admin workflows, and broader hierarchy/entity resolution

## Accuracy Rule

Do not claim full ClickUp API integration is implemented. Describe current status as generated V2 catalog discovery plus the first curated run toolchains.
