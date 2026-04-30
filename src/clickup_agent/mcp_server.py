"""Minimal MCP server for Cursor and other LLM clients.

The server exposes safe bootstrap tools first: clients can verify that the
agent is installed, inspect local configuration status, and discover the
planned ClickUp tool surface before full ClickUp API tools are implemented.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from . import __version__
from .cli import _load_env_file

SERVER_NAME = "clickup-agent"


def _configure_environment(env_file: str | None = None) -> dict[str, Any]:
    """Load optional env file and return redacted configuration status."""
    selected_env_file = env_file or os.getenv("CLICKUP_ENV_FILE")
    _load_env_file(selected_env_file)
    return {
        "version": __version__,
        "env_file": str(Path(selected_env_file).expanduser()) if selected_env_file else None,
        "clickup_api_key_configured": bool(os.getenv("CLICKUP_API_KEY")),
        "clickup_workspace_id_configured": bool(os.getenv("CLICKUP_WORKSPACE_ID")),
        "clickup_webhook_secret_configured": bool(os.getenv("CLICKUP_WEBHOOK_SECRET")),
    }


def create_server() -> FastMCP:
    """Create the MCP server instance and register bootstrap tools."""
    server = FastMCP(SERVER_NAME)

    @server.tool()
    def clickup_agent_status(env_file: str | None = None) -> dict[str, Any]:
        """Check whether clickup-agent is installed and locally configured."""
        return _configure_environment(env_file)

    @server.tool()
    def clickup_agent_tooling_plan() -> dict[str, Any]:
        """Return the planned native ClickUp toolsets for this agent."""
        return {
            "command": "clickup-agent",
            "planned_toolsets": [
                "clickup_core",
                "clickup_hierarchy",
                "clickup_tasks",
                "clickup_comments",
                "clickup_people",
                "clickup_search",
                "clickup_docs",
                "clickup_chat",
                "clickup_files",
                "clickup_time",
                "clickup_admin",
            ],
            "first_workflows": [
                "search workspace",
                "create task",
                "set task status",
                "assign task",
                "set due date",
                "comment on task",
                "create subtasks",
                "set priority",
                "add or remove tags",
                "start or stop timer",
            ],
        }

    return server


def run() -> None:
    """Run the MCP server over stdio for Cursor."""
    create_server().run()
