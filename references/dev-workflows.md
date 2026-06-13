# Development Workflows

Use these workflows when an agent is doing implementation work tied to a
ClickUp task.

## Work Log

`work-log` is mutable state for the current piece of work. It upserts exact-name
items in two task checklists:

- `Action Items`
- `Verification`

Examples:

```bash
clickup-agent run work-log --dry-run --task-id abc --add-item "Implement parser"
clickup-agent run work-log --dry-run --task-id abc --check "Implement parser"
clickup-agent run work-log --dry-run --task-id abc --checklist verification --add-item "Run focused tests"
clickup-agent run work-log --dry-run --task-id abc --checklist verification --check "Run focused tests"
```

Use `--live` only when the ClickUp task should be mutated.

## Decision Log

`decision-log` is append-only journal state. It creates one new comment per
decision and never edits or deletes previous decision comments.

```bash
clickup-agent run decision-log \
  --dry-run \
  --task-id abc \
  --decision "Switched X to Y" \
  --context "Y matches the existing wrapper model." \
  --alternatives "Keep X" \
  --source conversation \
  --pr-url https://github.com/owner/repo/pull/123 \
  --commit abc123
```

Decision comments begin with `[dev-sync:decision]` so they remain visible after
ClickUp markdown normalization.

Automatic extraction from PR review threads is out of scope for this version.
Agents should summarize the decision, pivot, or key conversation and append it
explicitly with `decision-log`.

## PR Body Sync

`dev-sync --mode clickup-to-github` writes only a managed block in the GitHub PR
body. It never closes, merges, reopens, or otherwise changes PR lifecycle state.

```bash
clickup-agent run dev-sync \
  --dry-run \
  --task-id abc \
  --mode clickup-to-github \
  --pr-url https://github.com/owner/repo/pull/123
```

The GitHub-managed block is bounded by HTML comments because GitHub preserves
them:

```text
<!-- clickup-agent:dev-sync:start -->
...
<!-- clickup-agent:dev-sync:end -->
```

The same command defaults to `--mode github-to-clickup`; use `--mode
bidirectional` when both ClickUp and GitHub surfaces should be updated in one
dry-run/live envelope.

## Branch Audit

`dev audit` is the read-only starting point for reconciling local branches and
merged PRs back into ClickUp tasks:

```bash
clickup-agent dev audit
```

It enumerates local branches, joins them with one batched GitHub PR listing, and
prints compact JSON with branch, PR, merge, task-id guess, ahead, and behind
fields. Use merged PR fields from this output as the low-token source for
`dev-sync`.

Do not inspect `git log` or backfill detailed comments/checklists from commit
history until the user explicitly approves that extra pass.

## Hotfix Documentation

Use `hotfix-doc` when a merged PR needs a documentation-only ClickUp receipt:

```bash
clickup-agent run hotfix-doc \
  --dry-run \
  --list-id 123 \
  --title "Fix docs" \
  --pr-url https://github.com/org/repo/pull/1 \
  --branch hotfix/docs \
  --merge-commit abc123 \
  --problem "What broke" \
  --fix "What changed" \
  --changed-file README.md \
  --validation "uv run pytest"
```

The macro creates a completed task with `documentation`, `github`, and `hotfix`
tags, high priority, PR fields in `markdown_content`, and a resolved `Hotfix
tracking` checklist. It previews by default; add `--live` only when the task
should be created.

## GitHub Actions Event Sync

`examples/github-actions-dev-sync.yml` is a reference workflow for repositories
that want PR events to update ClickUp automatically. Copy it into
`.github/workflows/` and configure a `CLICKUP_API_KEY` repository secret.
`CLICKUP_WORKSPACE_ID` is optional unless your task ids require it.

The workflow runs on:

- `pull_request`: opened, edited, synchronize, closed
- `pull_request_review`: submitted

The review event is separate because GitHub Actions models review submissions as
`pull_request_review`, not a `pull_request` subtype. Both event paths call the
same command:

```bash
clickup-agent run dev-sync --live --mode github-to-clickup ...
```

The workflow derives a ClickUp task id from the branch prefix and exits
successfully when no task id can be found. It does not echo the ClickUp token.

ClickUp-to-local webhooks are out of scope for a local CLI. Use `dev audit` as
the reconciliation path for ClickUp-side drift.
