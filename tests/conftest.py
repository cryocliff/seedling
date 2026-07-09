"""
Shared fixtures for the seedling test suite.

Design constraints these fixtures enforce:

- Every test runs against a THROWAWAY seedling home (tmp_path), never the
  real ~/seedling. seedling's path constants are computed at import time,
  so the `home` fixture rebinds them on the modules and restores the
  originals afterward.
- The machine-wide process killer (kill_cmd.kill_python_and_vscode) is
  neutered for every test -- it would otherwise force-close every Python
  process on the machine, including the test runner and anything the
  developer has open.
- Environment variables seedling reads (SEEDLING_*) or writes (SSL_*,
  UV_*, GIT_SSL_CAINFO) are cleared per test and restored by monkeypatch.

Run the suite with:  uvx pytest          (from the repo root)
             or:     python -m pytest   (with pytest installed)
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
sys.path.insert(0, str(SRC))

from seedling import git_tool as git_tool_mod  # noqa: E402
from seedling import paths as paths_mod  # noqa: E402

# Everything seedling might read from -- or write into -- the environment.
_ISOLATED_ENV_VARS = [
    "SEEDLING_HOME", "SEEDLING_YES", "SEEDLING_NONINTERACTIVE",
    "SEEDLING_NO_LOG", "SEEDLING_REPO", "SEEDLING_AUTO_SETUP",
    "SEEDLING_AUTO_VSCODE", "VIRTUAL_ENV",
    "SSL_CERT_FILE", "GIT_SSL_CAINFO", "UV_NATIVE_TLS",
    "UV_CACHE_DIR", "UV_CONFIG_FILE", "UV_DEFAULT_INDEX",
    "UV_PYTHON_INSTALL_MIRROR", "UV_FIND_LINKS", "UV_NO_INDEX",
]

_ORIGINALS = {
    "HOME": paths_mod.HOME,
    "SYSTEM_DIR": paths_mod.SYSTEM_DIR,
    "BIN_DIR": paths_mod.BIN_DIR,
    "TOOL_DIR": paths_mod.TOOL_DIR,
    "SRC_DIR": paths_mod.SRC_DIR,
    "CONFIG_DIR": paths_mod.CONFIG_DIR,
    "CONFIG_FILE": paths_mod.CONFIG_FILE,
    "SHELL_DIR": paths_mod.SHELL_DIR,
    "LOGS_DIR": paths_mod.LOGS_DIR,
    "UV_CACHE_DIR": paths_mod.UV_CACHE_DIR,
    "PYTHON_DIR": paths_mod.PYTHON_DIR,
    "BASE_DIR": paths_mod.BASE_DIR,
    "VENVS_DIR": paths_mod.VENVS_DIR,
    "EXTENSIONS_DIR": paths_mod.EXTENSIONS_DIR,
    "VSCODE_DIR": paths_mod.VSCODE_DIR,
    "VSCODE_APP_DIR": paths_mod.VSCODE_APP_DIR,
    "VSCODE_DATA_DIR": paths_mod.VSCODE_DATA_DIR,
    "VSCODE_EXTENSIONS_DIR": paths_mod.VSCODE_EXTENSIONS_DIR,
    "REPO_DIR": paths_mod.REPO_DIR,
}
_ORIGINAL_GIT_DIR = git_tool_mod.GIT_DIR


def _rebind_paths(home: Path) -> None:
    p = paths_mod
    p.HOME = home
    p.SYSTEM_DIR = home / "system"
    p.BIN_DIR = p.SYSTEM_DIR / "bin"
    p.TOOL_DIR = p.SYSTEM_DIR / "tool"
    p.SRC_DIR = p.SYSTEM_DIR / "src"
    p.CONFIG_DIR = p.SYSTEM_DIR / "config"
    p.CONFIG_FILE = p.CONFIG_DIR / "settings.json"
    p.SHELL_DIR = p.SYSTEM_DIR / "shell"
    p.LOGS_DIR = p.SYSTEM_DIR / "logs"
    p.UV_CACHE_DIR = p.SYSTEM_DIR / "cache" / "uv"
    p.PYTHON_DIR = home / "python"
    p.BASE_DIR = p.PYTHON_DIR / "base"
    p.VENVS_DIR = p.PYTHON_DIR / "venvs"
    p.EXTENSIONS_DIR = home / "extensions"
    p.VSCODE_DIR = p.EXTENSIONS_DIR / "vscode"
    p.VSCODE_APP_DIR = p.VSCODE_DIR / "app"
    p.VSCODE_DATA_DIR = p.VSCODE_DIR / "data"
    p.VSCODE_EXTENSIONS_DIR = p.VSCODE_DIR / "extensions"
    p.REPO_DIR = home / "repo"
    p.ALL_DIRS = [
        p.HOME, p.SYSTEM_DIR, p.BIN_DIR, p.CONFIG_DIR, p.SHELL_DIR,
        p.LOGS_DIR, p.UV_CACHE_DIR, p.PYTHON_DIR, p.BASE_DIR, p.VENVS_DIR,
        p.EXTENSIONS_DIR, p.VSCODE_DIR, p.REPO_DIR,
    ]
    git_tool_mod.GIT_DIR = p.EXTENSIONS_DIR / "git"


def _restore_paths() -> None:
    for name, value in _ORIGINALS.items():
        setattr(paths_mod, name, value)
    paths_mod.ALL_DIRS = [
        paths_mod.HOME, paths_mod.SYSTEM_DIR, paths_mod.BIN_DIR,
        paths_mod.CONFIG_DIR, paths_mod.SHELL_DIR, paths_mod.LOGS_DIR,
        paths_mod.UV_CACHE_DIR, paths_mod.PYTHON_DIR, paths_mod.BASE_DIR,
        paths_mod.VENVS_DIR, paths_mod.EXTENSIONS_DIR, paths_mod.VSCODE_DIR,
        paths_mod.REPO_DIR,
    ]
    git_tool_mod.GIT_DIR = _ORIGINAL_GIT_DIR


@pytest.fixture
def home(tmp_path, monkeypatch):
    """A sandbox seedling home: paths rebound, env isolated, process killer
    disabled. Yields the home Path (not yet created on disk)."""
    h = tmp_path / "seedling"
    for var in _ISOLATED_ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("SEEDLING_HOME", str(h))
    monkeypatch.setenv("SEEDLING_NO_LOG", "1")  # keep test output un-teed
    _rebind_paths(h)

    # Never let a test force-close real processes on this machine.
    from seedling.commands import kill_cmd
    monkeypatch.setattr(kill_cmd, "kill_python_and_vscode", lambda: [])

    yield h
    _restore_paths()


@pytest.fixture
def run_cli(home, capsys):
    """Invoke the CLI in-process; returns (exit_code, combined_output)."""
    from seedling import cli

    def _run(*argv: str):
        try:
            code = cli.main(list(argv))
        except SystemExit as e:  # argparse usage errors / --help
            code = e.code if isinstance(e.code, int) else 0
        captured = capsys.readouterr()
        return code, captured.out + captured.err

    return _run


@pytest.fixture
def answer(monkeypatch):
    """Feed scripted answers to input() prompts."""
    def _set(*answers: str):
        replies = list(answers)
        monkeypatch.setattr("builtins.input", lambda _prompt="": replies.pop(0))
    return _set


def make_venv_dirs(home: Path, *names: str) -> None:
    """Fake venv folders with a platform-appropriate interpreter, placed
    exactly where seedling looks for it (Scripts\\python.exe on Windows,
    bin/python on POSIX) so `status`/health checks treat them as real venvs."""
    for name in names:
        venv = home / "python" / "venvs" / name
        interp = (venv / "Scripts" / "python.exe") if os.name == "nt" \
            else (venv / "bin" / "python")
        interp.parent.mkdir(parents=True, exist_ok=True)
        interp.write_text("")
        (venv / "pyvenv.cfg").write_text("version = 3.12.0\n")


def make_base_python(home: Path, tag: str, dirname: str) -> Path:
    """Fake base-python install with a matching alias file and a
    platform-appropriate interpreter -- python.exe on Windows, bin/python3 on
    POSIX, matching what `status` and venv creation resolve."""
    base = home / "python" / "base"
    target = base / dirname
    interp = (target / "python.exe") if os.name == "nt" \
        else (target / "bin" / "python3")
    interp.parent.mkdir(parents=True, exist_ok=True)
    interp.write_text("")
    (base / f"{tag}.alias.json").write_text('{"target": "%s"}' % dirname)
    return target


# ---------------------------------------------------------------------------
# Tool availability, checked once
# ---------------------------------------------------------------------------
UV = shutil.which("uv")
GIT = shutil.which("git")
BASH = shutil.which("bash")
POWERSHELL = shutil.which("powershell")

needs_uv = pytest.mark.skipif(UV is None, reason="uv not on PATH")
needs_git = pytest.mark.skipif(GIT is None, reason="git not on PATH")
needs_bash = pytest.mark.skipif(BASH is None, reason="bash not on PATH")
needs_powershell = pytest.mark.skipif(POWERSHELL is None, reason="powershell not on PATH")
windows_only = pytest.mark.skipif(os.name != "nt", reason="Windows-only behavior")


def run_bash(script: str, timeout: int = 120) -> subprocess.CompletedProcess:
    """Run a bash script (git-bash on Windows) and capture output."""
    return subprocess.run(
        [BASH, "-c", script], capture_output=True, text=True, timeout=timeout,
    )


def make_repo_copy(dest: Path) -> Path:
    """Copy of this repo suitable for installer tests (no .git, no caches)."""
    shutil.copytree(
        REPO_ROOT, dest,
        ignore=shutil.ignore_patterns(".git", "__pycache__", "tests", ".claude"),
    )
    return dest


STUB_UV = """#!/bin/sh
BIN="$(dirname "$0")"
echo "uv $*" >> "$BIN/calls.log"
env | grep -E "^(UV_|SSL_CERT_FILE|GIT_SSL_CAINFO)" >> "$BIN/uv-env.log" 2>/dev/null
printf '#!/bin/sh\\necho "seed-cli $*" >> "$(dirname "$0")/calls.log"\\nexit 0\\n' > "$BIN/seed-cli"
chmod +x "$BIN/seed-cli"
exit 0
"""


def plant_stub_uv(home: Path) -> Path:
    """Pre-place a POSIX stub uv so installer runs need no network. The stub
    logs its invocations and environment, and fabricates a seed-cli stub
    that logs too."""
    bin_dir = home / "system" / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    stub = bin_dir / "uv"
    stub.write_text(STUB_UV)
    stub.chmod(0o755)
    return bin_dir
