#!/usr/bin/env python3
"""Generate the committed ClickUp tool catalog from the official OpenAPI spec."""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from urllib.parse import unquote
from pathlib import Path
from typing import Any

SOURCE_URL = "https://developer.clickup.com/openapi/clickup-api-v2-reference.json"
HTTP_METHODS = {"get", "post", "put", "patch", "delete"}
WRITE_METHODS = {"post", "put", "patch", "delete"}
DEFAULT_OUTPUT = Path("src/clickup_agent/catalog/tool_catalog.json")

TOOLCHAINS = [
    {
        "name": "search",
        "summary": "Search and filter tasks across a workspace or list.",
        "operation_ids": ["GetFilteredTeamTasks", "GetTasks"],
        "is_write": False,
    },
    {
        "name": "list-hierarchy",
        "summary": "List workspace, space, folder, and list names and IDs.",
        "operation_ids": ["GetAuthorizedTeams", "GetSpaces", "GetFolders", "GetLists", "GetFolderlessLists"],
        "is_write": False,
    },
    {
        "name": "create-task",
        "summary": "Create a task in a ClickUp list.",
        "operation_ids": ["CreateTask"],
        "is_write": True,
    },
    {
        "name": "create-subtask",
        "summary": "Create a subtask under a parent task.",
        "operation_ids": ["CreateTask"],
        "is_write": True,
    },
    {
        "name": "set-status",
        "summary": "Update a task status.",
        "operation_ids": ["UpdateTask"],
        "is_write": True,
    },
    {
        "name": "set-description",
        "summary": "Update a task description (plain or markdown).",
        "operation_ids": ["UpdateTask"],
        "is_write": True,
    },
    {
        "name": "update-task",
        "summary": "Update arbitrary fields on a task.",
        "operation_ids": ["UpdateTask"],
        "is_write": True,
    },
    {
        "name": "assign",
        "summary": "Add, remove, or replace task assignees.",
        "operation_ids": ["GetTask", "UpdateTask"],
        "is_write": True,
    },
    {
        "name": "assign-me",
        "summary": "Assign the authorized user to a task.",
        "operation_ids": ["GetAuthorizedUser", "UpdateTask"],
        "is_write": True,
    },
    {
        "name": "set-due-date",
        "summary": "Set or clear a task due date.",
        "operation_ids": ["UpdateTask"],
        "is_write": True,
    },
    {
        "name": "comment",
        "summary": "Add a comment to a task.",
        "operation_ids": ["CreateTaskComment"],
        "is_write": True,
    },
    {
        "name": "edit-comment",
        "summary": "Edit an existing comment.",
        "operation_ids": ["UpdateComment"],
        "is_write": True,
    },
    {
        "name": "create-checklist",
        "summary": "Create a checklist on a task.",
        "operation_ids": ["CreateChecklist"],
        "is_write": True,
    },
    {
        "name": "create-checklist-item",
        "summary": "Add an item to a checklist.",
        "operation_ids": ["CreateChecklistItem"],
        "is_write": True,
    },
    {
        "name": "check-item",
        "summary": "Edit a checklist item (resolve, rename, reparent, reassign).",
        "operation_ids": ["EditChecklistItem"],
        "is_write": True,
    },
    {
        "name": "subtasks",
        "summary": "Fetch a task with its subtasks expanded.",
        "operation_ids": ["GetTask"],
        "is_write": False,
    },
    {
        "name": "tags",
        "summary": "Add or remove tags on a task.",
        "operation_ids": ["AddTagToTask", "RemoveTagFromTask"],
        "is_write": True,
    },
    {
        "name": "timer",
        "summary": "Inspect, start, or stop the running timer.",
        "operation_ids": ["Getrunningtimeentry", "StartatimeEntry", "StopatimeEntry"],
        "is_write": True,
    },
]


def load_spec(url: str, path: Path | None) -> dict[str, Any]:
    if path is not None:
        return json.loads(path.read_text(encoding="utf-8"))
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "clickup-agent-catalog-generator/0.1"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def tool_name(operation_id: str) -> str:
    with_boundaries = re.sub(r"(.)([A-Z][a-z]+)", r"\1-\2", operation_id)
    dashed = re.sub(r"([a-z0-9])([A-Z])", r"\1-\2", with_boundaries)
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", dashed).strip("-")
    return cleaned.lower()


def _decode_pointer_token(token: str) -> str:
    return unquote(token).replace("~1", "/").replace("~0", "~")


def _resolve_pointer(document: dict[str, Any], ref: str) -> Any:
    if not ref.startswith("#/"):
        raise ValueError(f"External $ref is not supported: {ref}")
    current: Any = document
    for raw_token in ref[2:].split("/"):
        token = _decode_pointer_token(raw_token)
        if not isinstance(current, dict) or token not in current:
            raise ValueError(f"Unresolvable local $ref: {ref}")
        current = current[token]
    return current


def resolve_local_refs(value: Any, document: dict[str, Any], stack: tuple[str, ...] = ()) -> Any:
    if isinstance(value, list):
        return [resolve_local_refs(item, document, stack) for item in value]
    if not isinstance(value, dict):
        return value
    ref = value.get("$ref")
    if isinstance(ref, str):
        if ref in stack:
            cycle = " -> ".join((*stack, ref))
            raise ValueError(f"Cyclic local $ref detected: {cycle}")
        resolved = resolve_local_refs(_resolve_pointer(document, ref), document, (*stack, ref))
        if not isinstance(resolved, dict):
            return resolved
        siblings = {key: item for key, item in value.items() if key != "$ref"}
        if not siblings:
            return resolved
        return resolve_local_refs({**resolved, **siblings}, document, stack)
    return {key: resolve_local_refs(item, document, stack) for key, item in value.items()}


def compact_schema(schema: dict[str, Any] | None) -> dict[str, Any] | None:
    if not schema:
        return None
    allowed = {
        "$ref",
        "type",
        "title",
        "required",
        "properties",
        "items",
        "enum",
        "oneOf",
        "anyOf",
        "allOf",
        "additionalProperties",
        "nullable",
        "format",
        "contentEncoding",
        "minimum",
        "maximum",
    }
    compact: dict[str, Any] = {}
    for key, value in schema.items():
        if key not in allowed:
            continue
        if key == "properties" and isinstance(value, dict):
            compact[key] = {
                name: compact_schema(property_schema) or {}
                for name, property_schema in sorted(value.items())
                if isinstance(property_schema, dict)
            }
        elif key in {"items", "additionalProperties"} and isinstance(value, dict):
            compact[key] = compact_schema(value) or {}
        elif key in {"oneOf", "anyOf", "allOf"} and isinstance(value, list):
            compact[key] = [compact_schema(item) or {} for item in value if isinstance(item, dict)]
        else:
            compact[key] = value
    return compact or None


def request_schema(operation: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any] | None:
    content = operation.get("requestBody", {}).get("content", {})
    schema = content.get("application/json", {}).get("schema")
    if isinstance(schema, dict):
        schema = resolve_local_refs(schema, spec)
    return compact_schema(schema)


def response_schema(operation: dict[str, Any]) -> dict[str, Any] | None:
    statuses: dict[str, Any] = {}
    for status, response in sorted(operation.get("responses", {}).items()):
        content = response.get("content", {}) if isinstance(response, dict) else {}
        json_schema = content.get("application/json", {}).get("schema") or {}
        statuses[status] = {
            "description": response.get("description", "") if isinstance(response, dict) else "",
            "content_types": sorted(content),
            "schema_title": json_schema.get("title"),
            "schema_ref": None,
        }
    return {"statuses": statuses} if statuses else None


def normalize_parameter(parameter: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any]:
    schema = parameter.get("schema") or {}
    if isinstance(schema, dict):
        schema = resolve_local_refs(schema, spec)
    return {
        "name": parameter["name"],
        "location": parameter["in"],
        "required": bool(parameter.get("required", False)),
        "schema": compact_schema(schema) or {},
        "description": parameter.get("description", ""),
    }


def normalize_catalog(spec: dict[str, Any], source_url: str) -> dict[str, Any]:
    operations: list[dict[str, Any]] = []
    for path, path_item in spec.get("paths", {}).items():
        for method, operation in path_item.items():
            if method not in HTTP_METHODS:
                continue
            operation_id = operation.get("operationId")
            if not operation_id:
                continue
            operations.append(
                {
                    "operation_id": operation_id,
                    "name": tool_name(operation_id),
                    "summary": operation.get("summary", ""),
                    "method": method.upper(),
                    "path": path,
                    "tags": operation.get("tags", []),
                    "parameters": [
                        normalize_parameter(parameter, spec)
                        for parameter in operation.get("parameters", [])
                        if parameter.get("in") in {"path", "query", "header"} and parameter.get("name")
                    ],
                    "request_schema": request_schema(operation, spec),
                    "response_schema": response_schema(operation),
                    "is_write": method in WRITE_METHODS,
                }
            )
    return {
        "source": source_url,
        "source_version": str(spec.get("info", {}).get("version", "")),
        "operations": sorted(operations, key=lambda item: (item["tags"], item["name"])),
        "toolchains": TOOLCHAINS,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate the ClickUp tool catalog.")
    parser.add_argument("--url", default=SOURCE_URL, help="OpenAPI JSON URL to ingest.")
    parser.add_argument("--spec-path", type=Path, help="Read OpenAPI JSON from a local file.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Catalog JSON output path.")
    args = parser.parse_args(argv)

    spec = load_spec(args.url, args.spec_path)
    catalog = normalize_catalog(spec, args.url)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(catalog, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote {len(catalog['operations'])} operations to {args.output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
