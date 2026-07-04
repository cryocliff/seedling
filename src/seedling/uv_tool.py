"""
seedling never assumes uv is on the user's PATH. The bootstrap installer
(install.sh / install.ps1) downloads uv straight into ~/seedling/bin, and
this module always calls that exact copy. This keeps seedling fully
self-contained: nothing "pre-installed" is required.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from . import paths


class UvNotFound(RuntimeError):
    pass


def find_uv() -> Path:
    """Locate the sandboxed uv binary, falling back to PATH only as a last resort."""
    local = paths.uv_binary()
    if local.exists():
        return local

    on_path = shutil.which("uv")
    if on_path:
        return Path(on_path)

    raise UvNotFound(
        "uv was not found in ~/seedling/bin or on PATH.\n"
        "Re-run the seedling installer:\n"
        "  bash:       curl -fsSL https://raw.githubusercontent.com/.../install.sh | bash\n"
        "  powershell: irm https://raw.githubusercontent.com/.../install.ps1 | iex"
    )


def run(args: list[str], *, env: dict | None = None, check: bool = True) -> subprocess.CompletedProcess:
    uv = find_uv()
    full_env = os.environ.copy()
    if env:
        full_env.update(env)
    return subprocess.run([str(uv), *args], env=full_env, check=check)


def python_install_dir_env() -> dict:
    """Env override so `uv python install` lands under seedling's own tree
    instead of uv's default cache location."""
    return {"UV_PYTHON_INSTALL_DIR": str(paths.BASE_DIR)}


def tool_install_env() -> dict:
    """Env override so `uv tool install` (used to install/update seed-cli
    itself) keeps everything inside ~/seedling instead of uv's default
    per-user tool location."""
    return {
        "UV_TOOL_DIR": str(paths.TOOL_DIR),
        "UV_TOOL_BIN_DIR": str(paths.BIN_DIR),
    }
