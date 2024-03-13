#!/bin/bash

# Initialize
cd $(dirname "$0")
LOC=$(pwd)
SRC=${LOC}/../../src/

# Clean up
${LOC}/../remove_build_artifacts.sh

# Prep build environment.
cp ${LOC}/FlightLogViewer.spec ${SRC}

# Install mapview and patch, if not done already.
if [ ! -d "${SRC}/kivy_garden" ]; then
  ../install_mapview.sh
fi

# Run pyinstaller using the spec file.
echo "Building .app folder"
cd ${SRC}
pyinstaller FlightLogViewer.spec

APPNAME="FlightLogViewer"
DIST="./dist"
APPDIR="${DIST}/${APPNAME}.app"
TMPDMG="${SRC}/${APPNAME}-tmp.dmg"
DMG="${SRC}/${APPNAME}.dmg"
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
du -sm "${APPDIR}" | awk '{print $1}' > "${SRC}/_size"
expr "$(cat ${SRC}/_size)" + 99 > "${SRC}/_size"
hdiutil create -srcfolder "${DIST}" -volname "${APPNAME}" -fs HFS+ -format UDRW -size "$(cat ${SRC}/_size)" "${TMPDMG}"
rm "${SRC}/_size"
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
