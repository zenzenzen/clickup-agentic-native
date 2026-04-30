# Capabilities Reference

Use this when explaining what the agent can do today versus what is planned.

## Implemented

- `clickup-agent --version`
- `clickup-agent doctor --env-file <path>`
- `clickup-agent mcp`
- `scripts/install.sh` for env file, local install, and Cursor MCP config
- `scripts/install-skill.sh` for Codex skill discovery
- Cursor project/global MCP config shape
- Bootstrap MCP tools:
  - `clickup_agent_status`
  - `clickup_agent_tooling_plan`

## CLI Commands Reserved

These commands exist or are reserved as stable contracts:

```bash
clickup-agent chat
clickup-agent tools list
clickup-agent hotkeys list
clickup-agent run <hotkey-or-toolchain>
clickup-agent doctor
clickup-agent mcp
```

Placeholder commands explain the future contract instead of performing ClickUp API actions.

## Planned Toolsets

- `clickup_core`: auth, workspace lookup, health checks
- `clickup_hierarchy`: workspaces, spaces, folders, lists, members
- `clickup_tasks`: create/get/update/delete/move tasks, subtasks, checklists, relationships
- `clickup_comments`: task/list/view comments, update/delete, threaded replies
- `clickup_people`: users, guests, members, roles, user groups
- `clickup_search`: task/doc/list/channel/entity resolution
- `clickup_docs`: docs search/create/read/page edit
- `clickup_chat`: channels, DMs, messages, replies, reactions, tagged users
- `clickup_files`: attachments
- `clickup_time`: time entries, timers, estimates, time in status
- `clickup_admin`: webhooks, ACLs, audit logs; confirmation-gated by default

## Planned Hotkey Toolchains

- Search workspace
- Create task
- Set task status
- Assign task
- Set due date
- Comment on task
- Create subtasks
- Set priority
- Add or remove tags
- Start or stop timer

## Accuracy Rule

Do not claim full ClickUp API integration is implemented until the relevant tools exist. Describe current status as scaffold/bootstrap plus planned native tools.
