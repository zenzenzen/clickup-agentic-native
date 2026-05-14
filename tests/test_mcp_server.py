from __future__ import annotations

import asyncio
import json

import httpx

from clickup_agent.client import ClickUpClient
from clickup_agent.config import ClickUpConfig
from clickup_agent.mcp_server import _run_mcp_toolchain, create_server


def test_mcp_status_redacts_home_path(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    env_file = tmp_path / ".config" / "clickup-agent" / ".env"
    env_file.parent.mkdir(parents=True)
    env_file.write_text("CLICKUP_API_KEY=pk_test\n", encoding="utf-8")

    server = create_server()
    status = server._tool_manager._tools["clickup_agent_status"].fn()

    assert status["env_file"] == "~/.config/clickup-agent/.env"
    assert str(tmp_path) not in json.dumps(status)


def test_mcp_registers_direct_clickup_tools() -> None:
    async def list_tool_names() -> set[str]:
        tools = await create_server().list_tools()
        return {tool.name for tool in tools}

    names = asyncio.run(list_tool_names())

    assert {
        "clickup_agent_status",
        "clickup_agent_tooling_plan",
        "clickup_agent_search",
        "clickup_agent_list_hierarchy",
        "clickup_agent_resolve_user",
        "clickup_agent_resolve_task",
        "clickup_agent_inspect_task",
        "clickup_agent_audit_assigned",
        "clickup_agent_link_resource",
        "clickup_agent_apply_task_template",
        "clickup_agent_create_task",
        "clickup_agent_create_subtask",
        "clickup_agent_set_status",
        "clickup_agent_set_description",
        "clickup_agent_update_task",
        "clickup_agent_assign",
        "clickup_agent_assign_me",
        "clickup_agent_set_due_date",
        "clickup_agent_comment",
        "clickup_agent_edit_comment",
        "clickup_agent_create_checklist",
        "clickup_agent_create_checklist_item",
        "clickup_agent_check_item",
        "clickup_agent_subtasks",
        "clickup_agent_tags",
        "clickup_agent_timer",
    } <= names


def test_mcp_tooling_plan_omits_operation_samples_by_default() -> None:
    server = create_server()
    plan = server._tool_manager._tools["clickup_agent_tooling_plan"].fn()

    assert "sample_operations" not in plan
    assert len(json.dumps(plan)) < 5000


def test_mcp_tooling_plan_uses_compact_operation_samples_when_requested() -> None:
    server = create_server()
    plan = server._tool_manager._tools["clickup_agent_tooling_plan"].fn(include_samples=True)

    sample = plan["sample_operations"][0]

    assert "request_schema" not in sample
    assert "response_schema" not in sample
    assert {"name", "method", "path", "tags", "write", "summary"} <= set(sample)


def test_mcp_write_toolchains_default_to_dry_run() -> None:
    cases = [
        ("create-task", {"list_id": "123", "name": "Ship it"}, "CreateTask"),
        ("create-subtask", {"list_id": "123", "parent": "abc", "name": "Sub"}, "CreateTask"),
        ("set-status", {"task_id": "abc", "status": "done"}, "UpdateTask"),
        ("set-description", {"task_id": "abc", "description": "Plain"}, "UpdateTask"),
        ("update-task", {"task_id": "abc", "name": "Renamed"}, "UpdateTask"),
        ("assign", {"task_id": "abc", "assignees": [42]}, "UpdateTask"),
        ("assign-me", {"task_id": "abc"}, "GetAuthorizedUser"),
        ("set-due-date", {"task_id": "abc", "due_date_iso": "2026-05-01"}, "UpdateTask"),
        ("comment", {"task_id": "abc", "text": "Ready"}, "CreateTaskComment"),
        ("edit-comment", {"comment_id": "cmt", "text": "Updated", "assignee": 42, "resolved": True}, "UpdateComment"),
        ("create-checklist", {"task_id": "abc", "name": "Launch"}, "CreateChecklist"),
        ("create-checklist-item", {"checklist_id": "chk", "name": "Verify"}, "CreateChecklistItem"),
        ("check-item", {"checklist_id": "chk", "item_id": "it", "resolved": True}, "EditChecklistItem"),
        ("link-resource", {"task_id": "abc", "url": "https://github.com/acme/pr/1"}, "GetTask"),
        ("apply-task-template", {"task_id": "abc", "context": "Why"}, "GetTask"),
        ("tags", {"task_id": "abc", "add": ["review"]}, "AddTagToTask"),
        ("timer", {"action": "start", "team_id": "456", "task_id": "abc"}, "StartatimeEntry"),
    ]

    for name, payload, operation_id in cases:
        result = _run_mcp_toolchain(name, payload)

        assert result["ok"] is True
        assert result["dry_run"] is True
        assert result["operations"][0]["operation_id"] == operation_id


def test_mcp_live_toolchain_uses_runner_client(monkeypatch) -> None:
    requests: list[httpx.Request] = []

    def client_factory() -> ClickUpClient:
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


def test_mcp_list_hierarchy_live_execution_uses_runner_client(monkeypatch) -> None:
    requests: list[httpx.Request] = []

    def client_factory() -> ClickUpClient:
        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            if request.url.path == "/api/v2/team/123/space":
                return httpx.Response(200, json={"spaces": []})
            return httpx.Response(404, request=request)

        return ClickUpClient(ClickUpConfig(api_key="pk_test"), transport=httpx.MockTransport(handler))

    monkeypatch.setattr("clickup_agent.toolchains.ClickUpClient.from_environment", client_factory)

    result = _run_mcp_toolchain("list-hierarchy", {"team_id": "123"}, live=True)

    assert result["ok"] is True
    assert result["dry_run"] is False
    assert result["response"] == {"workspaces": [{"id": "123", "name": None, "spaces": []}]}
    assert requests[0].method == "GET"
    assert requests[0].url.path == "/api/v2/team/123/space"


def test_mcp_resolution_tools_expose_dry_run_wrappers() -> None:
    user_result = _run_mcp_toolchain("resolve-user", {"current_user": True})
    task_result = _run_mcp_toolchain("resolve-task", {"url": "https://app.clickup.com/t/abc"})
    inspect_result = _run_mcp_toolchain("inspect-task", {"task_id": "abc", "include_comments": True})
    audit_result = _run_mcp_toolchain("audit-assigned", {"team_id": "123", "assignee": "42"})

    assert user_result["ok"] is True
    assert user_result["dry_run"] is True
    assert user_result["operations"][0]["operation_id"] == "GetAuthorizedUser"

    assert task_result["ok"] is True
    assert task_result["dry_run"] is True
    assert task_result["operations"][0]["operation_id"] == "GetTask"
    assert task_result["operations"][0]["path"] == "/v2/task/abc"

    assert inspect_result["ok"] is True
    assert inspect_result["dry_run"] is True
    assert [operation["operation_id"] for operation in inspect_result["operations"]] == ["GetTask", "GetTaskComments"]

    assert audit_result["ok"] is True
    assert audit_result["dry_run"] is True
    assert audit_result["operations"][0]["operation_id"] == "GetFilteredTeamTasks"


def test_mcp_resolve_task_live_execution_uses_runner_client(monkeypatch) -> None:
    requests: list[httpx.Request] = []

    def client_factory() -> ClickUpClient:
        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return httpx.Response(200, json={"id": "abc", "name": "Ship it"})

        return ClickUpClient(ClickUpConfig(api_key="pk_test"), transport=httpx.MockTransport(handler))

    monkeypatch.setattr("clickup_agent.toolchains.ClickUpClient.from_environment", client_factory)

    result = _run_mcp_toolchain("resolve-task", {"task_id": "abc"}, live=True)

    assert result["ok"] is True
    assert result["dry_run"] is False
    assert result["response"] == {"mode": "task_id", "task": {"id": "abc", "name": "Ship it"}}
    assert requests[0].method == "GET"
    assert requests[0].url.path == "/api/v2/task/abc"


def test_mcp_inspect_and_audit_live_execution_use_runner_client(monkeypatch) -> None:
    requests: list[httpx.Request] = []

    def client_factory() -> ClickUpClient:
        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            if request.url.path == "/api/v2/task/abc":
                return httpx.Response(200, json={"id": "abc", "name": "Ship it", "description": ""})
            if request.url.path == "/api/v2/task/abc/comment":
                return httpx.Response(200, json={"comments": []})
            if request.url.path == "/api/v2/team/123/task":
                return httpx.Response(200, json={"tasks": [{"id": "abc", "name": "Ship it", "description": ""}]})
            return httpx.Response(404, request=request)

        return ClickUpClient(ClickUpConfig(api_key="pk_test"), transport=httpx.MockTransport(handler))

    monkeypatch.setattr("clickup_agent.toolchains.ClickUpClient.from_environment", client_factory)

    inspect_result = _run_mcp_toolchain("inspect-task", {"task_id": "abc", "include_comments": True}, live=True)
    audit_result = _run_mcp_toolchain("audit-assigned", {"team_id": "123", "assignee": "42"}, live=True)

    assert inspect_result["ok"] is True
    assert inspect_result["response"]["findings"] == [
        "missing-description",
        "missing-due-date",
        "missing-assignee",
        "missing-points",
        "missing-time-estimate",
        "missing-checklist",
        "missing-external-link",
    ]
    assert audit_result["ok"] is True
    assert audit_result["response"]["tasks_with_findings"] == 1
    assert [request.url.path for request in requests] == [
        "/api/v2/task/abc",
        "/api/v2/task/abc/comment",
        "/api/v2/team/123/task",
    ]


def test_mcp_subtasks_live_execution_uses_runner_client(monkeypatch) -> None:
    requests: list[httpx.Request] = []

    def client_factory() -> ClickUpClient:
        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return httpx.Response(200, json={"id": "abc", "subtasks": [{"id": "sub-1"}]})

        return ClickUpClient(ClickUpConfig(api_key="pk_test"), transport=httpx.MockTransport(handler))

    monkeypatch.setattr("clickup_agent.toolchains.ClickUpClient.from_environment", client_factory)

    result = _run_mcp_toolchain("subtasks", {"task_id": "abc"}, live=True)

    assert result["ok"] is True
    assert result["dry_run"] is False
    assert result["response"] == {"task_id": "abc", "subtasks": [{"id": "sub-1"}]}
    assert requests[0].method == "GET"
    assert requests[0].url.path == "/api/v2/task/abc"


def test_mcp_toolchain_errors_are_structured() -> None:
    result = _run_mcp_toolchain("create-task", {"list_id": "123"})

    assert result["ok"] is False
    assert "'name' is a required property" in result["error"]
