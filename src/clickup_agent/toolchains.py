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
ClientFactory = Callable[[str | None], ClickUpClient]


class ToolchainRunner:
    def __init__(
        self,
        catalog: ToolCatalog | None = None,
        *,
        client_factory: ClientFactory = ClickUpClient.from_environment,
    ) -> None:
        self.catalog = catalog or load_catalog()
        self.client_factory = client_factory
        self.handlers: dict[str, ToolchainHandler] = {
            "search": _run_search,
            "create-task": _run_create_task,
            "set-status": _run_set_status,
            "assign": _run_assign,
            "set-due-date": _run_set_due_date,
            "comment": _run_comment,
            "tags": _run_tags,
            "timer": _run_timer,
        }

    def run(self, name: str, argv: list[str]) -> RunResult:
        normalized = normalize_tool_name(name)
        options = self._parse_common(normalized, argv)
        handler = self.handlers.get(normalized)
        if handler is None:
            raise ToolchainError(f"Toolchain is not implemented yet: {normalized}")

        client: ClickUpClient | None = None
        if not options.dry_run:
            client = self.client_factory(options.env_file)
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


def _run_set_status(options: RunOptions, catalog: ToolCatalog, client: ClickUpClient | None) -> RunResult:
    flag_payload = _parse_tool_args(options.name, options.flag_payload["_argv"], _configure_set_status)
    payload = merge_inputs(options.json_payload, flag_payload)
    payload["body"] = {"status": payload.pop("status")}
    operation, response = _execute_operation(catalog, "UpdateTask", payload, dry_run=options.dry_run, client=client)
    return RunResult(options.name, options.dry_run, [operation], response)


def _configure_set_status(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--task-id", required=False)
    parser.add_argument("--status", required=True)
    parser.add_argument("--custom-task-ids", action="store_true", default=None)
    parser.add_argument("--team-id")


def _run_set_due_date(options: RunOptions, catalog: ToolCatalog, client: ClickUpClient | None) -> RunResult:
    flag_payload = _parse_tool_args(options.name, options.flag_payload["_argv"], _configure_set_due_date)
    payload = merge_inputs(options.json_payload, flag_payload)
    body: dict[str, Any] = {"due_date": _date_to_epoch_millis(str(payload.pop("due_date_iso")))}
    if "due_date_time" in payload:
        body["due_date_time"] = bool(payload.pop("due_date_time"))
    payload["body"] = body
    operation, response = _execute_operation(catalog, "UpdateTask", payload, dry_run=options.dry_run, client=client)
    return RunResult(options.name, options.dry_run, [operation], response)


def _configure_set_due_date(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--task-id", required=False)
    parser.add_argument("--due-date", dest="due_date_iso", required=True)
    parser.add_argument("--due-date-time", action="store_true", default=None)
    parser.add_argument("--custom-task-ids", action="store_true", default=None)
    parser.add_argument("--team-id")


def _run_assign(options: RunOptions, catalog: ToolCatalog, client: ClickUpClient | None) -> RunResult:
    flag_payload = _parse_tool_args(options.name, options.flag_payload["_argv"], _configure_assign)
    payload = merge_inputs(options.json_payload, flag_payload)
    mode = str(payload.pop("mode", "add"))
    assignee_ids = [int(item) for item in _csv_or_list(payload.pop("assignees", []))]
    if not assignee_ids:
        raise ToolchainError("assign requires at least one --assignee or assignees JSON value")

    operations: list[dict[str, Any]] = []
    if mode == "replace":
        get_payload = {
            key: value
            for key, value in payload.items()
            if key in {"task_id", "custom_task_ids", "team_id"}
        }
        get_operation, get_response = _execute_operation(
            catalog,
            "GetTask",
            get_payload,
            dry_run=options.dry_run,
            client=client,
        )
        operations.append(get_operation)
        remove_ids = _current_assignee_ids(get_response) if not options.dry_run else []
        body = {
            "assignees": {
                "add": assignee_ids,
                "rem": [item for item in remove_ids if item not in assignee_ids],
            }
        }
        if options.dry_run:
            body["replace_note"] = "Live run removes current assignees not in the requested replacement set."
    elif mode == "remove":
        body = {"assignees": {"add": [], "rem": assignee_ids}}
    elif mode == "add":
        body = {"assignees": {"add": assignee_ids, "rem": []}}
    else:
        raise ToolchainError("assign --mode must be add, remove, or replace")

    payload["body"] = body
    update_operation, response = _execute_operation(catalog, "UpdateTask", payload, dry_run=options.dry_run, client=client)
    operations.append(update_operation)
    return RunResult(options.name, options.dry_run, operations, response)


def _configure_assign(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--task-id", required=False)
    parser.add_argument("--assignee", dest="assignees", action="append")
    parser.add_argument("--mode", choices=["add", "remove", "replace"], default="add")
    parser.add_argument("--custom-task-ids", action="store_true", default=None)
    parser.add_argument("--team-id")


def _current_assignee_ids(response: Any) -> list[int]:
    if not isinstance(response, dict):
        return []
    assignees = response.get("assignees") or []
    if not isinstance(assignees, list):
        return []
    ids: list[int] = []
    for assignee in assignees:
        if isinstance(assignee, dict) and "id" in assignee:
            ids.append(int(assignee["id"]))
        elif isinstance(assignee, int):
            ids.append(assignee)
    return ids


def _run_comment(options: RunOptions, catalog: ToolCatalog, client: ClickUpClient | None) -> RunResult:
    flag_payload = _parse_tool_args(options.name, options.flag_payload["_argv"], _configure_comment)
    payload = merge_inputs(options.json_payload, flag_payload)
    body = {
        "comment_text": payload.pop("text"),
        "notify_all": bool(payload.pop("notify_all", False)),
    }
    if "assignee" in payload:
        body["assignee"] = int(payload.pop("assignee"))
    if "group_assignee" in payload:
        body["group_assignee"] = payload.pop("group_assignee")
    payload["body"] = body
    operation, response = _execute_operation(catalog, "CreateTaskComment", payload, dry_run=options.dry_run, client=client)
    return RunResult(options.name, options.dry_run, [operation], response)


def _configure_comment(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--task-id", required=False)
    parser.add_argument("--text", required=True)
    parser.add_argument("--notify-all", action="store_true", default=None)
    parser.add_argument("--assignee")
    parser.add_argument("--group-assignee")
    parser.add_argument("--custom-task-ids", action="store_true", default=None)
    parser.add_argument("--team-id")


def _run_tags(options: RunOptions, catalog: ToolCatalog, client: ClickUpClient | None) -> RunResult:
    flag_payload = _parse_tool_args(options.name, options.flag_payload["_argv"], _configure_tags)
    payload = merge_inputs(options.json_payload, flag_payload)
    adds = [str(item) for item in _csv_or_list(payload.pop("add", []))]
    removes = [str(item) for item in _csv_or_list(payload.pop("remove", []))]
    if not adds and not removes:
        raise ToolchainError("tags requires at least one --add or --remove value")

    operations: list[dict[str, Any]] = []
    responses: list[Any] = []
    base_payload = {
        key: value
        for key, value in payload.items()
        if key in {"task_id", "custom_task_ids", "team_id"}
    }
    for tag_name in adds:
        operation, response = _execute_operation(
            catalog,
            "AddTagToTask",
            {**base_payload, "tag_name": tag_name},
            dry_run=options.dry_run,
            client=client,
        )
        operations.append(operation)
        responses.append(response)
    for tag_name in removes:
        operation, response = _execute_operation(
            catalog,
            "RemoveTagFromTask",
            {**base_payload, "tag_name": tag_name},
            dry_run=options.dry_run,
            client=client,
        )
        operations.append(operation)
        responses.append(response)
    return RunResult(options.name, options.dry_run, operations, None if options.dry_run else responses)


def _configure_tags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--task-id", required=False)
    parser.add_argument("--add", action="append")
    parser.add_argument("--remove", action="append")
    parser.add_argument("--custom-task-ids", action="store_true", default=None)
    parser.add_argument("--team-id")


def _run_timer(options: RunOptions, catalog: ToolCatalog, client: ClickUpClient | None) -> RunResult:
    flag_payload = _parse_tool_args(options.name, options.flag_payload["_argv"], _configure_timer)
    payload = merge_inputs(options.json_payload, flag_payload)
    action = str(payload.pop("action", "current"))
    workspace_id = payload.pop("workspace_id", None) or payload.pop("team_id", None)
    if not workspace_id and client and client.config.workspace_id:
        workspace_id = client.config.workspace_id
    if not workspace_id:
        raise ToolchainError("timer requires --team-id, --workspace-id, or CLICKUP_WORKSPACE_ID")

    if action == "current":
        operation_payload = {"team_id": workspace_id}
        if "assignee" in payload:
            operation_payload["assignee"] = payload.pop("assignee")
        operation, response = _execute_operation(
            catalog,
            "Getrunningtimeentry",
            operation_payload,
            dry_run=options.dry_run,
            client=client,
        )
        return RunResult(options.name, options.dry_run, [operation], response)

    if action == "stop":
        operation, response = _execute_operation(
            catalog,
            "StopatimeEntry",
            {"team_id": workspace_id},
            dry_run=options.dry_run,
            client=client,
        )
        return RunResult(options.name, options.dry_run, [operation], response)

    if action == "start":
        body: dict[str, Any] = {}
        if "task_id" in payload:
            body["tid"] = payload.pop("task_id")
        if "description" in payload:
            body["description"] = payload.pop("description")
        if "tags" in payload:
            body["tags"] = [{"name": str(item)} for item in _csv_or_list(payload.pop("tags"))]
        if "billable" in payload:
            body["billable"] = bool(payload.pop("billable"))
        operation_payload = {
            "team_Id": workspace_id,
            "body": body,
        }
        if payload.get("custom_task_ids"):
            operation_payload["custom_task_ids"] = payload.pop("custom_task_ids")
            operation_payload["team_id"] = workspace_id
        operation, response = _execute_operation(
            catalog,
            "StartatimeEntry",
            operation_payload,
            dry_run=options.dry_run,
            client=client,
        )
        return RunResult(options.name, options.dry_run, [operation], response)

    raise ToolchainError("timer --action must be current, start, or stop")


def _configure_timer(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--action", choices=["current", "start", "stop"], default="current")
    parser.add_argument("--team-id")
    parser.add_argument("--workspace-id")
    parser.add_argument("--task-id")
    parser.add_argument("--description")
    parser.add_argument("--tag", dest="tags", action="append")
    parser.add_argument("--billable", action="store_true", default=None)
    parser.add_argument("--assignee")
    parser.add_argument("--custom-task-ids", action="store_true", default=None)
