#!/bin/bash

PYTHON_VERSION=3.11.10

platform=`uname`
if [ "${platform}" != 'Darwin' ]; then
  echo "For MacOS only."
  exit 1
fi

# Initialize
cd $(dirname "$0")
LOC=$(pwd)
SRC=${LOC}/../../src
export VIRTUAL_ENV=${LOC}/venv
BIN=${VIRTUAL_ENV}/bin
TRG=${VIRTUAL_ENV}/src

# Clean up
${LOC}/../remove_build_artifacts.sh
rm -Rf ${TRG}

# Set up python venv
if [ ! -d "${VIRTUAL_ENV}" ]; then
  echo "Setting up Python ${PYTHON_VERSION} virtual environment..."
  hasBrew=`which brew >/dev/null; echo $?`
  if [ ${hasBrew} -eq 1 ]; then
    echo "brew not installed or not found. For details: https://docs.brew.sh/Installation"
    exit 1
  fi
  hasPyenv=`brew list pyenv 2>/dev/null 1>&2; echo $?`
  if [ ${hasPyenv} -eq 1 ]; then
    echo "Installing pyenv..."
    brew install openssl readline sqlite3 xz zlib tcl-tk pyenv
    echo 'export PYENV_ROOT="$HOME/.pyenv"' >> ~/.bash_profile
    echo '[[ -d $PYENV_ROOT/bin ]] && export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.bash_profile
    echo 'eval "$(pyenv init -)"' >> ~/.bash_profile
  fi
  hasPyenv=`brew list pyenv 2>/dev/null 1>&2; echo $?`
  if [ ${hasPyenv} -eq 1 ]; then
    echo "Could not install pyenv. Install it manually and try again."
    exit 1
  fi
  . ~/.bash_profile
fi
hasPythonVersion=`pyenv versions | grep -c "${PYTHON_VERSION}"`
if [ ${hasPythonVersion} -eq 0 ]; then
  echo "Installing python ${PYTHON_VERSION}"
  pyenv install ${PYTHON_VERSION}
fi
pyenv local ${PYTHON_VERSION}
export PATH=${BIN}:${PATH}
python -m venv venv

# Install mapview and patch in source location, if not done already.
if [ ! -d "${SRC}/kivy_garden" ]; then
  ../install_mapview.sh
fi

# Prep build environment.
cp -R ${SRC} ${VIRTUAL_ENV}
cp ${LOC}/FlightLogViewer.spec ${TRG}/

echo "Building .app folder..."
cd ${TRG}

pip install pyinstaller==6.10.0 pyobjus==1.2.3
pip install -r requirements.txt

# Run pyinstaller using the spec file.
pyinstaller FlightLogViewer.spec

APPNAME="FlightLogViewer"
DIST="./dist"
APPDIR="${DIST}/${APPNAME}.app"
TMPDMG="${TRG}/${APPNAME}-tmp.dmg"
DMG="${TRG}/${APPNAME}.dmg"
IMG="${LOC}/background.png"
if [ ! -d "${APPDIR}" ]; then
  echo ".app folder not created."
  exit 1
fi

# Build .dmg package.
echo "Building .dmg package..."
rm -Rf "${DIST}/${APPNAME}"
ln -s /Applications "${DIST}/Applications"
mkdir "${DIST}/.background"
cp "${IMG}" "${DIST}/.background/"
du -sm "${APPDIR}" | awk '{print $1}' > "${TRG}/_size"
expr "$(cat ${TRG}/_size)" + 99 > "${TRG}/_size"
hdiutil create -srcfolder "${DIST}" -volname "${APPNAME}" -fs HFS+ -format UDRW -size "$(cat ${TRG}/_size)" "${TMPDMG}"
rm "${TRG}/_size"
hdiutil unmount "/Volumes/${APPNAME}"
DEVICE=$(hdiutil attach -readwrite -noverify "${TMPDMG}" | egrep '^/dev/' | sed 1q | awk '{print $1}')
sleep 2
echo '
   tell application "Finder"
     tell disk "'"${APPNAME}"'"
           open
           set current view of container window to icon view
           set toolbar visible of container window to false
           set statusbar visible of container window to false
           delay 1
           set the bounds of container window to {100, 100, 650, 501}
           delay 1
           set viewOptions to the icon view options of container window
           set arrangement of viewOptions to not arranged
           set icon size of viewOptions to 128
           set background picture of viewOptions to file ".background:'"$(basename "${IMG}")"'"
           set position of item "'"${APPNAME}.app"'" of container window to {160, 265}
           set position of item "Applications" of container window to {384, 265}
           close
           open
           update without registering applications
           delay 2
     end tell
   end tell
' | osascript
sync
sleep 10
hdiutil detach "${DEVICE}"
hdiutil convert "${TMPDMG}" -format UDZO -imagekey zlib-level=9 -o ${APPNAME}
rm -Rf "${TMPDMG}"

# Grab the generated dmg.
mv ${DMG} ${LOC}

# Clean up
#${LOC}/../remove_build_artifacts.sh
