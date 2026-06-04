"""Input parsing and JSON Schema validation for ClickUp toolchains.

Wrappers accept convenient CLI/MCP shapes, then this module normalizes simple
types and applies generated schema checks before a request can be dry-run or
sent live.
"""

from __future__ import annotations

import json
from datetime import date, datetime, time, timezone
from typing import Any

from jsonschema import Draft202012Validator, ValidationError

from .registry import ToolOperation


class InputValidationError(ValueError):
    """Raised when CLI or toolchain input cannot be safely executed."""


def parse_json_object(raw: str | None) -> dict[str, Any]:
    """Parse the shared --json payload format used by CLI and MCP adapters."""
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise InputValidationError(f"Invalid JSON payload: {exc.msg}") from exc
    if not isinstance(parsed, dict):
        raise InputValidationError("--json payload must be a JSON object")
    return parsed


def merge_inputs(json_payload: dict[str, Any], flag_payload: dict[str, Any]) -> dict[str, Any]:
    """Merge CLI flags over JSON so explicit flags can refine reusable payloads."""
    merged = dict(json_payload)
    for key, value in flag_payload.items():
        if value is not None:
            merged[key] = value
    return merged


def coerce_bool(value: Any, *, field: str) -> bool:
    """Coerce common CLI string booleans while rejecting ambiguous values."""
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in {0, 1}:
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "y", "on"}:
            return True
        if normalized in {"0", "false", "no", "n", "off"}:
            return False
    raise InputValidationError(f"{field} must be a boolean")


def coerce_int(value: Any, *, field: str) -> int:
    if isinstance(value, bool):
        raise InputValidationError(f"{field} must be an integer")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise InputValidationError(f"{field} must be an integer") from exc


def coerce_epoch_millis_date(value: Any, *, field: str) -> int:
    """Convert an ISO date into ClickUp's UTC midnight epoch-millis format."""
    if isinstance(value, date) and not isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = date.fromisoformat(value)
        except ValueError as exc:
            raise InputValidationError(f"{field} must be an ISO date like 2026-05-01") from exc
    else:
        raise InputValidationError(f"{field} must be an ISO date like 2026-05-01")
    return int(datetime.combine(parsed, time.min, tzinfo=timezone.utc).timestamp() * 1000)


def require_keys(payload: dict[str, Any], required: list[str], *, context: str) -> None:
    """Raise a corrective wrapper error when semantic inputs are absent."""
    missing = [key for key in required if payload.get(key) is None or payload.get(key) == ""]
    if missing:
        joined = ", ".join(missing)
        raise InputValidationError(f"{context} requires: {joined}")


def _is_open_object_schema(schema: dict[str, Any]) -> bool:
    additional = schema.get("additionalProperties")
    return additional is True or isinstance(additional, dict)


def _reject_unknown_body_keys(operation: ToolOperation, schema: dict[str, Any], body: dict[str, Any]) -> None:
    """Reject typos early when the generated schema declares a closed body."""
    properties = schema.get("properties")
    if not isinstance(properties, dict) or _is_open_object_schema(schema):
        return
    unknown = sorted(key for key in body if key not in properties)
    if unknown:
        joined = ", ".join(unknown)
        raise InputValidationError(f"Invalid {operation.operation_id} body: unknown field(s): {joined}")


def validate_operation_body(operation: ToolOperation, body: dict[str, Any] | None) -> None:
    """Validate generated-operation bodies before dry-run or live execution."""
    schema = operation.request_schema
    if schema is None:
        return
    body_to_validate = body if body is not None else {}
    _reject_unknown_body_keys(operation, schema, body_to_validate)
    try:
        Draft202012Validator(schema).validate(body_to_validate)
    except ValidationError as exc:
        path = ".".join(str(part) for part in exc.path)
        location = f" at {path}" if path else ""
        raise InputValidationError(f"Invalid {operation.operation_id} body{location}: {exc.message}") from exc
