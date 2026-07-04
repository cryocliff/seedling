from __future__ import annotations

import os

from .. import paths


def _activate_script(venv_path):
    """Return the right activation script for the current shell/OS."""
    if os.name == "nt":
        ps1 = venv_path / "Scripts" / "Activate.ps1"
        bat = venv_path / "Scripts" / "activate.bat"
        if ps1.exists():
            return ps1
        if bat.exists():
            return bat
    posix = venv_path / "bin" / "activate"
    if posix.exists():
        return posix
    return None


def run(args) -> int:
    if not args.name:
        print("Usage: seed activate <name>")
        return 1

    target = paths.venv_dir(args.name)
    if not target.exists():
        print(f"No venv named '{args.name}' found in {paths.VENVS_DIR}")
        return 1

    script = _activate_script(target)
    if script is None:
        print(f"Couldn't find an activation script inside {target}")
        return 1

    if getattr(args, "print_path", False):
        # Used by the `seed` shell function, which sources this path directly
        # so activation actually affects the caller's shell.
        print(str(script))
        return 0

    print(
        "This only works when 'seed' is the shell function installed by the "
        "seedling installer (it's what lets activation affect your current "
        "shell). If you're seeing this, re-run the installer or open a new "
        "terminal.\n"
        f"Activation script: {script}"
    )
    return 0
