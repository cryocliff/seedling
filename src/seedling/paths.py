"""
Single source of truth for seedling's folder layout.

Everything seedling touches lives under one directory so nothing gets
scattered across the filesystem:

~/seedling/
    system/               <- everything seedling needs to run itself, kept
        bin/                 out of the way of the stuff you actually use
        tool/             <- the uv-managed venv seed-cli itself runs in
        src/              <- seedling's own source (see `seed update-commands`)
        config/
            settings.json <- seedling's own config (default python version, etc.)
        logs/             <- one log file per day; every `seed` command appends
                             what ran and everything it printed
        shell/
            seed.sh       <- sourced by bash/zsh to define the `seed` function
            seed.ps1      <- dot-sourced by PowerShell to define the `seed` function
    python/
        base/<tag>/       <- base python installs, e.g. base/312
        venvs/<name>/     <- virtual environments built off a base python
    extensions/
        vscode/
            app/          <- the portable VS Code install itself
            data/         <- --user-data-dir (settings, keybindings, etc.)
            extensions/   <- --extensions-dir
    repo/
        <name>/           <- repos cloned with `seed clone-repo`
"""

from __future__ import annotations

import os
from pathlib import Path


def seedling_home() -> Path:
    """Root of everything seedling manages. Overridable for testing via env var."""
    override = os.environ.get("SEEDLING_HOME")
    if override:
        return Path(override).expanduser().resolve()
    return Path.home() / "seedling"


HOME = seedling_home()

# Everything seedling needs to operate itself lives under system/, so the
# top level of ~/seedling stays limited to system/, python/, extensions/,
# and repo/ -- the folders someone actually cares about browsing.
SYSTEM_DIR = HOME / "system"
BIN_DIR = SYSTEM_DIR / "bin"
TOOL_DIR = SYSTEM_DIR / "tool"
SRC_DIR = SYSTEM_DIR / "src"
CONFIG_DIR = SYSTEM_DIR / "config"
CONFIG_FILE = CONFIG_DIR / "settings.json"
SHELL_DIR = SYSTEM_DIR / "shell"
LOGS_DIR = SYSTEM_DIR / "logs"

PYTHON_DIR = HOME / "python"
BASE_DIR = PYTHON_DIR / "base"
VENVS_DIR = PYTHON_DIR / "venvs"

EXTENSIONS_DIR = HOME / "extensions"
VSCODE_DIR = EXTENSIONS_DIR / "vscode"
VSCODE_APP_DIR = VSCODE_DIR / "app"
VSCODE_DATA_DIR = VSCODE_DIR / "data"
VSCODE_EXTENSIONS_DIR = VSCODE_DIR / "extensions"

REPO_DIR = HOME / "repo"

ALL_DIRS = [
    HOME,
    SYSTEM_DIR,
    BIN_DIR,
    CONFIG_DIR,
    SHELL_DIR,
    LOGS_DIR,
    PYTHON_DIR,
    BASE_DIR,
    VENVS_DIR,
    EXTENSIONS_DIR,
    VSCODE_DIR,
    REPO_DIR,
]


def ensure_layout() -> None:
    for d in ALL_DIRS:
        d.mkdir(parents=True, exist_ok=True)


def uv_binary() -> Path:
    exe = "uv.exe" if os.name == "nt" else "uv"
    return BIN_DIR / exe


def base_python_dir(tag: str) -> Path:
    """e.g. tag='312' -> ~/seedling/python/base/312"""
    return BASE_DIR / tag


def base_alias_file(tag: str) -> Path:
    """uv installs python into a versioned dir name (e.g. cpython-3.12.4-...).
    We keep a tiny alias file so `312` always resolves to whatever that real
    dir is, without relying on symlink permissions (which Windows restricts)."""
    return BASE_DIR / f"{tag}.alias.json"


def venv_dir(name: str) -> Path:
    return VENVS_DIR / name


def repo_dir(name: str) -> Path:
    return REPO_DIR / name
