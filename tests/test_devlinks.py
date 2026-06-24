from __future__ import annotations

import json
import subprocess

import pytest

from clickup_agent.cli import main
from clickup_agent.devlinks import DevPrState, guess_clickup_task_id, inspect_dev_pr, upsert_pr_body_block, write_pr_title


def test_dev_pr_found_from_cli(monkeypatch, capsys) -> None:
    def fake_run(command, *, cwd=None, timeout=None, capture_output=True, text=True, check=False):
        if command[:2] == ["git", "remote"]:
            return subprocess.CompletedProcess(command, 0, stdout="origin\n", stderr="")
        if command[:3] == ["git", "branch", "--show-current"]:
            return subprocess.CompletedProcess(command, 0, stdout="feature/task\n", stderr="")
        if command[:3] == ["gh", "pr", "view"]:
            return subprocess.CompletedProcess(
                command,
                0,
                stdout=json.dumps(
                    {
                        "number": 12,
                        "title": "Ship feature",
                        "url": "https://github.com/acme/repo/pull/12",
                        "headRefName": "feature/task",
                        "baseRefName": "main",
                        "state": "OPEN",
                        "isDraft": False,
                        "mergedAt": None,
                        "body": "PR body",
                        "files": [{"path": "src/app.py"}],
                    }
                ),
                stderr="",
            )
        raise AssertionError(command)

    monkeypatch.setattr("clickup_agent.devlinks.subprocess.run", fake_run)

    assert main(["dev", "pr"]) == 0

    payload = json.loads(capsys.readouterr().out)

    assert payload["state"] == "found"
    assert payload["branch"] == "feature/task"
    assert payload["remote"] == "origin"
    assert payload["pr"]["number"] == 12
    assert payload["pr"]["url"] == "https://github.com/acme/repo/pull/12"


@pytest.mark.parametrize(
    ("returncode", "stderr", "state"),
    [
        (1, "no pull requests found", "not_found"),
        (4, "not logged into any GitHub hosts", "unauthenticated"),
    ],
)
def test_dev_pr_explicit_gh_states(monkeypatch, returncode: int, stderr: str, state: DevPrState) -> None:
    def fake_run(command, *, cwd=None, timeout=None, capture_output=True, text=True, check=False):
        if command[:2] == ["git", "remote"]:
            return subprocess.CompletedProcess(command, 0, stdout="origin\n", stderr="")
        if command[:3] == ["git", "branch", "--show-current"]:
            return subprocess.CompletedProcess(command, 0, stdout="feature/task\n", stderr="")
        return subprocess.CompletedProcess(command, returncode, stdout="", stderr=stderr)

    monkeypatch.setattr("clickup_agent.devlinks.subprocess.run", fake_run)

    result = inspect_dev_pr()

    assert result.state == state
    assert result.pr is None


def test_dev_pr_timeout(monkeypatch) -> None:
    def fake_run(command, *, cwd=None, timeout=None, capture_output=True, text=True, check=False):
        if command[:2] == ["git", "remote"]:
            return subprocess.CompletedProcess(command, 0, stdout="origin\n", stderr="")
        if command[:3] == ["git", "branch", "--show-current"]:
            return subprocess.CompletedProcess(command, 0, stdout="feature/task\n", stderr="")
        raise subprocess.TimeoutExpired(command, timeout=timeout)

    monkeypatch.setattr("clickup_agent.devlinks.subprocess.run", fake_run)

    result = inspect_dev_pr(timeout=0.01)

    assert result.state == "timeout"
    assert result.pr is None


def test_dev_pr_gh_missing(monkeypatch) -> None:
    def fake_run(command, *, cwd=None, timeout=None, capture_output=True, text=True, check=False):
        if command[:2] == ["git", "remote"]:
            return subprocess.CompletedProcess(command, 0, stdout="origin\n", stderr="")
        if command[:3] == ["git", "branch", "--show-current"]:
            return subprocess.CompletedProcess(command, 0, stdout="feature/task\n", stderr="")
        raise FileNotFoundError(command[0])

    monkeypatch.setattr("clickup_agent.devlinks.subprocess.run", fake_run)

    result = inspect_dev_pr()

    assert result.state == "gh_missing"
    assert result.pr is None


def test_dev_pr_no_remote(monkeypatch) -> None:
    def fake_run(command, *, cwd=None, timeout=None, capture_output=True, text=True, check=False):
        if command[:2] == ["git", "remote"]:
            return subprocess.CompletedProcess(command, 2, stdout="", stderr="No such remote")
        raise AssertionError(command)

    monkeypatch.setattr("clickup_agent.devlinks.subprocess.run", fake_run)

    result = inspect_dev_pr()

    assert result.state == "no_remote"
    assert result.pr is None


def test_pr_body_block_upsert_preserves_human_content() -> None:
    body = "Intro\n\n<!-- clickup-agent:dev-sync:start -->\nold\n<!-- clickup-agent:dev-sync:end -->\n\nFooter"
    block = "<!-- clickup-agent:dev-sync:start -->\nnew\n<!-- clickup-agent:dev-sync:end -->"

    updated = upsert_pr_body_block(body, block)

    assert updated == "Intro\n\n<!-- clickup-agent:dev-sync:start -->\nnew\n<!-- clickup-agent:dev-sync:end -->\n\nFooter"


def test_write_pr_title_uses_explicit_gh_title_edit(monkeypatch) -> None:
    calls: list[list[str]] = []

    def fake_run(command, *, timeout=None, capture_output=True, text=True, check=False):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr("clickup_agent.devlinks.subprocess.run", fake_run)

    result = write_pr_title("https://github.com/acme/repo/pull/12", "Ship feature")

    assert calls == [["gh", "pr", "edit", "https://github.com/acme/repo/pull/12", "--title", "Ship feature"]]
    assert result == {"pr_url": "https://github.com/acme/repo/pull/12", "title": "Ship feature", "updated": True}


@pytest.mark.parametrize(
    ("branch", "expected"),
    [
        ("feature/86dzdnmcr-dev-sync", "86dzdnmcr"),
        ("hotfix/CU-123-doc-fix", "CU-123"),
        ("feature/no-task-id", None),
    ],
)
def test_guess_clickup_task_id_default_pattern(branch: str, expected: str | None) -> None:
    assert guess_clickup_task_id(branch) == expected


def test_guess_clickup_task_id_custom_pattern() -> None:
    assert guess_clickup_task_id("feature/task-123-ship", pattern=r"task-(\d+)") == "123"


def test_dev_audit_joins_branches_with_batched_pr_list(monkeypatch, capsys) -> None:
    commands: list[list[str]] = []

    def fake_run(command, *, cwd=None, timeout=None, capture_output=True, text=True, check=False):
        commands.append(command)
        if command[:2] == ["git", "for-each-ref"]:
            return subprocess.CompletedProcess(
                command,
                0,
                stdout="feature/86dzdnmcr-dev-sync\tahead 2, behind 1\nmain\t\n",
                stderr="",
            )
        if command[:3] == ["gh", "pr", "list"]:
            return subprocess.CompletedProcess(
                command,
                0,
                stdout=json.dumps(
                    [
                        {
                            "number": 42,
                            "title": "Dev sync",
                            "url": "https://github.com/acme/repo/pull/42",
                            "headRefName": "feature/86dzdnmcr-dev-sync",
                            "state": "MERGED",
                            "mergedAt": "2026-06-13T01:02:03Z",
                        }
                    ]
                ),
                stderr="",
            )
        raise AssertionError(command)

    monkeypatch.setattr("clickup_agent.devlinks.subprocess.run", fake_run)

    assert main(["dev", "audit"]) == 0

    payload = json.loads(capsys.readouterr().out)

    assert payload == [
        {
            "branch": "feature/86dzdnmcr-dev-sync",
            "pr_number": 42,
            "pr_url": "https://github.com/acme/repo/pull/42",
            "pr_title": "Dev sync",
            "state": "MERGED",
            "merged": True,
            "merged_at": "2026-06-13T01:02:03Z",
            "clickup_task_id_guess": "86dzdnmcr",
            "ahead": 2,
            "behind": 1,
        },
        {
            "branch": "main",
            "pr_number": None,
            "pr_url": None,
            "pr_title": None,
            "state": "no_pr",
            "merged": False,
            "merged_at": None,
            "clickup_task_id_guess": None,
            "ahead": None,
            "behind": None,
        },
    ]
    assert sum(command[:3] == ["gh", "pr", "list"] for command in commands) == 1
