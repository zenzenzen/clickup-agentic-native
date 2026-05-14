"""Command-line entrypoint for the ClickUp agent.

The first scaffold keeps commands stable while the actual ClickUp client,
tool registry, and MCP server are implemented behind them.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import sys
from pathlib import Path

from . import __version__
from .client import ClickUpApiError, ClickUpClient
from .config import ConfigError, config_status, default_env_file, load_config
from .registry import ToolOperation, load_catalog
from .toolchains import ToolchainError, run_toolchain


def _display_path(path: Path) -> str:
    """Return a stable path for local setup output without exposing home internals."""
    home = Path.home()
    try:
        return f"~/{path.relative_to(home)}"
    except ValueError:
        return str(path)


def _repair_steps(
    *,
    has_key: bool,
    has_workspace: bool,
    status: dict[str, object],
) -> list[dict[str, str]]:
    env_file = default_env_file()
    env_dir = env_file.parent
    steps: list[dict[str, str]] = []

    if sys.version_info < (3, 12):
        steps.append(
            {
                "check": "python",
                "status": "needs Python 3.12+",
                "fix": "Install Python 3.12, then reinstall with `uv tool install . --python 3.12 --reinstall`.",
            }
        )

    if shutil.which("uv") is None:
        steps.append(
            {
                "check": "uv",
                "status": "missing",
                "fix": "Install uv, or use editable mode with `python3.12 -m venv .venv` and `python -m pip install -e .`.",
            }
        )

    if shutil.which("clickup-agent") is None:
        steps.append(
            {
                "check": "cli",
                "status": "not on PATH",
                "fix": "Run `uv tool install . --python 3.12 --reinstall`, then restart your shell if needed.",
            }
        )

    if not env_file.exists():
        steps.append(
            {
                "check": "env-file",
                "status": "missing",
                "fix": (
                    f"Run `mkdir -p {_display_path(env_dir)}` and copy `.env.example` "
                    f"to `{_display_path(env_file)}`, then run `chmod 600 {_display_path(env_file)}`."
                ),
            }
        )

    for warning in status.get("warnings", []):
        steps.append(
            {
                "check": "env-file-permissions",
                "status": str(warning),
                "fix": f"Run `chmod 600 {_display_path(env_file)}`.",
            }
        )

    if not has_key:
        steps.append(
            {
                "check": "CLICKUP_API_KEY",
                "status": "missing",
                "fix": f"Add `CLICKUP_API_KEY=<personal_token>` to `{_display_path(env_file)}`.",
            }
        )

    if not has_workspace:
        steps.append(
            {
                "check": "CLICKUP_WORKSPACE_ID",
                "status": "optional / missing",
                "fix": "Add a default workspace ID when you want workspace-scoped commands and live auth checks.",
            }
        )

    cursor_project = Path.cwd() / ".cursor" / "mcp.json"
    cursor_global = Path.home() / ".cursor" / "mcp.json"
    if not cursor_project.exists() and not cursor_global.exists():
        steps.append(
            {
                "check": "cursor-mcp",
                "status": "optional / not detected",
                "fix": "Run `bash scripts/install.sh` or add a server command with `clickup-agent mcp`.",
            }
        )

    return steps


def _cmd_doctor(args: argparse.Namespace) -> int:
    """Check local configuration for the future agent runtime."""
    env_file = default_env_file()
    status = config_status()
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
    for warning in status.get("warnings", []):
        print(f"CONFIG WARNING: {warning}")
    if args.repair_plan:
        _print_repair_plan(_repair_steps(has_key=has_key, has_workspace=has_workspace, status=status))
    if not has_key:
        print(f"Create {_display_path(env_file)} from .env.example, then set CLICKUP_API_KEY.")
        return 1
    if args.live_auth:
        return _run_live_auth_check()
    return 0


def _print_repair_plan(steps: list[dict[str, str]]) -> None:
    print("Repair plan:")
    if not steps:
        print("- no repairs suggested")
        return
    for index, step in enumerate(steps, start=1):
        print(f"{index}. {step['check']}: {step['status']}")
        print(f"   fix: {step['fix']}")


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


def _cmd_setup(args: argparse.Namespace) -> int:
    """Print a non-interactive first-run setup guide."""
    env_file = default_env_file()
    status = config_status()
    has_key = bool(status.get("clickup_api_key_configured"))
    has_workspace = bool(status.get("clickup_workspace_id_configured"))
    steps = [
        {
            "name": "install",
            "command": "uv tool install . --python 3.12 --reinstall",
            "note": "Install or refresh the clickup-agent CLI from this checkout.",
        },
        {
            "name": "env-file",
            "command": f"mkdir -p {_display_path(env_file.parent)} && cp .env.example {_display_path(env_file)} && chmod 600 {_display_path(env_file)}",
            "note": "Create the canonical local env file outside the workspace.",
        },
        {
            "name": "edit-secrets",
            "command": f"$EDITOR {_display_path(env_file)}",
            "note": "Fill in CLICKUP_API_KEY and optional workspace/webhook values.",
        },
        {
            "name": "verify",
            "command": "clickup-agent doctor --repair-plan",
            "note": "Check local config and print redacted repair guidance.",
        },
        {
            "name": "mcp-smoke-test",
            "command": "clickup-agent mcp --smoke-test",
            "note": "Verify MCP tool registration without starting stdio or calling ClickUp.",
        },
    ]
    payload = {
        "version": __version__,
        "env_file": _display_path(env_file),
        "configured": {
            "clickup_api_key": has_key,
            "clickup_workspace_id": has_workspace,
            "clickup_webhook_secret": bool(status.get("clickup_webhook_secret_configured")),
        },
        "steps": steps,
    }
    if args.format == "json":
        _print_json(payload)
        return 0

    print(f"clickup-agent setup ({__version__})")
    print(f"Env file: {payload['env_file']}")
    print(f"CLICKUP_API_KEY: {'configured' if has_key else 'missing'}")
    print(f"CLICKUP_WORKSPACE_ID: {'configured' if has_workspace else 'optional / missing'}")
    print("Steps:")
    for index, step in enumerate(steps, start=1):
        print(f"{index}. {step['name']}")
        print(f"   {step['command']}")
        print(f"   {step['note']}")
    return 0


def _cmd_mcp(args: argparse.Namespace) -> int:
    """Run the MCP stdio server used by Cursor and other LLM clients."""
    from .mcp_server import create_server, run

    if args.smoke_test:
        async def list_tools() -> list[object]:
            return await create_server().list_tools()

        try:
            tools = asyncio.run(list_tools())
        except Exception as exc:
            print(f"MCP smoke test: failed - {exc}")
            return 2
        names = {tool.name for tool in tools}
        required = {"clickup_agent_status", "clickup_agent_tooling_plan"}
        missing = sorted(required - names)
        if missing:
            print(f"MCP smoke test: failed - missing tools: {', '.join(missing)}")
            return 2
        print("MCP smoke test: ok")
        print(f"Registered tools: {len(names)}")
        print("ClickUp API calls: none")
        return 0
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
    doctor.add_argument(
        "--repair-plan",
        action="store_true",
        help="Print redacted local repair steps for missing setup pieces.",
    )
    doctor.set_defaults(func=_cmd_doctor)

    setup = subcommands.add_parser("setup", help="Print a non-interactive first-run setup guide.")
    setup.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    setup.set_defaults(func=_cmd_setup)

    chat = subcommands.add_parser("chat", help="Start the future interactive ClickUp agent.")
    chat.set_defaults(func=_cmd_placeholder("chat", "interactive ClickUp work sessions"))

    mcp = subcommands.add_parser("mcp", help="Start the future LLM/MCP tool server.")
    mcp.add_argument(
        "--smoke-test",
        action="store_true",
        help="Verify MCP tool registration without starting stdio or calling ClickUp.",
    )
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
