#!/usr/bin/env python3
"""Generate the committed ClickUp tool catalog from the official OpenAPI spec."""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
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
        "name": "create-task",
        "summary": "Create a task in a ClickUp list.",
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
        "name": "assign",
        "summary": "Add, remove, or replace task assignees.",
        "operation_ids": ["UpdateTask"],
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


def request_schema(operation: dict[str, Any]) -> dict[str, Any] | None:
    content = operation.get("requestBody", {}).get("content", {})
    schema = content.get("application/json", {}).get("schema")
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
            "schema_ref": json_schema.get("$ref"),
        }
    return {"statuses": statuses} if statuses else None


def normalize_parameter(parameter: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": parameter["name"],
        "location": parameter["in"],
        "required": bool(parameter.get("required", False)),
        "schema": compact_schema(parameter.get("schema") or {}) or {},
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
                        normalize_parameter(parameter)
                        for parameter in operation.get("parameters", [])
                        if parameter.get("in") in {"path", "query", "header"} and parameter.get("name")
                    ],
                    "request_schema": request_schema(operation),
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
