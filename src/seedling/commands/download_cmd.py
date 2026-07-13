"""
`seed download-whl` / `seed download-requirements` -- build an offline wheel
bundle on a connected machine that can then feed an air-gapped install.

Both shell out to `uvx pip download` (uv has no `pip download` of its own, so
pip is run as an ephemeral uv tool -- nothing is installed permanently). The
result is a flat directory of `.whl` files (plus any source archives) that is
exactly what seedling's `package_index` setting consumes on the offline side:

    (connected)  seed download-whl pandas
    (copy the ./wheelhouse folder to the offline machine or a share)
    (offline)    seed config set package_index <that-folder>
                 seed install pandas

Every `pip download` flag passes straight through, so cross-platform bundles
(`--platform`, `--python-version`, `--only-binary=:all:`) and `--no-deps` all
work without seedling needing to know about them.
"""

from __future__ import annotations

from pathlib import Path

from .. import colors, config, uv_tool

# pip's conventional name for a flat directory of wheels. Landed in the current
# directory (not ~/seedling) because a bundle is meant to be carried OFF this
# machine to a share or the air-gapped target.
DEFAULT_DEST = "wheelhouse"


def _has_own_dest(tokens: list[str]) -> bool:
    """True if the user already specified where to put the wheels, so we don't
    override them with the default."""
    for tok in tokens:
        if tok in ("-d", "--dest") or tok.startswith("--dest="):
            return True
    return False


def _index_and_cert_args() -> list[str]:
    """Translate seedling's `package_index` / `ca_cert` settings into the pip
    flags that honor them, so a configured corporate index or private CA is
    used automatically -- users never set PIP_* environment variables. Placed
    before the user's own tokens so an explicit `--index-url` still wins."""
    out: list[str] = []
    index = config.get("package_index")
    if index:
        index = str(index)
        if "://" in index:
            out += ["--index-url", index]
        else:
            # A plain directory of wheels: download (copy) from it with the
            # internet index disabled, mirroring the offline install path.
            out += ["--no-index", "--find-links", index]
    ca = config.get("ca_cert")
    if ca:
        ca_path = Path(str(ca)).expanduser()
        if ca_path.is_file():
            out += ["--cert", str(ca_path)]
    return out


def _download(tokens: list[str]) -> int:
    """Run `uvx pip download` with `tokens` (specifiers/flags the user gave),
    injecting a default destination when they didn't pick one, then report
    what landed and how to use it offline."""
    dest: Path | None = None
    if not _has_own_dest(tokens):
        dest = Path(DEFAULT_DEST).resolve()
        dest.mkdir(parents=True, exist_ok=True)
        tokens = ["--dest", str(dest), *tokens]

    uv_tool.run([
        "tool", "run", "--from", "pip", "pip", "download",
        *_index_and_cert_args(), *tokens,
    ])

    if dest is not None:
        _report(dest)
    return 0


def _report(dest: Path) -> None:
    wheels = list(dest.glob("*.whl"))
    others = [p for p in dest.iterdir() if p.is_file() and p.suffix != ".whl"]
    count = f"{len(wheels)} wheel" + ("" if len(wheels) == 1 else "s")
    if others:
        count += (f" (+{len(others)} source archive"
                  + ("" if len(others) == 1 else "s") + ")")
    print()
    print(colors.ok(f"Downloaded {count} into {dest}"))
    print("To install these on an offline machine:")
    print("  1. Copy this folder to the target machine or a shared drive.")
    print(f"  2. seed config set package_index {dest}")
    print("  3. seed install <package>   # now resolves from the folder, offline")


def run_whl(args) -> int:
    tokens = getattr(args, "args", None) or []
    if not tokens:
        print("Usage: seed download-whl <package> [<package> ...] [pip download flags]")
        print("Downloads each package AND all its dependencies as wheels "
              "(default: ./wheelhouse) for an offline install.")
        return 1
    return _download(tokens)


def run_requirements(args) -> int:
    tokens = getattr(args, "args", None) or []
    if not tokens:
        print("Usage: seed download-requirements <requirements.txt> [pip download flags]")
        print("Downloads every pinned package AND its dependencies as wheels "
              "(default: ./wheelhouse) for an offline install.")
        return 1
    req_file, rest = tokens[0], tokens[1:]
    if not Path(req_file).is_file():
        print(f"error: requirements file not found: {req_file}")
        return 1
    return _download(["-r", req_file, *rest])
