#!/usr/bin/env sh
# seedling installer (bash/zsh/sh) -- mirrors how `uv` installs itself.
# Requires nothing pre-installed except a POSIX shell and curl/wget (both
# already present on essentially every macOS/Linux system).
#
# Usage (from a local checkout of this repo):
#   ./install.sh
#
# Usage (remote):
#   curl -fsSL https://raw.githubusercontent.com/cryocliff/seedling/main/install.sh | sh
#   SEEDLING_REPO=https://github.com/someone/fork.git curl -fsSL .../install.sh | sh

set -eu

# Where seedling is cloned from when this script isn't run from inside a
# local checkout. Can be overridden per-run without editing the file --
# SEEDLING_REPO accepts a git URL or a plain directory path:
#   SEEDLING_REPO=https://github.com/someone/fork.git ./install.sh
#   SEEDLING_REPO=/mnt/share/seedling ./install.sh
DEFAULT_SEEDLING_REPO="https://github.com/cryocliff/seedling.git"

SEEDLING_HOME="${SEEDLING_HOME:-$HOME/seedling}"
SEEDLING_REPO="${SEEDLING_REPO:-$DEFAULT_SEEDLING_REPO}"

info()  { printf '\033[1;32m==>\033[0m %s\n' "$1"; }
warn()  { printf '\033[1;33m!!\033[0m %s\n' "$1"; }
die()   { printf '\033[1;31merror:\033[0m %s\n' "$1" >&2; exit 1; }

# ---------------------------------------------------------------------------
# 1. Locate the seedling source (local checkout next to this script, or clone)
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"

INSTALLED_FROM_DIR=""
if [ -f "$SCRIPT_DIR/pyproject.toml" ]; then
    ORIGINAL_SRC="$SCRIPT_DIR"
    CLEANUP_ORIGINAL_SRC=0
elif [ -d "$SEEDLING_REPO" ] && [ -f "$SEEDLING_REPO/pyproject.toml" ]; then
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

if [ "$CLEANUP_ORIGINAL_SRC" = "1" ]; then
    rm -rf "$ORIGINAL_SRC"
fi

# When installing from a directory, remember it as the update source so
# `seed update-commands` knows where to look for newer copies later.
if [ -n "$INSTALLED_FROM_DIR" ] && [ ! -f "$SEEDLING_HOME/system/config/settings.json" ]; then
    printf '{\n  "update_source": "%s"\n}\n' "$INSTALLED_FROM_DIR" \
        > "$SEEDLING_HOME/system/config/settings.json"
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
    "$UV" tool install --force --reinstall "$SRC_DIR"

[ -x "$SEEDLING_HOME/system/bin/seed-cli" ] || die "seed-cli was not installed correctly."

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
echo "Open a new terminal (or run: . \"$SEEDLING_HOME/system/shell/seed.sh\") and try:"
echo "  seed python 312"
echo "  seed venv myproject"
echo "  seed activate myproject"
echo "  seed vscode"
echo
echo "Note: seed-cli was installed from a private copy at $SEEDLING_HOME/system/src."
echo "Nothing updates it automatically -- run 'seed update-commands' whenever"
echo "you want to pull in changes."
