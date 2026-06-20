# Stage: Catch-Up Docs

## Purpose

Add `catch-up-docs` as a dry-run-first curated wrapper for documentation catch-up after the context manifest defines its pinned action and action-plan shape.

## Inputs

| Layer | Path | Required? | Use |
| --- | --- | --- | --- |
| 3 | `CONTEXT.md` | required | Operational catch-up and write safety rules. |
| 3 | `UBIQUITOUS_LANGUAGE.md` | required | Documentation catch-up, pinned action, and sync topology terms. |
| 3 | `docs/icm/stages/phase-1-5-context-manifest/STAGE.md` | required | Manifest contract to reuse. |
| 3 | `src/clickup_agent/toolchains.py` | required | Curated wrapper runtime and existing primitives. |
| 3 | `src/clickup_agent/devlinks.py` | optional | PR metadata and managed PR block conventions. |
| 3 | `src/clickup_agent/markers.py` | optional | Managed block markers. |

## Do Not Load

- Live ClickUp credentials.
- Arbitrary user-authored checklists for mutation.
- Full comment history unless a handoff/decision flow explicitly needs it.

## Process

1. Add `clickup-agent run catch-up-docs` as a curated wrapper.
2. Infer Task candidates from branch prefix/substring for dry-run only.
3. Require explicit Task target or explicit `--create-task --list-id <id>` for live writes.
4. Emit an MCP action plan in dry-run output.
5. Require explicit live write topology such as `clickup-only`, `pr-only`, or `bidirectional`.
6. Update only managed blocks and managed `Action Items` / `Verification` checklists.
7. Use comments only for `decision-log` or explicit handoff notes.

## Outputs

| Path | Description |
| --- | --- |
| `src/clickup_agent/toolchains.py` or split module | `catch-up-docs` wrapper implementation. |
| tests | Dry-run, target resolution, topology, checklist, and no-surprise-write coverage. |

## Verify

- Dry-run output includes an inspectable MCP action plan.
- Live execution rejects missing/ambiguous Task target.
- Live execution rejects missing/ambiguous write topology.
- Missing-Task flow offers explicit create-and-self-assign plan.
- Managed checklist updates are non-destructive.
- No live ClickUp/GitHub calls in unit tests.

## Review Gate

Human or agent reviewer confirms `catch-up-docs` automates operational catch-up without surprise writes or noisy comments.

## Transitions

- forward: `phase-2-runtime-split`
- revisit: return to Phase 1.5 if the manifest contract is insufficient
- abort: preserve dry-run output and write a resume note

## Provenance

Commit message should mention Phase 1.6 `catch-up-docs` and include focused tests run.
