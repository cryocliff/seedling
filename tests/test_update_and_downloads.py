"""seed update-commands (all three modes, vendor/.git exclusion) and the
download/verification helpers. uv's reinstall step is stubbed so these run
offline and fast; the fetch/copy logic is what's under test."""

from __future__ import annotations

import subprocess

import pytest

from conftest import GIT, REPO_ROOT, needs_git
from seedling import config, download, paths


@pytest.fixture
def src_installed(home, monkeypatch):
    """A sandbox with system/src populated and uv's tool-install stubbed."""
    src = home / "system" / "src" / "src"
    (src / "seedling").mkdir(parents=True)
    (src / "pyproject.toml").write_text("[project]\nname='seedling'\n")
    calls = []
    from seedling import uv_tool
    monkeypatch.setattr(uv_tool, "run", lambda args, **kw: calls.append(args))
    return home / "system" / "src", calls


def _make_source_tree(root, marker: str):
    (root / "src" / "seedling").mkdir(parents=True)
    (root / "src" / "pyproject.toml").write_text("[project]\nname='seedling'\n")
    (root / "MARKER.txt").write_text(marker)
    (root / ".git" / "objects").mkdir(parents=True)
    (root / "vendor" / "uv").mkdir(parents=True)
    (root / "vendor" / "uv" / "uv.exe").write_text("big binary")


def test_repair_mode_when_no_source_recorded(run_cli, home, src_installed):
    src, calls = src_installed
    code, out = run_cli("update-commands")
    assert code == 0
    assert "No update source is recorded" in out
    assert calls and calls[0][:2] == ["tool", "install"]
    assert calls[0][-1] == str(src / "src")


def test_directory_update_excludes_git_and_vendor(run_cli, home, src_installed, tmp_path):
    src, calls = src_installed
    upstream = tmp_path / "share"
    upstream.mkdir()
    _make_source_tree(upstream, "v2")
    config.set_value("update_source", str(upstream))
    code, out = run_cli("update-commands")
    assert code == 0
    assert (src / "MARKER.txt").read_text() == "v2"
    assert not (src / ".git").exists()
    assert not (src / "vendor").exists()


def test_directory_update_rejects_non_seedling_tree(run_cli, home, src_installed, tmp_path):
    bogus = tmp_path / "bogus"
    bogus.mkdir()
    config.set_value("update_source", str(bogus))
    code, out = run_cli("update-commands")
    assert code == 1
    assert "doesn't look like a seedling source tree" in out


@needs_git
def test_url_update_clones_and_swaps(run_cli, home, src_installed, tmp_path):
    src, calls = src_installed
    upstream = tmp_path / "upstream"
    upstream.mkdir()
    _make_source_tree(upstream, "v3")
    subprocess.run([GIT, "init", "-q", str(upstream)], check=True)
    subprocess.run([GIT, "-C", str(upstream), "add", "-A", "-f"], check=True)
    subprocess.run([GIT, "-C", str(upstream), "-c", "user.email=t@t",
                    "-c", "user.name=t", "commit", "-qm", "v3"], check=True)
    url = "file:///" + str(upstream).replace("\\", "/")
    config.set_value("update_source", url)

    # plant a read-only .git in the OLD copy: the swap must clear it
    old_git = src / ".git" / "objects" / "ab"
    old_git.mkdir(parents=True)
    ro = old_git / "deadbeef"
    ro.write_text("x")
    import stat
    ro.chmod(stat.S_IREAD)

    code, out = run_cli("update-commands")
    assert code == 0
    assert (src / "MARKER.txt").read_text() == "v3"
    assert not (src / ".git").exists()
    assert not (src / "vendor").exists()


@needs_git
def test_url_update_falls_back_when_clone_fails(run_cli, home, src_installed, tmp_path):
    src, calls = src_installed
    (src / "KEEP.txt").write_text("still here")
    config.set_value("update_source", "file:///" + str(tmp_path / "nonexistent").replace("\\", "/"))
    code, out = run_cli("update-commands")
    assert code == 0  # never fatal: reinstalls current copy
    assert "keeping the current copy" in out or "Download failed" in out
    assert (src / "KEEP.txt").exists()
    assert calls, "reinstall should still run"


# --- download.py -------------------------------------------------------------

def test_sha256_and_fetch_roundtrip(home, tmp_path, capsys):
    src_file = tmp_path / "payload.bin"
    src_file.write_bytes(b"hello seedling")
    url = "file:///" + str(src_file).replace("\\", "/")
    digest = download.sha256_of(src_file)

    dest = tmp_path / "out.bin"
    download.fetch(url, dest, expected_sha256=digest, label="payload")
    assert dest.read_bytes() == b"hello seedling"
    assert "Verified SHA-256" in capsys.readouterr().out

    # github-style "sha256:<hex>" prefix accepted
    download.fetch(url, dest, expected_sha256=f"sha256:{digest}", label="payload")


def test_fetch_mismatch_deletes_and_raises(home, tmp_path):
    src_file = tmp_path / "payload.bin"
    src_file.write_bytes(b"tampered")
    url = "file:///" + str(src_file).replace("\\", "/")
    dest = tmp_path / "out.bin"
    with pytest.raises(download.ChecksumMismatch):
        download.fetch(url, dest, expected_sha256="0" * 64, label="payload")
    assert not dest.exists()


def test_fetch_without_checksum_warns_but_proceeds(home, tmp_path, capsys):
    src_file = tmp_path / "payload.bin"
    src_file.write_bytes(b"data")
    url = "file:///" + str(src_file).replace("\\", "/")
    dest = tmp_path / "out.bin"
    download.fetch(url, dest, expected_sha256=None, label="payload")
    assert dest.exists()
    assert "no published checksum" in capsys.readouterr().out
