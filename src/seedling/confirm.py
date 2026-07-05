"""
Centralized confirmation handling for every destructive command.

Three knobs, honored everywhere:

  - `-y`/`--yes` (or SEEDLING_YES=1) skips the prompt and proceeds.
  - `--non-interactive` (or SEEDLING_NONINTERACTIVE=1) means "never sit
    waiting for keyboard input": anything that would have prompted instead
    aborts safely, unless -y/SEEDLING_YES was also given. This is the mode
    for scripts/CI, where a forgotten prompt would otherwise hang forever.
  - `--preview` shows exactly what a destructive command WOULD do, then
    exits without touching anything (see preview_requested()).
"""

from __future__ import annotations

import os

from . import colors


def auto_confirmed(args) -> bool:
    if getattr(args, "yes", False):
        return True
    return os.environ.get("SEEDLING_YES") == "1"


def non_interactive(args) -> bool:
    if getattr(args, "non_interactive", False):
        return True
    return os.environ.get("SEEDLING_NONINTERACTIVE") == "1"


def confirm(args, prompt: str = "") -> bool:
    """Returns True if the action should proceed. `prompt` is optional
    because several commands print a multi-line explanation themselves and
    only need the final "Type 'yes'" line."""
    if auto_confirmed(args):
        return True
    if non_interactive(args):
        print("Non-interactive mode: refusing to prompt for confirmation. "
              "Pass -y/--yes (or set SEEDLING_YES=1) to proceed.")
        return False
    lead = f"{prompt} " if prompt else ""
    answer = input(f"{lead}Type 'yes' to confirm: ").strip().lower()
    return answer == "yes"


def preview_requested(args) -> bool:
    return getattr(args, "preview", False)


def print_preview(title: str, items: list[str], notes: list[str] | None = None) -> None:
    """Standard rendering for --preview: what would be deleted, and any
    side effects (like force-closing processes), with an explicit reminder
    that nothing has happened."""
    print(colors.header(f"Preview: {title}"))
    if items:
        for item in items:
            print(f"  - {item}")
    else:
        print("  (nothing)")
    for note in notes or []:
        print(colors.dim(f"  note: {note}"))
    print(colors.ok("Preview only -- nothing was changed.") +
          " Re-run without --preview to proceed.")
