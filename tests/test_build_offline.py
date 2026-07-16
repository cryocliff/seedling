"""Pure-logic unit tests for the offline bundle builder (installers/
build_offline.py): platform/asset mapping, parsing uv's interpreter-download
line, and the conf writer. No network -- the download/subprocess steps are
exercised by hand on a connected machine, not in CI."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

# build_offline.py lives in installers/ and isn't a package; load it directly.
_spec = importlib.util.spec_from_file_location(
    "build_offline", REPO_ROOT / "installers" / "build_offline.py")
build_offline = importlib.util.module_from_spec(_spec)
sys.modules["build_offline"] = build_offline
_spec.loader.exec_module(build_offline)


@pytest.mark.parametrize("machine,expected", [
    ("AMD64", "x86_64"), ("x86_64", "x86_64"), ("x64", "x86_64"),
    ("arm64", "aarch64"), ("aarch64", "aarch64"),
])
def test_normalized_arch(machine, expected):
    assert build_offline.normalized_arch(machine) == expected


@pytest.mark.parametrize("system,arch,expected", [
    ("Windows", "x86_64", "uv-x86_64-pc-windows-msvc.zip"),
    ("Windows", "aarch64", "uv-aarch64-pc-windows-msvc.zip"),
    ("Linux", "x86_64", "uv-x86_64-unknown-linux-gnu.tar.gz"),
    ("Darwin", "aarch64", "uv-aarch64-apple-darwin.tar.gz"),
])
def test_uv_asset_name(system, arch, expected):
    assert build_offline.uv_asset_name(system, arch) == expected


def test_uv_asset_name_rejects_unknown_os():
    with pytest.raises(ValueError):
        build_offline.uv_asset_name("Plan9", "x86_64")


def test_parse_pbs_target_windows_stripped():
    # The exact shape uv prints with -v (note the URL-encoded '+').
    line = ("DEBUG Downloading file:///C:/m/20241016/"
            "cpython-3.12.7%2B20241016-x86_64-pc-windows-msvc-"
            "install_only_stripped.tar.gz")
    tag, filename = build_offline.parse_pbs_target(line)
    assert tag == "20241016"
    # '%2B' decoded back to '+', which is the real on-disk asset name uv expects.
    assert filename == ("cpython-3.12.7+20241016-x86_64-pc-windows-msvc-"
                        "install_only_stripped.tar.gz")


def test_parse_pbs_target_linux_zst():
    line = ("Downloading file:///m/20250101/"
            "cpython-3.11.9%2B20250101-x86_64-unknown-linux-gnu-"
            "install_only.tar.zst")
    tag, filename = build_offline.parse_pbs_target(line)
    assert tag == "20250101"
    assert filename.endswith("install_only.tar.zst")


def test_parse_pbs_target_none_when_absent():
    assert build_offline.parse_pbs_target("nothing to see here") is None


@pytest.mark.parametrize("filename,expected", [
    ("cpython-3.12.13+20260623-x86_64-pc-windows-msvc-install_only_stripped.tar.gz", "3.12"),
    ("cpython-3.9.20+20240814-x86_64-unknown-linux-gnu-install_only.tar.gz", "3.9"),
    ("not-a-cpython-archive.tar.gz", None),
])
def test_minor_version(filename, expected):
    assert build_offline._minor_version(filename) == expected


def test_write_conf_replaces_in_place(tmp_path):
    conf = tmp_path / "seedling.conf"
    conf.write_text('SEEDLING_REPO_URL="https://old"\nOTHER="keep"\n',
                    encoding="utf-8")
    build_offline.write_conf(conf, {"SEEDLING_REPO_URL": "https://new"})
    text = conf.read_text(encoding="utf-8")
    assert 'SEEDLING_REPO_URL="https://new"' in text
    assert text.count("SEEDLING_REPO_URL=") == 1   # replaced, not duplicated
    assert 'OTHER="keep"' in text                  # untouched line preserved


def test_write_conf_appends_missing_key(tmp_path):
    conf = tmp_path / "seedling.conf"
    conf.write_text('OTHER="keep"\n', encoding="utf-8")
    build_offline.write_conf(conf, {"SEEDLING_PACKAGE_INDEX": "S:/wheels"})
    assert 'SEEDLING_PACKAGE_INDEX="S:/wheels"' in conf.read_text(encoding="utf-8")


def test_write_conf_handles_windows_backslash_value(tmp_path):
    """A Windows path value must not be interpreted as a regex-replacement
    escape (the \\U-in-C:\\Users bug)."""
    conf = tmp_path / "seedling.conf"
    conf.write_text('SEEDLING_PYTHON_MIRROR="x"\n', encoding="utf-8")
    win = r"C:\Users\dev\bundle\python-builds"
    build_offline.write_conf(conf, {"SEEDLING_PYTHON_MIRROR": win})
    assert f'SEEDLING_PYTHON_MIRROR="{win}"' in conf.read_text(encoding="utf-8")


def test_dry_run_returns_zero(tmp_path):
    code = build_offline.main(["--dry-run", "--output", str(tmp_path / "b")])
    assert code == 0
