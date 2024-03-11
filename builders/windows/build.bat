rem Generate exe version file.
create-version-file ./app-version.yml --outfile ../../src/file_version_info.txt
cd ..\..\src
del /f /q /s build
del /f /q /s dist

rem Create spec file.
rem pyinstaller --name FlightLogViewer -i ./assets/app-icon256.png --version-file file_version_info.txt main.py

rem Run pyinstaller using the spec file.
pyinstaller FlightLogViewer.spec

cd ..\builders\windows