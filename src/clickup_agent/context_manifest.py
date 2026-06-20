"""Static context manifest for low-token operational catch-up planning."""

from __future__ import annotations

from typing import Any


def build_context_manifest() -> dict[str, Any]:
    """Return a static map of retrievable context and common catch-up actions."""
    return {
        "kind": "context_manifest",
        "version": 1,
        "default_posture": "inspect manifest first; load context only on demand",
        "verbosity": {
            "default": "concise",
            "allowed": ["concise", "normal", "detailed"],
            "guidance": "Prefer compact responses and load only the surfaces needed for the active intent.",
        },
        "surfaces": [
            {
                "name": "clickup-task-summary",
                "summary": "Compact ClickUp Task fields for planning.",
                "loader_command": "clickup-agent run get-task --task-id <task-id> --summary",
                "cost": "cheap",
                "freshness": "live-read",
            },
            {
                "name": "clickup-task-comments",
                "summary": "Task comments, loaded only when comment context is needed.",
                "loader_command": "clickup-agent run comments --task-id <task-id> --list",
                "cost": "moderate",
                "freshness": "live-read",
            },
            {
                "name": "clickup-checklist-state",
                "summary": "Task checklist state through task details.",
                "loader_command": "clickup-agent run get-task --task-id <task-id> --details",
                "cost": "moderate",
                "freshness": "live-read",
            },
            {
                "name": "github-pr",
                "summary": "Current branch GitHub PR metadata.",
                "loader_command": "clickup-agent dev pr",
                "cost": "cheap",
                "freshness": "local-gh-read",
            },
            {
                "name": "branch-audit",
                "summary": "Local branch to GitHub PR audit for catch-up candidates.",
                "loader_command": "clickup-agent dev audit",
                "cost": "moderate",
                "freshness": "local-gh-read",
            },
        ],
        "pinned_actions": [
            {
                "name": "dev-sync",
                "kind": "curated-wrapper",
                "command": "clickup-agent run dev-sync --dry-run --task-id <task-id> --branch <branch>",
                "summary": "Sync development/PR state into ClickUp and optionally the managed GitHub PR block.",
            },
            {
                "name": "get-task",
                "kind": "curated-wrapper",
                "command": "clickup-agent run get-task --task-id <task-id> --summary",
                "summary": "Fetch compact ClickUp Task context.",
            },
            {
                "name": "catch-up-docs",
                "kind": "planned-curated-wrapper",
                "command": "clickup-agent run catch-up-docs --dry-run",
                "summary": "Plan documentation catch-up from current development state.",
            },
        ],
        "mcp_action_templates": [
            {
                "intent": "catch-up-clickup-from-current-work",
                "aliases": ["pull-clickup-and-update"],
                "load_first": ["clickup-task-summary"],
                "then_consider": ["clickup-task-comments", "clickup-checklist-state"],
                "actions": ["get-task", "update-task", "work-log", "decision-log"],
                "sync_topology": "one-way-sync",
                "safety": "dry-run before live writes",
            },
            {
                "intent": "catch-up-clickup-from-pr",
                "aliases": ["get-pr-then-update-clickup"],
                "load_first": ["github-pr", "clickup-task-summary"],
                "actions": ["dev-sync"],
                "sync_topology": "one-way-sync",
                "safety": "dry-run dev-sync before live writes",
            },
            {
                "intent": "catch-up-clickup-and-pr",
                "aliases": ["sync-current-work-to-clickup-and-pr"],
                "load_first": ["github-pr", "clickup-task-summary", "clickup-checklist-state"],
                "actions": ["dev-sync --mode bidirectional", "work-log", "decision-log"],
                "sync_topology": "tri-surface-sync",
                "authority": {
                    "development_state": "current work summary, branch/diff facts, validation",
                    "github_pr": "PR URL, title, review state, merge state, managed PR block",
                    "clickup_task": "task status, checklists, comments, decision/work logs",
                },
                "safety": "dry-run action plan; explicit topology for live writes",
            },
            {
                "intent": "prepare-handoff-summary",
                "aliases": [],
                "load_first": ["clickup-task-summary", "github-pr"],
                "then_consider": ["clickup-checklist-state", "clickup-task-comments"],
                "actions": ["get-task", "work-log", "decision-log"],
                "sync_topology": "no-write-or-explicit-handoff",
                "safety": "prefer summaries and handles over full comment dumps",
            },
        ],
        "cleanup": {
            "cache_policy": "no repo-resident context; future loaded context must live outside the git worktree",
            "session_id": "use --session-id or CLICKUP_AGENT_SESSION_ID when context caching is added",
            "completion_trigger": "cleanup when the main task goal completes or the operator is done with ClickUp updates",
        },
    }
