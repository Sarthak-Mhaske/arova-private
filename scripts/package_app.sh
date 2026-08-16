#!/usr/bin/env bash
set -e

# ==============================================================================
# Arova Standalone Release Packaging Script
# Builds fully compiled, zero-source-leak distribution package for Arch / Linux
# ==============================================================================

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

echo "========================================================"
echo "  📦 Building Arova Standalone Distribution Package     "
echo "========================================================"

# 1. Step 1: Compile Backend Daemon (arovad)
echo ""
echo "▶ [1/4] Compiling standalone backend daemon (arovad)..."
bash "$REPO_ROOT/scripts/build_arovad.sh"

# 2. Step 2: Build Frontend UI
echo ""
echo "▶ [2/4] Compiling frontend assets..."
cd "$REPO_ROOT/frontend"
npm run build

# 3. Step 3: Compile Tauri Desktop App & AppImage
echo ""
echo "▶ [3/4] Compiling Tauri desktop binary and AppImage bundle..."
npm run tauri build

# 4. Step 4: Assemble Release Artifacts
echo ""
echo "▶ [4/4] Assembling release folder..."
RELEASE_DIR="$REPO_ROOT/release"
rm -rf "$RELEASE_DIR"
mkdir -p "$RELEASE_DIR"

# Find generated binary
TAURI_BIN=$(find "$REPO_ROOT/frontend/src-tauri/target/release" -maxdepth 1 -type f \( -name "frontend" -o -name "arova" \) 2>/dev/null | head -n 1)

if [ -f "$TAURI_BIN" ]; then
    echo "✓ Bundling standalone binary from $TAURI_BIN..."
    cp -f "$TAURI_BIN" "$RELEASE_DIR/arova"
    mkdir -p "$RELEASE_DIR/resources"
    if [ -d "$REPO_ROOT/dist/arovad" ]; then
        cp -rf "$REPO_ROOT/dist/arovad" "$RELEASE_DIR/resources/"
        [ -f "$RELEASE_DIR/resources/arovad/arovad" ] && chmod +x "$RELEASE_DIR/resources/arovad/arovad"
    elif [ -f "$REPO_ROOT/dist/arovad" ]; then
        cp -f "$REPO_ROOT/dist/arovad" "$RELEASE_DIR/resources/arovad"
        chmod +x "$RELEASE_DIR/resources/arovad"
    fi
    strip "$RELEASE_DIR/arova" 2>/dev/null || true
    chmod +x "$RELEASE_DIR/arova"
else
    echo "❌ Error: Tauri release binary not found in target/release/"
    exit 1
fi

# Copy App Icon
cp -f "$REPO_ROOT/frontend/src-tauri/icons/128x128.png" "$RELEASE_DIR/arova.png"

# Generate One-Click Installer script for Arch Linux
cat << 'EOF' > "$RELEASE_DIR/install.sh"
#!/usr/bin/env bash
set -e

echo "========================================================"
echo "  🚀 Installing Arova Desktop on Linux                  "
echo "========================================================"

# Verify and install required desktop libraries (webkit2gtk-4.1 & gtk3)
if ! ldconfig -p 2>/dev/null | grep -q "libwebkit2gtk-4.1.so.0"; then
    echo "⚠️  Missing system dependency: webkit2gtk-4.1"
    if command -v pacman >/dev/null 2>&1; then
        echo "📦 Installing webkit2gtk-4.1 via pacman..."
        sudo pacman -S --needed --noconfirm webkit2gtk-4.1 gtk3 || sudo pacman -S --needed webkit2gtk-4.1 gtk3
    elif command -v apt >/dev/null 2>&1; then
        echo "📦 Installing libwebkit2gtk-4.1-0 via apt..."
        sudo apt update && sudo apt install -y libwebkit2gtk-4.1-0 libgtk-3-0
    elif command -v dnf >/dev/null 2>&1; then
        echo "📦 Installing webkit2gtk4.1 via dnf..."
        sudo dnf install -y webkit2gtk4.1 gtk3
    else
        echo "👉 Please install 'webkit2gtk-4.1' using your distribution package manager."
    fi
fi

INSTALL_DIR="$HOME/.local/bin"
APP_DIR="$HOME/.local/share/arova"
DESKTOP_DIR="$HOME/.local/share/applications"
ICON_DIR="$HOME/.local/share/icons/hicolor/128x128/apps"

mkdir -p "$INSTALL_DIR" "$APP_DIR" "$DESKTOP_DIR" "$ICON_DIR"

DIR="$(cd "$(dirname "$0")" && pwd)"

# Copy files to permanent application directory (~/.local/share/arova)
if [ -f "$DIR/arova" ]; then
    cp -f "$DIR/arova" "$APP_DIR/arova"
    rm -rf "$APP_DIR/resources"
    mkdir -p "$APP_DIR/resources"
    if [ -d "$DIR/resources" ]; then
        cp -rf "$DIR/resources/"* "$APP_DIR/resources/"
    fi
    chmod +x "$APP_DIR/arova"
    [ -f "$APP_DIR/resources/arovad" ] && chmod +x "$APP_DIR/resources/arovad"
    [ -f "$APP_DIR/resources/arovad/arovad" ] && chmod +x "$APP_DIR/resources/arovad/arovad"
    ln -sf "$APP_DIR/arova" "$INSTALL_DIR/arova"
fi

if [ -f "$DIR/arova.png" ]; then
    cp -f "$DIR/arova.png" "$APP_DIR/arova.png"
    cp -f "$DIR/arova.png" "$ICON_DIR/arova.png"
fi

# Ensure ~/.local/bin is in PATH for fish, bash, zsh
if command -v fish >/dev/null 2>&1; then
    fish -c "fish_add_path -U $HOME/.local/bin" 2>/dev/null || true
fi
if [ -f "$HOME/.bashrc" ] && ! grep -q '\.local/bin' "$HOME/.bashrc"; then
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.bashrc"
fi
if [ -f "$HOME/.zshrc" ] && ! grep -q '\.local/bin' "$HOME/.zshrc"; then
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.zshrc"
fi

# Create Desktop Entry with absolute paths for Rofi / Wofi / Hyprland / KDE / GNOME
cat << DESKTOP_EOF > "$DESKTOP_DIR/arova.desktop"
[Desktop Entry]
Name=Arova
Comment=Persistent working memory for knowledge work
Exec=$APP_DIR/arova
Path=$APP_DIR
Icon=$APP_DIR/arova.png
Terminal=false
Type=Application
Categories=Utility;Development;Productivity;
StartupNotify=true
StartupWMClass=arova
DESKTOP_EOF

chmod +x "$DESKTOP_DIR/arova.desktop"

# Configure standard XDG autostart on system login
AUTOSTART_DIR="$HOME/.config/autostart"
mkdir -p "$AUTOSTART_DIR"
cp -f "$DESKTOP_DIR/arova.desktop" "$AUTOSTART_DIR/arova.desktop"
chmod +x "$AUTOSTART_DIR/arova.desktop"

# Configure persistent background daemon service via systemd user units
if command -v systemctl >/dev/null 2>&1; then
    SYSTEMD_USER_DIR="$HOME/.config/systemd/user"
    mkdir -p "$SYSTEMD_USER_DIR"
    cat << SERVICE_EOF > "$SYSTEMD_USER_DIR/arovad.service"
[Unit]
Description=Arova Ambient Intelligence Daemon
After=network.target

[Service]
Type=simple
ExecStart=$APP_DIR/resources/arovad/arovad
Restart=always
RestartSec=3
WorkingDirectory=$APP_DIR

[Install]
WantedBy=default.target
SERVICE_EOF

    systemctl --user daemon-reload 2>/dev/null || true
    systemctl --user enable --now arovad.service 2>/dev/null || true
fi

# Refresh desktop databases and icon caches
update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true
gtk-update-icon-cache "$HOME/.local/share/icons/hicolor" 2>/dev/null || true

echo ""
echo "✓ Arova installed successfully!"
echo "✓ Auto-launch on startup configured (~/.config/autostart/arova.desktop)"
echo "✓ Ambient background daemon active (tracks context 24/7 even when UI is closed)"
echo ""
echo "▶ Launch options:"
echo "  1. App Launcher : Open Rofi / Wofi / Hyprland / GNOME / KDE and search 'Arova'"
echo "  2. Terminal     : arova"
echo "  3. Direct Path  : $APP_DIR/arova"
echo ""
if [ -d "$HOME/.config/hypr" ]; then
    echo "💡 Note for Hyprland users: To ensure auto-start on Hyprland login, add:"
    echo "   exec-once = $APP_DIR/arova"
    echo "   to your ~/.config/hypr/hyprland.conf"
    echo ""
fi
if command -v fish >/dev/null 2>&1; then
    echo "💡 Note for fish shell: In your current active terminal session, run:"
    echo "   fish_add_path ~/.local/bin"
    echo "   (or run ~/.local/share/arova/arova directly)"
fi
EOF

chmod +x "$RELEASE_DIR/install.sh"

# Create a clean tarball with top-level 'arova' directory
DIST_TEMP="$REPO_ROOT/target_dist_tar"
rm -rf "$DIST_TEMP" "$REPO_ROOT/arova-linux-x86_64.tar.gz"
mkdir -p "$DIST_TEMP/arova"
cp -rf "$RELEASE_DIR/"* "$DIST_TEMP/arova/"
tar -czf "$REPO_ROOT/arova-linux-x86_64.tar.gz" -C "$DIST_TEMP" arova
rm -rf "$DIST_TEMP"

echo ""
echo "========================================================"
echo "  🎉 Distribution Package Ready!                        "
echo "  Archive: $REPO_ROOT/arova-linux-x86_64.tar.gz         "
echo "  Folder:  $RELEASE_DIR/                          "
echo "========================================================"
