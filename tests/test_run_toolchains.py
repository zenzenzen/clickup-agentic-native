from __future__ import annotations

import json

import httpx

from clickup_agent.client import ClickUpClient
from clickup_agent.cli import main
from clickup_agent.config import ClickUpConfig
from clickup_agent.registry import load_catalog
from clickup_agent.requests import OperationInputError, build_operation_request
from clickup_agent.toolchains import ToolchainRunner
from clickup_agent.validation import InputValidationError, validate_operation_body


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


def test_unknown_top_level_payload_keys_are_rejected() -> None:
    operation = load_catalog().get_operation("CreateTask")

    try:
        build_operation_request(operation, {"list_id": "123", "name": "Ship it", "unexpected": True})
    except OperationInputError as exc:
        assert "Unknown input field(s)" in str(exc)
        assert "unexpected" in str(exc)
    else:
        raise AssertionError("unknown payload key was accepted")


def test_required_request_body_is_validated_even_when_empty() -> None:
    operation = load_catalog().get_operation("CreateTask")
    request = build_operation_request(operation, {"list_id": "123"})

    assert request.json_body == {}
    try:
        validate_operation_body(operation, request.json_body)
    except InputValidationError as exc:
        assert "'name' is a required property" in str(exc)
    else:
        raise AssertionError("empty required body was accepted")


def test_unknown_top_level_body_keys_are_rejected() -> None:
    operation = load_catalog().get_operation("UpdateTask")

    try:
        validate_operation_body(operation, {"status": "done", "unexpected": True})
    except InputValidationError as exc:
        assert "unknown field(s): unexpected" in str(exc)
    else:
        raise AssertionError("unknown body key was accepted")


def test_json_payload_can_satisfy_semantic_required_fields(capsys) -> None:
    assert main(["run", "set-status", "--dry-run", "--json", '{"task_id":"abc","status":"done"}']) == 0

    payload = _json_output(capsys)

    assert payload["operations"][0]["path"] == "/v2/task/abc"
    assert payload["operations"][0]["json"] == {"status": "done"}


def test_predictable_cli_errors_return_exit_2_without_traceback(capsys) -> None:
    assert main(["run", "create-task", "--dry-run", "--list-id", "123"]) == 2

    captured = capsys.readouterr()

    assert "'name' is a required property" in captured.out
    assert "Traceback" not in captured.out
    assert "Traceback" not in captured.err


def test_cli_rejects_unknown_explicit_body_keys(capsys) -> None:
    assert (
        main(
            [
                "run",
                "create-task",
                "--dry-run",
                "--json",
                '{"list_id":"123","body":{"name":"Ship it","bogus":true}}',
            ]
        )
        == 2
    )

    captured = capsys.readouterr()

    assert "unknown field(s): bogus" in captured.out
    assert "Traceback" not in captured.out
    assert "Traceback" not in captured.err


def test_date_int_and_boolean_json_values_are_coerced(capsys) -> None:
    assert (
        main(
            [
                "run",
                "set-due-date",
                "--dry-run",
                "--json",
                '{"task_id":"abc","due_date_iso":"2026-05-01","due_date_time":"false"}',
            ]
        )
        == 0
    )
    due_date_payload = _json_output(capsys)

    assert due_date_payload["operations"][0]["json"]["due_date"] == 1777593600000
    assert due_date_payload["operations"][0]["json"]["due_date_time"] is False

    assert (
        main(
            [
                "run",
                "assign",
                "--dry-run",
                "--json",
                '{"task_id":"abc","assignees":"42,43","mode":"add"}',
            ]
        )
        == 0
    )
    assign_payload = _json_output(capsys)

    assert assign_payload["operations"][0]["json"]["assignees"]["add"] == [42, 43]


def test_assign_replace_dry_run_keeps_note_outside_request_body(capsys) -> None:
    assert main(["run", "assign", "--dry-run", "--task-id", "abc", "--assignee", "42", "--mode", "replace"]) == 0

    payload = _json_output(capsys)
    update_operation = payload["operations"][1]

    assert update_operation["json"] == {"assignees": {"add": [42], "rem": []}}
    assert "note" in update_operation


def test_dry_run_search_and_timer_use_env_file_workspace_without_api_key(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.delenv("CLICKUP_API_KEY", raising=False)
    monkeypatch.delenv("CLICKUP_WORKSPACE_ID", raising=False)
    env_file = tmp_path / ".env.local"
    env_file.write_text("CLICKUP_WORKSPACE_ID=789\n", encoding="utf-8")

    assert main(["run", "search", "--dry-run", "--env-file", str(env_file), "--query", "ship"]) == 0
    search_payload = _json_output(capsys)

    assert search_payload["operations"][0]["operation_id"] == "GetFilteredTeamTasks"
    assert search_payload["operations"][0]["path"] == "/v2/team/789/task"

    assert main(["run", "timer", "--dry-run", "--env-file", str(env_file)]) == 0
    timer_payload = _json_output(capsys)

    assert timer_payload["operations"][0]["operation_id"] == "Getrunningtimeentry"
    assert timer_payload["operations"][0]["path"] == "/v2/team/789/time_entries/current"


def test_search_team_id_alias_is_consumed(capsys) -> None:
    assert main(["run", "search", "--dry-run", "--team-id", "789", "--query", "ship"]) == 0

    payload = _json_output(capsys)

    assert payload["operations"][0]["operation_id"] == "GetFilteredTeamTasks"
    assert payload["operations"][0]["path"] == "/v2/team/789/task"


def test_live_api_errors_return_cli_error_without_traceback(monkeypatch, capsys) -> None:
    monkeypatch.setenv("CLICKUP_API_KEY", "pk_test")

    def failing_client(_: str | None) -> ClickUpClient:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(400, text="bad pk_test token", request=request)

        return ClickUpClient(
            ClickUpConfig(api_key="pk_test"),
            transport=httpx.MockTransport(handler),
        )

    monkeypatch.setattr("clickup_agent.toolchains.ClickUpClient.from_environment", failing_client)

    assert main(["run", "create-task", "--list-id", "123", "--name", "Ship it"]) == 2
    captured = capsys.readouterr()

    assert "ClickUp API error (400)" in captured.out
    assert "<redacted>" in captured.out
    assert "pk_test" not in captured.out
    assert "Traceback" not in captured.out
    assert "Traceback" not in captured.err
