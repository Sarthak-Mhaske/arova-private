#!/usr/bin/env bash
set -e

# ==============================================================================
# Arova Linux Complete Uninstallation Script
# Removes all binaries, background daemon services, desktop integration, autostart,
# and shell hooks.
# Supports --purge to also delete all configuration, cache, and semantic memory.
# ==============================================================================

PURGE_DATA=false

for arg in "$@"; do
    case "$arg" in
        --purge|-p)
            PURGE_DATA=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [--purge]"
            echo "  --purge, -p    Also remove all user configuration (~/.config/arova), logs, and cached databases (~/.cache/arova)"
            exit 0
            ;;
    esac
done

echo "========================================================"
echo "  🗑️  Uninstalling Arova Desktop & Daemon from Linux    "
echo "========================================================"

# 1. Stop and terminate running processes
echo "▶ [1/6] Stopping active Arova processes..."
pkill -f "arovad" 2>/dev/null || true
pkill -f "arova" 2>/dev/null || true

# 2. Stop and disable systemd user service
if command -v systemctl >/dev/null 2>&1; then
    echo "▶ [2/6] Disabling and removing systemd user service (arovad.service)..."
    systemctl --user stop arovad.service 2>/dev/null || true
    systemctl --user disable arovad.service 2>/dev/null || true
    rm -f "$HOME/.config/systemd/user/arovad.service"
    systemctl --user daemon-reload 2>/dev/null || true
    systemctl --user reset-failed 2>/dev/null || true
fi

# 3. Remove Desktop Launcher, Autostart, and Icons
echo "▶ [3/6] Removing desktop launchers, autostart entries, and icons..."
rm -f "$HOME/.config/autostart/arova.desktop"
rm -f "$HOME/.local/share/applications/arova.desktop"
rm -f "$HOME/.local/share/icons/hicolor/128x128/apps/arova.png"
rm -f "$HOME/.local/share/icons/hicolor/scalable/apps/arova.svg" 2>/dev/null || true

# 4. Remove Binary Symlinks and Installed Files
echo "▶ [4/6] Removing application binaries and resources..."
rm -f "$HOME/.local/bin/arova"
rm -rf "$HOME/.local/share/arova"

# 5. Remove Shell Hooks (if any were installed)
echo "▶ [5/6] Checking for ambience shell hooks..."
if [ -f "$HOME/.bashrc" ]; then
    sed -i '/# === AROVA AMBIENCE HOOK START ===/,/# === AROVA AMBIENCE HOOK END ===/d' "$HOME/.bashrc" 2>/dev/null || true
fi
if [ -f "$HOME/.zshrc" ]; then
    sed -i '/# === AROVA AMBIENCE HOOK START ===/,/# === AROVA AMBIENCE HOOK END ===/d' "$HOME/.zshrc" 2>/dev/null || true
fi

# 6. Purge Data (Optional)
if [ "$PURGE_DATA" = true ]; then
    echo "▶ [6/6] Purging configuration, session history, and semantic memory..."
    rm -rf "$HOME/.config/arova"
    rm -rf "$HOME/.cache/arova"
    rm -rf "$HOME/.local/state/arova"
    echo "✓ Purged all user configs (~/.config/arova) and caches (~/.cache/arova)"
else
    echo "▶ [6/6] Preserving user configuration and memory (~/.config/arova)."
    echo "       (To completely wipe user data, re-run with: $0 --purge)"
fi

# Refresh desktop databases and icon caches
update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
gtk-update-icon-cache "$HOME/.local/share/icons/hicolor" 2>/dev/null || true

echo ""
echo "========================================================"
echo "  ✓ Arova has been completely uninstalled from Linux.   "
echo "========================================================"
