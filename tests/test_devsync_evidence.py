from __future__ import annotations

from dataclasses import replace
import json
import subprocess

import httpx
import pytest

from clickup_agent.client import ClickUpClient
from clickup_agent.config import ClickUpConfig
from clickup_agent.devsync import ClickUpTaskContext, DevSyncInput, GitHubPrContext, GitRepositoryContext, build_dev_sync_plan
from clickup_agent.evidence import GitHubEvidence, inspect_pr_evidence
from clickup_agent.toolchains import ToolchainError, ToolchainRunner
from clickup_agent.devlinks import render_pr_body_block, write_pr_body_block

SHA = "a" * 40
URL = "https://github.com/example/repo/pull/12"


def _input(**kwargs):
    return DevSyncInput("abc", GitRepositoryContext("work/demo", SHA),
                        GitHubPrContext(url=URL, state="merged"), {}, **kwargs)


def test_metadata_and_manual_checks_do_not_prove_push_review_or_checks():
    plan = build_dev_sync_plan(_input(check_items=("Branch pushed", "Review completed", "Lint/type checks passed")),
                               ClickUpTaskContext("abc"))
    items = {i["name"]: i["resolved"] for i in plan.checklist_items}
    assert not items["Branch pushed"]
    assert not items["Review completed"]
    assert not items["Lint/type checks passed"]
    assert plan.evidence["push"] == "unknown"


def test_only_current_commit_evidence_counts():
    evidence = GitHubEvidence(URL, SHA, "now", True, True, True)
    current = build_dev_sync_plan(_input(evidence=evidence), ClickUpTaskContext("abc"))
    assert all(i["resolved"] for i in current.checklist_items)
    stale = build_dev_sync_plan(_input(evidence=replace(evidence, head_sha="b" * 40)), ClickUpTaskContext("abc"))
    assert stale.evidence["checks"] == "unknown"
    assert not next(i for i in stale.checklist_items if i["name"] == "Lint/type checks passed")["resolved"]


def _github(monkeypatch, *, review_sha=SHA, conclusion="success", check_sha=SHA,
            second_sha=SHA, duplicate=False, missing_check=False, changes_requested=False):
    calls = []
    pr_reads = 0
    def run(command, **kwargs):
        nonlocal pr_reads
        calls.append(command)
        endpoint = command[4]
        if endpoint.endswith("/reviews?per_page=100"):
            data = [[{"id": 1, "user": {"id": 10}, "state": "APPROVED", "commit_id": review_sha}]]
            if changes_requested:
                data[0].append({"id": 2, "user": {"id": 10}, "state": "CHANGES_REQUESTED", "commit_id": SHA})
        elif "/check-runs?" in endpoint:
            runs = [] if missing_check else [{"name": "lint", "head_sha": check_sha, "status": "completed", "conclusion": conclusion}]
            data = [{"check_runs": runs * (2 if duplicate else 1)}]
        elif endpoint.endswith("/statuses?per_page=100"):
            data = [[]]
        elif "/git/ref/heads/" in endpoint:
            data = {"object": {"sha": SHA}}
        else:
            pr_reads += 1
            data = {"head": {"sha": SHA if pr_reads == 1 else second_sha,
                             "ref": "work/demo", "repo": {"full_name": "example/repo"}}}
        return subprocess.CompletedProcess(command, 0, json.dumps(data), "")
    monkeypatch.setattr("clickup_agent.evidence.subprocess.run", run)
    return calls


def test_evidence_fetches_current_sha_and_requested_checks(monkeypatch):
    calls = _github(monkeypatch)
    result = inspect_pr_evidence(URL, expected_sha=SHA, branch="work/demo", required_checks=("lint",))
    assert result.branch_pushed and result.review_completed and result.checks_passed
    assert result.head_sha == SHA and result.source == URL
    assert any("--paginate" in c for c in calls)
    assert calls[-1][4].endswith("/pulls/12")


@pytest.mark.parametrize("options,field,expected", [
    ({"review_sha": "b" * 40}, "review_completed", False),
    ({"changes_requested": True}, "review_completed", False),
    ({"conclusion": "failure"}, "checks_passed", False),
    ({"conclusion": "skipped"}, "checks_passed", False),
    ({"check_sha": "b" * 40}, "checks_passed", None),
    ({"duplicate": True}, "checks_passed", None),
    ({"missing_check": True}, "checks_passed", None),
])
def test_missing_stale_or_ambiguous_evidence_never_passes(monkeypatch, options, field, expected):
    _github(monkeypatch, **options)
    result = inspect_pr_evidence(URL, expected_sha=SHA, required_checks=("lint",))
    assert getattr(result, field) is expected


def test_head_change_aborts_evidence(monkeypatch):
    _github(monkeypatch, second_sha="b" * 40)
    with pytest.raises(RuntimeError, match="head changed"):
        inspect_pr_evidence(URL, expected_sha=SHA)


def test_failed_verification_prevents_clickup_calls(monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("unavailable")
    monkeypatch.setattr("clickup_agent.toolchains.inspect_pr_evidence", fail)
    requests = []
    runner = ToolchainRunner(client_factory=lambda: ClickUpClient(ClickUpConfig(api_key="pk_test"),
        transport=httpx.MockTransport(lambda req: requests.append(req))))
    with pytest.raises(ToolchainError, match="unavailable"):
        runner.run("dev-sync", ["--live", "--task-id", "abc", "--pr-url", URL, "--latest-commit", SHA, "--verify-github"])
    assert requests == []


def test_cli_passes_verification_policy_to_evidence(monkeypatch):
    def inspect(url, **kwargs):
        assert url == URL
        assert kwargs == {"expected_sha": SHA, "branch": "work/demo", "required_checks": ("lint", "typecheck")}
        return GitHubEvidence(URL, SHA, "now", True, True, True)
    monkeypatch.setattr("clickup_agent.toolchains.inspect_pr_evidence", inspect)
    result = ToolchainRunner().run("dev-sync", ["--dry-run", "--task-id", "abc", "--branch", "work/demo",
        "--pr-url", URL, "--latest-commit", SHA, "--verify-github", "--required-check", "lint", "--required-check", "typecheck"])
    assert result.response["evidence"]["checks"] == "verified"


def test_repeated_live_sync_has_no_writes_and_preserves_human_items():
    first = build_dev_sync_plan(_input(), ClickUpTaskContext("abc"))
    task = {"name": "Example task", "description": "Human task notes " + URL, "checklists": [{"id": "chk", "name": first.checklist_name,
        "items": [{"id": str(n), **i} for n, i in enumerate(first.checklist_items)] + [{"id": "human", "name": "Human step", "resolved": True}]}]}
    calls = []
    def handler(request):
        calls.append(request)
        assert request.method == "GET", "Unchanged sync must not write"
        if request.url.path.endswith("/comment"):
            # ClickUp can return rich comment fragments instead of a plain field.
            return httpx.Response(200, json={"comments": [{"id": "comment", "comment": [{"text": first.status_comment_text.replace(first.status_comment_text.split('Last sync: ')[-1], 'old')}]}]})
        return httpx.Response(200, json=task)
    runner = ToolchainRunner(client_factory=lambda: ClickUpClient(ClickUpConfig(api_key="pk_test"), transport=httpx.MockTransport(handler)))
    result = runner.run("dev-sync", ["--live", "--task-id", "abc", "--name", "Example task", "--branch", "work/demo", "--latest-commit", SHA, "--pr-url", URL, "--pr-state", "merged"])
    assert len(calls) == 2
    assert result.response["planned_updates"]["status_comment"] == "unchanged"
    assert task["checklists"][0]["items"][-1]["resolved"]


def test_unchanged_github_managed_block_is_not_rewritten(monkeypatch):
    old = render_pr_body_block(task_id="abc", task_url=None, status="active", checklist_progress=[], last_sync="old")
    new = render_pr_body_block(task_id="abc", task_url=None, status="active", checklist_progress=[], last_sync="new")
    calls = []
    def run(command, **kwargs):
        calls.append(command)
        assert command[:3] == ["gh", "pr", "view"]
        return subprocess.CompletedProcess(command, 0, json.dumps({"body": "Human notes\n\n" + old}), "")
    monkeypatch.setattr("clickup_agent.devlinks.subprocess.run", run)
    assert write_pr_body_block(URL, new)["updated"] is False
    assert len(calls) == 1


def test_mcp_verification_has_same_contract(monkeypatch):
    from clickup_agent.mcp_server import create_server
    def inspect(url, **kwargs):
        assert url == URL and kwargs["required_checks"] == ("lint",)
        return GitHubEvidence(URL, SHA, "now", True, True, True)
    monkeypatch.setattr("clickup_agent.toolchains.inspect_pr_evidence", inspect)
    tool = create_server()._tool_manager._tools["clickup_agent_dev_sync"].fn
    result = tool(task_id="abc", pr_url=URL, latest_commit=SHA, verify_github=True, required_checks=["lint"])
    assert result["response"]["evidence"]["sha"] == SHA
    assert result["response"]["evidence"]["checks"] == "verified"


def test_provider_errors_are_redacted(monkeypatch):
    def run(command, **kwargs):
        return subprocess.CompletedProcess(command, 1, "", "private fixture token")
    monkeypatch.setattr("clickup_agent.evidence.subprocess.run", run)
    with pytest.raises(RuntimeError) as error:
        inspect_pr_evidence(URL, expected_sha=SHA)
    assert "private fixture token" not in str(error.value)


def test_invalid_identity_does_not_call_github(monkeypatch):
    def run(*args, **kwargs):
        pytest.fail("Invalid inputs should not call GitHub")
    monkeypatch.setattr("clickup_agent.evidence.subprocess.run", run)
    for url, sha in [("https://github.com/example/repo/pull/12?token=bad", SHA), (URL, "abc123")]:
        with pytest.raises(RuntimeError):
            inspect_pr_evidence(url, expected_sha=sha)


def test_explicit_comment_clock_line_remains_meaningful():
    inputs = _input(comment="Operator note\nLast sync: changed")
    context = ClickUpTaskContext("abc", comments=[{"comment_text": "Operator note\nLast sync: original"}])
    assert inputs.comment in build_dev_sync_plan(inputs, context).comment_texts
