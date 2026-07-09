"""seed status: OK/WARN/FAIL matrix, exit codes, stale-hook and offline
source validation."""

from __future__ import annotations

import json

from conftest import make_base_python, make_venv_dirs
from seedling import config, paths


def test_fresh_sandbox_is_healthy_with_warnings(run_cli, home):
    code, out = run_cli("status")
    assert code == 0
    assert "FAIL" not in out
    assert "no base Pythons installed yet" in out
    assert "no update_source recorded" in out


def test_broken_default_venv_fails(run_cli, home):
    config.set_value("default_venv", "ghost")
    code, out = run_cli("status")
    assert code == 1
    assert "default_venv 'ghost'" in out


def test_corrupt_alias_fails(run_cli, home):
    paths.ensure_layout()
    (paths.BASE_DIR / "312.alias.json").write_text("{broken")
    code, out = run_cli("status")
    assert code == 1
    assert "alias file is corrupt" in out


def test_missing_base_target_fails(run_cli, home):
    paths.ensure_layout()
    (paths.BASE_DIR / "312.alias.json").write_text(
        json.dumps({"target": "cpython-gone"}))
    code, out = run_cli("status")
    assert code == 1 and "missing" in out


def test_venv_with_deleted_base_fails(run_cli, home):
    make_venv_dirs(home, "dev")
    (home / "python" / "venvs" / "dev" / "pyvenv.cfg").write_text(
        f"home = {home / 'python' / 'base' / 'gone'}\nversion = 3.12.0\n")
    code, out = run_cli("status")
    assert code == 1 and "its base Python" in out


def test_missing_offline_dirs_fail(run_cli, home):
    config.set_value("package_index", str(home / "no-wheels"))
    config.set_value("python_mirror", str(home / "no-mirror"))
    code, out = run_cli("status")
    assert code == 1
    assert "package_index directory" in out and "python_mirror directory" in out


def test_url_offline_sources_pass_without_network(run_cli, home):
    config.set_value("package_index", "https://pypi.internal/simple")
    config.set_value("python_mirror", "https://mirror.internal/pbs")
    code, out = run_cli("status")
    assert "package_index directory" not in out  # URLs aren't dir-checked


def test_missing_ca_cert_fails(run_cli, home):
    config.set_value("ca_cert", str(home / "gone.pem"))
    code, out = run_cli("status")
    assert code == 1 and "ca_cert" in out


def test_stale_hook_detection(run_cli, home, monkeypatch, tmp_path):
    """A profile hook line pointing at a deleted seed script must WARN, and a
    present target reads as OK. Uses the current platform's profile + script
    name (and native path separators) so the target actually resolves."""
    import os
    fake_userhome = tmp_path / "userhome"
    if os.name == "nt":
        profile = (fake_userhome / "Documents" / "WindowsPowerShell"
                   / "Microsoft.PowerShell_profile.ps1")
        seed_script = home / "system" / "shell" / "seed.ps1"
    else:
        profile = fake_userhome / ".bashrc"
        seed_script = home / "system" / "shell" / "seed.sh"
    profile.parent.mkdir(parents=True, exist_ok=True)
    profile.write_text(f'. "{seed_script}"\n')
    import pathlib
    monkeypatch.setattr(pathlib.Path, "home", staticmethod(lambda: fake_userhome))
    code, out = run_cli("status")
    assert "stale seedling hook" in out
    # now make the hook target real -> OK
    seed_script.parent.mkdir(parents=True, exist_ok=True)
    seed_script.write_text("")
    code, out = run_cli("status")
    assert "shell hook installed" in out
