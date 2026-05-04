"""Small authenticated ClickUp HTTP client with redacted errors."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from .config import ClickUpConfig, load_config, redact_secret


@dataclass(frozen=True)
class ClickUpApiError(RuntimeError):
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
    def from_environment(cls, env_file: str | None = None) -> ClickUpClient:
        return cls(load_config(env_file))

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
            body = redact_secret(exc.response.text, self.config.api_key)
            raise ClickUpApiError(exc.response.status_code, exc.response.reason_phrase, body) from exc
        except httpx.HTTPError as exc:
            message = redact_secret(str(exc), self.config.api_key)
            raise ClickUpApiError(None, message) from exc

        if not response.content:
            return None
        content_type = response.headers.get("content-type", "")
        if "application/json" in content_type:
            return response.json()
        return response.text
