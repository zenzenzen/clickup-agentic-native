# Stage: Truthful Discovery

## Purpose

Make all implemented curated wrappers visible and described consistently from one lightweight metadata source, without adding runtime or setup overhead.

## Inputs

| Layer | Path | Required? | Use |
| --- | --- | --- | --- |
| 3 | `CONTEXT.md` | required | Product terms and safety rules. |
| 3 | `UBIQUITOUS_LANGUAGE.md` | required | Canonical command/discovery language. |
| 3 | `src/clickup_agent/toolchains.py` | required | Implemented wrapper handlers and runtime metadata fallback. |
| 3 | `scripts/generate_tool_catalog.py` | required | Catalog generation path for curated wrappers. |
| 3 | `src/clickup_agent/mcp_server.py` | required | MCP tooling plan surface. |
| 3 | `tests/test_cli_discovery.py`, `tests/test_catalog_generation.py`, `tests/test_mcp_server.py` | required | Drift guard and discovery validation. |

## Do Not Load

- Live ClickUp credentials or `$HOME/.config/clickup-agent/.env`.
- Ignored local `plans/` artifacts unless the operator explicitly asks for planning context.
- Full OpenAPI catalog JSON except for the `toolchains` section needed by tests.

## Process

1. Add a dependency-light curated-wrapper metadata module.
2. Make catalog generation import that metadata instead of a hard-coded wrapper list.
3. Make MCP `implemented_commands` derive from the same metadata.
4. Regenerate the committed catalog.
5. Tighten discovery tests to strict equality.
6. Add a structural import/startup check proving metadata import does not load heavy runtime modules.

## Outputs

| Path | Description |
| --- | --- |
| `src/clickup_agent/discovery.py` or equivalent | Single metadata source for curated wrappers. |
| `src/clickup_agent/catalog/tool_catalog.json` | Regenerated catalog with all implemented wrappers. |
| `tests/*` | Drift guards and import sanity checks. |

## Verify

- `pytest tests/test_catalog_generation.py tests/test_cli_discovery.py tests/test_mcp_server.py`
- `python -m clickup_agent hotkeys list --format json`
- Metadata import does not import heavy modules such as `httpx`, `mcp_server`, `devsync`, or `toolchains`.

## Review Gate

Human or agent reviewer confirms discovery truth and no new runtime/setup overhead before moving to Phase 1.5.

## Transitions

- forward: `phase-1-5-context-manifest`
- revisit: update metadata/test shape if a wrapper is missing or overhead check fails
- abort: preserve test output and write a resume note

## Provenance

Commit message should mention Phase 1 truthful discovery and summarize the validation commands run.
