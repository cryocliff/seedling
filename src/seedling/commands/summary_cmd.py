"""
`seed summary` -- one screen showing everything seedling has installed:
tooling, base Pythons, venvs, repos, VS Code, and the current settings.
Read-only. Pass --sizes to also compute per-section disk usage (walks the
whole tree, so it can take a few seconds on big installs).
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from .. import colors, config, git_tool, paths, uv_tool


def _dir_size(path: Path) -> int:
    total = 0
    for root, _dirs, files in os.walk(path, onerror=lambda e: None):
        for name in files:
            try:
                total += os.path.getsize(os.path.join(root, name))
            except OSError:
                pass
    return total


def _human(nbytes: int) -> str:
    size = float(nbytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
        size /= 1024
    return f"{size:.1f} TB"


def _size_suffix(path: Path, want_sizes: bool) -> str:
    if not want_sizes or not path.exists():
        return ""
    return colors.dim(f"  [{_human(_dir_size(path))}]")


def _uv_version() -> str:
    try:
        result = uv_tool.run_captured(["--version"], check=False)
        return result.stdout.strip() or "unknown"
    except uv_tool.UvNotFound:
        return colors.warn("NOT FOUND")


def _section(title: str) -> None:
    print()
    print(colors.header(title))


def run(args) -> int:
    want_sizes = getattr(args, "sizes", False)
    home = paths.HOME

    print(colors.bold("seedling summary") + f"  ({home})")
    if not home.exists():
        print("Nothing is installed yet -- run the installer first.")
        return 0

    _section("Tooling")
    print(f"  uv:      {_uv_version()}")
    git = git_tool.find_git()
    print(f"  git:     {git if git else colors.dim('not found (auto-downloaded on Windows when needed)')}")
    vscode_installed = paths.VSCODE_APP_DIR.exists() and any(paths.VSCODE_APP_DIR.iterdir())
    vscode_str = "installed" if vscode_installed else "not installed (run `seed vscode`)"
    print(f"  VS Code: {vscode_str}{_size_suffix(paths.VSCODE_DIR, want_sizes)}")

    _section(f"Base Pythons ({paths.BASE_DIR})")
    alias_files = sorted(paths.BASE_DIR.glob("*.alias.json")) if paths.BASE_DIR.exists() else []
    default_tag = config.get_default_base()
    if not alias_files:
        print("  none -- run: seed python <version>")
    for alias in alias_files:
        tag = alias.name[: -len(".alias.json")]
        try:
            target = json.loads(alias.read_text())["target"]
        except (json.JSONDecodeError, KeyError, OSError):
            target = "?"
        resolved = paths.BASE_DIR / target
        marker = "  (default)" if tag == default_tag else ""
        missing = "" if resolved.exists() else colors.warn("  [missing!]")
        print(f"  {tag:<8} -> {target}{marker}{missing}"
              f"{_size_suffix(resolved, want_sizes)}")

    _section(f"Venvs ({paths.VENVS_DIR})")
    venvs = (sorted(d for d in paths.VENVS_DIR.iterdir() if d.is_dir())
             if paths.VENVS_DIR.exists() else [])
    if not venvs:
        print("  none -- run: seed venv <name>")
    active = os.environ.get("VIRTUAL_ENV")
    active_resolved = os.path.abspath(active) if active else None
    default_venv = config.get("default_venv")
    for v in venvs:
        version = ""
        cfg = v / "pyvenv.cfg"
        if cfg.exists():
            try:
                for line in cfg.read_text().splitlines():
                    if line.strip().lower().startswith("version"):
                        version = f"  [python {line.split('=', 1)[1].strip()}]"
                        break
            except OSError:
                pass
        markers = ""
        if active_resolved and os.path.abspath(str(v)) == active_resolved:
            markers += "  (active)"
        if v.name == default_venv:
            markers += "  (auto-activated in new shells)"
        print(f"  {v.name}{version}{markers}{_size_suffix(v, want_sizes)}")

    _section(f"Repos ({paths.REPO_DIR})")
    repos = (sorted(d for d in paths.REPO_DIR.iterdir() if d.is_dir())
             if paths.REPO_DIR.exists() else [])
    if not repos:
        print("  none -- run: seed repo-clone <git-url>")
    for r in repos:
        remote = ""
        if git and (r / ".git").exists():
            result = subprocess.run(
                [git, "-C", str(r), "remote", "get-url", "origin"],
                capture_output=True, text=True,
            )
            remote = result.stdout.strip()
        suffix = colors.dim(f"  -> {remote}") if remote else ""
        print(f"  {r.name}{suffix}{_size_suffix(r, want_sizes)}")

    _section("Settings")
    data = config.load()
    for key in config.KNOWN_KEYS:
        value = data.get(key)
        if isinstance(value, list):
            shown = ", ".join(str(x) for x in value)
        elif value is None:
            shown = colors.dim("(not set)")
        else:
            shown = str(value)
        print(f"  {key} = {shown}")
    print(colors.dim("  change with: seed config set <key> <value>"))

    if want_sizes:
        _section("Total")
        print(f"  {home}: {_human(_dir_size(home))}")
    else:
        print()
        print(colors.dim("Tip: `seed summary --sizes` adds disk usage per item."))
    return 0
