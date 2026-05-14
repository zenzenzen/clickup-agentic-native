"""MCP server for Cursor and other LLM clients.

The server exposes bootstrap/status tools plus the first curated ClickUp
toolchains. Write workflows default to dry-run previews unless callers
explicitly request live execution.
"""

from __future__ import annotations

import json
from typing import Any
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from . import __version__
from .config import config_status
from .registry import load_catalog
from .toolchains import ToolchainError, ToolchainRunner

SERVER_NAME = "clickup-agent"


def _configure_environment() -> dict[str, Any]:
    """Load the canonical env file and return redacted configuration status."""
    status = config_status()
    env_file = status.get("env_file")
    if isinstance(env_file, str):
        home = str(Path.home())
        if env_file == home or env_file.startswith(f"{home}/"):
            status["env_file"] = f"~{env_file[len(home):]}"
    return {
        "version": __version__,
        **status,
    }


def _payload_without_none(**items: Any) -> dict[str, Any]:
    return {key: value for key, value in items.items() if value is not None}


def _compact_operation(operation: Any) -> dict[str, Any]:
    return {
        "name": operation.name,
        "method": operation.method,
        "path": operation.path,
        "tags": list(operation.tags),
        "write": operation.is_write,
        "summary": operation.summary,
    }


def _run_mcp_toolchain(
    name: str,
    payload: dict[str, Any],
    *,
    live: bool = False,
) -> dict[str, Any]:
    argv: list[str] = []
    if not live:
        argv.append("--dry-run")
    else:
        argv.append("--live")
    if payload:
        argv.extend(["--json", json.dumps(payload)])

    try:
        result = ToolchainRunner().run(name, argv)
    except ToolchainError as exc:
        return {"ok": False, "error": str(exc)}
    return {"ok": True, **result.to_dict()}


def create_server() -> FastMCP:
    """Create the MCP server instance and register bootstrap tools."""
    server = FastMCP(SERVER_NAME)

    @server.tool()
    def clickup_agent_status() -> dict[str, Any]:
        """Check whether clickup-agent is installed and locally configured."""
        return _configure_environment()

    @server.tool()
    def clickup_agent_tooling_plan(include_samples: bool = False) -> dict[str, Any]:
        """Return the generated and curated native ClickUp tool surface."""
        catalog = load_catalog()
        plan: dict[str, Any] = {
            "command": "clickup-agent",
            "catalog": {
                "source": catalog.source,
                "source_version": catalog.source_version,
                "operation_count": len(catalog.operations),
                "write_operation_count": len([operation for operation in catalog.operations if operation.is_write]),
            },
            "implemented_commands": [
                "clickup-agent tools list",
                "clickup-agent hotkeys list",
                "clickup-agent run search",
                "clickup-agent run list-hierarchy",
                "clickup-agent run resolve-user",
                "clickup-agent run resolve-task",
                "clickup-agent run inspect-task",
                "clickup-agent run audit-assigned",
                "clickup-agent run link-resource",
                "clickup-agent run apply-task-template",
                "clickup-agent run create-task",
                "clickup-agent run create-subtask",
                "clickup-agent run set-status",
                "clickup-agent run set-description",
                "clickup-agent run update-task",
                "clickup-agent run assign",
                "clickup-agent run assign-me",
                "clickup-agent run set-due-date",
                "clickup-agent run comment",
                "clickup-agent run edit-comment",
                "clickup-agent run create-checklist",
                "clickup-agent run create-checklist-item",
                "clickup-agent run check-item",
                "clickup-agent run subtasks",
                "clickup-agent run tags",
                "clickup-agent run timer",
            ],
            "hotkeys": [
                toolchain.to_dict()
                for toolchain in catalog.toolchains
            ],
        }
        if include_samples:
            plan["sample_operations"] = [_compact_operation(operation) for operation in catalog.operations[:10]]
        return plan

    @server.tool()
    def clickup_agent_search(
        query: str | None = None,
        list_id: str | None = None,
        workspace_id: str | None = None,
        team_id: str | None = None,
        page: int | None = None,
        include_closed: bool | None = None,
        live: bool = True,
    ) -> dict[str, Any]:
        """Search tasks across a workspace or within a list."""
        return _run_mcp_toolchain(
            "search",
            _payload_without_none(
                query=query,
                list_id=list_id,
                workspace_id=workspace_id,
                team_id=team_id,
                page=page,
                include_closed=include_closed,
            ),
            live=live,
        )

    @server.tool()
    def clickup_agent_list_hierarchy(
        workspace_id: str | None = None,
        team_id: str | None = None,
        space_id: str | None = None,
        folder_id: str | None = None,
        archived: bool | None = None,
        live: bool = True,
    ) -> dict[str, Any]:
        """List workspace, space, folder, and list names and IDs."""
        return _run_mcp_toolchain(
            "list-hierarchy",
            _payload_without_none(
                workspace_id=workspace_id,
                team_id=team_id,
                space_id=space_id,
                folder_id=folder_id,
                archived=archived,
            ),
            live=live,
        )

    @server.tool()
    def clickup_agent_resolve_user(
        user_id: str | None = None,
        query: str | None = None,
        workspace_id: str | None = None,
        team_id: str | None = None,
        current_user: bool | None = None,
        include_shared: bool | None = None,
        live: bool = True,
    ) -> dict[str, Any]:
        """Resolve the current user or look up workspace users by id or query."""
        return _run_mcp_toolchain(
            "resolve-user",
            _payload_without_none(
                user_id=user_id,
                query=query,
                workspace_id=workspace_id,
                team_id=team_id,
                current_user=current_user,
                include_shared=include_shared,
            ),
            live=live,
        )

    @server.tool()
    def clickup_agent_resolve_task(
        task_id: str | None = None,
        url: str | None = None,
        custom_id: str | None = None,
        query: str | None = None,
        list_id: str | None = None,
        workspace_id: str | None = None,
        team_id: str | None = None,
        custom_task_ids: bool | None = None,
        include_subtasks: bool | None = None,
        include_markdown_description: bool | None = None,
        include_closed: bool | None = None,
        page: int | None = None,
        live: bool = True,
    ) -> dict[str, Any]:
        """Resolve a task by URL, raw id, custom id, or search query."""
        return _run_mcp_toolchain(
            "resolve-task",
            _payload_without_none(
                task_id=task_id,
                url=url,
                custom_id=custom_id,
                query=query,
                list_id=list_id,
                workspace_id=workspace_id,
                team_id=team_id,
                custom_task_ids=custom_task_ids,
                include_subtasks=include_subtasks,
                include_markdown_description=include_markdown_description,
                include_closed=include_closed,
                page=page,
            ),
            live=live,
        )

    @server.tool()
    def clickup_agent_inspect_task(
        task_id: str | None = None,
        url: str | None = None,
        custom_id: str | None = None,
        custom_task_ids: bool | None = None,
        team_id: str | None = None,
        workspace_id: str | None = None,
        include_subtasks: bool | None = None,
        include_markdown_description: bool | None = None,
        include_comments: bool | None = None,
        comment_limit: int | None = None,
        live: bool = True,
    ) -> dict[str, Any]:
        """Inspect a task for documentation, checklist, comment, link, and planning gaps."""
        return _run_mcp_toolchain(
            "inspect-task",
            _payload_without_none(
                task_id=task_id,
                url=url,
                custom_id=custom_id,
                custom_task_ids=custom_task_ids,
                team_id=team_id,
                workspace_id=workspace_id,
                include_subtasks=include_subtasks,
                include_markdown_description=include_markdown_description,
                include_comments=include_comments,
                comment_limit=comment_limit,
            ),
            live=live,
        )

    @server.tool()
    def clickup_agent_audit_assigned(
        workspace_id: str | None = None,
        team_id: str | None = None,
        assignee: str | None = None,
        user_id: str | None = None,
        include_closed: bool | None = None,
        page: int | None = None,
        limit: int | None = None,
        live: bool = True,
    ) -> dict[str, Any]:
        """Audit assigned tasks for cleanup gaps and proposed next actions."""
        return _run_mcp_toolchain(
            "audit-assigned",
            _payload_without_none(
                workspace_id=workspace_id,
                team_id=team_id,
                assignee=assignee,
                user_id=user_id,
                include_closed=include_closed,
                page=page,
                limit=limit,
            ),
            live=live,
        )

    @server.tool()
    def clickup_agent_link_resource(
        task_id: str,
        url: str,
        title: str | None = None,
        kind: str | None = None,
        note: str | None = None,
        include_comments: bool | None = None,
        custom_task_ids: bool | None = None,
        team_id: str | None = None,
        live: bool = False,
    ) -> dict[str, Any]:
        """Attach an external resource link to a task. Defaults to dry-run unless live is true."""
        return _run_mcp_toolchain(
            "link-resource",
            _payload_without_none(
                task_id=task_id,
                url=url,
                title=title,
                kind=kind,
                note=note,
                include_comments=include_comments,
                custom_task_ids=custom_task_ids,
                team_id=team_id,
            ),
            live=live,
        )

    @server.tool()
    def clickup_agent_apply_task_template(
        task_id: str,
        context: str | None = None,
        decision: str | None = None,
        acceptance: str | None = None,
        implementation_notes: str | None = None,
        external_link: str | None = None,
        review_notes: str | None = None,
        custom_task_ids: bool | None = None,
        team_id: str | None = None,
        include_markdown_description: bool | None = None,
        live: bool = False,
    ) -> dict[str, Any]:
        """Apply standard task documentation sections. Defaults to dry-run unless live is true."""
        return _run_mcp_toolchain(
            "apply-task-template",
            _payload_without_none(
                task_id=task_id,
                context=context,
                decision=decision,
                acceptance=acceptance,
                implementation_notes=implementation_notes,
                external_link=external_link,
                review_notes=review_notes,
                custom_task_ids=custom_task_ids,
                team_id=team_id,
                include_markdown_description=include_markdown_description,
            ),
            live=live,
        )

    @server.tool()
    def clickup_agent_create_task(
        list_id: str,
        name: str,
        description: str | None = None,
        status: str | None = None,
        assignees: list[int] | None = None,
        tags: list[str] | None = None,
        due_date: str | None = None,
        live: bool = False,
    ) -> dict[str, Any]:
        """Create a task. Defaults to dry-run unless live is true."""
        return _run_mcp_toolchain(
            "create-task",
            _payload_without_none(
                list_id=list_id,
                name=name,
                description=description,
                status=status,
                assignees=assignees,
                tags=tags,
                due_date_iso=due_date,
            ),
            live=live,
        )

    @server.tool()
    def clickup_agent_create_subtask(
        list_id: str,
        parent: str,
        name: str,
        description: str | None = None,
        status: str | None = None,
        assignees: list[int] | None = None,
        tags: list[str] | None = None,
        due_date: str | None = None,
        live: bool = False,
    ) -> dict[str, Any]:
        """Create a subtask under a parent task. Defaults to dry-run unless live is true."""
        return _run_mcp_toolchain(
            "create-subtask",
            _payload_without_none(
                list_id=list_id,
                parent=parent,
                name=name,
                description=description,
                status=status,
                assignees=assignees,
                tags=tags,
                due_date_iso=due_date,
            ),
            live=live,
        )

    @server.tool()
    def clickup_agent_set_status(
        task_id: str,
        status: str,
        custom_task_ids: bool | None = None,
        team_id: str | None = None,
        live: bool = False,
    ) -> dict[str, Any]:
        """Update a task status. Defaults to dry-run unless live is true."""
        return _run_mcp_toolchain(
            "set-status",
            _payload_without_none(
                task_id=task_id,
                status=status,
                custom_task_ids=custom_task_ids,
                team_id=team_id,
            ),
            live=live,
        )

    @server.tool()
    def clickup_agent_set_description(
        task_id: str,
        description: str | None = None,
        markdown_content: str | None = None,
        custom_task_ids: bool | None = None,
        team_id: str | None = None,
        live: bool = False,
    ) -> dict[str, Any]:
        """Update a task description. Defaults to dry-run unless live is true."""
        return _run_mcp_toolchain(
            "set-description",
            _payload_without_none(
                task_id=task_id,
                description=description,
                markdown_content=markdown_content,
                custom_task_ids=custom_task_ids,
                team_id=team_id,
            ),
            live=live,
        )

    @server.tool()
    def clickup_agent_update_task(
        task_id: str,
        name: str | None = None,
        description: str | None = None,
        markdown_content: str | None = None,
        priority: int | None = None,
        due_date: str | None = None,
        due_date_time: bool | None = None,
        start_date: str | None = None,
        start_date_time: bool | None = None,
        points: float | None = None,
        time_estimate: int | None = None,
        archived: bool | None = None,
        parent: str | None = None,
        custom_task_ids: bool | None = None,
        team_id: str | None = None,
        live: bool = False,
    ) -> dict[str, Any]:
        """Update arbitrary task fields. Defaults to dry-run unless live is true."""
        return _run_mcp_toolchain(
            "update-task",
            _payload_without_none(
                task_id=task_id,
                name=name,
                description=description,
                markdown_content=markdown_content,
                priority=priority,
                due_date_iso=due_date,
                due_date_time=due_date_time,
                start_date_iso=start_date,
                start_date_time=start_date_time,
                points=points,
                time_estimate=time_estimate,
                archived=archived,
                parent=parent,
                custom_task_ids=custom_task_ids,
                team_id=team_id,
            ),
            live=live,
        )

    @server.tool()
    def clickup_agent_assign(
        task_id: str,
        assignees: list[int],
        mode: str = "add",
        custom_task_ids: bool | None = None,
        team_id: str | None = None,
        live: bool = False,
    ) -> dict[str, Any]:
        """Add, remove, or replace task assignees. Defaults to dry-run unless live is true."""
        return _run_mcp_toolchain(
            "assign",
            _payload_without_none(
                task_id=task_id,
                assignees=assignees,
                mode=mode,
                custom_task_ids=custom_task_ids,
                team_id=team_id,
            ),
            live=live,
        )

    @server.tool()
    def clickup_agent_assign_me(
        task_id: str,
        mode: str = "add",
        custom_task_ids: bool | None = None,
        team_id: str | None = None,
        live: bool = False,
    ) -> dict[str, Any]:
        """Assign the authorized user to a task. Defaults to dry-run unless live is true."""
        return _run_mcp_toolchain(
            "assign-me",
            _payload_without_none(
                task_id=task_id,
                mode=mode,
                custom_task_ids=custom_task_ids,
                team_id=team_id,
            ),
            live=live,
        )

    @server.tool()
    def clickup_agent_set_due_date(
        task_id: str,
        due_date: str,
        due_date_time: bool | None = None,
        custom_task_ids: bool | None = None,
        team_id: str | None = None,
        live: bool = False,
    ) -> dict[str, Any]:
        """Set a task due date. Defaults to dry-run unless live is true."""
        return _run_mcp_toolchain(
            "set-due-date",
            _payload_without_none(
                task_id=task_id,
                due_date_iso=due_date,
                due_date_time=due_date_time,
                custom_task_ids=custom_task_ids,
                team_id=team_id,
            ),
            live=live,
        )

    @server.tool()
    def clickup_agent_comment(
        task_id: str,
        text: str,
        notify_all: bool | None = None,
        assignee: int | None = None,
        group_assignee: str | None = None,
        custom_task_ids: bool | None = None,
        team_id: str | None = None,
        live: bool = False,
    ) -> dict[str, Any]:
        """Add a task comment. Defaults to dry-run unless live is true."""
        return _run_mcp_toolchain(
            "comment",
            _payload_without_none(
                task_id=task_id,
                text=text,
                notify_all=notify_all,
                assignee=assignee,
                group_assignee=group_assignee,
                custom_task_ids=custom_task_ids,
                team_id=team_id,
            ),
            live=live,
        )

    @server.tool()
    def clickup_agent_edit_comment(
        comment_id: str,
        text: str,
        assignee: int,
        resolved: bool,
        live: bool = False,
    ) -> dict[str, Any]:
        """Edit an existing comment. Defaults to dry-run unless live is true."""
        return _run_mcp_toolchain(
            "edit-comment",
            _payload_without_none(
                comment_id=comment_id,
                text=text,
                assignee=assignee,
                resolved=resolved,
            ),
            live=live,
        )

    @server.tool()
    def clickup_agent_create_checklist(
        task_id: str,
        name: str,
        custom_task_ids: bool | None = None,
        team_id: str | None = None,
        live: bool = False,
    ) -> dict[str, Any]:
        """Create a checklist on a task. Defaults to dry-run unless live is true."""
        return _run_mcp_toolchain(
            "create-checklist",
            _payload_without_none(
                task_id=task_id,
                name=name,
                custom_task_ids=custom_task_ids,
                team_id=team_id,
            ),
            live=live,
        )

    @server.tool()
    def clickup_agent_create_checklist_item(
        checklist_id: str,
        name: str,
        assignee: int | None = None,
        live: bool = False,
    ) -> dict[str, Any]:
        """Add an item to a checklist. Defaults to dry-run unless live is true."""
        return _run_mcp_toolchain(
            "create-checklist-item",
            _payload_without_none(
                checklist_id=checklist_id,
                name=name,
                assignee=assignee,
            ),
            live=live,
        )

    @server.tool()
    def clickup_agent_check_item(
        checklist_id: str,
        item_id: str,
        resolved: bool | None = None,
        name: str | None = None,
        assignee: int | None = None,
        parent: str | None = None,
        live: bool = False,
    ) -> dict[str, Any]:
        """Edit a checklist item. Defaults to dry-run unless live is true."""
        return _run_mcp_toolchain(
            "check-item",
            _payload_without_none(
                checklist_id=checklist_id,
                item_id=item_id,
                resolved=resolved,
                name=name,
                assignee=assignee,
                parent=parent,
            ),
            live=live,
        )

    @server.tool()
    def clickup_agent_subtasks(
        task_id: str,
        custom_task_ids: bool | None = None,
        team_id: str | None = None,
        include_markdown_description: bool | None = None,
        live: bool = True,
    ) -> dict[str, Any]:
        """Fetch a task with subtasks expanded."""
        return _run_mcp_toolchain(
            "subtasks",
            _payload_without_none(
                task_id=task_id,
                custom_task_ids=custom_task_ids,
                team_id=team_id,
                include_markdown_description=include_markdown_description,
            ),
            live=live,
        )

    @server.tool()
    def clickup_agent_tags(
        task_id: str,
        add: list[str] | None = None,
        remove: list[str] | None = None,
        custom_task_ids: bool | None = None,
        team_id: str | None = None,
        live: bool = False,
    ) -> dict[str, Any]:
        """Add or remove task tags. Defaults to dry-run unless live is true."""
        return _run_mcp_toolchain(
            "tags",
            _payload_without_none(
                task_id=task_id,
                add=add,
                remove=remove,
                custom_task_ids=custom_task_ids,
                team_id=team_id,
            ),
            live=live,
        )

    @server.tool()
    def clickup_agent_timer(
        action: str = "current",
        workspace_id: str | None = None,
        team_id: str | None = None,
        task_id: str | None = None,
        description: str | None = None,
        tags: list[str] | None = None,
        billable: bool | None = None,
        assignee: int | None = None,
        live: bool = False,
    ) -> dict[str, Any]:
        """Inspect, start, or stop a timer. Defaults to dry-run unless live is true."""
        return _run_mcp_toolchain(
            "timer",
            _payload_without_none(
                action=action,
                workspace_id=workspace_id,
                team_id=team_id,
                task_id=task_id,
                description=description,
                tags=tags,
                billable=billable,
                assignee=assignee,
            ),
            live=live,
        )

    return server


def run() -> None:
    """Run the MCP server over stdio for Cursor."""
    create_server().run()
