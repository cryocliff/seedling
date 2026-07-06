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

from . import colors, paths


class UvNotFound(RuntimeError):
    pass


def tag_line(line: str) -> str:
    """Prefix a line of uv's own output so it's never mistaken for a message
    seedling printed itself. Blank lines pass through untouched."""
    if not line.strip():
        return line
    return f"{colors.dim('[uv]')} {line}"


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
        "  bash:       curl -fsSL https://raw.githubusercontent.com/cryocliff/seedling/main/installers/install.sh | sh\n"
        "  powershell: irm https://raw.githubusercontent.com/cryocliff/seedling/main/installers/install.ps1 | iex"
    )


def _build_env(env: dict | None) -> dict:
    """The environment for every uv invocation. Redirects uv's download/
    package cache into ~/seedling/system/cache/uv so it lives inside the
    seedling folder like everything else, instead of uv's default
    ~/.cache/uv or %LOCALAPPDATA%\\uv. setdefault means an explicit
    UV_CACHE_DIR already in the user's environment still wins."""
    full_env = os.environ.copy()
    if env:
        full_env.update(env)
    full_env.setdefault("UV_CACHE_DIR", str(paths.UV_CACHE_DIR))
    return full_env


def run(args: list[str], *, env: dict | None = None, check: bool = True) -> subprocess.CompletedProcess:
    """Runs uv, streaming its combined stdout/stderr live with a `[uv]` tag
    on every line so it reads distinctly from seedling's own print()s."""
    uv = find_uv()
    full_env = _build_env(env)
    cmd = [str(uv), *args]
    proc = subprocess.Popen(
        cmd, env=full_env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1,
    )
    assert proc.stdout is not None
    for line in proc.stdout:
        sys.stdout.write(tag_line(line))
    proc.wait()
    if check and proc.returncode != 0:
        raise subprocess.CalledProcessError(proc.returncode, cmd)
    return subprocess.CompletedProcess(cmd, proc.returncode)


def run_captured(args: list[str], *, env: dict | None = None, check: bool = True) -> subprocess.CompletedProcess:
    """Like run(), but captures stdout/stderr instead of streaming them
    live, so the caller can filter/inspect output before deciding what (if
    anything) to print. Used where uv's own messaging would be redundant or
    misleading given seedling's own folder conventions -- e.g. uv's
    "activate with: source .../activate" hint after `uv venv`, which doesn't
    match how `seed activate` actually works."""
    uv = find_uv()
    full_env = _build_env(env)
    return subprocess.run(
        [str(uv), *args], env=full_env, check=check,
        capture_output=True, text=True,
    )


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
