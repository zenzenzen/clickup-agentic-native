"""MCP server for Cursor and other LLM clients.

The server exposes bootstrap/status tools plus the first curated ClickUp
toolchains. Write workflows default to dry-run previews unless callers
explicitly request live execution.

The MCP functions are intentionally thin adapters over the CLI toolchain runner
so agent clients see the same wrapper/generated-operation behavior, source
metadata, dry-run payloads, and corrective errors as terminal users.
"""

from __future__ import annotations

import json
from typing import Any
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from . import __version__
from .config import config_status
from .devlinks import inspect_dev_pr
from .discovery import CURATED_WRAPPERS
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
    """Preserve explicit false/empty values while dropping omitted options."""
    return {key: value for key, value in items.items() if value is not None}


def _compact_operation(operation: Any) -> dict[str, Any]:
    """Expose enough catalog context for planning without large schemas."""
    return {
        "name": operation.name,
        "method": operation.method,
        "path": operation.path,
        "tags": list(operation.tags),
        "write": operation.is_write,
        "summary": operation.summary,
    }


def _compact_toolchain(toolchain: Any) -> dict[str, Any]:
    """Expose enough curated-wrapper context for planning without long operation lists."""
    return {
        "name": toolchain.name,
        "write": toolchain.is_write,
        "summary": toolchain.summary,
    }


def _run_mcp_toolchain(
    name: str,
    payload: dict[str, Any],
    *,
    live: bool = False,
) -> dict[str, Any]:
    """Invoke a toolchain through the same JSON argv path used by the CLI."""
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
        # This plan is designed for LLM clients deciding whether to call a
        # curated wrapper or the raw generated operation escape hatch.
        plan: dict[str, Any] = {
            "command": "clickup-agent",
            "catalog": {
                "source": catalog.source,
                "source_version": catalog.source_version,
                "operation_count": len(catalog.operations),
                "write_operation_count": len([operation for operation in catalog.operations if operation.is_write]),
            },
            "implemented_commands": [
                "clickup-agent tools list (generated OpenAPI operations)",
                "clickup-agent hotkeys list (curated wrappers)",
                *[f"clickup-agent run {wrapper.name}" for wrapper in CURATED_WRAPPERS],
                "clickup-agent dev pr",
                "clickup-agent dev audit",
                "clickup-agent run <generated operation name or ID>",
            ],
            "hotkeys": [
                _compact_toolchain(toolchain)
                for toolchain in catalog.toolchains
            ],
        }
        if include_samples:
            plan["sample_operations"] = [_compact_operation(operation) for operation in catalog.operations[:10]]
        return plan

    @server.tool()
    def clickup_agent_run_operation(
        operation: str,
        payload: dict[str, Any] | None = None,
        live: bool = False,
    ) -> dict[str, Any]:
        """Run any generated ClickUp operation by operation id or tool name. Defaults to dry-run."""
        return _run_mcp_toolchain(operation, payload or {}, live=live)

    @server.tool()
    def clickup_agent_dev_pr(timeout: float = 10.0, repo: str | None = None) -> dict[str, Any]:
        """Inspect the current branch's GitHub PR. Read-only."""
        return inspect_dev_pr(cwd=repo, timeout=timeout).to_dict()

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
    def clickup_agent_get_task(
        task_id: str,
        summary: bool | None = None,
        fields: list[str] | str | None = None,
        custom_task_ids: bool | None = None,
        team_id: str | None = None,
        include_markdown_description: bool | None = None,
        live: bool = True,
    ) -> dict[str, Any]:
        """Fetch a task, optionally returning a compact summary or selected fields."""
        return _run_mcp_toolchain(
            "get-task",
            _payload_without_none(
                task_id=task_id,
                summary=summary,
                fields=fields,
                custom_task_ids=custom_task_ids,
                team_id=team_id,
                include_markdown_description=include_markdown_description,
            ),
            live=live,
        )

    @server.tool()
    def clickup_agent_task_statuses(
        task_id: str | None = None,
        list_id: str | None = None,
        custom_task_ids: bool | None = None,
        team_id: str | None = None,
        live: bool = True,
    ) -> dict[str, Any]:
        """Discover valid statuses for a task or list."""
        return _run_mcp_toolchain(
            "task-statuses",
            _payload_without_none(
                task_id=task_id,
                list_id=list_id,
                custom_task_ids=custom_task_ids,
                team_id=team_id,
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
        status: str | None = None,
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
                status=status,
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
        items: list[Any] | None = None,
        resolved: bool | None = None,
        custom_task_ids: bool | None = None,
        team_id: str | None = None,
        live: bool = False,
    ) -> dict[str, Any]:
        """Create a checklist and optional items on a task. Defaults to dry-run unless live is true."""
        return _run_mcp_toolchain(
            "create-checklist",
            _payload_without_none(
                task_id=task_id,
                name=name,
                items=items,
                resolved=resolved,
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
    def clickup_agent_sync_checklist(
        task_id: str,
        name: str,
        items: list[Any],
        resolve_all: bool | None = None,
        custom_task_ids: bool | None = None,
        team_id: str | None = None,
        live: bool = False,
    ) -> dict[str, Any]:
        """Create or update checklist items by id or exact name. Defaults to dry-run unless live is true."""
        return _run_mcp_toolchain(
            "sync-checklist",
            _payload_without_none(
                task_id=task_id,
                name=name,
                items=items,
                resolve_all=resolve_all,
                custom_task_ids=custom_task_ids,
                team_id=team_id,
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

    @server.tool()
    def clickup_agent_dev_sync(
        task_id: str,
        repo: str | None = None,
        mode: str | None = None,
        branch: str | None = None,
        latest_commit: str | None = None,
        pr_url: str | None = None,
        pr_title: str | None = None,
        pr_number: int | str | None = None,
        pr_branch: str | None = None,
        pr_base: str | None = None,
        pr_state: str | None = None,
        name: str | None = None,
        status: str | None = None,
        priority: int | None = None,
        description: str | None = None,
        markdown_content: str | None = None,
        comment: str | None = None,
        pr_summary: bool | None = None,
        checklist: str | None = None,
        add_items: list[str] | None = None,
        check_items: list[str] | None = None,
        backlink_mode: str | None = None,
        no_backlink: bool | None = None,
        pr_title_prefix: str | None = None,
        custom_task_ids: bool | None = None,
        team_id: str | None = None,
        live: bool = False,
    ) -> dict[str, Any]:
        """Sync GitHub development state into a ClickUp task. Defaults to dry-run."""
        return _run_mcp_toolchain(
            "dev-sync",
            _payload_without_none(
                task_id=task_id,
                repo=repo,
                mode=mode,
                branch=branch,
                latest_commit=latest_commit,
                pr_url=pr_url,
                pr_title=pr_title,
                pr_number=pr_number,
                pr_branch=pr_branch,
                pr_base=pr_base,
                pr_state=pr_state,
                name=name,
                status=status,
                priority=priority,
                description=description,
                markdown_content=markdown_content,
                comment=comment,
                pr_summary=pr_summary,
                checklist=checklist,
                add_items=add_items,
                check_items=check_items,
                backlink_mode=backlink_mode,
                no_backlink=no_backlink,
                pr_title_prefix=pr_title_prefix,
                custom_task_ids=custom_task_ids,
                team_id=team_id,
            ),
            live=live,
        )

    @server.tool()
    def clickup_agent_work_log(
        task_id: str,
        checklist: str | None = None,
        add_items: list[str] | None = None,
        checks: list[str] | None = None,
        custom_task_ids: bool | None = None,
        team_id: str | None = None,
        live: bool = False,
    ) -> dict[str, Any]:
        """Upsert Action Items or Verification checklist state. Defaults to dry-run."""
        return _run_mcp_toolchain(
            "work-log",
            _payload_without_none(
                task_id=task_id,
                checklist=checklist,
                add_items=add_items,
                checks=checks,
                custom_task_ids=custom_task_ids,
                team_id=team_id,
            ),
            live=live,
        )

    @server.tool()
    def clickup_agent_decision_log(
        task_id: str,
        decision: str,
        context: str | None = None,
        alternatives: str | None = None,
        source: str | None = None,
        pr_url: str | None = None,
        commit: str | None = None,
        custom_task_ids: bool | None = None,
        team_id: str | None = None,
        live: bool = False,
    ) -> dict[str, Any]:
        """Append a decision record comment. Defaults to dry-run."""
        return _run_mcp_toolchain(
            "decision-log",
            _payload_without_none(
                task_id=task_id,
                decision=decision,
                context=context,
                alternatives=alternatives,
                source=source,
                pr_url=pr_url,
                commit=commit,
                custom_task_ids=custom_task_ids,
                team_id=team_id,
            ),
            live=live,
        )

    @server.tool()
    def clickup_agent_hotfix_doc(
        list_id: str,
        title: str,
        pr_url: str,
        problem: str,
        fix: str,
        branch: str | None = None,
        merge_commit: str | None = None,
        changed_files: list[str] | None = None,
        validation: str | None = None,
        domain_tag: str | None = None,
        status: str | None = None,
        priority: int | None = None,
        live: bool = False,
    ) -> dict[str, Any]:
        """Create a completed documentation task for a hotfix PR. Defaults to dry-run."""
        return _run_mcp_toolchain(
            "hotfix-doc",
            _payload_without_none(
                list_id=list_id,
                title=title,
                pr_url=pr_url,
                problem=problem,
                fix=fix,
                branch=branch,
                merge_commit=merge_commit,
                changed_files=changed_files,
                validation=validation,
                domain_tag=domain_tag,
                status=status,
                priority=priority,
            ),
            live=live,
        )

    return server


def run() -> None:
    """Run the MCP server over stdio for Cursor."""
    create_server().run()
