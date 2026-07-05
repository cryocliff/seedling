from __future__ import annotations

import json
import re

from .. import colors, config, paths, uv_tool


def _normalize_tag(raw: str) -> tuple[str, str]:
    """'312' -> ('312', '3.12'); '3.12' -> ('312', '3.12'); '3.12.4' -> ('3124', '3.12.4')"""
    digits = re.sub(r"[^0-9]", "", raw)
    if "." in raw:
        version_spec = raw
    elif len(digits) >= 2:
        version_spec = f"{digits[0]}.{digits[1:]}"
    else:
        version_spec = raw
    tag = digits
    return tag, version_spec


def find_installed_dir(tag: str, version_spec: str):
    """After `uv python install`, find the real directory uv created."""
    if not paths.BASE_DIR.exists():
        return None
    prefix_variants = [f"cpython-{version_spec}", f"cpython-{version_spec}."]
    candidates = []
    for entry in paths.BASE_DIR.iterdir():
        if not entry.is_dir():
            continue
        if any(entry.name.startswith(p) for p in prefix_variants):
            candidates.append(entry)
    if not candidates:
        return None
    # prefer the most specific / most recently created
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0]


def write_alias(tag: str, target_dir_name: str) -> None:
    paths.base_alias_file(tag).write_text(json.dumps({"target": target_dir_name}))


def resolve_base(tag: str):
    """Resolve a short tag like '312' to the actual install directory."""
    alias = paths.base_alias_file(tag)
    if alias.exists():
        try:
            target = json.loads(alias.read_text())["target"]
            resolved = paths.BASE_DIR / target
            if resolved.exists():
                return resolved
        except (json.JSONDecodeError, KeyError, OSError):
            pass
    direct = paths.base_python_dir(tag)
    if direct.exists():
        return direct
    return None


def run(args) -> int:
    if not args.version:
        print("Usage: seed python <version>   e.g. seed python 312")
        return 1

    tag, version_spec = _normalize_tag(args.version)
    paths.ensure_layout()

    print(f"Installing Python {version_spec} into {paths.base_python_dir(tag)} ...")
    uv_tool.run(
        ["python", "install", version_spec],
        env=uv_tool.python_install_dir_env(),
    )

    installed = find_installed_dir(tag, version_spec)
    if installed is None:
        print("uv reported success but seedling could not locate the installed "
              "interpreter directory under python/base/. Check `uv python list`.")
        return 1

    write_alias(tag, installed.name)

    # First base python installed becomes the default used by `seed venv`.
    if config.get_default_base() is None:
        config.set_default_base(tag)

    print(colors.ok(f"Done. Python {version_spec} is available as base '{tag}'") +
          f" (-> {installed.name}).")
    print(f"Create a venv from it with:  seed venv <name>")
    return 0
