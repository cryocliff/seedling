"""
`seed venv-default [name]` -- show or set the venv every new shell
auto-activates. Sugar for `seed config get/set default_venv`, promoted to
its own command because it's the setting people actually reach for (the
installer points the default at 'dev'; switching it to your real project
is a natural next step).
"""

from __future__ import annotations

from .. import colors, config, paths


def run(args) -> int:
    name = getattr(args, "name", None)

    if not name:
        current = config.get("default_venv")
        if current:
            print(f"New shells auto-activate: {current}")
        else:
            print("No default venv is set; new shells start with no venv active.")
        print("Set one with:  seed venv-default <name>   "
              "(clear with: seed config unset default_venv)")
        return 0

    if not paths.venv_dir(name).exists():
        print(f"No venv named '{name}' found in {paths.VENVS_DIR}")
        print(f"Create it first with:  seed venv {name}")
        return 1

    config.set_value("default_venv", name)
    print(colors.ok(f"Done. New shells will auto-activate '{name}'."))
    print("(Existing shells are unaffected -- open a new terminal, or run "
          f"`seed activate {name}` here.)")
    return 0
