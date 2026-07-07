#!/usr/bin/env sh
# seedling installer (bash/zsh/sh) -- mirrors how `uv` installs itself.
# Requires nothing pre-installed except a POSIX shell and curl/wget (both
# already present on essentially every macOS/Linux system).
#
# Usage (from a local checkout of this repo, either works):
#   sh ./install.cmd
#   sh installers/install.sh
#
# Usage (remote):
#   curl -fsSL https://raw.githubusercontent.com/cryocliff/seedling/main/installers/install.sh | sh
#   SEEDLING_REPO=https://github.com/someone/fork.git curl -fsSL .../installers/install.sh | sh

set -eu

# Built-in defaults. seedling.conf ships with these same values written
# out, so a conf that still matches them changes nothing -- only edited
# values have any effect. The baked-in copies exist for the piped
# one-liner install, where no local seedling.conf exists yet to consult.
DEFAULT_SEEDLING_REPO="https://github.com/cryocliff/seedling.git"
DEFAULT_VENV_PACKAGES="ipython,ruff,ipykernel,pip"

SEEDLING_REPO_FROM_ENV="${SEEDLING_REPO:-}"
SEEDLING_HOME_FROM_ENV="${SEEDLING_HOME:-}"
SEEDLING_AUTO_SETUP_FROM_ENV="${SEEDLING_AUTO_SETUP:-}"
SEEDLING_AUTO_VSCODE_FROM_ENV="${SEEDLING_AUTO_VSCODE:-}"

info()  { printf '\033[1;32m==>\033[0m %s\n' "$1"; }
warn()  { printf '\033[1;33m!!\033[0m %s\n' "$1"; }
die()   { printf '\033[1;31merror:\033[0m %s\n' "$1" >&2; exit 1; }

# ---------------------------------------------------------------------------
# 1. Locate the seedling source (local checkout next to this script, or clone)
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
# This script lives in installers/; the repo root (seedling.conf, src/) is
# one level up.
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

# seedling.conf at the repo root is the deployment config: organizations
# distributing seedling from their own git host or a network drive set the
# source (and any install-time settings) there ONCE, and their users install
# with no flags or env vars. Standard internet installs ship a conf whose
# values match the baked-in defaults, so nothing changes for them.
SEEDLING_REPO_URL=""
SEEDLING_HOME_DIR=""
SEEDLING_VENV_DEFAULT_PACKAGES=""
SEEDLING_AUTO_SETUP=""
SEEDLING_AUTO_VSCODE=""
SEEDLING_PYTHON_MIRROR=""
SEEDLING_PACKAGE_INDEX=""
CONF_FILE=""
if [ -f "$REPO_ROOT/seedling.conf" ]; then
    CONF_FILE="$REPO_ROOT/seedling.conf"
    . "$CONF_FILE"
fi

# Source resolution: SEEDLING_REPO env var (one-run override) beats
# seedling.conf, which beats the baked-in default.
if [ -n "$SEEDLING_REPO_FROM_ENV" ]; then
    SEEDLING_REPO="$SEEDLING_REPO_FROM_ENV"
elif [ -n "$SEEDLING_REPO_URL" ]; then
    SEEDLING_REPO="$SEEDLING_REPO_URL"
else
    SEEDLING_REPO="$DEFAULT_SEEDLING_REPO"
fi

# Home resolution follows the same order. A leading "~" in the conf value
# means the installing user's home directory.
if [ -n "$SEEDLING_HOME_FROM_ENV" ]; then
    SEEDLING_HOME="$SEEDLING_HOME_FROM_ENV"
elif [ -n "$SEEDLING_HOME_DIR" ]; then
    case "$SEEDLING_HOME_DIR" in
        "~")   SEEDLING_HOME="$HOME" ;;
        "~/"*) SEEDLING_HOME="$HOME/${SEEDLING_HOME_DIR#??}" ;;
        *)     SEEDLING_HOME="$SEEDLING_HOME_DIR" ;;
    esac
else
    SEEDLING_HOME="$HOME/seedling"
fi

INSTALLED_FROM_DIR=""
CLONE_MODE=0
if [ -f "$REPO_ROOT/src/pyproject.toml" ]; then
    ORIGINAL_SRC="$REPO_ROOT"
    CLEANUP_ORIGINAL_SRC=0
elif [ -d "$SEEDLING_REPO" ] && [ -f "$SEEDLING_REPO/src/pyproject.toml" ]; then
    # SEEDLING_REPO can be a plain directory instead of a git URL -- e.g. a
    # network drive holding a copy of this repo, on machines/networks with
    # no GitHub access at all.
    info "Installing from directory $SEEDLING_REPO ..."
    ORIGINAL_SRC="$SEEDLING_REPO"
    CLEANUP_ORIGINAL_SRC=0
    INSTALLED_FROM_DIR="$SEEDLING_REPO"
else
    command -v git >/dev/null 2>&1 || die "git is required to clone $SEEDLING_REPO."
    ORIGINAL_SRC="$(mktemp -d)"
    CLEANUP_ORIGINAL_SRC=1
    CLONE_MODE=1
    info "Cloning $SEEDLING_REPO ..."
    git clone --depth 1 "$SEEDLING_REPO" "$ORIGINAL_SRC"
fi

# ---------------------------------------------------------------------------
# 2. Lay out the folder structure
# ---------------------------------------------------------------------------
info "Setting up $SEEDLING_HOME"
mkdir -p "$SEEDLING_HOME/system/bin" \
         "$SEEDLING_HOME/system/config" \
         "$SEEDLING_HOME/system/shell" \
         "$SEEDLING_HOME/python/base" \
         "$SEEDLING_HOME/python/venvs" \
         "$SEEDLING_HOME/extensions" \
         "$SEEDLING_HOME/repo"

# ---------------------------------------------------------------------------
# 2b. Copy the source INTO seedling itself. This is what makes updates
#     explicit: seed-cli gets installed from $SEEDLING_HOME/src, a copy that
#     nothing outside of `seed update-commands` ever touches again. Deleting,
#     moving, or `git pull`-ing wherever you originally downloaded this from
#     has zero effect on the installed commands after this point.
# ---------------------------------------------------------------------------
info "Copying source into $SEEDLING_HOME/system/src ..."
rm -rf "$SEEDLING_HOME/system/src"
cp -R "$ORIGINAL_SRC" "$SEEDLING_HOME/system/src"
SRC_DIR="$SEEDLING_HOME/system/src"
# No git checkout lives inside ~/seedling: updates re-download from the
# recorded update_source (see below) instead of `git pull`-ing, so the
# .git folder would be dead weight (and its read-only object files used
# to break deletion on Windows).
rm -rf "$SRC_DIR/.git"

if [ "$CLEANUP_ORIGINAL_SRC" = "1" ]; then
    rm -rf "$ORIGINAL_SRC"
fi

# ---------------------------------------------------------------------------
# 2c. Seed seedling's settings from seedling.conf (first install only --
#     an existing settings.json is never touched, so reinstalls don't
#     clobber choices made later with `seed config set`).
# ---------------------------------------------------------------------------
# Piped installs have no local conf, but the clone we just copied does.
if [ -z "$CONF_FILE" ] && [ -f "$SRC_DIR/seedling.conf" ]; then
    . "$SRC_DIR/seedling.conf"
fi

# Record where this install came from, so `seed update-commands` knows
# where to fetch newer versions (there's no git checkout inside ~/seedling
# to pull with -- updating re-downloads from this source instead):
#   - directory install  -> that directory
#   - cloned from a URL  -> that URL
#   - local checkout     -> the checkout's own origin remote if it has one,
#                           else whatever URL the conf/default resolved to
UPDATE_SOURCE_SEED=""
if [ -n "$INSTALLED_FROM_DIR" ]; then
    UPDATE_SOURCE_SEED="$INSTALLED_FROM_DIR"
elif [ "$CLONE_MODE" = "1" ]; then
    UPDATE_SOURCE_SEED="$SEEDLING_REPO"
else
    # Local checkout. An explicit env var or an org-edited conf states
    # intent and wins; otherwise use the checkout's own origin remote;
    # otherwise fall back to the resolved (default) URL.
    if [ -n "$SEEDLING_REPO_FROM_ENV" ]; then
        UPDATE_SOURCE_SEED="$SEEDLING_REPO"
    elif [ -n "$SEEDLING_REPO_URL" ] && [ "$SEEDLING_REPO_URL" != "$DEFAULT_SEEDLING_REPO" ]; then
        UPDATE_SOURCE_SEED="$SEEDLING_REPO_URL"
    elif command -v git >/dev/null 2>&1 && [ -d "$REPO_ROOT/.git" ]; then
        UPDATE_SOURCE_SEED="$(git -C "$REPO_ROOT" remote get-url origin 2>/dev/null || true)"
    fi
    [ -n "$UPDATE_SOURCE_SEED" ] || UPDATE_SOURCE_SEED="$SEEDLING_REPO"
fi

SETTINGS_FILE="$SEEDLING_HOME/system/config/settings.json"
if [ ! -f "$SETTINGS_FILE" ]; then
    json_escape() { printf '%s' "$1" | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g'; }
    entries=""
    if [ -n "$UPDATE_SOURCE_SEED" ]; then
        entries="  \"update_source\": \"$(json_escape "$UPDATE_SOURCE_SEED")\""
    fi
    # Only seed the package list when it was actually changed -- the conf
    # ships with the built-in default written out for discoverability.
    pkgs_norm=$(printf '%s' "$SEEDLING_VENV_DEFAULT_PACKAGES" | tr -d ' ')
    if [ -n "$pkgs_norm" ] && [ "$pkgs_norm" != "$DEFAULT_VENV_PACKAGES" ]; then
        pkgs=""
        OLD_IFS=$IFS; IFS=,
        for p in $SEEDLING_VENV_DEFAULT_PACKAGES; do
            p=$(printf '%s' "$p" | sed -e 's/^ *//' -e 's/ *$//')
            [ -z "$p" ] && continue
            [ -n "$pkgs" ] && pkgs="$pkgs, "
            pkgs="$pkgs\"$(json_escape "$p")\""
        done
        IFS=$OLD_IFS
        if [ -n "$pkgs" ]; then
            [ -n "$entries" ] && entries="$entries,
"
            entries="$entries  \"venv_default_packages\": [$pkgs]"
        fi
    fi
    # Offline sources (see docs/OFFLINE.md): recorded so every future
    # `seed` command applies them automatically -- users never set
    # environment variables themselves.
    if [ -n "$SEEDLING_PYTHON_MIRROR" ]; then
        [ -n "$entries" ] && entries="$entries,
"
        entries="$entries  \"python_mirror\": \"$(json_escape "$SEEDLING_PYTHON_MIRROR")\""
    fi
    if [ -n "$SEEDLING_PACKAGE_INDEX" ]; then
        [ -n "$entries" ] && entries="$entries,
"
        entries="$entries  \"package_index\": \"$(json_escape "$SEEDLING_PACKAGE_INDEX")\""
    fi
    if [ -n "$entries" ]; then
        printf '{\n%s\n}\n' "$entries" > "$SETTINGS_FILE"
        info "Seeded seedling settings from seedling.conf"
    fi
fi

# ---------------------------------------------------------------------------
# 2d. Apply the offline sources to THIS installer's own uv/seed-cli calls
#     too (building seed-cli needs the package index; the default
#     environment setup needs both). Pre-set UV_* variables still win.
# ---------------------------------------------------------------------------
to_file_url() {
    _v=$(printf '%s' "$1" | tr '\\' '/')
    case "$_v" in
        *"://"*)     printf '%s' "$_v" ;;
        [A-Za-z]:/*) printf 'file:///%s' "$_v" ;;
        /*)          printf 'file://%s' "$_v" ;;
        *)           printf '%s' "$_v" ;;
    esac
}

if [ -n "$SEEDLING_PYTHON_MIRROR" ] && [ -z "${UV_PYTHON_INSTALL_MIRROR:-}" ]; then
    UV_PYTHON_INSTALL_MIRROR="$(to_file_url "$SEEDLING_PYTHON_MIRROR")"
    export UV_PYTHON_INSTALL_MIRROR
fi
if [ -n "$SEEDLING_PACKAGE_INDEX" ]; then
    case "$SEEDLING_PACKAGE_INDEX" in
        *"://"*)
            if [ -z "${UV_DEFAULT_INDEX:-}" ]; then
                UV_DEFAULT_INDEX="$SEEDLING_PACKAGE_INDEX"
                export UV_DEFAULT_INDEX
            fi
            ;;
        *)
            # A directory of wheels: uv has no reliable env var for "flat
            # directory index, internet disabled", but honors a config
            # file. seed-cli generates the same file from settings later.
            if [ -z "${UV_CONFIG_FILE:-}" ]; then
                UV_TOML="$SEEDLING_HOME/system/config/uv.toml"
                {
                    echo "# Generated by seedling from the \`package_index\` setting. Do not edit;"
                    echo "# change it with:  seed config set package_index <url-or-directory>"
                    echo "[[index]]"
                    echo "name = \"seedling-offline\""
                    echo "url = \"$(to_file_url "$SEEDLING_PACKAGE_INDEX")\""
                    echo "format = \"flat\""
                    echo "default = true"
                } > "$UV_TOML"
                UV_CONFIG_FILE="$UV_TOML"
                export UV_CONFIG_FILE
            fi
            ;;
    esac
fi


# ---------------------------------------------------------------------------
# 3. Install uv itself into seedling/bin (uv is the one true dependency, and
#    its own official installer has zero prerequisites, same as this script)
# ---------------------------------------------------------------------------
if [ ! -x "$SEEDLING_HOME/system/bin/uv" ]; then
    info "Installing uv into $SEEDLING_HOME/system/bin ..."
    if command -v curl >/dev/null 2>&1; then
        env UV_INSTALL_DIR="$SEEDLING_HOME/system/bin" UV_NO_MODIFY_PATH=1 \
            sh -c "$(curl -fsSL https://astral.sh/uv/install.sh)"
    elif command -v wget >/dev/null 2>&1; then
        env UV_INSTALL_DIR="$SEEDLING_HOME/system/bin" UV_NO_MODIFY_PATH=1 \
            sh -c "$(wget -qO- https://astral.sh/uv/install.sh)"
    else
        die "Neither curl nor wget is available; cannot bootstrap uv."
    fi
else
    info "uv already present, skipping."
fi

UV="$SEEDLING_HOME/system/bin/uv"
[ -x "$UV" ] || die "uv install appears to have failed (not found at $UV)."

# ---------------------------------------------------------------------------
# 4. Install the seedling CLI itself as an isolated uv tool, from the copy
#    living inside ~/seedling/src (not the original download location).
#    `seed update-commands` is the only thing that ever re-runs this step.
# ---------------------------------------------------------------------------
info "Installing the seedling CLI ..."
env UV_TOOL_DIR="$SEEDLING_HOME/system/tool" UV_TOOL_BIN_DIR="$SEEDLING_HOME/system/bin" \
    UV_CACHE_DIR="$SEEDLING_HOME/system/cache/uv" \
    "$UV" tool install --force --reinstall "$SRC_DIR/src"

[ -x "$SEEDLING_HOME/system/bin/seed-cli" ] || die "seed-cli was not installed correctly."
SEED_CLI="$SEEDLING_HOME/system/bin/seed-cli"

# ---------------------------------------------------------------------------
# 4b. Default environment: the newest stable Python plus a 'dev' venv (with
#     the default packages) that every new shell auto-activates -- so a
#     fresh install is immediately usable with plain `python`/`ipython`.
#     Skip with SEEDLING_AUTO_SETUP=no (env var or seedling.conf). Never
#     fatal: a network hiccup here still leaves a working seedling.
# ---------------------------------------------------------------------------
if [ -n "$SEEDLING_AUTO_SETUP_FROM_ENV" ]; then
    AUTO_SETUP="$SEEDLING_AUTO_SETUP_FROM_ENV"
elif [ -n "$SEEDLING_AUTO_SETUP" ]; then
    AUTO_SETUP="$SEEDLING_AUTO_SETUP"
else
    AUTO_SETUP="yes"
fi

DEV_READY=0
case "$AUTO_SETUP" in
    no|NO|No|0|false|FALSE)
        info "Skipping default environment setup (SEEDLING_AUTO_SETUP=$AUTO_SETUP)."
        ;;
    *)
        if [ -d "$SEEDLING_HOME/python/venvs/dev" ]; then
            info "Default 'dev' venv already exists, leaving it as-is."
            DEV_READY=1
        else
            info "Setting up the default environment: newest Python + a 'dev' venv ..."
            if env SEEDLING_HOME="$SEEDLING_HOME" "$SEED_CLI" python && \
               env SEEDLING_HOME="$SEEDLING_HOME" "$SEED_CLI" venv dev; then
                # Make 'dev' the venv new shells auto-activate -- unless the
                # user already chose one (reinstall case).
                if [ -z "$(env SEEDLING_HOME="$SEEDLING_HOME" SEEDLING_NO_LOG=1 "$SEED_CLI" config get default_venv 2>/dev/null)" ]; then
                    env SEEDLING_HOME="$SEEDLING_HOME" "$SEED_CLI" config set default_venv dev
                fi
                DEV_READY=1
            else
                warn "Default environment setup didn't finish (network problem?)."
                warn "Set it up later with:  seed python && seed venv dev && seed config set default_venv dev"
            fi
        fi

        # VS Code too, so `seed vscode` opens instantly instead of
        # downloading on first use. Idempotent (skips if already present)
        # and never fatal.
        if [ -n "$SEEDLING_AUTO_VSCODE_FROM_ENV" ]; then
            AUTO_VSCODE="$SEEDLING_AUTO_VSCODE_FROM_ENV"
        elif [ -n "$SEEDLING_AUTO_VSCODE" ]; then
            AUTO_VSCODE="$SEEDLING_AUTO_VSCODE"
        else
            AUTO_VSCODE="yes"
        fi
        case "$AUTO_VSCODE" in
            no|NO|No|0|false|FALSE)
                info "Skipping VS Code install (SEEDLING_AUTO_VSCODE=$AUTO_VSCODE)."
                ;;
            *)
                info "Setting up VS Code ..."
                if ! env SEEDLING_HOME="$SEEDLING_HOME" "$SEED_CLI" vscode --no-open; then
                    warn "VS Code setup didn't finish (network problem?). Install it later with:  seed vscode"
                fi
                ;;
        esac
        ;;
esac

# ---------------------------------------------------------------------------
# 5. Write the `seed` shell function and hook it into the user's shell
# ---------------------------------------------------------------------------
info "Writing shell integration ..."
sed "s#__SEEDLING_HOME_PLACEHOLDER__#$SEEDLING_HOME#g" \
    "$SRC_DIR/src/seedling/shell/seed.sh.template" > "$SEEDLING_HOME/system/shell/seed.sh"

HOOK_LINE=". \"$SEEDLING_HOME/system/shell/seed.sh\""

add_hook() {
    profile="$1"
    [ -f "$profile" ] || touch "$profile"
    # Drop hook lines left by older seedling layouts (e.g. ~/seedling/shell/
    # before it moved under system/) before adding the current one, so a
    # reinstall never leaves a stale line erroring in every new shell.
    awk -v home="$SEEDLING_HOME" -v keep="$HOOK_LINE" '
        index($0, home) && (index($0, "seed.sh") || index($0, "seed.ps1")) && $0 != keep { next }
        { print }
    ' "$profile" > "$profile.tmp"
    if cmp -s "$profile" "$profile.tmp"; then
        rm -f "$profile.tmp"
    else
        mv "$profile.tmp" "$profile"
        info "Removed stale seedling hook line(s) from $profile"
    fi
    if ! grep -qF "$HOOK_LINE" "$profile" 2>/dev/null; then
        {
            echo ""
            echo "# seedling"
            echo "$HOOK_LINE"
        } >> "$profile"
        info "Added seedling to $profile"
    fi
}

case "${SHELL:-}" in
    */zsh)  add_hook "$HOME/.zshrc" ;;
    */bash) add_hook "$HOME/.bashrc" ;;
    *)      add_hook "$HOME/.profile" ;;
esac

info "seedling is installed."
echo
if [ "$DEV_READY" = "1" ]; then
    echo "Open a new terminal (or run: . \"$SEEDLING_HOME/system/shell/seed.sh\") --"
    echo "the 'dev' venv auto-activates there, so you can immediately try:"
    echo "  python / ipython          # the newest Python, ready to go"
    echo "  seed install <package>    # add packages to 'dev'"
    echo "  seed venv myproject       # create another venv"
    echo "  seed summary              # see everything seedling has installed"
else
    echo "Open a new terminal (or run: . \"$SEEDLING_HOME/system/shell/seed.sh\") and try:"
    echo "  seed python               # install the newest Python"
    echo "  seed venv myproject"
    echo "  seed activate myproject"
    echo "  seed summary"
fi
echo
echo "Note: seed-cli was installed from a private copy at $SEEDLING_HOME/system/src."
echo "Nothing updates it automatically -- run 'seed update-commands' whenever"
echo "you want to pull in changes."
