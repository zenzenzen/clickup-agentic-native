from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from generate_tool_catalog import normalize_catalog, tool_name  # noqa: E402

from clickup_agent.registry import load_catalog


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
                                    "properties": {"name": {"type": "string", "examples": ["Task"]}},
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
    }

    catalog = normalize_catalog(spec, "fixture")

    operation = catalog["operations"][0]
    assert operation["operation_id"] == "CreateTask"
    assert operation["method"] == "POST"
    assert operation["is_write"] is True
    assert operation["parameters"][0]["name"] == "list_id"
    assert operation["request_schema"]["required"] == ["name"]
    assert "examples" not in operation["request_schema"]
    assert operation["response_schema"]["statuses"]["200"]["schema_title"] == "CreateTaskResponse"
    assert {toolchain["name"] for toolchain in catalog["toolchains"]} >= {"search", "create-task", "timer"}


def test_committed_catalog_loads_required_toolchains() -> None:
    catalog = load_catalog()

    assert len(catalog.operations) > 100
    assert catalog.get_operation("CreateTask").path == "/v2/list/{list_id}/task"
    assert catalog.get_operation("UpdateTask").request_schema is not None
    assert catalog.get_toolchain("create task").name == "create-task"
