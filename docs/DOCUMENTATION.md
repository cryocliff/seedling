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
- Running on an offline network -> see [OFFLINE.md](OFFLINE.md)
- [The folder layout](#the-folder-layout)
- [Why `seed` is a shell function](#why-seed-is-a-shell-function)
- [Why deletion is so defensive](#why-deletion-is-so-defensive)
- [Help output & color](#help-output--color)
- [Command logging](#command-logging)
- [Non-interactive mode & previews](#non-interactive-mode--previews)
- [Download verification](#download-verification)
- [Command reference](#command-reference)
- [The update model](#the-update-model)
- [Uninstalling](#uninstalling)
- [Troubleshooting](#troubleshooting)
- [Known limits](#known-limits)

---

## How installation works

Nothing needs to be pre-installed to install seedling itself — not Python,
not uv, not git (git is only needed if you install from a GitHub repo
rather than a local checkout; see below). Separately, `seed clone-repo`
(a feature *of* seedling, used after it's installed) needs git to work —
on Windows, seedling downloads a portable copy automatically if none is
found; see [`seed clone-repo`](#seed-clone-repo-git-url) for details.

### The four ways to install

There are four install origins. Whichever one is used gets recorded as the
`update_source` setting, so `seed update-commands` keeps fetching from the
right place afterward — and `seed purge`'s "to reinstall later" message
matches it too:

| # | Origin | How you install | Recorded as `update_source` | Reinstall later by |
|---|--------|-----------------|------------------------------|--------------------|
| 1 | **Public GitHub** | The `curl`/`irm` one-liners below | The public repo URL | The same one-liners |
| 2 | **Local checkout** | Run `install.cmd` from inside a downloaded/cloned copy of this repo | The checkout's own `origin` remote (or the resolved default) | Running `install.cmd` in a checkout again |
| 3 | **Directory / network share** | `seedling.conf`'s `SEEDLING_REPO_URL` (or the `SEEDLING_REPO` env var) set to a folder holding a copy of this repo | That directory | Running `install.cmd` on the share again |
| 4 | **Self-hosted git** | `seedling.conf`'s `SEEDLING_REPO_URL` (or `SEEDLING_REPO`) set to a git URL (GitHub Enterprise, GitLab, a fork...) | That URL | `git clone <url>` + `install.cmd` inside the clone |

Origins 3 and 4 are the organization-deployment story: edit
[`seedling.conf`](#deployment-configuration-seedlingconf) once in the copy
you distribute, and users install with no flags at all. The sections below
cover each mechanism in detail.

### One-line install

```sh
curl -fsSL https://raw.githubusercontent.com/cryocliff/seedling/main/installers/install.sh | sh
```
```powershell
irm https://raw.githubusercontent.com/cryocliff/seedling/main/installers/install.ps1 | iex
```

By default the installers clone from
`https://github.com/cryocliff/seedling.git` (the `DEFAULT_SEEDLING_REPO` /
`$DefaultSeedlingRepo` value near the top of `installers/install.sh` / `installers/install.ps1`).

### Local checkout install

If you have a local copy of this project (e.g. an unzipped download), run
the installer from inside it:

- **macOS/Linux:** `sh ./install.cmd` (or `installers/install.sh` directly)
- **Windows:** `install.cmd` (double-clicking it also works)

### Deployment configuration: `seedling.conf`

`seedling.conf` at the repo root is the single place a deployment's paths
and install-time settings live. Every setting is listed in the file with
its default value written out, so there's no guessing what can be changed
or what the current behavior is — values left at their defaults change
nothing. Standard users installing from the internet never touch it.
Organizations replace whichever values they need in the copy of the repo
they distribute (self-hosted git host, or a folder on a network drive),
and everyone installing from that copy picks the values up with no flags
or environment variables:

- `SEEDLING_REPO_URL` (default: the public GitHub repo) — the source used
  when the installer isn't run from inside a checkout, and where
  `seed update-commands` fetches updates. A git URL or a plain directory path.
- `SEEDLING_HOME_DIR` (default: `~/seedling`) — the folder everything
  seedling manages lives in. A leading `~` means the installing user's
  home directory. The shell integration exports `SEEDLING_HOME` so
  seed-cli finds a custom location at runtime too.
- `SEEDLING_VENV_DEFAULT_PACKAGES` (default: `ipython,ruff,ipykernel`) —
  comma-separated packages installed into every new venv (seeds the
  `venv_default_packages` setting).
- `SEEDLING_AUTO_SETUP` (default: `yes`) — after installing seedling
  itself, install the newest stable Python and create a `dev` venv (with
  the default packages) that every new shell auto-activates. Set to `no`
  for a bare install; the `SEEDLING_AUTO_SETUP` environment variable
  overrides for one run. Never fatal: if this step fails (e.g. offline),
  seedling itself is still installed and working.
- `SEEDLING_AUTO_VSCODE` (default: `yes`) — also download and set up the
  portable VS Code during install, so `seed vscode` opens instantly
  instead of downloading ~130 MB on first use. Only applies when
  `SEEDLING_AUTO_SETUP` is `yes`.
- `SEEDLING_PYTHON_MIRROR` (default: empty = internet) — where `seed
  python` downloads interpreter builds: a URL of an internal mirror, or a
  plain directory of python-build-standalone archives on a share. Seeds
  the `python_mirror` setting.
- `SEEDLING_PACKAGE_INDEX` (default: empty = pypi.org) — where packages
  install from: an index URL, or a plain directory of wheels on a share
  (the internet index is then disabled entirely). Seeds the
  `package_index` setting. See [OFFLINE.md](OFFLINE.md) for the full
  offline deployment guide.
- `SEEDLING_NATIVE_TLS` (default: empty = bundled trust store) — set to
  `yes` to trust the operating system's certificate store, for internal
  HTTPS hosts signed by a machine-installed corporate CA (seeds the
  `native_tls` setting). Alternatively, ship the CA itself in
  `vendor/certs/` — see [OFFLINE.md](OFFLINE.md).

How it's applied: both installers read `seedling.conf` at the repo root
(a piped install reads the copy inside the repo it just cloned). The
install source is always recorded as `update_source`, and other values
that differ from the public defaults are written alongside it, into
`~/seedling/system/config/settings.json` on **first install only** — an
existing settings file is never overwritten, so later `seed config set`
choices survive reinstalls. Resolution order for the install source:

1. `SEEDLING_REPO` environment variable (one-run override)
2. `SEEDLING_REPO_URL` from `seedling.conf`
3. the baked-in public default (what the piped one-liner uses)

### Installing from a different source, for one run

`SEEDLING_REPO` accepts a git URL (a fork, or a self-hosted GitHub/GitLab
on another network) or a plain directory path (e.g. a network drive
holding a copy of this repo — no git hosting needed at all). When it's a
directory, the installer copies from it instead of cloning. Either way
the source is recorded as the `update_source` setting so
`seed update-commands` keeps working from it too.

```sh
SEEDLING_REPO=https://github.com/someone/fork.git sh ./install.cmd
SEEDLING_REPO=/mnt/share/seedling sh ./install.cmd
```
```powershell
$env:SEEDLING_REPO = "https://github.com/someone/fork.git"; .\install.cmd
$env:SEEDLING_REPO = "S:\shared\seedling"; .\install.cmd
```

### What the installer actually does, step by step

1. **Locates the source.** If run from inside a copy of this repo (it
   checks for `src/pyproject.toml`), it uses that. Otherwise it clones the
   resolved source via `git clone --depth 1`, or copies it if it's a
   directory path.
2. **Lays out `~/seedling/`** — `system/bin/`, `system/config/`,
   `system/shell/`, `python/base/`, `python/venvs/`, `extensions/`, `repo/`.
3. **Copies the source into `~/seedling/system/src`** — minus any `.git`
   folder: no git checkout lives inside seedling, and the origin is
   recorded in the `update_source` setting instead. This copy, not the
   original download/clone location, is what `seed-cli` actually gets
   installed from. See [The update model](#the-update-model).
   Any `vendor/` folder in the source (offline binaries: uv, portable
   git, pre-seeded VS Code — see [OFFLINE.md](OFFLINE.md)) is placed into
   its runtime locations at this point, and excluded from the copy.
4. **Installs `uv` into `~/seedling/system/bin`**, using uv's own official
   installer with `UV_INSTALL_DIR` redirected there and
   `UV_NO_MODIFY_PATH=1` set (seedling manages its own PATH/shell
   integration rather than letting uv touch your global PATH). Skipped if
   `~/seedling/system/bin/uv` already exists.
5. **Installs `~/seedling/system/src/src` as an isolated uv tool**, via
   `uv tool install --force --reinstall`, with `UV_TOOL_DIR` and
   `UV_TOOL_BIN_DIR` redirected into `~/seedling/system/tool` and
   `~/seedling/system/bin`. uv will fetch its own private Python
   interpreter for this if none is available — you still never need Python
   pre-installed. This produces the `seed-cli` binary/shim. `--reinstall`
   forces uv to bypass its build cache, which matters every time
   `seed update-commands` runs this same step later.
6. **Sets up the default environment** (unless `SEEDLING_AUTO_SETUP` is
   `no`, or a `dev` venv already exists from a previous install): installs
   the newest stable Python, creates a `dev` venv with the default
   packages, and records `dev` as the `default_venv` that new shells
   auto-activate — unless a different `default_venv` was already chosen.
   Also downloads the portable VS Code (unless `SEEDLING_AUTO_VSCODE` is
   `no`, or it's already present) so `seed vscode` opens instantly.
7. **Writes the shell integration.** Copies `seed.sh.template` /
   `seed.ps1.template` into `~/seedling/system/shell/seed.sh` (or `.ps1`),
   with the real `~/seedling` path substituted in, then appends a line to
   your shell profile (`.zshrc`, `.bashrc`, `.profile`, or `$PROFILE`) that
   sources it — only if that line isn't already present.

### Windows execution policy

Running `.\installers\install.ps1` directly, with no flags, fails with an
`is not digitally signed` error — that's Windows' default PowerShell policy
blocking unsigned local scripts, not a bug in the script. Three ways around
it:

- Use `install.cmd` instead — it launches `installers\install.ps1` with
  `-ExecutionPolicy Bypass` scoped to that single run only. It does not change your system-wide policy.
- Use the `irm | iex` one-liner — piping into `Invoke-Expression` never
  saves a local script file, so there's nothing for the policy to block.
- Run manually: `powershell -ExecutionPolicy Bypass -File .\installers\install.ps1`

**After a successful `install.cmd` run**, it opens a brand-new, ordinary
PowerShell window (profile loads normally, so `seed` is available right
away) with a short welcome banner listing the first few commands to try,
and leaves it open at an interactive prompt. This isn't just a convenience:
`install.cmd` itself runs in plain `cmd.exe`, and even drives `installers\install.ps1`
with `-NoProfile`, so there's no window at any point in that original
invocation where `seed` — a PowerShell function defined in `$PROFILE` —
could actually work. On failure, this window is skipped and the original
`cmd.exe` window instead pauses on the error so you can read it.

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
│   │   └── settings.json         seedling's own config -- see `seed config`
│   ├── logs/
│   │   └── seed-YYYY-MM-DD.log   every command + its output, one file per day
│   ├── cache/
│   │   └── uv/                   uv's package/interpreter download cache --
│   │                             kept in here instead of ~/.cache / %LOCALAPPDATA%
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
- `seed cd-repo [name]` → same trick as activate: the CLI resolves the
  repo's path (`--print-path`), and the function `cd`s the current shell
  there.
- **After every command**, the function checks whether the venv this shell
  has active still exists — if a `remove-venv`/`remove-venvs`/
  `remove-python`/`remove-user`/`purge` just deleted it, the shell
  deactivates it automatically (printing `(deactivated: the venv this
  shell had active no longer exists)`) instead of leaving a dangling
  prompt pointing at a folder that's gone.
- After `seed purge`/`seed remove-user`, the function also waits for the
  invisible self-deletion helper and prints the final confirmation — see
  [Why deletion is so defensive](#why-deletion-is-so-defensive).
- Every other subcommand is forwarded straight through to the real
  `seed-cli` binary as a normal subprocess.

If you invoke `seed-cli activate <name>` or `seed-cli deactivate` directly
(bypassing the shell function — e.g. by calling the binary path explicitly),
you'll get a message explaining that this only works through the `seed`
shell function, since a subprocess has no way to affect your shell.

---

## Why deletion is so defensive

Every command that deletes a directory (`remove-venv(s)`, `remove-python`,
`remove-repo`, `remove-user`, `purge`) routes through a shared helper
(`robust_rmtree`) that works around four real causes of "file in use" /
permission-denied failures, rather than just calling
`shutil.rmtree(path, ignore_errors=True)` and hoping:

1. **The calling process's own working directory being inside the folder
   being deleted.** Windows refuses to delete a directory that is any
   running process's cwd — including `seed-cli` itself. This is easy to hit
   in practice: activate a venv, `cd` into its project directory (or the
   venv folder itself), then run a remove/purge command from right there.
   The fix moves the process out to the user's home directory first, if
   its cwd is inside (or is) the target.
2. **A process that was just force-killed** (every delete command closes
   Python/VS Code processes first, see `seed kill-processes`) not having
   released its file handles instantly. The fix retries deletion a few
   times with a short delay instead of failing on the first pass.
3. **Read-only files.** Windows refuses to delete them outright, and git
   marks every file under `.git/objects` read-only — so any tree holding a
   git checkout (every cloned repo) would otherwise fail on hundreds of
   files at once. The error handler clears the read-only bit and retries
   each failed file individually.
4. **A program can't delete its own running executable.** `seed purge` and
   `seed remove-user` run *as* `seed-cli.exe` (plus the tool venv's
   `python.exe` underneath it), which live inside the very tree being
   deleted. When those are the only survivors, the command hands them to a
   small invisible helper that finishes the deletion a moment after
   `seed-cli` exits — and says so, instead of reporting an error. The
   `seed` shell function (still loaded in your session) then waits for the
   helper and prints an explicit confirmation — "Confirmed: ~/seedling has
   been fully removed" — or a warning with the leftover path if something
   is still holding files open, so the outcome is never silent.

If a file is genuinely still stuck after all retries — something *outside*
seedling holding it open — you get its exact path printed, instead of a
vague "something might be in use" message.

---

## Help output & color

`seed` (no arguments) or `seed -h`/`--help` shows commands grouped into
Python & venvs / Git repos / VS Code / Utilities / a "danger zone" for
everything destructive — rather than argparse's default flat, alphabetized
list, which stops being easy to scan once there are more than a handful of
commands. Subcommand-specific help (`seed venv -h`, etc.) is unaffected and
still uses argparse's normal per-command output.

Color (used for headers, warnings, and success messages) is automatically
disabled when stdout isn't a real terminal — piped output, redirected to a
file, CI logs — or when the `NO_COLOR` environment variable is set (per
[no-color.org](https://no-color.org)), so scripting against seedling's
output never has to deal with stray ANSI escape codes. On Windows, seedling
enables virtual terminal processing itself rather than requiring it be
turned on beforehand.

Output from the tools seedling drives is attributed in the terminal: lines
coming from uv are prefixed `[uv]`, and lines from git are prefixed
`[git]`, so it's always clear whether a message came from seedling itself
or from the tool underneath.

---

## Command logging

Every `seed` invocation appends to a daily log file under
`~/seedling/system/logs/` (e.g. `seed-2026-07-05.log`):

- the exact command line and a timestamp,
- everything the command printed — stdout *and* stderr, including the
  tagged `[uv]`/`[git]` output — with ANSI color codes stripped,
- and the exit code.

Log files older than 30 days are pruned automatically. Logging never
interferes with the command itself: if the log file can't be written, the
command carries on unlogged. Set `SEEDLING_NO_LOG=1` to disable logging for
a given call (the shell integration uses this itself for its startup
`default_venv` query, so opening a terminal doesn't spam the log).

---

## Non-interactive mode & previews

Every destructive command (`remove-python`, `remove-venv`, `remove-venvs`,
`remove-repo`, `remove-user`, `purge`, `kill-processes`) supports three
shared flags:

- `-y` / `--yes` — skip the confirmation prompt and proceed.
  (`SEEDLING_YES=1` is the environment equivalent.)
- `--preview` — print exactly what would be deleted (full paths; for
  `kill-processes`, the actual matching processes running right now), then
  exit without changing anything.
- `--non-interactive` — never wait for keyboard input. Anything that would
  have prompted aborts safely instead, unless `-y` was also given.
  (`SEEDLING_NONINTERACTIVE=1` is the environment equivalent.) This is the
  mode for scripts and CI, where a forgotten prompt would otherwise hang
  the job forever.

---

## Download verification

The two things seedling downloads itself as plain archives — portable
MinGit on Windows and VS Code — are verified against their publishers'
SHA-256 checksums before extraction (GitHub's release-asset digest for
MinGit; VS Code's update API hash for VS Code). A checksum mismatch deletes
the download and aborts with an explanation. If no checksum could be
obtained (e.g. the metadata endpoint is blocked on your network), the
download proceeds but says so explicitly. uv and Python interpreters are
installed by uv's own tooling, which does its own verification.

---

## Command reference

### `seed python [version]`

Installs a base CPython interpreter via `uv python install`, redirected
(via `UV_PYTHON_INSTALL_DIR`) into `~/seedling/python/base`. With no
version at all, installs the **newest stable Python** uv knows about and
derives the tag from what actually landed (e.g. `314`) — this is what the
installer's default-environment setup uses.

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

### `seed venv <name> [--python <tag>] [--no-default-packages]`

Creates a virtual environment at `~/seedling/python/venvs/<name>` via
`uv venv --python <interpreter>`, then installs the default packages
(`ipython`, `ruff`, and `ipykernel`, unless changed via
`seed config set venv_default_packages ...`) into it.

- `--python <tag>` selects which installed base Python to build from
  (matching a tag from `seed python`). If omitted, uses the default base
  (the first one installed).
- `--no-default-packages` (alias `--bare`) skips the default package
  install for just this venv. If the package install fails (e.g. offline),
  the venv itself is still created and usable.
- Fails with a clear message if the requested base isn't installed, or if
  a venv with that name already exists.
- uv's own output is shown as-is (interpreter resolution, creation
  confirmation) *except* for its "activate with: source .../activate" hint,
  which is filtered out -- that's not how `seed activate` actually works
  (it's a shell function, not a sourced script path), so showing it would
  just be confusing. seedling prints its own `seed activate <name>`
  instruction instead.

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

### `seed default-venv [name]`

Shows or sets the venv every **new** shell auto-activates on startup —
sugar for `seed config get/set default_venv`, promoted to its own command
because it's the setting people actually reach for. The installer's
default-environment setup points this at `dev`; switching it to your real
project is a natural next step.

- With a name: validates the venv exists, then sets it. Existing shells
  are unaffected — open a new terminal (or `seed activate <name>`).
- With no name: prints the current default (or that none is set).
- Clear it with `seed config unset default_venv` — new shells then start
  with no venv active.

```
seed default-venv
seed default-venv myproject
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
everything else, and your shell deactivates it automatically once it's
gone (see [Why `seed` is a shell function](#why-seed-is-a-shell-function)).
Prompts for confirmation unless `-y`/`--yes`.

Deletion itself uses a retrying, defensive helper shared by every
`remove-*`/`purge` command — see
[Why deletion is so defensive](#why-deletion-is-so-defensive)
for the bug this fixes and how.

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

### `seed vscode [path] [--reinstall] [--no-open]`

Opens VS Code at `path` (defaults to the current directory), installing a
fully portable copy into `~/seedling/extensions/vscode/app` first if none
exists — though a default install already did that up front (see
`SEEDLING_AUTO_VSCODE` in `seedling.conf`), so normally this just opens.
`--no-open` installs/verifies without opening a window (what the
installer's default setup uses).

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

Clones a git repository into `~/seedling/repo/<name>` via `git clone`. The
repo name is derived from the URL (handles `https://host/group/name.git`,
SSH-style `git@host:group/name.git`, and plain paths).

**git itself:** on Windows, if no system `git` is found, seedling
automatically downloads a portable copy ("MinGit", Git for Windows'
official dependency-free build — no installer, no admin rights) into
`~/seedling/extensions/git` and uses that. This is the only piece of
seedling bootstrapped this way, because it's the only platform with a
genuinely portable official build; on macOS and Linux, git is dynamically
linked against system libraries, so there's no equivalent to safely bundle.
There, if git isn't found, you'll get a clear one-line instruction
(`xcode-select --install`/`brew install git` on macOS; your distro's package
manager on Linux) instead of a silent failure.

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

### `seed cd-repo [name]`

Changes your **current shell's** directory to a cloned repo — the natural
follow-up to `seed clone-repo`, and the quickest way to run git commands
(`git status`, `git pull`, `git push`) against it. With no name, takes you
to `~/seedling/repo` itself. Errors (without moving) if the repo doesn't
exist.

Like `seed activate`, this only works through the `seed` shell function —
a child process can't change its parent shell's directory — so the CLI
resolves and validates the path, and the function does the actual `cd`
(see [Why `seed` is a shell function](#why-seed-is-a-shell-function)).

```
seed cd-repo myproject
seed cd-repo
```

### `seed vscode-repo <name>`

Opens a cloned repo in VS Code — installing VS Code first if it isn't
already (same one-time setup as `seed vscode`). Shares the same CLI-entry-
point, detached-process opening logic as `seed vscode`.

```
seed vscode-repo some-project
```

### `seed open-repo [name]`

Opens a cloned repo in the **operating system's file manager** (Explorer
on Windows, Finder on macOS, your desktop's default elsewhere). With no
name, opens `~/seedling/repo` itself. For opening in VS Code, use
`seed vscode-repo`.

```
seed open-repo some-project
seed open-repo
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

- If the `update_source` setting holds a git URL, downloads a fresh
  shallow clone of it into a temp folder, swaps it in as the new
  `~/seedling/system/src` (minus its `.git`), then reinstalls via
  `uv tool install --force --reinstall`.
- If `update_source` holds a directory path, re-copies from it instead
  (same swap, same reinstall).
- If no source is recorded, it just reinstalls from whatever is currently
  in `~/seedling/system/src`, which doubles as a repair command if you've
  hand-edited something there. A failed download also falls back to this,
  never leaving you without a working `seed`.

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
profile — use `seed purge` (or `uninstall.cmd` --
`sh ./uninstall.cmd` on macOS/Linux) for that.

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
This is the same end state as running `uninstall.cmd` (or
`sh ./uninstall.cmd` on macOS/Linux), just reachable from inside `seed` itself without needing
the original installer files around. Reports exactly which profile files
it edited.

**`--keep-repos`** moves `~/seedling/repo` out to a sibling folder
(`~/seedling-repo-backup`, or `-1`/`-2`/... if that already exists) before
deleting everything else, so your cloned repos survive the purge. Without
it, repos are deleted along with everything else — if you have cloned
repos and didn't pass the flag, the confirmation screen reminds you before
asking you to type `yes`, but there's a single confirmation gate either
way (no separate interactive question to answer differently).

Without `--keep-repos`, any leftover `~/seedling-repo-backup*` folder from a
*previous* `seed purge --keep-repos` is deleted too — the flag means "keep
repos this time," so leaving it off means you're saying you don't want
them kept around at all, and stale backups from an earlier purge would
otherwise just accumulate in your home directory forever.

The interactive confirmation screen also points out the alternatives
before you commit: how to preserve repos (`--keep-repos`), the smaller
partial-removal commands (`remove-venv`, `remove-venvs`, `remove-python`,
`remove-repo`, and `remove-user`, which keeps the shell hook), and the
reinstall instructions matched to how this copy was installed: the
public one-liners for a github.com install, "run the installer on the
share again" for a network-drive install, or "clone this URL" for a
self-hosted git install. The same instructions are printed again after a
successful purge — that's the last output `seed` ever produces, so it's
the last chance to see them.

```
seed purge
seed purge --keep-repos
seed purge -y --keep-repos
```

```
seed purge
```

### `seed where`

Prints the seedling home directory (`~/seedling`, or the value of the
`SEEDLING_HOME` environment variable override if set).

```
seed where
```

### `seed summary [--sizes]`

One read-only screen showing everything seedling has installed: uv/git/VS
Code status, every base Python (and which is default), every venv (its
Python version, which is active, which auto-activates in new shells),
every cloned repo with its origin remote, and all current settings.
`--sizes` also computes disk usage per item and a grand total (it walks
the whole tree, so it can take a few seconds on big installs).

```
seed summary
seed summary --sizes
```

### `seed status`

The health check. Verifies each moving part and prints one `OK` / `WARN` /
`FAIL` line per check: uv actually runs, git is available, the config file
parses, every base Python alias resolves to a real interpreter, every venv
has its interpreter and its base Python still exists, the configured
defaults (`default_base`, `default_venv`) point at things that exist, an
`update_source` is recorded (and, for a directory source, looks like a
seedling tree), any offline `python_mirror`/`package_index` directories
exist, the `seed` shell hook is installed and not stale (a hook line
pointing at a deleted file gets a loud warning), and the log directory is
writable.

`FAIL` means a core operation would not work right now and makes the
command exit 1 (useful in scripts/CI); `WARN` is informational (nothing
installed yet, no git, etc.) and doesn't affect the exit code.

```
seed status
```

### `seed config [get <key> | set <key> <value> | unset <key>]`

Views and changes seedling's own settings, stored in
`~/seedling/system/config/settings.json`. Bare `seed config` lists every
setting with its current value and an explanation. The keys:

- `default_base` — the base Python tag `seed venv` builds from when
  `--python` isn't given. Set automatically by your first `seed python`.
- `default_venv` — a venv name that **every new shell auto-activates** on
  startup. Unset means no auto-activation. (Existing shells are
  unaffected; open a new terminal to see it.)
- `update_source` — where `seed update-commands` gets seedling's own
  source: a git URL (works with self-hosted GitHub/GitLab on isolated
  networks) *or* a plain directory path (e.g. a network drive holding a
  copy of the repo, for machines with no git hosting at all). Recorded
  automatically at install time; unset means updates can only reinstall
  the existing copy.
- `venv_default_packages` — the packages installed into every new venv
  (default: `ipython, ruff, ipykernel`). Takes comma-separated input.
- `python_mirror` / `package_index` — offline sources for interpreters
  and packages (a URL, or a plain directory on a share). Normally seeded
  from `seedling.conf` at install time; see [OFFLINE.md](OFFLINE.md).
- `native_tls` / `ca_cert` — HTTPS trust for corporate-CA internal hosts:
  the OS trust store, or a PEM bundle (normally installed automatically
  from `vendor/certs/`). Applied to uv, git, and seedling's own downloads
  on every command.

`seed config get <key>` prints just the value (nothing at all when unset),
so it's script-friendly. `unset` resets a key to its built-in default.

```
seed config
seed config set default_venv myproject
seed config set update_source https://github.mycompany.com/tools/seedling.git
seed config set update_source "S:\shared\seedling"
seed config set venv_default_packages "ipython,ruff,requests"
seed config unset default_venv
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

`~/seedling/system/src` is a plain copy of the source — deliberately NOT
a git checkout (no `.git` folder lives inside seedling). Instead, the
installer records where the source came from in the `update_source`
setting, and `seed update-commands` re-fetches from there: a fresh shallow
`git clone` for a URL, a re-copy for a directory path (see `seed config`).

If no source is recorded, it just reinstalls from whatever's currently in
`~/seedling/system/src`, so it doubles as a "repair" command if you've
hand-edited something. Note that updating *overwrites* the private copy —
hand-edits there don't survive an update (edit and reinstall from a real
checkout instead if you're developing seedling itself).

The installers accept the same flexibility up front: `SEEDLING_REPO` may
be a git URL *or* a directory containing a copy of this repo. When it's a
directory, the installer copies from it and records it as `update_source`
automatically, so machines on networks without github.com stay updatable.

---

## Uninstalling

- `seed remove-user` — removes everything *seedling manages* (Python
  installs, venvs, VS Code, cloned repos, uv, its own source) but leaves
  the `seed` shell hook in your profile.
- `seed purge`, or `uninstall.cmd` (`sh ./uninstall.cmd` on macOS/Linux) —
  removes the `seed` shell hook from your profile **and** deletes
  `~/seedling` entirely, for a full clean removal. `seed purge` is the same
  operation reachable from inside `seed` itself, for when you don't have
  the original installer files handy.

---

## Troubleshooting

**"is not digitally signed. You cannot run this script on the current
system"** — see [Windows execution policy](#windows-execution-policy).

**`iex : Cannot bind argument to parameter 'Path' because it is null`**
when running the `irm ... | iex` one-liner — you're running a stale cached
copy of the install script; re-fetch it (or download the repo and run
`install.cmd` instead).

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

**`git isn't installed, and seedling can't bundle a portable copy on
<macOS/Linux>`** — install git through your OS's package manager (the error
message tells you the exact command for your platform) and try again. On
Windows this shouldn't happen — seedling downloads a portable copy
automatically — but if it does (e.g. GitHub API rate-limiting), the error
message includes a manual download link and the exact folder to extract it
into.

---

## Known limits

- `seed vscode`/`seed vscode-repo` on macOS unpack the official `.app` bundle
  and launch its embedded CLI binary; this is the least-tested of the
  three platforms.
- `seed python` version resolution assumes CPython (uv's default); PyPy and
  other implementations aren't wired up.
- `seed kill-processes` (and everything that reuses it) is machine-wide,
  not seedling-scoped, by design — see the command reference above.
- `seed clone-repo`/`install-repo` need git; only Windows is auto-bootstrapped
  (via portable MinGit) — macOS/Linux still need system git already present,
  since neither has an equivalent official portable build.
- `seed install-repo` only recognizes `pyproject.toml` and
  `requirements.txt` — repos using other dependency files (e.g. Poetry's
  `poetry.lock` without a PEP 621 `pyproject.toml` section, or Pipenv) may
  need manual installation.
- The installers assume `curl`/`wget` (POSIX) or PowerShell's
  `Invoke-RestMethod` are available, which is true by default on
  effectively every macOS/Linux/Windows 10+ machine.
