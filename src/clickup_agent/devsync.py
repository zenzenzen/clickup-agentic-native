"""Reusable planning logic for GitHub-to-ClickUp development sync."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from .evidence import GitHubEvidence
from .markers import (
    comment_text,
    semantic_sync_text,
    comment_contains_url,
    find_status_comment,
    render_description_block,
    render_status_comment,
)


DEVELOPMENT_SYNC_CHECKLIST = "Development Sync"
CANONICAL_CHECKLIST_ITEMS = (
    "Branch pushed",
    "PR opened",
    "Latest commit recorded",
    "Lint/type checks passed",
    "Review completed",
    "Merged",
)


@dataclass(frozen=True)
class GitRepositoryContext:
    branch: str | None = None
    latest_commit: str | None = None


@dataclass(frozen=True)
class GitHubPrContext:
    url: str | None = None
    title: str | None = None
    number: int | str | None = None
    branch: str | None = None
    base: str | None = None
    state: str | None = None


@dataclass(frozen=True)
class ClickUpTaskContext:
    task_id: str
    task: dict[str, Any] = field(default_factory=dict)
    comments: list[Any] = field(default_factory=list)


@dataclass(frozen=True)
class DevSyncInput:
    task_id: str
    repo: GitRepositoryContext
    pr: GitHubPrContext
    task_updates: dict[str, Any]
    evidence: GitHubEvidence | None = None
    comment: str | None = None
    pr_summary: bool = False
    checklist_name: str = DEVELOPMENT_SYNC_CHECKLIST
    add_items: tuple[str, ...] = ()
    check_items: tuple[str, ...] = ()
    backlink_mode: str = "comment"
    no_backlink: bool = False
    last_sync: str = field(default_factory=lambda: datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"))


@dataclass(frozen=True)
class DevSyncPlan:
    task_id: str
    branch: str | None
    pr_state: str
    task_updates: dict[str, Any]
    backlink_needed: bool
    backlink_mode: str
    status_comment: dict[str, Any] | None
    status_comment_text: str
    status_comment_needed: bool
    evidence: dict[str, Any]
    description_block: str
    comment_texts: tuple[str, ...]
    checklist_name: str
    checklist_items: tuple[dict[str, Any], ...]
    duplicates_avoided: dict[str, bool]

    def to_response(self) -> dict[str, Any]:
        status_action = ("update" if self.status_comment else "create") if self.status_comment_needed else "unchanged"
        return {
            "task_id": self.task_id,
            "branch": self.branch,
            "pr_state": self.pr_state,
            "evidence": self.evidence,
            "planned_updates": {
                "task_fields": sorted(self.task_updates),
                "backlink": None if not self.backlink_needed else self.backlink_mode,
                "status_comment": status_action,
                "checklist": self.checklist_name,
            },
            "duplicates_avoided": self.duplicates_avoided,
        }


def build_dev_sync_plan(inputs: DevSyncInput, context: ClickUpTaskContext) -> DevSyncPlan:
    """Build an idempotent development sync plan from fetched ClickUp state."""
    branch = inputs.pr.branch or inputs.repo.branch
    pr_state = _normalized_pr_state(inputs.pr)
    description = _task_description(context.task)
    backlink_exists = bool(inputs.pr.url) and (
        inputs.pr.url in description or any(comment_contains_url(comment, inputs.pr.url) for comment in context.comments)
    )
    backlink_needed = bool(inputs.pr.url) and not inputs.no_backlink and not backlink_exists
    status_comment = find_status_comment(context.comments)
    latest_commit = inputs.repo.latest_commit
    block = render_description_block(
        pr_title=inputs.pr.title,
        pr_number=inputs.pr.number,
        pr_state=pr_state,
        pr_url=inputs.pr.url,
        branch=branch,
        base=inputs.pr.base,
        latest_commit=latest_commit,
        last_sync=inputs.last_sync,
    )
    status_body = _status_body(inputs, pr_state, latest_commit)
    comments = []
    if inputs.comment:
        comments.append(inputs.comment)
    if inputs.pr_summary and inputs.pr.url:
        comments.append(status_body)
    rendered_status = render_status_comment(branch=branch, pr_number=inputs.pr.number, body=status_body)
    status_needed = status_comment is None or semantic_sync_text(comment_text(status_comment)) != semantic_sync_text(rendered_status)
    existing_texts = {comment_text(c) for c in context.comments if isinstance(c, dict)}
    existing_summaries = {semantic_sync_text(text) for text in existing_texts}
    unique_comments = []
    for text in comments:
        duplicate = text in existing_texts if text == inputs.comment else semantic_sync_text(text) in existing_summaries
        if not duplicate and text not in unique_comments:
            unique_comments.append(text)
    comments = unique_comments
    return DevSyncPlan(
        task_id=inputs.task_id,
        branch=branch,
        pr_state=pr_state,
        task_updates=inputs.task_updates,
        backlink_needed=backlink_needed,
        backlink_mode=inputs.backlink_mode,
        status_comment=status_comment,
        status_comment_text=rendered_status,
        status_comment_needed=status_needed,
        evidence=_evidence_summary(inputs),
        description_block=block,
        comment_texts=tuple(comments),
        checklist_name=inputs.checklist_name,
        checklist_items=tuple(_checklist_items(inputs, pr_state, branch, latest_commit)),
        duplicates_avoided={"backlink": bool(backlink_exists)},
    )


def _normalized_pr_state(pr: GitHubPrContext) -> str:
    raw = str(pr.state or "").strip().lower()
    if not pr.url:
        return "no_pr"
    if raw == "merged" or pr.state == "MERGED":
        return "merged"
    if raw in {"closed", "closed_without_merge", "closed-without-merge"}:
        return "closed-without-merge"
    if raw == "draft":
        return "draft"
    return "open"


def _status_body(inputs: DevSyncInput, pr_state: str, latest_commit: str | None) -> str:
    lines = [
        f"State: {pr_state}",
        f"Branch: {inputs.pr.branch or inputs.repo.branch or 'unknown'} -> {inputs.pr.base or 'unknown'}",
        f"PR: {inputs.pr.url or 'No PR exists for this branch yet.'}",
        f"Latest commit: {latest_commit or 'unknown'}",
        f"Evidence: {inputs.evidence.source if inputs.evidence else 'unverified caller metadata'}",
        f"Evidence SHA: {inputs.evidence.head_sha if inputs.evidence else 'unknown'}",
        f"Verification: {_evidence_summary(inputs)['checks']}; review: {_evidence_summary(inputs)['review']}; push: {_evidence_summary(inputs)['push']}",
        f"Last sync: {inputs.last_sync}",
    ]
    if inputs.pr.title:
        lines.insert(1, f"Title: {inputs.pr.title}")
    return "\n".join(lines)


def _checklist_items(inputs: DevSyncInput, pr_state: str, branch: str | None, latest_commit: str | None) -> list[dict[str, Any]]:
    resolved = {
        "Branch pushed": _evidence_value(inputs, "branch_pushed") is True,
        "PR opened": pr_state in {"open", "draft", "merged", "closed-without-merge"},
        "Latest commit recorded": bool(latest_commit),
        "Lint/type checks passed": _evidence_value(inputs, "checks_passed") is True,
        "Review completed": _evidence_value(inputs, "review_completed") is True,
        "Merged": pr_state == "merged",
    }
    for item in inputs.check_items:
        if item not in {"Branch pushed", "Lint/type checks passed", "Review completed"}:
            resolved[item] = True
    names = [*CANONICAL_CHECKLIST_ITEMS]
    if pr_state == "no_pr":
        names.append("Open PR")
    names.extend(item for item in inputs.add_items if item not in names)
    return [{"name": name, "resolved": bool(resolved.get(name, False))} for name in names]


def _task_description(task: dict[str, Any]) -> str:
    return "\n".join(
        str(task.get(key) or "")
        for key in ("description", "text_content", "markdown_description", "markdown_content")
    )


def _evidence_value(inputs: DevSyncInput, name: str) -> bool | None:
    if inputs.evidence is None or inputs.evidence.head_sha != inputs.repo.latest_commit:
        return None
    return getattr(inputs.evidence, name)


def _evidence_summary(inputs: DevSyncInput) -> dict[str, Any]:
    def label(name: str) -> str:
        value = _evidence_value(inputs, name)
        return "unknown" if value is None else ("verified" if value else "not_verified")
    return {"source": inputs.evidence.source if inputs.evidence else None,
            "sha": inputs.evidence.head_sha if inputs.evidence else None,
            "observed_at": inputs.evidence.observed_at if inputs.evidence else None,
            "push": label("branch_pushed"), "review": label("review_completed"), "checks": label("checks_passed")}
