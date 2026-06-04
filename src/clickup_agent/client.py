"""Small authenticated ClickUp HTTP client with redacted errors.

The CLI, curated wrappers, and MCP server all cross the network through this
module so secret handling and API error shape stay consistent for humans and
LLM clients.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from .config import ClickUpConfig, load_config, redact_secret

MAX_ERROR_DETAIL_CHARS = 2000


@dataclass(frozen=True)
class ClickUpApiError(RuntimeError):
    """User-safe ClickUp failure with already-redacted response details."""

    status_code: int | None
    message: str
    response_body: str | None = None

    def __str__(self) -> str:
        details = f"ClickUp API error"
        if self.status_code is not None:
            details += f" ({self.status_code})"
        details += f": {self.message}"
        if self.response_body:
            details += f" - {self.response_body}"
        return details


class ClickUpClient:
    """HTTP boundary for ClickUp API calls used by CLI and future MCP tools."""

    def __init__(
        self,
        config: ClickUpConfig,
        *,
        timeout: float = 30.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.config = config
        self._client = httpx.Client(
            base_url=config.base_url,
            timeout=timeout,
            transport=transport,
            headers={"Authorization": config.api_key, "Accept": "application/json"},
        )

    @classmethod
    def from_environment(cls) -> ClickUpClient:
        """Build a client from the canonical user config file."""
        return cls(load_config())

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> ClickUpClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        """Execute one ClickUp request and return parsed response content."""
        try:
            response = self._client.request(
                method,
                path,
                params=params,
                json=json_body,
                headers=headers,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            body = _compact_error_detail(redact_secret(exc.response.text, self.config.api_key))
            raise ClickUpApiError(exc.response.status_code, exc.response.reason_phrase, body) from exc
        except httpx.HTTPError as exc:
            message = _compact_error_detail(redact_secret(str(exc), self.config.api_key))
            raise ClickUpApiError(None, message) from exc

        if not response.content:
            return None
        content_type = response.headers.get("content-type", "")
        if "application/json" in content_type:
            return response.json()
        return response.text


def _compact_error_detail(value: str) -> str:
    """Keep API error payloads useful without flooding CLI/MCP output."""
    if len(value) <= MAX_ERROR_DETAIL_CHARS:
        return value
    omitted = len(value) - MAX_ERROR_DETAIL_CHARS
    return f"{value[:MAX_ERROR_DETAIL_CHARS]}... <truncated {omitted} chars>"
