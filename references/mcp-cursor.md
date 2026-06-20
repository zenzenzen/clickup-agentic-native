# MCP Client Reference

Use this when connecting `clickup-agent` to Cursor, Claude Code, Codex, or
another MCP-capable LLM client.

## Server Command

The MCP stdio server command is:

```bash
clickup-agent mcp
```

LLM clients should launch this command. Users normally should not run it manually except for smoke testing.

## Project Cursor Config

For one repo/workspace, use `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "clickup-agent": {
      "command": "clickup-agent",
      "args": ["mcp"],
      "env": {}
    }
  }
}
```

The repo includes `.cursor/mcp.example.json` as a portable template. The local `.cursor/mcp.json` is ignored because it contains machine-specific paths.

## Global Cursor Config

For all Cursor workspaces, use:

```text
~/.cursor/mcp.json
```

The same JSON shape applies. `clickup-agent` always reads `$HOME/.config/clickup-agent/.env`; do not add `CLICKUP_ENV_FILE` to MCP config.

## Connect Command

Print client-specific registration:

```bash
clickup-agent connect cursor
clickup-agent connect claude-code
clickup-agent connect codex
clickup-agent connect generic
```

Write config where supported:

```bash
clickup-agent connect cursor --write --scope project
clickup-agent connect cursor --write --scope global
clickup-agent connect codex --write
```

Claude Code registration is command-driven:

```bash
claude mcp add clickup-agent -- clickup-agent mcp
```

Codex config uses `~/.codex/config.toml`:

```toml
[mcp_servers.clickup-agent]
command = "clickup-agent"
args = ["mcp"]
```

## Installer Path

Run:

```bash
bash scripts/install.sh
```

Choose project config or global config when prompted, or pass
`--cursor project|global|skip` for non-interactive setup. The installer
preserves existing MCP servers and backs up the existing config first.

## Troubleshooting

- Reload Cursor after editing MCP config.
- Confirm `clickup-agent` resolves on PATH with `command -v clickup-agent`.
- Confirm the env file path exists outside tracked workspaces and does not expose token values in config files.
- Run `clickup-agent doctor`.
- Run `clickup-agent doctor --live-auth` to confirm token and workspace access with read-only ClickUp API calls.
- The current MCP server exposes bootstrap/status tools, `clickup_agent_context_manifest`, direct wrappers for all implemented curated macros including `catch-up-docs`, and `clickup_agent_run_operation` for generated operations that do not have a curated wrapper yet.
- Write wrappers return dry-run previews by default; pass `live: true` only when the action should call ClickUp.
- Broader ClickUp API coverage for docs, chat, attachments, admin workflows, and richer entity resolution is still planned.
