from __future__ import annotations

import json

from clickup_agent.cli import main


def test_tools_list_json_filters_by_tag(capsys) -> None:
    assert main(["tools", "list", "--format", "json", "--tag", "Tasks"]) == 0

    payload = json.loads(capsys.readouterr().out)

    assert payload["count"] >= 1
    assert all("Tasks" in tool["tags"] for tool in payload["tools"])
    assert any(tool["operation_id"] == "CreateTask" for tool in payload["tools"])


def test_tools_list_table_supports_write_only(capsys) -> None:
    assert main(["tools", "list", "--tag", "Tasks", "--write-only"]) == 0

    output = capsys.readouterr().out

    assert "Generated OpenAPI operations" in output
    assert "create-task" in output
    assert "Update Task" in output


def test_hotkeys_list_json_includes_curated_toolchains(capsys) -> None:
    assert main(["hotkeys", "list", "--format", "json"]) == 0

    payload = json.loads(capsys.readouterr().out)
    names = {hotkey["name"] for hotkey in payload["hotkeys"]}

    assert {
        "search",
        "get-task",
        "task-statuses",
        "create-task",
        "set-status",
        "assign",
        "set-due-date",
        "comment",
        "create-checklist",
        "sync-checklist",
        "tags",
        "timer",
    } <= names


def test_hotkeys_list_table_labels_curated_wrappers(capsys) -> None:
    assert main(["hotkeys", "list"]) == 0

    output = capsys.readouterr().out

    assert "Curated wrappers" in output
    assert "sync-checklist" in output


def test_run_tool_specific_help_shows_selected_flags(capsys) -> None:
    assert main(["run", "create-task", "--help"]) == 0

    output = capsys.readouterr().out

    assert "--list-id" in output
    assert "--name" in output
    assert "--dry-run" in output
    assert "--live" in output

    assert main(["run", "update-task", "--help"]) == 0
    output = capsys.readouterr().out

    assert "--status" in output
    assert "For full API fields, use generated operation UpdateTask." in output
