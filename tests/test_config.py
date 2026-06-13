from __future__ import annotations

import os
import stat

from clickup_agent.cli import main
from clickup_agent.config import config_status, default_env_file, load_config, write_env_file


def _clear_clickup_env(monkeypatch) -> None:
    for key in (
        "CLICKUP_API_KEY",
        "CLICKUP_WORKSPACE_ID",
        "CLICKUP_WEBHOOK_SECRET",
        "CLICKUP_ENV_FILE",
        "CLICKUP_BASE_URL",
    ):
        monkeypatch.delenv(key, raising=False)


def test_default_env_file_uses_home_config_path(tmp_path, monkeypatch) -> None:
    _clear_clickup_env(monkeypatch)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "ignored-xdg"))
    env_file = tmp_path / ".config" / "clickup-agent" / ".env"
    env_file.parent.mkdir(parents=True)
    env_file.write_text("CLICKUP_API_KEY=pk_test\nCLICKUP_WORKSPACE_ID=123\n", encoding="utf-8")
    env_file.chmod(0o600)

    assert default_env_file() == env_file

    status = config_status()
    config = load_config()

    assert status["env_file"] == str(env_file)
    assert status["clickup_api_key_configured"] is True
    assert status["warnings"] == []
    assert config.api_key == "pk_test"
    assert config.workspace_id == "123"


def test_clickup_env_file_is_ignored_for_native_agent(tmp_path, monkeypatch) -> None:
    _clear_clickup_env(monkeypatch)
    monkeypatch.setenv("HOME", str(tmp_path))
    env_file = tmp_path / ".config" / "clickup-agent" / ".env"
    env_file.parent.mkdir(parents=True)
    env_file.write_text("CLICKUP_API_KEY=pk_canonical\n", encoding="utf-8")
    override_file = tmp_path / "custom.env"
    override_file.write_text("CLICKUP_API_KEY=pk_override\n", encoding="utf-8")
    monkeypatch.setenv("CLICKUP_ENV_FILE", str(override_file))

    config = load_config()

    assert config.api_key == "pk_canonical"


def test_load_config_does_not_export_secrets_to_process_env(tmp_path, monkeypatch) -> None:
    _clear_clickup_env(monkeypatch)
    monkeypatch.setenv("HOME", str(tmp_path))
    env_file = tmp_path / ".config" / "clickup-agent" / ".env"
    env_file.parent.mkdir(parents=True)
    env_file.write_text("CLICKUP_API_KEY=pk_canonical\nCLICKUP_WORKSPACE_ID=123\n", encoding="utf-8")

    config = load_config()

    assert config.api_key == "pk_canonical"
    assert os.environ.get("CLICKUP_API_KEY") is None
    assert os.environ.get("CLICKUP_WORKSPACE_ID") is None


def test_clickup_base_url_in_env_file_is_ignored(tmp_path, monkeypatch) -> None:
    _clear_clickup_env(monkeypatch)
    monkeypatch.setenv("HOME", str(tmp_path))
    env_file = tmp_path / ".config" / "clickup-agent" / ".env"
    env_file.parent.mkdir(parents=True)
    env_file.write_text("CLICKUP_API_KEY=pk_canonical\nCLICKUP_BASE_URL=https://example.invalid\n", encoding="utf-8")

    config = load_config()

    assert config.base_url == "https://api.clickup.com/api"


def test_config_status_warns_about_broad_env_file_permissions(tmp_path, monkeypatch) -> None:
    _clear_clickup_env(monkeypatch)
    monkeypatch.setenv("HOME", str(tmp_path))
    env_file = tmp_path / ".config" / "clickup-agent" / ".env"
    env_file.parent.mkdir(parents=True)
    env_file.write_text("CLICKUP_API_KEY=pk_test\n", encoding="utf-8")
    env_file.chmod(0o644)

    status = config_status()

    assert status["warnings"] == ["Env file is readable by group or other users; run chmod 600 on it."]


def test_write_env_file_creates_owner_only_file_and_backup(tmp_path, monkeypatch) -> None:
    _clear_clickup_env(monkeypatch)
    monkeypatch.setenv("HOME", str(tmp_path))
    env_file = default_env_file()

    written = write_env_file(
        {
            "CLICKUP_API_KEY": "pk_first",
            "CLICKUP_WORKSPACE_ID": "workspace-1",
            "CLICKUP_WEBHOOK_SECRET": "",
        },
        force=True,
    )

    assert written == env_file
    assert stat.S_IMODE(env_file.stat().st_mode) == 0o600
    assert 'CLICKUP_API_KEY="pk_first"' in env_file.read_text(encoding="utf-8")

    write_env_file(
        {
            "CLICKUP_API_KEY": "pk_second",
            "CLICKUP_WORKSPACE_ID": "",
            "CLICKUP_WEBHOOK_SECRET": "hook-secret",
        },
        force=True,
    )

    backups = list(env_file.parent.glob(".env.bak.*"))
    assert len(backups) == 1
    assert stat.S_IMODE(backups[0].stat().st_mode) == 0o600
    assert "pk_first" in backups[0].read_text(encoding="utf-8")
    assert "pk_second" in env_file.read_text(encoding="utf-8")


def test_doctor_loads_default_env_file(tmp_path, monkeypatch, capsys) -> None:
    _clear_clickup_env(monkeypatch)
    monkeypatch.setenv("HOME", str(tmp_path))
    env_file = tmp_path / ".config" / "clickup-agent" / ".env"
    env_file.parent.mkdir(parents=True)
    env_file.write_text("CLICKUP_API_KEY=pk_test\n", encoding="utf-8")

    assert main(["doctor"]) == 0

    captured = capsys.readouterr()
    assert "CLICKUP_API_KEY: configured" in captured.out


def test_doctor_rejects_env_file_override(tmp_path, monkeypatch, capsys) -> None:
    _clear_clickup_env(monkeypatch)
    monkeypatch.setenv("HOME", str(tmp_path))
    env_file = tmp_path / ".env.example"
    env_file.write_text("CLICKUP_API_KEY=\n", encoding="utf-8")

    assert main(["doctor", "--env-file", str(env_file)]) == 2

    captured = capsys.readouterr()
    assert "unrecognized arguments: --env-file" in captured.err
