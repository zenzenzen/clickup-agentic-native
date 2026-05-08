from __future__ import annotations

import httpx

from clickup_agent.client import ClickUpClient
from clickup_agent.cli import main
from clickup_agent.config import ClickUpConfig


def _write_canonical_env(tmp_path, monkeypatch, text: str) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    env_file = tmp_path / ".config" / "clickup-agent" / ".env"
    env_file.parent.mkdir(parents=True)
    env_file.write_text(text, encoding="utf-8")


def test_doctor_live_auth_reports_redacted_success(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("CLICKUP_API_KEY", "pk_shell_ignored")
    monkeypatch.setenv("CLICKUP_WORKSPACE_ID", "shell_ignored")
    _write_canonical_env(tmp_path, monkeypatch, "CLICKUP_API_KEY=pk_file\nCLICKUP_WORKSPACE_ID=901\n")

    def client_factory() -> ClickUpClient:
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/api/v2/user":
                return httpx.Response(200, json={"user": {"id": 1, "username": "Hidden"}})
            if request.url.path == "/api/v2/team":
                return httpx.Response(200, json={"teams": [{"id": "901", "name": "Workspace"}]})
            return httpx.Response(404, request=request)

        return ClickUpClient(ClickUpConfig(api_key="pk_test", workspace_id="901"), transport=httpx.MockTransport(handler))

    monkeypatch.setattr("clickup_agent.cli.ClickUpClient.from_environment", client_factory)

    assert main(["doctor", "--live-auth"]) == 0
    output = capsys.readouterr().out

    assert "ClickUp /v2/user: authorized" in output
    assert "ClickUp /v2/team: authorized (1 team(s))" in output
    assert "CLICKUP_WORKSPACE_ID authorization: authorized" in output
    assert "pk_test" not in output
    assert "Hidden" not in output
    assert "Workspace" not in output


def test_doctor_live_auth_redacts_api_errors(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("CLICKUP_API_KEY", "pk_shell_ignored")
    monkeypatch.delenv("CLICKUP_WORKSPACE_ID", raising=False)
    _write_canonical_env(tmp_path, monkeypatch, "CLICKUP_API_KEY=pk_file\n")

    def client_factory() -> ClickUpClient:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(401, text="bad pk_test token", request=request)

        return ClickUpClient(ClickUpConfig(api_key="pk_test"), transport=httpx.MockTransport(handler))

    monkeypatch.setattr("clickup_agent.cli.ClickUpClient.from_environment", client_factory)

    assert main(["doctor", "--live-auth"]) == 2
    output = capsys.readouterr().out

    assert "ClickUp live auth: failed" in output
    assert "<redacted>" in output
    assert "pk_test" not in output
