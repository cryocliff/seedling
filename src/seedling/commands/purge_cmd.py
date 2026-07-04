"""
`seed purge` -- the nuclear option. Unlike `seed remove-user` (which only
deletes what's under ~/seedling but leaves the `seed` shell hook installed,
so a fresh `seed update-commands`/reinstall can pick back up cleanly),
`seed purge` also strips the shell hook from every shell profile it can
find. After this, `seed` stops existing as a command entirely -- this is
the same end state as running uninstall.sh/uninstall.ps1, just reachable
from inside `seed` itself.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from .. import paths
from . import kill_cmd


def _candidate_profiles() -> list[Path]:
    home = Path.home()
    candidates = [
        home / ".zshrc",
        home / ".bashrc",
        home / ".bash_profile",
        home / ".profile",
        # PowerShell profile locations (checked on every OS since PowerShell
        # itself is cross-platform; harmless no-ops where they don't exist)
        home / "Documents" / "PowerShell" / "Microsoft.PowerShell_profile.ps1",
        home / "Documents" / "WindowsPowerShell" / "Microsoft.PowerShell_profile.ps1",
    ]
    return candidates


def _strip_hook(profile: Path) -> bool:
    if not profile.exists():
        return False
    try:
        lines = profile.read_text().splitlines()
    except OSError:
        return False

    marker = str(paths.SHELL_DIR)
    new_lines = [
        line for line in lines
        if marker not in line and line.strip() != "# seedling"
    ]

    if new_lines == lines:
        return False

    try:
        profile.write_text("\n".join(new_lines).rstrip() + "\n" if new_lines else "")
    except OSError:
        return False
    return True


def run(args) -> int:
    home = paths.HOME

    if not getattr(args, "yes", False):
        print(f"This fully uninstalls seedling: deletes EVERYTHING under {home}")
        print("(all base pythons, venvs, VS Code, cloned repos, uv, and seedling's")
        print("own source) AND removes the `seed` shell hook from your shell profile.")
        print("After this, `seed` stops working entirely -- you'd need to reinstall.")
        print("It will also force-close any running Python/VS Code processes first")
        print("(not just seedling's) so nothing blocks deletion.")
        answer = input("Type 'yes' to confirm: ").strip().lower()
        if answer != "yes":
            print("Aborted. Nothing was removed.")
            return 1

    print("Closing Python and VS Code processes so nothing is left in use...")
    killed = kill_cmd.kill_python_and_vscode()
    print(f"Closed {len(killed)} process(es)." if killed else "Nothing matching was running.")

    removed_from = [p for p in _candidate_profiles() if _strip_hook(p)]

    if home.exists():
        print(f"Deleting {home} ...")
        shutil.rmtree(home, ignore_errors=True)

    if removed_from:
        print("Removed the seedling shell hook from:")
        for p in removed_from:
            print(f"  - {p}")
    else:
        print("No shell hook found in the usual profile locations "
              "(nothing to clean up there, or it lives somewhere this "
              "command doesn't check).")

    if home.exists():
        print("Some files under seedling could not be removed (still in use?). "
              "Close anything else that might have them open and try again.")
        return 1

    print("seedling has been fully uninstalled.")
    return 0
