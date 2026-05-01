"""Curated ClickUp run toolchains built on the generated operation registry."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import Any, Callable

from .client import ClickUpClient
from .registry import ToolCatalog, load_catalog, normalize_tool_name
from .validation import InputValidationError, merge_inputs, parse_json_object


class ToolchainError(RuntimeError):
    """Raised when a requested run toolchain cannot be parsed or executed."""


@dataclass(frozen=True)
class RunOptions:
    name: str
    json_payload: dict[str, Any]
    flag_payload: dict[str, Any]
    dry_run: bool
    env_file: str | None

    @property
    def payload(self) -> dict[str, Any]:
        return merge_inputs(self.json_payload, self.flag_payload)


@dataclass(frozen=True)
class RunResult:
    toolchain: str
    dry_run: bool
    operations: list[dict[str, Any]]
    response: Any = None

    def to_dict(self) -> dict[str, Any]:
        data = {
            "toolchain": self.toolchain,
            "dry_run": self.dry_run,
            "operations": self.operations,
        }
        if self.response is not None:
            data["response"] = self.response
        return data


ToolchainHandler = Callable[[RunOptions, ToolCatalog, ClickUpClient | None], RunResult]


class ToolchainRunner:
    def __init__(self, catalog: ToolCatalog | None = None) -> None:
        self.catalog = catalog or load_catalog()
        self.handlers: dict[str, ToolchainHandler] = {}

    def run(self, name: str, argv: list[str]) -> RunResult:
        normalized = normalize_tool_name(name)
        options = self._parse_common(normalized, argv)
        handler = self.handlers.get(normalized)
        if handler is None:
            raise ToolchainError(f"Toolchain is not implemented yet: {normalized}")

        client: ClickUpClient | None = None
        if not options.dry_run:
            client = ClickUpClient.from_environment(options.env_file)
        try:
            return handler(options, self.catalog, client)
        finally:
            if client is not None:
                client.close()

    def _parse_common(self, name: str, argv: list[str]) -> RunOptions:
        parser = argparse.ArgumentParser(prog=f"clickup-agent run {name}")
        parser.add_argument("--json", dest="json_payload", help="JSON object with toolchain inputs.")
        parser.add_argument("--dry-run", action="store_true", help="Preview resolved operations without calling ClickUp.")
        parser.add_argument("--env-file", help="Path to a local env file such as .env.local.")
        known, remaining = parser.parse_known_args(argv)
        try:
            json_payload = parse_json_object(known.json_payload)
        except InputValidationError as exc:
            raise ToolchainError(str(exc)) from exc
        return RunOptions(
            name=name,
            json_payload=json_payload,
            flag_payload={"_argv": remaining},
            dry_run=known.dry_run,
            env_file=known.env_file,
        )


def run_toolchain(name: str, argv: list[str]) -> RunResult:
    return ToolchainRunner().run(name, argv)
