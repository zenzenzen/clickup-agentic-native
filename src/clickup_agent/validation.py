"""Input parsing and JSON Schema validation for ClickUp toolchains."""

from __future__ import annotations

import json
from typing import Any

from jsonschema import Draft202012Validator, ValidationError

from .registry import ToolOperation


class InputValidationError(ValueError):
    """Raised when CLI or toolchain input cannot be safely executed."""


def parse_json_object(raw: str | None) -> dict[str, Any]:
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


def validate_operation_body(operation: ToolOperation, body: dict[str, Any] | None) -> None:
    schema = operation.request_schema
    if schema is None or body is None:
        return
    try:
        Draft202012Validator(schema).validate(body)
    except ValidationError as exc:
        path = ".".join(str(part) for part in exc.path)
        location = f" at {path}" if path else ""
        raise InputValidationError(f"Invalid {operation.operation_id} body{location}: {exc.message}") from exc
