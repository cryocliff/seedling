"""seed download-whl / download-requirements -- the offline wheel-bundle
builders. uv's `pip download` is stubbed (monkeypatched uv_tool.run), so these
run offline and fast; what's under test is the command line seedling hands to
`uvx pip download` and how it wires into the offline `package_index` setting."""

from __future__ import annotations

import pytest

from seedling import config


@pytest.fixture
def uv_calls(monkeypatch):
    """Capture the argument list of every uv_tool.run call instead of running uv."""
    from seedling import uv_tool
    calls: list[list[str]] = []
    monkeypatch.setattr(uv_tool, "run", lambda args, **kw: calls.append(list(args)))
    return calls


@pytest.fixture
def in_tmp(tmp_path, monkeypatch):
    """Run with cwd in a throwaway dir so the default ./wheelhouse lands there."""
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _tokens(calls):
    assert len(calls) == 1, f"expected one uv call, got {calls}"
    args = calls[0]
    assert args[:6] == ["tool", "run", "--from", "pip", "pip", "download"]
    return args[6:]


def test_download_whl_passes_through_and_injects_default_dest(run_cli, uv_calls, in_tmp):
    code, out = run_cli("download-whl", "pandas")
    assert code == 0
    tokens = _tokens(uv_calls)
    assert "pandas" in tokens
    # default destination injected and created
    dest = in_tmp / "wheelhouse"
    assert ["--dest", str(dest)] == tokens[:2]
    assert dest.is_dir()
    assert str(dest) in out  # next-step guidance names the folder


def test_download_whl_respects_user_dest(run_cli, uv_calls, in_tmp, tmp_path):
    custom = tmp_path / "mybundle"
    code, out = run_cli("download-whl", "pandas", "--dest", str(custom))
    assert code == 0
    tokens = _tokens(uv_calls)
    # our default was NOT injected; the user's --dest is the only one
    assert tokens.count("--dest") == 1
    assert not (in_tmp / "wheelhouse").exists()


def test_download_whl_forwards_pip_flags(run_cli, uv_calls, in_tmp):
    code, out = run_cli("download-whl", "numpy", "--only-binary=:all:",
                        "--platform", "manylinux2014_x86_64", "--python-version", "312")
    assert code == 0
    tokens = _tokens(uv_calls)
    for flag in ("--only-binary=:all:", "--platform", "manylinux2014_x86_64",
                 "--python-version", "312", "numpy"):
        assert flag in tokens


def test_download_whl_empty_is_usage_error(run_cli, uv_calls, in_tmp):
    code, out = run_cli("download-whl")
    assert code == 1
    assert "Usage: seed download-whl" in out
    assert not uv_calls


def test_package_index_url_becomes_index_url(run_cli, uv_calls, in_tmp):
    config.set_value("package_index", "https://nexus.corp/repository/pypi/simple")
    code, out = run_cli("download-whl", "pandas")
    assert code == 0
    tokens = _tokens(uv_calls)
    i = tokens.index("--index-url")
    assert tokens[i + 1] == "https://nexus.corp/repository/pypi/simple"


def test_package_index_dir_becomes_find_links(run_cli, uv_calls, in_tmp, tmp_path):
    wheels = tmp_path / "wheels"
    wheels.mkdir()
    config.set_value("package_index", str(wheels))
    code, out = run_cli("download-whl", "pandas")
    assert code == 0
    tokens = _tokens(uv_calls)
    assert "--no-index" in tokens
    i = tokens.index("--find-links")
    assert tokens[i + 1] == str(wheels)


def test_ca_cert_becomes_cert_flag(run_cli, uv_calls, in_tmp, tmp_path):
    cert = tmp_path / "corp-ca.pem"
    cert.write_text("-----BEGIN CERTIFICATE-----\n")
    config.set_value("ca_cert", str(cert))
    code, out = run_cli("download-whl", "pandas")
    assert code == 0
    tokens = _tokens(uv_calls)
    i = tokens.index("--cert")
    assert tokens[i + 1] == str(cert)


def test_download_requirements_uses_dash_r(run_cli, uv_calls, in_tmp, tmp_path):
    req = tmp_path / "requirements.txt"
    req.write_text("pandas==2.2.0\nrequests\n")
    code, out = run_cli("download-requirements", str(req))
    assert code == 0
    tokens = _tokens(uv_calls)
    i = tokens.index("-r")
    assert tokens[i + 1] == str(req)


def test_download_requirements_missing_file_errors(run_cli, uv_calls, in_tmp):
    code, out = run_cli("download-requirements", "nope.txt")
    assert code == 1
    assert "requirements file not found" in out
    assert not uv_calls


def test_download_requirements_empty_is_usage_error(run_cli, uv_calls, in_tmp):
    code, out = run_cli("download-requirements")
    assert code == 1
    assert "Usage: seed download-requirements" in out
    assert not uv_calls
