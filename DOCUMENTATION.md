# seedling — full documentation

seedling is a single `seed` command that wraps [`uv`](https://astral.sh/uv)
and keeps every Python interpreter, virtual environment, VS Code install,
and cloned repo it manages inside one folder: `~/seedling`. Nothing it does
touches your system Python, `%APPDATA%`, `~/.vscode`, or any of the other
places these tools normally scatter files into.

This document covers every command and behavior as currently implemented.
For a shorter quickstart, see [README.md](README.md).

---

## Contents

- [How installation works](#how-installation-works)
- [The folder layout](#the-folder-layout)
- [Why `seed` is a shell function](#why-seed-is-a-shell-function)
- [Command reference](#command-reference)
- [The update model](#the-update-model)
- [Uninstalling](#uninstalling)
- [Troubleshooting](#troubleshooting)
- [Known limits](#known-limits)

---

## How installation works

Nothing needs to be pre-installed — not Python, not uv, not git (unless
you're installing from a repo rather than a local checkout, or using
`seed clone-repo` later, which does need git on PATH).

### One-line install (once published to GitHub)

```sh
curl -fsSL https://raw.githubusercontent.com/<you>/seedling/main/install.sh | sh
```
```powershell
irm https://raw.githubusercontent.com/<you>/seedling/main/install.ps1 | iex
```

This only works after the repo owner has pushed this project to GitHub and
set `DEFAULT_SEEDLING_REPO` (bash) / `$DefaultSeedlingRepo` (PowerShell) near
the top of `install.sh` / `install.ps1` to point at it.

### Local checkout install

If you have a local copy of this project (e.g. an unzipped download), run
the installer from inside it:

- **macOS/Linux:** `./install.sh`
- **Windows:** `install.cmd` (double-clicking it also works)

### Installing from a different repo, for one run

```sh
SEEDLING_REPO=https://github.com/someone/fork.git ./install.sh
```
```powershell
$env:SEEDLING_REPO = "https://github.com/someone/fork.git"; .\install.ps1
```

### What the installer actually does, step by step

1. **Locates the source.** If run from inside a folder with `pyproject.toml`
   (a local checkout), it uses that. Otherwise it clones `SEEDLING_REPO`
   (env var, or the baked-in default) via `git clone --depth 1`.
2. **Lays out `~/seedling/`** — `system/bin/`, `system/config/`,
   `system/shell/`, `python/base/`, `python/venvs/`, `extensions/`, `repo/`.
3. **Copies the source into `~/seedling/system/src`.** This copy, not the
   original download/clone location, is what `seed-cli` actually gets
   installed from. See [The update model](#the-update-model).
4. **Installs `uv` into `~/seedling/system/bin`**, using uv's own official
   installer with `UV_INSTALL_DIR` redirected there and
   `UV_NO_MODIFY_PATH=1` set (seedling manages its own PATH/shell
   integration rather than letting uv touch your global PATH). Skipped if
   `~/seedling/system/bin/uv` already exists.
5. **Installs `~/seedling/system/src` as an isolated uv tool**, via
   `uv tool install --force --reinstall`, with `UV_TOOL_DIR` and
   `UV_TOOL_BIN_DIR` redirected into `~/seedling/system/tool` and
   `~/seedling/system/bin`. uv will fetch its own private Python
   interpreter for this if none is available — you still never need Python
   pre-installed. This produces the `seed-cli` binary/shim. `--reinstall`
   forces uv to bypass its build cache, which matters every time
   `seed update-commands` runs this same step later.
6. **Writes the shell integration.** Copies `seed.sh.template` /
   `seed.ps1.template` into `~/seedling/system/shell/seed.sh` (or `.ps1`),
   with the real `~/seedling` path substituted in, then appends a line to
   your shell profile (`.zshrc`, `.bashrc`, `.profile`, or `$PROFILE`) that
   sources it — only if that line isn't already present.

### Windows execution policy

Running `.\install.ps1` directly, with no flags, fails with an
`is not digitally signed` error — that's Windows' default PowerShell policy
blocking unsigned local scripts, not a bug in the script. Three ways around
it:

- Use `install.cmd` instead — it's a one-line batch wrapper that launches
  `install.ps1` with `-ExecutionPolicy Bypass` scoped to that single run
  only. It does not change your system-wide policy.
- Use the `irm | iex` one-liner — piping into `Invoke-Expression` never
  saves a local script file, so there's nothing for the policy to block.
- Run manually: `powershell -ExecutionPolicy Bypass -File .\install.ps1`

---

## The folder layout

```
~/seedling/
├── system/                    everything seedling needs to run itself,
│   │                          kept out of the way of what you actually use
│   ├── bin/                      uv, and the seed-cli shim
│   ├── tool/                     the isolated uv-managed venv seed-cli runs in
│   ├── src/                      seedling's own source -- see "update model"
│   ├── config/
│   │   └── settings.json         seedling's own tiny config (default base, etc.)
│   └── shell/
│       ├── seed.sh                sourced by bash/zsh
│       └── seed.ps1                dot-sourced by PowerShell
├── python/
│   ├── base/
│   │   ├── 312/                   (nothing here directly -- see alias below)
│   │   ├── 312.alias.json         points "312" -> the real versioned dir uv made
│   │   └── cpython-3.12.x-.../    the actual interpreter uv installed
│   └── venvs/
│       └── <name>/                one folder per `seed venv <name>`
├── extensions/
│   └── vscode/
│       └── app/                   portable VS Code
│           └── data/               portable-mode settings + extensions, all local
└── repo/
    └── <name>/                    one folder per `seed clone-repo <url>`
```

Only `system/` holds seedling's own internals; `python/`, `extensions/`,
and `repo/` are the folders you'd actually browse into.

**Why the `.alias.json` files exist:** `uv python install 3.12` creates a
directory named after the exact resolved version and platform (e.g.
`cpython-3.12.4-linux-x86_64-gnu`), not a short `312`. seedling writes a
small JSON pointer file (`312.alias.json`) instead of relying on a symlink,
because creating symlinks requires elevated privileges on Windows by
default. `seed venv`/anything else that resolves a base tag reads this file
first.

---

## Why `seed` is a shell function

`seed activate <name>` and `seed deactivate` need to change environment
variables (`PATH`, `VIRTUAL_ENV`, your prompt) in **your current terminal
session**. A subprocess can never do that to its parent shell — this is the
same reason `conda activate` and `source venv/bin/activate` work the way
they do, rather than being plain executables.

So the installer writes `seed` as a shell **function** (bash/zsh) or
PowerShell function, not just a path to a binary:

- `seed activate <name>` → calls `seed-cli activate <name> --print-path`
  (a hidden flag) to get the venv's activation script path, then **sources**
  that script directly into the current shell.
- `seed deactivate` → calls the `deactivate` function that a venv's own
  activation script defines (bash: via `declare -f`/`command -v`;
  PowerShell: via `Get-Command`), if one exists in the current shell.
- Every other subcommand is forwarded straight through to the real
  `seed-cli` binary as a normal subprocess.

If you invoke `seed-cli activate <name>` or `seed-cli deactivate` directly
(bypassing the shell function — e.g. by calling the binary path explicitly),
you'll get a message explaining that this only works through the `seed`
shell function, since a subprocess has no way to affect your shell.

---

## Command reference

### `seed python <version>`

Installs a base CPython interpreter via `uv python install`, redirected
(via `UV_PYTHON_INSTALL_DIR`) into `~/seedling/python/base`.

- Accepts `312`, `3.12`, or `3.12.4` — digits are extracted and normalized
  into a dotted version spec for uv, and a short tag (e.g. `312`) for the
  folder alias.
- After installing, seedling locates the real directory uv created and
  writes the `<tag>.alias.json` pointer file described above.
- The **first** base Python you install becomes the default used by
  `seed venv` when you don't pass `--python`. This is tracked in
  `~/seedling/system/config/settings.json`.

```
seed python 312
```

### `seed list-python`

Lists every base Python interpreter installed via `seed python`, showing
the short tag, the real versioned directory it points to, which one is the
default used by `seed venv`, and flags any alias whose target directory has
gone missing (e.g. if it was deleted by hand).

```
seed list-python
```
```
Base Python interpreters in ~/seedling/python/base:
  311      -> cpython-3.11.9-linux-x86_64-gnu
  312      -> cpython-3.12.4-linux-x86_64-gnu  (default for `seed venv`)
```

### `seed remove-python <tag> [-y]`

Deletes a base Python **and every venv that was built from it** — venvs
can't function without the interpreter they were created against, so this
cascades rather than leaving them broken.

- Detects dependent venvs by reading the `home` field out of each venv's
  `pyvenv.cfg` and checking whether it resolves inside the base Python's
  directory.
- Lists exactly what it's about to delete (the base, plus each dependent
  venv by name) before asking for confirmation, unless `-y`/`--yes`.
- Force-closes Python/VS Code processes first — same mechanism as
  `seed kill-processes all` — so nothing blocks deletion.
- If the removed base was the default for `seed venv`, automatically
  switches the default to another remaining base (or clears it if none are
  left).

```
seed remove-python 311
```

### `seed venv <name> [--python <tag>]`

Creates a virtual environment at `~/seedling/python/venvs/<name>` via
`uv venv --python <interpreter>`.

- `--python <tag>` selects which installed base Python to build from
  (matching a tag from `seed python`). If omitted, uses the default base
  (the first one installed).
- Fails with a clear message if the requested base isn't installed, or if
  a venv with that name already exists.

```
seed venv myproject
seed venv myproject --python 311
```

### `seed list-venvs`

Lists every venv under `~/seedling/python/venvs`, showing the Python
version each was created with (read straight from its `pyvenv.cfg`) and
marking whichever one matches the current `VIRTUAL_ENV` (i.e. the one
you're actually inside right now) as active.

```
seed list-venvs
```
```
Venvs in ~/seedling/python/venvs:
  myproject  [python 3.12.4]  (active)
  scratch    [python 3.11.9]
```

### `seed activate <name>`

Activates a venv **in your current shell** (see
[Why `seed` is a shell function](#why-seed-is-a-shell-function)). Resolves
the right activation script per OS/shell:
- POSIX: `<venv>/bin/activate`
- Windows: `<venv>/Scripts/Activate.ps1` (falls back to `activate.bat`)

```
seed activate myproject
```

### `seed deactivate`

Deactivates whatever venv is currently active in your shell, by invoking
the `deactivate` function/command that the venv's own activation script
defined. Prints a message instead of erroring if nothing is active.

```
seed deactivate
```

### `seed install <package...>`

Direct passthrough to `uv pip install <package...>` — everything after
`install` is forwarded untouched (flags, version pins, multiple packages,
`-U`/`--upgrade`, etc. all work exactly as they would with `uv pip install`
directly).

Prints a warning first (but still proceeds) if `VIRTUAL_ENV` isn't set in
the environment, since `uv pip` needs a target environment to install into.

```
seed install requests
seed install -U "django>=5,<6" pillow
```

### `seed uninstall <package...>`

Direct passthrough to `uv pip uninstall <package...>`, with the same
argument-forwarding and `VIRTUAL_ENV` warning behavior as `seed install`.

```
seed uninstall requests
```

### `seed list-packages`

Direct passthrough to `uv pip list` for the active venv. Anything after
`list-packages` is forwarded to `uv pip list` untouched (e.g. `--format
json`, `--outdated`). Same `VIRTUAL_ENV` warning as `install`/`uninstall`.

```
seed list-packages
```
```
Package            Version
------------------ ---------
certifi            2026.6.17
requests           2.34.2
urllib3            2.7.0
```

### `seed remove-venv <name> [-y]`

Deletes a single venv from `~/seedling/python/venvs`. Force-closes
Python/VS Code processes first (see `seed kill-processes`) so a running
interpreter or open file inside the venv can't block deletion. Warns (but
doesn't block) if the target looks like the currently active venv
(`VIRTUAL_ENV` matches its path) — it'll be force-closed along with
everything else, so your shell may be left with a dangling activated
prompt; run `seed deactivate` afterward. Prompts for confirmation unless
`-y`/`--yes`.

```
seed remove-venv myproject
seed remove-venv myproject -y
```

### `seed remove-venvs [-y]`

Deletes **every** venv under `~/seedling/python/venvs`, with the same
process-closing behavior as `seed remove-venv`. Lists them all before
asking for confirmation (skippable with `-y`).

```
seed remove-venvs
```

### `seed vscode [path] [--reinstall]`

Installs (once) a fully portable copy of VS Code into
`~/seedling/extensions/vscode/app`, then opens it at `path` (defaults to
the current directory).

- **Portable mode:** a `data/` folder is created next to the VS Code
  executable, which makes VS Code keep all settings, extension installs,
  and workspace state inside that same folder — nothing goes to
  `~/.vscode`, `~/Library/Application Support`, or `%APPDATA%`.
- **Default settings** written on first install
  (`data/user-data/User/settings.json`):
  - `editor.formatOnSave: true`, default formatter set to Ruff
  - `notebook.formatOnSave.enabled: true`
  - `python.terminal.activateEnvironment: true`
  - `python.analysis.typeCheckingMode: "basic"`
  - `files.autoSave: "onFocusChange"`
  - Telemetry, auto-update, and extension auto-update all turned off
- **Default extensions** installed on first install:
  - `ms-python.python`, `ms-python.vscode-pylance`, `ms-python.debugpy`
    (Python language support + debugging)
  - `ms-toolsai.jupyter`, `ms-toolsai.jupyter-keymap`,
    `ms-toolsai.jupyter-renderers` (Jupyter notebooks)
  - `charliermarsh.ruff` (fast linting/formatting)
  - `editorconfig.editorconfig`
  - `mechatroner.rainbow-csv` (color-codes CSV/TSV columns by position, plus
    a simple SQL-like query feature over the file)
- `--reinstall` forces a fresh download/reinstall even if VS Code is
  already present.
- **Uses VS Code's actual CLI entry point** (`bin/code.cmd` on Windows,
  `Contents/Resources/app/bin/code` on macOS, `bin/code` on Linux) for both
  installing extensions and opening windows — the same thing that runs
  when you type `code --install-extension ...` or `code .` in a normal
  terminal, rather than the raw Electron GUI binary (which would open a
  full window per extension and flood stdout/stderr with log spam). If the
  CLI script genuinely can't be found, extension installation is skipped
  with a warning rather than falling back to that behavior.
- All subprocess calls (extension installs, opening a window) run with
  stdout/stderr/stdin redirected away from your terminal, and the window-
  open call is fully detached from seedling's own process — `seed vscode`
  returns immediately either way and never blocks on VS Code's own output.
- Idempotent: a plain `seed vscode` with no `--reinstall` only ever
  downloads/reinstalls/re-adds extensions on the very first run for a given
  `~/seedling`; every call after that just opens a window.
- Platform support: downloads the correct stable-build archive for
  Windows (`win32-x64-archive`), macOS (`darwin` / `darwin-arm64`), and
  Linux (`linux-x64` / `linux-arm64`) automatically.

```
seed vscode
seed vscode ./my-project
seed vscode --reinstall
```

### `seed clone-repo <git-url>`

Clones a git repository into `~/seedling/repo/<name>` via a plain
`git clone`. The repo name is derived from the URL (handles
`https://host/group/name.git`, SSH-style `git@host:group/name.git`, and
plain paths). Requires `git` on PATH — this is the one command in seedling
that isn't self-bootstrapping, since seedling doesn't manage git itself.
Fails with a clear message (rather than overwriting) if a repo with that
name already exists — remove it first with `seed remove-repo`.

```
seed clone-repo https://github.com/you/some-project.git
```

### `seed list-repos`

Lists every repo cloned via `seed clone-repo`, along with each one's
`origin` remote URL (if it's still a git checkout with one configured).

```
seed list-repos
```
```
Repos in ~/seedling/repo:
  some-project  -> https://github.com/you/some-project.git
```

### `seed open-repo <name>`

Opens a cloned repo in VS Code — installing VS Code first if it isn't
already (same one-time setup as `seed vscode`). Shares the same CLI-entry-
point, detached-process opening logic as `seed vscode`.

```
seed open-repo some-project
```

### `seed install-repo <name>`

Installs a cloned repo's dependencies into the currently active venv:

- If the repo has a `pyproject.toml`, runs `uv pip install -e <repo>`
  (editable install — changes you make in the cloned repo take effect
  immediately without reinstalling, which is what you want when actively
  developing against it).
- Otherwise, if it has a `requirements.txt`, runs
  `uv pip install -r <repo>/requirements.txt`.
- If neither file exists, fails with a message rather than guessing.
- Same `VIRTUAL_ENV` warning as `seed install` if nothing is active.

```
seed activate myproject
seed install-repo some-project
```

### `seed remove-repo <name> [-y]`

Deletes a cloned repo from `~/seedling/repo`. Same process-closing
behavior as `seed remove-venv` before deletion, and the same confirmation
prompt (skippable with `-y`).

```
seed remove-repo some-project
```

### `seed kill-processes <all|name> [-y]`

An escape hatch for stuck scripts or a frozen VS Code window. Always
prompts for confirmation first (skippable with `-y`), since it's
machine-wide and destructive (unsaved work included).

- `seed kill-processes all` — force-closes every process matching common
  Python interpreter names (`python`, `python3`, `python3.8`-`3.14`,
  `pythonw`) and VS Code/Electron process names (`code`, `Code`,
  `Code Helper*`, `Electron`).
- `seed kill-processes <name>` — force-closes every process with that
  **exact** name (e.g. `seed kill-processes node`). On Windows, `.exe` is
  appended automatically if you don't include it.

Implementation notes:
- **Not** seedling-scoped — this affects every matching process on the
  machine, not just ones seedling started.
- Uses only OS-builtin tools: `pgrep -x` + `kill`/`os.kill` on macOS/Linux,
  `taskkill /F /IM` on Windows. No third-party dependency like `psutil`.
- Always excludes seedling's own running process (and its parent) from the
  kill list, so it can't terminate itself mid-cleanup — this matters
  because on macOS/Linux, `seed-cli`'s own process image is literally a
  `python3.x` process (its shebang execs the interpreter directly).
- The underlying `kill_python_and_vscode()` helper is reused by
  `seed remove-venv(s)`, `seed remove-python`, `seed remove-repo`,
  `seed remove-user`, and `seed purge` — anything that deletes files is
  preceded by this same sweep, to avoid "file in use" failures.

```
seed kill-processes all
seed kill-processes node -y
```

### `seed update-commands`

The **only** thing that updates the `seed` command itself after initial
install. See [The update model](#the-update-model) below for the full
explanation. In short:

- If `~/seedling/system/src` is a git checkout, runs `git pull --ff-only`
  against its origin remote (printing that remote's URL), then reinstalls
  via `uv tool install --force --reinstall`.
- If it isn't a git checkout, there's no remote to pull from — it just
  reinstalls from whatever is currently in `~/seedling/system/src`, which
  doubles as a repair command if you've hand-edited something there.

```
seed update-commands
```

### `seed remove-user [-y]`

Deletes `~/seedling` in its entirety — every base Python, every venv, VS
Code and all its extensions/settings, every cloned repo, uv itself,
everything. Prompts for confirmation (`yes` typed exactly) unless
`-y`/`--yes` is passed.

Before deleting, it first force-closes every Python and VS Code process on
the machine (the same sweep as `seed kill-processes all`, with the same
self-exclusion so it can't kill `seed-cli`'s own process mid-run). This
avoids the classic "file is in use" failure on Windows, and stray file
handles on any OS, from a running venv interpreter or an open VS Code
window blocking deletion of files inside `~/seedling`. Like
`kill-processes`, this is machine-wide, not seedling-scoped — the
confirmation prompt says so up front.

This does **not** remove the `seed` shell function/hook from your shell
profile — use `seed purge` (or `uninstall.sh` / `uninstall.cmd` /
`uninstall.ps1`) for that.

```
seed remove-user
```

### `seed purge [-y]`

The full uninstall — everything `seed remove-user` does, **plus** removes
the `seed` shell hook from every shell profile it can find:
`~/.zshrc`, `~/.bashrc`, `~/.bash_profile`, `~/.profile`, and both the
PowerShell Core and Windows PowerShell profile locations (checked on every
OS, since PowerShell itself is cross-platform — harmless no-ops wherever
they don't exist).

After `seed purge` finishes, `seed` stops existing as a command entirely.
This is the same end state as running `uninstall.sh` / `uninstall.cmd` /
`uninstall.ps1`, just reachable from inside `seed` itself without needing
the original installer files around. Reports exactly which profile files
it edited.

```
seed purge
```

### `seed where`

Prints the seedling home directory (`~/seedling`, or the value of the
`SEEDLING_HOME` environment variable override if set).

```
seed where
```

---

## The update model

seedling is deliberately designed so that **nothing updates the `seed`
command without you explicitly asking it to.**

The installer doesn't install `seed-cli` from wherever you ran it from — it
clones/copies the source into `~/seedling/system/src` first, and installs
from *that* private copy. Concretely:

- Deleting, moving, or renaming your original download or clone does
  nothing to your working `seed` install — it already has its own copy.
- New commits landing on the GitHub repo you installed from have zero
  effect on your install until you act.
- The only command that ever touches `~/seedling/system/src` (and
  therefore what `seed` does) after the initial install is
  `seed update-commands`.

This means re-running the original `curl | sh` one-liner is not how you
update seedling day-to-day — `seed update-commands` is.

---

## Uninstalling

- `seed remove-user` — removes everything *seedling manages* (Python
  installs, venvs, VS Code, cloned repos, uv, its own source) but leaves
  the `seed` shell hook in your profile.
- `seed purge`, or `./uninstall.sh` / `uninstall.cmd` / `.\uninstall.ps1` —
  removes the `seed` shell hook from your profile **and** deletes
  `~/seedling` entirely, for a full clean removal. `seed purge` is the same
  operation reachable from inside `seed` itself, for when you don't have
  the original installer files handy.

---

## Troubleshooting

**"is not digitally signed. You cannot run this script on the current
system"** — see [Windows execution policy](#windows-execution-policy).

**`seed: command not found` after installing** — open a new terminal (the
shell hook only takes effect in new shells), or manually run
`. ~/seedling/system/shell/seed.sh` (bash/zsh) /
`. ~/seedling/system/shell/seed.ps1` (PowerShell) in your current one.

**`No base Python found`** when running `seed venv` — install one first
with `seed python <version>`.

**`uv was not found in ~/seedling/system/bin or on PATH`** — re-run the
installer; this means the uv bootstrap step didn't complete.

**A venv or VS Code window is stuck / won't close** — `seed kill-processes
all` (or targeting a specific process name) force-closes it, after
confirmation. Every `remove-*` command and `seed purge` also do this
automatically before deleting anything.

**`git is required for 'seed clone-repo'`** — install git through your OS's
normal package manager; unlike everything else in seedling, this one
command needs it on PATH, since seedling doesn't manage git itself.

**`seed vscode` repeatedly opens new windows and/or floods the terminal with
VS Code logs, and extensions never actually get installed** — this was a
real bug (fixed): extension installation was calling the raw Electron GUI
binary directly instead of VS Code's CLI script, which opens a window per
extension instead of installing headlessly. If you're still hitting this,
run `seed update-commands` to pick up the fix, then `seed vscode --reinstall`.

---

## Known limits

- `seed vscode`/`seed open-repo` on macOS unpack the official `.app` bundle
  and launch its embedded CLI binary; this is the least-tested of the
  three platforms.
- `seed python` version resolution assumes CPython (uv's default); PyPy and
  other implementations aren't wired up.
- `seed kill-processes` (and everything that reuses it) is machine-wide,
  not seedling-scoped, by design — see the command reference above.
- `seed clone-repo`/`install-repo` require `git` on PATH; this is the one
  place seedling doesn't fully self-bootstrap.
- `seed install-repo` only recognizes `pyproject.toml` and
  `requirements.txt` — repos using other dependency files (e.g. Poetry's
  `poetry.lock` without a PEP 621 `pyproject.toml` section, or Pipenv) may
  need manual installation.
- The installers assume `curl`/`wget` (POSIX) or PowerShell's
  `Invoke-RestMethod` are available, which is true by default on
  effectively every macOS/Linux/Windows 10+ machine.
