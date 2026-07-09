"""CLI-level behavior of the non-destructive commands: help layout,
dispatch completeness, list/empty states, venv-default, config, status,
summary, python-cmd helpers."""

from __future__ import annotations

import json

import pytest

from conftest import make_base_python, make_venv_dirs
from seedling import config, paths
from seedling.commands import python_cmd

ALL_COMMANDS = [
    "python", "python-list", "python-remove",
    "venv", "venv-list", "venv-remove", "venv-remove-all", "venv-default",
    "activate", "deactivate", "install", "uninstall", "package-list",
    "repo-clone", "repo-list", "repo-cd", "repo-vscode", "repo-open",
    "repo-install", "repo-remove",
    "vscode", "summary", "status", "config", "where",
    "kill-processes", "update-commands", "remove-user", "purge",
]

# handled specially in _dispatch_main rather than via the dispatch table
_NON_DISPATCH = {"where", "help"}

ADMIN_COMMANDS = [
    "admin-purge-all-users", "admin-remove-user", "admin-venv-remove",
    "admin-venv-remove-all", "admin-python-remove", "admin-repo-remove",
]


def test_every_command_is_dispatchable(home):
    """Guards against a rename touching the parser but not the dispatch
    table (or vice versa) -- admin family included."""
    from seedling import cli
    parser = cli.build_parser()
    subparsers = next(
        a for a in parser._actions
        if a.__class__.__name__ == "_SubParsersAction")
    parser_names = set(subparsers.choices)
    assert parser_names == set(ALL_COMMANDS) | set(ADMIN_COMMANDS) | _NON_DISPATCH


def test_bare_seed_shows_grouped_help(run_cli):
    code, out = run_cli()
    assert code == 0
    for family_member in ("python-list", "venv-remove-all", "repo-clone",
                          "repo-vscode", "venv-default", "package-list"):
        assert family_member in out


def test_help_hides_admin_note_on_single_user(run_cli, home):
    from seedling import config
    assert config.is_multi_user() is False
    code, out = run_cli("help")
    assert "multi-user" not in out  # no admin note on a plain install
    assert "admin-" not in out


def test_help_shows_admin_note_only_when_multi_user(run_cli, home):
    from seedling import config
    config.set_value("shared_root", r"C:\seedling")   # valid JSON via json.dumps
    assert config.is_multi_user() is True
    code, out = run_cli("help")
    assert "shared multi-user install" in out
    assert "seed help --admin" in out


def test_summary_shows_install_type(run_cli, home):
    from seedling import config
    code, out = run_cli("summary")
    assert "install type: single-user" in out
    config.set_value("shared_root", r"C:\seedling")
    code, out = run_cli("summary")
    assert "install type: multi-user" in out and r"C:\seedling" in out


def test_is_multi_user_ignores_corrupt_settings(home):
    from seedling import config, paths
    paths.ensure_layout()
    paths.CONFIG_FILE.write_text("{ broken json")
    assert config.is_multi_user() is False  # never raises


def test_unknown_command_exits_nonzero(run_cli):
    code, out = run_cli("frobnicate")
    assert code == 2  # argparse usage error


def test_where(run_cli, home):
    code, out = run_cli("where")
    assert code == 0
    assert str(home) in out


def test_empty_state_messages(run_cli):
    for cmd, expected in [
        ("python-list", "No base Python interpreters installed yet"),
        ("venv-list", "No venvs created yet"),
        ("repo-list", "No repos cloned yet"),
    ]:
        code, out = run_cli(cmd)
        assert code == 0
        assert expected in out


def test_python_list_shows_alias_and_default(run_cli, home):
    make_base_python(home, "312", "cpython-3.12.5-windows-x86_64-none")
    config.set_default_base("312")
    code, out = run_cli("python-list")
    assert code == 0
    assert "312" in out and "cpython-3.12.5" in out and "default" in out


def test_venv_list_marks_auto_activated(run_cli, home):
    make_venv_dirs(home, "dev", "other")
    config.set_value("default_venv", "dev")
    code, out = run_cli("venv-list")
    assert "dev" in out and "auto-activated in new shells" in out


def test_venv_default_show_set_and_missing(run_cli, home):
    code, out = run_cli("venv-default")
    assert code == 0 and "No default venv is set" in out
    code, out = run_cli("venv-default", "ghost")
    assert code == 1 and "No venv named 'ghost'" in out
    make_venv_dirs(home, "dev")
    code, out = run_cli("venv-default", "dev")
    assert code == 0
    assert config.get("default_venv") == "dev"
    code, out = run_cli("venv-default")
    assert "dev" in out


def test_config_show_get_set_unset(run_cli, home):
    code, out = run_cli("config")
    assert code == 0 and "update_source" in out and "package_index" in out
    code, out = run_cli("config", "set", "venv_default_packages", "a, b ,c")
    assert code == 0
    assert config.get("venv_default_packages") == ["a", "b", "c"]
    code, out = run_cli("config", "get", "venv_default_packages")
    assert out.strip().endswith("a,b,c")
    code, out = run_cli("config", "unset", "venv_default_packages")
    assert config.get("venv_default_packages") == ["ipython", "ruff", "ipykernel"]
    code, out = run_cli("config", "set", "bogus_key", "x")
    assert code == 1 and "Unknown key" in out


def test_config_native_tls_stores_real_bool(run_cli, home):
    run_cli("config", "set", "native_tls", "false")
    assert config.get("native_tls") is False
    run_cli("config", "set", "native_tls", "true")
    assert config.get("native_tls") is True
    run_cli("config", "set", "native_tls", "FALSE")  # case-insensitive
    assert config.get("native_tls") is False


def test_config_get_unset_prints_nothing(run_cli, home):
    code, out = run_cli("config", "get", "default_venv")
    assert code == 0 and out.strip() == ""


def test_summary_lists_sections_and_settings(run_cli, home):
    make_base_python(home, "312", "cpython-3.12.5-windows-x86_64-none")
    make_venv_dirs(home, "dev")
    code, out = run_cli("summary")
    assert code == 0
    for token in ("Tooling", "Base Pythons", "Venvs", "Repos", "Settings",
                  "312", "dev"):
        assert token in out, token


# --- python_cmd helpers -----------------------------------------------------

@pytest.mark.parametrize("raw,expected", [
    ("312", ("312", "3.12")),
    ("3.12", ("312", "3.12")),
    ("3.12.4", ("3124", "3.12.4")),
])
def test_normalize_tag(raw, expected):
    assert python_cmd._normalize_tag(raw) == expected


def test_newest_installed_dir_picks_highest_version(home):
    make_base_python(home, "312", "cpython-3.12.5-windows-x86_64-none")
    make_base_python(home, "313", "cpython-3.13.2-windows-x86_64-none")
    make_base_python(home, "39", "cpython-3.9.19-windows-x86_64-none")
    newest = python_cmd._newest_installed_dir()
    assert newest.name.startswith("cpython-3.13.2")


def test_resolve_base_via_alias_and_direct(home):
    target = make_base_python(home, "312", "cpython-3.12.5-windows-x86_64-none")
    assert python_cmd.resolve_base("312") == target
    assert python_cmd.resolve_base("999") is None
