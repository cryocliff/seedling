"""vscode_cmd (pre-seed short-circuit, --no-open, clean offline errors) and
git_tool (lookup order, streamed tagging)."""

from __future__ import annotations

import io
import subprocess
import urllib.error

import pytest

from conftest import needs_git
from seedling import git_tool, paths
from seedling.commands import vscode_cmd


def _preseed_vscode(home):
    """A fake portable VS Code whose CLI script exists (Windows layout)."""
    bin_dir = home / "extensions" / "vscode" / "app" / "bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "code.cmd").write_text("@echo off\r\nexit /b 0\r\n")


def test_install_short_circuits_when_preseeded(home, monkeypatch):
    _preseed_vscode(home)
    def boom(*a, **k):
        raise AssertionError("network touched despite pre-seeded install")
    monkeypatch.setattr(vscode_cmd, "_resolve_download", boom)
    cli = vscode_cmd.install(force=False)
    assert cli is not None
    assert "code.cmd" in cli[-1]


def test_no_open_installs_without_window(run_cli, home, monkeypatch):
    _preseed_vscode(home)
    opened = []
    monkeypatch.setattr(vscode_cmd, "open_window", lambda cli, p: opened.append(p))
    code, out = run_cli("vscode", "--no-open")
    assert code == 0
    assert "installed and ready" in out
    assert opened == []


def test_vscode_opens_given_path(run_cli, home, monkeypatch, tmp_path):
    _preseed_vscode(home)
    opened = []
    monkeypatch.setattr(vscode_cmd, "open_window", lambda cli, p: opened.append(p))
    code, out = run_cli("vscode", str(tmp_path))
    assert code == 0
    assert opened == [str(tmp_path)]


def test_offline_download_fails_cleanly(home, monkeypatch, capsys):
    """No pre-seed + no network must be a one-line error, not a traceback."""
    monkeypatch.setattr(
        vscode_cmd, "_resolve_download", lambda os_id: ("https://x/download", None))
    def refuse(url, dest, **kw):
        raise urllib.error.URLError("no route to host")
    monkeypatch.setattr(vscode_cmd.download, "fetch", refuse)
    cli = vscode_cmd.install(force=False)
    assert cli is None
    out = capsys.readouterr().out
    assert "could not be downloaded" in out


def test_resolve_download_falls_back_when_api_unreachable(home, monkeypatch):
    def refuse(*a, **k):
        raise urllib.error.URLError("offline")
    monkeypatch.setattr(vscode_cmd.urllib.request, "urlopen", refuse)
    url, sha = vscode_cmd._resolve_download("win32-x64-archive")
    assert "code.visualstudio.com" in url
    assert sha is None


# --- git_tool ----------------------------------------------------------------

@needs_git
def test_find_git_prefers_path(home):
    found = git_tool.find_git()
    assert found is not None
    # bundled dir is empty in the sandbox, so this must be the PATH git
    assert str(git_tool.GIT_DIR) not in found


def test_find_git_falls_back_to_bundled(home, monkeypatch):
    monkeypatch.setattr(git_tool.shutil, "which", lambda name: None)
    bundled = git_tool.GIT_DIR / "cmd"
    bundled.mkdir(parents=True)
    (bundled / "git.exe").write_text("")
    assert git_tool.find_git() == str(bundled / "git.exe")


def test_find_git_none_when_nothing_available(home, monkeypatch):
    monkeypatch.setattr(git_tool.shutil, "which", lambda name: None)
    assert git_tool.find_git() is None


@needs_git
def test_run_streamed_tags_output(home, capsys):
    rc = git_tool.run_streamed([git_tool.find_git(), "--version"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "[git]" in out and "git version" in out
