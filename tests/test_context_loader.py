from __future__ import annotations

import httpx

from clickup_agent.client import ClickUpClient
from clickup_agent.config import ClickUpConfig
from clickup_agent.context_loader import load_context_profile
from clickup_agent.markers import DESCRIPTION_START


def test_context_load_handoff_returns_task_decisions_dev_sync_and_pr(monkeypatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.path == "/api/v2/task/abc":
            return httpx.Response(
                200,
                json={
                    "id": "abc",
                    "name": "Ship feature",
                    "url": "https://app.clickup.com/t/abc",
                    "description": f"Intro\n{DESCRIPTION_START}\nblock",
                    "status": {"status": "in progress"},
                    "checklists": [
                        {
                            "id": "chk",
                            "name": "Action Items",
                            "items": [{"id": "item-1", "name": "Update docs", "resolved": True}],
                        }
                    ],
                },
            )
        if request.method == "GET" and request.url.path == "/api/v2/task/abc/comment":
            return httpx.Response(
                200,
                json={
                    "comments": [
                        {"id": "sync", "comment_text": "[dev-sync] GitHub development state\nState: open"},
                        {"id": "decision", "comment_text": "[dev-sync:decision] 2026-06-24 - Keep dev-sync narrow"},
                        {"id": "human", "comment_text": "Human note"},
                    ]
                },
            )
        raise AssertionError(request.url.path)

    class FakePr:
        def to_dict(self) -> dict:
            return {
                "state": "found",
                "branch": "feature/task",
                "remote": "origin",
                "pr": {"url": "https://github.com/acme/repo/pull/12"},
            }

    monkeypatch.setattr("clickup_agent.context_loader.inspect_dev_pr", lambda cwd=None, timeout=10.0: FakePr())
    client = ClickUpClient(ClickUpConfig(api_key="pk_test"), transport=httpx.MockTransport(handler))

    result = load_context_profile(task_id="abc", client=client)

    assert result["kind"] == "context_load"
    assert result["profile"] == "handoff"
    assert result["task"]["name"] == "Ship feature"
    assert result["checklists"][0]["name"] == "Action Items"
    assert result["decision_comments"] == [
        {"id": "decision", "date": None, "text": "[dev-sync:decision] 2026-06-24 - Keep dev-sync narrow"}
    ]
    assert result["dev_sync"]["description_block_present"] is True
    assert result["dev_sync"]["status_comment"]["id"] == "sync"
    assert result["github_pr"]["pr"]["url"] == "https://github.com/acme/repo/pull/12"
