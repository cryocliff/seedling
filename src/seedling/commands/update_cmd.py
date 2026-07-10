"""
`seed update-commands` -- the ONLY way seedling's own commands change.

The installers copy seedling's source into ~/seedling/system/src (WITHOUT
its .git folder -- no git checkout lives inside seedling) and record where
that source came from in the `update_source` setting: the git URL it was
cloned from, or the directory it was copied from. That copy never changes
on its own. This command updates by RE-FETCHING from the recorded source:

  - git URL          -> fresh `git clone --depth 1` into a temp folder,
                        then swap it in (minus .git)
  - directory path   -> re-copy from that directory (minus .git)
  - nothing recorded -> reinstall the local copy as-is, which doubles as a
                        "repair" command for hand-edited sources

Either way, seed-cli is then reinstalled from the refreshed copy, and the
`seed` shell function (system/shell/seed.ps1|.sh) is re-rendered from the
refreshed templates so shell-side changes ship with updates too.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from .. import colors, config, fsutil, paths, shell_integration, uv_tool, git_tool

# Suffix for the rename-aside trick below; also what the sweep looks for.
_ASIDE_MARKER = ".old-"


def _swap_in(src: Path, tmp: Path) -> bool:
    """Replace ~/seedling/system/src with the freshly fetched copy at `tmp`.
    robust_rmtree (not plain rmtree) because pre-existing installs may still
    have a .git full of read-only object files in the old copy."""
    failures = fsutil.robust_rmtree(src)
    if failures:
        print("Could not replace the old source copy; these files are stuck:")
        for f in failures:
            print(f"  - {f}")
        fsutil.robust_rmtree(tmp)
        return False
    tmp.rename(src)
    return True


def _refresh_from_directory(src: Path, source_dir: Path) -> bool:
    """Replace ~/seedling/system/src with a copy of `source_dir`."""
    if not (source_dir / "src" / "pyproject.toml").exists():
        print(f"error: {source_dir} doesn't look like a seedling source tree "
              "(no src/pyproject.toml). Check the `update_source` config value.")
        return False
    print(f"Copying seedling source from {source_dir} ...")
    tmp = src.parent / (src.name + ".new")
    fsutil.robust_rmtree(tmp)
    # .git never lives inside seedling, and vendor/ payloads (offline
    # binaries -- possibly hundreds of MB of pre-seeded VS Code) belong on
    # the distribution source, not in the private source copy.
    shutil.copytree(source_dir, tmp, ignore=shutil.ignore_patterns(".git", "vendor"))
    return _swap_in(src, tmp)


def _refresh_from_url(src: Path, url: str) -> bool:
    """Replace ~/seedling/system/src with a fresh shallow clone of `url`.
    Never fatal: a failed download leaves the current copy in place, and
    the reinstall below still runs against it."""
    try:
        git = git_tool.ensure_git()
    except git_tool.GitNotFound as e:
        print(f"git isn't available ({e}), so seedling can't download updates. "
              "Reinstalling from the current local copy instead.")
        return True

    print(f"Downloading the latest seedling from {url} ...")
    tmp = src.parent / (src.name + ".new")
    fsutil.robust_rmtree(tmp)
    returncode = git_tool.run_streamed([git, "clone", "--depth", "1", url, str(tmp)])
    if returncode != 0:
        print("Download failed; reinstalling from the current local copy instead.")
        fsutil.robust_rmtree(tmp)
        return True
    if not (tmp / "src" / "pyproject.toml").exists():
        print(f"warning: what {url} serves doesn't look like a seedling source "
              "tree (no src/pyproject.toml); keeping the current copy.")
        fsutil.robust_rmtree(tmp)
        return True
    fsutil.robust_rmtree(tmp / ".git")
    fsutil.robust_rmtree(tmp / "vendor")
    return _swap_in(src, tmp)


def _self_install_targets() -> list[Path]:
    """What `uv tool install` must replace: the tool venv (whose python.exe
    IS the currently running seed-cli) and the seed-cli shim."""
    exe = "seed-cli.exe" if os.name == "nt" else "seed-cli"
    return [paths.TOOL_DIR / "seedling", paths.BIN_DIR / exe]


def _sweep_aside_leftovers() -> None:
    """Delete the renamed-aside copies a PREVIOUS update left behind (see
    _move_running_self_aside). By now that update's process has long exited,
    so they delete normally. Best-effort."""
    for target in _self_install_targets():
        for leftover in target.parent.glob(target.name + _ASIDE_MARKER + "*"):
            fsutil.robust_rmtree(leftover)


def _move_running_self_aside() -> list[tuple[Path, Path]]:
    """The self-update trick that keeps `uv tool install --force --reinstall`
    from failing with 'Access is denied' on Windows: the reinstall must
    DELETE the tool venv, but this very process is running from its
    python.exe -- Windows refuses to delete a running executable (and, worse,
    uv gets partway before failing, leaving a gutted install with a broken
    `seed`). Windows DOES allow renaming a running executable's tree, so the
    live copies are renamed aside, uv installs into fresh paths, and the
    aside copies are swept on the NEXT update (or rolled back if uv fails).
    Returns [(original, aside), ...] for rollback."""
    if os.name != "nt":
        return []  # POSIX replaces in-use files fine
    moved = []
    for target in _self_install_targets():
        if not target.exists():
            continue
        aside = target.with_name(target.name + _ASIDE_MARKER + str(os.getpid()))
        try:
            target.rename(aside)
            moved.append((target, aside))
        except OSError:
            pass  # locked harder than expected; let uv try its luck as-is
    return moved


def _roll_back_aside(moved: list[tuple[Path, Path]]) -> None:
    """uv failed mid-install: put the renamed-aside live copies back so the
    user still has a working `seed` (the failure must never brick the CLI)."""
    for original, aside in reversed(moved):
        try:
            if original.exists():
                fsutil.robust_rmtree(original)  # uv's partial debris
            aside.rename(original)
        except OSError:
            print(f"warning: couldn't restore {original} from {aside}; "
                  "if `seed` stops working, re-run the installer.")


def run(args) -> int:
    src = paths.SRC_DIR
    if not src.exists():
        print(f"No seedling source found at {src}.")
        print("Re-run the installer (install.cmd -- or `sh install.cmd` on "
              "macOS/Linux) to set it up.")
        return 1

    update_source = config.get("update_source")

    if update_source:
        source_dir = Path(str(update_source)).expanduser()
        if source_dir.is_dir():
            if not _refresh_from_directory(src, source_dir):
                return 1
        else:
            if not _refresh_from_url(src, str(update_source)):
                return 1
    else:
        print("No update source is recorded, so there's nowhere to fetch a "
              "newer version from; reinstalling from the current local copy "
              "(this still picks up any changes made there by hand).")
        print("Tip: `seed config set update_source <git-url-or-directory>` "
              "gives this command somewhere to update from.")

    print("Reinstalling the seed CLI ...")
    _sweep_aside_leftovers()
    moved = _move_running_self_aside()
    try:
        # The python package (pyproject.toml) lives in src/ within the repo tree.
        uv_tool.run(["tool", "install", "--force", "--reinstall", str(src / "src")],
                    env=uv_tool.tool_install_env())
    except (subprocess.CalledProcessError, uv_tool.UvNotFound):
        _roll_back_aside(moved)
        print("The reinstall failed; the previous seed CLI was restored and "
              "still works. Fix the problem above and re-run "
              "`seed update-commands`.")
        return 1

    # The `seed` shell FUNCTION (system/shell/seed.ps1|.sh, hooked into the
    # user's profile by the installer) is part of "the commands" too --
    # re-render it from the refreshed templates, or template changes would
    # only ever reach users on a full reinstall.
    refreshed = shell_integration.refresh()
    if refreshed:
        print("Refreshing shell integration ...")
        print("(takes effect in new shells; or re-source "
              f"{refreshed[0]} in this one)")

    print(colors.ok("Done. Your `seed` commands are up to date."))
    return 0
