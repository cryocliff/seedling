# seedling 🌱

**A clean implementation of Python tool management, for people who prefer
organization.** Interpreters, venvs, editor, cloned repos, config, and logs
all live in one tidy folder — `~/seedling` — instead of being scattered
across your filesystem. Built on [`uv`](https://astral.sh/uv). Delete the
folder and your machine is exactly as it was.

## Install

Nothing needs to be pre-installed — not Python, not uv, nothing.

**macOS / Linux:**
```sh
curl -fsSL https://raw.githubusercontent.com/cryocliff/seedling/main/installers/install.sh | sh
```

**Windows (PowerShell):**
```powershell
irm https://raw.githubusercontent.com/cryocliff/seedling/main/installers/install.ps1 | iex
```

The install also sets up the **newest stable Python** and a **`dev` venv**
(with `ipython` + `ruff`) that auto-activates in every new shell — so open
a new terminal and you're immediately ready:

```
python                    # the newest Python, in the dev venv, ready to go
seed install <package>    # add packages to it
seed python 312           # install another interpreter version
seed venv myproject       # create another venv
seed vscode               # install (once) + open a self-contained VS Code
seed remove-user          # wipe everything seedling has ever created
```

(Skip the default environment with `SEEDLING_AUTO_SETUP=no` before running
the installer, or by editing [`seedling.conf`](seedling.conf).)

📖 **[Full documentation](docs/DOCUMENTATION.md)** covers every command and
behavior in detail. This README is a quickstart. Command name: **`seed`**

## Everything lives in one place

```
~/seedling/
├── system/                 everything seedling needs to run itself
│   ├── bin/                    uv itself, and the seed-cli shim
│   ├── tool/                   the uv-managed venv seed-cli runs in
│   ├── src/                    seedling's own source (see `seed update-commands`)
│   ├── config/settings.json    seedling's own small config (see `seed config`)
│   ├── logs/                   one log file per day -- every command + its output
│   ├── cache/uv/               uv's download cache, kept in here too
│   └── shell/                  the seed.sh / seed.ps1 your shell profile loads
├── python/
│   ├── base/312/           `seed python 312`
│   └── venvs/myproject/    `seed venv myproject`
├── extensions/
│   └── vscode/
│       └── app/            portable VS Code — binary, settings, and extensions all in one place
└── repo/
    └── myrepo/             `seed clone-repo <url>`
```

Nothing is written to `%APPDATA%`, `~/.vscode`, `~/.local/share`, or any of
the other places tools like this usually scatter files into. Deleting
`~/seedling` (via `seed remove-user`) leaves your machine exactly as it was.

## Install details

The one-liners at the top bootstrap everything, the same way `uv`'s own
installer does — no git clone, no download, nothing to know in advance
beyond that one URL. (One exception, unrelated to installing seedling
itself: `seed clone-repo` needs git — auto-bootstrapped on Windows, needs
to already be present on macOS/Linux. See
[DOCUMENTATION.md](docs/DOCUMENTATION.md) for why.)

The installers also support two other modes:

- **Local checkout** — run `install.cmd` (Windows, double-click works) or
  `sh ./install.cmd` (macOS/Linux) from inside a copy of this repo (e.g. an
  unzipped download). No GitHub access needed at all for this mode.
- **A different source, for one run** — `SEEDLING_REPO=<git-url-or-directory>`
  (bash) or `$env:SEEDLING_REPO = "<git-url-or-directory>"` (PowerShell)
  before running the installer: a fork, a self-hosted git remote, or a plain
  directory such as a network drive holding a copy of this repo.

### Windows execution policy

```
install.cmd
```
(double-clicking it in File Explorer also works)

`install.cmd` is a small wrapper that runs `installers\install.ps1` with
the execution-policy bypass already applied for just that one run — it does
**not** change your system's PowerShell policy. The `irm | iex` one-liner
above sidesteps this issue entirely, since it never saves a local script
file for the execution policy to block in the first place. (The same
`install.cmd` doubles as the macOS/Linux entry point via `sh ./install.cmd`.)

Once the install succeeds, `install.cmd` opens a fresh PowerShell window
for you with `seed` ready to use and a short reminder of the first few
commands to try — since `install.cmd` itself runs in plain `cmd.exe`
(and even the PowerShell it drives runs with `-NoProfile`), `seed` could
never actually work in that original window no matter how it was launched.

What the installer actually does:
1. Clones seedling from GitHub (or uses your local checkout) into a temp
   location, then **copies it into `~/seedling/system/src`** — a private copy
   nothing outside of `seed update-commands` ever touches again.
2. Downloads `uv` straight into `~/seedling/system/bin` (uv's own installer, just
   redirected — this is the one binary seedling depends on, and it has zero
   dependencies of its own).
3. Uses that `uv` to install `~/seedling/system/src` itself as an isolated tool
   (uv will fetch a private Python for this automatically if needed — you
   still never have to have Python pre-installed).
4. Sets up the default environment — newest stable Python + the
   auto-activated `dev` venv — unless `SEEDLING_AUTO_SETUP=no`.
5. Writes `seed.sh` / `seed.ps1` — a **shell function**, not just a binary —
   and hooks it into your shell profile.

### Why `seed` is a shell function, not a plain command

`seed activate myproject` needs to change environment variables in *your
current terminal session*. No child process can do that to its parent shell
— it's why `conda activate` and virtualenv's `source venv/bin/activate` work
the way they do. So `seed` is a small shell function that special-cases
`activate` (sourcing the venv's activation script directly into your shell)
and forwards every other command straight to the real CLI binary,
`seed-cli`, which does the actual work.

## Commands

| Command | What it does |
|---|---|
| `seed python [ver]` | Installs a base interpreter, e.g. `seed python 312` → `~/seedling/python/base/312`. Accepts `312`, `3.12`, or `3.12.4` — or no version at all for the newest stable Python. |
| `seed list-python` | Lists every base Python installed, and which one is the default for `seed venv`. |
| `seed remove-python <tag> [-y]` | Deletes a base Python **and** any venvs that were built from it. |
| `seed venv <name>` | Creates a venv at `~/seedling/python/venvs/<name>` via `uv venv`, off the base Python (the first one you installed, or pass `--python <tag>`). Installs `ipython` + `ruff` into it by default — skip with `--no-default-packages`, or change the list with `seed config set venv_default_packages ...`. |
| `seed list-venvs` | Lists every venv, its Python version, and which one (if any) is currently active. |
| `seed activate <name>` | Activates that venv in your current shell. |
| `seed deactivate` | Deactivates the current venv in your current shell (runs the `deactivate` function venv's own activation script defines). |
| `seed default-venv [name]` | Shows or sets the venv every **new** shell auto-activates (the installer points this at `dev`). Clear it with `seed config unset default_venv`. |
| `seed install <pkg...>` | Installs packages into the active venv — a direct passthrough to `uv pip install <pkg...>`. |
| `seed uninstall <pkg...>` | Removes packages from the active venv — a direct passthrough to `uv pip uninstall <pkg...>`. |
| `seed list-packages` | Lists packages in the active venv — a direct passthrough to `uv pip list`. |
| `seed remove-venv <name>` | Deletes a single venv from `~/seedling/python/venvs`. |
| `seed remove-venvs [-y]` | Deletes every venv seedling has created. |
| `seed vscode [path]` | Installs a fully portable VS Code (first run only) into `~/seedling/extensions/vscode`, then opens it. Comes with Python, Pylance, debugpy, Jupyter, Ruff, and Rainbow CSV pre-installed, plus sane default settings. |
| `seed clone-repo <url>` | Clones a git repo into `~/seedling/repo/<name>`. Needs git; on Windows a portable copy is downloaded automatically if none is found. |
| `seed list-repos` | Lists every repo cloned with `seed clone-repo`, and each one's origin remote. |
| `seed open-repo <name>` | Opens a cloned repo in VS Code. |
| `seed install-repo <name>` | Installs a cloned repo's dependencies into the active venv (editable install if it has a `pyproject.toml`, otherwise `requirements.txt`). |
| `seed remove-repo <name> [-y]` | Deletes a cloned repo. |
| `seed kill-processes all [-y]` | Force-closes every Python and VS Code related process on the machine (not just seedling's). |
| `seed kill-processes <name> [-y]` | Force-closes every process with that exact name (e.g. `seed kill-processes node`). |
| `seed update-commands` | Explicitly updates the `seed` CLI itself. See below — nothing else ever does this automatically. |
| `seed summary [--sizes]` | One screen showing everything seedling has installed: tooling, base Pythons, venvs, repos, VS Code, and settings. `--sizes` adds disk usage. |
| `seed status` | Health check: verifies uv, git, config, every base Python and venv, the defaults, and the shell hook. Exit code 1 if anything is actually broken. |
| `seed config` | Views/changes seedling settings (`get`/`set`/`unset`): the default base Python, a `default_venv` auto-activated by every new shell, the `venv_default_packages` list, and `update_source` (see below). |
| `seed remove-user [-y]` | Deletes `~/seedling` entirely, after confirming. Leaves the `seed` shell hook in place. |
| `seed purge [-y] [--keep-repos]` | **Fully uninstalls seedling** — deletes `~/seedling` entirely *and* removes the `seed` shell hook from your profile. After this, `seed` stops existing as a command. `--keep-repos` preserves `~/seedling/repo` in a sibling folder first; without it, that folder *and* any leftover backup from a previous `--keep-repos` purge are both deleted. |
| `seed where` | Prints the seedling home directory. |

Run `uninstall.cmd` (Windows) or `sh ./uninstall.cmd` (macOS/Linux) to
also remove the shell hook from your profile (i.e. remove `seed` itself, not
just what it created).

**Every destructive command** (`remove-*`, `purge`, `kill-processes`) also
takes `--preview` — it prints exactly what would be deleted or closed, then
exits without touching anything — and `--non-interactive`, which makes it
abort instead of waiting for keyboard input (combine with `-y` to proceed;
`SEEDLING_NONINTERACTIVE=1` / `SEEDLING_YES=1` are the env equivalents for
scripts and CI).

Every command also appends what ran and everything it printed to a daily
log file under `~/seedling/system/logs/` (30-day retention; set
`SEEDLING_NO_LOG=1` to disable). Downloads seedling performs itself
(portable git, VS Code) are verified against their publishers' SHA-256
checksums before being extracted.

## Updates never happen without asking

The installer doesn't install `seed-cli` from wherever you downloaded or
cloned seedling from — it copies the source into `~/seedling/system/src`
(a plain copy, no `.git` folder) and installs from that private copy,
recording where it came from in the `update_source` setting. After that:

- Deleting your original download folder, or new commits landing on
  GitHub, does nothing to your working `seed` install.
- The **only** thing that ever changes `~/seedling/system/src` (and therefore what
  `seed` does) after the initial install is running:
  ```
  seed update-commands
  ```
  This re-fetches the latest copy from the recorded `update_source` — a
  fresh shallow `git clone` for a URL, or a re-copy for a directory — swaps
  it in, and reinstalls. If no source is recorded, it just reinstalls from
  whatever's currently there, so it also doubles as a "repair" command if
  you've hand-edited something.

### Deploying inside an organization (no github.com needed)

[`seedling.conf`](seedling.conf) at the top of this repo is the deployment
config. Every install-time setting is listed in it with its default value
already filled in — values left at their defaults change nothing, so
standard internet installs never touch the file. An organization replaces
whichever values it needs in the copy of the repo it distributes, and
everyone who installs from that copy picks them up automatically — no
flags or environment variables for users to remember:

- `SEEDLING_REPO_URL` — where seedling installs from and where
  `seed update-commands` fetches updates. Accepts **either a git URL** (e.g.
  a self-hosted GitHub Enterprise remote) **or a plain directory path**
  (a copy of this repo on a network drive — no git hosting needed at all).
- `SEEDLING_HOME_DIR` — the folder everything seedling manages lives in
  (default `~/seedling`).
- `SEEDLING_VENV_DEFAULT_PACKAGES` — the packages preinstalled into every
  new venv (default `ipython,ruff`).
- `SEEDLING_AUTO_SETUP` — whether the install finishes by setting up the
  newest Python + auto-activated `dev` venv (default `yes`).
- `SEEDLING_PYTHON_MIRROR` / `SEEDLING_PACKAGE_INDEX` — offline sources
  for interpreters and packages: URLs, or plain directories on a network
  share. Users never touch environment variables — the conf is applied
  automatically at install time and on every command after.

The install source is written into seedling's own settings on first
install (visible via `seed config`), so updates keep flowing from the
right place afterward. Per-run overrides still work without editing
anything: `SEEDLING_REPO=<url-or-directory>` before running the installer,
or `seed config set update_source <url-or-directory>` later.

For a **fully offline network** (no internet at all), see
📴 **[docs/OFFLINE.md](docs/OFFLINE.md)** — it lists every component
seedling normally downloads (uv, Python interpreters, packages, git,
VS Code) and exactly what to provide instead.

## Project layout (for contributors)

```
README.md
seedling.conf         deployment config: install/update source URL (or directory) + install-time settings
install.cmd           generic installer entry point: batch on Windows, `sh ./install.cmd` on macOS/Linux
uninstall.cmd         generic uninstaller entry point (same dual-platform trick)
installers/
  install.sh          the real POSIX installer (also what the curl one-liner runs)
  install.ps1         the real Windows installer (also what the irm one-liner runs)
  uninstall.sh / uninstall.ps1   full removal, including the shell hook (same end state as `seed purge`)
docs/
  DOCUMENTATION.md    the full documentation
src/
  pyproject.toml      the python package definition (`uv tool install` targets this folder)
  seedling/
    cli.py            argparse dispatcher
    paths.py          single source of truth for the ~/seedling folder layout
    config.py         JSON config (default base, default venv, update source, etc.) + `seed config`'s KNOWN_KEYS
    confirm.py        shared -y / --preview / --non-interactive handling for destructive commands
    runlog.py         tees stdout/stderr into ~/seedling/system/logs/, one file per day
    download.py       SHA-256-verifying download helper (MinGit, VS Code)
    uv_tool.py        locates + invokes the sandboxed uv binary, tags its output `[uv]`
    git_tool.py       locates git, bootstraps portable MinGit on Windows, tags streamed output `[git]`
    fsutil.py         retrying, cwd-aware directory deletion (see docs/DOCUMENTATION.md)
    colors.py         minimal ANSI color helper (NO_COLOR/non-tty aware)
    commands/         one module per `seed` command (python, venv, activate, repo,
                      vscode, kill, update, summary, status, config, remove, purge, ...)
    shell/
      seed.sh.template   copied to ~/seedling/system/shell/seed.sh at install time
      seed.ps1.template  copied to ~/seedling/system/shell/seed.ps1 at install time
```

## Notes / known limits

- `seed vscode` on macOS unpacks the official `.app` bundle and launches its
  embedded CLI binary; this is the least-tested of the three platforms.
- `seed python` version resolution assumes CPython (uv's default). PyPy etc.
  aren't wired up.
- `seed kill-processes` is machine-wide, not seedling-scoped — `all` closes
  every process whose name matches Python or VS Code, and `<name>` closes
  every process with that exact name, including ones unrelated to seedling.
  It relies on OS-builtin tools (`pgrep`/`kill` on macOS/Linux, `taskkill` on
  Windows) rather than a dependency like psutil, and always spares
  seedling's own running process.
- The installers assume `curl`/`wget` (POSIX) or PowerShell's
  `Invoke-RestMethod` (Windows) are available, which is true on effectively
  every macOS/Linux/Windows 10+ machine by default.
