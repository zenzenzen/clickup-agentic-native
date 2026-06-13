from __future__ import annotations

import json

from clickup_agent.cli import main


def test_connect_claude_code_prints_registration_command_without_secrets(monkeypatch, capsys) -> None:
    monkeypatch.setenv("CLICKUP_API_KEY", "pk_should_not_print")

    assert main(["connect", "claude-code"]) == 0

    output = capsys.readouterr().out

    assert "claude mcp add clickup-agent -- clickup-agent mcp" in output
    assert "pk_should_not_print" not in output


def test_connect_codex_prints_portable_toml_without_home_path(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("CLICKUP_API_KEY", "pk_should_not_print")

    assert main(["connect", "codex"]) == 0

    output = capsys.readouterr().out

    assert "[mcp_servers.clickup-agent]" in output
    assert 'command = "clickup-agent"' in output
    assert 'args = ["mcp"]' in output
    assert "~/.codex/config.toml" in output
    assert str(tmp_path) not in output
    assert "pk_should_not_print" not in output


def test_connect_cursor_prints_mcp_json_shape(capsys) -> None:
    assert main(["connect", "cursor"]) == 0

    output = capsys.readouterr().out
    payload = json.loads(output[output.index("{") :])

    assert payload == {
        "mcpServers": {
            "clickup-agent": {
                "command": "clickup-agent",
                "args": ["mcp"],
                "env": {},
            }
        }
    }


def test_connect_generic_prints_mcp_json_shape(capsys) -> None:
    assert main(["connect", "generic"]) == 0

    output = capsys.readouterr().out
    payload = json.loads(output[output.index("{") :])

    assert payload["mcpServers"]["clickup-agent"]["command"] == "clickup-agent"
    assert payload["mcpServers"]["clickup-agent"]["args"] == ["mcp"]
    assert payload["mcpServers"]["clickup-agent"]["env"] == {}


def test_connect_cursor_write_preserves_existing_servers(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    config_file = tmp_path / ".cursor" / "mcp.json"
    config_file.parent.mkdir()
    config_file.write_text(
        json.dumps({"mcpServers": {"other": {"command": "other-tool", "args": [], "env": {}}}}),
        encoding="utf-8",
    )

    assert main(["connect", "cursor", "--write", "--scope", "project"]) == 0

    captured = capsys.readouterr()
    payload = json.loads(config_file.read_text(encoding="utf-8"))

    assert payload["mcpServers"]["other"]["command"] == "other-tool"
    assert payload["mcpServers"]["clickup-agent"] == {
        "command": "clickup-agent",
        "args": ["mcp"],
        "env": {},
    }
    assert "Wrote Cursor MCP config" in captured.out


def test_connect_codex_write_preserves_existing_config_text(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    config_file = tmp_path / ".codex" / "config.toml"
    config_file.parent.mkdir()
    config_file.write_text('model = "gpt-5"\n', encoding="utf-8")

    assert main(["connect", "codex", "--write"]) == 0

    captured = capsys.readouterr()
    text = config_file.read_text(encoding="utf-8")

    assert 'model = "gpt-5"' in text
    assert "[mcp_servers.clickup-agent]" in text
    assert 'command = "clickup-agent"' in text
    assert "Wrote Codex MCP config" in captured.out
