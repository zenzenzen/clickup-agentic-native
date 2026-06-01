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


def test_write_toolchains_default_to_dry_run_from_cli(capsys) -> None:
    assert main(["run", "create-task", "--list-id", "123", "--name", "Ship it"]) == 0

    payload = _json_output(capsys)

    assert payload["dry_run"] is True
    assert payload["operations"][0]["operation_id"] == "CreateTask"
    assert payload["operations"][0]["json"] == {"name": "Ship it"}


def test_run_rejects_conflicting_live_and_dry_run_flags(capsys) -> None:
    assert main(["run", "create-task", "--dry-run", "--live", "--list-id", "123", "--name", "Ship it"]) == 2

    captured = capsys.readouterr()

    assert "Use either --dry-run or --live" in captured.out
    assert "Traceback" not in captured.out


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


def test_list_hierarchy_dry_run_from_cli(capsys) -> None:
    assert main(["run", "list-hierarchy", "--dry-run", "--team-id", "123"]) == 0

    payload = _json_output(capsys)

    assert payload["dry_run"] is True
    assert payload["operations"][0]["operation_id"] == "GetSpaces"
    assert payload["operations"][0]["path"] == "/v2/team/123/space"
    assert "Live run expands each returned space" in payload["operations"][0]["note"]

    assert main(["run", "list-hierarchy", "--dry-run", "--folder-id", "folder-1"]) == 0
    payload = _json_output(capsys)

    assert payload["operations"][0]["operation_id"] == "GetLists"
    assert payload["operations"][0]["path"] == "/v2/folder/folder-1/list"


def test_new_task_checklist_comment_hotkeys_dry_run(capsys) -> None:
    commands = [
        (
            ["run", "create-subtask", "--dry-run", "--list-id", "123", "--parent", "abc", "--name", "Sub"],
            "CreateTask",
            "/v2/list/123/task",
            {"parent": "abc", "name": "Sub"},
        ),
        (
            ["run", "create-checklist", "--dry-run", "--task-id", "abc", "--name", "Launch"],
            "CreateChecklist",
            "/v2/task/abc/checklist",
            {"name": "Launch"},
        ),
        (
            [
                "run",
                "create-checklist-item",
                "--dry-run",
                "--checklist-id",
                "chk",
                "--name",
                "Verify",
                "--assignee",
                "42",
            ],
            "CreateChecklistItem",
            "/v2/checklist/chk/checklist_item",
            {"name": "Verify", "assignee": 42},
        ),
        (
            ["run", "check-item", "--dry-run", "--checklist-id", "chk", "--item-id", "it", "--resolved"],
            "EditChecklistItem",
            "/v2/checklist/chk/checklist_item/it",
            {"resolved": True},
        ),
        (
            ["run", "check-item", "--dry-run", "--checklist-id", "chk", "--item-id", "it", "--name", "Renamed"],
            "EditChecklistItem",
            "/v2/checklist/chk/checklist_item/it",
            {"name": "Renamed"},
        ),
        (
            ["run", "subtasks", "--dry-run", "--task-id", "abc"],
            "GetTask",
            "/v2/task/abc",
            None,
        ),
        (
            [
                "run",
                "edit-comment",
                "--dry-run",
                "--comment-id",
                "cmt",
                "--text",
                "Updated",
                "--assignee",
                "42",
                "--resolved",
            ],
            "UpdateComment",
            "/v2/comment/cmt",
            {"comment_text": "Updated", "assignee": 42, "resolved": True},
        ),
    ]

    for command, operation_id, path, expected_json in commands:
        assert main(command) == 0
        payload = _json_output(capsys)
        operation = payload["operations"][0]
        assert payload["dry_run"] is True
        assert operation["operation_id"] == operation_id
        assert operation["path"] == path
        if expected_json is not None:
            assert operation["json"] == expected_json
        if operation_id == "GetTask":
            assert operation["params"]["include_subtasks"] is True


def test_generated_operation_fallback_accepts_flags_and_defaults_writes_to_dry_run(capsys) -> None:
    assert main(["run", "DeleteChecklist", "--checklist-id", "chk"]) == 0

    delete_payload = _json_output(capsys)

    assert delete_payload["toolchain"] == "delete-checklist"
    assert delete_payload["dry_run"] is True
    assert delete_payload["operations"][0]["operation_id"] == "DeleteChecklist"
    assert delete_payload["operations"][0]["method"] == "DELETE"
    assert delete_payload["operations"][0]["path"] == "/v2/checklist/chk"

    assert (
        main(
            [
                "run",
                "EditChecklistItem",
                "--dry-run",
                "--checklist-id",
                "chk",
                "--checklist-item-id",
                "it",
                "--resolved",
            ]
        )
        == 0
    )

    edit_payload = _json_output(capsys)

    assert edit_payload["toolchain"] == "edit-checklist-item"
    assert edit_payload["operations"][0]["path"] == "/v2/checklist/chk/checklist_item/it"
    assert edit_payload["operations"][0]["json"] == {"resolved": True}


def test_set_description_dry_runs_and_validation(capsys) -> None:
    assert main(["run", "set-description", "--dry-run", "--task-id", "abc", "--description", "Plain"]) == 0
    payload = _json_output(capsys)
    assert payload["operations"][0]["operation_id"] == "UpdateTask"
    assert payload["operations"][0]["path"] == "/v2/task/abc"
    assert payload["operations"][0]["json"] == {"description": "Plain"}

    assert (
        main(
            [
                "run",
                "set-description",
                "--dry-run",
                "--task-id",
                "abc",
                "--markdown-content",
                "## Markdown",
            ]
        )
        == 0
    )
    payload = _json_output(capsys)
    assert payload["operations"][0]["json"] == {"markdown_content": "## Markdown"}

    assert main(["run", "set-description", "--dry-run", "--task-id", "abc"]) == 2
    captured = capsys.readouterr()
    assert "set-description requires --description or --markdown-content" in captured.out
    assert "Traceback" not in captured.out


def test_update_task_dry_run_coerces_fields_and_requires_change(capsys) -> None:
    assert (
        main(
            [
                "run",
                "update-task",
                "--dry-run",
                "--task-id",
                "abc",
                "--name",
                "Renamed",
                "--description",
                "Plain",
                "--markdown-content",
                "## Markdown",
                "--priority",
                "2",
                "--due-date",
                "2026-05-01",
                "--due-date-time",
                "--start-date",
                "2026-04-30",
                "--start-date-time",
                "--points",
                "3.5",
                "--time-estimate",
                "3600000",
                "--archived",
                "--parent",
                "parent-1",
            ]
        )
        == 0
    )
    payload = _json_output(capsys)
    body = payload["operations"][0]["json"]

    assert body == {
        "name": "Renamed",
        "description": "Plain",
        "markdown_content": "## Markdown",
        "priority": 2,
        "points": 3.5,
        "time_estimate": 3600000,
        "archived": True,
        "due_date_time": True,
        "start_date_time": True,
        "due_date": 1777593600000,
        "start_date": 1777507200000,
        "parent": "parent-1",
    }

    assert main(["run", "update-task", "--dry-run", "--task-id", "abc"]) == 2
    captured = capsys.readouterr()
    assert "update-task requires at least one field to change" in captured.out
    assert "Traceback" not in captured.out


def test_assign_me_dry_run_uses_placeholder(capsys) -> None:
    assert main(["run", "assign-me", "--dry-run", "--task-id", "abc"]) == 0

    payload = _json_output(capsys)
    update_operation = payload["operations"][1]

    assert payload["operations"][0]["operation_id"] == "GetAuthorizedUser"
    assert update_operation["operation_id"] == "UpdateTask"
    assert update_operation["json"] == {"assignees": {"add": ["<self>"], "rem": []}}
    assert "Live run resolves the authorized user id" in update_operation["note"]


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
        client_factory=lambda: ClickUpClient(
            ClickUpConfig(api_key="pk_test"),
            transport=httpx.MockTransport(handler),
        )
    )

    result = runner.run("create-task", ["--live", "--list-id", "123", "--name", "Ship it"])

    assert len(requests) == 1
    assert result.response == {"id": "task-1"}
    assert result.operations[0]["operation_id"] == "CreateTask"
    assert "json" not in result.operations[0]
    assert "headers" not in result.operations[0]


def test_generated_operation_fallback_live_execution_uses_mocked_http() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.method == "POST"
        assert request.url.path == "/api/v2/task/abc/checklist"
        assert json.loads(request.content) == {"name": "Launch"}
        return httpx.Response(200, json={"id": "chk"})

    runner = ToolchainRunner(
        client_factory=lambda: ClickUpClient(
            ClickUpConfig(api_key="pk_test"),
            transport=httpx.MockTransport(handler),
        )
    )

    result = runner.run("CreateChecklist", ["--live", "--task-id", "abc", "--name", "Launch"])

    assert len(requests) == 1
    assert result.toolchain == "create-checklist"
    assert result.response == {"id": "chk"}
    assert result.operations[0]["operation_id"] == "CreateChecklist"


def test_list_hierarchy_live_execution_returns_only_names_and_ids() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/api/v2/team/123/space":
            return httpx.Response(200, json={"spaces": [{"id": "space-1", "name": "Roadmap", "private": True}]})
        if request.url.path == "/api/v2/space/space-1/folder":
            return httpx.Response(200, json={"folders": [{"id": "folder-1", "name": "Engineering", "hidden": True}]})
        if request.url.path == "/api/v2/space/space-1/list":
            return httpx.Response(200, json={"lists": [{"id": "list-0", "name": "Inbox", "content": "redacted"}]})
        if request.url.path == "/api/v2/folder/folder-1/list":
            return httpx.Response(200, json={"lists": [{"id": "list-1", "name": "Sprint", "content": "redacted"}]})
        return httpx.Response(404, request=request)

    runner = ToolchainRunner(
        client_factory=lambda: ClickUpClient(
            ClickUpConfig(api_key="pk_test"),
            transport=httpx.MockTransport(handler),
        )
    )

    result = runner.run("list-hierarchy", ["--team-id", "123"])

    assert [request.url.path for request in requests] == [
        "/api/v2/team/123/space",
        "/api/v2/space/space-1/folder",
        "/api/v2/space/space-1/list",
        "/api/v2/folder/folder-1/list",
    ]
    assert result.response == {
        "workspaces": [
            {
                "id": "123",
                "name": None,
                "spaces": [
                    {
                        "id": "space-1",
                        "name": "Roadmap",
                        "lists": [{"id": "list-0", "name": "Inbox"}],
                        "folders": [
                            {
                                "id": "folder-1",
                                "name": "Engineering",
                                "lists": [{"id": "list-1", "name": "Sprint"}],
                            }
                        ],
                    }
                ],
            }
        ]
    }


def test_new_hotkeys_live_execution_uses_mocked_http() -> None:
    cases = [
        (
            "set-description",
            ["--task-id", "abc", "--description", "Plain"],
            "PUT",
            "/api/v2/task/abc",
            {"description": "Plain"},
        ),
        (
            "create-checklist",
            ["--task-id", "abc", "--name", "Launch"],
            "POST",
            "/api/v2/task/abc/checklist",
            {"name": "Launch"},
        ),
        (
            "create-checklist-item",
            ["--checklist-id", "chk", "--name", "Verify"],
            "POST",
            "/api/v2/checklist/chk/checklist_item",
            {"name": "Verify"},
        ),
        (
            "check-item",
            ["--checklist-id", "chk", "--item-id", "it", "--resolved"],
            "PUT",
            "/api/v2/checklist/chk/checklist_item/it",
            {"resolved": True},
        ),
        (
            "create-subtask",
            ["--list-id", "123", "--parent", "abc", "--name", "Sub"],
            "POST",
            "/api/v2/list/123/task",
            {"parent": "abc", "name": "Sub"},
        ),
        (
            "edit-comment",
            ["--comment-id", "cmt", "--text", "Updated", "--assignee", "42", "--resolved"],
            "PUT",
            "/api/v2/comment/cmt",
            {"comment_text": "Updated", "assignee": 42, "resolved": True},
        ),
    ]

    for name, argv, method, path, body in cases:
        requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return httpx.Response(200, json={"ok": True})

        runner = ToolchainRunner(
            client_factory=lambda: ClickUpClient(
                ClickUpConfig(api_key="pk_test"),
                transport=httpx.MockTransport(handler),
            )
        )

        result = runner.run(name, ["--live", *argv])

        assert result.dry_run is False
        assert len(requests) == 1
        assert requests[0].method == method
        assert requests[0].url.path == path
        assert json.loads(requests[0].content) == body


def test_assign_me_live_execution_resolves_authorized_user() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/api/v2/user":
            return httpx.Response(200, json={"user": {"id": 99}})
        return httpx.Response(200, json={"id": "abc"})

    runner = ToolchainRunner(
        client_factory=lambda: ClickUpClient(
            ClickUpConfig(api_key="pk_test"),
            transport=httpx.MockTransport(handler),
        )
    )

    result = runner.run("assign-me", ["--live", "--task-id", "abc"])

    assert result.response == {"id": "abc"}
    assert [request.method for request in requests] == ["GET", "PUT"]
    assert [request.url.path for request in requests] == ["/api/v2/user", "/api/v2/task/abc"]
    assert json.loads(requests[1].content) == {"assignees": {"add": [99], "rem": []}}


def test_subtasks_live_execution_filters_response() -> None:
    requests: list[httpx.Request] = []
    subtasks = [{"id": "sub-1", "name": "Sub"}]

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"id": "abc", "name": "Parent", "subtasks": subtasks})

    runner = ToolchainRunner(
        client_factory=lambda: ClickUpClient(
            ClickUpConfig(api_key="pk_test"),
            transport=httpx.MockTransport(handler),
        )
    )

    result = runner.run("subtasks", ["--task-id", "abc"])

    assert result.response == {"task_id": "abc", "subtasks": subtasks}
    assert requests[0].method == "GET"
    assert requests[0].url.path == "/api/v2/task/abc"
    assert requests[0].url.params["include_subtasks"] == "true"


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


def test_dry_run_search_and_timer_use_canonical_workspace_without_api_key(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.delenv("CLICKUP_API_KEY", raising=False)
    monkeypatch.delenv("CLICKUP_WORKSPACE_ID", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    env_file = tmp_path / ".config" / "clickup-agent" / ".env"
    env_file.parent.mkdir(parents=True)
    env_file.write_text("CLICKUP_WORKSPACE_ID=789\n", encoding="utf-8")

    assert main(["run", "search", "--dry-run", "--query", "ship"]) == 0
    search_payload = _json_output(capsys)

    assert search_payload["operations"][0]["operation_id"] == "GetFilteredTeamTasks"
    assert search_payload["operations"][0]["path"] == "/v2/team/789/task"

    assert main(["run", "timer", "--dry-run"]) == 0
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

    def failing_client() -> ClickUpClient:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(400, text="bad pk_test token", request=request)

        return ClickUpClient(
            ClickUpConfig(api_key="pk_test"),
            transport=httpx.MockTransport(handler),
        )

    monkeypatch.setattr("clickup_agent.toolchains.ClickUpClient.from_environment", failing_client)

    assert main(["run", "create-task", "--live", "--list-id", "123", "--name", "Ship it"]) == 2
    captured = capsys.readouterr()

    assert "ClickUp API error (400)" in captured.out
    assert "<redacted>" in captured.out
    assert "pk_test" not in captured.out
    assert "Traceback" not in captured.out
    assert "Traceback" not in captured.err


def test_live_api_error_details_are_truncated(monkeypatch, capsys) -> None:
    monkeypatch.setenv("CLICKUP_API_KEY", "pk_test")

    def failing_client() -> ClickUpClient:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(400, text="bad pk_test token " + ("x" * 3000), request=request)

        return ClickUpClient(
            ClickUpConfig(api_key="pk_test"),
            transport=httpx.MockTransport(handler),
        )

    monkeypatch.setattr("clickup_agent.toolchains.ClickUpClient.from_environment", failing_client)

    assert main(["run", "create-task", "--live", "--list-id", "123", "--name", "Ship it"]) == 2
    captured = capsys.readouterr()

    assert "<redacted>" in captured.out
    assert "<truncated " in captured.out
    assert "pk_test" not in captured.out
    assert len(captured.out) < 2300
