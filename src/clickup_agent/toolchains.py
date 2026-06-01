"""Curated ClickUp run toolchains built on the generated operation registry."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import Any, Callable

from .client import ClickUpApiError, ClickUpClient
from .config import ConfigError, load_workspace_id
from .registry import ToolCatalog, ToolOperation, load_catalog, normalize_tool_name
from .requests import OperationInputError, OperationRequest, build_operation_request
from .validation import (
    InputValidationError,
    coerce_bool,
    coerce_epoch_millis_date,
    coerce_int,
    merge_inputs,
    parse_json_object,
    require_keys,
)


class ToolchainError(RuntimeError):
    """Raised when a requested run toolchain cannot be parsed or executed."""


@dataclass(frozen=True)
class RunOptions:
    name: str
    json_payload: dict[str, Any]
    flag_payload: dict[str, Any]
    dry_run: bool
    live: bool

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
ClientFactory = Callable[[], ClickUpClient]


class ToolchainRunner:
    def __init__(
        self,
        catalog: ToolCatalog | None = None,
        *,
        client_factory: ClientFactory | None = None,
    ) -> None:
        self.catalog = catalog or load_catalog()
        self.client_factory = client_factory or ClickUpClient.from_environment
        self.handlers: dict[str, ToolchainHandler] = {
            "search": _run_search,
            "list-hierarchy": _run_list_hierarchy,
            "create-task": _run_create_task,
            "create-subtask": _run_create_subtask,
            "set-status": _run_set_status,
            "set-description": _run_set_description,
            "update-task": _run_update_task,
            "assign": _run_assign,
            "assign-me": _run_assign_me,
            "set-due-date": _run_set_due_date,
            "comment": _run_comment,
            "edit-comment": _run_edit_comment,
            "create-checklist": _run_create_checklist,
            "create-checklist-item": _run_create_checklist_item,
            "check-item": _run_check_item,
            "subtasks": _run_subtasks,
            "tags": _run_tags,
            "timer": _run_timer,
        }

    def run(self, name: str, argv: list[str]) -> RunResult:
        normalized = normalize_tool_name(name)
        options = self._parse_common(normalized, argv)
        handler = self.handlers.get(normalized)
        operation = None if handler is not None else self._resolve_generated_operation(name, normalized)
        if handler is None and operation is None:
            raise ToolchainError(f"No implemented toolchain or generated operation found for: {normalized}")
        if any(item in {"-h", "--help"} for item in options.flag_payload.get("_argv", [])):
            if handler is not None:
                return handler(options, self.catalog, None)
            return _run_generated_operation(operation, options, self.catalog, None)

        client: ClickUpClient | None = None
        if not options.dry_run:
            try:
                client = self.client_factory()
            except ConfigError as exc:
                raise ToolchainError(str(exc)) from exc
        try:
            if handler is not None:
                return handler(options, self.catalog, client)
            return _run_generated_operation(operation, options, self.catalog, client)
        finally:
            if client is not None:
                client.close()

    def _parse_common(self, name: str, argv: list[str]) -> RunOptions:
        parser = argparse.ArgumentParser(prog=f"clickup-agent run {name}", add_help=False)
        _add_common_run_arguments(parser)
        known, remaining = parser.parse_known_args(argv)
        if known.dry_run and known.live:
            raise ToolchainError("Use either --dry-run or --live, not both")
        try:
            json_payload = parse_json_object(known.json_payload)
        except InputValidationError as exc:
            raise ToolchainError(str(exc)) from exc
        dry_run = bool(known.dry_run)
        if not known.live and not dry_run:
            dry_run = self._defaults_to_dry_run(name)
        return RunOptions(
            name=name,
            json_payload=json_payload,
            flag_payload={"_argv": remaining},
            dry_run=dry_run,
            live=bool(known.live),
        )

    def _defaults_to_dry_run(self, name: str) -> bool:
        try:
            return self.catalog.get_toolchain(name).is_write
        except KeyError:
            pass
        operation = self._resolve_generated_operation(name)
        return bool(operation and operation.is_write)

    def _resolve_generated_operation(self, *names: str) -> ToolOperation | None:
        for name in names:
            try:
                return self.catalog.get_operation_by_name_or_id(name)
            except KeyError:
                continue
        return None


def run_toolchain(name: str, argv: list[str]) -> RunResult:
    return ToolchainRunner().run(name, argv)


def _argument_parser(name: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=f"clickup-agent run {name}", add_help=True)
    _add_common_run_arguments(parser)
    return parser


def _add_common_run_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--json", dest="json_payload", help="JSON object with toolchain inputs.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=None,
        help="Preview resolved operations without calling ClickUp.",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        default=None,
        help="Execute the toolchain against ClickUp.",
    )


def _parse_tool_args(name: str, argv: list[str], configure: Callable[[argparse.ArgumentParser], None]) -> dict[str, Any]:
    parser = _argument_parser(name)
    configure(parser)
    namespace = parser.parse_args(argv)
    return {key: value for key, value in vars(namespace).items() if value is not None}


def _run_generated_operation(
    operation: ToolOperation,
    options: RunOptions,
    catalog: ToolCatalog,
    client: ClickUpClient | None,
) -> RunResult:
    flag_payload = _parse_generated_operation_args(operation, options.flag_payload["_argv"])
    payload = merge_inputs(options.json_payload, flag_payload)
    executed_operation, response = _execute_operation(
        catalog,
        operation.operation_id,
        payload,
        dry_run=options.dry_run,
        client=client,
    )
    return RunResult(operation.name, options.dry_run, [executed_operation], response)


def _parse_generated_operation_args(operation: ToolOperation, argv: list[str]) -> dict[str, Any]:
    parser = _argument_parser(operation.name)
    parser.description = operation.summary or f"Run generated ClickUp operation {operation.operation_id}."
    field_schemas = _generated_operation_field_schemas(operation)
    for field, schema in field_schemas.items():
        flag = f"--{normalize_tool_name(field)}"
        kwargs: dict[str, Any] = {"dest": _generated_arg_dest(field), "required": False}
        if _schema_type(schema) == "boolean":
            kwargs.update({"nargs": "?", "const": True})
        elif _schema_type(schema) == "array":
            kwargs["action"] = "append"
        parser.add_argument(flag, **kwargs)
    namespace = parser.parse_args(argv)
    parsed: dict[str, Any] = {}
    for field, schema in field_schemas.items():
        dest = _generated_arg_dest(field)
        value = getattr(namespace, dest)
        if value is not None:
            parsed[dest] = _coerce_generated_arg(value, schema, field=dest)
    return parsed


def _generated_operation_field_schemas(operation: ToolOperation) -> dict[str, dict[str, Any]]:
    fields: dict[str, dict[str, Any]] = {}
    normalized_flags: set[str] = set()

    def add_field(field: str, schema: dict[str, Any]) -> None:
        flag_key = normalize_tool_name(field)
        if flag_key in normalized_flags:
            return
        normalized_flags.add(flag_key)
        fields[field] = schema

    for parameter in operation.parameters:
        add_field(parameter.name, parameter.schema)
    schema = operation.request_schema or {}
    properties = schema.get("properties") if isinstance(schema, dict) else None
    if isinstance(properties, dict):
        for field, property_schema in properties.items():
            if isinstance(property_schema, dict):
                add_field(str(field), property_schema)
    return fields


def _generated_arg_dest(field: str) -> str:
    return normalize_tool_name(field).replace("-", "_")


def _schema_type(schema: dict[str, Any]) -> str | None:
    raw_type = schema.get("type")
    if isinstance(raw_type, list):
        return next((item for item in raw_type if item != "null"), None)
    if isinstance(raw_type, str):
        return raw_type
    return None


def _coerce_generated_arg(value: Any, schema: dict[str, Any], *, field: str) -> Any:
    schema_type = _schema_type(schema)
    if schema_type == "boolean":
        return _bool(value, field=field)
    if schema_type == "integer":
        return _int(value, field=field)
    if schema_type == "number":
        return _number(value, field=field)
    if schema_type == "array":
        return _coerce_generated_array(value, schema, field=field)
    if schema_type == "object" and isinstance(value, str):
        try:
            return parse_json_object(value)
        except InputValidationError as exc:
            raise ToolchainError(str(exc)) from exc
    return value


def _coerce_generated_array(value: Any, schema: dict[str, Any], *, field: str) -> list[Any]:
    if isinstance(value, list):
        raw_items: list[Any] = []
        for item in value:
            if isinstance(item, str) and item.strip().startswith("["):
                try:
                    parsed = parse_json_object(f'{{"items": {item}}}')["items"]
                except InputValidationError as exc:
                    raise ToolchainError(str(exc)) from exc
                if not isinstance(parsed, list):
                    raise ToolchainError(f"{field} must be an array")
                raw_items.extend(parsed)
            elif isinstance(item, str) and "," in item:
                raw_items.extend(part.strip() for part in item.split(",") if part.strip())
            else:
                raw_items.append(item)
    elif isinstance(value, str) and value.strip().startswith("["):
        try:
            parsed = parse_json_object(f'{{"items": {value}}}')["items"]
        except InputValidationError as exc:
            raise ToolchainError(str(exc)) from exc
        if not isinstance(parsed, list):
            raise ToolchainError(f"{field} must be an array")
        raw_items = parsed
    elif isinstance(value, str):
        raw_items = [part.strip() for part in value.split(",") if part.strip()]
    else:
        raw_items = [value]

    item_schema = schema.get("items")
    if not isinstance(item_schema, dict):
        return raw_items
    return [_coerce_generated_arg(item, item_schema, field=field) for item in raw_items]


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
    if request.json_body is not None or operation.request_schema is not None:
        try:
            from .validation import validate_operation_body

            validate_operation_body(operation, request.json_body)
        except InputValidationError as exc:
            raise ToolchainError(str(exc)) from exc

    if dry_run:
        return request.to_dry_run(), None
    if client is None:
        raise ToolchainError("Live execution requires a ClickUp client")
    try:
        response = client.request(
            request.method,
            request.path,
            params=request.params,
            json_body=request.json_body,
            headers=request.headers,
        )
    except ClickUpApiError as exc:
        raise ToolchainError(str(exc)) from exc
    return request.to_live_summary(), response


def _date_to_epoch_millis(value: Any, *, field: str) -> int:
    try:
        return coerce_epoch_millis_date(value, field=field)
    except InputValidationError as exc:
        raise ToolchainError(str(exc)) from exc


def _int(value: Any, *, field: str) -> int:
    try:
        return coerce_int(value, field=field)
    except InputValidationError as exc:
        raise ToolchainError(str(exc)) from exc


def _bool(value: Any, *, field: str) -> bool:
    try:
        return coerce_bool(value, field=field)
    except InputValidationError as exc:
        raise ToolchainError(str(exc)) from exc


def _number(value: Any, *, field: str) -> int | float:
    if isinstance(value, bool):
        raise ToolchainError(f"{field} must be a number")
    if isinstance(value, int | float):
        return value
    if isinstance(value, str):
        try:
            if "." in value:
                return float(value)
            return int(value)
        except ValueError as exc:
            raise ToolchainError(f"{field} must be a number") from exc
    raise ToolchainError(f"{field} must be a number")


def _require(payload: dict[str, Any], keys: list[str], *, context: str) -> None:
    try:
        require_keys(payload, keys, context=context)
    except InputValidationError as exc:
        raise ToolchainError(str(exc)) from exc


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
        workspace_id = payload.pop("workspace_id", None) or payload.pop("team_id", None)
        if workspace_id:
            payload["team_Id"] = workspace_id
        elif client and client.config.workspace_id:
            payload["team_Id"] = client.config.workspace_id
        else:
            workspace_id = load_workspace_id()
            if workspace_id:
                payload["team_Id"] = workspace_id

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


def _run_list_hierarchy(options: RunOptions, catalog: ToolCatalog, client: ClickUpClient | None) -> RunResult:
    flag_payload = _parse_tool_args(options.name, options.flag_payload["_argv"], _configure_list_hierarchy)
    payload = merge_inputs(options.json_payload, flag_payload)
    archived = _bool(payload.pop("archived"), field="archived") if "archived" in payload else None
    workspace_id = payload.pop("workspace_id", None) or payload.pop("team_id", None)
    if not workspace_id and client and client.config.workspace_id:
        workspace_id = client.config.workspace_id
    if not workspace_id:
        workspace_id = load_workspace_id()

    operations: list[dict[str, Any]] = []
    if "folder_id" in payload:
        folder_operation, folder_response = _execute_operation(
            catalog,
            "GetLists",
            _hierarchy_payload({"folder_id": payload.pop("folder_id")}, archived),
            dry_run=options.dry_run,
            client=client,
        )
        operations.append(folder_operation)
        response = None if options.dry_run else {"lists": _compact_named_items(_items(folder_response, "lists"))}
        return RunResult(options.name, options.dry_run, operations, response)

    if "space_id" in payload:
        space = _resolve_space_hierarchy(catalog, payload.pop("space_id"), archived, options.dry_run, client, operations)
        return RunResult(options.name, options.dry_run, operations, None if options.dry_run else {"spaces": [space]})

    if not workspace_id:
        teams_operation, teams_response = _execute_operation(
            catalog,
            "GetAuthorizedTeams",
            {},
            dry_run=options.dry_run,
            client=client,
        )
        operations.append(teams_operation)
        if options.dry_run:
            operations[0]["note"] = "Live run lists authorized workspaces when no workspace id is configured."
            return RunResult(options.name, True, operations)
        return RunResult(options.name, False, operations, {"workspaces": _compact_named_items(_items(teams_response, "teams"))})

    workspace = _resolve_workspace_hierarchy(catalog, workspace_id, archived, options.dry_run, client, operations)
    return RunResult(options.name, options.dry_run, operations, None if options.dry_run else {"workspaces": [workspace]})


def _configure_list_hierarchy(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--team-id")
    parser.add_argument("--workspace-id")
    parser.add_argument("--space-id")
    parser.add_argument("--folder-id")
    parser.add_argument("--archived", action="store_true", default=None)


def _hierarchy_payload(payload: dict[str, Any], archived: bool | None) -> dict[str, Any]:
    if archived is not None:
        payload["archived"] = archived
    return payload


def _resolve_workspace_hierarchy(
    catalog: ToolCatalog,
    workspace_id: Any,
    archived: bool | None,
    dry_run: bool,
    client: ClickUpClient | None,
    operations: list[dict[str, Any]],
) -> dict[str, Any]:
    spaces_operation, spaces_response = _execute_operation(
        catalog,
        "GetSpaces",
        _hierarchy_payload({"team_id": workspace_id}, archived),
        dry_run=dry_run,
        client=client,
    )
    operations.append(spaces_operation)
    workspace = {"id": str(workspace_id), "name": None, "spaces": []}
    if dry_run:
        spaces_operation["note"] = "Live run expands each returned space into folders and lists."
        return workspace
    workspace["spaces"] = [
        _resolve_space_hierarchy(catalog, space.get("id"), archived, dry_run, client, operations, source=space)
        for space in _items(spaces_response, "spaces")
        if isinstance(space, dict) and space.get("id") is not None
    ]
    return workspace


def _resolve_space_hierarchy(
    catalog: ToolCatalog,
    space_id: Any,
    archived: bool | None,
    dry_run: bool,
    client: ClickUpClient | None,
    operations: list[dict[str, Any]],
    *,
    source: dict[str, Any] | None = None,
) -> dict[str, Any]:
    folders_operation, folders_response = _execute_operation(
        catalog,
        "GetFolders",
        _hierarchy_payload({"space_id": space_id}, archived),
        dry_run=dry_run,
        client=client,
    )
    operations.append(folders_operation)
    folderless_operation, folderless_response = _execute_operation(
        catalog,
        "GetFolderlessLists",
        _hierarchy_payload({"space_id": space_id}, archived),
        dry_run=dry_run,
        client=client,
    )
    operations.append(folderless_operation)
    space = {
        **_compact_named_item(source or {"id": space_id}),
        "lists": [],
        "folders": [],
    }
    if dry_run:
        folders_operation["note"] = "Live run expands each returned folder into lists."
        return space
    space["lists"] = _compact_named_items(_items(folderless_response, "lists"))
    space["folders"] = [
        _resolve_folder_hierarchy(catalog, folder, archived, dry_run, client, operations)
        for folder in _items(folders_response, "folders")
        if isinstance(folder, dict) and folder.get("id") is not None
    ]
    return space


def _resolve_folder_hierarchy(
    catalog: ToolCatalog,
    folder: dict[str, Any],
    archived: bool | None,
    dry_run: bool,
    client: ClickUpClient | None,
    operations: list[dict[str, Any]],
) -> dict[str, Any]:
    lists_operation, lists_response = _execute_operation(
        catalog,
        "GetLists",
        _hierarchy_payload({"folder_id": folder.get("id")}, archived),
        dry_run=dry_run,
        client=client,
    )
    operations.append(lists_operation)
    compact = _compact_named_item(folder)
    compact["lists"] = [] if dry_run else _compact_named_items(_items(lists_response, "lists"))
    return compact


def _items(response: Any, key: str) -> list[Any]:
    if isinstance(response, dict) and isinstance(response.get(key), list):
        return response[key]
    return []


def _compact_named_items(items: list[Any]) -> list[dict[str, Any]]:
    return [_compact_named_item(item) for item in items if isinstance(item, dict)]


def _compact_named_item(item: dict[str, Any]) -> dict[str, Any]:
    compact: dict[str, Any] = {"id": str(item.get("id")) if item.get("id") is not None else None}
    if "name" in item:
        compact["name"] = item.get("name")
    return compact


def _run_create_task(options: RunOptions, catalog: ToolCatalog, client: ClickUpClient | None) -> RunResult:
    flag_payload = _parse_tool_args(options.name, options.flag_payload["_argv"], _configure_create_task)
    payload = merge_inputs(options.json_payload, flag_payload)
    _require(payload, ["list_id"], context="create-task")
    _normalize_create_task_payload(payload)

    operation, response = _execute_operation(catalog, "CreateTask", payload, dry_run=options.dry_run, client=client)
    return RunResult(options.name, options.dry_run, [operation], response)


def _normalize_create_task_payload(payload: dict[str, Any]) -> None:
    if "due_date_iso" in payload:
        payload["due_date"] = _date_to_epoch_millis(payload.pop("due_date_iso"), field="due_date")
    if "assignees" in payload:
        payload["assignees"] = [_int(item, field="assignees") for item in _csv_or_list(payload["assignees"])]
    if "tags" in payload:
        payload["tags"] = [str(item) for item in _csv_or_list(payload["tags"])]


def _configure_create_task(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--list-id", required=False)
    parser.add_argument("--name")
    parser.add_argument("--description")
    parser.add_argument("--status")
    parser.add_argument("--assignee", dest="assignees", action="append")
    parser.add_argument("--tag", dest="tags", action="append")
    parser.add_argument("--due-date", dest="due_date_iso")


def _run_create_subtask(options: RunOptions, catalog: ToolCatalog, client: ClickUpClient | None) -> RunResult:
    flag_payload = _parse_tool_args(options.name, options.flag_payload["_argv"], _configure_create_subtask)
    payload = merge_inputs(options.json_payload, flag_payload)
    _require(payload, ["list_id", "parent", "name"], context="create-subtask")
    _normalize_create_task_payload(payload)

    operation, response = _execute_operation(catalog, "CreateTask", payload, dry_run=options.dry_run, client=client)
    return RunResult(options.name, options.dry_run, [operation], response)


def _configure_create_subtask(parser: argparse.ArgumentParser) -> None:
    _configure_create_task(parser)
    parser.add_argument("--parent")


def _run_set_status(options: RunOptions, catalog: ToolCatalog, client: ClickUpClient | None) -> RunResult:
    flag_payload = _parse_tool_args(options.name, options.flag_payload["_argv"], _configure_set_status)
    payload = merge_inputs(options.json_payload, flag_payload)
    _require(payload, ["task_id", "status"], context="set-status")
    payload["body"] = {"status": payload.pop("status")}
    operation, response = _execute_operation(catalog, "UpdateTask", payload, dry_run=options.dry_run, client=client)
    return RunResult(options.name, options.dry_run, [operation], response)


def _configure_set_status(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--task-id", required=False)
    parser.add_argument("--status")
    parser.add_argument("--custom-task-ids", action="store_true", default=None)
    parser.add_argument("--team-id")


def _run_set_description(options: RunOptions, catalog: ToolCatalog, client: ClickUpClient | None) -> RunResult:
    flag_payload = _parse_tool_args(options.name, options.flag_payload["_argv"], _configure_set_description)
    payload = merge_inputs(options.json_payload, flag_payload)
    _require(payload, ["task_id"], context="set-description")
    body = {key: payload.pop(key) for key in ("description", "markdown_content") if key in payload}
    if not body:
        raise ToolchainError("set-description requires --description or --markdown-content")
    payload["body"] = body
    operation, response = _execute_operation(catalog, "UpdateTask", payload, dry_run=options.dry_run, client=client)
    return RunResult(options.name, options.dry_run, [operation], response)


def _configure_set_description(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--task-id", required=False)
    parser.add_argument("--description")
    parser.add_argument("--markdown-content", dest="markdown_content")
    parser.add_argument("--custom-task-ids", action="store_true", default=None)
    parser.add_argument("--team-id")


def _run_update_task(options: RunOptions, catalog: ToolCatalog, client: ClickUpClient | None) -> RunResult:
    flag_payload = _parse_tool_args(options.name, options.flag_payload["_argv"], _configure_update_task)
    payload = merge_inputs(options.json_payload, flag_payload)
    _require(payload, ["task_id"], context="update-task")
    body: dict[str, Any] = {}
    for key in ("name", "description", "markdown_content", "parent"):
        if key in payload:
            body[key] = payload.pop(key)
    for key in ("priority", "time_estimate"):
        if key in payload:
            body[key] = _int(payload.pop(key), field=key)
    if "points" in payload:
        body["points"] = _number(payload.pop("points"), field="points")
    for key in ("archived", "due_date_time", "start_date_time"):
        if key in payload:
            body[key] = _bool(payload.pop(key), field=key)
    if "due_date_iso" in payload:
        body["due_date"] = _date_to_epoch_millis(payload.pop("due_date_iso"), field="due_date")
    if "start_date_iso" in payload:
        body["start_date"] = _date_to_epoch_millis(payload.pop("start_date_iso"), field="start_date")
    if not body:
        raise ToolchainError("update-task requires at least one field to change")
    payload["body"] = body
    operation, response = _execute_operation(catalog, "UpdateTask", payload, dry_run=options.dry_run, client=client)
    return RunResult(options.name, options.dry_run, [operation], response)


def _configure_update_task(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--task-id", required=False)
    parser.add_argument("--name")
    parser.add_argument("--description")
    parser.add_argument("--markdown-content", dest="markdown_content")
    parser.add_argument("--priority")
    parser.add_argument("--due-date", dest="due_date_iso")
    parser.add_argument("--due-date-time", action="store_true", default=None)
    parser.add_argument("--start-date", dest="start_date_iso")
    parser.add_argument("--start-date-time", action="store_true", default=None)
    parser.add_argument("--points")
    parser.add_argument("--time-estimate")
    parser.add_argument("--archived", action="store_true", default=None)
    parser.add_argument("--parent")
    parser.add_argument("--custom-task-ids", action="store_true", default=None)
    parser.add_argument("--team-id")


def _run_set_due_date(options: RunOptions, catalog: ToolCatalog, client: ClickUpClient | None) -> RunResult:
    flag_payload = _parse_tool_args(options.name, options.flag_payload["_argv"], _configure_set_due_date)
    payload = merge_inputs(options.json_payload, flag_payload)
    _require(payload, ["task_id", "due_date_iso"], context="set-due-date")
    body: dict[str, Any] = {"due_date": _date_to_epoch_millis(payload.pop("due_date_iso"), field="due_date")}
    if "due_date_time" in payload:
        body["due_date_time"] = _bool(payload.pop("due_date_time"), field="due_date_time")
    payload["body"] = body
    operation, response = _execute_operation(catalog, "UpdateTask", payload, dry_run=options.dry_run, client=client)
    return RunResult(options.name, options.dry_run, [operation], response)


def _configure_set_due_date(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--task-id", required=False)
    parser.add_argument("--due-date", dest="due_date_iso")
    parser.add_argument("--due-date-time", action="store_true", default=None)
    parser.add_argument("--custom-task-ids", action="store_true", default=None)
    parser.add_argument("--team-id")


def _run_assign(options: RunOptions, catalog: ToolCatalog, client: ClickUpClient | None) -> RunResult:
    flag_payload = _parse_tool_args(options.name, options.flag_payload["_argv"], _configure_assign)
    payload = merge_inputs(options.json_payload, flag_payload)
    _require(payload, ["task_id"], context="assign")
    mode = str(payload.pop("mode", "add"))
    assignee_ids = [_int(item, field="assignees") for item in _csv_or_list(payload.pop("assignees", []))]
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
    elif mode == "remove":
        body = {"assignees": {"add": [], "rem": assignee_ids}}
    elif mode == "add":
        body = {"assignees": {"add": assignee_ids, "rem": []}}
    else:
        raise ToolchainError("assign --mode must be add, remove, or replace")

    payload["body"] = body
    update_operation, response = _execute_operation(catalog, "UpdateTask", payload, dry_run=options.dry_run, client=client)
    if options.dry_run and mode == "replace":
        update_operation["note"] = "Live run removes current assignees not in the requested replacement set."
    operations.append(update_operation)
    return RunResult(options.name, options.dry_run, operations, response)


def _run_assign_me(options: RunOptions, catalog: ToolCatalog, client: ClickUpClient | None) -> RunResult:
    flag_payload = _parse_tool_args(options.name, options.flag_payload["_argv"], _configure_assign_me)
    payload = merge_inputs(options.json_payload, flag_payload)
    _require(payload, ["task_id"], context="assign-me")
    mode = str(payload.pop("mode", "add"))
    if mode not in {"add", "remove", "replace"}:
        raise ToolchainError("assign-me --mode must be add, remove, or replace")

    workspace_id = payload.get("team_id")
    if not workspace_id and client and client.config.workspace_id:
        workspace_id = client.config.workspace_id
    if not workspace_id:
        workspace_id = load_workspace_id()
    if workspace_id and payload.get("custom_task_ids") and "team_id" not in payload:
        payload["team_id"] = workspace_id

    user_operation, user_response = _execute_operation(
        catalog,
        "GetAuthorizedUser",
        {},
        dry_run=options.dry_run,
        client=client,
    )
    assignee_id: Any = 0
    if not options.dry_run:
        assignee_id = _authorized_user_id(user_response)

    body, extra_operations = _assignment_body(mode, [assignee_id], payload, catalog, options.dry_run, client)
    payload["body"] = body
    update_operation, response = _execute_operation(catalog, "UpdateTask", payload, dry_run=options.dry_run, client=client)
    if options.dry_run:
        _replace_self_placeholder(update_operation)
        update_operation["note"] = "Live run resolves the authorized user id and substitutes it in assignees.add."
    return RunResult(options.name, options.dry_run, [user_operation, *extra_operations, update_operation], response)


def _configure_assign(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--task-id", required=False)
    parser.add_argument("--assignee", dest="assignees", action="append")
    parser.add_argument("--mode", choices=["add", "remove", "replace"], default=None)
    parser.add_argument("--custom-task-ids", action="store_true", default=None)
    parser.add_argument("--team-id")


def _configure_assign_me(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--task-id", required=False)
    parser.add_argument("--mode", choices=["add", "remove", "replace"], default=None)
    parser.add_argument("--custom-task-ids", action="store_true", default=None)
    parser.add_argument("--team-id")


def _authorized_user_id(response: Any) -> int:
    if not isinstance(response, dict) or not isinstance(response.get("user"), dict):
        raise ToolchainError("GetAuthorizedUser returned an unexpected response")
    if "id" not in response["user"]:
        raise ToolchainError("GetAuthorizedUser response did not include user.id")
    return _int(response["user"]["id"], field="authorized user id")


def _replace_self_placeholder(operation: dict[str, Any]) -> None:
    body = operation.get("json")
    if not isinstance(body, dict):
        return
    assignees = body.get("assignees")
    if not isinstance(assignees, dict):
        return
    for key in ("add", "rem"):
        values = assignees.get(key)
        if isinstance(values, list):
            assignees[key] = ["<self>" if item == 0 else item for item in values]


def _assignment_body(
    mode: str,
    assignee_ids: list[Any],
    payload: dict[str, Any],
    catalog: ToolCatalog,
    dry_run: bool,
    client: ClickUpClient | None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
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
            dry_run=dry_run,
            client=client,
        )
        remove_ids = _current_assignee_ids(get_response) if not dry_run else []
        return (
            {
                "assignees": {
                    "add": assignee_ids,
                    "rem": [item for item in remove_ids if item not in assignee_ids],
                }
            },
            [get_operation],
        )
    if mode == "remove":
        return {"assignees": {"add": [], "rem": assignee_ids}}, []
    if mode == "add":
        return {"assignees": {"add": assignee_ids, "rem": []}}, []
    raise ToolchainError("assign --mode must be add, remove, or replace")


def _current_assignee_ids(response: Any) -> list[int]:
    if not isinstance(response, dict):
        return []
    assignees = response.get("assignees") or []
    if not isinstance(assignees, list):
        return []
    ids: list[int] = []
    for assignee in assignees:
        if isinstance(assignee, dict) and "id" in assignee:
            ids.append(_int(assignee["id"], field="assignee id"))
        elif isinstance(assignee, int):
            ids.append(assignee)
    return ids


def _run_comment(options: RunOptions, catalog: ToolCatalog, client: ClickUpClient | None) -> RunResult:
    flag_payload = _parse_tool_args(options.name, options.flag_payload["_argv"], _configure_comment)
    payload = merge_inputs(options.json_payload, flag_payload)
    _require(payload, ["task_id", "text"], context="comment")
    body = {
        "comment_text": payload.pop("text"),
        "notify_all": _bool(payload.pop("notify_all", False), field="notify_all"),
    }
    if "assignee" in payload:
        body["assignee"] = _int(payload.pop("assignee"), field="assignee")
    if "group_assignee" in payload:
        body["group_assignee"] = payload.pop("group_assignee")
    payload["body"] = body
    operation, response = _execute_operation(catalog, "CreateTaskComment", payload, dry_run=options.dry_run, client=client)
    return RunResult(options.name, options.dry_run, [operation], response)


def _configure_comment(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--task-id", required=False)
    parser.add_argument("--text")
    parser.add_argument("--notify-all", action="store_true", default=None)
    parser.add_argument("--assignee")
    parser.add_argument("--group-assignee")
    parser.add_argument("--custom-task-ids", action="store_true", default=None)
    parser.add_argument("--team-id")


def _run_edit_comment(options: RunOptions, catalog: ToolCatalog, client: ClickUpClient | None) -> RunResult:
    flag_payload = _parse_tool_args(options.name, options.flag_payload["_argv"], _configure_edit_comment)
    payload = merge_inputs(options.json_payload, flag_payload)
    _require(payload, ["comment_id", "text", "assignee"], context="edit-comment")
    if "resolved" not in payload:
        raise ToolchainError("edit-comment requires --resolved or --unresolved")
    body = {
        "comment_text": payload.pop("text"),
        "assignee": _int(payload.pop("assignee"), field="assignee"),
        "resolved": _bool(payload.pop("resolved"), field="resolved"),
    }
    payload["body"] = body
    operation, response = _execute_operation(catalog, "UpdateComment", payload, dry_run=options.dry_run, client=client)
    return RunResult(options.name, options.dry_run, [operation], response)


def _configure_edit_comment(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--comment-id", required=False)
    parser.add_argument("--text")
    parser.add_argument("--assignee")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--resolved", dest="resolved", action="store_true", default=None)
    group.add_argument("--unresolved", dest="resolved", action="store_false", default=None)


def _run_create_checklist(options: RunOptions, catalog: ToolCatalog, client: ClickUpClient | None) -> RunResult:
    flag_payload = _parse_tool_args(options.name, options.flag_payload["_argv"], _configure_create_checklist)
    payload = merge_inputs(options.json_payload, flag_payload)
    _require(payload, ["task_id", "name"], context="create-checklist")
    payload["body"] = {"name": payload.pop("name")}
    operation, response = _execute_operation(catalog, "CreateChecklist", payload, dry_run=options.dry_run, client=client)
    return RunResult(options.name, options.dry_run, [operation], response)


def _configure_create_checklist(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--task-id", required=False)
    parser.add_argument("--name")
    parser.add_argument("--custom-task-ids", action="store_true", default=None)
    parser.add_argument("--team-id")


def _run_create_checklist_item(options: RunOptions, catalog: ToolCatalog, client: ClickUpClient | None) -> RunResult:
    flag_payload = _parse_tool_args(options.name, options.flag_payload["_argv"], _configure_create_checklist_item)
    payload = merge_inputs(options.json_payload, flag_payload)
    _require(payload, ["checklist_id", "name"], context="create-checklist-item")
    body: dict[str, Any] = {"name": payload.pop("name")}
    if "assignee" in payload:
        body["assignee"] = _int(payload.pop("assignee"), field="assignee")
    payload["body"] = body
    operation, response = _execute_operation(
        catalog,
        "CreateChecklistItem",
        payload,
        dry_run=options.dry_run,
        client=client,
    )
    return RunResult(options.name, options.dry_run, [operation], response)


def _configure_create_checklist_item(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--checklist-id", required=False)
    parser.add_argument("--name")
    parser.add_argument("--assignee")


def _run_check_item(options: RunOptions, catalog: ToolCatalog, client: ClickUpClient | None) -> RunResult:
    flag_payload = _parse_tool_args(options.name, options.flag_payload["_argv"], _configure_check_item)
    payload = merge_inputs(options.json_payload, flag_payload)
    _require(payload, ["checklist_id", "item_id"], context="check-item")
    payload["checklist_item_id"] = payload.pop("item_id")
    body: dict[str, Any] = {}
    if "resolved" in payload:
        body["resolved"] = _bool(payload.pop("resolved"), field="resolved")
    if "name" in payload:
        body["name"] = payload.pop("name")
    if "assignee" in payload:
        body["assignee"] = _int(payload.pop("assignee"), field="assignee")
    if "parent" in payload:
        body["parent"] = payload.pop("parent")
    if not body:
        raise ToolchainError("check-item requires at least one field to change")
    payload["body"] = body
    operation, response = _execute_operation(catalog, "EditChecklistItem", payload, dry_run=options.dry_run, client=client)
    return RunResult(options.name, options.dry_run, [operation], response)


def _configure_check_item(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--checklist-id", required=False)
    parser.add_argument("--item-id")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--resolved", dest="resolved", action="store_true", default=None)
    group.add_argument("--unresolved", dest="resolved", action="store_false", default=None)
    parser.add_argument("--name")
    parser.add_argument("--assignee")
    parser.add_argument("--parent")


def _run_subtasks(options: RunOptions, catalog: ToolCatalog, client: ClickUpClient | None) -> RunResult:
    flag_payload = _parse_tool_args(options.name, options.flag_payload["_argv"], _configure_subtasks)
    payload = merge_inputs(options.json_payload, flag_payload)
    _require(payload, ["task_id"], context="subtasks")
    payload["include_subtasks"] = True
    operation, response = _execute_operation(catalog, "GetTask", payload, dry_run=options.dry_run, client=client)
    if options.dry_run:
        return RunResult(options.name, True, [operation])
    if isinstance(response, dict):
        return RunResult(
            options.name,
            False,
            [operation],
            {"task_id": response.get("id"), "subtasks": response.get("subtasks", [])},
        )
    return RunResult(options.name, False, [operation], response)


def _configure_subtasks(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--task-id", required=False)
    parser.add_argument("--custom-task-ids", action="store_true", default=None)
    parser.add_argument("--team-id")
    parser.add_argument("--include-markdown-description", dest="include_markdown_description", action="store_true", default=None)


def _run_tags(options: RunOptions, catalog: ToolCatalog, client: ClickUpClient | None) -> RunResult:
    flag_payload = _parse_tool_args(options.name, options.flag_payload["_argv"], _configure_tags)
    payload = merge_inputs(options.json_payload, flag_payload)
    _require(payload, ["task_id"], context="tags")
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
        workspace_id = load_workspace_id()
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
            body["billable"] = _bool(payload.pop("billable"), field="billable")
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
    parser.add_argument("--action", choices=["current", "start", "stop"], default=None)
    parser.add_argument("--team-id")
    parser.add_argument("--workspace-id")
    parser.add_argument("--task-id")
    parser.add_argument("--description")
    parser.add_argument("--tag", dest="tags", action="append")
    parser.add_argument("--billable", action="store_true", default=None)
    parser.add_argument("--assignee")
    parser.add_argument("--custom-task-ids", action="store_true", default=None)
