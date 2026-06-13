from __future__ import annotations

import json
import subprocess

import pytest

from clickup_agent.cli import main
from clickup_agent.devlinks import DevPrState, inspect_dev_pr


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
