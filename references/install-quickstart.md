# Install Quickstart

Use this reference when setting up `clickup-agent` manually or from another
agent. Real ClickUp tokens belong only in `$HOME/.config/clickup-agent/.env`.

## Manual One-Line Path

```bash
bash scripts/quickstart.sh
clickup-agent connect <cursor|claude-code|codex|generic>
clickup-agent doctor --live-auth
```

`scripts/quickstart.sh` installs the package with `uv tool install`, runs
`clickup-agent setup` interactively, and prints the next commands.

## Agent-Automatic Path

Use process environment for secret input so tokens do not appear in tracked
files:

```bash
uv tool install . --python 3.12 --reinstall
CLICKUP_API_KEY=... CLICKUP_WORKSPACE_ID=... clickup-agent setup --non-interactive
clickup-agent connect <cursor|claude-code|codex|generic>
clickup-agent doctor --live-auth
```

Optional setup inputs:

```bash
CLICKUP_WEBHOOK_SECRET=...
```

Equivalent installer form:

```bash
bash scripts/install.sh \
  --non-interactive \
  --api-key "$CLICKUP_API_KEY" \
  --workspace-id "$CLICKUP_WORKSPACE_ID" \
  --install-method uv \
  --cursor skip
```

Add `--cursor project` or `--cursor global` to write Cursor MCP config during
install. Add `--skill` to install the bundled Codex skill after setup.

## MCP Registration

All clients should launch the same stdio command:

```bash
clickup-agent mcp
```

`clickup-agent connect <client>` prints the right registration shape without
embedding tokens, `CLICKUP_ENV_FILE`, or absolute executable paths. Use
`--write` for config-file clients:

```bash
clickup-agent connect cursor --write --scope project
clickup-agent connect cursor --write --scope global
clickup-agent connect codex --write
clickup-agent connect claude-code
```

The native agent always reads `$HOME/.config/clickup-agent/.env`.
