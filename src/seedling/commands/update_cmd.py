"""
`seed update-commands` -- the ONLY way seedling's own commands change.

install.sh/install.ps1 install seedling by cloning it straight from GitHub
into ~/seedling/src, and installing seed-cli from that copy -- not from
wherever the user happened to run the installer from. That copy never
changes on its own. The only thing that updates ~/seedling/src (and
therefore the installed `seed` command) is this command, on request only.

Where updates come from, in order:
  1. the `update_source` config value, if set (`seed config set
     update_source ...`) -- either a git URL (works with self-hosted
     GitHub/GitLab on isolated networks) or a plain directory path (e.g. a
     network drive holding a copy of this repo, for machines with no git
     hosting at all);
  2. otherwise, the git remote ~/seedling/src was originally cloned from.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from .. import colors, config, paths, uv_tool, git_tool


def _refresh_from_directory(src: Path, source_dir: Path) -> bool:
    """Replace ~/seedling/system/src with a copy of `source_dir`."""
    if not (source_dir / "pyproject.toml").exists():
        print(f"error: {source_dir} doesn't look like a seedling source tree "
              "(no pyproject.toml). Check the `update_source` config value.")
        return False
    print(f"Copying seedling source from {source_dir} ...")
    tmp = src.parent / (src.name + ".new")
    if tmp.exists():
        shutil.rmtree(tmp, ignore_errors=True)
    shutil.copytree(source_dir, tmp, ignore=shutil.ignore_patterns(".git"))
    shutil.rmtree(src, ignore_errors=True)
    tmp.rename(src)
    return True


def _refresh_from_git(src: Path, url: str | None) -> None:
    """git pull into ~/seedling/system/src -- from `url` if given, else from
    whatever remote the checkout already points at. Never fatal: a failed
    pull falls back to reinstalling the local copy as-is."""
    git = git_tool.find_git()
    if git is None:
        print("git isn't available, so seedling can't pull updates. "
              "Reinstalling from the current local copy instead.")
        return

    if url is None:
        remote = subprocess.run(
            [git, "-C", str(src), "remote", "get-url", "origin"],
            capture_output=True, text=True,
        ).stdout.strip()
        label = f" from {remote}" if remote else ""
        pull_cmd = [git, "-C", str(src), "pull", "--ff-only"]
    else:
        label = f" from {url} (update_source)"
        pull_cmd = [git, "-C", str(src), "pull", "--ff-only", url]

    print(f"Checking for updates{label} ...")
    returncode = git_tool.run_streamed(pull_cmd)
    if returncode != 0:
        print("git pull failed; reinstalling from the current local copy instead.")


def run(args) -> int:
    src = paths.SRC_DIR
    if not src.exists():
        print(f"No seedling source found at {src}.")
        print("Re-run install.sh / install.cmd / install.ps1 to set it up.")
        return 1

    update_source = config.get("update_source")
    source_dir = Path(update_source).expanduser() if update_source else None

    if source_dir is not None and source_dir.is_dir():
        if not _refresh_from_directory(src, source_dir):
            return 1
    elif update_source:
        if not (src / ".git").is_dir():
            print(f"{src} isn't a git checkout, so the git URL in "
                  f"`update_source` can't be pulled from. If {update_source} "
                  "was meant to be a directory, it wasn't found.")
            print("Reinstalling from the current local copy instead.")
        else:
            _refresh_from_git(src, str(update_source))
    elif (src / ".git").is_dir():
        _refresh_from_git(src, None)
    else:
        print(f"{src} isn't a git checkout, so there's no remote to pull "
              "updates from. Reinstalling from the current local copy "
              "(this still picks up any changes you made there by hand). "
              "Tip: `seed config set update_source <git-url-or-directory>` "
              "gives this command somewhere to update from.")

    print("Reinstalling the seed CLI ...")
    uv_tool.run(["tool", "install", "--force", "--reinstall", str(src)], env=uv_tool.tool_install_env())
    print(colors.ok("Done. Your `seed` commands are up to date."))
    return 0
