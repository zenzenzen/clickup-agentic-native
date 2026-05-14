from __future__ import annotations

import json

from clickup_agent.cli import main


def _write_env(tmp_path, monkeypatch, text: str) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    env_file = tmp_path / ".config" / "clickup-agent" / ".env"
    env_file.parent.mkdir(parents=True)
    env_file.write_text(text, encoding="utf-8")
    env_file.chmod(0o600)


def test_setup_json_reports_redacted_first_run_steps(tmp_path, monkeypatch, capsys) -> None:
    _write_env(tmp_path, monkeypatch, "CLICKUP_API_KEY=pk_secret\nCLICKUP_WORKSPACE_ID=901\n")

    assert main(["setup", "--format", "json"]) == 0

    payload = json.loads(capsys.readouterr().out)
    commands = [step["command"] for step in payload["steps"]]

    assert payload["env_file"] == "~/.config/clickup-agent/.env"
    assert payload["configured"]["clickup_api_key"] is True
    assert payload["configured"]["clickup_workspace_id"] is True
    assert "clickup-agent doctor --repair-plan" in commands
    assert "clickup-agent mcp --smoke-test" in commands
    assert "pk_secret" not in json.dumps(payload)
    assert str(tmp_path) not in json.dumps(payload)


def test_doctor_repair_plan_explains_missing_env_without_secrets(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))

    assert main(["doctor", "--repair-plan"]) == 1

    output = capsys.readouterr().out

    assert "Repair plan:" in output
    assert "env-file: missing" in output
    assert "CLICKUP_API_KEY: missing" in output
    assert "CLICKUP_API_KEY=<personal_token>" in output
    assert "~/.config/clickup-agent/.env" in output
    assert str(tmp_path) not in output


def test_mcp_smoke_test_registers_tools_without_live_calls(capsys) -> None:
    assert main(["mcp", "--smoke-test"]) == 0

    output = capsys.readouterr().out

    assert "MCP smoke test: ok" in output
    assert "Registered tools:" in output
    assert "ClickUp API calls: none" in output
