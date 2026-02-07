#!/bin/bash

PYTHON_VERSION=3.13.12
APPNAME="FlightLogViewer"

platform=`uname`
if [ "${platform}" != 'Darwin' ]; then
  echo "For MacOS only."
  exit 1
fi

echo "############################"
echo "# INITIALIZING ..."
echo "############################"

# Initialize
cd $(dirname "$0")
LOC=$(pwd)
SRC=${LOC}/../../src
${LOC}/../remove_build_artifacts.sh

cd ${LOC}
rm -Rf dist build ${APPNAME}.dmg

# Funcion that builds the code to .app binary.
build_for_arch() {
  local arch="$1"
  local pyexe="$2"

  echo "############################"
  echo "# BUILDING FOR ${arch} ..."
  echo "############################"

  cd ${LOC}

  export VIRTUAL_ENV=${LOC}/build/venv_${arch}
  BIN=${VIRTUAL_ENV}/bin
  TRG=${VIRTUAL_ENV}/src
  POB=${VIRTUAL_ENV}/pyobjus

  # Clean up
  rm -Rf ${TRG}

  arch -${arch} ${pyexe} -m venv build/venv_${arch}

  # Install mapview and patch in source location, if not done already.
  if [ ! -d "${SRC}/kivy_garden" ]; then
    ../install_mapview.sh
  fi

  # Prep build environment.
  cp -R ${SRC} ${VIRTUAL_ENV}
  cp ${LOC}/FlightLogViewer.spec ${TRG}/

  cd ${VIRTUAL_ENV}

  echo "Installing dependencies..."
  arch -${arch} ${BIN}/pip3 install pyinstaller==6.10.0 Cython==3.0.12

  echo "Building pyobjus..."
  git clone https://github.com/kivy/pyobjus.git
  cd ${POB}
  arch -${arch} make build_ext
  arch -${arch} ${BIN}/python3 setup.py install

  echo "Building .app folder..."
  cd ${TRG}
  arch -${arch} ${BIN}/pip3 install -r requirements.txt

  # Run pyinstaller using the spec file.
  arch -${arch} ${BIN}/pyinstaller FlightLogViewer.spec

  DIST="./dist"
  APPDIR="${DIST}/${APPNAME}.app"
  if [ ! -d "${APPDIR}" ]; then
    echo ".app folder not created."
    exit 1
  fi
}

# Build for both ARM and x86.
build_for_arch arm64 "/opt/homebrew/bin/python3.13"

DIST="${LOC}/dist"
mkdir -p ${DIST}
mv ./dist/* ${DIST}

cd ${LOC}
APPDIR="${DIST}/${APPNAME}.app"
TMPDMG="${DIST}/${APPNAME}-tmp.dmg"
IMG="${LOC}/background.png"

echo "############################"
echo "# BUILDING DMG ..."
echo "############################"

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

# Clean up
#${LOC}/../remove_build_artifacts.sh
