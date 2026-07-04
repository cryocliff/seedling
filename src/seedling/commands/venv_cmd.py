from __future__ import annotations

from .. import config, paths, uv_tool
from . import python_cmd


def _python_interpreter_path(base_dir):
    # uv's managed CPython layout: <base>/bin/python3 on unix, <base>/python.exe on windows
    import os

    if os.name == "nt":
        candidate = base_dir / "python.exe"
        if candidate.exists():
            return candidate
    candidate = base_dir / "bin" / "python3"
    if candidate.exists():
        return candidate
    candidate = base_dir / "bin" / "python"
    if candidate.exists():
        return candidate
    return None


def run(args) -> int:
    if not args.name:
        print("Usage: seed venv <name> [--python <tag>]")
        return 1

    paths.ensure_layout()

    tag = args.python or config.get_default_base()
    if tag is None:
        print("No base Python found. Install one first, e.g.:  seed python 312")
        return 1

    base_dir = python_cmd.resolve_base(tag)
    if base_dir is None:
        print(f"Base python '{tag}' isn't installed. Run:  seed python {tag}")
        return 1

    interpreter = _python_interpreter_path(base_dir)
    if interpreter is None:
        print(f"Could not find a python executable inside {base_dir}")
        return 1

    target = paths.venv_dir(args.name)
    if target.exists():
        print(f"A venv named '{args.name}' already exists at {target}")
        return 1

    print(f"Creating venv '{args.name}' from base '{tag}' -> {target}")
    uv_tool.run(["venv", "--python", str(interpreter), str(target)])

    print("Done.")
    print(f"Activate it with:  seed activate {args.name}")
    return 0
