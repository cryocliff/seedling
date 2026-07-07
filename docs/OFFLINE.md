# Running seedling on an offline network

seedling was designed so that an organization on an isolated network — no
github.com, no pypi.org, no internet at all — can still install it, use it,
and keep it updated. This page lists **every component that normally comes
from the internet**, when it's needed, and what to provide instead.

The audience here is whoever prepares the deployment (a shared drive or a
self-hosted git server). End users on the offline network never deal with
any of this — they run `install.cmd` from the share and everything works.

---

## The short version

Everything is driven by **editing [`seedling.conf`](../seedling.conf)** in
the copy of the repo you distribute — users never set environment
variables or change anything on their machines. You provide **four
things** (plus two optional ones):

| # | Component | What to provide |
|---|-----------|-----------------|
| 1 | seedling's own source | A copy of this repo on a network share (or self-hosted git) — set `SEEDLING_REPO_URL` in `seedling.conf` |
| 2 | The `uv` binary | Drop it in `vendor/uv/` inside your repo copy — the installer places it automatically |
| 3 | Python interpreters | An internal mirror (or share folder) of `python-build-standalone` archives — set `SEEDLING_PYTHON_MIRROR` in `seedling.conf` |
| 4 | Python packages | An internal index (Artifactory / Nexus / devpi) or a plain directory of wheels — set `SEEDLING_PACKAGE_INDEX` in `seedling.conf`; must include `hatchling` |
| 5 | git *(optional)* | Drop MinGit in `vendor/git/`, or deploy git through your normal software channel |
| 6 | VS Code *(optional)* | Drop a pre-seeded portable install in `vendor/vscode/` |

The conf values are recorded in seedling's settings at install time and
applied automatically to every command from then on (visible and
changeable later via `seed config`).

Everything in seedling that *isn't* a download — venvs, activation, config,
logging, previews, removal commands, directory-based updates — already
works with zero network access.

---

## The `vendor/` convention

Binaries that can't come from a URL/directory setting are handled by a
single convention: a **`vendor/` folder inside the copy of the repo you
distribute**. The installer copies whatever it finds there into place
*before* any download step runs (each of which skips itself when its
target already exists) — presence equals intent, no wrapper scripts, no
configuration:

Every payload is a folder whose contents go to the destination:

```
vendor/uv/         (uv.exe or uv, uvx too if present) -> ~/seedling/system/bin/
vendor/git/        (an extracted MinGit)              -> ~/seedling/extensions/git/
vendor/vscode/     (a pre-seeded portable VS Code)    -> ~/seedling/extensions/vscode/
```

Reinstalls never overwrite binaries already in place, `vendor/` is
excluded from seedling's private source copy and from updates (a
pre-seeded VS Code would otherwise bloat `system/src` by hundreds of MB),
and the folder is gitignored — it exists only on distribution media.

---

## What seedling downloads, and when

| Download | From | When it happens |
|---|---|---|
| seedling source | github.com (default) | Install; `seed update-commands` |
| `uv` binary | astral.sh | Install (skipped if already present) |
| CPython interpreters | github.com (python-build-standalone releases) | `seed python`; the installer's default-environment setup; first `uv tool install` if no Python exists on the machine |
| Python packages (incl. `hatchling` to build seed-cli, and the default venv packages `ipython`/`ruff`) | pypi.org | Install; `seed venv`; `seed install`; `seed update-commands` |
| MinGit (Windows only) | github.com (git-for-windows releases) | First `seed clone-repo` if no git is found |
| VS Code + extensions | update.code.visualstudio.com / marketplace.visualstudio.com | First `seed vscode` / `seed open-repo` |

---

## 1. seedling's own source — built-in support

Put a copy of this repo on a network share (say `S:\tools\seedling`), edit
[`seedling.conf`](../seedling.conf) in that copy, and users install by
running `install.cmd` from it (or with
`SEEDLING_REPO=S:\tools\seedling` from anywhere). The installer records the
share as `update_source`, so `seed update-commands` re-copies from it —
**no git involved anywhere** in this flow. To ship an update, replace the
contents of the share.

A self-hosted git server (GitHub Enterprise, GitLab, Gitea) works the same
way with a URL instead of a path; updates then do a fresh shallow clone,
which requires git on user machines (see #5).

---

## 2. The `uv` binary

The installers normally download uv from `astral.sh` — but they **skip that
step entirely if uv is already in place**:

- Windows: `~\seedling\system\bin\uv.exe`
- macOS/Linux: `~/seedling/system/bin/uv`

So the offline recipe is: download uv's standalone binary once (from
[github.com/astral-sh/uv/releases](https://github.com/astral-sh/uv/releases),
on a connected machine) and drop it into `vendor/uv/` in your repo copy —
the installer places it automatically. Pin one uv version for the whole organization and update it deliberately —
that also pins which Python versions "newest" resolves to.

---

## 3. Python interpreters

`seed python` (and `uv tool install`, when no usable Python exists on the
machine) downloads CPython builds from the
[python-build-standalone](https://github.com/astral-sh/python-build-standalone)
GitHub releases. To redirect this:

1. Mirror the release archives you need onto an internal web server or
   file share (only the platforms/versions you actually use — one
   `cpython-<version>-windows-x86_64-none` archive is ~30 MB).
2. Set **`SEEDLING_PYTHON_MIRROR`** in `seedling.conf` to that location —
   a URL, or just the share path (`S:\tools\python-builds`); seedling
   converts paths to the `file://` form uv needs.

The installer applies it to its own default-environment setup and records
it as the `python_mirror` setting, which every later `seed python` applies
automatically.

---

## 4. Python packages

`seed venv` (default packages), `seed install`, and building seed-cli
itself all resolve packages from PyPI. Redirect this by setting
**`SEEDLING_PACKAGE_INDEX`** in `seedling.conf` to either:

- an **index URL** (any pip-compatible index: Artifactory, Nexus, devpi),
  or
- a **plain directory of wheels** (e.g. a network share folder). seedling
  then generates a uv configuration declaring that directory as the one
  and only package source, with the internet index disabled entirely — a
  package that isn't in the folder fails cleanly instead of silently
  reaching for pypi.org.

Like the mirror, it's applied during install itself (building seed-cli
needs it) and recorded as the `package_index` setting for every later
command. The index/directory must contain at minimum:

- **`hatchling`** (and its dependencies `packaging`, `pathspec`,
  `pluggy`, `trove-classifiers`) — uv needs it to **build seed-cli from
  source** during install and every `seed update-commands`.
- **the default venv packages** (`ipython`, `ruff`, `ipykernel`, `pip`, and their dependencies)
  for every new venv. If your organization prefers a different set, change
  `SEEDLING_VENV_DEFAULT_PACKAGES` in `seedling.conf` and stock those
  instead.
- Whatever your users actually `seed install`.

---

## 5. git (optional)

git is needed for exactly two things, both avoidable:

- **`seed clone-repo`** — cloning your internal repos. If your git host is
  on the internal network, users need a git client: extract
  [MinGit](https://github.com/git-for-windows/git/releases) (Windows) into
  `vendor/git/` in your repo copy — the installer places it at
  `~\seedling\extensions\git\`, which seedling checks right after PATH
  and never re-downloads from — or deploy git through your normal
  software channel.
- **URL-based `seed update-commands`** — only if your `update_source` is a
  git URL. A directory `update_source` (the network-share flow above)
  needs no git at all.

If neither applies, skip this component entirely.

---

## 6. VS Code (optional)

`seed vscode` downloads VS Code from Microsoft's update API and extensions
from the marketplace — neither has a supported mirror. Two options:

- **Pre-seed it**: run `seed vscode` once on a connected machine, then copy
  the resulting `~/seedling/extensions/vscode/` folder into `vendor/vscode/`
  in your repo copy — the installer places it on each machine, and seedling
  detects the existing install and never re-downloads. VS Code is fully
  portable in this layout — settings and extensions travel with the folder.
- **Skip it**: everything else in seedling works without VS Code; users
  bring whatever editor your organization deploys.

Additional extensions on an offline network must be installed from `.vsix`
files (`code --install-extension foo.vsix`), downloadable from the
marketplace website on a connected machine.

---

## The default environment setup

A standard install ends by installing the newest Python and creating the
auto-activated `dev` venv. Offline, this works **only if #3 and #4 are in
place** (it needs an interpreter archive and the `ipython`/`ruff`
packages), and the VS Code part only works pre-seeded (#6) — otherwise set
`SEEDLING_AUTO_VSCODE="no"` alongside it. If none of it is ready yet, set
`SEEDLING_AUTO_SETUP="no"` in your distributed `seedling.conf` — the install then finishes bare but working,
and the setup can be run later per-machine:

```
seed python && seed venv dev && seed config set default_venv dev
```

A failed auto-setup is never fatal either way — seedling itself still
installs; users just see a warning with those same commands.

---

## Putting it together: preparing the share

On a connected machine:

```
S:\tools\seedling\                     <- a copy of this repo
S:\tools\seedling\vendor\uv\           <- pinned uv binary (placed automatically)
S:\tools\seedling\vendor\git\          <- (optional) extracted MinGit
S:\tools\seedling\vendor\vscode\       <- (optional) pre-seeded portable VS Code
S:\tools\python-builds\                <- python-build-standalone archives
S:\tools\wheels\                       <- wheels: hatchling + the default venv packages + your org's packages
```

And in `S:\tools\seedling\seedling.conf` — the **only file anyone edits**:

```
SEEDLING_REPO_URL="S:\tools\seedling"
SEEDLING_PYTHON_MIRROR="S:\tools\python-builds"
SEEDLING_PACKAGE_INDEX="S:\tools\wheels"
```

Then a user runs `S:\tools\seedling\install.cmd` and gets the full
experience — newest mirrored Python, `dev` venv with your default
packages auto-activated, and `seed update-commands` flowing from the share
— without their machine ever attempting to reach the internet, and without
setting a single environment variable.

---

## Variant: nothing but a shared drive

An organization whose only common infrastructure is a **file share between
machines** — no internal web servers, no git host, no index server — can
still run everything. Each server-shaped component above has a plain-files
equivalent:

| Component | Share-only equivalent |
|---|---|
| seedling source + updates | Already file-based (#1) — the ideal case |
| Python interpreter mirror | `SEEDLING_PYTHON_MIRROR="S:\tools\python-builds"` — a share folder of archives; seedling handles the `file://` conversion |
| Package index | `SEEDLING_PACKAGE_INDEX="S:\tools\wheels"` — a **directory of wheels** on the share; the internet index is disabled automatically. Populate it on a connected machine with `pip download -d` (include `hatchling`, the default venv packages, and all transitive deps for your platform) |
| git hosting | git needs no server: **bare repositories on the share** (`git init --bare S:/repos/project.git`) are full remotes — `seed clone-repo S:/repos/project.git`, push, and pull all work over git's file protocol |
| VS Code | Pre-seeded portable folder in `vendor/vscode/`, as above (#6) |

Practical notes for this setup: since all users are on the same platform
(typical for VM fleets), the wheel directory stays small and single-arch;
a missing transitive dependency fails resolution outright rather than
falling back, so test the wheel set by creating a venv from a clean
machine; and file-protocol git remotes rely on share permissions for
access control.

---

## Known degradations offline

- **Download checksum lookups** (used for MinGit and VS Code metadata)
  aren't reachable — irrelevant in practice, since those downloads don't
  happen offline; anything pre-seeded was verified when you fetched it.
- **`seed python` "newest"** means the newest your pinned uv knows about
  and your mirror stocks — update the uv binary and mirror together.
- The conf values translate into uv's own knobs under the hood
  (`UV_PYTHON_INSTALL_MIRROR`, `UV_DEFAULT_INDEX`, or a generated
  `system/config/uv.toml`). A power user who sets those `UV_*` environment
  variables explicitly still wins over the config — useful for one-off
  experiments, never required.
