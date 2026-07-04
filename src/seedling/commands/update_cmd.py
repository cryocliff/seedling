"""
`seed update-commands` -- the ONLY way seedling's own commands change.

install.sh/install.ps1 install seedling by cloning it straight from GitHub
into ~/seedling/src, and installing seed-cli from that copy -- not from
wherever the user happened to run the installer from. That copy never
changes on its own. The only thing that updates ~/seedling/src (and
therefore the installed `seed` command) is this command: it runs
`git pull` against the GitHub remote and reinstalls, on request only.
"""

from __future__ import annotations

import shutil
import subprocess

from .. import paths, uv_tool


def run(args) -> int:
    src = paths.SRC_DIR
    if not src.exists():
        print(f"No seedling source found at {src}.")
        print("Re-run install.sh / install.cmd / install.ps1 to set it up.")
        return 1

    git_dir = src / ".git"
    if git_dir.is_dir():
        if shutil.which("git") is None:
            print("git isn't available, so seedling can't pull updates. "
                  "Reinstalling from the current local copy instead.")
        else:
            remote = subprocess.run(
                ["git", "-C", str(src), "remote", "get-url", "origin"],
                capture_output=True, text=True,
            ).stdout.strip()
            label = f" from {remote}" if remote else ""
            print(f"Checking for updates{label} ...")
            result = subprocess.run(
                ["git", "-C", str(src), "pull", "--ff-only"],
                capture_output=True, text=True,
            )
            output = (result.stdout + result.stderr).strip()
            if output:
                print(output)
            if result.returncode != 0:
                print("git pull failed; reinstalling from the current local copy instead.")
    else:
        print(f"{src} isn't a git checkout, so there's no remote to pull "
              "updates from. Reinstalling from the current local copy "
              "(this still picks up any changes you made there by hand).")

    print("Reinstalling the seed CLI ...")
    uv_tool.run(["tool", "install", "--force", "--reinstall", str(src)], env=uv_tool.tool_install_env())
    print("Done. Your `seed` commands are up to date.")
    return 0
