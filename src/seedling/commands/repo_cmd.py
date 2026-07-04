from __future__ import annotations

import os
import shutil
import subprocess

from .. import paths, uv_tool
from . import kill_cmd, vscode_cmd


def _derive_name(url: str) -> str:
    """Best-effort repo-name extraction from any common git URL shape:
    https://host/group/name.git, git@host:group/name.git, ./local/path, etc."""
    name = url.rstrip("/")
    if name.endswith(".git"):
        name = name[: -len(".git")]
    name = name.split("/")[-1]
    name = name.split(":")[-1]  # scp-style git@host:group/name
    return name or "repo"


def clone(args) -> int:
    url = getattr(args, "url", None)
    if not url:
        print("Usage: seed clone-repo <git-url>")
        return 1

    if shutil.which("git") is None:
        print("git is required for `seed clone-repo`, but wasn't found on PATH.")
        return 1

    name = _derive_name(url)
    target = paths.repo_dir(name)
    if target.exists():
        print(f"'{name}' already exists at {target}.")
        print(f"Run `seed remove-repo {name}` first if you want to re-clone it.")
        return 1

    paths.REPO_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Cloning {url} -> {target} ...")
    result = subprocess.run(["git", "clone", url, str(target)])
    if result.returncode != 0:
        print("git clone failed.")
        return 1

    print(f"Cloned '{name}'.")
    print(f"  seed open-repo {name}      # open it in VS Code")
    print(f"  seed install-repo {name}   # install its dependencies into the active venv")
    return 0


def list_repos(args) -> int:
    if not paths.REPO_DIR.exists() or not any(paths.REPO_DIR.iterdir()):
        print("No repos cloned yet. Run: seed clone-repo <git-url>")
        return 0

    repos = sorted(d for d in paths.REPO_DIR.iterdir() if d.is_dir())
    if not repos:
        print("No repos cloned yet. Run: seed clone-repo <git-url>")
        return 0

    have_git = shutil.which("git") is not None
    print(f"Repos in {paths.REPO_DIR}:")
    for r in repos:
        remote = ""
        if have_git and (r / ".git").exists():
            result = subprocess.run(
                ["git", "-C", str(r), "remote", "get-url", "origin"],
                capture_output=True, text=True,
            )
            remote = result.stdout.strip()
        suffix = f"  -> {remote}" if remote else ""
        print(f"  {r.name}{suffix}")
    return 0


def remove(args) -> int:
    name = getattr(args, "name", None)
    if not name:
        print("Usage: seed remove-repo <name>")
        return 1

    target = paths.repo_dir(name)
    if not target.exists():
        print(f"No repo named '{name}' found in {paths.REPO_DIR}")
        return 1

    if not getattr(args, "yes", False):
        answer = input(
            f"Delete repo '{name}' at {target}? This will also force-close "
            "any running Python/VS Code processes first (not just "
            "seedling's). Type 'yes' to confirm: "
        ).strip().lower()
        if answer != "yes":
            print("Aborted. Nothing was deleted.")
            return 1

    print("Closing Python and VS Code processes so nothing is left in use...")
    killed = kill_cmd.kill_python_and_vscode()
    print(f"Closed {len(killed)} process(es)." if killed else "Nothing matching was running.")

    shutil.rmtree(target, ignore_errors=True)
    print(f"Deleted repo '{name}'.")
    return 0


def open_repo(args) -> int:
    name = getattr(args, "name", None)
    if not name:
        print("Usage: seed open-repo <name>")
        return 1

    target = paths.repo_dir(name)
    if not target.exists():
        print(f"No repo named '{name}' found in {paths.REPO_DIR}")
        return 1

    cli = vscode_cmd.install(force=False)
    if cli is None:
        print("Could not find any way to launch VS Code after installing it.")
        return 1

    print(f"Opening VS Code -> {target}")
    vscode_cmd.open_window(cli, str(target))
    return 0


def install_repo(args) -> int:
    name = getattr(args, "name", None)
    if not name:
        print("Usage: seed install-repo <name>")
        return 1

    target = paths.repo_dir(name)
    if not target.exists():
        print(f"No repo named '{name}' found in {paths.REPO_DIR}")
        return 1

    if not os.environ.get("VIRTUAL_ENV"):
        print("Note: no venv looks active (VIRTUAL_ENV isn't set). "
              "Run `seed activate <name>` first, or uv will fall back to "
              "whatever it can find (e.g. a .venv in the current directory).")

    pyproject = target / "pyproject.toml"
    requirements = target / "requirements.txt"

    if pyproject.exists():
        print(f"Installing '{name}' (editable) via `uv pip install -e` ...")
        uv_tool.run(["pip", "install", "-e", str(target)])
    elif requirements.exists():
        print(f"Installing dependencies from {requirements} ...")
        uv_tool.run(["pip", "install", "-r", str(requirements)])
    else:
        print(f"Nothing to install: no pyproject.toml or requirements.txt found in {target}.")
        return 1

    return 0
