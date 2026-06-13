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
        "clickup_agent_run_operation",
        "clickup_agent_search",
        "clickup_agent_list_hierarchy",
        "clickup_agent_get_task",
        "clickup_agent_task_statuses",
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
        "clickup_agent_sync_checklist",
        "clickup_agent_subtasks",
        "clickup_agent_tags",
        "clickup_agent_timer",
        "clickup_agent_dev_pr",
        "clickup_agent_dev_sync",
        "clickup_agent_work_log",
        "clickup_agent_decision_log",
        "clickup_agent_hotfix_doc",
    } <= names


def test_mcp_tooling_plan_omits_operation_samples_by_default() -> None:
    server = create_server()
    plan = server._tool_manager._tools["clickup_agent_tooling_plan"].fn()

    assert "sample_operations" not in plan
    assert len(json.dumps(plan)) < 5000


def test_mcp_tooling_plan_labels_generated_operations_and_curated_wrappers() -> None:
    server = create_server()
    plan = server._tool_manager._tools["clickup_agent_tooling_plan"].fn()

    commands = set(plan["implemented_commands"])

    assert "clickup-agent tools list (generated OpenAPI operations)" in commands
    assert "clickup-agent hotkeys list (curated wrappers)" in commands
    assert "clickup-agent run get-task" in commands
    assert "clickup-agent run task-statuses" in commands
    assert "clickup-agent run sync-checklist" in commands


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
        ("update-task", {"task_id": "abc", "name": "Renamed", "status": "done"}, "UpdateTask"),
        ("assign", {"task_id": "abc", "assignees": [42]}, "UpdateTask"),
        ("assign-me", {"task_id": "abc"}, "GetAuthorizedUser"),
        ("set-due-date", {"task_id": "abc", "due_date_iso": "2026-05-01"}, "UpdateTask"),
        ("comment", {"task_id": "abc", "text": "Ready"}, "CreateTaskComment"),
        ("edit-comment", {"comment_id": "cmt", "text": "Updated", "assignee": 42, "resolved": True}, "UpdateComment"),
        (
            "create-checklist",
            {"task_id": "abc", "name": "Launch", "items": ["Smoke test"], "resolved": True},
            "CreateChecklist",
        ),
        ("create-checklist-item", {"checklist_id": "chk", "name": "Verify"}, "CreateChecklistItem"),
        ("check-item", {"checklist_id": "chk", "item_id": "it", "resolved": True}, "EditChecklistItem"),
        (
            "sync-checklist",
            {"task_id": "abc", "name": "Launch", "items": [{"id": "it", "name": "Verify"}], "resolve_all": True},
            "GetTask",
        ),
        ("tags", {"task_id": "abc", "add": ["review"]}, "AddTagToTask"),
        ("timer", {"action": "start", "team_id": "456", "task_id": "abc"}, "StartatimeEntry"),
        (
            "dev-sync",
            {
                "task_id": "abc",
                "branch": "feature/task",
                "pr_url": "https://github.com/acme/repo/pull/12",
                "pr_number": 12,
                "mode": "bidirectional",
            },
            "GetTask",
        ),
        ("work-log", {"task_id": "abc", "add_items": ["Run pytest"]}, "GetTask"),
        ("decision-log", {"task_id": "abc", "decision": "Switched X to Y"}, "CreateTaskComment"),
        (
            "hotfix-doc",
            {
                "list_id": "123",
                "title": "Fix PR docs",
                "pr_url": "https://github.com/acme/repo/pull/12",
                "branch": "hotfix/docs",
                "problem": "Docs missed the changed endpoint.",
                "fix": "Documented the endpoint.",
            },
            "CreateTask",
        ),
    ]

    for name, payload, operation_id in cases:
        result = _run_mcp_toolchain(name, payload)

        assert result["ok"] is True
        assert result["dry_run"] is True
        assert operation_id in [operation["operation_id"] for operation in result["operations"]]


def test_mcp_dev_pr_returns_compact_state(monkeypatch) -> None:
    class FakeResult:
        def to_dict(self) -> dict:
            return {"state": "not_found", "branch": "feature/task", "remote": "origin", "pr": None}

    monkeypatch.setattr("clickup_agent.mcp_server.inspect_dev_pr", lambda cwd=None, timeout=10.0: FakeResult())

    server = create_server()
    result = server._tool_manager._tools["clickup_agent_dev_pr"].fn(timeout=2.0, repo="/tmp/repo")

    assert result == {"state": "not_found", "branch": "feature/task", "remote": "origin", "pr": None}


def test_mcp_new_wrappers_forward_payloads_and_default_writes_to_dry_run(monkeypatch) -> None:
    calls: list[tuple[str, list[str]]] = []

    class FakeResult:
        def __init__(self, name: str, argv: list[str]) -> None:
            self.name = name
            self.argv = argv

        def to_dict(self) -> dict:
            return {
                "toolchain": self.name,
                "source": "curated_wrapper",
                "requested_name": self.name,
                "resolved_name": self.name,
                "dry_run": "--dry-run" in self.argv,
                "operations": [],
                "response": {"checklist_item": {"id": "item-1"}, "created_items": [{"id": "item-1"}]},
            }

    class FakeRunner:
        def run(self, name: str, argv: list[str]) -> FakeResult:
            calls.append((name, argv))
            return FakeResult(name, argv)

    monkeypatch.setattr("clickup_agent.mcp_server.ToolchainRunner", FakeRunner)

    server = create_server()
    update = server._tool_manager._tools["clickup_agent_update_task"].fn(
        task_id="task-1",
        status="done",
    )
    create = server._tool_manager._tools["clickup_agent_create_checklist"].fn(
        task_id="task-1",
        name="Launch",
        items=["Smoke test"],
        resolved=True,
    )
    sync = server._tool_manager._tools["clickup_agent_sync_checklist"].fn(
        task_id="task-1",
        name="Launch",
        items=[{"id": "item-1", "name": "Smoke test", "resolved": True}],
        resolve_all=True,
    )
    hotfix = server._tool_manager._tools["clickup_agent_hotfix_doc"].fn(
        list_id="123",
        title="Fix PR docs",
        pr_url="https://github.com/acme/repo/pull/12",
        branch="hotfix/docs",
        problem="Docs missed the changed endpoint.",
        fix="Documented the endpoint.",
        changed_files=["README.md"],
        validation="uv run pytest",
    )

    assert update["ok"] is True
    assert create["dry_run"] is True
    assert sync["dry_run"] is True
    assert hotfix["dry_run"] is True
    assert create["response"]["checklist_item"]["id"] == "item-1"
    assert create["response"]["created_items"][0]["id"] == "item-1"

    update_payload = json.loads(calls[0][1][calls[0][1].index("--json") + 1])
    create_payload = json.loads(calls[1][1][calls[1][1].index("--json") + 1])
    sync_payload = json.loads(calls[2][1][calls[2][1].index("--json") + 1])
    hotfix_payload = json.loads(calls[3][1][calls[3][1].index("--json") + 1])

    assert calls == [
        ("update-task", calls[0][1]),
        ("create-checklist", calls[1][1]),
        ("sync-checklist", calls[2][1]),
        ("hotfix-doc", calls[3][1]),
    ]
    assert calls[0][1][0] == "--dry-run"
    assert calls[1][1][0] == "--dry-run"
    assert calls[2][1][0] == "--dry-run"
    assert calls[3][1][0] == "--dry-run"
    assert update_payload == {"task_id": "task-1", "status": "done"}
    assert create_payload == {
        "task_id": "task-1",
        "name": "Launch",
        "items": ["Smoke test"],
        "resolved": True,
    }
    assert sync_payload == {
        "task_id": "task-1",
        "name": "Launch",
        "items": [{"id": "item-1", "name": "Smoke test", "resolved": True}],
        "resolve_all": True,
    }
    assert hotfix_payload == {
        "list_id": "123",
        "title": "Fix PR docs",
        "pr_url": "https://github.com/acme/repo/pull/12",
        "branch": "hotfix/docs",
        "problem": "Docs missed the changed endpoint.",
        "fix": "Documented the endpoint.",
        "changed_files": ["README.md"],
        "validation": "uv run pytest",
    }


def test_mcp_get_task_and_status_wrappers_default_to_live_reads(monkeypatch) -> None:
    calls: list[tuple[str, list[str]]] = []

    class FakeResult:
        def __init__(self, name: str, argv: list[str]) -> None:
            self.name = name
            self.argv = argv

        def to_dict(self) -> dict:
            return {
                "toolchain": self.name,
                "source": "curated_wrapper",
                "requested_name": self.name,
                "resolved_name": self.name,
                "dry_run": "--dry-run" in self.argv,
                "operations": [],
            }

    class FakeRunner:
        def run(self, name: str, argv: list[str]) -> FakeResult:
            calls.append((name, argv))
            return FakeResult(name, argv)

    monkeypatch.setattr("clickup_agent.mcp_server.ToolchainRunner", FakeRunner)

    server = create_server()
    task = server._tool_manager._tools["clickup_agent_get_task"].fn(
        task_id="task-1",
        summary=True,
        fields=["id", "url", "status"],
    )
    statuses = server._tool_manager._tools["clickup_agent_task_statuses"].fn(task_id="task-1")

    task_payload = json.loads(calls[0][1][calls[0][1].index("--json") + 1])
    statuses_payload = json.loads(calls[1][1][calls[1][1].index("--json") + 1])

    assert task["ok"] is True
    assert statuses["ok"] is True
    assert calls[0][0] == "get-task"
    assert calls[1][0] == "task-statuses"
    assert calls[0][1][0] == "--live"
    assert calls[1][1][0] == "--live"
    assert task_payload == {"task_id": "task-1", "summary": True, "fields": ["id", "url", "status"]}
    assert statuses_payload == {"task_id": "task-1"}


def test_mcp_generated_operation_runner_uses_catalog_fallback() -> None:
    server = create_server()
    result = server._tool_manager._tools["clickup_agent_run_operation"].fn(
        operation="DeleteChecklist",
        payload={"checklist_id": "chk"},
    )

    assert result["ok"] is True
    assert result["toolchain"] == "delete-checklist"
    assert result["dry_run"] is True
    assert result["operations"][0]["operation_id"] == "DeleteChecklist"
    assert result["operations"][0]["path"] == "/v2/checklist/chk"


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
