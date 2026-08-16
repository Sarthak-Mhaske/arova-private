#!/usr/bin/env bash
set -e

# ==============================================================================
# Arova macOS Standalone Release Packaging Script
# Builds universal daemon (arovad), compiles Tauri .app, and generates .dmg bundle
# ==============================================================================

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

echo "========================================================"
echo "  📦 Building Arova Standalone macOS Release Package    "
echo "========================================================"

# 1. Compile Backend Daemon via PyInstaller
echo ""
echo "▶ [1/4] Compiling standalone backend daemon (arovad)..."
if [ -f "$REPO_ROOT/venv/bin/pyinstaller" ]; then
    "$REPO_ROOT/venv/bin/pyinstaller" --noconfirm "$REPO_ROOT/arovad.spec"
else
    pyinstaller --noconfirm "$REPO_ROOT/arovad.spec"
fi

# 2. Compile Frontend UI Assets
echo ""
echo "▶ [2/4] Compiling frontend assets..."
cd "$REPO_ROOT/frontend"
if [ ! -d "node_modules" ]; then
    npm install
fi
npm run build

# 3. Build Tauri macOS Application Bundle (.app & .dmg)
echo ""
echo "▶ [3/4] Compiling Tauri desktop binary and macOS bundle..."
npm run tauri build

# 4. Assemble Arova.app Bundle
echo ""
echo "▶ [4/4] Assembling Arova.app bundle..."
RELEASE_DIR="$REPO_ROOT/release-macos"
rm -rf "$RELEASE_DIR"
mkdir -p "$RELEASE_DIR"

APP_BUNDLE=$(find "$REPO_ROOT/frontend/src-tauri/target/release/bundle/macos" -maxdepth 1 -name "*.app" 2>/dev/null | head -n 1)
if [ -z "$APP_BUNDLE" ]; then
    APP_BUNDLE=$(find "$REPO_ROOT/frontend/src-tauri/target/release" -maxdepth 2 -name "*.app" 2>/dev/null | head -n 1)
fi

if [ -d "$APP_BUNDLE" ]; then
    echo "✓ Found Tauri macOS App Bundle: $APP_BUNDLE"
    cp -rf "$APP_BUNDLE" "$RELEASE_DIR/Arova.app"
else
    echo "Creating Arova.app bundle structure..."
    mkdir -p "$RELEASE_DIR/Arova.app/Contents/MacOS"
    mkdir -p "$RELEASE_DIR/Arova.app/Contents/Resources"

    BIN=$(find "$REPO_ROOT/frontend/src-tauri/target/release" -maxdepth 1 -name "arova" -o -name "frontend" 2>/dev/null | head -n 1)
    if [ -f "$BIN" ]; then
        cp -f "$BIN" "$RELEASE_DIR/Arova.app/Contents/MacOS/arova"
        chmod +x "$RELEASE_DIR/Arova.app/Contents/MacOS/arova"
    fi

    if [ -f "$REPO_ROOT/frontend/src-tauri/icons/icon.icns" ]; then
        cp -f "$REPO_ROOT/frontend/src-tauri/icons/icon.icns" "$RELEASE_DIR/Arova.app/Contents/Resources/icon.icns"
    fi

    cat << 'EOF' > "$RELEASE_DIR/Arova.app/Contents/Info.plist"
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>arova</string>
    <key>CFBundleIdentifier</key>
    <string>com.arova.desktop</string>
    <key>CFBundleName</key>
    <string>Arova</string>
    <key>CFBundleDisplayName</key>
    <string>Arova</string>
    <key>CFBundleIconFile</key>
    <string>icon</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>0.1.0</string>
    <key>LSMinimumSystemVersion</key>
    <string>10.15</string>
    <key>NSHighResolutionCapable</key>
    <true/>
</dict>
</plist>
EOF
fi

# Inject backend daemon into Arova.app
mkdir -p "$RELEASE_DIR/Arova.app/Contents/Resources/arovad"
if [ -d "$REPO_ROOT/dist/arovad" ]; then
    cp -rf "$REPO_ROOT/dist/arovad/"* "$RELEASE_DIR/Arova.app/Contents/Resources/arovad/"
    chmod +x "$RELEASE_DIR/Arova.app/Contents/Resources/arovad/arovad" || true
fi

# Create Zip Archive
cd "$RELEASE_DIR"
zip -r -q "$REPO_ROOT/Arova-macOS.zip" "Arova.app"
echo "✓ Zip archive created: $REPO_ROOT/Arova-macOS.zip"

# Check / Generate DMG
DMG_FILE=$(find "$REPO_ROOT/frontend/src-tauri/target/release/bundle/dmg" -name "*.dmg" 2>/dev/null | head -n 1)
if [ -f "$DMG_FILE" ]; then
    cp -f "$DMG_FILE" "$REPO_ROOT/Arova-macOS.dmg"
    echo "✓ DMG created by Tauri: $REPO_ROOT/Arova-macOS.dmg"
elif command -v hdiutil &>/dev/null; then
    echo "Creating Arova-macOS.dmg with hdiutil..."
    hdiutil create -volname "Arova" -srcfolder "$RELEASE_DIR" -ov -format UDZO "$REPO_ROOT/Arova-macOS.dmg"
    echo "✓ DMG created via hdiutil: $REPO_ROOT/Arova-macOS.dmg"
fi

echo ""
echo "========================================================"
echo "  🎉 macOS Release Package Ready!                       "
echo "========================================================"
