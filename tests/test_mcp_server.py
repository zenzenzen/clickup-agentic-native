from __future__ import annotations

import asyncio

import httpx

from clickup_agent.client import ClickUpClient
from clickup_agent.config import ClickUpConfig
from clickup_agent.mcp_server import _run_mcp_toolchain, create_server


def test_mcp_registers_direct_clickup_tools() -> None:
    async def list_tool_names() -> set[str]:
        tools = await create_server().list_tools()
        return {tool.name for tool in tools}

    names = asyncio.run(list_tool_names())

    assert {
        "clickup_agent_status",
        "clickup_agent_tooling_plan",
        "clickup_agent_search",
        "clickup_agent_create_task",
        "clickup_agent_set_status",
        "clickup_agent_assign",
        "clickup_agent_set_due_date",
        "clickup_agent_comment",
        "clickup_agent_tags",
        "clickup_agent_timer",
    } <= names


def test_mcp_write_toolchains_default_to_dry_run() -> None:
    result = _run_mcp_toolchain("create-task", {"list_id": "123", "name": "Ship it"})

    assert result["ok"] is True
    assert result["dry_run"] is True
    assert result["operations"][0]["operation_id"] == "CreateTask"
    assert result["operations"][0]["path"] == "/v2/list/123/task"


def test_mcp_live_toolchain_uses_runner_client(monkeypatch) -> None:
    requests: list[httpx.Request] = []

    def client_factory(_: str | None) -> ClickUpClient:
        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return httpx.Response(200, json={"id": "task-1"})

        return ClickUpClient(ClickUpConfig(api_key="pk_test"), transport=httpx.MockTransport(handler))

    monkeypatch.setattr("clickup_agent.toolchains.ClickUpClient.from_environment", client_factory)

    result = _run_mcp_toolchain("create-task", {"list_id": "123", "name": "Ship it"}, live=True)

    assert result["ok"] is True
    assert result["dry_run"] is False
    assert result["response"] == {"id": "task-1"}
    assert requests[0].method == "POST"
    assert requests[0].url.path == "/api/v2/list/123/task"


def test_mcp_toolchain_errors_are_structured() -> None:
    result = _run_mcp_toolchain("create-task", {"list_id": "123"})

    assert result["ok"] is False
    assert "'name' is a required property" in result["error"]
