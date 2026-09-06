"""Exercise the exact example shell with the real setup/config contract."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import textwrap

import pytest


WORKFLOW = Path(__file__).resolve().parents[1] / "examples/github-actions-dev-sync.yml"


def _script(name: str) -> str:
    section = WORKFLOW.read_text().split(f"      - name: {name}\n", 1)[1]
    section = section.split("      - name:", 1)[0]
    return textwrap.dedent(section.split("        run: |\n", 1)[1])


def _run(tmp_path, *, fail=False, existing=False, branch="work/86abcdefgh-demo", token="pk_ci_fixture"):
    bindir = tmp_path / "bin"
    bindir.mkdir()
    # Real setup and loader; replace only the remote write with a recording stub.
    launcher = bindir / "clickup-agent"
    launcher.write_text(f"#!{sys.executable}\n" + '''import json, os, stat, sys
from pathlib import Path
from clickup_agent.cli import main
from clickup_agent.config import load_config, default_env_file
if sys.argv[1] == 'setup':
    raise SystemExit(main(sys.argv[1:]))
config = load_config()
assert config.api_key == os.environ['CLICKUP_API_KEY']
assert stat.S_IMODE(default_env_file().stat().st_mode) == 0o600
Path(os.environ['RECEIPT']).write_text(json.dumps(sys.argv[1:]))
raise SystemExit(int(os.environ.get('FAIL_SYNC', '0')))
''')
    launcher.chmod(0o700)
    home = tmp_path / "home"
    home.mkdir()
    config = home / ".config/clickup-agent/.env"
    if existing:
        config.parent.mkdir(parents=True)
        config.write_text("preserve me")
    env = {**os.environ, "HOME": str(home), "PATH": str(bindir) + os.pathsep + os.environ["PATH"],
           "CLICKUP_API_KEY": token, "CLICKUP_WORKSPACE_ID": "123", "PR_BRANCH": branch,
           "PR_NUMBER": "12", "PR_TITLE": 'literal $(touch BAD); `false`',
           "PR_URL": "https://github.com/example/repo/pull/12", "PR_STATE": "open", "PR_SHA": "a" * 40,
           "RECEIPT": str(tmp_path / "receipt.json"), "FAIL_SYNC": "7" if fail else "0"}
    result = subprocess.run(["bash", "-c", _script("Configure and sync")], env=env, cwd=tmp_path,
                            capture_output=True, text=True)
    assert not token or token not in result.stdout + result.stderr
    assert not (tmp_path / "BAD").exists()
    return result, config


@pytest.mark.parametrize("fail", [False, True])
def test_ci_native_setup_loads_credentials_and_cleans_up_after_sync(tmp_path, fail):
    result, config = _run(tmp_path, fail=fail)
    assert result.returncode == (7 if fail else 0), result.stderr
    assert not config.exists()
    args = json.loads((tmp_path / "receipt.json").read_text())
    assert args[args.index("--pr-title") + 1] == 'literal $(touch BAD); `false`'


def test_ci_preserves_existing_configuration(tmp_path):
    result, config = _run(tmp_path, existing=True)
    assert result.returncode == 2
    assert config.read_text() == "preserve me"
    assert not (tmp_path / "receipt.json").exists()


@pytest.mark.parametrize("overrides", [{"token": ""}, {"branch": "unlinked-work"}])
def test_ci_skips_without_credentials_or_task(tmp_path, overrides):
    result, config = _run(tmp_path, **overrides)
    assert result.returncode == 0
    assert not config.exists()
    assert not (tmp_path / "receipt.json").exists()


def test_ci_custom_id_passes_workspace_resolution(tmp_path):
    result, _ = _run(tmp_path, branch="work/DEMO-42-change")
    assert result.returncode == 0, result.stderr
    args = json.loads((tmp_path / "receipt.json").read_text())
    assert "--custom-task-ids" in args
    assert args[args.index("--team-id") + 1] == "123"


def test_ci_install_rejects_unpinned_revision(tmp_path):
    env = {**os.environ, "CLICKUP_AGENT_REV": "main"}
    result = subprocess.run(["bash", "-c", _script("Install pinned clickup-agent")],
                            env=env, capture_output=True, text=True)
    assert result.returncode == 2
    assert "full commit SHA" in result.stderr
