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
