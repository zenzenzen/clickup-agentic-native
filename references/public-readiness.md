# Public baseline audit

Checked 6 September 2026, before the first workflow hardening slice. Repository visibility was public. This is a scoped audit, not certification that all historical data is safe.

- Scanned 61 tracked files and 293 historical blobs across 54 commits reachable from locally available refs for company-name variants, credential-shaped strings and maintainer machine paths.
- No company-name or machine-path matches. One credential-pattern hit in tests/test_connect_cmd.py is a hardcoded synthetic fixture used to assert that tokens are absent from output.
- Inspected title/body text for 22 GitHub issues/PRs and one release with the same company/credential patterns; no matches. There were zero Actions runs.
- Built the source distribution and wheel. Neither includes .env, .env.local, plans, .icm or .git paths.

Not covered: unknown private identifiers, semantic confidentiality, refs unavailable locally, issue comments/review threads, externally hosted screenshots and attachments, or downloaded release assets. Preserve LICENSE/NOTICE attribution. A dedicated secret scanner and human review of company-derived material remain release gates.

## Remediation order

1. Fix the Actions credential bootstrap; runtime deliberately reads the canonical user env file rather than process environment.
2. Require evidence for push, checks and review; do not infer them from branch names or merge state.
3. Replace narrow task-ID inference and fixed workflow defaults with validated configuration in the binding slice.
4. Before promotion, test a clean install and disposable provider round trip and pin that tested revision. Refresh this audit for the actual release commit and artifact contents.

The existing license metadata format produced a setuptools deprecation warning during build; update it in a separate packaging change while preserving license terms.
