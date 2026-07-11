#!/usr/bin/env python3
"""Render the mermaid diagrams to self-describing SVGs.

Each ``*.mmd`` in this folder is rendered to a matching ``*.svg`` with
mermaid-cli (``mmdc``), and the original mermaid source is embedded back into
the SVG as a base64-encoded ``<metadata>`` element. That embedded copy is the
"hidden reference": the picture carries its own source, so any ``*.svg`` here
can be regenerated even if its ``*.mmd`` is lost.

Usage
-----
    python build.py                # render every *.mmd -> *.svg (+ embed source)
    python build.py --check        # render to a temp dir; nonzero exit if any
                                   #   committed *.svg is stale (for CI)
    python build.py --from-svg F   # recover F's embedded source to <name>.mmd,
                                   #   then re-render it (regenerate from SVG alone)

Requires Node's mermaid-cli. It's found on PATH as ``mmdc`` if installed
globally, otherwise run on demand via ``npx -y @mermaid-js/mermaid-cli``
(set SEEDLING_MMDC to override the command).
"""

from __future__ import annotations

import argparse
import base64
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
# Sentinel so we can find (and replace) our own embedded block on re-runs
# instead of stacking a new one each time.
_META_RE = re.compile(
    r'\s*<metadata id="mermaid-source"[^>]*>.*?</metadata>', re.DOTALL)


def _mmdc_cmd() -> list[str]:
    """The mermaid-cli invocation: a real `mmdc` if one is on PATH, else
    `npx` fetching it on demand. SEEDLING_MMDC overrides both."""
    import os
    override = os.environ.get("SEEDLING_MMDC")
    if override:
        return override.split()
    if shutil.which("mmdc"):
        return ["mmdc"]
    if shutil.which("npx"):
        return ["npx", "-y", "@mermaid-js/mermaid-cli"]
    sys.exit("error: need mermaid-cli. Install Node, then `npm i -g "
             "@mermaid-js/mermaid-cli` (or ensure `npx` is available).")


def _render(mmd: Path, out_svg: Path) -> None:
    """Run mermaid-cli for one diagram. Transparent background so the node
    fills (not a page-colored rectangle) are all that shows, which keeps the
    image legible on both light and dark pages."""
    cmd = _mmdc_cmd() + ["-i", str(mmd), "-o", str(out_svg),
                         "-b", "transparent"]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        sys.exit(f"error: mmdc failed for {mmd.name}:\n{proc.stdout}\n{proc.stderr}")


def _embed_source(svg: Path, mmd_text: str) -> None:
    """Insert (or replace) the base64 mermaid source as the first child of
    <svg>. base64 keeps the payload free of <, >, and -- so it can never
    disturb the surrounding XML, and the element is metadata (never drawn)."""
    text = svg.read_text(encoding="utf-8")
    text = _META_RE.sub("", text)  # drop a previous embed, if any
    payload = base64.b64encode(mmd_text.encode("utf-8")).decode("ascii")
    block = (f'<metadata id="mermaid-source" data-encoding="base64">'
             f'{payload}</metadata>')
    # Insert right after the opening <svg ...> tag.
    m = re.search(r"<svg\b[^>]*>", text)
    if not m:
        sys.exit(f"error: {svg.name} has no <svg> opening tag to embed into.")
    svg.write_text(text[:m.end()] + "\n  " + block + text[m.end():],
                   encoding="utf-8")


def extract_source(svg: Path) -> str:
    """Recover the mermaid source embedded in an SVG (the reverse of
    _embed_source)."""
    text = svg.read_text(encoding="utf-8")
    m = re.search(r'<metadata id="mermaid-source"[^>]*>(.*?)</metadata>',
                  text, re.DOTALL)
    if not m:
        sys.exit(f"error: {svg.name} has no embedded mermaid source.")
    return base64.b64decode(m.group(1).strip()).decode("utf-8")


def build_one(mmd: Path, out_svg: Path) -> None:
    _render(mmd, out_svg)
    _embed_source(out_svg, mmd.read_text(encoding="utf-8"))


def cmd_build() -> int:
    mmds = sorted(HERE.glob("*.mmd"))
    if not mmds:
        sys.exit("error: no *.mmd files found next to build.py")
    for mmd in mmds:
        out = mmd.with_suffix(".svg")
        print(f"rendering {mmd.name} -> {out.name}")
        build_one(mmd, out)
    return 0


def cmd_check() -> int:
    """Render into a temp dir and compare against the committed SVGs. Used by
    CI to catch a *.mmd that was edited without re-rendering its *.svg."""
    stale = []
    with tempfile.TemporaryDirectory() as tmp:
        for mmd in sorted(HERE.glob("*.mmd")):
            fresh = Path(tmp) / (mmd.stem + ".svg")
            build_one(mmd, fresh)
            committed = mmd.with_suffix(".svg")
            if (not committed.exists()
                    or committed.read_text(encoding="utf-8")
                    != fresh.read_text(encoding="utf-8")):
                stale.append(mmd.stem)
    if stale:
        print("stale (re-run `python docs/diagrams/build.py`): "
              + ", ".join(stale))
        return 1
    print("diagrams up to date")
    return 0


def cmd_from_svg(svg_path: str) -> int:
    svg = Path(svg_path).resolve()
    src = extract_source(svg)
    mmd = svg.with_suffix(".mmd")
    mmd.write_text(src if src.endswith("\n") else src + "\n", encoding="utf-8")
    print(f"recovered {mmd.name} from {svg.name}; re-rendering")
    build_one(mmd, svg)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--check", action="store_true",
                   help="fail if any committed SVG is out of date")
    g.add_argument("--from-svg", metavar="FILE",
                   help="recover a diagram's source from its SVG, then re-render")
    args = ap.parse_args()
    if args.check:
        return cmd_check()
    if args.from_svg:
        return cmd_from_svg(args.from_svg)
    return cmd_build()


if __name__ == "__main__":
    raise SystemExit(main())
