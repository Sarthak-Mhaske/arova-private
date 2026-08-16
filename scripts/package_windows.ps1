# ==============================================================================
# Arova Windows Standalone Release Packaging Script (PowerShell)
# Builds standalone daemon (arovad.exe), compiles Tauri x64 frontend, and packages .zip/.msi
# ==============================================================================

$ErrorActionPreference = "Stop"

$RepoRoot = (Get-Item $PSScriptRoot).Parent.FullName
Set-Location $RepoRoot

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "  📦 Building Arova Standalone Windows Release Package   " -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan

# 1. Compile Backend Daemon via PyInstaller
Write-Host "`n▶ [1/4] Compiling standalone backend daemon (arovad.exe)..." -ForegroundColor Yellow
if (Test-Path "$RepoRoot\venv\Scripts\pyinstaller.exe") {
    & "$RepoRoot\venv\Scripts\pyinstaller.exe" --noconfirm "$RepoRoot\arovad.spec"
} else {
    pyinstaller --noconfirm "$RepoRoot\arovad.spec"
}

# 2. Compile Frontend UI Assets
Write-Host "`n▶ [2/4] Compiling frontend assets..." -ForegroundColor Yellow
Set-Location "$RepoRoot\frontend"
if (-not (Test-Path "node_modules")) {
    npm install
}
npm run build

# 3. Build Tauri Windows Application
Write-Host "`n▶ [3/4] Compiling Tauri desktop binary..." -ForegroundColor Yellow
npm run tauri build -- --no-bundle

# 4. Assemble Complete Standalone Release Directory
Write-Host "`n▶ [4/4] Assembling release directory with full backend resources..." -ForegroundColor Yellow
$ReleaseDir = "$RepoRoot\release-windows"
if (Test-Path $ReleaseDir) { Remove-Item -Recurse -Force $ReleaseDir }
New-Item -ItemType Directory -Path $ReleaseDir | Out-Null

$TauriExe = Get-ChildItem "$RepoRoot\frontend\src-tauri\target\release" -Filter "arova.exe" -Recurse | Select-Object -First 1
if (-not $TauriExe) {
    $TauriExe = Get-ChildItem "$RepoRoot\frontend\src-tauri\target\release" -Filter "frontend.exe" -Recurse | Select-Object -First 1
}

if ($TauriExe) {
    Copy-Item $TauriExe.FullName "$ReleaseDir\arova.exe"
} else {
    Write-Error "Tauri Windows executable not found in target\release"
}

# Copy full compiled backend resources (arovad daemon + models)
New-Item -ItemType Directory -Path "$ReleaseDir\resources" | Out-Null
if (Test-Path "$RepoRoot\dist\arovad") {
    Copy-Item -Recurse "$RepoRoot\dist\arovad" "$ReleaseDir\resources\arovad"
}

Copy-Item "$RepoRoot\frontend\src-tauri\icons\icon.ico" "$ReleaseDir\arova.ico"

# 5. Build Native NSIS Installer Embedding Full Application & Resources
Write-Host "`n▶ [5/5] Compiling native NSIS Windows Setup Wizard (Arova-Setup-x64.exe)..." -ForegroundColor Yellow
if (Get-Command makensis -ErrorAction SilentlyContinue) {
    & makensis "$RepoRoot\scripts\windows_installer.nsi"
    if (Test-Path "$RepoRoot\Arova-Setup-x64.exe") {
        Write-Host "✓ Native NSIS Setup Installer created: $RepoRoot\Arova-Setup-x64.exe" -ForegroundColor Green
    }
}

# Create One-Click Windows Installer Script
$InstallerContent = @'
# Arova Windows One-Click Installer
$ErrorActionPreference = "Stop"

$AppDir = "$env:LOCALAPPDATA\Arova"
$BinDir = "$env:LOCALAPPDATA\Microsoft\WindowsApps"
$CurrentDir = $PSScriptRoot

Write-Host "Installing Arova to $AppDir..." -ForegroundColor Cyan

if (Test-Path $AppDir) {
    Get-Process -Name "arova", "arovad" -ErrorAction SilentlyContinue | Stop-Process -Force
    Start-Sleep -Seconds 1
}

New-Item -ItemType Directory -Force -Path $AppDir | Out-Null
Copy-Item "$CurrentDir\arova.exe" "$AppDir\arova.exe" -Force
Copy-Item "$CurrentDir\arova.ico" "$AppDir\arova.ico" -Force
if (Test-Path "$CurrentDir\resources") {
    Copy-Item -Recurse "$CurrentDir\resources" "$AppDir\" -Force
}

# Create Desktop and Start Menu Shortcuts
$WshShell = New-Object -ComObject WScript.Shell
$DesktopPath = [Environment]::GetFolderPath("Desktop")
$StartMenuPath = [Environment]::GetFolderPath("StartMenu") + "\Programs"

$Shortcut = $WshShell.CreateShortcut("$StartMenuPath\Arova.lnk")
$Shortcut.TargetPath = "$AppDir\arova.exe"
$Shortcut.IconLocation = "$AppDir\arova.ico"
$Shortcut.WorkingDirectory = "$AppDir"
$Shortcut.Save()

$DesktopShortcut = $WshShell.CreateShortcut("$DesktopPath\Arova.lnk")
$DesktopShortcut.TargetPath = "$AppDir\arova.exe"
$DesktopShortcut.IconLocation = "$AppDir\arova.ico"
$DesktopShortcut.WorkingDirectory = "$AppDir"
$DesktopShortcut.Save()

Write-Host "`n✓ Arova installed successfully!" -ForegroundColor Green
Write-Host "✓ Launch via Start Menu, Desktop Shortcut, or '$AppDir\arova.exe'"
'@

Set-Content -Path "$ReleaseDir\install.ps1" -Value $InstallerContent

# Create ZIP archive
$ZipPath = "$RepoRoot\arova-windows-x64.zip"
if (Test-Path $ZipPath) { Remove-Item -Force $ZipPath }
Compress-Archive -Path "$ReleaseDir\*" -DestinationPath $ZipPath

Write-Host "`n========================================================" -ForegroundColor Green
Write-Host "  🎉 Windows Release Package Ready: $ZipPath" -ForegroundColor Green
Write-Host "========================================================" -ForegroundColor Green
