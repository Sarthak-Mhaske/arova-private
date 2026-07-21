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
