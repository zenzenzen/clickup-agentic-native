from __future__ import annotations

import os

import pytest

from clickup_agent.markers import (
    DESCRIPTION_END,
    DESCRIPTION_START,
    STATUS_COMMENT_PREFIX,
    description_block_survives,
    find_status_comment,
    render_description_block,
    render_status_comment,
    upsert_description_block,
)


def test_description_block_uses_visible_text_markers_and_preserves_user_text() -> None:
    block = render_description_block(
        pr_title="Ship feature",
        pr_number=12,
        pr_state="open",
        pr_url="https://github.com/acme/repo/pull/12",
        branch="feature/task",
        base="main",
        latest_commit="abc123 Fix bug",
        last_sync="2026-06-13T00:00:00Z",
    )

    assert DESCRIPTION_START in block
    assert DESCRIPTION_END in block
    assert "<!--" not in block

    original = "User-authored context above.\n"
    updated = upsert_description_block(original, block)

    assert updated.startswith("User-authored context above.")
    assert block in updated

    replacement = render_description_block(
        pr_title="Ship feature",
        pr_number=12,
        pr_state="merged",
        pr_url="https://github.com/acme/repo/pull/12",
        branch="feature/task",
        base="main",
        latest_commit="def456 Merge",
        last_sync="2026-06-13T01:00:00Z",
    )

    replaced = upsert_description_block(updated, replacement)

    assert replacement in replaced
    assert replaced.count(DESCRIPTION_START) == 1
    assert "User-authored context above." in replaced
    assert "abc123 Fix bug" not in replaced


def test_status_comment_detection_uses_visible_prefix() -> None:
    comment = render_status_comment(branch="feature/task", pr_number=12, body="Ready")

    found = find_status_comment(
        [
            {"id": "human", "comment_text": "Human note"},
            {"id": "sync", "comment_text": comment},
        ]
    )

    assert comment.startswith(STATUS_COMMENT_PREFIX)
    assert "<!--" not in comment
    assert found == {"id": "sync", "comment_text": comment}


@pytest.mark.skipif(
    not os.environ.get("CLICKUP_AGENT_MARKER_PROBE_TASK_ID"),
    reason="set CLICKUP_AGENT_MARKER_PROBE_TASK_ID to run the live marker normalization probe",
)
def test_live_marker_probe_placeholder() -> None:
    assert description_block_survives(os.environ["CLICKUP_AGENT_MARKER_PROBE_TASK_ID"]) is True
