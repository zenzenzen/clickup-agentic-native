"""Build ClickUp HTTP requests from registry operations and user inputs.

This module is the catalog-to-HTTP translator: it turns generated operation
metadata plus wrapper/CLI payloads into one concrete request, and rejects any
leftover fields before they reach ClickUp.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

from .registry import ToolOperation


class OperationInputError(ValueError):
    """Raised when an operation payload cannot satisfy a registry contract."""


@dataclass(frozen=True)
class OperationRequest:
    """Concrete ClickUp request plus safe dry-run/live summaries."""

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

    def to_live_summary(self) -> dict[str, Any]:
        return {
            "operation_id": self.operation_id,
            "method": self.method,
            "path": self.path,
            "params": self.params,
        }


def _aliases(name: str) -> tuple[str, ...]:
    """Accept OpenAPI names and CLI-friendly snake/kebab-style spellings."""
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
    return path.replace(token, quote(str(value), safe=""))


def build_operation_request(operation: ToolOperation, payload: dict[str, Any]) -> OperationRequest:
    """Resolve path/query/header/body inputs for a generated operation."""
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

    # Curated wrappers pass explicit body when they need a narrower, intentional
    # mutation shape; raw generated operations can fall through to schema fields.
    json_body = _extract_body(operation, explicit_body, values)
    if values:
        unknown = ", ".join(sorted(values))
        raise OperationInputError(f"Unknown input field(s) for {operation.operation_id}: {unknown}")
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
    """Build the JSON body from an explicit wrapper body or schema fields."""
    if explicit_body is not None:
        if not isinstance(explicit_body, dict):
            raise OperationInputError("body must be a JSON object")
        return explicit_body

    schema = operation.request_schema or {}
    properties = schema.get("properties") if isinstance(schema, dict) else None
    if not isinstance(properties, dict):
        return None

    body = {key: remaining_values.pop(key) for key in list(remaining_values) if key in properties}
    required = schema.get("required")
    if body or (isinstance(required, list) and required):
        return body
    return None
