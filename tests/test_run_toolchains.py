from __future__ import annotations

import json

import httpx

from clickup_agent.client import ClickUpClient
from clickup_agent.cli import main
from clickup_agent.config import ClickUpConfig
from clickup_agent.toolchains import ToolchainRunner


def _json_output(capsys) -> dict:
    return json.loads(capsys.readouterr().out)


def test_create_task_dry_run_from_cli(capsys) -> None:
    assert main(["run", "create-task", "--dry-run", "--list-id", "123", "--name", "Ship it"]) == 0

    payload = _json_output(capsys)

    assert payload["dry_run"] is True
    assert payload["operations"][0]["operation_id"] == "CreateTask"
    assert payload["operations"][0]["path"] == "/v2/list/123/task"
    assert payload["operations"][0]["json"]["name"] == "Ship it"


def test_update_comment_tag_and_timer_dry_runs(capsys) -> None:
    commands = [
        ["run", "set-status", "--dry-run", "--task-id", "abc", "--status", "in progress"],
        ["run", "assign", "--dry-run", "--task-id", "abc", "--assignee", "42", "--mode", "add"],
        ["run", "set-due-date", "--dry-run", "--task-id", "abc", "--due-date", "2026-05-01"],
        ["run", "comment", "--dry-run", "--task-id", "abc", "--text", "Ready"],
        ["run", "tags", "--dry-run", "--task-id", "abc", "--add", "review", "--remove", "stale"],
        ["run", "timer", "--dry-run", "--action", "start", "--team-id", "456", "--task-id", "abc"],
    ]

    for command in commands:
        assert main(command) == 0
        payload = _json_output(capsys)
        assert payload["dry_run"] is True
        assert payload["operations"]


def test_create_task_live_execution_uses_mocked_http() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.headers["authorization"] == "pk_test"
        assert request.method == "POST"
        assert request.url.path == "/api/v2/list/123/task"
        assert json.loads(request.content) == {"name": "Ship it"}
        return httpx.Response(200, json={"id": "task-1"})

    runner = ToolchainRunner(
        client_factory=lambda _: ClickUpClient(
            ClickUpConfig(api_key="pk_test"),
            transport=httpx.MockTransport(handler),
        )
    )

    result = runner.run("create-task", ["--list-id", "123", "--name", "Ship it"])

    assert len(requests) == 1
    assert result.response == {"id": "task-1"}
    assert result.operations[0]["operation_id"] == "CreateTask"
