# MCP And Cursor Reference

Use this when connecting `clickup-agent` to Cursor or another LLM client.

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
      "env": {
        "CLICKUP_ENV_FILE": "/absolute/path/to/clickup-agentic-native/.env.local"
      }
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

The same JSON shape applies. Prefer absolute paths for `CLICKUP_ENV_FILE`.

## Installer Path

Run:

```bash
bash scripts/install.sh
```

Choose project config or global config when prompted. The installer preserves existing MCP servers and backs up the existing config first.

## Troubleshooting

- Reload Cursor after editing MCP config.
- Confirm `clickup-agent` resolves on PATH with `command -v clickup-agent`.
- Confirm the env file path exists and does not expose token values in tracked files.
- Run `clickup-agent doctor --env-file /absolute/path/to/.env.local`.
- The current MCP server exposes bootstrap/status tools; full ClickUp API tools are planned.
