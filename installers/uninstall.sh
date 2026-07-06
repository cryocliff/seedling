#!/usr/bin/env sh
# Fully removes seedling: the managed folder AND the shell hook line.
set -eu

SEEDLING_HOME="${SEEDLING_HOME:-$HOME/seedling}"

# Match any line sourcing a seed shell script from under the seedling home
# -- not just the exact current hook text -- so hooks written by older
# seedling layouts (e.g. ~/seedling/shell/ before it moved under system/)
# are cleaned up too instead of erroring in every new shell.
for profile in "$HOME/.zshrc" "$HOME/.bashrc" "$HOME/.profile"; do
    [ -f "$profile" ] || continue
    awk -v home="$SEEDLING_HOME" '
        $0 == "# seedling" { next }
        index($0, home) && (index($0, "seed.sh") || index($0, "seed.ps1")) { next }
        { print }
    ' "$profile" > "$profile.tmp"
    if cmp -s "$profile" "$profile.tmp"; then
        rm -f "$profile.tmp"
    else
        mv "$profile.tmp" "$profile"
        echo "Removed seedling hook from $profile"
    fi
done

if [ -d "$SEEDLING_HOME" ]; then
    rm -rf "$SEEDLING_HOME"
    echo "Removed $SEEDLING_HOME"
fi

echo "seedling fully uninstalled. Open a new terminal for it to take effect."
