# Development Link Reference

Use this when a ClickUp task is being created, updated, summarized, or commented from a code repository.

## Branch To PR Lookup

If the current work is on a Git branch, check whether a GitHub PR already exists for that branch:

```bash
git branch --show-current
gh pr view --json url,number,title,headRefName,baseRefName,state 2>/dev/null
```

If `gh pr view` succeeds, treat the returned `url` as the canonical PR link for the current branch. If it fails, do not invent a PR URL and do not create a PR unless the user explicitly asks.

## ClickUp Back-Link Rule

When creating or updating the related ClickUp task, include the existing PR link in the task context. Preferred order once ClickUp write tools exist:

1. Add or update a dedicated development/reference field if the workspace defines one.
2. Otherwise add a task comment with the PR title, number, URL, source branch, and base branch.
3. Otherwise include the PR URL in the task description or task update summary.

Do not duplicate the same PR link repeatedly. First search or inspect recent task context when tools support it.

## Current Scaffold Behavior

The current agent has task comments and task description updates, so development links can be carried into ClickUp today through those fallbacks. Dedicated development/reference custom field discovery and duplicate-safe link updates are still planned.

## Example Task Comment Shape

```text
Development reference:
- PR: <title> (#<number>)
- URL: <url>
- Branch: <headRefName> -> <baseRefName>
```

## Safety

- Link only PRs discovered from the current branch or explicitly provided by the user.
- Never expose tokens from `gh`, env files, or MCP config.
- If the repo has no GitHub remote or `gh` is unauthenticated, report that PR discovery is unavailable.
