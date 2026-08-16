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

# Copy backend resources into Tauri resources folder before bundle build
Write-Host "`n▶ [2.5/4] Staging daemon resources for Tauri bundler..." -ForegroundColor Yellow
$TauriResourceDir = "$RepoRoot\frontend\src-tauri\resources\arovad"
if (Test-Path $TauriResourceDir) { Remove-Item -Recurse -Force $TauriResourceDir }
New-Item -ItemType Directory -Force -Path $TauriResourceDir | Out-Null
if (Test-Path "$RepoRoot\dist\arovad") {
    Copy-Item -Recurse "$RepoRoot\dist\arovad\*" "$TauriResourceDir"
}

# 3. Build Tauri Windows Application (Produces native NSIS setup exe + binaries)
Write-Host "`n▶ [3/4] Compiling Tauri desktop binary and NSIS installer..." -ForegroundColor Yellow
npm run tauri build

# 4. Assemble Release Directory
Write-Host "`n▶ [4/4] Assembling release package..." -ForegroundColor Yellow
$ReleaseDir = "$RepoRoot\release-windows"
if (Test-Path $ReleaseDir) { Remove-Item -Recurse -Force $ReleaseDir }
New-Item -ItemType Directory -Path $ReleaseDir | Out-Null

# Copy NSIS installer if generated
$NsisExe = Get-ChildItem "$RepoRoot\frontend\src-tauri\target\release\bundle\nsis" -Filter "*.exe" -Recurse | Select-Object -First 1
if ($NsisExe) {
    Copy-Item $NsisExe.FullName "$RepoRoot\Arova-Setup-x64.exe" -Force
    Copy-Item $NsisExe.FullName "$ReleaseDir\Arova-Setup-x64.exe" -Force
    Write-Host "✓ Native NSIS Windows Installer ready: $RepoRoot\Arova-Setup-x64.exe" -ForegroundColor Green
}

$TauriExe = Get-ChildItem "$RepoRoot\frontend\src-tauri\target\release" -Filter "arova.exe" -Recurse | Select-Object -First 1
if (-not $TauriExe) {
    $TauriExe = Get-ChildItem "$RepoRoot\frontend\src-tauri\target\release" -Filter "frontend.exe" -Recurse | Select-Object -First 1
}

if ($TauriExe) {
    Copy-Item $TauriExe.FullName "$ReleaseDir\arova.exe"
} else {
    Write-Error "Tauri Windows executable not found in target\release"
}

# Copy compiled backend resources
New-Item -ItemType Directory -Path "$ReleaseDir\resources" | Out-Null
if (Test-Path "$RepoRoot\dist\arovad") {
    Copy-Item -Recurse "$RepoRoot\dist\arovad" "$ReleaseDir\resources\arovad"
}

Copy-Item "$RepoRoot\frontend\src-tauri\icons\icon.ico" "$ReleaseDir\arova.ico"

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
