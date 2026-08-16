# Arova Cross-Platform Release & Packaging Guide

Arova runs natively across **Linux**, **Windows (x64)**, and **macOS (Universal / Apple Silicon & Intel)**.

---

## 🏗️ Architecture Overview

Each release package contains:
1. **Frontend Desktop App**: Tauri 2.0 native binary with obsidian glass UI and WebSockets IPC bridge.
2. **Ambient Cognitive Daemon (`arovad`)**: Standalone compiled Python backend bundled with:
   - Voice activity detection & wake word models (`openwakeword`).
   - SQLite semantic timeline and memory indexes.
   - Dynamic 12-hour session aggregation and process trackers.
   - Platform backend services for native application launching, browser tab management, and window tracking.

---

## 📦 Building Releases for Each Platform

### 1. Linux (`.tar.gz` Standalone Archive)
```bash
./scripts/package_app.sh
```
- Produces: `arova-linux-x86_64.tar.gz` (contains `arova` binary, `resources/arovad`, and one-click `install.sh`).
- To install on Linux:
  ```bash
  tar -xzf arova-linux-x86_64.tar.gz
  cd arova-linux-x86_64
  ./install.sh
  ```

### 2. Windows (`.zip` Standalone & `.exe` Installer)
Run in PowerShell (Windows environment):
```powershell
.\scripts\package_windows.ps1
```
- Produces: `arova-windows-x64.zip` (contains `arova.exe`, `resources/arovad/arovad.exe`, and one-click `install.ps1`).
- Installs to `%LOCALAPPDATA%\Arova` and creates Start Menu + Desktop shortcuts.

### 3. macOS (`.dmg` & `.app` Bundle)
Run on macOS:
```bash
chmod +x scripts/package_macos.sh
./scripts/package_macos.sh
```
- Produces: `Arova-macOS.dmg` and `Arova-macOS.zip` (contains `Arova.app` with internal `Contents/Resources/arovad` daemon).
- Installs to `/Applications/Arova.app`.

---

## 🚀 Automated Multi-Platform CI/CD Release (GitHub Actions)

Pushing any semantic version tag (e.g. `v0.1.0`) triggers `.github/workflows/release.yml`:
- **Linux Runner (`ubuntu-latest`)**: Builds `arova-linux-x86_64.tar.gz`.
- **Windows Runner (`windows-latest`)**: Builds `arova-windows-x64.zip`.
- **macOS Runner (`macos-latest`)**: Builds `Arova-macOS.dmg` and `Arova-macOS.zip`.
- All artifacts are automatically uploaded and published to the GitHub Release.
