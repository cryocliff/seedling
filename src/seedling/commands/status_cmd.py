"""
`seed status` -- the health check. Verifies every moving part seedling
depends on and reports OK / WARN / FAIL per check. Exit code 0 when nothing
FAILed (warnings are informational), 1 otherwise.

WARN vs FAIL: FAIL means a core seedling operation would not work right now
(missing uv, broken venv, unreadable config). WARN means something is off
but degradable (no git yet, no shell hook found in the usual profiles).
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

from .. import colors, config, git_tool, paths, uv_tool

_failures = 0
_warnings = 0


def _ok(msg: str) -> None:
    print(f"  {colors.ok('OK')}    {msg}")


def _warn(msg: str) -> None:
    global _warnings
    _warnings += 1
    print(f"  {colors.warn('WARN')}  {msg}")


def _fail(msg: str) -> None:
    global _failures
    _failures += 1
    print(f"  {colors.danger('FAIL')}  {msg}")


def _check_uv() -> None:
    try:
        uv = uv_tool.find_uv()
    except uv_tool.UvNotFound:
        _fail("uv not found in ~/seedling/system/bin or on PATH -- re-run the installer")
        return
    result = subprocess.run([str(uv), "--version"], capture_output=True, text=True, check=False)
    if result.returncode == 0:
        _ok(f"uv runs ({result.stdout.strip()}) at {uv}")
    else:
        _fail(f"uv exists at {uv} but won't run (exit {result.returncode})")


def _check_git() -> None:
    git = git_tool.find_git()
    if git:
        _ok(f"git available at {git}")
    else:
        _warn("git not found (Windows: auto-downloaded on first `seed clone-repo`; "
              "macOS/Linux: install it with your package manager)")


def _check_config() -> None:
    if not paths.CONFIG_FILE.exists():
        _ok("config not written yet (defaults in effect)")
        return
    try:
        json.loads(paths.CONFIG_FILE.read_text())
        _ok(f"config parses ({paths.CONFIG_FILE})")
    except (json.JSONDecodeError, OSError) as e:
        _fail(f"config file is unreadable/corrupt: {e} -- fix or delete {paths.CONFIG_FILE}")


def _check_base_pythons() -> None:
    alias_files = sorted(paths.BASE_DIR.glob("*.alias.json")) if paths.BASE_DIR.exists() else []
    if not alias_files:
        _warn("no base Pythons installed yet (run `seed python <version>`)")
        return
    for alias in alias_files:
        tag = alias.name[: -len(".alias.json")]
        try:
            target = json.loads(alias.read_text())["target"]
        except (json.JSONDecodeError, KeyError, OSError):
            _fail(f"base '{tag}': alias file is corrupt -- re-run `seed python {tag}`")
            continue
        base_dir = paths.BASE_DIR / target
        if not base_dir.exists():
            _fail(f"base '{tag}': points at {target}, which is missing -- "
                  f"re-run `seed python {tag}`")
            continue
        exe = (base_dir / "python.exe") if os.name == "nt" else (base_dir / "bin" / "python3")
        if exe.exists():
            _ok(f"base Python '{tag}' -> {target}")
        else:
            _fail(f"base '{tag}': directory exists but no interpreter found inside {base_dir}")


def _check_venvs() -> None:
    venvs = (sorted(d for d in paths.VENVS_DIR.iterdir() if d.is_dir())
             if paths.VENVS_DIR.exists() else [])
    if not venvs:
        _warn("no venvs created yet (run `seed venv <name>`)")
        return
    for v in venvs:
        exe = (v / "Scripts" / "python.exe") if os.name == "nt" else (v / "bin" / "python")
        if not exe.exists():
            _fail(f"venv '{v.name}': no interpreter at {exe} -- recreate it")
            continue
        # A venv silently breaks if the base Python it links to is deleted.
        cfg = v / "pyvenv.cfg"
        home_line = None
        try:
            for line in cfg.read_text().splitlines():
                if line.strip().lower().startswith("home"):
                    home_line = line.split("=", 1)[1].strip()
                    break
        except OSError:
            pass
        if home_line and not Path(home_line).exists():
            _fail(f"venv '{v.name}': its base Python ({home_line}) is gone -- recreate the venv")
        else:
            _ok(f"venv '{v.name}'")


def _check_defaults() -> None:
    default_base = config.get_default_base()
    if default_base and not paths.base_alias_file(default_base).exists():
        _fail(f"config default_base '{default_base}' isn't installed -- "
              f"`seed python {default_base}` or `seed config set default_base <tag>`")
    elif default_base:
        _ok(f"default_base '{default_base}' is installed")

    default_venv = config.get("default_venv")
    if default_venv and not paths.venv_dir(default_venv).exists():
        _fail(f"config default_venv '{default_venv}' doesn't exist -- new shells "
              "will fail to auto-activate it")
    elif default_venv:
        _ok(f"default_venv '{default_venv}' exists")

    update_source = config.get("update_source")
    if update_source:
        source = Path(str(update_source)).expanduser()
        if source.is_dir() and not (source / "src" / "pyproject.toml").exists():
            _warn(f"update_source directory {source} has no src/pyproject.toml -- "
                  "`seed update-commands` will refuse it")
        elif source.is_dir():
            _ok(f"update_source directory {source} looks usable")
        else:
            _ok(f"update_source is set to {update_source} (assumed git URL; "
                "not checked over the network)")
    else:
        _warn("no update_source recorded -- `seed update-commands` can only "
              "reinstall the existing copy, not fetch newer versions; set one "
              "with `seed config set update_source <git-url-or-directory>`")

    ca_cert = config.get("ca_cert")
    if ca_cert:
        if Path(str(ca_cert)).expanduser().is_file():
            _ok(f"ca_cert bundle exists ({ca_cert})")
        else:
            _fail(f"config ca_cert file {ca_cert} doesn't exist -- HTTPS to "
                  "your internal hosts will fail certificate verification; "
                  "re-run the installer (which rebuilds the bundle from "
                  "vendor/certs) or `seed config unset ca_cert`")

    # Offline sources: a directory-path value that doesn't exist means the
    # next `seed python`/`seed install` fails with an obscure uv error.
    for key in ("python_mirror", "package_index"):
        value = config.get(key)
        if not value or "://" in str(value):
            continue  # unset, or a URL we can't cheaply verify
        if Path(str(value)).expanduser().is_dir():
            _ok(f"{key} directory {value} exists")
        else:
            _fail(f"config {key} directory {value} doesn't exist -- installs "
                  "that need it will fail; fix it or `seed config unset "
                  f"{key}`")


_HOOK_PATH_RE = re.compile(r'["\']([^"\']*seed\.(?:ps1|sh))["\']')


def _check_shell_hook() -> None:
    profiles = [
        Path.home() / ".zshrc",
        Path.home() / ".bashrc",
        Path.home() / ".bash_profile",
        Path.home() / ".profile",
        Path.home() / "Documents" / "PowerShell" / "Microsoft.PowerShell_profile.ps1",
        Path.home() / "Documents" / "WindowsPowerShell" / "Microsoft.PowerShell_profile.ps1",
    ]
    home_str = str(paths.HOME)
    found_working = False
    for profile in profiles:
        if not profile.exists():
            continue
        try:
            text = profile.read_text()
        except OSError:
            continue
        for line in text.splitlines():
            if home_str not in line:
                continue
            if "seed.ps1" not in line and "seed.sh" not in line:
                continue
            match = _HOOK_PATH_RE.search(line)
            target = Path(match.group(1)) if match else None
            if target is not None and target.exists():
                found_working = True
                _ok(f"shell hook installed in {profile}")
            else:
                # A hook pointing at a deleted file (e.g. left behind by an
                # old seedling layout) makes every new shell print an error.
                _warn(f"stale seedling hook in {profile}: `{line.strip()}` "
                      "points at a file that doesn't exist -- every new "
                      "shell will print an error until that line is removed "
                      "(re-running the installer cleans it up)")
    if not found_working:
        _warn("no working `seed` shell hook found in the usual shell profiles "
              "-- `seed activate` won't affect your shell; re-run the "
              "installer if so")


def _check_logs_writable() -> None:
    try:
        paths.LOGS_DIR.mkdir(parents=True, exist_ok=True)
        probe = paths.LOGS_DIR / ".write-probe"
        probe.write_text("ok")
        probe.unlink()
        _ok(f"log directory writable ({paths.LOGS_DIR})")
    except OSError as e:
        _warn(f"log directory not writable ({e}) -- commands still work, just unlogged")


def run(args) -> int:
    global _failures, _warnings
    _failures = 0
    _warnings = 0

    print(colors.bold("seedling health check") + f"  ({paths.HOME})")
    print()
    _check_uv()
    _check_git()
    _check_config()
    _check_base_pythons()
    _check_venvs()
    _check_defaults()
    _check_shell_hook()
    _check_logs_writable()

    print()
    if _failures:
        print(colors.danger(f"{_failures} problem(s) found") +
              (f", {_warnings} warning(s)." if _warnings else "."))
        return 1
    if _warnings:
        print(colors.warn(f"Healthy, with {_warnings} warning(s)."))
    else:
        print(colors.ok("Everything looks healthy."))
    return 0
