from __future__ import annotations

import json
from typing import Any

from . import paths

_DEFAULTS: dict[str, Any] = {
    "default_base": None,  # tag of the base python `venv` should use by default, e.g. "312"
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


def set_default_base(tag: str) -> None:
    data = load()
    data["default_base"] = tag
    save(data)


def get_default_base() -> str | None:
    return load().get("default_base")
