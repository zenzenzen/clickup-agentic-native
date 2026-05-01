"""Configuration helpers for local ClickUp credentials and defaults."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


DEFAULT_BASE_URL = "https://api.clickup.com/api"


class ConfigError(RuntimeError):
    """Raised when required local ClickUp configuration is missing."""


@dataclass(frozen=True)
class ClickUpConfig:
    api_key: str
    workspace_id: str | None = None
    webhook_secret: str | None = None
    base_url: str = DEFAULT_BASE_URL


def load_env_file(path: str | None) -> None:
    """Load simple KEY=VALUE pairs without adding secrets to tracked files."""
    if not path:
        return
    env_path = Path(path).expanduser()
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        cleaned = line.strip()
        if not cleaned or cleaned.startswith("#") or "=" not in cleaned:
            continue
        key, value = cleaned.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def config_status(env_file: str | None = None) -> dict[str, object]:
    selected_env_file = env_file or os.getenv("CLICKUP_ENV_FILE")
    load_env_file(selected_env_file)
    return {
        "env_file": str(Path(selected_env_file).expanduser()) if selected_env_file else None,
        "clickup_api_key_configured": bool(os.getenv("CLICKUP_API_KEY")),
        "clickup_workspace_id_configured": bool(os.getenv("CLICKUP_WORKSPACE_ID")),
        "clickup_webhook_secret_configured": bool(os.getenv("CLICKUP_WEBHOOK_SECRET")),
    }


def load_config(env_file: str | None = None) -> ClickUpConfig:
    selected_env_file = env_file or os.getenv("CLICKUP_ENV_FILE")
    load_env_file(selected_env_file)
    api_key = os.getenv("CLICKUP_API_KEY")
    if not api_key:
        raise ConfigError("CLICKUP_API_KEY is missing. Set it in .env.local or CLICKUP_ENV_FILE.")
    return ClickUpConfig(
        api_key=api_key,
        workspace_id=os.getenv("CLICKUP_WORKSPACE_ID") or None,
        webhook_secret=os.getenv("CLICKUP_WEBHOOK_SECRET") or None,
        base_url=os.getenv("CLICKUP_BASE_URL") or DEFAULT_BASE_URL,
    )


def load_workspace_id(env_file: str | None = None) -> str | None:
    selected_env_file = env_file or os.getenv("CLICKUP_ENV_FILE")
    load_env_file(selected_env_file)
    return os.getenv("CLICKUP_WORKSPACE_ID") or None


def redact_secret(value: str, secret: str | None) -> str:
    if not secret:
        return value
    return value.replace(secret, "<redacted>")
