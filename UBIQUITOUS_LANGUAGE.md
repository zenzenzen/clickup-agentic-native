# Ubiquitous Language

## Product And Actors

| Term | Definition | Aliases to avoid |
| --- | --- | --- |
| **ClickUp agent** | The local CLI/MCP integration exposed through the `clickup-agent` command. | Bot, app, ClickUp product |
| **Operator** | The person using an agent or terminal to inspect or mutate ClickUp work. | Customer, user account |
| **Agent** | An LLM-driven worker using the CLI or MCP tools on behalf of the operator. | Bot, automation, script |
| **LLM client** | A host application, such as Codex or Cursor, that can call `clickup-agent` directly or through MCP. | IDE, chat app |
| **Native operational layer** | The desired experience where ClickUp work can be handled from the operator's existing workflow. | Replacement UI, hosted platform |

## Command Surface

| Term | Definition | Aliases to avoid |
| --- | --- | --- |
| **Command family** | A category that tells whether a command is a curated wrapper or a generated OpenAPI operation. | Source, tool type |
| **Curated wrapper** | A kebab-case command designed around a common workflow and safer CLI ergonomics. | Hotkey, toolchain, lowercase operation |
| **Wrapper name** | The kebab-case identifier for a curated wrapper, such as `update-task`. | Operation name, alias |
| **Generated OpenAPI operation** | A raw ClickUp V2 catalog operation generated from the official OpenAPI spec. | Generated tool, raw tool |
| **Operation ID** | The PascalCase OpenAPI identifier, such as `UpdateTask`, that should select a generated operation exactly. | Wrapper name, tool name |
| **Catalog name** | The normalized kebab-case name of a generated OpenAPI operation, used only when no curated wrapper owns that name. | Wrapper name, alias |
| **Source metadata** | Output metadata that states whether a run used a curated wrapper or a generated OpenAPI operation. | Provenance, family label |
| **Generated operation hint** | A wrapper note that names the raw operation to use when full API fields are needed. | Help text, fallback |
| **Dry-run** | A non-mutating preview of the operation payload and execution plan. | Test mode, fake run |
| **Live execution** | A run that is allowed to call ClickUp mutating endpoints. | Real run, production mode |

## ClickUp Work Objects

| Term | Definition | Aliases to avoid |
| --- | --- | --- |
| **Task** | A ClickUp work item that can be fetched, updated, assigned, commented on, tagged, and given checklists. | Ticket, issue |
| **Task ID** | The ClickUp identifier used to address a task in CLI and API calls. | Task URL, custom ID |
| **List** | The ClickUp container that owns a task's available statuses. | Project, board |
| **List status** | A valid status value configured on a ClickUp list. | Workflow state, status option |
| **Task status** | The current status value on a task. | State, phase |
| **Status validation** | Wrapper behavior that checks a requested task status against valid list statuses before mutation. | Status coercion, status guessing |
| **Task summary** | A compact `get-task` projection with high-signal fields such as id, url, name, status, assignees, checklist counts, and description length. | Short task, compact response |
| **Field projection** | A caller-selected subset of task output fields. | Filter, summary |

## Checklist Workflows

| Term | Definition | Aliases to avoid |
| --- | --- | --- |
| **Checklist** | A named collection of checklist items attached to a ClickUp task. | Todo list, checklist group |
| **Checklist ID** | The identifier for the checklist container. | Checklist item ID, item ID |
| **Checklist item** | A single actionable row inside a checklist. | Checklist, todo |
| **Checklist item ID** | The identifier for a single checklist item, required when editing that item. | Checklist ID, row ID |
| **Checklist item file** | A JSON file containing strings or item objects used for multi-item checklist creation or sync. | Items file, checklist JSON |
| **Resolved item** | A checklist item marked complete in ClickUp. | Checked item, completed task |
| **Bulk checklist create** | Creating a checklist and zero or more initial items in one wrapper workflow. | Batch create, checklist import |
| **Checklist sync** | A non-destructive workflow that reuses a checklist by exact name, updates matched items, and creates missing items. | Replace checklist, checklist overwrite |
| **Resolve all** | An option that marks all supplied checklist items resolved during create or sync. | Complete all, close all |

## Configuration And Formatting

| Term | Definition | Aliases to avoid |
| --- | --- | --- |
| **Canonical env file** | `$HOME/.config/clickup-agent/.env`, the only native env file `clickup-agent` should read. | `.env.local`, `CLICKUP_ENV_FILE` |
| **Live auth check** | The `doctor --live-auth` read-only authorization probe. | Login, token dump |
| **Markdown content** | The rich task description field sent as `markdown_content` or `--markdown-content`. | Description, markdown description |
| **Plain description** | The returned or submitted plain text description field that ClickUp may normalize. | Markdown content, rendered markdown |

## Relationships

- A **ClickUp agent** is used by an **Agent** or **Operator** through a terminal or **LLM client**.
- A **Command family** is either **Curated wrapper** or **Generated OpenAPI operation**.
- A **Curated wrapper** may compose one or more **Generated OpenAPI operations**.
- An exact **Operation ID** selects a **Generated OpenAPI operation**; a **Wrapper name** selects a **Curated wrapper** when one exists.
- A **Task** belongs to a **List**, and a **List** defines one or more **List statuses**.
- **Status validation** compares a requested **Task status** against the **List statuses** before **Live execution**.
- A **Checklist** belongs to one **Task** and contains zero or more **Checklist items**.
- A **Checklist item ID** identifies one **Checklist item**; a **Checklist ID** identifies the parent **Checklist**.
- **Checklist sync** may update matched **Checklist items** and create missing **Checklist items**, but it must not delete unspecified items.
- **Markdown content** may become a normalized **Plain description** after ClickUp stores and returns it.

## Example Dialogue

> **Dev:** "Should `clickup-agent run update-task --status done` call the same thing as `clickup-agent run UpdateTask --status done`?"
>
> **Domain expert:** "No. `update-task` is a **Curated wrapper** and should perform **Status validation**. `UpdateTask` is an **Operation ID** and runs the **Generated OpenAPI operation**."
>
> **Dev:** "If the wrapper cannot express a ClickUp field, what should the agent do?"
>
> **Domain expert:** "Use the **Generated operation hint**, switch to the exact **Operation ID**, and keep **Dry-run** as the default before **Live execution**."
>
> **Dev:** "For checklists, can I pass the checklist ID when editing an item?"
>
> **Domain expert:** "No. Use the **Checklist item ID** for item edits; the **Checklist ID** only identifies the container."
>
> **Dev:** "And task descriptions should use `description`?"
>
> **Domain expert:** "Use **Markdown content** for rich formatting, then expect ClickUp may return a normalized **Plain description** later."

## Flagged Ambiguities

- "tool", "hotkey", and "toolchain" were used for both wrappers and generated operations; use **Curated wrapper** for kebab-case workflow commands and **Generated OpenAPI operation** for raw catalog operations.
- `update-task` and `UpdateTask` look like the same command but are distinct; use **Wrapper name** for `update-task` and **Operation ID** for `UpdateTask`.
- "checklist id" was confused with **Checklist item ID**; error messages and docs should explicitly distinguish the container from the editable item.
- "status" can mean a task's current state or the valid options on a list; use **Task status** for the value on a task and **List status** for an allowed value.
- "description" can mean submitted markdown or returned normalized text; use **Markdown content** for rich submitted content and **Plain description** for the normalized field.
- "source" can mean the OpenAPI spec URL, command family, or output metadata; use **Source metadata** only for run output provenance and **Command family** for discovery grouping.
