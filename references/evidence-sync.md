# Evidence-aware development sync

`dev-sync` accepts branch/PR metadata as caller-supplied context. A branch name
no longer resolves “Branch pushed,” and a merged PR no longer resolves “Review
completed.” Push, review and lint/type-check items require fetched evidence.
Without it, their result is unknown and their managed checklist items remain
unresolved. `--check-item` cannot override these three evidence-backed items;
it still applies to operator-defined work items.

## Verify a PR

Use `gh` authentication with read access to the repository, PR reviews, refs,
checks and statuses. Supply the full current PR head SHA. This optional flag
performs GitHub reads even in dry-run mode; it does not write to GitHub.

```bash
clickup-agent run dev-sync --dry-run \
  --task-id TASK_ID --pr-url https://github.com/OWNER/REPO/pull/123 \
  --latest-commit FULL_40_CHARACTER_HEAD_SHA --verify-github \
  --required-check lint --required-check typecheck
```

List exact check/context names that represent your lint/type requirements.
With no required names, lint/type checks remain unknown. Missing, ambiguous
or wrong-SHA checks cannot pass. A skipped check is not successful evidence.
The current policy recognizes GitHub check runs and commit statuses; it does
not infer required checks from branch protection or certify deployment.

Push evidence checks the current remote ref against the SHA. A deleted branch
returns unknown. Review evidence requires a current-SHA approval and no
outstanding changes-requested review in the fetched reviewer states. It does
not certify all branch-protection review requirements. The PR head is re-read
after collection; a changed head aborts before ClickUp operations.

GitHub errors or mismatched supplied branch/SHA stop the sync. The response
includes evidence source, SHA, observation time and per-category results.
CLI and `clickup_agent_dev_sync` MCP support the same `verify_github` and
`required_checks` inputs. Raw generated operations remain unchanged.

## Repeats and limits

For the default managed sync, equal status-comment content and equal checklist
items produce no mutation. The generated timestamp alone does not trigger an
update. The GitHub managed PR block also skips equal content while preserving
human text. Explicit duplicate comments are suppressed when found in fetched
comments. Unchanged direct task-field values are skipped.

This is scoped replay suppression, not transactional or concurrent sync.
Durable operation receipts, complete comment pagination, conflict detection,
explicit task bindings, and multi-provider recovery remain later roadmap work.
A concurrent remote edit can still race a write. Do not infer full workflow
completion from the development checklist.

The Actions example needs `CLICKUP_AGENT_REV` pinned to a commit containing
these flags, plus ClickUp credentials and GitHub read permissions. Changes are
local until committed/released; do not pin an older release and expect new flags.

Provider field references: [PR reviews](https://docs.github.com/en/rest/pulls/reviews)
and [check runs](https://docs.github.com/en/rest/checks/runs).
