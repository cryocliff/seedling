#!/usr/bin/env sh
# seedling installer (bash/zsh/sh) -- mirrors how `uv` installs itself.
# Requires nothing pre-installed except a POSIX shell and curl/wget (both
# already present on essentially every macOS/Linux system).
#
# Usage (from a local checkout of this repo):
#   ./install.sh
#
# Usage (remote, once hosted):
#   curl -fsSL https://.../install.sh | sh
#   SEEDLING_REPO=https://github.com/you/seedling.git curl -fsSL .../install.sh | sh

set -eu

# Change this once you've pushed seedling to your own GitHub repo, then host
# this script's raw URL so people can install with a single line, same as uv:
#   curl -fsSL https://raw.githubusercontent.com/<you>/seedling/main/install.sh | sh
# Can also be overridden per-run without editing the file:
#   SEEDLING_REPO=https://github.com/someone/fork.git curl -fsSL .../install.sh | sh
DEFAULT_SEEDLING_REPO="https://github.com/CHANGE_ME/seedling.git"

SEEDLING_HOME="${SEEDLING_HOME:-$HOME/seedling}"
SEEDLING_REPO="${SEEDLING_REPO:-$DEFAULT_SEEDLING_REPO}"

info()  { printf '\033[1;32m==>\033[0m %s\n' "$1"; }
warn()  { printf '\033[1;33m!!\033[0m %s\n' "$1"; }
die()   { printf '\033[1;31merror:\033[0m %s\n' "$1" >&2; exit 1; }

# ---------------------------------------------------------------------------
# 1. Locate the seedling source (local checkout next to this script, or clone)
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"

if [ -f "$SCRIPT_DIR/pyproject.toml" ]; then
    ORIGINAL_SRC="$SCRIPT_DIR"
    CLEANUP_ORIGINAL_SRC=0
else
    case "$SEEDLING_REPO" in
        *CHANGE_ME*)
            die "No local pyproject.toml found next to this script, and no repo is configured. \
Either run this from inside a seedling checkout, set SEEDLING_REPO=<git url>, \
or edit DEFAULT_SEEDLING_REPO at the top of install.sh once you've pushed this to GitHub."
            ;;
    esac
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
