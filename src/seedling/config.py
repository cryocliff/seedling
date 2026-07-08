from __future__ import annotations

import json
import os
from pathlib import Path
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
    "python_mirror": (
        "Where `seed python` downloads interpreter builds from, instead of "
        "the internet: a URL or a directory of python-build-standalone "
        "archives (e.g. a network share). Applied to every uv call as "
        "UV_PYTHON_INSTALL_MIRROR. Empty/null means the internet."),
    "package_index": (
        "Where packages install from, instead of pypi.org: an index URL "
        "(Artifactory/Nexus/devpi), or a plain directory of wheels (e.g. a "
        "network share -- becomes the one and only package source, with "
        "the internet index disabled). Empty/null means pypi.org."),
    "native_tls": (
        "Use the operating system's certificate trust store for HTTPS "
        "instead of the bundled one -- for internal mirrors/indexes whose "
        "corporate CA is installed machine-wide by IT. true/false."),
    "ca_cert": (
        "Path to a PEM CA bundle trusted for HTTPS (uv downloads, git "
        "clones, and seedling's own downloads). Normally installed "
        "automatically from vendor/certs/ in the distributed repo copy."),
}

_DEFAULTS: dict[str, Any] = {
    "default_base": None,
    "default_venv": None,
    "update_source": None,
    "venv_default_packages": ["ipython", "ruff", "ipykernel"],
    "python_mirror": None,
    "package_index": None,
    "native_tls": None,
    "ca_cert": None,
}


def apply_runtime_env() -> None:
    """Translate the TLS settings into THIS process's environment, once per
    invocation (cli calls it before dispatching any command). Process-wide
    rather than per-subprocess because three different consumers read the
    same variables: uv (child process), git (child process), and seedling's
    own urllib downloads (this process). Values already present in the
    user's environment always win."""
    ca_cert = get("ca_cert")
    if ca_cert and Path(str(ca_cert)).expanduser().is_file():
        os.environ.setdefault("SSL_CERT_FILE", str(ca_cert))
        os.environ.setdefault("GIT_SSL_CAINFO", str(ca_cert))
    if get("native_tls"):
        os.environ.setdefault("UV_NATIVE_TLS", "1")


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
