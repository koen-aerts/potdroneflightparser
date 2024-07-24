rem Generate exe version file.
create-version-file ./app-version.yml --outfile ../../src/file_version_info.txt
copy FlightLogViewer.spec ..\..\src\
cd ..\..\src
rmdir /q /s build
rmdir /q /s dist

if not exist kivy_garden\ (
  curl -OL https://github.com/kivy-garden/mapview/archive/refs/tags/1.0.6.zip
  tar -xf 1.0.6.zip
  move mapview-1.0.6\kivy_garden .
  del /f /q /s 1.0.6.zip
  rmdir /q /s mapview-1.0.6
  copy ..\builders\mapview_constants.py .\kivy_garden\mapview\constants.py
)

rem Run pyinstaller using the spec file. Install version 5 since as of version 6 and up, assets are not correctly included in the build.
pyinstaller FlightLogViewer.spec

del /f /q FlightLogViewer.spec
cd ..\builders\windows

"C:\Program Files (x86)\NSIS\makensis.exe" .\FlightLogViewer.nsi
