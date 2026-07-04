#!/usr/bin/env sh
# Fully removes seedling: the managed folder AND the shell hook line.
set -eu

SEEDLING_HOME="${SEEDLING_HOME:-$HOME/seedling}"
HOOK_LINE=". \"$SEEDLING_HOME/system/shell/seed.sh\""

for profile in "$HOME/.zshrc" "$HOME/.bashrc" "$HOME/.profile"; do
    [ -f "$profile" ] || continue
    if grep -qF "$HOOK_LINE" "$profile" 2>/dev/null; then
        grep -vF "$HOOK_LINE" "$profile" | grep -v '^# seedling$' > "$profile.tmp"
        mv "$profile.tmp" "$profile"
        echo "Removed seedling hook from $profile"
    fi
done

if [ -d "$SEEDLING_HOME" ]; then
    rm -rf "$SEEDLING_HOME"
    echo "Removed $SEEDLING_HOME"
fi

echo "seedling fully uninstalled. Open a new terminal for it to take effect."
