"""Visible sync marker formats shared by ClickUp/GitHub sync workflows."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any


DESCRIPTION_START = "--- Development reference (dev-sync; auto-managed, edits will be overwritten) ---"
DESCRIPTION_END = "--- end dev-sync ---"
STATUS_COMMENT_PREFIX = "[dev-sync] GitHub development state"
DECISION_COMMENT_PREFIX = "[dev-sync:decision]"


def render_description_block(
    *,
    pr_title: str | None,
    pr_number: int | str | None,
    pr_state: str,
    pr_url: str | None,
    branch: str | None,
    base: str | None,
    latest_commit: str | None,
    last_sync: str,
) -> str:
    """Render a ClickUp-safe visible development reference block."""
    pr_label = "No PR found"
    if pr_url:
        title = pr_title or "Pull request"
        number = f" (#{pr_number})" if pr_number is not None else ""
        pr_label = f"{title}{number} - {pr_state}"
    return "\n".join(
        [
            DESCRIPTION_START,
            f"- PR: {pr_label}",
            f"- URL: {pr_url or 'none'}",
            f"- Branch: {branch or 'unknown'} -> {base or 'unknown'}",
            f"- Latest commit: {latest_commit or 'unknown'}",
            f"- Last sync: {last_sync}",
            DESCRIPTION_END,
        ]
    )


def upsert_description_block(description: str | None, block: str) -> str:
    """Insert or replace the managed block while preserving human text."""
    text = description or ""
    found = find_description_block(text)
    if found is not None:
        start, end = found
        end += len(DESCRIPTION_END)
        return (text[:start].rstrip() + "\n\n" + block + "\n\n" + text[end:].lstrip()).strip() + "\n"
    if not text.strip():
        return block + "\n"
    return text.rstrip() + "\n\n" + block + "\n"


def find_description_block(description: str | None) -> tuple[int, int] | None:
    """Return the managed description block marker range when present."""
    text = description or ""
    start = text.find(DESCRIPTION_START)
    end = text.find(DESCRIPTION_END, start if start >= 0 else 0)
    if start < 0 or end < 0:
        return None
    return start, end


def render_status_comment(*, branch: str | None, pr_number: int | str | None, body: str) -> str:
    """Render the single sync-managed ClickUp status comment."""
    suffix = f", PR #{pr_number}" if pr_number is not None else ""
    return f"{STATUS_COMMENT_PREFIX} - branch {branch or 'unknown'}{suffix}\n{body}".strip()


def find_status_comment(comments: list[Any]) -> dict[str, Any] | None:
    """Find the sync-managed status comment by visible prefix."""
    for comment in comments:
        if not isinstance(comment, dict):
            continue
        text = _comment_text(comment)
        if text.startswith(STATUS_COMMENT_PREFIX):
            return comment
    return None


def comment_contains_url(comment: Any, url: str) -> bool:
    return isinstance(comment, dict) and url in _comment_text(comment)


def has_pr_backlink(description: str | None, comments: list[Any], pr_url: str | None) -> bool:
    if not pr_url:
        return False
    return pr_url in str(description or "") or any(comment_contains_url(comment, pr_url) for comment in comments)


def render_decision_comment(
    *,
    decision: str,
    context: str | None = None,
    alternatives: str | None = None,
    source: str | None = None,
    pr_url: str | None = None,
    commit: str | None = None,
    timestamp: str | None = None,
) -> str:
    """Render an append-only decision journal comment."""
    stamp = timestamp or datetime.now(UTC).date().isoformat()
    title = _decision_title(decision)
    lines = [
        f"{DECISION_COMMENT_PREFIX} {stamp} - {title}",
        f"Decision: {decision}",
    ]
    if context:
        lines.append(f"Context: {context}")
    if alternatives:
        lines.append(f"Alternatives considered: {alternatives}")
    source_label = source or "conversation"
    links = " ".join(item for item in (pr_url, commit) if item)
    if links:
        lines.append(f"Source: {source_label} · Links: {links}")
    else:
        lines.append(f"Source: {source_label}")
    return "\n".join(lines)


def _decision_title(decision: str) -> str:
    cleaned = " ".join(decision.strip().split())
    if len(cleaned) <= 72:
        return cleaned
    return cleaned[:69].rstrip() + "..."


def _comment_text(comment: dict[str, Any]) -> str:
    for key in ("comment_text", "text", "comment"):
        value = comment.get(key)
        if isinstance(value, str):
            return value
    return ""


def description_block_survives(task_id: str) -> bool:
    """Live opt-in probe for ClickUp markdown normalization of visible markers."""
    from .client import ClickUpClient

    marker = render_description_block(
        pr_title="Marker probe",
        pr_number=None,
        pr_state="probe",
        pr_url=None,
        branch="marker-probe",
        base="main",
        latest_commit="probe",
        last_sync="probe",
    )
    with ClickUpClient.from_environment() as client:
        task = client.request("GET", f"/v2/task/{task_id}", params={"include_markdown_description": True})
        original = task.get("description") if isinstance(task, dict) else ""
        updated = upsert_description_block(str(original or ""), marker)
        try:
            client.request("PUT", f"/v2/task/{task_id}", json_body={"description": updated})
            fetched = client.request("GET", f"/v2/task/{task_id}", params={"include_markdown_description": True})
            description = fetched.get("description") if isinstance(fetched, dict) else ""
            markdown_description = fetched.get("markdown_description") if isinstance(fetched, dict) else ""
            combined = f"{description or ''}\n{markdown_description or ''}"
            return DESCRIPTION_START in combined and DESCRIPTION_END in combined
        finally:
            client.request("PUT", f"/v2/task/{task_id}", json_body={"description": original or ""})
