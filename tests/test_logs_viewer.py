"""seed logs-viewer: log parsing, self-contained/escaped HTML output, the
--no-open and --days flags, and the empty state."""

from __future__ import annotations

import datetime

from seedling import paths
from seedling.commands import logs_viewer_cmd as lv


def _write_log(day: str, body: str) -> None:
    paths.LOGS_DIR.mkdir(parents=True, exist_ok=True)
    (paths.LOGS_DIR / f"seed-{day}.log").write_text(body, encoding="utf-8")


_SAMPLE = (
    "\n=== [2026-07-08 09:00:01] seed venv dev\n"
    "Created venv dev\n"
    "=== [09:00:02] exit code 0\n"
    "\n=== [2026-07-08 09:05:00] seed install nope\n"
    "error: could not find nope\n"
    "=== [09:05:03] exit code 1\n"
)


def test_parses_commands_output_and_exit_codes(home):
    _write_log("2026-07-08", _SAMPLE)
    entries = lv.collect_entries()
    assert [e["cmd"] for e in entries] == ["seed install nope", "seed venv dev"]  # newest first
    assert entries[0]["exit"] == 1 and entries[1]["exit"] == 0
    assert entries[1]["output"] == "Created venv dev"


def test_duration_computed_from_start_and_exit_timestamps(home):
    _write_log("2026-07-08",
               "\n=== [2026-07-08 09:00:01] seed venv dev\nout\n"
               "=== [09:00:13] exit code 0\n")
    entries = lv.collect_entries()
    assert entries[0]["dur"] == 12  # 09:00:13 - 09:00:01
    # an entry with no exit line has no duration
    _write_log("2026-07-08",
               "\n=== [2026-07-08 09:00:01] seed python\nout\n")
    assert lv.collect_entries()[0]["dur"] is None


def test_entry_without_exit_line_is_still_parsed(home):
    # A hard-killed process never writes its exit line.
    _write_log("2026-07-08",
               "\n=== [2026-07-08 09:00:01] seed python\nDownloading ...\n")
    entries = lv.collect_entries()
    assert len(entries) == 1
    assert entries[0]["exit"] is None
    assert entries[0]["cmd"] == "seed python"


def test_install_log_block_format_becomes_an_install_entry(home):
    # install.sh writes the same block format as the daily logs.
    paths.LOGS_DIR.mkdir(parents=True, exist_ok=True)
    (paths.LOGS_DIR / "install-20260708-100000.log").write_text(
        "=== [2026-07-08 10:00:00] installer (bootstrap)\n"
        "==> Installing uv ...\n==> seedling is installed.\n"
        "=== [10:02:11] exit code 0\n", encoding="utf-8")
    entries = lv.collect_entries()
    assert len(entries) == 1
    assert entries[0]["kind"] == "install"
    assert entries[0]["exit"] == 0
    assert "seedling is installed" in entries[0]["output"]


def test_install_log_raw_transcript_becomes_one_entry(home):
    # install.ps1 (Start-Transcript) writes a raw transcript, not block format.
    # The explicit completion marker is what carries the exit code.
    paths.LOGS_DIR.mkdir(parents=True, exist_ok=True)
    (paths.LOGS_DIR / "install-20260709-142530.log").write_text(
        "**********************\nWindows PowerShell transcript start\n"
        "==> Cloning ...\n==> seedling is installed.\n"
        "seedling install completed (exit code 0)\n", encoding="utf-8")
    entries = lv.collect_entries()
    assert len(entries) == 1
    e = entries[0]
    assert e["kind"] == "install" and e["exit"] == 0
    assert e["ts"] == "2026-07-09 14:25:30"  # from the filename
    assert "seedling is installed" in e["output"]


def test_install_transcript_failure_marker_yields_exit_1(home):
    paths.LOGS_DIR.mkdir(parents=True, exist_ok=True)
    (paths.LOGS_DIR / "install-20260709-150000.log").write_text(
        "transcript start\nerror: git is required to clone x.\n"
        "seedling install FAILED (exit code 1)\n", encoding="utf-8")
    assert lv.collect_entries()[0]["exit"] == 1


def test_install_transcript_without_marker_falls_back(home):
    # Logs written before the marker existed: the human-facing success line
    # means completed; nothing at all means unknown (crashed / interrupted).
    paths.LOGS_DIR.mkdir(parents=True, exist_ok=True)
    (paths.LOGS_DIR / "install-20260708-090000.log").write_text(
        "transcript start\n==> seedling is installed.\ntranscript end\n",
        encoding="utf-8")
    (paths.LOGS_DIR / "install-20260708-080000.log").write_text(
        "transcript start\n==> Installing uv ...\n", encoding="utf-8")
    entries = {e["ts"][11:13]: e["exit"] for e in lv.collect_entries()}
    assert entries["09"] == 0     # legacy success line -> completed
    assert entries["08"] is None  # nothing to go on -> unknown


def test_install_log_utf16_bom_is_decoded(home):
    # install.ps1 captures via Tee-Object, which writes UTF-16LE with a BOM on
    # Windows PowerShell 5.1; the viewer must decode it, not show mojibake.
    paths.LOGS_DIR.mkdir(parents=True, exist_ok=True)
    (paths.LOGS_DIR / "install-20260709-160000.log").write_text(
        "==> Cloning ...\n==> seedling is installed.\n", encoding="utf-16")
    entries = lv.collect_entries()
    assert len(entries) == 1
    assert entries[0]["kind"] == "install"
    assert "seedling is installed" in entries[0]["output"]
    assert "\x00" not in entries[0]["output"]  # not read as raw UTF-16 bytes


def test_install_entries_render_a_setup_tag(home):
    html = lv.render_html([{"ts": "2026-07-08 10:00:00", "cmd": "installer (bootstrap)",
                            "output": "ok", "exit": 0, "kind": "install"}])
    assert "kindtag" in html and '"setup"' in html  # class + JS textContent


def test_writes_viewer_and_reports(run_cli, home):
    _write_log("2026-07-08", _SAMPLE)
    code, out = run_cli("logs-viewer", "--no-open")
    assert code == 0
    viewer = paths.LOGS_DIR / lv.VIEWER_FILENAME
    assert viewer.exists()
    assert "2 commands" in out and "1 failed" in out
    html = viewer.read_text(encoding="utf-8")
    assert "seed venv dev" in html and "seed install nope" in html


def test_html_is_self_contained_and_escapes_output(home):
    # Output containing markup must not be able to break out of the embedding
    # <script> or inject nodes.
    entries = [{"ts": "2026-07-09 10:00:00", "cmd": "seed x",
                "output": "danger </script><img src=x onerror=alert(1)>", "exit": 0}]
    html = lv.render_html(entries)
    # No external resources -> works offline.
    assert "http://" not in html and "https://" not in html
    assert "<script src" not in html and "<link" not in html
    # The only literal </script> is the real closing tag; the one in the data
    # was escaped to <\/script>.
    assert html.count("</script>") == 1
    assert "<\\/script>" in html


def test_viewer_has_interactive_date_range_controls(home):
    # The range picker filters the embedded data client-side, so the controls
    # and the range-filter logic must be present in the page.
    html = lv.render_html([{"ts": "2026-07-09 10:00:00", "cmd": "seed x",
                            "output": "", "exit": 0}])
    assert html.count('type="date"') == 2          # From / To inputs
    assert html.count('class="preset"') == 4        # All / Today / 7 days / 30 days
    assert "inRange" in html                        # range filtering in apply()


def test_no_open_does_not_launch_browser(run_cli, home, monkeypatch):
    _write_log("2026-07-08", _SAMPLE)
    calls = []
    monkeypatch.setattr(lv, "_open_in_browser", lambda p: calls.append(p) or True)
    code, out = run_cli("logs-viewer", "--no-open")
    assert code == 0 and calls == []


def test_open_launches_browser_when_not_no_open(run_cli, home, monkeypatch):
    _write_log("2026-07-08", _SAMPLE)
    calls = []
    monkeypatch.setattr(lv, "_open_in_browser", lambda p: calls.append(p) or True)
    code, out = run_cli("logs-viewer")
    assert code == 0
    assert calls == [paths.LOGS_DIR / lv.VIEWER_FILENAME]
    assert "Opening in your browser" in out


def test_days_filter_limits_history(home):
    today = datetime.date.today()
    old = (today - datetime.timedelta(days=40)).isoformat()
    recent = (today - datetime.timedelta(days=1)).isoformat()
    _write_log(old, f"\n=== [{old} 08:00:00] seed ancient\n=== [08:00:01] exit code 0\n")
    _write_log(recent, f"\n=== [{recent} 08:00:00] seed recent\n=== [08:00:01] exit code 0\n")
    cmds = [e["cmd"] for e in lv.collect_entries(days=7)]
    assert "seed recent" in cmds
    assert "seed ancient" not in cmds
    # Without the limit, both show up.
    assert "seed ancient" in [e["cmd"] for e in lv.collect_entries()]


def test_empty_state_when_no_logs(run_cli, home):
    code, out = run_cli("logs-viewer", "--no-open")
    assert code == 0
    assert "No commands logged yet" in out
    viewer = paths.LOGS_DIR / lv.VIEWER_FILENAME
    assert viewer.exists()  # still writes a (empty-state) page
