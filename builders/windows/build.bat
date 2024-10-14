@echo off

rem Generate exe version file, for Windows 10 and up.
rem Run this script in a CMD window and in the same directory. Do not run through file explorer.
rem Pre-Requisites:
rem   Python (3.11.8 or greater): https://www.python.org/downloads/
rem   NSIS (3.08 or greater): https://nsis.sourceforge.io/Download
rem   pyenv: this script will show the installation steps when you run it

rem Note: 3.11.10 not available in pyenv
set PYTHON_VERSION=3.11.9

IF not "%OS%"=="Windows_NT" (
  echo For Windows Only
  exit /b
)

set thisDir=%cd%
if not exist "%thisDir%\build.bat" (
  echo Run this script from a CMD prompt and from the same directory.
  exit /b
)

FOR %%I in (.) DO set LOC=%%~fI
set SRC=%LOC%\..\..\src
set VIRTUAL_ENV=%LOC%\venv
set BIN=%VIRTUAL_ENV%\Scripts
set TRG=%VIRTUAL_ENV%\src

rmdir /q /s "%TRG%" 2>NUL

IF NOT EXIST "%VIRTUAL_ENV%\" (
  echo Setting up Python %PYTHON_VERSION% virtual environment...
  IF NOT EXIST "%USERPROFILE%\.pyenv\" (
    echo Please install pyenv for Windows using the pip method. You need to have Python 3.11 or greater installed.
    echo.
    echo Install commands:
    echo.    pip install pyenv-win --target "%%USERPROFILE%%\\.pyenv"
    echo.    Run after first install: "%%USERPROFILE%%\\.pyenv\pyenv-win\bin\pyenv.bat" update
    echo.
    echo Info:
    echo.    https://github.com/pyenv-win/pyenv-win/blob/master/docs/installation.md#python-pip
    exit /b
  )
)

set PATH=%BIN%;%USERPROFILE%\.pyenv\pyenv-win\shims;%USERPROFILE%\.pyenv\pyenv-win\bin;%PATH%
pyenv versions | find /c "%PYTHON_VERSION%" > NUL
IF NOT %ERRORLEVEL% EQU 0 (
  echo Installing Python %PYTHON_VERSION%...
  cmd /c "pyenv install %PYTHON_VERSION%"
)

echo %PYTHON_VERSION% > .python-version
cmd /c "python --version"
cmd /c "python -m venv venv"

if not exist "%SRC%\kivy_garden\" (
  echo Installing Kivy Garden...
  cd "%SRC%"
  curl -OL https://github.com/kivy-garden/mapview/archive/refs/tags/1.0.6.zip
  tar -xf 1.0.6.zip
  move mapview-1.0.6\kivy_garden .
  del /f /q /s 1.0.6.zip
  rmdir /q /s mapview-1.0.6
  copy ..\builders\mapview_constants.py .\kivy_garden\mapview\constants.py
  cd ..\builders\windows
)

echo Preparing build environment.
xcopy "%SRC%" "%TRG%" /e /q /i
copy "%LOC%\FlightLogViewer.spec" "%TRG%\"

cd "%TRG%"

pip install pyinstaller==6.10.0
pip install pyinstaller-versionfile==2.1.1
pip install -r requirements.txt

create-version-file ..\..\app-version.yml --outfile .\file_version_info.txt
copy ..\..\FlightLogViewer.spec .

rmdir /q /s build 2>NUL
rmdir /q /s dist 2>NUL

rem If running this in a VM, you may encounter OpenGL issues: https://koenaerts.ca/run-kivy-on-virtualbox-windows-guest/
rem Download opengl32.dll and save in a location outside of this project, then update the path below to point to it.
set OPENGL_FIX=C:\projects\MesaForWindows-x64-20.1.8\opengl32.dll
IF EXIST "%OPENGL_FIX%" (
  copy %OPENGL_FIX% ..\share\sdl2\bin\
)

echo Building executables...
pyinstaller FlightLogViewer.spec

cd ..\..

echo Building installer...
"C:\Program Files (x86)\NSIS\makensis.exe" .\FlightLogViewer.nsi
