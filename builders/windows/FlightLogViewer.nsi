# Package script for nullsoft NSIS 3.08 or higher.

!define PRODUCT_ID "FlightLogViewer"
!define PRODUCT_NAME "Flight Log Viewer"
!define PRODUCT_VERSION "2.4.0"
!define EXECUTABLE "FlightLogViewer.exe"
!define UNINSTALLER "uninstall.exe"

!include "FileFunc.nsh"

# define installer name
OutFile "install_flightlogviewer_v${PRODUCT_VERSION}.exe"

# set desktop as install directory
InstallDir "$PROGRAMFILES\${PRODUCT_NAME}"


Section "install"
  SetOutPath $INSTDIR
  File /r .\venv\src\dist\${PRODUCT_ID}\*.*
  WriteUninstaller $INSTDIR\${UNINSTALLER}
  CreateShortCut "$DESKTOP\${PRODUCT_NAME}.lnk" "$INSTDIR\${EXECUTABLE}" ""
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_ID}" "DisplayName" "${PRODUCT_NAME}"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_ID}" "UninstallString" "$\"$INSTDIR\${UNINSTALLER}$\""
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_ID}" "QuietUninstallString" "$\"$INSTDIR\${UNINSTALLER}$\" /S"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_ID}" "DisplayVersion" "${PRODUCT_VERSION}"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_ID}" "DisplayIcon" "$\"$INSTDIR\${EXECUTABLE}$\""
  ${GetSize} "$INSTDIR" "/S=0K" $0 $1 $2
  IntFmt $0 "0x%08X" $0
  WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_ID}" "EstimatedSize" "$0"
  RMDir /r $LOCALAPPDATA\${PRODUCT_ID}\${PRODUCT_ID}\Cache\*.*
SectionEnd


Section "Uninstall"
  Delete "$DESKTOP\${PRODUCT_NAME}.lnk"
  RMDir /r $INSTDIR
  RMDir /r $LOCALAPPDATA\${PRODUCT_ID}\${PRODUCT_ID}\Cache\*.*
  DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_ID}"
SectionEnd