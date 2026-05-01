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

    assert "create-task" in output
    assert "Update Task" in output


def test_hotkeys_list_json_includes_curated_toolchains(capsys) -> None:
    assert main(["hotkeys", "list", "--format", "json"]) == 0

    payload = json.loads(capsys.readouterr().out)
    names = {hotkey["name"] for hotkey in payload["hotkeys"]}

    assert {"search", "create-task", "set-status", "assign", "set-due-date", "comment", "tags", "timer"} <= names
