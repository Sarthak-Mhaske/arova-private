#!/usr/bin/env bash
set -e

echo "[build_arovad] Compiling standalone Arova Daemon (arovad) via PyInstaller..."

# Ensure we are in the repository root
cd "$(dirname "$0")/.."

# Run PyInstaller inside our venv
./venv/bin/pyinstaller --onefile \
  --name arovad \
  --collect-all openwakeword \
  --collect-all arova \
  --hidden-import arova \
  --hidden-import arova.core \
  --hidden-import arova.daemon \
  --hidden-import arova.core.cognition.workspace_manager \
  --hidden-import arova.core.projection.projector \
  arova/daemon/main.py

echo "[build_arovad] Build complete! Checking dist/arovad..."
ls -lh dist/arovad

# Copy to frontend/src-tauri/resources (untracked by git)
mkdir -p frontend/src-tauri/resources
cp -f dist/arovad frontend/src-tauri/resources/arovad

# Update any existing target bundles so they immediately use the new binary
for target_bin in $(find frontend/src-tauri/target -name arovad 2>/dev/null); do
  echo "[build_arovad] Updating target bundle binary: $target_bin"
  cp -f dist/arovad "$target_bin"
done

echo "[build_arovad] All arovad binaries updated successfully!"
