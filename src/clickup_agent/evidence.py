"""Read-only, commit-specific GitHub evidence for development sync."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import json
import re
import subprocess
from typing import Any
from urllib.parse import quote, urlsplit


@dataclass(frozen=True)
class GitHubEvidence:
    source: str
    head_sha: str
    observed_at: str
    branch_pushed: bool | None = None
    review_completed: bool | None = None
    checks_passed: bool | None = None


def _read(host: str, endpoint: str, *, pages: bool = False, missing_ok: bool = False) -> Any:
    command = ["gh", "api", "--hostname", host, endpoint]
    if pages:
        command += ["--paginate", "--slurp"]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=30, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError("GitHub evidence unavailable; check gh installation/authentication and retry.") from exc
    if result.returncode:
        if missing_ok and "(HTTP 404)" in result.stderr:
            return {}
        # Provider diagnostics may contain private data; don't copy them into logs.
        raise RuntimeError("GitHub evidence request failed; check repository permissions and retry.")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("GitHub evidence returned invalid JSON.") from exc


def inspect_pr_evidence(pr_url: str, *, expected_sha: str, branch: str | None = None,
                        required_checks: tuple[str, ...] = ()) -> GitHubEvidence:
    """Require exact identity/SHA and re-read the PR after collecting evidence."""
    url = urlsplit(pr_url)
    match = re.fullmatch(r"/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)/pull/([0-9]+)/?", url.path)
    if (url.scheme != "https" or not url.hostname or url.username or url.password
            or url.port or url.query or url.fragment or not match):
        raise RuntimeError("GitHub evidence requires a canonical HTTPS pull request URL.")
    if not re.fullmatch(r"[a-fA-F0-9]{40}", expected_sha):
        raise RuntimeError("GitHub evidence requires --latest-commit with the full 40-character head SHA.")
    repo = f"{match[1]}/{match[2]}"
    endpoint = f"repos/{repo}/pulls/{match[3]}"
    pr = _read(url.hostname, endpoint)
    head = pr.get("head", {})
    sha = head.get("sha")
    if sha != expected_sha or (branch is not None and head.get("ref") != branch):
        raise RuntimeError("PR head differs from the requested commit or branch; refresh context before syncing.")
    head_repo = (head.get("repo") or {}).get("full_name")
    pushed = None
    if head_repo and head.get("ref"):
        ref = _read(url.hostname, f"repos/{head_repo}/git/ref/heads/{quote(head['ref'], safe='')}", missing_ok=True)
        pushed = ref.get("object", {}).get("sha") == sha if ref else None

    review_pages = _read(url.hostname, endpoint + "/reviews?per_page=100", pages=True)
    latest: dict[int, dict] = {}
    for review in sorted((r for page in review_pages for r in page), key=lambda r: r.get("id", 0)):
        actor = (review.get("user") or {}).get("id")
        if actor is not None and review.get("state") in {"APPROVED", "CHANGES_REQUESTED", "DISMISSED"}:
            latest[actor] = review
    reviewed = None
    if latest:
        reviewed = (any(r.get("state") == "APPROVED" and r.get("commit_id") == sha for r in latest.values())
                    and not any(r.get("state") == "CHANGES_REQUESTED" for r in latest.values()))

    checks_passed = None
    if required_checks:
        pages = _read(url.hostname, f"repos/{repo}/commits/{sha}/check-runs?per_page=100&filter=latest", pages=True)
        runs = [run for page in pages for run in page.get("check_runs", []) if run.get("head_sha") == sha]
        statuses = _read(url.hostname, f"repos/{repo}/commits/{sha}/statuses?per_page=100", pages=True)
        latest_statuses: dict[str, dict] = {}
        for status in sorted((s for page in statuses for s in page), key=lambda s: s.get("id", 0), reverse=True):
            latest_statuses.setdefault(status.get("context", ""), status)
        results = []
        for name in required_checks:
            matches = [r for r in runs if r.get("name") == name]
            # A duplicated name across Apps/status contexts is ambiguous.
            status = latest_statuses.get(name)
            if len(matches) + int(status is not None) != 1:
                results.append(None)
            elif status is not None:
                results.append(status.get("state") == "success")
            else:
                results.append(matches[0].get("status") == "completed" and matches[0].get("conclusion") == "success")
        checks_passed = False if False in results else (None if None in results else True)
    current = _read(url.hostname, endpoint)
    if current.get("head", {}).get("sha") != sha:
        raise RuntimeError("PR head changed while collecting evidence; retry before syncing.")
    return GitHubEvidence(pr_url, sha, datetime.now(UTC).isoformat(), pushed, reviewed, checks_passed)
