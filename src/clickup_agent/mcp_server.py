"""Minimal MCP server for Cursor and other LLM clients.

The server exposes safe bootstrap tools first: clients can verify that the
agent is installed, inspect local configuration status, and discover the
planned ClickUp tool surface before full ClickUp API tools are implemented.
"""

from __future__ import annotations

import os
from typing import Any

from mcp.server.fastmcp import FastMCP

from . import __version__
from .config import config_status
from .registry import load_catalog

SERVER_NAME = "clickup-agent"


def _configure_environment(env_file: str | None = None) -> dict[str, Any]:
    """Load optional env file and return redacted configuration status."""
    status = config_status(env_file or os.getenv("CLICKUP_ENV_FILE"))
    return {
        "version": __version__,
        **status,
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

    return server


def run() -> None:
    """Run the MCP server over stdio for Cursor."""
    create_server().run()
