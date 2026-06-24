"""Read-only context loaders for agent handoff and cross-surface review."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .client import ClickUpClient
from .devlinks import inspect_dev_pr
from .markers import DECISION_COMMENT_PREFIX, DESCRIPTION_START, STATUS_COMMENT_PREFIX
from .toolchains import _checklist_summaries, _task_details, _task_summary


def load_context_profile(
    *,
    task_id: str,
    profile: str = "handoff",
    custom_task_ids: bool | None = None,
    team_id: str | None = None,
    timeout: float = 10.0,
    repo: str | Path | None = None,
    client: ClickUpClient | None = None,
) -> dict[str, Any]:
    """Load compact read-only context for a ClickUp task and current PR."""
    if profile != "handoff":
        raise ValueError("context load only supports --profile handoff")

    owned_client = client is None
    active_client = client or ClickUpClient.from_environment()
    try:
        params = _task_params(custom_task_ids=custom_task_ids, team_id=team_id)
        task = active_client.request("GET", f"/v2/task/{task_id}", params={**params, "include_markdown_description": True})
        comments_response = active_client.request("GET", f"/v2/task/{task_id}/comment", params=params)
    finally:
        if owned_client:
            active_client.close()

    comments = _comments_from_response(comments_response)
    return {
        "kind": "context_load",
        "profile": profile,
        "task_id": task_id,
        "task": _task_summary(task),
        "task_details": _task_details(task),
        "checklists": _checklist_summaries(task.get("checklists") if isinstance(task, dict) else None),
        "decision_comments": _decision_comments(comments),
        "dev_sync": _dev_sync_context(task, comments),
        "github_pr": inspect_dev_pr(cwd=repo, timeout=timeout).to_dict(),
    }


def _task_params(*, custom_task_ids: bool | None, team_id: str | None) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if custom_task_ids is not None:
        params["custom_task_ids"] = custom_task_ids
    if team_id:
        params["team_id"] = team_id
    return params


def _comments_from_response(response: Any) -> list[dict[str, Any]]:
    if isinstance(response, dict) and isinstance(response.get("comments"), list):
        return [item for item in response["comments"] if isinstance(item, dict)]
    if isinstance(response, list):
        return [item for item in response if isinstance(item, dict)]
    return []


def _decision_comments(comments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    decisions: list[dict[str, Any]] = []
    for comment in comments:
        text = _comment_text(comment)
        if not text.startswith(DECISION_COMMENT_PREFIX):
            continue
        decisions.append(
            {
                "id": comment.get("id"),
                "date": comment.get("date") or comment.get("date_created"),
                "text": text,
            }
        )
    return decisions


def _dev_sync_context(task: Any, comments: list[dict[str, Any]]) -> dict[str, Any]:
    description = ""
    if isinstance(task, dict):
        description = "\n".join(
            str(task.get(key) or "")
            for key in ("description", "text_content", "markdown_description", "markdown_content")
        )
    status_comment = next((comment for comment in comments if _comment_text(comment).startswith(STATUS_COMMENT_PREFIX)), None)
    return {
        "description_block_present": DESCRIPTION_START in description,
        "status_comment": {
            "id": status_comment.get("id"),
            "text": _comment_text(status_comment),
        }
        if isinstance(status_comment, dict)
        else None,
    }


def _comment_text(comment: dict[str, Any] | None) -> str:
    if not isinstance(comment, dict):
        return ""
    for key in ("comment_text", "text", "comment"):
        value = comment.get(key)
        if isinstance(value, str):
            return value
    return ""
