"""Typed registry for generated and curated ClickUp tool metadata."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from importlib import resources
from typing import Any, Iterable, Literal

HttpMethod = Literal["GET", "POST", "PUT", "PATCH", "DELETE"]
ParameterLocation = Literal["path", "query", "header"]
ToolKind = Literal["operation", "toolchain"]

CATALOG_PACKAGE = "clickup_agent.catalog"
CATALOG_RESOURCE = "tool_catalog.json"


@dataclass(frozen=True)
class ToolParameter:
    """A path, query, or header parameter exposed by an OpenAPI operation."""

    name: str
    location: ParameterLocation
    required: bool
    schema: dict[str, Any]
    description: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ToolParameter:
        return cls(
            name=str(data["name"]),
            location=data["location"],
            required=bool(data.get("required", False)),
            schema=dict(data.get("schema") or {}),
            description=str(data.get("description") or ""),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "location": self.location,
            "required": self.required,
            "schema": self.schema,
            "description": self.description,
        }


@dataclass(frozen=True)
class ToolOperation:
    """A normalized ClickUp API operation from the generated OpenAPI catalog."""

    operation_id: str
    name: str
    summary: str
    method: HttpMethod
    path: str
    tags: tuple[str, ...]
    parameters: tuple[ToolParameter, ...]
    request_schema: dict[str, Any] | None
    response_schema: dict[str, Any] | None
    is_write: bool

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ToolOperation:
        return cls(
            operation_id=str(data["operation_id"]),
            name=str(data["name"]),
            summary=str(data.get("summary") or ""),
            method=data["method"],
            path=str(data["path"]),
            tags=tuple(str(tag) for tag in data.get("tags", ())),
            parameters=tuple(ToolParameter.from_dict(item) for item in data.get("parameters", ())),
            request_schema=data.get("request_schema"),
            response_schema=data.get("response_schema"),
            is_write=bool(data.get("is_write", False)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "operation_id": self.operation_id,
            "name": self.name,
            "summary": self.summary,
            "method": self.method,
            "path": self.path,
            "tags": list(self.tags),
            "parameters": [parameter.to_dict() for parameter in self.parameters],
            "request_schema": self.request_schema,
            "response_schema": self.response_schema,
            "is_write": self.is_write,
        }


@dataclass(frozen=True)
class Toolchain:
    """A curated workflow that composes one or more generated operations."""

    name: str
    summary: str
    operation_ids: tuple[str, ...]
    is_write: bool

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Toolchain:
        return cls(
            name=str(data["name"]),
            summary=str(data.get("summary") or ""),
            operation_ids=tuple(str(item) for item in data.get("operation_ids", ())),
            is_write=bool(data.get("is_write", False)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "summary": self.summary,
            "operation_ids": list(self.operation_ids),
            "is_write": self.is_write,
        }


@dataclass(frozen=True)
class ToolCatalog:
    """Generated operation metadata plus curated agentic toolchains."""

    source: str
    source_version: str
    operations: tuple[ToolOperation, ...]
    toolchains: tuple[Toolchain, ...]
    _operations_by_id: dict[str, ToolOperation] = field(init=False, repr=False, compare=False)
    _toolchains_by_name: dict[str, Toolchain] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "_operations_by_id", {operation.operation_id: operation for operation in self.operations})
        object.__setattr__(self, "_toolchains_by_name", {toolchain.name: toolchain for toolchain in self.toolchains})

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ToolCatalog:
        return cls(
            source=str(data.get("source") or ""),
            source_version=str(data.get("source_version") or ""),
            operations=tuple(ToolOperation.from_dict(item) for item in data.get("operations", ())),
            toolchains=tuple(Toolchain.from_dict(item) for item in data.get("toolchains", ())),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "source_version": self.source_version,
            "operations": [operation.to_dict() for operation in self.operations],
            "toolchains": [toolchain.to_dict() for toolchain in self.toolchains],
        }

    def get_operation(self, operation_id: str) -> ToolOperation:
        try:
            return self._operations_by_id[operation_id]
        except KeyError as exc:
            raise KeyError(f"Unknown ClickUp operation: {operation_id}") from exc

    def get_toolchain(self, name: str) -> Toolchain:
        normalized = normalize_tool_name(name)
        try:
            return self._toolchains_by_name[normalized]
        except KeyError as exc:
            raise KeyError(f"Unknown ClickUp toolchain: {name}") from exc

    def list_operations(
        self,
        *,
        tag: str | None = None,
        write_only: bool = False,
    ) -> tuple[ToolOperation, ...]:
        operations: Iterable[ToolOperation] = self.operations
        if tag:
            tag_lower = tag.lower()
            operations = (op for op in operations if any(item.lower() == tag_lower for item in op.tags))
        if write_only:
            operations = (op for op in operations if op.is_write)
        return tuple(operations)


def normalize_tool_name(value: str) -> str:
    """Normalize user-facing command names to stable kebab-case ids."""
    cleaned = value.strip().lower().replace("_", "-").replace(" ", "-")
    return "-".join(part for part in cleaned.split("-") if part)


@lru_cache(maxsize=1)
def load_catalog() -> ToolCatalog:
    """Load the committed generated catalog bundled with the package."""
    try:
        content = resources.files(CATALOG_PACKAGE).joinpath(CATALOG_RESOURCE).read_text(encoding="utf-8")
    except (FileNotFoundError, ModuleNotFoundError) as exc:
        raise RuntimeError("ClickUp tool catalog has not been generated.") from exc
    return ToolCatalog.from_dict(json.loads(content))
