"""Command-line entrypoint for the ClickUp agent.

The first scaffold keeps commands stable while the actual ClickUp client,
tool registry, and MCP server are implemented behind them.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from . import __version__


def _load_env_file(path: str | None) -> None:
    """Load simple KEY=VALUE pairs without adding a runtime dependency yet."""
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


def _cmd_doctor(args: argparse.Namespace) -> int:
    """Check local configuration for the future agent runtime."""
    _load_env_file(args.env_file or os.getenv("CLICKUP_ENV_FILE"))
    has_key = bool(os.getenv("CLICKUP_API_KEY"))
    has_workspace = bool(os.getenv("CLICKUP_WORKSPACE_ID"))
    print(f"clickup-agent {__version__}")
    print(f"CLICKUP_API_KEY: {'configured' if has_key else 'missing'}")
    print(f"CLICKUP_WORKSPACE_ID: {'configured' if has_workspace else 'missing'}")
    if not has_key:
        print("Create .env.local from .env.example, then set CLICKUP_API_KEY.")
        return 1
    return 0


def _cmd_placeholder(name: str, next_step: str):
    """Create a placeholder command that explains the stable contract."""
    def run(_: argparse.Namespace) -> int:
        print(f"`clickup-agent {name}` is reserved for {next_step}.")
        print("The command contract is in place; implementation comes in the next build pass.")
        return 0

    return run


def build_parser() -> argparse.ArgumentParser:
    """Build the command parser shared by console script and module entrypoint."""
    parser = argparse.ArgumentParser(prog="clickup-agent")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subcommands = parser.add_subparsers(dest="command", required=True)

    doctor = subcommands.add_parser("doctor", help="Check local ClickUp agent configuration.")
    doctor.add_argument("--env-file", help="Path to a local env file such as .env.local.")
    doctor.set_defaults(func=_cmd_doctor)

    chat = subcommands.add_parser("chat", help="Start the future interactive ClickUp agent.")
    chat.set_defaults(func=_cmd_placeholder("chat", "interactive ClickUp work sessions"))

    mcp = subcommands.add_parser("mcp", help="Start the future LLM/MCP tool server.")
    mcp.set_defaults(func=_cmd_placeholder("mcp", "LLM client access over MCP stdio"))

    tools = subcommands.add_parser("tools", help="Inspect future ClickUp tools.")
    tools_subcommands = tools.add_subparsers(dest="tools_command", required=True)
    tools_list = tools_subcommands.add_parser("list", help="List future ClickUp tools.")
    tools_list.set_defaults(func=_cmd_placeholder("tools list", "generated and curated tool discovery"))

    hotkeys = subcommands.add_parser("hotkeys", help="Inspect future hotkey toolchains.")
    hotkeys_subcommands = hotkeys.add_subparsers(dest="hotkeys_command", required=True)
    hotkeys_list = hotkeys_subcommands.add_parser("list", help="List future hotkey toolchains.")
    hotkeys_list.set_defaults(func=_cmd_placeholder("hotkeys list", "ClickUp-inspired workflow shortcuts"))

    run = subcommands.add_parser("run", help="Run a future hotkey or toolchain.")
    run.add_argument("name", help="Hotkey or toolchain name.")
    run.set_defaults(func=_cmd_placeholder("run", "executing named ClickUp toolchains"))

    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the clickup-agent CLI."""
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))
