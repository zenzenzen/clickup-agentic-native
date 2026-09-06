# Developer workflow roadmap

The intended workflow connects a task to its branch and PR, preserves the plan
as work progresses, and attaches verification evidence to the code under review.
ClickUp is the first task provider and GitHub is the development provider.

## Delivered in the public-baseline hardening change

- Independent integration positioning and a scoped public-artifact audit.
- Optional SHA-specific GitHub verification through CLI and MCP.
- Push, review and check evidence that cannot be inferred from branch names or
  merge state; unknown evidence stays unresolved.
- Replay suppression for unchanged managed status comments, checklist items and
  GitHub PR body blocks.
- A pinned CI example that uses native credential setup, skips forks and cleans
  up its own credential file after success or failure.

Read [evidence-aware sync](../references/evidence-sync.md) for behavior and
limitations, and [public readiness](../references/public-readiness.md) for audit
scope. The feature ledger's verified entries refer to the stated checks; they
do not certify a hosted rollout or production integration.

## Delivery sequence

| Stage | Outcome | Ledger items |
|---|---|---|
| Public baseline | Honest capabilities, installable package and scoped audit | W01–W03 |
| Reliable task/branch relationship | Explicit bindings, configuration, durable reconciliation and a live demo | W04–W06 |
| Ticket preparation | Provenance-backed drafts, readiness checks and staged plans | W07–W08 |
| Portable agent workflow | Installable skill, bounded execution and independent review | W09–W11 |
| Broader automation | Event reconciliation and a second real provider | W12–W13 |

The next implementation slice is explicit binding and neutral configuration.
A regex match should identify a candidate, never authorize a ticket mutation.
Task scope belongs to the task owner; PR, check and review facts belong to
GitHub. Human prose remains outside managed regions.

Staged execution will require readiness gates, bounded worker inputs, isolated
worktrees, revision-aware evidence, repair limits and a resumable journal.
These capabilities, a generalized skill and a second provider are planned,
not included in the hardening release. Merge and deployment remain separately
controlled actions.

See [feature-ledger.json](../feature-ledger.json) for acceptance criteria,
dependencies, verification evidence and remaining work.
