"""Native setup command for the canonical clickup-agent env file."""

from __future__ import annotations

import argparse
import getpass
import os
import sys
from collections.abc import Callable

from .config import CLICKUP_ENV_WRITE_ORDER, default_env_file, write_env_file


def run_live_auth_check() -> int:
    """Run the CLI live auth probe after setup writes configuration."""
    from .cli import _run_live_auth_check

    return _run_live_auth_check()


def _value_from_sources(cli_value: str | None, env_key: str) -> str:
    if cli_value is not None:
        return cli_value
    return os.environ.get(env_key, "")


def _prompt_value(label: str, *, secret: bool, required: bool) -> str:
    while True:
        if secret:
            value = getpass.getpass(f"{label}: ")
        else:
            value = input(f"{label}: ")
        if value or not required:
            return value
        print("This value is required.", file=sys.stderr)


def _resolve_values(
    args: argparse.Namespace,
    *,
    stdin_isatty: Callable[[], bool] = sys.stdin.isatty,
) -> dict[str, str]:
    values = {
        "CLICKUP_API_KEY": _value_from_sources(args.api_key, "CLICKUP_API_KEY"),
        "CLICKUP_WORKSPACE_ID": _value_from_sources(args.workspace_id, "CLICKUP_WORKSPACE_ID"),
        "CLICKUP_WEBHOOK_SECRET": _value_from_sources(args.webhook_secret, "CLICKUP_WEBHOOK_SECRET"),
    }

    can_prompt = stdin_isatty() and not args.non_interactive
    if can_prompt:
        if not values["CLICKUP_API_KEY"]:
            values["CLICKUP_API_KEY"] = _prompt_value("Paste your ClickUp API token", secret=True, required=True)
        if not values["CLICKUP_WORKSPACE_ID"]:
            values["CLICKUP_WORKSPACE_ID"] = _prompt_value(
                "Default ClickUp workspace ID (optional)",
                secret=False,
                required=False,
            )
        if not values["CLICKUP_WEBHOOK_SECRET"]:
            values["CLICKUP_WEBHOOK_SECRET"] = _prompt_value(
                "Webhook/signing secret for inbound ClickUp events (optional)",
                secret=True,
                required=False,
            )

    return values


def _print_redacted_summary(values: dict[str, str], *, env_written: bool) -> None:
    env_file = default_env_file()
    action = "Would write" if not env_written else "Wrote"
    print(f"{action}: {env_file}")
    for key in CLICKUP_ENV_WRITE_ORDER:
        if key == "CLICKUP_WEBHOOK_SECRET":
            label = "configured" if values.get(key) else "optional / missing"
        else:
            label = "configured" if values.get(key) else "missing"
        print(f"{key}: {label}")


def run_setup(args: argparse.Namespace) -> int:
    """Resolve setup inputs, optionally write them, and print a redacted summary."""
    values = _resolve_values(args)
    if not values["CLICKUP_API_KEY"]:
        print("CLICKUP_API_KEY is required for clickup-agent setup.", file=sys.stderr)
        return 2

    if args.print_only:
        _print_redacted_summary(values, env_written=False)
        return 0

    write_env_file(values, force=args.force)
    _print_redacted_summary(values, env_written=True)
    if args.live_auth:
        return run_live_auth_check()
    return 0
