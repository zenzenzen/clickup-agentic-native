from __future__ import annotations

import json
import sys
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from generate_tool_catalog import normalize_catalog, tool_name  # noqa: E402

from clickup_agent.discovery import CURATED_WRAPPER_NAMES
from clickup_agent.registry import load_catalog
from clickup_agent.toolchains import ToolchainRunner


def test_tool_name_normalizes_operation_ids() -> None:
    assert tool_name("CreateTask") == "create-task"
    assert tool_name("Getrunningtimeentry") == "getrunningtimeentry"
    assert tool_name("GetTask'sTimeinStatus") == "get-task-s-timein-status"


def test_normalize_catalog_extracts_operations_and_toolchains() -> None:
    spec = {
        "info": {"version": "test"},
        "paths": {
            "/v2/list/{list_id}/task": {
                "post": {
                    "operationId": "CreateTask",
                    "summary": "Create Task",
                    "tags": ["Tasks"],
                    "parameters": [
                        {
                            "name": "list_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                        }
                    ],
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "required": ["name"],
                                    "properties": {
                                        "name": {"$ref": "#/components/schemas/TaskName"},
                                    },
                                    "examples": [{"name": "Task"}],
                                }
                            }
                        }
                    },
                    "responses": {
                        "200": {
                            "description": "ok",
                            "content": {"application/json": {"schema": {"title": "CreateTaskResponse"}}},
                        }
                    },
                }
            }
        },
        "components": {
            "schemas": {
                "TaskName": {"type": "string", "examples": ["Task"]},
            }
        },
    }

    catalog = normalize_catalog(spec, "fixture")

    operation = catalog["operations"][0]
    assert operation["operation_id"] == "CreateTask"
    assert operation["method"] == "POST"
    assert operation["is_write"] is True
    assert operation["parameters"][0]["name"] == "list_id"
    assert operation["request_schema"]["required"] == ["name"]
    assert operation["request_schema"]["properties"]["name"] == {"type": "string"}
    assert "examples" not in operation["request_schema"]
    assert operation["response_schema"]["statuses"]["200"]["schema_title"] == "CreateTaskResponse"
    assert {toolchain["name"] for toolchain in catalog["toolchains"]} == CURATED_WRAPPER_NAMES


def test_normalize_catalog_rejects_external_refs() -> None:
    spec = {
        "info": {"version": "test"},
        "paths": {
            "/v2/test": {
                "post": {
                    "operationId": "CreateThing",
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "https://example.com/schema.json#/Thing"}
                            }
                        }
                    },
                    "responses": {},
                }
            }
        },
    }

    with pytest.raises(ValueError, match="External \\$ref"):
        normalize_catalog(spec, "fixture")


def test_normalize_catalog_rejects_cyclic_refs() -> None:
    spec = {
        "info": {"version": "test"},
        "paths": {
            "/v2/test": {
                "post": {
                    "operationId": "CreateThing",
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/A"}
                            }
                        }
                    },
                    "responses": {},
                }
            }
        },
        "components": {
            "schemas": {
                "A": {"$ref": "#/components/schemas/B"},
                "B": {"$ref": "#/components/schemas/A"},
            }
        },
    }

    with pytest.raises(ValueError, match="Cyclic local \\$ref"):
        normalize_catalog(spec, "fixture")


def test_committed_catalog_loads_required_toolchains() -> None:
    catalog = load_catalog()

    assert len(catalog.operations) > 100
    assert catalog.get_operation("CreateTask").path == "/v2/list/{list_id}/task"
    assert catalog.get_operation("UpdateTask").request_schema is not None
    assert catalog.get_toolchain("create task").name == "create-task"
    assert {toolchain.name for toolchain in catalog.toolchains} == CURATED_WRAPPER_NAMES
    assert "$ref" not in (ROOT / "src/clickup_agent/catalog/tool_catalog.json").read_text(encoding="utf-8")


def test_curated_wrapper_metadata_matches_runner_handlers_and_catalog() -> None:
    catalog = load_catalog()

    assert set(ToolchainRunner().handlers) == CURATED_WRAPPER_NAMES
    assert {toolchain.name for toolchain in catalog.toolchains} == CURATED_WRAPPER_NAMES


def test_curated_wrapper_metadata_import_is_lightweight() -> None:
    script = """
import json
import sys
import clickup_agent.discovery
print(json.dumps({name: name in sys.modules for name in ["httpx", "clickup_agent.mcp_server", "clickup_agent.devsync", "clickup_agent.toolchains"]}))
"""

    result = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(result.stdout) == {
        "httpx": False,
        "clickup_agent.mcp_server": False,
        "clickup_agent.devsync": False,
        "clickup_agent.toolchains": False,
    }


def test_catalog_load_is_cached() -> None:
    load_catalog.cache_clear()

    first = load_catalog()
    second = load_catalog()

    assert first is second
