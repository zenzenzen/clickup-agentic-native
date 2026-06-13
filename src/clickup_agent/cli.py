"""User-facing CLI for local ClickUp automation.

This module owns command discovery, secret-safe diagnostics, and JSON/table
rendering. Runtime behavior lives in focused modules so the CLI can stay a thin
contract layer for humans, agents, and MCP clients.
"""

from __future__ import annotations

import argparse
import json

from . import __version__
from .client import ClickUpApiError, ClickUpClient
from .connect_cmd import run_connect
from .config import ConfigError, config_status, default_env_file, load_config
from .devlinks import inspect_dev_pr
from .registry import ToolOperation, load_catalog
from .setup_cmd import run_setup
from .toolchains import ToolchainError, run_toolchain


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


def _operation_matches_query(operation: ToolOperation, terms: list[str]) -> bool:
    haystack = " ".join(
        [
            operation.name,
            operation.operation_id,
            operation.summary,
            *operation.tags,
        ]
    ).casefold()
    return all(term.casefold() in haystack for term in terms)


def _cmd_tools_list(args: argparse.Namespace) -> int:
    catalog = load_catalog()
    rows = [_operation_row(operation) for operation in catalog.list_operations(tag=args.tag, write_only=args.write_only)]
    if args.format == "json":
        _print_json(
            {
                "kind": "generated_openapi_operations",
                "source": catalog.source,
                "source_version": catalog.source_version,
                "count": len(rows),
                "tools": rows,
            }
        )
        return 0
    print("Generated OpenAPI operations. For curated wrappers, run `clickup-agent hotkeys list`.")
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


def _cmd_tools_find(args: argparse.Namespace) -> int:
    terms = [str(item).strip() for item in args.query if str(item).strip()]
    catalog = load_catalog()
    rows = [
        _operation_row(operation)
        for operation in catalog.operations
        if _operation_matches_query(operation, terms)
    ]
    if args.format == "json":
        _print_json(
            {
                "kind": "generated_openapi_operations_search",
                "source": catalog.source,
                "source_version": catalog.source_version,
                "query": " ".join(terms),
                "count": len(rows),
                "tools": rows,
            }
        )
        return 0
    print(f"Generated OpenAPI operations matching: {' '.join(terms)}")
    _print_table(
        rows,
        [
            ("name", "Name"),
            ("operation_id", "Operation"),
            ("method", "Method"),
            ("path", "Path"),
            ("tags", "Tags"),
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
                "kind": "curated_wrappers",
                "source": catalog.source,
                "source_version": catalog.source_version,
                "count": len(rows),
                "hotkeys": rows,
            }
        )
        return 0
    print("Curated wrappers. For full generated OpenAPI operations, run `clickup-agent tools list`.")
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


def _cmd_dev_pr(args: argparse.Namespace) -> int:
    result = inspect_dev_pr(timeout=args.timeout)
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

    def add_setup_parser(name: str) -> None:
        setup = subcommands.add_parser(name, help="Create the native clickup-agent env file.")
        setup.add_argument("--api-key", help="ClickUp API token. Process env fallback: CLICKUP_API_KEY.")
        setup.add_argument(
            "--workspace-id",
            help="Default ClickUp workspace ID. Process env fallback: CLICKUP_WORKSPACE_ID.",
        )
        setup.add_argument(
            "--webhook-secret",
            help="Optional inbound webhook signing secret. Process env fallback: CLICKUP_WEBHOOK_SECRET.",
        )
        setup.add_argument("--non-interactive", action="store_true", help="Fail instead of prompting.")
        setup.add_argument("--force", action="store_true", help="Overwrite after backing up any existing env file.")
        setup.add_argument(
            "--print",
            action="store_true",
            dest="print_only",
            help="Show the redacted setup result without writing the env file.",
        )
        setup.add_argument(
            "--live-auth",
            action="store_true",
            help="After writing, run the read-only ClickUp live auth probe.",
        )
        setup.set_defaults(func=run_setup)

    add_setup_parser("setup")
    add_setup_parser("init")

    chat = subcommands.add_parser("chat", help="Start the future interactive ClickUp agent.")
    chat.set_defaults(func=_cmd_placeholder("chat", "interactive ClickUp work sessions"))

    mcp = subcommands.add_parser("mcp", help="Start the future LLM/MCP tool server.")
    mcp.set_defaults(func=_cmd_mcp)

    connect = subcommands.add_parser("connect", help="Print or write MCP client registration.")
    connect.add_argument("client", choices=["cursor", "claude-code", "codex", "generic"], help="Client to connect.")
    connect.add_argument("--write", action="store_true", help="Write or register the MCP config when supported.")
    connect.add_argument(
        "--scope",
        choices=["project", "global"],
        default="project",
        help="Cursor config scope when using `connect cursor --write`.",
    )
    connect.set_defaults(func=run_connect)

    tools = subcommands.add_parser("tools", help="Inspect future ClickUp tools.")
    tools_subcommands = tools.add_subparsers(dest="tools_command", required=True)
    tools_list = tools_subcommands.add_parser("list", help="List future ClickUp tools.")
    tools_list.add_argument("--format", choices=["table", "json"], default="table", help="Output format.")
    tools_list.add_argument("--tag", help="Filter operations by an OpenAPI tag such as Tasks.")
    tools_list.add_argument("--write-only", action="store_true", help="Only show operations that can mutate ClickUp.")
    tools_list.set_defaults(func=_cmd_tools_list)
    tools_find = tools_subcommands.add_parser("find", help="Find generated ClickUp operations by free text.")
    tools_find.add_argument("query", nargs="+", help="Case-insensitive query terms.")
    tools_find.add_argument("--format", choices=["table", "json"], default="table", help="Output format.")
    tools_find.set_defaults(func=_cmd_tools_find)

    hotkeys = subcommands.add_parser("hotkeys", help="Inspect future hotkey toolchains.")
    hotkeys_subcommands = hotkeys.add_subparsers(dest="hotkeys_command", required=True)
    hotkeys_list = hotkeys_subcommands.add_parser("list", help="List future hotkey toolchains.")
    hotkeys_list.add_argument("--format", choices=["table", "json"], default="table", help="Output format.")
    hotkeys_list.set_defaults(func=_cmd_hotkeys_list)

    run = subcommands.add_parser("run", help="Run a future hotkey or toolchain.")
    run.add_argument("name", help="Hotkey or toolchain name.")
    run.add_argument("tool_args", nargs=argparse.REMAINDER, help="Toolchain-specific flags.")
    run.set_defaults(func=_cmd_run)

    dev = subcommands.add_parser("dev", help="Read-only development helpers.")
    dev_subcommands = dev.add_subparsers(dest="dev_command", required=True)
    dev_pr = dev_subcommands.add_parser("pr", help="Inspect the current branch GitHub PR.")
    dev_pr.add_argument("--timeout", type=float, default=10.0, help="gh subprocess timeout in seconds.")
    dev_pr.set_defaults(func=_cmd_dev_pr)

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
