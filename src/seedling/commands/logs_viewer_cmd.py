"""
`seed logs-viewer` -- render the daily command logs as a single, self-contained
HTML page and open it in the browser.

The logs are the plain-text daily files runlog.py writes under
~/seedling/system/logs/ (seed-YYYY-MM-DD.log), each a sequence of blocks:

    === [2026-07-05 14:30:22] seed venv dev
    <everything the command printed, ANSI stripped>
    === [14:30:23] exit code 0

This parses those blocks into structured entries, embeds them as JSON in a
standalone HTML file (no CDN, no network -- it works on a closed network like
the rest of seedling), and opens it. The page has search, a failures-only
filter, and collapsible per-command output; failed commands auto-expand.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import platform
import re
import subprocess
import sys
from pathlib import Path

from .. import colors, paths

# A block starts with a full date+time stamp; the matching exit line carries a
# time-only stamp. The two stamp shapes are what tell start lines apart from
# exit lines (and from any stray "=== " a command might print).
_START_RE = re.compile(r"^=== \[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\] (.*)$")
_EXIT_RE = re.compile(r"^=== \[(\d{2}:\d{2}:\d{2})\] exit code (-?\d+)$")
# install-YYYYMMDD-HHMMSS.log -- one file per bootstrap run (install.sh /
# install.ps1). install.sh writes the same block format as the daily logs;
# install.ps1 (Start-Transcript) writes a raw transcript, handled as one entry.
_INSTALL_RE = re.compile(r"^install-(\d{8})-(\d{6})\.log$")

VIEWER_FILENAME = "logs-viewer.html"


def _log_files(days: int | None) -> list[Path]:
    """Daily log files, newest first, optionally limited to the last `days`."""
    if not paths.LOGS_DIR.exists():
        return []
    files = []
    cutoff = None
    if days is not None:
        cutoff = _dt.date.today() - _dt.timedelta(days=days - 1)
    for f in paths.LOGS_DIR.glob("seed-*.log"):
        stamp = f.name[len("seed-"): -len(".log")]
        try:
            day = _dt.date.fromisoformat(stamp)
        except ValueError:
            continue
        if cutoff is None or day >= cutoff:
            files.append(f)
    return sorted(files, reverse=True)


def _read_log_text(path: Path) -> str:
    """Read a log file honoring a BOM. The daily logs and install.sh write
    UTF-8; install.ps1 captures via Tee-Object, which on Windows PowerShell
    5.1 writes UTF-16LE with a BOM -- detect it so both decode correctly."""
    try:
        raw = path.read_bytes()
    except OSError:
        return ""
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return raw.decode("utf-16", errors="replace")
    if raw[:3] == b"\xef\xbb\xbf":
        return raw.decode("utf-8-sig", errors="replace")
    return raw.decode("utf-8", errors="replace")


def _parse_file(path: Path, kind: str = "command") -> list[dict]:
    """Parse one block-format log (daily seed log, or an install.sh log) into
    a list of entries, each tagged with `kind` ('command' or 'install')."""
    text = _read_log_text(path)

    entries: list[dict] = []
    current: dict | None = None
    for line in text.splitlines():
        start = _START_RE.match(line)
        if start:
            # A previous entry with no exit line (e.g. a hard-killed process)
            # is flushed as-is before the new one begins.
            if current is not None:
                entries.append(_finalize(current, kind))
            current = {"ts": start.group(1), "cmd": start.group(2),
                       "out": [], "exit": None}
            continue
        exit_match = _EXIT_RE.match(line)
        if exit_match and current is not None and current["exit"] is None:
            current["exit"] = int(exit_match.group(2))
            entries.append(_finalize(current, kind))
            current = None
            continue
        if current is not None:
            current["out"].append(line)
    if current is not None:
        entries.append(_finalize(current, kind))
    return entries


def _finalize(entry: dict, kind: str = "command") -> dict:
    out = "\n".join(entry["out"]).strip("\n")
    return {"ts": entry["ts"], "cmd": entry["cmd"], "output": out,
            "exit": entry["exit"], "kind": kind}


def _install_files(days: int | None) -> list[Path]:
    """install-*.log files, newest first, optionally limited to the last
    `days` (dated from the filename)."""
    if not paths.LOGS_DIR.exists():
        return []
    cutoff = None
    if days is not None:
        cutoff = _dt.date.today() - _dt.timedelta(days=days - 1)
    files = []
    for f in paths.LOGS_DIR.glob("install-*.log"):
        m = _INSTALL_RE.match(f.name)
        if not m:
            continue
        try:
            day = _dt.datetime.strptime(m.group(1), "%Y%m%d").date()
        except ValueError:
            continue
        if cutoff is None or day >= cutoff:
            files.append(f)
    return sorted(files, reverse=True)


def _parse_install_file(path: Path) -> list[dict]:
    """A bootstrap log. install.sh writes the same block format as the daily
    logs (so it parses identically); install.ps1 writes a raw transcript,
    which becomes a single entry timestamped from the filename."""
    text = _read_log_text(path)
    if text.lstrip().startswith("=== ["):
        return _parse_file(path, kind="install")
    m = _INSTALL_RE.match(path.name)
    if m:
        d, t = m.group(1), m.group(2)
        ts = f"{d[0:4]}-{d[4:6]}-{d[6:8]} {t[0:2]}:{t[2:4]}:{t[4:6]}"
    else:
        ts = "0000-00-00 00:00:00"
    return [{"ts": ts, "cmd": "installer (bootstrap)", "output": text.strip("\n"),
             "exit": None, "kind": "install"}]


def collect_entries(days: int | None = None) -> list[dict]:
    """Every logged command AND every bootstrap install, newest first. The
    start timestamp is 'YYYY-MM-DD HH:MM:SS', which sorts chronologically as
    plain text."""
    entries: list[dict] = []
    for f in _log_files(days):
        entries.extend(_parse_file(f, kind="command"))
    for f in _install_files(days):
        entries.extend(_parse_install_file(f))
    entries.sort(key=lambda e: e["ts"], reverse=True)
    return entries


def render_html(entries: list[dict]) -> str:
    """A standalone HTML page. Entries are embedded as JSON and rendered with
    textContent in the browser, so arbitrary log output can never inject
    markup. The `</` escape keeps a literal </script> in the data from
    closing the embedding <script> tag early."""
    payload = {
        "generated": _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "home": str(paths.HOME),
        "entries": entries,
    }
    data = json.dumps(payload).replace("</", "<\\/")
    return _TEMPLATE.replace("__DATA__", data)


def _open_in_browser(path: Path) -> bool:
    """Open the generated page with the OS default handler for .html (the
    browser), same approach as `seed repo-open`. Never fatal -- a headless
    box has no browser, and the caller prints the path either way."""
    system = platform.system()
    try:
        if system == "Windows":
            os.startfile(str(path))  # noqa: type-ignore  # Windows-only
        elif system == "Darwin":
            subprocess.Popen(["open", str(path)], start_new_session=True)
        else:
            subprocess.Popen(["xdg-open", str(path)], start_new_session=True)
        return True
    except OSError:
        return False


def run(args) -> int:
    days = getattr(args, "days", None)
    no_open = getattr(args, "no_open", False)

    entries = collect_entries(days)

    paths.LOGS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = paths.LOGS_DIR / VIEWER_FILENAME
    try:
        out_path.write_text(render_html(entries), encoding="utf-8")
    except OSError as e:
        print(f"error: couldn't write the log viewer ({e})", file=sys.stderr)
        return 1

    if not entries:
        print("No commands logged yet -- the viewer will be empty until you "
              "run some `seed` commands (or logging is off via SEEDLING_NO_LOG=1).")

    n = len(entries)
    fails = sum(1 for e in entries if e["exit"] not in (0, None))
    summary = f"{n} command{'s' if n != 1 else ''}"
    if fails:
        summary += f", {colors.danger(str(fails) + ' failed')}"
    print(f"Log viewer: {summary}")
    print(f"  {out_path}")

    if no_open:
        return 0
    if _open_in_browser(out_path):
        print("Opening in your browser ...")
    else:
        print("Couldn't launch a browser automatically; open the file above by hand.")
    return 0


# The page: dark/light via prefers-color-scheme, a search box, a failures-only
# toggle, and collapsible output per command. __DATA__ is replaced with the
# JSON payload before writing.
_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>seedling logs</title>
<style>
  :root {
    color-scheme: light dark;  /* native date pickers follow the theme */
    --bg: #ffffff; --fg: #1f2328; --muted: #656d76; --border: #d0d7de;
    --card: #f6f8fa; --accent: #0969da; --ok: #1a7f37; --fail: #cf222e;
    --code-bg: #f6f8fa;
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --bg: #0d1117; --fg: #e6edf3; --muted: #8b949e; --border: #30363d;
      --card: #161b22; --accent: #4493f8; --ok: #3fb950; --fail: #f85149;
      --code-bg: #010409;
    }
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; background: var(--bg); color: var(--fg);
    font: 14px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
  }
  header {
    position: sticky; top: 0; background: var(--bg);
    border-bottom: 1px solid var(--border); padding: 16px 20px; z-index: 1;
  }
  h1 { margin: 0 0 4px; font-size: 18px; }
  h1 .seed { color: var(--accent); }
  .meta { color: var(--muted); font-size: 12px; }
  .controls { margin-top: 12px; display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }
  #search {
    flex: 1; min-width: 200px; padding: 7px 10px; border: 1px solid var(--border);
    border-radius: 6px; background: var(--card); color: var(--fg); font-size: 14px;
  }
  label.toggle { color: var(--muted); font-size: 13px; user-select: none; cursor: pointer; }
  .rangelabel { color: var(--muted); font-size: 13px; }
  input[type=date] {
    padding: 6px 8px; border: 1px solid var(--border); border-radius: 6px;
    background: var(--card); color: var(--fg); font-size: 13px;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  }
  input[type=date]:disabled { opacity: .5; }
  .dash { color: var(--muted); }
  .preset {
    padding: 6px 10px; border: 1px solid var(--border); border-radius: 6px;
    background: var(--card); color: var(--fg); font-size: 13px; cursor: pointer;
  }
  .preset:hover { border-color: var(--accent); }
  .preset.active { border-color: var(--accent); color: var(--accent); }
  main { padding: 12px 20px 60px; max-width: 1100px; margin: 0 auto; }
  .day { color: var(--muted); font-size: 12px; text-transform: uppercase;
         letter-spacing: .04em; margin: 20px 0 8px; }
  .entry { border: 1px solid var(--border); border-radius: 8px; margin: 8px 0;
           overflow: hidden; background: var(--card); }
  .entry.hidden { display: none; }
  .row { display: flex; align-items: center; gap: 10px; padding: 9px 12px; cursor: pointer; }
  .row:hover { background: rgba(127,127,127,.06); }
  .badge { flex: none; font: 600 11px/1 ui-monospace, SFMono-Regular, Menlo, monospace;
           padding: 4px 7px; border-radius: 20px; min-width: 34px; text-align: center; }
  .badge.ok { color: #fff; background: var(--ok); }
  .badge.fail { color: #fff; background: var(--fail); }
  .badge.unknown { color: var(--muted); border: 1px solid var(--border); }
  .kindtag { flex: none; font: 600 10px/1 ui-monospace, SFMono-Regular, Menlo, monospace;
             text-transform: uppercase; letter-spacing: .04em; color: var(--accent);
             border: 1px solid var(--accent); border-radius: 4px; padding: 3px 5px; }
  .cmd { flex: 1; font: 13px ui-monospace, SFMono-Regular, Menlo, monospace;
         white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .cmd .seed { color: var(--muted); }
  .time { flex: none; color: var(--muted); font-size: 12px; }
  .caret { flex: none; color: var(--muted); transition: transform .12s; }
  .entry.open .caret { transform: rotate(90deg); }
  pre.output { margin: 0; padding: 12px 14px; border-top: 1px solid var(--border);
    background: var(--code-bg); font: 12.5px/1.45 ui-monospace, SFMono-Regular, Menlo, monospace;
    white-space: pre-wrap; word-break: break-word; display: none; }
  .entry.open pre.output { display: block; }
  pre.output.empty { color: var(--muted); font-style: italic; }
  .empty-state { text-align: center; color: var(--muted); padding: 60px 20px; }
  mark { background: #ffd33d; color: #000; border-radius: 2px; }
</style>
</head>
<body>
<header>
  <h1><span class="seed">seed</span> command logs</h1>
  <div class="meta" id="meta"></div>
  <div class="controls">
    <input id="search" type="search" placeholder="Filter by command or output ...">
    <label class="toggle"><input type="checkbox" id="failonly"> failures only</label>
  </div>
  <div class="controls">
    <span class="rangelabel">Range</span>
    <button class="preset" data-days="0">All</button>
    <button class="preset" data-days="1">Today</button>
    <button class="preset" data-days="7">7 days</button>
    <button class="preset" data-days="30">30 days</button>
    <input type="date" id="from" aria-label="From date">
    <span class="dash">–</span>
    <input type="date" id="to" aria-label="To date">
  </div>
</header>
<main id="list"></main>
<script>
const PAYLOAD = __DATA__;
const entries = PAYLOAD.entries;
document.getElementById("meta").textContent =
  entries.length + " command" + (entries.length === 1 ? "" : "s") +
  " · " + PAYLOAD.home + " · generated " + PAYLOAD.generated;

const list = document.getElementById("list");
const search = document.getElementById("search");
const failonly = document.getElementById("failonly");

function badgeFor(exit) {
  const b = document.createElement("span");
  b.className = "badge " + (exit === 0 ? "ok" : exit === null ? "unknown" : "fail");
  b.textContent = exit === null ? "?" : String(exit);
  return b;
}

// Build the DOM once; filtering just toggles a .hidden class.
const nodes = [];
let lastDay = null;
for (const e of entries) {
  const day = e.ts.slice(0, 10);
  if (day !== lastDay) {
    const h = document.createElement("div");
    h.className = "day"; h.textContent = day; h.dataset.day = day;
    list.appendChild(h); lastDay = day;
  }
  const entry = document.createElement("div");
  entry.className = "entry" + (e.exit !== 0 && e.exit !== null ? " open" : "");

  const row = document.createElement("div");
  row.className = "row";
  row.appendChild(badgeFor(e.exit));

  if (e.kind === "install") {
    const tag = document.createElement("span");
    tag.className = "kindtag"; tag.textContent = "setup";
    row.appendChild(tag);
  }

  const cmd = document.createElement("span");
  cmd.className = "cmd"; cmd.textContent = e.cmd;
  row.appendChild(cmd);

  const time = document.createElement("span");
  time.className = "time"; time.textContent = e.ts.slice(11);
  row.appendChild(time);

  const caret = document.createElement("span");
  caret.className = "caret"; caret.textContent = "›";
  row.appendChild(caret);

  const pre = document.createElement("pre");
  pre.className = "output" + (e.output ? "" : " empty");
  pre.textContent = e.output || "(no output)";

  row.addEventListener("click", () => entry.classList.toggle("open"));
  entry.appendChild(row);
  entry.appendChild(pre);
  list.appendChild(entry);
  nodes.push({ entry, day, text: (e.cmd + "\n" + e.output).toLowerCase(),
               fail: e.exit !== 0 && e.exit !== null });
}

// Date range: all entries are embedded, so range selection is pure
// client-side filtering. ISO day strings (YYYY-MM-DD) compare correctly as
// plain text, so no Date objects are needed for the comparisons.
const fromEl = document.getElementById("from");
const toEl = document.getElementById("to");
const presets = [...document.querySelectorAll(".preset")];
let minDay = null, maxDay = null;
if (entries.length) {
  const days = entries.map(e => e.ts.slice(0, 10)).sort();
  minDay = days[0];
  maxDay = days[days.length - 1];
  for (const el of [fromEl, toEl]) { el.min = minDay; el.max = maxDay; }
  fromEl.value = minDay; toEl.value = maxDay;
} else {
  fromEl.disabled = toEl.disabled = true;
}

function addDays(iso, n) {
  const d = new Date(iso + "T00:00:00");
  d.setDate(d.getDate() + n);
  return d.toISOString().slice(0, 10);
}

function markPreset(active) {
  for (const b of presets) b.classList.toggle("active", b === active);
}

for (const btn of presets) {
  btn.addEventListener("click", () => {
    if (!maxDay) return;
    const n = parseInt(btn.dataset.days, 10);
    let from = (n === 0) ? minDay : addDays(maxDay, -(n - 1));
    if (from < minDay) from = minDay;   // don't run before the oldest log
    fromEl.value = from; toEl.value = maxDay;
    markPreset(btn);
    apply();
  });
}
// Editing a date by hand clears the highlighted preset.
for (const el of [fromEl, toEl]) el.addEventListener("change", () => { markPreset(null); apply(); });

function apply() {
  const q = search.value.trim().toLowerCase();
  const onlyFail = failonly.checked;
  const from = fromEl.value, to = toEl.value;
  let shown = 0;
  for (const n of nodes) {
    const inRange = (!from || n.day >= from) && (!to || n.day <= to);
    const ok = inRange && (!q || n.text.includes(q)) && (!onlyFail || n.fail);
    n.entry.classList.toggle("hidden", !ok);
    if (ok) shown++;
  }
  // Hide day headers whose entries are all filtered out.
  for (const h of list.querySelectorAll(".day")) {
    let sib = h.nextElementSibling, any = false;
    while (sib && !sib.classList.contains("day")) {
      if (sib.classList.contains("entry") && !sib.classList.contains("hidden")) { any = true; break; }
      sib = sib.nextElementSibling;
    }
    h.style.display = any ? "" : "none";
  }
  let es = document.querySelector(".empty-state");
  if (shown === 0) {
    if (!es) { es = document.createElement("div"); es.className = "empty-state"; list.appendChild(es); }
    es.textContent = entries.length ? "No commands match your filter." : "No commands have been logged yet.";
  } else if (es) { es.remove(); }
}
search.addEventListener("input", apply);
failonly.addEventListener("change", apply);
markPreset(presets.find(b => b.dataset.days === "0"));  // "All" selected on load
apply();
</script>
</body>
</html>
"""
