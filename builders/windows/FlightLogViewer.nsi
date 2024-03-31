# Package script for nullsoft NSIS 3.08 or higher.

!define PRODUCT_NAME "Flight Log Viewer"
!define PRODUCT_VERSION "2.1.0"
!define EXECUTABLE "FlightLogViewer.exe"

# define installer name
OutFile "install_flightlogviewer_v${PRODUCT_VERSION}.exe"

# set desktop as install directory
InstallDir "$PROGRAMFILES\${PRODUCT_NAME}"


Section "install"
  SetOutPath $INSTDIR
  File /r ..\..\src\dist\FlightLogViewer\*.*
  WriteUninstaller $INSTDIR\uninstaller.exe
  CreateShortCut "$DESKTOP\${PRODUCT_NAME}.lnk" "$INSTDIR\${EXECUTABLE}" ""
SectionEnd


Section "Uninstall"
  Delete "$DESKTOP\${PRODUCT_NAME}.lnk"
  RMDir /r $INSTDIR
SectionEnd