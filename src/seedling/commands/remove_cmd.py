from __future__ import annotations

import shutil

from .. import paths
from . import kill_cmd


def run(args) -> int:
    home = paths.HOME
    if not home.exists():
        print(f"Nothing to remove; {home} does not exist.")
        return 0

    if not getattr(args, "yes", False):
        print(f"This will permanently delete EVERYTHING under {home}")
        print("(all base pythons, venvs, VS Code, and its extensions/settings).")
        print("It will also force-close any running Python and VS Code processes "
              "first (not just seedling's) to make sure nothing is left in use.")
        answer = input("Type 'yes' to confirm: ").strip().lower()
        if answer != "yes":
            print("Aborted. Nothing was deleted.")
            return 1

    print("Closing Python and VS Code processes so nothing is left in use...")
    killed = kill_cmd.kill_python_and_vscode()
    if killed:
        print(f"Closed {len(killed)} process(es).")
    else:
        print("Nothing matching was running.")

    print(f"Deleting {home} ...")
    shutil.rmtree(home, ignore_errors=True)

    if home.exists():
        print("Some files could still not be removed (they may be held open by "
              "something outside Python/VS Code, e.g. a file explorer window "
              "with a folder under ~/seedling open). Close it and try again.")
        return 1

    print("Done. seedling has been fully removed from your user directory.")
    print("Note: the `seed` shell function/alias itself is still in your shell")
    print("profile. Run the uninstaller, or remove it manually, to fully clean up.")
    return 0
