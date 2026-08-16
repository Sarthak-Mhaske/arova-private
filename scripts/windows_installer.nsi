!include "MUI2.nsh"

Name "Arova"
OutFile "..\Arova-Setup-x64.exe"
InstallDir "$LOCALAPPDATA\Arova"
RequestExecutionLevel user
SetCompressor /SOLID lzma

!define MUI_ICON "..\frontend\src-tauri\icons\icon.ico"
!define MUI_UNICON "..\frontend\src-tauri\icons\icon.ico"
!define MUI_ABORTWARNING

; Pages
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!define MUI_FINISHPAGE_RUN "$INSTDIR\arova.exe"
!define MUI_FINISHPAGE_RUN_TEXT "Launch Arova"
!insertmacro MUI_PAGE_FINISH

; Uninstaller Pages
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

!insertmacro MUI_LANGUAGE "English"

Section "Install"
    ; Stop existing running processes
    DetailPrint "Stopping existing Arova processes if running..."
    nsExec::Exec 'taskkill /F /IM arova.exe /IM arovad.exe /T'

    SetOutPath "$INSTDIR"
    File /r "..\release-windows\*"
    
    ; Create Shortcuts
    CreateDirectory "$SMPROGRAMS\Arova"
    CreateShortCut "$SMPROGRAMS\Arova\Arova.lnk" "$INSTDIR\arova.exe" "" "$INSTDIR\arova.ico"
    CreateShortCut "$SMPROGRAMS\Arova\Uninstall Arova.lnk" "$INSTDIR\uninstall.exe"
    CreateShortCut "$DESKTOP\Arova.lnk" "$INSTDIR\arova.exe" "" "$INSTDIR\arova.ico"
    
    ; Register Uninstaller in Windows Add/Remove Programs
    WriteUninstaller "$INSTDIR\uninstall.exe"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\Arova" "DisplayName" "Arova"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\Arova" "UninstallString" "$\"$INSTDIR\uninstall.exe$\""
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\Arova" "DisplayIcon" "$INSTDIR\arova.ico"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\Arova" "Publisher" "Arova AI"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\Arova" "DisplayVersion" "0.1.0"
    WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\Arova" "NoModify" 1
    WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\Arova" "NoRepair" 1
SectionEnd

Section "Uninstall"
    ; Stop existing running processes
    nsExec::Exec 'taskkill /F /IM arova.exe /IM arovad.exe /T'

    RMDir /r "$INSTDIR"
    Delete "$SMPROGRAMS\Arova\Arova.lnk"
    Delete "$SMPROGRAMS\Arova\Uninstall Arova.lnk"
    RMDir "$SMPROGRAMS\Arova"
    Delete "$DESKTOP\Arova.lnk"
    DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\Arova"
SectionEnd
