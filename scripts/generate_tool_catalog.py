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

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from clickup_agent.discovery import curated_wrapper_dicts  # noqa: E402

SOURCE_URL = "https://developer.clickup.com/openapi/clickup-api-v2-reference.json"
HTTP_METHODS = {"get", "post", "put", "patch", "delete"}
WRITE_METHODS = {"post", "put", "patch", "delete"}
DEFAULT_OUTPUT = Path("src/clickup_agent/catalog/tool_catalog.json")
GENERATED_OPERATION_SOURCE = "generated_operation"
CURATED_WRAPPER_SOURCE = "curated_wrapper"
GENERATED_OPERATION_FAMILY = "generated_openapi_operations"
CURATED_WRAPPER_FAMILY = "curated_wrappers"

COMMAND_FAMILIES = {
    GENERATED_OPERATION_FAMILY: {
        "source": GENERATED_OPERATION_SOURCE,
        "label": "Generated OpenAPI operations",
        "discovery_command": "clickup-agent tools list",
        "description": "Raw/generated ClickUp OpenAPI operations.",
        "run_note": (
            "Exact OpenAPI operation IDs such as UpdateTask run the generated operation. "
            "Catalog names are also available when no curated wrapper owns that kebab-case name."
        ),
    },
    CURATED_WRAPPER_FAMILY: {
        "source": CURATED_WRAPPER_SOURCE,
        "label": "Curated wrapper commands",
        "discovery_command": "clickup-agent hotkeys list",
        "description": "Curated wrapper commands for common agent workflows.",
        "run_note": "Kebab-case names such as update-task run curated wrappers with CLI-friendly flags.",
    },
}

def normalize_toolchain(toolchain: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(toolchain)
    operation_ids = [str(item) for item in enriched.get("operation_ids", ())]
    generated_word = "operation" if len(operation_ids) == 1 else "operations"
    generated_names = ", ".join(operation_ids)
    enriched.setdefault("source", CURATED_WRAPPER_SOURCE)
    enriched.setdefault("family", CURATED_WRAPPER_FAMILY)
    enriched.setdefault("label", "Curated wrapper commands")
    enriched.setdefault("command_family", CURATED_WRAPPER_FAMILY)
    enriched.setdefault("generated_operation_hint", f"For full API fields, use generated {generated_word} {generated_names}.")
    return enriched


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
                    "source": GENERATED_OPERATION_SOURCE,
                    "family": GENERATED_OPERATION_FAMILY,
                    "label": "Generated OpenAPI operations",
                    "command_family": GENERATED_OPERATION_FAMILY,
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
        "command_families": COMMAND_FAMILIES,
        "operations": sorted(operations, key=lambda item: (item["tags"], item["name"])),
        "toolchains": [normalize_toolchain(toolchain) for toolchain in curated_wrapper_dicts()],
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
