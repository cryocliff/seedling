from __future__ import annotations

import json
import os

from .. import config, paths


def _read_venv_python_version(venv_dir) -> str | None:
    """Best-effort read of the Python version a venv was created with,
    straight out of its pyvenv.cfg."""
    cfg = venv_dir / "pyvenv.cfg"
    if not cfg.exists():
        return None
    try:
        for line in cfg.read_text().splitlines():
            if line.strip().lower().startswith("version"):
                return line.split("=", 1)[1].strip()
    except OSError:
        pass
    return None


def list_python(args) -> int:
    if not paths.BASE_DIR.exists():
        print("No base Python interpreters installed yet. Run: seed python <version>")
        return 0

    alias_files = sorted(paths.BASE_DIR.glob("*.alias.json"))
    if not alias_files:
        print("No base Python interpreters installed yet. Run: seed python <version>")
        return 0

    default_tag = config.get_default_base()

    print(f"Base Python interpreters in {paths.BASE_DIR}:")
    for alias in alias_files:
        tag = alias.name[: -len(".alias.json")]
        try:
            target = json.loads(alias.read_text())["target"]
        except (json.JSONDecodeError, KeyError, OSError):
            target = "?"

        resolved = paths.BASE_DIR / target
        marker = "  (default for `seed venv`)" if tag == default_tag else ""
        missing = "" if resolved.exists() else f"  [missing! re-run: seed python {tag}]"
        print(f"  {tag:<8} -> {target}{marker}{missing}")

    return 0


def list_venvs(args) -> int:
    if not paths.VENVS_DIR.exists():
        print("No venvs created yet. Run: seed venv <name>")
        return 0

    venvs = sorted(d for d in paths.VENVS_DIR.iterdir() if d.is_dir())
    if not venvs:
        print("No venvs created yet. Run: seed venv <name>")
        return 0

    active = os.environ.get("VIRTUAL_ENV")
    active_resolved = os.path.abspath(active) if active else None

    print(f"Venvs in {paths.VENVS_DIR}:")
    for v in venvs:
        version = _read_venv_python_version(v)
        version_str = f"  [python {version}]" if version else ""
        marker = "  (active)" if active_resolved and os.path.abspath(str(v)) == active_resolved else ""
        print(f"  {v.name}{version_str}{marker}")

    return 0
