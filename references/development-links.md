# Development Link Reference

Use this when a ClickUp task is being created, updated, summarized, or commented from a code repository.

## Branch To PR Lookup

If the current work is on a Git branch, check whether a GitHub PR already exists for that branch:

```bash
clickup-agent dev pr
```

`dev pr` is read-only and reports one explicit state: `found`, `not_found`,
`timeout`, `gh_missing`, `unauthenticated`, or `no_remote`. If it returns
`found`, treat the returned `pr.url` as the canonical PR link for the current
branch. If it does not return `found`, do not invent a PR URL and do not create
a PR unless the user explicitly asks.

## ClickUp Back-Link Rule

When creating or updating the related ClickUp task, include the existing PR link in the task context. Preferred order:

1. Use `clickup-agent run dev-sync --dry-run` to preview the managed ClickUp updates.
2. Use `--live` only when the user wants ClickUp mutated.
3. Let `dev-sync` manage only its visible development reference block, status comment, and `Development Sync` checklist.

Do not duplicate the same PR link repeatedly. `dev-sync` reads the task and
comments first and skips backlink creation when the URL is already present.

## Development Sync

Dry-run example:

```bash
clickup-agent run dev-sync \
  --dry-run \
  --task-id abc \
  --branch feature/task \
  --pr-url https://github.com/owner/repo/pull/123 \
  --pr-title "Ship feature" \
  --pr-number 123 \
  --pr-state open
```

Managed ClickUp description block:

```text
--- Development reference (dev-sync; auto-managed, edits will be overwritten) ---
- PR: <title> (#<number>) - <state>
- URL: <url>
- Branch: <head> -> <base>
- Latest commit: <sha> <subject>
- Last sync: <iso8601>
--- end dev-sync ---
```

Managed status comments begin with `[dev-sync] GitHub development state`.

## Safety

- Link only PRs discovered from the current branch or explicitly provided by the user.
- Never expose tokens from `gh`, env files, or MCP config.
- If the repo has no GitHub remote or `gh` is unauthenticated, report that PR discovery is unavailable.
- ClickUp-side markers are visible text, not HTML comments.
