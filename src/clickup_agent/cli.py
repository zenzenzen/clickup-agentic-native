"""Command-line entrypoint for the ClickUp agent.

The first scaffold keeps commands stable while the actual ClickUp client,
tool registry, and MCP server are implemented behind them.
"""

from __future__ import annotations

import argparse
import json

from . import __version__
from .client import ClickUpApiError, ClickUpClient
from .config import ConfigError, default_env_file, load_config, load_env_file
from .registry import ToolOperation, load_catalog
from .toolchains import ToolchainError, run_toolchain


def _load_env_file() -> None:
    """Load simple KEY=VALUE pairs without adding a runtime dependency yet."""
    load_env_file()


def _cmd_doctor(args: argparse.Namespace) -> int:
    """Check local configuration for the future agent runtime."""
    env_file = default_env_file()
    _load_env_file()
    try:
        config = load_config()
    except ConfigError:
        config = None
    has_key = bool(config and config.api_key)
    has_workspace = bool(config and config.workspace_id)
    has_webhook_secret = bool(config and config.webhook_secret)
    print(f"clickup-agent {__version__}")
    print(f"CLICKUP_API_KEY: {'configured' if has_key else 'missing'}")
    print(f"CLICKUP_WORKSPACE_ID: {'configured' if has_workspace else 'missing'}")
    print(f"CLICKUP_WEBHOOK_SECRET: {'configured' if has_webhook_secret else 'optional / missing'}")
    if not has_key:
        print(f"Create {env_file} from .env.example, then set CLICKUP_API_KEY.")
        return 1
    if args.live_auth:
        return _run_live_auth_check()
    return 0


def _run_live_auth_check() -> int:
    """Probe read-only ClickUp endpoints without printing secret values."""
    try:
        with ClickUpClient.from_environment() as client:
            user_response = client.request("GET", "/v2/user")
            teams_response = client.request("GET", "/v2/team")
    except ClickUpApiError as exc:
        print(f"ClickUp live auth: failed - {exc}")
        return 2

    user = user_response.get("user") if isinstance(user_response, dict) else None
    teams = teams_response.get("teams") if isinstance(teams_response, dict) else None
    team_list = teams if isinstance(teams, list) else []
    workspace_id = client.config.workspace_id
    workspace_authorized = (
        any(isinstance(team, dict) and str(team.get("id")) == workspace_id for team in team_list)
        if workspace_id
        else None
    )

    print(f"ClickUp /v2/user: {'authorized' if isinstance(user, dict) else 'unexpected response'}")
    print(f"ClickUp /v2/team: authorized ({len(team_list)} team(s))")
    if workspace_authorized is not None:
        print(f"CLICKUP_WORKSPACE_ID authorization: {'authorized' if workspace_authorized else 'not found'}")
        if not workspace_authorized:
            return 2
    return 0


def _cmd_placeholder(name: str, next_step: str):
    """Create a placeholder command that explains the stable contract."""
    def run(_: argparse.Namespace) -> int:
        print(f"`clickup-agent {name}` is reserved for {next_step}.")
        print("The command contract is in place; implementation comes in the next build pass.")
        return 0

    return run


def _cmd_mcp(_: argparse.Namespace) -> int:
    """Run the MCP stdio server used by Cursor and other LLM clients."""
    from .mcp_server import run

    run()
    return 0


def _print_json(data: object) -> None:
    print(json.dumps(data, indent=2, sort_keys=True))


def _print_table(rows: list[dict[str, object]], columns: list[tuple[str, str]]) -> None:
    if not rows:
        print("No results.")
        return
    widths = {
        key: max(len(label), *(len(str(row.get(key, ""))) for row in rows))
        for key, label in columns
    }
    print("  ".join(label.ljust(widths[key]) for key, label in columns))
    print("  ".join("-" * widths[key] for key, _ in columns))
    for row in rows:
        print("  ".join(str(row.get(key, "")).ljust(widths[key]) for key, _ in columns))


def _operation_row(operation: ToolOperation) -> dict[str, object]:
    return {
        "name": operation.name,
        "operation_id": operation.operation_id,
        "method": operation.method,
        "path": operation.path,
        "tags": ",".join(operation.tags),
        "write": operation.is_write,
        "summary": operation.summary,
    }


def _cmd_tools_list(args: argparse.Namespace) -> int:
    catalog = load_catalog()
    rows = [_operation_row(operation) for operation in catalog.list_operations(tag=args.tag, write_only=args.write_only)]
    if args.format == "json":
        _print_json(
            {
                "source": catalog.source,
                "source_version": catalog.source_version,
                "count": len(rows),
                "tools": rows,
            }
        )
        return 0
    _print_table(
        rows,
        [
            ("name", "Name"),
            ("method", "Method"),
            ("path", "Path"),
            ("tags", "Tags"),
            ("write", "Write"),
            ("summary", "Summary"),
        ],
    )
    return 0


def _cmd_hotkeys_list(args: argparse.Namespace) -> int:
    catalog = load_catalog()
    rows = [
        {
            "name": toolchain.name,
            "operations": ",".join(toolchain.operation_ids),
            "write": toolchain.is_write,
            "summary": toolchain.summary,
        }
        for toolchain in catalog.toolchains
    ]
    if args.format == "json":
        _print_json(
            {
                "source": catalog.source,
                "source_version": catalog.source_version,
                "count": len(rows),
                "hotkeys": rows,
            }
        )
        return 0
    _print_table(
        rows,
        [
            ("name", "Name"),
            ("operations", "Operations"),
            ("write", "Write"),
            ("summary", "Summary"),
        ],
    )
    return 0


def _cmd_run(args: argparse.Namespace) -> int:
    try:
        result = run_toolchain(args.name, args.tool_args)
    except ToolchainError as exc:
        print(str(exc))
        return 2
    _print_json(result.to_dict())
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Build the command parser shared by console script and module entrypoint."""
    parser = argparse.ArgumentParser(prog="clickup-agent")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subcommands = parser.add_subparsers(dest="command", required=True)

    doctor = subcommands.add_parser("doctor", help="Check local ClickUp agent configuration.")
    doctor.add_argument(
        "--live-auth",
        action="store_true",
        help="Call read-only ClickUp auth endpoints and report redacted authorization status.",
    )
    doctor.set_defaults(func=_cmd_doctor)

    chat = subcommands.add_parser("chat", help="Start the future interactive ClickUp agent.")
    chat.set_defaults(func=_cmd_placeholder("chat", "interactive ClickUp work sessions"))

    mcp = subcommands.add_parser("mcp", help="Start the future LLM/MCP tool server.")
    mcp.set_defaults(func=_cmd_mcp)

    tools = subcommands.add_parser("tools", help="Inspect future ClickUp tools.")
    tools_subcommands = tools.add_subparsers(dest="tools_command", required=True)
    tools_list = tools_subcommands.add_parser("list", help="List future ClickUp tools.")
    tools_list.add_argument("--format", choices=["table", "json"], default="table", help="Output format.")
    tools_list.add_argument("--tag", help="Filter operations by an OpenAPI tag such as Tasks.")
    tools_list.add_argument("--write-only", action="store_true", help="Only show operations that can mutate ClickUp.")
    tools_list.set_defaults(func=_cmd_tools_list)

    hotkeys = subcommands.add_parser("hotkeys", help="Inspect future hotkey toolchains.")
    hotkeys_subcommands = hotkeys.add_subparsers(dest="hotkeys_command", required=True)
    hotkeys_list = hotkeys_subcommands.add_parser("list", help="List future hotkey toolchains.")
    hotkeys_list.add_argument("--format", choices=["table", "json"], default="table", help="Output format.")
    hotkeys_list.set_defaults(func=_cmd_hotkeys_list)

    run = subcommands.add_parser("run", help="Run a future hotkey or toolchain.")
    run.add_argument("name", help="Hotkey or toolchain name.")
    run.add_argument("tool_args", nargs=argparse.REMAINDER, help="Toolchain-specific flags.")
    run.set_defaults(func=_cmd_run)

    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the clickup-agent CLI."""
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
        return int(args.func(args))
    except SystemExit as exc:
        if isinstance(exc.code, int):
            return exc.code
        if exc.code is None:
            return 0
        print(str(exc.code))
        return 2
