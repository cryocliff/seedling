from __future__ import annotations

import json
from typing import Any

from . import paths

# Every key seedling understands, with a description shown by `seed config`.
# Anything else in settings.json is preserved but flagged as unknown.
KNOWN_KEYS: dict[str, str] = {
    "default_base": (
        "Base Python tag `seed venv` builds from when --python isn't given "
        "(e.g. \"312\"). Set automatically by the first `seed python` install."),
    "default_venv": (
        "Venv name every new shell auto-activates on startup. Empty/null "
        "means no auto-activation."),
    "update_source": (
        "Where `seed update-commands` fetches seedling's own source from: a "
        "git URL (including self-hosted GitHub/GitLab on another network) "
        "OR a plain directory path (e.g. a mounted network drive holding a "
        "copy of the repo). Recorded automatically at install time. "
        "Empty/null means updates can only reinstall the existing copy."),
    "venv_default_packages": (
        "Packages installed into every new venv (list). Skip per-venv with "
        "`seed venv <name> --no-default-packages`."),
}

_DEFAULTS: dict[str, Any] = {
    "default_base": None,
    "default_venv": None,
    "update_source": None,
    "venv_default_packages": ["ipython", "ruff"],
}


def load() -> dict[str, Any]:
    paths.ensure_layout()
    if not paths.CONFIG_FILE.exists():
        return dict(_DEFAULTS)
    try:
        data = json.loads(paths.CONFIG_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        data = {}
    merged = dict(_DEFAULTS)
    merged.update(data)
    return merged


def save(data: dict[str, Any]) -> None:
    paths.ensure_layout()
    paths.CONFIG_FILE.write_text(json.dumps(data, indent=2, sort_keys=True))


def get(key: str) -> Any:
    return load().get(key)


def set_value(key: str, value: Any) -> None:
    data = load()
    data[key] = value
    save(data)


def unset(key: str) -> None:
    """Reset a key back to its built-in default."""
    data = load()
    data[key] = _DEFAULTS.get(key)
    save(data)


def default_of(key: str) -> Any:
    return _DEFAULTS.get(key)


def set_default_base(tag: str) -> None:
    set_value("default_base", tag)


def get_default_base() -> str | None:
    return load().get("default_base")
