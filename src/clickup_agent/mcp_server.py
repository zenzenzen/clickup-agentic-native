"""MCP server for Cursor and other LLM clients.

The server exposes bootstrap/status tools plus the first curated ClickUp
toolchains. Write workflows default to dry-run previews unless callers
explicitly request live execution.
"""

from __future__ import annotations

import os
import json
from typing import Any

from mcp.server.fastmcp import FastMCP

from . import __version__
from .config import config_status
from .registry import load_catalog
from .toolchains import ToolchainError, ToolchainRunner

SERVER_NAME = "clickup-agent"


def _configure_environment(env_file: str | None = None) -> dict[str, Any]:
    """Load optional env file and return redacted configuration status."""
    status = config_status(env_file or os.getenv("CLICKUP_ENV_FILE"))
    return {
        "version": __version__,
        **status,
    }


def _payload_without_none(**items: Any) -> dict[str, Any]:
    return {key: value for key, value in items.items() if value is not None}


def _run_mcp_toolchain(
    name: str,
    payload: dict[str, Any],
    *,
    live: bool = False,
    env_file: str | None = None,
) -> dict[str, Any]:
    argv: list[str] = []
    if not live:
        argv.append("--dry-run")
    if env_file:
        argv.extend(["--env-file", env_file])
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
    def clickup_agent_status(env_file: str | None = None) -> dict[str, Any]:
        """Check whether clickup-agent is installed and locally configured."""
        return _configure_environment(env_file)

    @server.tool()
    def clickup_agent_tooling_plan() -> dict[str, Any]:
        """Return the generated and curated native ClickUp tool surface."""
        catalog = load_catalog()
        return {
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
                "clickup-agent run create-task",
                "clickup-agent run set-status",
                "clickup-agent run assign",
                "clickup-agent run set-due-date",
                "clickup-agent run comment",
                "clickup-agent run tags",
                "clickup-agent run timer",
            ],
            "hotkeys": [
                toolchain.to_dict()
                for toolchain in catalog.toolchains
            ],
            "sample_operations": [operation.to_dict() for operation in catalog.operations[:10]],
        }

    @server.tool()
    def clickup_agent_search(
        query: str | None = None,
        list_id: str | None = None,
        workspace_id: str | None = None,
        team_id: str | None = None,
        page: int | None = None,
        include_closed: bool | None = None,
        live: bool = True,
        env_file: str | None = None,
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
            env_file=env_file,
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
        env_file: str | None = None,
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
            env_file=env_file,
        )

    @server.tool()
    def clickup_agent_set_status(
        task_id: str,
        status: str,
        custom_task_ids: bool | None = None,
        team_id: str | None = None,
        live: bool = False,
        env_file: str | None = None,
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
            env_file=env_file,
        )

    @server.tool()
    def clickup_agent_assign(
        task_id: str,
        assignees: list[int],
        mode: str = "add",
        custom_task_ids: bool | None = None,
        team_id: str | None = None,
        live: bool = False,
        env_file: str | None = None,
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
            env_file=env_file,
        )

    @server.tool()
    def clickup_agent_set_due_date(
        task_id: str,
        due_date: str,
        due_date_time: bool | None = None,
        custom_task_ids: bool | None = None,
        team_id: str | None = None,
        live: bool = False,
        env_file: str | None = None,
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
            env_file=env_file,
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
        env_file: str | None = None,
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
            env_file=env_file,
        )

    @server.tool()
    def clickup_agent_tags(
        task_id: str,
        add: list[str] | None = None,
        remove: list[str] | None = None,
        custom_task_ids: bool | None = None,
        team_id: str | None = None,
        live: bool = False,
        env_file: str | None = None,
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
            env_file=env_file,
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
        env_file: str | None = None,
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
            env_file=env_file,
        )

    return server


def run() -> None:
    """Run the MCP server over stdio for Cursor."""
    create_server().run()
