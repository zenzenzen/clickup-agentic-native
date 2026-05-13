"""Configuration helpers for local ClickUp credentials and defaults."""

from __future__ import annotations

import stat
from dataclasses import dataclass
from pathlib import Path


DEFAULT_BASE_URL = "https://api.clickup.com/api"
DEFAULT_ENV_DIR_NAME = "clickup-agent"
DEFAULT_ENV_FILE_NAME = ".env"
CLICKUP_ENV_KEYS = {
    "CLICKUP_API_KEY",
    "CLICKUP_WORKSPACE_ID",
    "CLICKUP_WEBHOOK_SECRET",
}


class ConfigError(RuntimeError):
    """Raised when required local ClickUp configuration is missing."""


@dataclass(frozen=True)
class ClickUpConfig:
    api_key: str
    workspace_id: str | None = None
    webhook_secret: str | None = None
    base_url: str = DEFAULT_BASE_URL


def default_env_file() -> Path:
    """Return the stable user config env file outside any workspace."""
    return Path.home() / ".config" / DEFAULT_ENV_DIR_NAME / DEFAULT_ENV_FILE_NAME


def read_env_file() -> dict[str, str]:
    """Read ClickUp KEY=VALUE pairs from the one canonical env file."""
    env_path = default_env_file()
    if not env_path.exists():
        return {}
    values: dict[str, str] = {}
    for line in env_path.read_text(encoding="utf-8").splitlines():
        cleaned = line.strip()
        if not cleaned or cleaned.startswith("#") or "=" not in cleaned:
            continue
        key, value = cleaned.split("=", 1)
        key = key.strip()
        if key in CLICKUP_ENV_KEYS:
            values[key] = value.strip().strip('"').strip("'")
    return values


def env_file_warnings() -> list[str]:
    """Return redacted local config hygiene warnings."""
    env_path = default_env_file()
    if not env_path.exists():
        return []
    try:
        mode = stat.S_IMODE(env_path.stat().st_mode)
    except OSError as exc:
        return [f"Could not inspect env file permissions: {exc.strerror or exc.__class__.__name__}"]
    if mode & 0o077:
        return ["Env file is readable by group or other users; run chmod 600 on it."]
    return []


def config_status() -> dict[str, object]:
    selected_env_file = default_env_file()
    values = read_env_file()
    return {
        "env_file": str(selected_env_file),
        "clickup_api_key_configured": bool(values.get("CLICKUP_API_KEY")),
        "clickup_workspace_id_configured": bool(values.get("CLICKUP_WORKSPACE_ID")),
        "clickup_webhook_secret_configured": bool(values.get("CLICKUP_WEBHOOK_SECRET")),
        "warnings": env_file_warnings(),
    }


def load_config() -> ClickUpConfig:
    selected_env_file = default_env_file()
    values = read_env_file()
    api_key = values.get("CLICKUP_API_KEY")
    if not api_key:
        raise ConfigError(f"CLICKUP_API_KEY is missing. Set it in {selected_env_file}.")
    return ClickUpConfig(
        api_key=api_key,
        workspace_id=values.get("CLICKUP_WORKSPACE_ID") or None,
        webhook_secret=values.get("CLICKUP_WEBHOOK_SECRET") or None,
    )


def load_workspace_id() -> str | None:
    return read_env_file().get("CLICKUP_WORKSPACE_ID") or None


def redact_secret(value: str, secret: str | None) -> str:
    if not secret:
        return value
    return value.replace(secret, "<redacted>")
