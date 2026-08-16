#!/usr/bin/env bash
set -e

echo "[build_arovad] Compiling standalone Arova Daemon (arovad) via PyInstaller..."

# Ensure we are in the repository root
cd "$(dirname "$0")/.."

# Run PyInstaller using arovad.spec for clean onedir packaging
./venv/bin/pyinstaller --noconfirm --clean arovad.spec

echo "[build_arovad] Build complete! Checking dist/arovad..."
ls -ld dist/arovad dist/arovad/arovad

# Copy to frontend/src-tauri/resources (untracked by git)
mkdir -p frontend/src-tauri/resources
rm -rf frontend/src-tauri/resources/arovad
cp -rf dist/arovad frontend/src-tauri/resources/arovad

# Update any existing target bundles so they immediately use the new directory/binary
for target_dir in $(find frontend/src-tauri/target -name resources 2>/dev/null); do
  if [ -d "$target_dir" ]; then
    echo "[build_arovad] Updating target bundle resources: $target_dir/arovad"
    rm -rf "$target_dir/arovad"
    cp -rf dist/arovad "$target_dir/arovad"
  fi
done

echo "[build_arovad] All arovad binaries updated successfully!"
