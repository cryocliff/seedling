"""
Shared, defensive directory deletion, used everywhere seedling deletes a
directory tree (remove-venv(s), remove-python, remove-repo, remove-user,
purge).

Plain `shutil.rmtree(path, ignore_errors=True)` has two real failure modes
this works around:

1. Windows refuses to delete a directory that is any running process's
   current working directory -- including the calling process itself. If
   the terminal that ran `seed remove-user`/`seed purge` happens to have its
   cwd inside the tree being deleted (a common case: someone `cd`s into a
   project under a venv/repo, activates it, then runs the remove command
   from right there), deletion of that specific directory silently fails
   and `ignore_errors=True` hides it -- which matches the reported "unable
   to delete some file if a venv is activated" symptom.
2. A process we just force-killed (see kill_cmd) may not release its file
   handles instantly; deleting immediately can race that.

This retries with a short backoff and actually reports which paths, if
any, are still stuck after all attempts, instead of swallowing everything.
"""

from __future__ import annotations

import os
import shutil
import time
from pathlib import Path


def robust_rmtree(path: Path, retries: int = 3, delay: float = 0.75) -> list[str]:
    """Delete a directory tree. Returns a list of paths that still
    couldn't be removed after all retries (empty on full success)."""
    path = Path(path)
    if not path.exists():
        return []

    _escape_if_inside(path)

    failures: list[str] = []
    for attempt in range(retries):
        failures = []

        def _on_error(_func, failed_path, _exc_info):
            failures.append(str(failed_path))

        shutil.rmtree(path, onerror=_on_error)
        if not path.exists() and not failures:
            return []
        if attempt < retries - 1:
            time.sleep(delay)

    return failures


def _escape_if_inside(path: Path) -> None:
    """If the current process's cwd is inside (or is) `path`, move out of
    it first -- otherwise Windows will refuse to delete that directory."""
    safe = str(Path.home())
    try:
        current = Path.cwd().resolve()
    except OSError:
        # cwd is already invalid for some reason; just try to land somewhere sane
        try:
            os.chdir(safe)
        except OSError:
            pass
        return

    resolved_target = path.resolve()
    if current == resolved_target or resolved_target in current.parents:
        try:
            os.chdir(safe)
        except OSError:
            pass
