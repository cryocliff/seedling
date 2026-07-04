from __future__ import annotations


def run(args) -> int:
    # The real work happens in the `seed` shell function, which intercepts
    # `deactivate` before it ever gets here and calls the shell's own
    # `deactivate` function/command (the one venv's activate script defines).
    # A subprocess has no way to affect the parent shell's environment, so if
    # we're running here it means seed-cli was invoked directly rather than
    # through the shell function.
    print(
        "This only works when 'seed' is the shell function installed by the "
        "seedling installer (it's what lets deactivation affect your current "
        "shell). If you're seeing this, re-run the installer or open a new "
        "terminal, then run:  seed deactivate"
    )
    return 0
