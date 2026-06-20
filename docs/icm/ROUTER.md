# ICM Router

This router gives agents a low-token path through the operational catch-up roadmap. Keep `CONTEXT.md` and `UBIQUITOUS_LANGUAGE.md` as glossary/reference files; use these stage contracts for executable workflow routing.

## Route

| Stage | Contract | Job |
| --- | --- | --- |
| Phase 1 | [Truthful Discovery](stages/phase-1-truthful-discovery/STAGE.md) | Make curated-wrapper discovery match implemented wrappers without adding startup/setup overhead. |
| Phase 1.5 | [Context Manifest](stages/phase-1-5-context-manifest/STAGE.md) | Add static, manifest-first context loading surfaces and pinned actions without repo-resident context. |
| Phase 1.6 | [Catch-Up Docs](stages/phase-1-6-catch-up-docs/STAGE.md) | Add the `catch-up-docs` curated wrapper for documentation catch-up. |

## Layer Map

| Layer | Path | Purpose |
| --- | --- | --- |
| 0 | `README.md`, `SKILL.md` | Operator and agent identity surfaces. |
| 1 | `docs/icm/ROUTER.md` | Route agents to the right stage contract. |
| 2 | `docs/icm/stages/*/STAGE.md` | Stage contracts with inputs, exclusions, outputs, and gates. |
| 3 | `CONTEXT.md`, `UBIQUITOUS_LANGUAGE.md`, `docs/adr/` | Stable reference context. |
| 4 | OS temp/cache paths | Working context artifacts; never write generated context into the repository. |

## Global Rules

- Do not load the whole repository by default.
- Do not commit ignored `plans/` artifacts.
- Keep writes dry-run-first unless live execution is explicit.
- Keep generated or retrieved context outside the git worktree.
- Record provenance in any stage output or implementation summary.
