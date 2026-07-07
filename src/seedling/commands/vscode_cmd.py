from __future__ import annotations

import json
import os
import platform
import subprocess
import tarfile
import urllib.request
import zipfile
from pathlib import Path

from .. import download, paths

# A minimal, opinionated starter kit: Python debugging, Jupyter, and linting.
DEFAULT_EXTENSIONS = [
    "ms-python.python",
    "ms-python.vscode-pylance",
    "ms-python.debugpy",
    "ms-toolsai.jupyter",
    "ms-toolsai.jupyter-keymap",
    "ms-toolsai.jupyter-renderers",
    "charliermarsh.ruff",  # fast linter/formatter for python
    "editorconfig.editorconfig",
    "mechatroner.rainbow-csv",  # color-codes CSV/TSV columns, adds a query feature
]

DEFAULT_SETTINGS = {
    "python.terminal.activateEnvironment": True,
    "editor.formatOnSave": True,
    "editor.defaultFormatter": "charliermarsh.ruff",
    "notebook.formatOnSave.enabled": True,
    "files.autoSave": "onFocusChange",
    "python.analysis.typeCheckingMode": "basic",
    "telemetry.telemetryLevel": "off",
    "update.mode": "none",
    "extensions.autoUpdate": False,
}

# Passed to every subprocess we launch against VS Code, so its own
# Electron/GPU/Chromium log spam never lands in the user's terminal.
_QUIET = {
    "stdout": subprocess.DEVNULL,
    "stderr": subprocess.DEVNULL,
    "stdin": subprocess.DEVNULL,
}


def _os_build() -> tuple[str, str]:
    """Return (download-os-id, archive-kind) for the current platform."""
    system = platform.system()
    machine = platform.machine().lower()
    if system == "Windows":
        return "win32-x64-archive", "zip"
    if system == "Darwin":
        arch = "darwin-arm64" if machine in ("arm64", "aarch64") else "darwin"
        return arch, "zip"
    # Linux
    arch = "linux-arm64" if machine in ("arm64", "aarch64") else "linux-x64"
    return arch, "tar"


def _resolve_download(os_id: str) -> tuple[str, str | None]:
    """Ask VS Code's update API for the latest stable build's direct URL and
    its published SHA-256, so the archive can be verified after download.
    Falls back to the plain redirect URL (no checksum) if the API is
    unreachable -- e.g. on locked-down networks."""
    api = f"https://update.code.visualstudio.com/api/update/{os_id}/stable/latest"
    try:
        req = urllib.request.Request(api, headers={"User-Agent": "seedling"})
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read())
        url = data.get("url")
        if url:
            return url, data.get("sha256hash")
    except (OSError, ValueError):
        pass
    return f"https://code.visualstudio.com/sha/download?build=stable&os={os_id}", None


def _extract(archive: Path, dest: Path, kind: str) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    print(f"Extracting to {dest} ...")
    if kind == "zip":
        with zipfile.ZipFile(archive) as z:
            z.extractall(dest)
    else:
        with tarfile.open(archive) as t:
            t.extractall(dest)


def _find_cli(app_dir: Path) -> list[str] | None:
    """The argv PREFIX for VS Code's actual CLI entry point -- the thing
    that runs when you type `code --install-extension ...` or `code .` in a
    normal terminal. This is what handles extension management and window
    opening headlessly, without spawning a bare Electron/GPU process.

    Using the raw main GUI binary instead of this (an earlier bug in this
    file) opens a full window per --install-extension call, and floods
    stdout/stderr with Electron log spam. Always prefer this over the GUI
    binary for anything CLI-shaped.
    """
    system = platform.system()
    if system == "Windows":
        # The .cmd wrapper is what actually runs VS Code's CLI JS entry
        # point as a plain Node process; Code.exe alone does not do this.
        script = app_dir / "bin" / "code.cmd"
        if script.exists():
            return ["cmd", "/c", str(script)]
        return None
    if system == "Darwin":
        bundle = next(app_dir.glob("*.app"), None)
        if bundle:
            candidate = bundle / "Contents" / "Resources" / "app" / "bin" / "code"
            if candidate.exists():
                return [str(candidate)]
        return None
    # Linux
    candidate = app_dir / "bin" / "code"
    if candidate.exists():
        return [str(candidate)]
    candidate = app_dir / "code"
    if candidate.exists():
        return [str(candidate)]
    return None


def _find_gui_executable(app_dir: Path) -> Path | None:
    """The main GUI binary. Only used as a last-resort fallback for opening
    a window if the CLI script (above) can't be found for some reason."""
    system = platform.system()
    if system == "Windows":
        candidate = app_dir / "Code.exe"
        if candidate.exists():
            return candidate
    elif system == "Darwin":
        bundle = next(app_dir.glob("*.app"), None)
        if bundle:
            candidate = bundle / "Contents" / "MacOS" / "Electron"
            if candidate.exists():
                return candidate
    else:
        candidate = app_dir / "code"
        if candidate.exists():
            return candidate
    return None


def _write_default_settings() -> None:
    user_dir = paths.VSCODE_APP_DIR / "data" / "user-data" / "User"
    user_dir.mkdir(parents=True, exist_ok=True)
    settings_file = user_dir / "settings.json"
    if not settings_file.exists():
        settings_file.write_text(json.dumps(DEFAULT_SETTINGS, indent=2))


def _chmod_executables(app_dir: Path) -> None:
    if os.name == "nt":
        return
    for candidate in (app_dir / "bin" / "code", app_dir / "code"):
        if candidate.exists():
            candidate.chmod(candidate.stat().st_mode | 0o111)
    bundle = next(app_dir.glob("*.app"), None)
    if bundle:
        candidate = bundle / "Contents" / "Resources" / "app" / "bin" / "code"
        if candidate.exists():
            candidate.chmod(candidate.stat().st_mode | 0o111)


def install(force: bool = False) -> list[str] | None:
    """Ensure VS Code is installed, returning the CLI argv prefix to use for
    opening it (or None on failure). Only re-downloads if `force` is set or
    nothing is installed yet -- this is what makes plain `seed vscode` calls
    idempotent instead of re-downloading/reinstalling every single time."""
    paths.ensure_layout()

    cli = _find_cli(paths.VSCODE_APP_DIR)
    if cli and not force:
        return cli

    os_id, kind = _os_build()
    url, sha256 = _resolve_download(os_id)
    tmp_archive = paths.VSCODE_DIR / f"vscode-download.{'zip' if kind == 'zip' else 'tar.gz'}"

    paths.VSCODE_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Downloading VS Code from {url} ...")
    try:
        download.fetch(url, tmp_archive, expected_sha256=sha256, label="VS Code")
    except download.ChecksumMismatch as e:
        print(f"error: {e}")
        return None
    except OSError as e:
        # Clean failure instead of a traceback -- e.g. an offline network.
        # (On offline deployments, pre-seed extensions/vscode instead; see
        # docs/OFFLINE.md.)
        print(f"error: VS Code could not be downloaded ({e}).")
        tmp_archive.unlink(missing_ok=True)
        return None
    _extract(tmp_archive, paths.VSCODE_APP_DIR, kind)
    tmp_archive.unlink(missing_ok=True)

    # Portable mode: a `data` folder next to the executable keeps *everything*
    # (settings, extensions, workspace state) inside extensions/vscode/app,
    # instead of the OS-default per-user locations.
    (paths.VSCODE_APP_DIR / "data").mkdir(exist_ok=True)

    _chmod_executables(paths.VSCODE_APP_DIR)

    cli = _find_cli(paths.VSCODE_APP_DIR)
    if cli is None:
        print("VS Code was downloaded but its CLI script could not be located "
              "-- extensions won't be installed automatically. You can still "
              "install them by hand from within VS Code.")
        gui = _find_gui_executable(paths.VSCODE_APP_DIR)
        return [str(gui)] if gui else None

    _write_default_settings()

    print("Installing default extensions (Python, Jupyter, linting)...")
    for ext in DEFAULT_EXTENSIONS:
        result = subprocess.run(
            [*cli, "--install-extension", ext, "--force"],
            **_QUIET, check=False,
        )
        if result.returncode != 0:
            print(f"  warning: failed to install {ext} (exit {result.returncode})")

    print(f"VS Code installed at {paths.VSCODE_APP_DIR}")
    return cli


def open_window(cli: list[str], path: str) -> None:
    """Open VS Code at `path` via its CLI entry point, fully detached from
    seedling's own process so it never blocks or leaks output into the
    caller's terminal. Shared by `seed vscode` and `seed open-repo`."""
    popen_kwargs = dict(_QUIET)
    if os.name == "nt":
        popen_kwargs["creationflags"] = (
            subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
        )
    else:
        popen_kwargs["start_new_session"] = True
    subprocess.Popen([*cli, path], **popen_kwargs)


def run(args) -> int:
    cli = install(force=getattr(args, "reinstall", False))
    if cli is None:
        print("Could not find any way to launch VS Code after installing it.")
        return 1

    if getattr(args, "no_open", False):
        # Install-only mode, used by the installers' default setup: get VS
        # Code onto disk without popping a window in the middle of install.
        print("VS Code is installed and ready. Open it with:  seed vscode")
        return 0

    open_path = getattr(args, "path", None) or str(Path.cwd())
    print(f"Opening VS Code -> {open_path}")
    open_window(cli, open_path)
    return 0
