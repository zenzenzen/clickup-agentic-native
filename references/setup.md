# Setup Reference

Use this when installing, repairing, or checking `clickup-agent`.

## Requirements

- Python 3.12
- `uv` preferred for isolated installation
- A ClickUp personal token stored in the default local env file

## Install Or Reinstall

From the repo root:

```bash
uv tool install . --python 3.12 --reinstall
clickup-agent --version
```

For editable development:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

## Env File

Use `$HOME/.config/clickup-agent/.env` for local secrets. It is the only native `clickup-agent` env file, stays outside any workspace, and should have owner-only permissions:

```bash
mkdir -p "$HOME/.config/clickup-agent"
cp .env.example "$HOME/.config/clickup-agent/.env"
chmod 600 "$HOME/.config/clickup-agent/.env"
```

Expected keys:

```bash
CLICKUP_API_KEY=
CLICKUP_WORKSPACE_ID=
CLICKUP_WEBHOOK_SECRET=
```

`CLICKUP_API_KEY` is required. `CLICKUP_WORKSPACE_ID` and `CLICKUP_WEBHOOK_SECRET` are optional for the current scaffold.

## Interactive Setup

The local installer prompts for token, workspace ID, optional webhook secret, package install, and Cursor MCP config:

```bash
bash scripts/install.sh
```

It backs up an existing env file, writes `$HOME/.config/clickup-agent/.env` with `0600` permissions, and prints an MCP config snippet. `CLICKUP_ENV_FILE` and `--env-file` are not used by the native agent.

## Health Check

```bash
clickup-agent doctor
clickup-agent doctor --live-auth
```

The output should only say whether values are configured. It must not reveal token values.
