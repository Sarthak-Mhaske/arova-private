#!/usr/bin/env bash
set -e

# ==============================================================================
# Arova macOS Standalone Release Packaging Script
# Builds universal daemon (arovad), compiles Tauri .app, and generates .dmg bundle
# with strict macOS security hardening, ad-hoc code signing, and full permissions.
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
npm run tauri build || npm run tauri build -- --no-bundle

# 4. Assemble Arova.app Bundle
echo ""
echo "▶ [4/4] Assembling and hardening Arova.app bundle..."
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

    if [ -f "$REPO_ROOT/frontend/src-tauri/Info.plist" ]; then
        cp -f "$REPO_ROOT/frontend/src-tauri/Info.plist" "$RELEASE_DIR/Arova.app/Contents/Info.plist"
    fi
fi

# Inject backend daemon into Arova.app
mkdir -p "$RELEASE_DIR/Arova.app/Contents/Resources/arovad"
if [ -d "$REPO_ROOT/dist/arovad" ]; then
    echo "Injecting compiled arovad daemon into Arova.app/Contents/Resources/arovad..."
    cp -rf "$REPO_ROOT/dist/arovad/"* "$RELEASE_DIR/Arova.app/Contents/Resources/arovad/"
fi

# Ensure executable permissions across all binaries and dylibs
echo "Setting executable permissions on all binaries and dynamic libraries..."
chmod -R 755 "$RELEASE_DIR/Arova.app"
find "$RELEASE_DIR/Arova.app/Contents/MacOS" -type f -exec chmod +x {} +
find "$RELEASE_DIR/Arova.app/Contents/Resources/arovad" -type f -perm +111 -exec chmod +x {} + 2>/dev/null || true
if [ -f "$RELEASE_DIR/Arova.app/Contents/Resources/arovad/arovad" ]; then
    chmod +x "$RELEASE_DIR/Arova.app/Contents/Resources/arovad/arovad"
fi

# Strip quarantine extended attributes
echo "Clearing quarantine extended attributes..."
xattr -cr "$RELEASE_DIR/Arova.app" 2>/dev/null || true

# Apply deep ad-hoc code signature (required for ARM64 M1/M2/M3/M4 & Intel macOS security)
ENTITLEMENTS="$REPO_ROOT/frontend/src-tauri/Entitlements.plist"
if command -v codesign &>/dev/null; then
    echo "Applying deep ad-hoc code signature..."
    if [ -f "$ENTITLEMENTS" ]; then
        find "$RELEASE_DIR/Arova.app" -type f \( -name "*.dylib" -o -name "*.so" \) -exec codesign --force --options runtime --entitlements "$ENTITLEMENTS" --sign - {} + 2>/dev/null || true
        codesign --force --deep --options runtime --entitlements "$ENTITLEMENTS" --sign - "$RELEASE_DIR/Arova.app" 2>/dev/null || codesign --force --deep --sign - "$RELEASE_DIR/Arova.app"
    else
        codesign --force --deep --sign - "$RELEASE_DIR/Arova.app"
    fi
    echo "✓ Ad-hoc code signature applied."
fi

# Create Zip Archive
echo "Creating standalone ZIP archive..."
cd "$RELEASE_DIR"
zip -r -q "$REPO_ROOT/Arova-macOS.zip" "Arova.app"
echo "✓ Standalone Zip archive created: $REPO_ROOT/Arova-macOS.zip"

# Generate Drag-to-Applications Disk Image (DMG) containing full Arova.app + Applications symlink + Quickstart
echo "Creating complete Drag-to-Applications Disk Image (DMG)..."
DMG_STAGING="$REPO_ROOT/dmg_staging"
rm -rf "$DMG_STAGING" "$REPO_ROOT/Arova-macOS.dmg"
mkdir -p "$DMG_STAGING"
cp -rf "$RELEASE_DIR/Arova.app" "$DMG_STAGING/"
ln -s /Applications "$DMG_STAGING/Applications"

cat << 'EOF' > "$DMG_STAGING/README_macOS.txt"
========================================================
  Arova for macOS — Installation & Quickstart
========================================================

1. Drag Arova.app into the Applications folder shortcut.
2. Launch Arova from Applications.

* macOS Security Note:
If macOS displays "Arova is an app downloaded from the Internet",
simply Right-Click (or Control-Click) Arova.app in Applications
and click "Open", then confirm by clicking "Open" in the dialog.

Enjoy using Arova!
========================================================
EOF

if command -v hdiutil &>/dev/null; then
    hdiutil create -volname "Arova" -srcfolder "$DMG_STAGING" -ov -format UDZO "$REPO_ROOT/Arova-macOS.dmg"
    rm -rf "$DMG_STAGING"
    echo "✓ Full macOS DMG created: $REPO_ROOT/Arova-macOS.dmg"
fi

echo ""
echo "========================================================"
echo "  🎉 macOS Release Package Ready!                       "
echo "========================================================"
