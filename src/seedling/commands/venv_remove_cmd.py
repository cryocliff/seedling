from __future__ import annotations

import os
import shutil

from .. import paths
from . import kill_cmd


def _warn_if_active(target) -> None:
    active = os.environ.get("VIRTUAL_ENV")
    if active and os.path.abspath(active) == os.path.abspath(str(target)):
        print(f"Note: '{target.name}' looks like your currently active venv. "
              "It'll be force-closed along with any other running Python/VS "
              "Code processes before deletion, so your shell may end up with "
              "a dangling activated prompt afterward -- run `seed deactivate` "
              "once it's done.")


def _close_processes() -> None:
    print("Closing Python and VS Code processes so nothing is left in use...")
    killed = kill_cmd.kill_python_and_vscode()
    if killed:
        print(f"Closed {len(killed)} process(es).")
    else:
        print("Nothing matching was running.")


def run_all(args) -> int:
    if not paths.VENVS_DIR.exists():
        print("No venvs to remove.")
        return 0

    venvs = sorted(d for d in paths.VENVS_DIR.iterdir() if d.is_dir())
    if not venvs:
        print("No venvs to remove.")
        return 0

    for v in venvs:
        _warn_if_active(v)

    if not getattr(args, "yes", False):
        print(f"This will permanently delete {len(venvs)} venv(s) from {paths.VENVS_DIR}:")
        for v in venvs:
            print(f"  - {v.name}")
        print("It will also force-close any running Python/VS Code processes "
              "first (not just seedling's) so nothing blocks deletion.")
        answer = input("Type 'yes' to confirm: ").strip().lower()
        if answer != "yes":
            print("Aborted. Nothing was deleted.")
            return 1

    _close_processes()

    for v in venvs:
        shutil.rmtree(v, ignore_errors=True)

    print(f"Deleted {len(venvs)} venv(s).")
    return 0


def run_one(args) -> int:
    if not args.name:
        print("Usage: seed remove-venv <name>")
        return 1

    target = paths.venv_dir(args.name)
    if not target.exists():
        print(f"No venv named '{args.name}' found in {paths.VENVS_DIR}")
        return 1

    _warn_if_active(target)

    if not getattr(args, "yes", False):
        answer = input(
            f"Delete venv '{args.name}' at {target}? This will also "
            "force-close any running Python/VS Code processes first (not "
            "just seedling's). Type 'yes' to confirm: "
        ).strip().lower()
        if answer != "yes":
            print("Aborted. Nothing was deleted.")
            return 1

    _close_processes()

    shutil.rmtree(target, ignore_errors=True)
    print(f"Deleted venv '{args.name}'.")
    return 0
