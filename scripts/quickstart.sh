#!/usr/bin/env bash
# One-line local quickstart for installing and configuring clickup-agent.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

if ! command -v uv >/dev/null 2>&1; then
  printf 'uv is required for quickstart. Install uv, then rerun this script.\n' >&2
  printf 'Fallback: python3.12 -m venv .venv && source .venv/bin/activate && python -m pip install -e .\n' >&2
  exit 2
fi

(cd "${REPO_ROOT}" && uv tool install . --python 3.12 --reinstall)

clickup-agent setup

cat <<'TXT'

Next:
  clickup-agent connect <cursor|claude-code|codex|generic>
  clickup-agent doctor --live-auth
TXT
