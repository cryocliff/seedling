from __future__ import annotations

import argparse
import subprocess
import sys

from . import paths
from .commands import (
    activate_cmd,
    deactivate_cmd,
    install_cmd,
    kill_cmd,
    list_cmd,
    purge_cmd,
    python_cmd,
    python_remove_cmd,
    remove_cmd,
    repo_cmd,
    uninstall_cmd,
    update_cmd,
    venv_cmd,
    venv_remove_cmd,
    vscode_cmd,
)
from .uv_tool import UvNotFound


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="seed",
        description="seedling: a tidy, single-folder wrapper around uv for "
                     "getting started with Python.",
    )
    sub = parser.add_subparsers(dest="command")

    p_python = sub.add_parser("python", help="Install a base Python version")
    p_python.add_argument("version", nargs="?", help="e.g. 312, 3.12, 3.12.4")

    p_remove_python = sub.add_parser(
        "remove-python", help="Remove a base Python and any venvs built from it")
    p_remove_python.add_argument("tag", nargs="?", help="e.g. 312")
    p_remove_python.add_argument("-y", "--yes", action="store_true",
                                  help="Skip the confirmation prompt")

    p_venv = sub.add_parser("venv", help="Create a venv from a base Python")
    p_venv.add_argument("name", nargs="?", help="Name of the venv to create")
    p_venv.add_argument("--python", dest="python", default=None,
                         help="Base python tag to build from (defaults to "
                              "the first one installed)")

    sub.add_parser("list-venvs", help="List every venv seedling has created")
    sub.add_parser("list-python", help="List every base Python interpreter installed")

    p_activate = sub.add_parser("activate", help="Activate a venv")
    p_activate.add_argument("name", nargs="?", help="Name of the venv to activate")
    p_activate.add_argument("--print-path", dest="print_path", action="store_true",
                             help=argparse.SUPPRESS)  # used internally by the shell wrapper

    sub.add_parser("deactivate", help="Deactivate the current venv")

    p_install = sub.add_parser(
        "install", help="Install packages into the active venv (passthrough to `uv pip install`)")
    p_install.add_argument("packages", nargs=argparse.REMAINDER,
                            help="Anything after this is passed straight to `uv pip install`")

    p_uninstall = sub.add_parser(
        "uninstall", help="Uninstall packages from the active venv (passthrough to `uv pip uninstall`)")
    p_uninstall.add_argument("packages", nargs=argparse.REMAINDER,
                              help="Anything after this is passed straight to `uv pip uninstall`")

    p_list_packages = sub.add_parser(
        "list-packages", help="List packages in the active venv (passthrough to `uv pip list`)")
    p_list_packages.add_argument("extra", nargs=argparse.REMAINDER,
                                  help="Anything after this is passed straight to `uv pip list`")

    p_vscode = sub.add_parser("vscode", help="Install (if needed) and open VS Code")
    p_vscode.add_argument("path", nargs="?", help="Path to open (defaults to cwd)")
    p_vscode.add_argument("--reinstall", action="store_true",
                           help="Force a fresh VS Code install")

    p_clone_repo = sub.add_parser(
        "clone-repo", help="Clone a git repo into ~/seedling/repo")
    p_clone_repo.add_argument("url", nargs="?", help="Git URL to clone")

    sub.add_parser("list-repos", help="List every repo cloned with `seed clone-repo`")

    p_remove_repo = sub.add_parser("remove-repo", help="Delete a cloned repo")
    p_remove_repo.add_argument("name", nargs="?", help="Name of the repo to delete")
    p_remove_repo.add_argument("-y", "--yes", action="store_true",
                                help="Skip the confirmation prompt")

    p_open_repo = sub.add_parser("open-repo", help="Open a cloned repo in VS Code")
    p_open_repo.add_argument("name", nargs="?", help="Name of the repo to open")

    p_install_repo = sub.add_parser(
        "install-repo",
        help="Install a cloned repo's dependencies into the active venv")
    p_install_repo.add_argument("name", nargs="?", help="Name of the repo to install")

    p_remove = sub.add_parser("remove-user", help="Delete everything seedling manages")
    p_remove.add_argument("-y", "--yes", action="store_true",
                          help="Skip the confirmation prompt")

    p_remove_venvs = sub.add_parser("remove-venvs", help="Delete every venv seedling has created")
    p_remove_venvs.add_argument("-y", "--yes", action="store_true",
                                help="Skip the confirmation prompt")

    p_remove_venv = sub.add_parser("remove-venv", help="Delete a single venv")
    p_remove_venv.add_argument("name", nargs="?", help="Name of the venv to delete")
    p_remove_venv.add_argument("-y", "--yes", action="store_true",
                               help="Skip the confirmation prompt")

    p_purge = sub.add_parser(
        "purge", help="Fully uninstall seedling: delete everything AND remove the shell hook")
    p_purge.add_argument("-y", "--yes", action="store_true",
                          help="Skip the confirmation prompt")

    p_kill = sub.add_parser(
        "kill-processes", help="Force-close processes by name, or 'all' for python + VS Code")
    p_kill.add_argument("target", nargs="?",
                         help="'all' for python/VS Code processes, or a specific process name")
    p_kill.add_argument("-y", "--yes", action="store_true",
                         help="Skip the confirmation prompt")

    sub.add_parser("update-commands",
                    help="Update the seed CLI itself from its source in ~/seedling/system/src")

    sub.add_parser("where", help="Print the seedling home directory")

    return parser


def main(argv=None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    parser = build_parser()
    args = parser.parse_args(argv)

    paths.ensure_layout()

    dispatch = {
        "python": python_cmd.run,
        "remove-python": python_remove_cmd.run,
        "venv": venv_cmd.run,
        "list-venvs": list_cmd.list_venvs,
        "list-python": list_cmd.list_python,
        "activate": activate_cmd.run,
        "deactivate": deactivate_cmd.run,
        "install": install_cmd.run,
        "uninstall": uninstall_cmd.run,
        "list-packages": list_cmd.list_packages,
        "vscode": vscode_cmd.run,
        "clone-repo": repo_cmd.clone,
        "list-repos": repo_cmd.list_repos,
        "remove-repo": repo_cmd.remove,
        "open-repo": repo_cmd.open_repo,
        "install-repo": repo_cmd.install_repo,
        "remove-user": remove_cmd.run,
        "remove-venvs": venv_remove_cmd.run_all,
        "remove-venv": venv_remove_cmd.run_one,
        "purge": purge_cmd.run,
        "kill-processes": kill_cmd.run,
        "update-commands": update_cmd.run,
    }

    if args.command == "where":
        print(paths.HOME)
        return 0

    handler = dispatch.get(args.command)
    if handler is None:
        parser.print_help()
        return 0 if args.command is None else 1

    try:
        return handler(args)
    except UvNotFound as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    except subprocess.CalledProcessError as e:
        print(f"error: `{' '.join(str(a) for a in e.cmd)}` failed "
              f"(exit code {e.returncode})", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nCancelled.")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
