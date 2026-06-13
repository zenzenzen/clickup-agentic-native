"""MCP client registration helpers for clickup-agent."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path


SERVER_NAME = "clickup-agent"
SERVER_COMMAND = "clickup-agent"
SERVER_ARGS = ["mcp"]


def mcp_server_config() -> dict[str, object]:
    """Return the portable MCP JSON server definition."""
    return {
        "mcpServers": {
            SERVER_NAME: {
                "command": SERVER_COMMAND,
                "args": SERVER_ARGS,
                "env": {},
            }
        }
    }


def codex_toml_snippet() -> str:
    """Return the portable Codex MCP TOML block."""
    return "\n".join(
        [
            "[mcp_servers.clickup-agent]",
            f'command = "{SERVER_COMMAND}"',
            'args = ["mcp"]',
            "",
        ]
    )


def _print_json_snippet(label: str) -> None:
    print(label)
    print(json.dumps(mcp_server_config(), indent=2))


def _print_codex() -> None:
    print("Add this to ~/.codex/config.toml:")
    print()
    print(codex_toml_snippet(), end="")


def _print_claude_code() -> None:
    print("Run this Claude Code MCP registration command:")
    print("claude mcp add clickup-agent -- clickup-agent mcp")


def _cursor_config_path(scope: str) -> Path:
    if scope == "global":
        return Path.home() / ".cursor" / "mcp.json"
    return Path.cwd() / ".cursor" / "mcp.json"


def _backup_existing(path: Path) -> None:
    if not path.exists():
        return
    timestamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S%f")
    shutil.copy2(path, path.with_name(f"{path.name}.bak.{timestamp}"))


def _write_cursor_config(scope: str) -> Path:
    config_path = _cursor_config_path(scope)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    _backup_existing(config_path)
    if config_path.exists() and config_path.read_text(encoding="utf-8").strip():
        config = json.loads(config_path.read_text(encoding="utf-8"))
    else:
        config = {}
    servers = config.setdefault("mcpServers", {})
    servers[SERVER_NAME] = mcp_server_config()["mcpServers"][SERVER_NAME]
    config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    return config_path


def _codex_config_path() -> Path:
    return Path.home() / ".codex" / "config.toml"


def _replace_or_append_toml_block(existing: str, block: str) -> str:
    pattern = re.compile(r"(?ms)^\[mcp_servers\.clickup-agent\]\n.*?(?=^\[|\Z)")
    normalized = block.rstrip() + "\n"
    if pattern.search(existing):
        return pattern.sub(normalized, existing).rstrip() + "\n"
    separator = "" if not existing or existing.endswith("\n\n") else "\n"
    return existing + separator + normalized


def _write_codex_config() -> Path:
    config_path = _codex_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    _backup_existing(config_path)
    existing = config_path.read_text(encoding="utf-8") if config_path.exists() else ""
    config_path.write_text(_replace_or_append_toml_block(existing, codex_toml_snippet()), encoding="utf-8")
    return config_path


def _write_claude_code() -> int:
    try:
        subprocess.run(
            ["claude", "mcp", "add", SERVER_NAME, "--", SERVER_COMMAND, *SERVER_ARGS],
            check=True,
        )
    except FileNotFoundError:
        print("Claude Code CLI not found. Run: claude mcp add clickup-agent -- clickup-agent mcp")
        return 2
    except subprocess.CalledProcessError as exc:
        return exc.returncode or 2
    return 0


def run_connect(args: argparse.Namespace) -> int:
    """Print or write MCP registration for supported clients."""
    if not args.write:
        if args.client == "claude-code":
            _print_claude_code()
        elif args.client == "codex":
            _print_codex()
        elif args.client == "cursor":
            _print_json_snippet("Add this to .cursor/mcp.json or ~/.cursor/mcp.json:")
        else:
            _print_json_snippet("Use this MCP server configuration:")
        return 0

    if args.client == "cursor":
        path = _write_cursor_config(args.scope)
        print(f"Wrote Cursor MCP config: {path}")
        return 0
    if args.client == "codex":
        path = _write_codex_config()
        print(f"Wrote Codex MCP config: {path}")
        return 0
    if args.client == "claude-code":
        return _write_claude_code()

    print("Generic MCP snippets are print-only; omit --write and copy the JSON into your client.")
    return 2
