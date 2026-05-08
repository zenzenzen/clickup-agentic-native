# Milestone Runbook Validation

This records the implementation conveyor belt used for the generated ClickUp tool catalog and first `run` toolchains.

## Commit Conveyor Belt

Each milestone task was committed separately with a body containing:

- `Milestone`
- `Task`
- `Why`
- `Validation`

## Public Repo Verification

The repository was verified as public before implementation and again after validation:

```bash
gh repo view --json nameWithOwner,visibility,url
```

Expected visibility:

```text
PUBLIC
```

## Final Validation

Run before the final runbook commit:

```bash
uv run pytest
bash -n scripts/install.sh
bash -n scripts/install-skill.sh
clickup-agent --version
clickup-agent doctor || true
gh repo view --json nameWithOwner,visibility,url
```

Observed result:

- `9 passed`
- Shell scripts parsed successfully.
- `clickup-agent --version` reported `0.1.0`.
- `.env.example` doctor check reported missing credentials without exposing secrets.
- GitHub reported `zenzenzen/clickup-agentic-native` as `PUBLIC`.
