"""
`seed kill-processes all` -- an escape hatch for when a venv, a runaway
script, or VS Code itself is stuck and you just want a clean slate.

Deliberately uses only OS-builtin tools (pgrep/kill on macOS+Linux,
taskkill on Windows) rather than a third-party dependency like psutil, to
stay consistent with seedling's "nothing pre-installed required" design.

Always excludes seedling's own running process (and its parent) so it can't
kill itself mid-cleanup on platforms where seed-cli's own process image is
literally a python interpreter.
"""

from __future__ import annotations

import os
import platform
import signal
import subprocess

from .. import colors, confirm

PYTHON_PROCESS_NAMES_UNIX = [
    "python", "python3",
    "python3.8", "python3.9", "python3.10", "python3.11",
    "python3.12", "python3.13", "python3.14",
    "pythonw",
]
VSCODE_PROCESS_NAMES_UNIX = [
    "code", "Code",
    "Code Helper", "Code Helper (Renderer)", "Code Helper (GPU)", "Code Helper (Plugin)",
    "Electron",
]

WINDOWS_PYTHON_IMAGES = ["python.exe", "pythonw.exe", "py.exe"]
WINDOWS_VSCODE_IMAGES = ["Code.exe"]


def _self_and_parent() -> set[int]:
    pids = {os.getpid()}
    try:
        pids.add(os.getppid())
    except OSError:
        pass
    return pids


def _pgrep(name: str) -> list[int]:
    try:
        result = subprocess.run(["pgrep", "-x", name], capture_output=True, text=True, check=False)
    except FileNotFoundError:
        return []
    return [int(line) for line in result.stdout.split() if line.isdigit()]


def _kill_unix(names: list[str], exclude: set[int]) -> list[int]:
    killed: list[int] = []
    seen: set[int] = set()
    for name in names:
        for pid in _pgrep(name):
            if pid in exclude or pid in seen:
                continue
            seen.add(pid)
            try:
                os.kill(pid, signal.SIGKILL)
                killed.append(pid)
            except ProcessLookupError:
                pass
            except PermissionError:
                print(f"  (skipped pid {pid}: permission denied)")
    return killed


def _kill_windows(images: list[str], exclude: set[int]) -> list[str]:
    killed: list[str] = []
    for image in images:
        cmd = ["taskkill", "/F", "/IM", image]
        for pid in exclude:
            cmd += ["/FI", f"PID ne {pid}"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        # taskkill exits 0 only if it actually terminated something
        if result.returncode == 0:
            killed.append(image)
    return killed


def _list_windows(images: list[str], exclude: set[int]) -> list[str]:
    """What would be killed: 'image (pid N)' entries, via tasklist."""
    found: list[str] = []
    for image in images:
        result = subprocess.run(
            ["tasklist", "/FI", f"IMAGENAME eq {image}", "/FO", "CSV", "/NH"],
            capture_output=True, text=True, check=False,
        )
        for line in result.stdout.splitlines():
            parts = [p.strip('"') for p in line.split('","')]
            if len(parts) >= 2 and parts[1].isdigit() and int(parts[1]) not in exclude:
                found.append(f"{parts[0]} (pid {parts[1]})")
    return found


def _list_unix(names: list[str], exclude: set[int]) -> list[str]:
    found: list[str] = []
    seen: set[int] = set()
    for name in names:
        for pid in _pgrep(name):
            if pid in exclude or pid in seen:
                continue
            seen.add(pid)
            found.append(f"{name} (pid {pid})")
    return found


def list_matching(target: str) -> list[str]:
    """Human-readable list of the processes a kill would hit right now."""
    exclude = _self_and_parent()
    if platform.system() == "Windows":
        if target == "all":
            images = WINDOWS_PYTHON_IMAGES + WINDOWS_VSCODE_IMAGES
        else:
            images = [target if target.lower().endswith(".exe") else f"{target}.exe"]
        return _list_windows(images, exclude)
    names = (PYTHON_PROCESS_NAMES_UNIX + VSCODE_PROCESS_NAMES_UNIX
             if target == "all" else [target])
    return _list_unix(names, exclude)


def kill_python_and_vscode() -> list:
    """Force-closes every Python/VS Code process, sparing seedling's own.
    Shared by `seed kill-processes all` and `seed remove-user` (which uses
    this to release any file locks before deleting ~/seedling)."""
    exclude = _self_and_parent()
    if platform.system() == "Windows":
        return _kill_windows(WINDOWS_PYTHON_IMAGES + WINDOWS_VSCODE_IMAGES, exclude)
    return _kill_unix(PYTHON_PROCESS_NAMES_UNIX + VSCODE_PROCESS_NAMES_UNIX, exclude)


def run(args) -> int:
    target = getattr(args, "target", None)
    if not target:
        print("Usage: seed kill-processes <all|process_name>")
        print("  seed kill-processes all          closes python + VS Code processes")
        print("  seed kill-processes <name>       closes every process named <name>")
        return 1

    if target == "all":
        description = "ALL Python and VS Code processes"
    else:
        names_unix = [target]
        image = target if target.lower().endswith(".exe") else f"{target}.exe"
        names_windows = [image]
        description = f"all '{target}' processes"

    if confirm.preview_requested(args):
        confirm.print_preview(
            f"force-close {description}",
            list_matching(target),
            notes=["processes are listed as of right now; a real run "
                   "re-matches at execution time"],
        )
        return 0

    if not confirm.auto_confirmed(args):
        print()
        print(colors.warn(f"This force-closes {description} on this machine") + " --")
        print("not just seedling's -- including any unsaved work.")
        print()
    if not confirm.confirm(args):
        print("Aborted.")
        return 1
    print()

    system = platform.system()

    print(f"Closing {description}...")
    if target == "all":
        killed = kill_python_and_vscode()
        if system == "Windows":
            print(colors.ok(f"Closed: {', '.join(killed)}") if killed else "Nothing matching was running.")
        else:
            print(colors.ok(f"Killed {len(killed)} process(es): {', '.join(str(p) for p in killed)}")
                  if killed else "Nothing matching was running.")
        return 0

    exclude = _self_and_parent()
    if system == "Windows":
        killed = _kill_windows(names_windows, exclude)
        if killed:
            print(colors.ok(f"Closed: {', '.join(killed)}"))
        else:
            print("Nothing matching was running.")
    else:
        killed = _kill_unix(names_unix, exclude)
        if killed:
            print(colors.ok(f"Killed {len(killed)} process(es): {', '.join(str(p) for p in killed)}"))
        else:
            print("Nothing matching was running.")

    return 0
