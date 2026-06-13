"""Read-only GitHub development context helpers."""

from __future__ import annotations

import json
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal


DevPrState = Literal["found", "not_found", "timeout", "gh_missing", "unauthenticated", "no_remote"]
GITHUB_SYNC_START = "<!-- clickup-agent:dev-sync:start -->"
GITHUB_SYNC_END = "<!-- clickup-agent:dev-sync:end -->"


@dataclass(frozen=True)
class DevPrResult:
    """Compact branch-to-PR lookup result for CLI and MCP callers."""

    state: DevPrState
    branch: str | None = None
    remote: str | None = None
    pr: dict[str, Any] | None = None
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "state": self.state,
            "branch": self.branch,
            "remote": self.remote,
            "pr": self.pr,
        }
        if self.reason:
            data["reason"] = self.reason
        return data


def inspect_dev_pr(*, cwd: str | Path | None = None, timeout: float = 10.0) -> DevPrResult:
    """Resolve the current branch's GitHub PR without writing to git or GitHub."""
    repo = Path(cwd) if cwd is not None else None
    remote_result = subprocess.run(
        ["git", "remote"],
        cwd=repo,
        timeout=timeout,
        capture_output=True,
        text=True,
        check=False,
    )
    remote_names = [line.strip() for line in remote_result.stdout.splitlines() if line.strip()]
    if remote_result.returncode != 0 or not remote_names:
        return DevPrResult("no_remote", reason=_clean_reason(remote_result.stderr) or "No git remote configured.")
    remote = "origin" if "origin" in remote_names else remote_names[0]

    branch_result = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=repo,
        timeout=timeout,
        capture_output=True,
        text=True,
        check=False,
    )
    branch = branch_result.stdout.strip() or None
    if branch_result.returncode != 0 or not branch:
        return DevPrResult("not_found", remote=remote, reason=_clean_reason(branch_result.stderr) or "No current branch.")

    command = [
        "gh",
        "pr",
        "view",
        "--json",
        "number,title,url,headRefName,baseRefName,state,isDraft,mergedAt,body,files",
    ]
    try:
        gh_result = subprocess.run(
            command,
            cwd=repo,
            timeout=timeout,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return DevPrResult("gh_missing", branch=branch, remote=remote, reason="GitHub CLI `gh` was not found.")
    except subprocess.TimeoutExpired:
        return DevPrResult("timeout", branch=branch, remote=remote, reason=f"gh pr view timed out after {timeout:g}s.")

    if gh_result.returncode != 0:
        reason = _clean_reason(gh_result.stderr) or _clean_reason(gh_result.stdout)
        lowered = reason.casefold()
        if "not logged" in lowered or "authentication" in lowered or "gh auth login" in lowered:
            return DevPrResult("unauthenticated", branch=branch, remote=remote, reason=reason)
        return DevPrResult("not_found", branch=branch, remote=remote, reason=reason or "No pull request found.")

    try:
        pr = json.loads(gh_result.stdout)
    except json.JSONDecodeError:
        return DevPrResult("not_found", branch=branch, remote=remote, reason="gh pr view returned invalid JSON.")
    if not isinstance(pr, dict) or not pr.get("url"):
        return DevPrResult("not_found", branch=branch, remote=remote, reason="No pull request found.")
    return DevPrResult("found", branch=branch, remote=remote, pr=_compact_pr(pr))


def _compact_pr(pr: dict[str, Any]) -> dict[str, Any]:
    files = pr.get("files")
    return {
        "number": pr.get("number"),
        "title": pr.get("title"),
        "url": pr.get("url"),
        "head": pr.get("headRefName"),
        "base": pr.get("baseRefName"),
        "state": pr.get("state"),
        "draft": bool(pr.get("isDraft")),
        "merged_at": pr.get("mergedAt"),
        "body": pr.get("body"),
        "files": [
            {"path": item.get("path")}
            for item in files
            if isinstance(item, dict) and item.get("path") is not None
        ]
        if isinstance(files, list)
        else [],
    }


def render_pr_body_block(
    *,
    task_id: str,
    task_url: str | None,
    status: str | None,
    checklist_progress: list[str],
    last_sync: str,
) -> str:
    lines = [
        GITHUB_SYNC_START,
        "### ClickUp development state",
        f"- Task: {task_url or task_id}",
        f"- Status: {status or 'unknown'}",
    ]
    if checklist_progress:
        lines.append("- Checklist progress:")
        lines.extend(f"  - {item}" for item in checklist_progress)
    else:
        lines.append("- Checklist progress: none")
    lines.append(f"- Last sync: {last_sync}")
    lines.append(GITHUB_SYNC_END)
    return "\n".join(lines)


def upsert_pr_body_block(body: str | None, block: str) -> str:
    """Insert or replace only the GitHub sync-managed PR body block."""
    text = body or ""
    start = text.find(GITHUB_SYNC_START)
    end = text.find(GITHUB_SYNC_END, start if start >= 0 else 0)
    if start >= 0 and end >= 0:
        end += len(GITHUB_SYNC_END)
        suffix = text[end:].lstrip()
        updated = text[:start].rstrip() + "\n\n" + block
        if suffix:
            updated += "\n\n" + suffix
        return updated
    if not text.strip():
        return block
    return text.rstrip() + "\n\n" + block


def write_pr_body_block(pr_url: str, block: str, *, timeout: float = 10.0) -> dict[str, Any]:
    """Live GitHub write: update only the managed PR body block via gh."""
    view = subprocess.run(
        ["gh", "pr", "view", pr_url, "--json", "body"],
        timeout=timeout,
        capture_output=True,
        text=True,
        check=False,
    )
    if view.returncode != 0:
        raise RuntimeError(_clean_reason(view.stderr) or "Could not read PR body with gh.")
    try:
        current = json.loads(view.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("gh pr view returned invalid JSON.") from exc
    updated = upsert_pr_body_block(str(current.get("body") or ""), block)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=True) as handle:
        handle.write(updated)
        handle.flush()
        edit = subprocess.run(
            ["gh", "pr", "edit", pr_url, "--body-file", handle.name],
            timeout=timeout,
            capture_output=True,
            text=True,
            check=False,
        )
    if edit.returncode != 0:
        raise RuntimeError(_clean_reason(edit.stderr) or "Could not update PR body with gh.")
    return {"pr_url": pr_url, "updated": True}


def _clean_reason(value: str | None) -> str:
    return " ".join(str(value or "").strip().split())
