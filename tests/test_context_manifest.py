from __future__ import annotations

import json

from clickup_agent.cli import main


def test_context_manifest_is_static_and_compact(capsys) -> None:
    assert main(["context", "manifest"]) == 0

    payload = json.loads(capsys.readouterr().out)

    assert payload["kind"] == "context_manifest"
    assert payload["verbosity"]["default"] == "concise"
    assert len(json.dumps(payload)) < 7000
    assert "cache_path" not in json.dumps(payload)


def test_context_manifest_exposes_operational_catchup_actions(capsys) -> None:
    assert main(["context", "manifest"]) == 0

    payload = json.loads(capsys.readouterr().out)
    pinned_actions = {action["name"] for action in payload["pinned_actions"]}
    intents = {template["intent"] for template in payload["mcp_action_templates"]}
    surfaces = {surface["name"] for surface in payload["surfaces"]}

    assert {"dev-sync", "get-task", "catch-up-docs"} <= pinned_actions
    assert any(item["choose"] == "catch-up-docs" for item in payload["dialogue_guide"])
    assert {
        "catch-up-clickup-from-current-work",
        "catch-up-clickup-from-pr",
        "catch-up-clickup-and-pr",
        "prepare-handoff-summary",
    } <= intents
    assert {"clickup-task-summary", "github-pr", "branch-audit", "handoff-context"} <= surfaces
