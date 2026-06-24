#!/usr/bin/env bash
# Install the repo's canonical SKILL.md into Codex's skill discovery folder.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
CODEX_HOME_DIR="${CODEX_HOME:-${HOME}/.codex}"
TARGET_DIR="${CODEX_HOME_DIR}/skills/clickup-agentic-native"

say() {
  printf '\n%s\n' "$*"
}

require_file() {
  local path="$1"
  if [[ ! -f "${path}" ]]; then
    printf 'Required file not found: %s\n' "${path}" >&2
    exit 1
  fi
}

validate_frontmatter() {
  local skill_file="$1"
  if ! grep -q '^name: clickup-agentic-native$' "${skill_file}"; then
    printf 'SKILL.md frontmatter is missing name: clickup-agentic-native\n' >&2
    exit 1
  fi
  if ! grep -q '^description: ' "${skill_file}"; then
    printf 'SKILL.md frontmatter is missing description.\n' >&2
    exit 1
  fi
}

install_skill() {
  require_file "${REPO_ROOT}/SKILL.md"
  validate_frontmatter "${REPO_ROOT}/SKILL.md"

  if [[ -e "${TARGET_DIR}" ]]; then
    local backup="${TARGET_DIR}.bak.$(date +%Y%m%d%H%M%S)"
    mv "${TARGET_DIR}" "${backup}"
    say "Existing skill backed up to ${backup}"
  fi

  mkdir -p "${TARGET_DIR}"
  cp "${REPO_ROOT}/SKILL.md" "${TARGET_DIR}/SKILL.md"
  if [[ -d "${REPO_ROOT}/references" ]]; then
    mkdir -p "${TARGET_DIR}/references"
    cp "${REPO_ROOT}"/references/*.md "${TARGET_DIR}/references/"
  fi

  say "Installed clickup-agentic-native skill to ${TARGET_DIR}"
  printf 'Validation:\n'
  printf '  test -f "%s/SKILL.md"\n' "${TARGET_DIR}"
  printf '  rg "clickup-agent" "%s"\n' "${TARGET_DIR}"
  printf '\nExample trigger prompts:\n'
  printf '  "Use clickup-agentic-native to set up Cursor MCP access."\n'
  printf '  "Use clickup-agentic-native to repair my clickup-agent install."\n'
  printf '  "Use clickup-agentic-native to explain current ClickUp capabilities."\n'
  printf '\nOnboarding:\n'
  printf '  clickup-agent onboard\n'
  printf '  Macro movesets: dev-sync, catch-up-docs, context load, branch audit, hotfix-doc.\n'
}

install_skill "$@"
