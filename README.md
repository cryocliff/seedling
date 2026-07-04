# seedling 🌱

A tiny, opinionated wrapper around [`uv`](https://astral.sh/uv) that gets you
from "nothing installed" to "writing Python" — with everything living in one
tidy folder instead of scattered across your filesystem.

📖 **[Full documentation](DOCUMENTATION.md)** covers every command and
behavior in detail. This README is a quickstart.

Command name: **`seed`**

```
seed python 312          # install a base Python interpreter
seed venv myproject       # create a venv off the current base python
seed activate myproject   # activate it, right in your current shell
seed vscode               # install (once) + open a self-contained VS Code
seed remove-user          # wipe everything seedling has ever created
```

## Everything lives in one place

```
~/seedling/
├── bin/                    uv itself, and the seed-cli shim (nothing on your PATH is required)
├── python/
│   ├── base/312/           `seed python 312`
│   └── venvs/myproject/    `seed venv myproject`
├── extensions/
│   └── vscode/
│       └── app/            portable VS Code — binary, settings, and extensions all in one place
├── config/settings.json    seedling's own small config (e.g. default base version)
└── shell/                  the seed.sh / seed.ps1 that your shell profile loads
```

Nothing is written to `%APPDATA%`, `~/.vscode`, `~/.local/share`, or any of
the other places tools like this usually scatter files into. Deleting
`~/seedling` (via `seed remove-user`) leaves your machine exactly as it was.

## Install

Nothing needs to be pre-installed — not Python, not uv, nothing. The
installer bootstraps all of it, the same way `uv`'s own installer does.

### First: publish this repo to GitHub (one-time setup)

The one-line installs below only work once seedling lives in a real GitHub
repo, because that's what `install.sh`/`install.ps1` clone from by default:

1. Create a GitHub repo (e.g. `you/seedling`) and push this project to it.
2. Edit the `DEFAULT_SEEDLING_REPO` / `$DefaultSeedlingRepo` line near the
   top of `install.sh` and `install.ps1` to point at it, and commit that.
3. Anyone can now install with a single line — no git clone, no download,
   nothing to know in advance beyond that one URL:

**macOS / Linux:**
```sh
curl -fsSL https://raw.githubusercontent.com/you/seedling/main/install.sh | sh
```

**Windows (PowerShell):**
```powershell
irm https://raw.githubusercontent.com/you/seedling/main/install.ps1 | iex
```

Until you've done that edit, the installers fall back to two other modes:

- **Local checkout** — run `./install.sh` / `install.cmd` from inside a
  folder that already has this project's `pyproject.toml` in it (e.g. after
  unzipping a downloaded copy). No GitHub repo needed at all for this mode.
- **A different repo, for one run** — `SEEDLING_REPO=<git url>` (bash) or
  `$env:SEEDLING_REPO = "<git url>"` (PowerShell) before running the
  installer, without editing the file.

### Windows execution policy

```
install.cmd
```
(double-clicking it in File Explorer also works)

`install.cmd` is a one-line wrapper that runs `install.ps1` with the
execution-policy bypass already applied for just that one run — it does
**not** change your system's PowerShell policy. The `irm | iex` one-liner
above sidesteps this issue entirely, since it never saves a local script
file for the execution policy to block in the first place.

What the installer actually does:
1. Clones seedling from GitHub (or uses your local checkout) into a temp
   location, then **copies it into `~/seedling/src`** — a private copy
   nothing outside of `seed update-commands` ever touches again.
2. Downloads `uv` straight into `~/seedling/bin` (uv's own installer, just
   redirected — this is the one binary seedling depends on, and it has zero
   dependencies of its own).
3. Uses that `uv` to install `~/seedling/src` itself as an isolated tool
   (uv will fetch a private Python for this automatically if needed — you
   still never have to have Python pre-installed).
4. Writes `seed.sh` / `seed.ps1` — a **shell function**, not just a binary —
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
| `seed python <ver>` | Installs a base interpreter, e.g. `seed python 312` → `~/seedling/python/base/312`. Accepts `312`, `3.12`, or `3.12.4`. |
| `seed list-python` | Lists every base Python installed, and which one is the default for `seed venv`. |
| `seed venv <name>` | Creates a venv at `~/seedling/python/venvs/<name>` via `uv venv`, off the base Python (the first one you installed, or pass `--python <tag>`). |
| `seed list-venvs` | Lists every venv, its Python version, and which one (if any) is currently active. |
| `seed activate <name>` | Activates that venv in your current shell. |
| `seed deactivate` | Deactivates the current venv in your current shell (runs the `deactivate` function venv's own activation script defines). |
| `seed install <pkg...>` | Installs packages into the active venv — a direct passthrough to `uv pip install <pkg...>`. |
| `seed uninstall <pkg...>` | Removes packages from the active venv — a direct passthrough to `uv pip uninstall <pkg...>`. |
| `seed remove-venv <name>` | Deletes a single venv from `~/seedling/python/venvs`. |
| `seed remove-venvs [-y]` | Deletes every venv seedling has created. |
| `seed kill-processes all [-y]` | Force-closes every Python and VS Code related process on the machine (not just seedling's). |
| `seed kill-processes <name> [-y]` | Force-closes every process with that exact name (e.g. `seed kill-processes node`). |
| `seed update-commands` | Explicitly updates the `seed` CLI itself. See below — nothing else ever does this automatically. |
| `seed vscode [path]` | Installs a fully portable VS Code (first run only) into `~/seedling/extensions/vscode`, then opens it. Comes with Python, Pylance, debugpy, Jupyter, and Ruff (linting/formatting) pre-installed, plus sane default settings. |
| `seed remove-user [-y]` | Deletes `~/seedling` entirely, after confirming. Closes any running Python/VS Code processes first so nothing blocks deletion. |
| `seed where` | Prints the seedling home directory. |

Run `./uninstall.sh` / `uninstall.cmd` (or `.\uninstall.ps1` directly) to
also remove the shell hook from your profile (i.e. remove `seed` itself, not
just what it created).

## Updates never happen without asking

The installer doesn't install `seed-cli` from wherever you downloaded or
cloned seedling from — it clones straight from your GitHub repo into
`~/seedling/src` and installs from that private copy. After that:

- Deleting your original download folder, or new commits landing on
  GitHub, does nothing to your working `seed` install.
- The **only** thing that ever changes `~/seedling/src` (and therefore what
  `seed` does) after the initial install is running:
  ```
  seed update-commands
  ```
  This runs `git pull --ff-only` against the GitHub remote it was originally
  cloned from, then reinstalls. If `~/seedling/src` somehow isn't a git
  checkout (e.g. you installed from a plain local folder with no repo),
  there's no remote to pull from — it just reinstalls from whatever's
  currently there, so it also doubles as a "repair" command if you've
  hand-edited something.

## Project layout (for contributors)

```
pyproject.toml
src/seedling/
  cli.py            argparse dispatcher
  paths.py          single source of truth for the ~/seedling folder layout
  config.py         tiny JSON config (default base python, etc.)
  uv_tool.py         locates + invokes the sandboxed uv binary
  commands/
    python_cmd.py   `seed python`
    venv_cmd.py     `seed venv`
    list_cmd.py     `seed list-python` / `seed list-venvs`
    activate_cmd.py `seed activate`
    deactivate_cmd.py `seed deactivate`
    install_cmd.py  `seed install`
    uninstall_cmd.py `seed uninstall`
    venv_remove_cmd.py `seed remove-venv(s)`
    kill_cmd.py     `seed kill-processes`
    update_cmd.py   `seed update-commands`
    vscode_cmd.py   `seed vscode`
    remove_cmd.py    `seed remove-user`
  shell/
    seed.sh.template   copied to ~/seedling/shell/seed.sh at install time
    seed.ps1.template  copied to ~/seedling/shell/seed.ps1 at install time
install.sh / install.ps1 / install.cmd      bootstrap installers (install.cmd wraps install.ps1 to dodge PowerShell's execution-policy prompt)
uninstall.sh / uninstall.ps1 / uninstall.cmd  full removal, including the shell hook
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
