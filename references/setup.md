# Setup Reference

Use this when installing, repairing, or checking `clickup-agent`.

## Requirements

- Python 3.12
- `uv` preferred for isolated installation
- A ClickUp personal token stored in a local env file

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

Use `.env.local` for local secrets. It is gitignored and should have owner-only permissions:

```bash
cp .env.example .env.local
chmod 600 .env.local
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

It backs up an existing env file, writes the new env file with `0600` permissions, and prints an MCP config snippet.

## Health Check

```bash
clickup-agent doctor --env-file .env.local
```

The output should only say whether values are configured. It must not reveal token values.
