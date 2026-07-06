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

import re
import shutil
from pathlib import Path

from .. import colors, config, confirm, fsutil, paths, runlog
from . import kill_cmd

_BACKUP_NAME_RE = re.compile(r"^seedling-repo-backup(-\d+)?$")

# Shown before confirming and again after a successful purge -- once `seed`
# is gone, this screen is the last place the user will see these.
_REINSTALL_LINES = [
    "  macOS/Linux:  curl -fsSL https://raw.githubusercontent.com/cryocliff/seedling/main/installers/install.sh | sh",
    "  PowerShell:   irm https://raw.githubusercontent.com/cryocliff/seedling/main/installers/install.ps1 | iex",
]


def _print_reinstall(update_source) -> None:
    """The reinstall instructions. Installs configured with a custom
    `update_source` (self-hosted git, network drive) came from somewhere the
    public one-liners can't reach, so point at that source first."""
    print("To reinstall seedling later:")
    if update_source:
        print(f"  from your configured source ({update_source}):")
        print("    run install.cmd from inside it (`sh install.cmd` on macOS/Linux), or")
        print("    pass it to the installer as the SEEDLING_REPO environment variable")
        print("  or from the public repo:")
    for line in _REINSTALL_LINES:
        print(line)

_PARTIAL_REMOVE_LINES = [
    "  seed remove-venv <name>    delete one venv",
    "  seed remove-venvs          delete all venvs",
    "  seed remove-python <tag>   delete a base Python and the venvs built from it",
    "  seed remove-repo <name>    delete one cloned repo",
    "  seed remove-user           delete everything under ~/seedling, but keep the",
    "                             `seed` command hook so a reinstall picks right back up",
]


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


def _is_hook_line(line: str) -> bool:
    """Any line that dot-sources a seed shell script from under the seedling
    home -- deliberately matching on the home dir plus the script name
    rather than the exact current hook text, so hooks written by OLDER
    seedling layouts (e.g. ~/seedling/shell/ before it moved under
    system/) are cleaned up too. A stale survivor here means every new
    shell greets the user with a 'file not found' error after a purge."""
    if line.strip() == "# seedling":
        return True
    return str(paths.HOME) in line and ("seed.ps1" in line or "seed.sh" in line)


def _strip_hook(profile: Path) -> bool:
    if not profile.exists():
        return False
    try:
        lines = profile.read_text().splitlines()
    except OSError:
        return False

    new_lines = [line for line in lines if not _is_hook_line(line)]

    if new_lines == lines:
        return False

    try:
        profile.write_text("\n".join(new_lines).rstrip() + "\n" if new_lines else "")
    except OSError:
        return False
    return True


def _has_repos() -> bool:
    return paths.REPO_DIR.exists() and any(paths.REPO_DIR.iterdir())


def _move_repos_to_safety() -> Path:
    """Moves ~/seedling/repo out to a sibling folder in the user's home
    directory, so it survives `shutil.rmtree`-ing everything else under
    ~/seedling. Picks a non-colliding name if run more than once."""
    base = Path.home() / "seedling-repo-backup"
    dest = base
    n = 1
    while dest.exists():
        dest = Path(f"{base}-{n}")
        n += 1
    shutil.move(str(paths.REPO_DIR), str(dest))
    return dest


def _existing_backups() -> list[Path]:
    """Backup folders left behind by previous `seed purge --keep-repos` runs
    (~/seedling-repo-backup, -1, -2, ...). Without --keep-repos this time,
    the user has said they don't want cloned repos kept around at all, so
    these stale backups get cleaned up too instead of accumulating forever."""
    home = Path.home()
    return sorted(
        p for p in home.iterdir()
        if p.is_dir() and _BACKUP_NAME_RE.match(p.name)
    )


def run(args) -> int:
    home = paths.HOME
    keep_repos = getattr(args, "keep_repos", False)
    old_backups = [] if keep_repos else _existing_backups()
    # Read this before anything is deleted -- it's needed for the reinstall
    # instructions printed at the very end, when the config file is gone.
    update_source = config.get("update_source")

    if confirm.preview_requested(args):
        items = []
        if home.exists():
            items += sorted(str(p) for p in home.iterdir())
        items += [f"{p}  (shell hook line removed)"
                  for p in _candidate_profiles() if p.exists()]
        items += [f"{p}  (leftover backup from a previous --keep-repos purge)"
                  for p in old_backups]
        notes = ["any running Python/VS Code processes will be force-closed "
                 "first (not just seedling's) so nothing blocks deletion",
                 "after a real run, `seed` stops working entirely"]
        if keep_repos and _has_repos():
            notes.append(f"{paths.REPO_DIR} would be moved to safety first "
                         "(--keep-repos), not deleted")
        confirm.print_preview("fully uninstall seedling", items, notes=notes)
        return 0

    if not confirm.auto_confirmed(args):
        print()
        print(colors.danger("This fully uninstalls seedling.") + " It will:")
        print()
        print(f"  - delete {colors.bold('everything')} under {home}")
        print("    (base pythons, venvs, VS Code, cloned repos, uv, and seedling's own source)")
        print("  - remove the `seed` shell hook from your shell profile")
        print("  - force-close any running Python/VS Code processes first,")
        print("    not just seedling's, so nothing blocks deletion")
        print()
        print(colors.warn("After this, `seed` stops working entirely -- you'd need to reinstall."))
        print()

        if not keep_repos and _has_repos():
            print(colors.header("Want to keep your cloned repos?") +
                  f" ({paths.REPO_DIR} has some.)")
            print("Abort now and re-run as `seed purge --keep-repos` -- they get moved")
            print(f"out to {Path.home() / 'seedling-repo-backup'} before everything else is deleted.")
            print()

        if old_backups:
            print("Note: also deleting leftover repo backup folder(s) from a previous "
                  "`seed purge --keep-repos` (this run isn't keeping repos, so these "
                  "won't be left behind either):")
            for p in old_backups:
                print(f"  - {p}")
            print()

        print(colors.header("Only need to remove part of seedling?") +
              " There are smaller hammers:")
        for line in _PARTIAL_REMOVE_LINES:
            print(line)
        print()

        _print_reinstall(update_source)
        print()

    if not confirm.confirm(args):
        print("Aborted. Nothing was removed.")
        return 1
    print()

    print("Closing Python and VS Code processes so nothing is left in use...")
    killed = kill_cmd.kill_python_and_vscode()
    print(f"Closed {len(killed)} process(es)." if killed else "Nothing matching was running.")
    print()

    repo_backup = None
    if keep_repos and _has_repos():
        repo_backup = _move_repos_to_safety()
        print(f"Moved your cloned repos to {repo_backup} before deleting the rest.")
        print()

    removed_from = [p for p in _candidate_profiles() if _strip_hook(p)]

    failures: list[str] = []

    if old_backups:
        print(f"Deleting {len(old_backups)} leftover repo backup folder(s) ...")
        for p in old_backups:
            failures.extend(fsutil.robust_rmtree(p))
        print()

    if home.exists():
        print(f"Deleting {home} ...")
        runlog.close_before_deleting_home()
        failures.extend(fsutil.robust_rmtree(home))

    print()
    if removed_from:
        print("Removed the seedling shell hook from:")
        for p in removed_from:
            print(f"  - {p}")
    else:
        print("No shell hook found in the usual profile locations.")
        print("(Nothing to clean up there, or it lives somewhere this command doesn't check.)")

    if failures and fsutil.failures_are_only_running_cli(failures, home):
        # The only survivors are seedling's own running program (the
        # seed-cli shim and the tool venv python executing this very
        # command) -- Windows can't delete a running executable, so hand
        # the last few files to a detached helper that runs after exit.
        fsutil.schedule_deferred_delete(home)
        print()
        print("The only files left are seedling's own running program, which")
        print("can't delete itself while it's still running. A background")
        print("cleanup removes them automatically a moment after this")
        print("command exits -- nothing more to do.")
        failures = []
    elif failures:
        print()
        print(colors.warn("Some files under seedling could not be removed after several attempts:"))
        for f in failures:
            print(f"  - {f}")
        print()
        print("These are usually held open by something outside Python/VS Code.")
        print("Close whatever has them open and run `seed purge` again.")
        return 1

    print()
    print(colors.ok("seedling has been fully uninstalled."))
    if repo_backup:
        print()
        print(f"Your cloned repos are safe at {repo_backup}.")
        print("Move them wherever you'd like -- seedling won't touch that folder again.")
    print()
    _print_reinstall(update_source)
    return 0
