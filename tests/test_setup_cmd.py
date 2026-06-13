from __future__ import annotations

import stat

from clickup_agent.cli import main
from clickup_agent.config import default_env_file, read_env_file


def _clear_clickup_env(monkeypatch) -> None:
    for key in (
        "CLICKUP_API_KEY",
        "CLICKUP_WORKSPACE_ID",
        "CLICKUP_WEBHOOK_SECRET",
        "CLICKUP_ENV_FILE",
    ):
        monkeypatch.delenv(key, raising=False)


def test_setup_writes_redacted_owner_only_env_file(tmp_path, monkeypatch, capsys) -> None:
    _clear_clickup_env(monkeypatch)
    monkeypatch.setenv("HOME", str(tmp_path))

    assert main(
        [
            "setup",
            "--api-key",
            "pk_test_secret",
            "--workspace-id",
            "workspace-1",
            "--webhook-secret",
            "hook-secret",
            "--non-interactive",
        ]
    ) == 0

    env_file = default_env_file()
    captured = capsys.readouterr()

    assert stat.S_IMODE(env_file.stat().st_mode) == 0o600
    assert read_env_file() == {
        "CLICKUP_API_KEY": "pk_test_secret",
        "CLICKUP_WORKSPACE_ID": "workspace-1",
        "CLICKUP_WEBHOOK_SECRET": "hook-secret",
    }
    assert "CLICKUP_API_KEY: configured" in captured.out
    assert "CLICKUP_WORKSPACE_ID: configured" in captured.out
    assert "pk_test_secret" not in captured.out
    assert "hook-secret" not in captured.out


def test_init_alias_uses_env_vars_and_flags_override_env(tmp_path, monkeypatch, capsys) -> None:
    _clear_clickup_env(monkeypatch)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("CLICKUP_API_KEY", "pk_from_env")
    monkeypatch.setenv("CLICKUP_WORKSPACE_ID", "workspace-from-env")

    assert main(["init", "--api-key", "pk_from_flag", "--non-interactive"]) == 0

    captured = capsys.readouterr()
    values = read_env_file()

    assert values["CLICKUP_API_KEY"] == "pk_from_flag"
    assert values["CLICKUP_WORKSPACE_ID"] == "workspace-from-env"
    assert "pk_from_flag" not in captured.out
    assert "pk_from_env" not in captured.out


def test_setup_print_is_redacted_and_does_not_write(tmp_path, monkeypatch, capsys) -> None:
    _clear_clickup_env(monkeypatch)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("CLICKUP_API_KEY", "pk_print_secret")
    monkeypatch.setenv("CLICKUP_WORKSPACE_ID", "workspace-print")

    assert main(["setup", "--print", "--non-interactive"]) == 0

    captured = capsys.readouterr()

    assert not default_env_file().exists()
    assert "CLICKUP_API_KEY: configured" in captured.out
    assert "CLICKUP_WORKSPACE_ID: configured" in captured.out
    assert "pk_print_secret" not in captured.out


def test_setup_non_interactive_requires_api_key(tmp_path, monkeypatch, capsys) -> None:
    _clear_clickup_env(monkeypatch)
    monkeypatch.setenv("HOME", str(tmp_path))

    assert main(["setup", "--non-interactive"]) == 2

    captured = capsys.readouterr()

    assert "CLICKUP_API_KEY is required" in captured.err
    assert not default_env_file().exists()


def test_setup_live_auth_runs_after_write(tmp_path, monkeypatch) -> None:
    _clear_clickup_env(monkeypatch)
    monkeypatch.setenv("HOME", str(tmp_path))
    called = False

    def fake_live_auth_check() -> int:
        nonlocal called
        called = True
        return 0

    monkeypatch.setattr("clickup_agent.setup_cmd.run_live_auth_check", fake_live_auth_check)

    assert main(["setup", "--api-key", "pk_live_secret", "--non-interactive", "--live-auth"]) == 0

    assert called is True
