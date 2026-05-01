"""Build ClickUp HTTP requests from registry operations and user inputs."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .registry import ToolOperation


class OperationInputError(ValueError):
    """Raised when an operation payload cannot satisfy a registry contract."""


@dataclass(frozen=True)
class OperationRequest:
    operation_id: str
    method: str
    path: str
    params: dict[str, Any]
    headers: dict[str, str]
    json_body: dict[str, Any] | None

    def to_dry_run(self) -> dict[str, Any]:
        return {
            "operation_id": self.operation_id,
            "method": self.method,
            "path": self.path,
            "params": self.params,
            "headers": self.headers,
            "json": self.json_body,
        }


def _aliases(name: str) -> tuple[str, ...]:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "_", name).strip("_").lower()
    lowered = name.lower()
    return tuple(dict.fromkeys((name, lowered, normalized)))


def _pop_value(values: dict[str, Any], name: str) -> Any:
    for alias in _aliases(name):
        if alias in values:
            return values.pop(alias)
    return None


def _replace_path(path: str, name: str, value: Any) -> str:
    token = "{" + name + "}"
    if token not in path:
        return path
    return path.replace(token, str(value))


def build_operation_request(operation: ToolOperation, payload: dict[str, Any]) -> OperationRequest:
    values = dict(payload)
    path = operation.path
    params: dict[str, Any] = {}
    headers: dict[str, str] = {}

    explicit_body = values.pop("body", None)
    for parameter in operation.parameters:
        value = _pop_value(values, parameter.name)
        if value is None:
            if parameter.location == "header" and parameter.name.lower() == "content-type":
                value = "application/json"
            elif parameter.required:
                raise OperationInputError(f"Missing required {parameter.location} parameter: {parameter.name}")
            else:
                continue

        if parameter.location == "path":
            path = _replace_path(path, parameter.name, value)
        elif parameter.location == "query":
            params[parameter.name] = value
        elif parameter.location == "header":
            headers[parameter.name] = str(value)

    if "{" in path or "}" in path:
        raise OperationInputError(f"Unresolved path parameters for {operation.operation_id}: {path}")

    json_body = _extract_body(operation, explicit_body, values)
    return OperationRequest(
        operation_id=operation.operation_id,
        method=operation.method,
        path=path,
        params=params,
        headers=headers,
        json_body=json_body,
    )


def _extract_body(
    operation: ToolOperation,
    explicit_body: Any,
    remaining_values: dict[str, Any],
) -> dict[str, Any] | None:
    if explicit_body is not None:
        if not isinstance(explicit_body, dict):
            raise OperationInputError("body must be a JSON object")
        return explicit_body

    schema = operation.request_schema or {}
    properties = schema.get("properties") if isinstance(schema, dict) else None
    if not isinstance(properties, dict):
        return None

    body = {key: remaining_values.pop(key) for key in list(remaining_values) if key in properties}
    return body or None
