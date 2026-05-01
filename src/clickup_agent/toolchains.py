"""Curated ClickUp run toolchains built on the generated operation registry."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from typing import Any, Callable

from .client import ClickUpClient
from .registry import ToolCatalog, load_catalog, normalize_tool_name
from .requests import OperationInputError, OperationRequest, build_operation_request
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
        self.handlers: dict[str, ToolchainHandler] = {
            "search": _run_search,
            "create-task": _run_create_task,
        }

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


def _argument_parser(name: str) -> argparse.ArgumentParser:
    return argparse.ArgumentParser(prog=f"clickup-agent run {name}", add_help=True)


def _parse_tool_args(name: str, argv: list[str], configure: Callable[[argparse.ArgumentParser], None]) -> dict[str, Any]:
    parser = _argument_parser(name)
    configure(parser)
    namespace = parser.parse_args(argv)
    return {key: value for key, value in vars(namespace).items() if value is not None}


def _execute_operation(
    catalog: ToolCatalog,
    operation_id: str,
    payload: dict[str, Any],
    *,
    dry_run: bool,
    client: ClickUpClient | None,
) -> tuple[dict[str, Any], Any]:
    operation = catalog.get_operation(operation_id)
    try:
        request = build_operation_request(operation, payload)
    except OperationInputError as exc:
        raise ToolchainError(str(exc)) from exc
    if request.json_body is not None:
        try:
            from .validation import validate_operation_body

            validate_operation_body(operation, request.json_body)
        except InputValidationError as exc:
            raise ToolchainError(str(exc)) from exc

    dry_run_payload = request.to_dry_run()
    if dry_run:
        return dry_run_payload, None
    if client is None:
        raise ToolchainError("Live execution requires a ClickUp client")
    return dry_run_payload, client.request(
        request.method,
        request.path,
        params=request.params,
        json_body=request.json_body,
        headers=request.headers,
    )


def _date_to_epoch_millis(value: str) -> int:
    parsed = date.fromisoformat(value)
    return int(datetime.combine(parsed, time.min, tzinfo=timezone.utc).timestamp() * 1000)


def _csv_or_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return [value]


def _run_search(options: RunOptions, catalog: ToolCatalog, client: ClickUpClient | None) -> RunResult:
    flag_payload = _parse_tool_args(options.name, options.flag_payload["_argv"], _configure_search)
    payload = merge_inputs(options.json_payload, flag_payload)
    query = str(payload.pop("query", "") or "").strip().lower()
    list_id = payload.get("list_id")
    operation_id = "GetTasks" if list_id else "GetFilteredTeamTasks"
    if operation_id == "GetFilteredTeamTasks":
        workspace_id = payload.pop("workspace_id", None) or payload.get("team_id")
        if workspace_id:
            payload["team_Id"] = workspace_id
        elif client and client.config.workspace_id:
            payload["team_Id"] = client.config.workspace_id

    operation, response = _execute_operation(catalog, operation_id, payload, dry_run=options.dry_run, client=client)
    if options.dry_run:
        if query:
            operation["client_filter"] = {"query": query}
        return RunResult(options.name, True, [operation])

    filtered_response = _filter_task_response(response, query) if query else response
    return RunResult(options.name, False, [operation], filtered_response)


def _configure_search(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--team-id", dest="team_id")
    parser.add_argument("--workspace-id")
    parser.add_argument("--list-id")
    parser.add_argument("--query")
    parser.add_argument("--page", type=int)
    parser.add_argument("--include-closed", action="store_true", default=None)
    parser.add_argument("--status", dest="statuses", action="append")
    parser.add_argument("--assignee", dest="assignees", action="append")
    parser.add_argument("--tag", dest="tags", action="append")


def _filter_task_response(response: Any, query: str) -> Any:
    if not isinstance(response, dict) or "tasks" not in response or not isinstance(response["tasks"], list):
        return response
    tasks = [task for task in response["tasks"] if _task_matches_query(task, query)]
    filtered = dict(response)
    filtered["tasks"] = tasks
    filtered["client_filter"] = {"query": query, "matched": len(tasks)}
    return filtered


def _task_matches_query(task: Any, query: str) -> bool:
    if not isinstance(task, dict):
        return False
    haystack = " ".join(
        str(task.get(key, ""))
        for key in ("id", "custom_id", "name", "text_content", "description", "url")
    ).lower()
    return query in haystack


def _run_create_task(options: RunOptions, catalog: ToolCatalog, client: ClickUpClient | None) -> RunResult:
    flag_payload = _parse_tool_args(options.name, options.flag_payload["_argv"], _configure_create_task)
    payload = merge_inputs(options.json_payload, flag_payload)
    if "due_date_iso" in payload:
        payload["due_date"] = _date_to_epoch_millis(str(payload.pop("due_date_iso")))
    if "assignees" in payload:
        payload["assignees"] = [int(item) for item in _csv_or_list(payload["assignees"])]
    if "tags" in payload:
        payload["tags"] = [str(item) for item in _csv_or_list(payload["tags"])]

    operation, response = _execute_operation(catalog, "CreateTask", payload, dry_run=options.dry_run, client=client)
    return RunResult(options.name, options.dry_run, [operation], response)


def _configure_create_task(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--list-id", required=False)
    parser.add_argument("--name")
    parser.add_argument("--description")
    parser.add_argument("--status")
    parser.add_argument("--assignee", dest="assignees", action="append")
    parser.add_argument("--tag", dest="tags", action="append")
    parser.add_argument("--due-date", dest="due_date_iso")
