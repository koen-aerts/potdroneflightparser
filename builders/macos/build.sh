#!/bin/bash

PYTHON_VERSION=3.11.13
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

is_macho() {
  # Return 0 if file is a Mach-O binary (dylib, bundle, executable)
  local f="$1"
  [[ -f "$f" ]] || return 1
  file "$f" | grep -q "Mach-O"
}

merge_macho() {
  # lipo merge two binaries into a universal2 output
  local arm="$1"
  local x86="$2"
  local out="$3"

  # Strip existing signatures (codesigning breaks when merging)
  codesign --remove-signature "$arm" >/dev/null 2>&1 || true
  codesign --remove-signature "$x86" >/dev/null 2>&1 || true

  mkdir -p "$(dirname "$out")"
  lipo -create -output "$out" "$arm" "$x86"

  # Optional: ad-hoc sign to keep Gatekeeper happy in dev workflows
  codesign -s - --force --timestamp=none "$out" >/dev/null 2>&1 || true
}

copy_if_absent() {
  local src="$1"
  local dst="$2"
  mkdir -p "$(dirname "$dst")"
  cp -p "$src" "$dst"
}

# Build for both ARM and x86.
build_for_arch arm64 "/opt/homebrew/bin/python3.11"
build_for_arch x86_64 "/usr/local/bin/python3.11"

echo "############################"
echo "# MERGING BINARIES TO UNIVERSAL ..."
echo "############################"

cd ${LOC}
DIST="${LOC}/dist"
APPDIR="${DIST}/${APPNAME}.app"
TMPDMG="${DIST}/${APPNAME}-tmp.dmg"
IMG="${LOC}/background.png"

# Merge both builds into 1 for universal.
mkdir -p ${APPDIR}
out_root="${APPDIR}"
arm_root="${LOC}/build/venv_arm64/src/dist/${APPNAME}.app"
x86_root="${LOC}/build/venv_x86_64/src/dist/${APPNAME}.app"
rsync -a --delete --exclude '*.DS_Store' "$arm_root/" "$out_root/"

# Walk the arm tree; for each Mach-O find counterpart in x86 tree and merge
while IFS= read -r -d '' arm_path; do
  rel="${arm_path#$arm_root/}"
  x86_path="${x86_root}/${rel}"
  out_path="${out_root}/${rel}"

  if [[ -f "$x86_path" ]] && is_macho "$arm_path" && is_macho "$x86_path"; then
    merge_macho "$arm_path" "$x86_path" "$out_path"
  fi
done < <(find "$arm_root" -type f -print0)

# Sometimes x86 package contains Mach-Os that arm didn’t have (rare but possible).
# Walk x86 tree to catch those.
while IFS= read -r -d '' x86_path; do
  rel="${x86_path#$x86_root/}"
  arm_path="${arm_root}/${rel}"
  out_path="${out_root}/${rel}"

  if [[ ! -e "$arm_path" ]] && is_macho "$x86_path"; then
    # Single-arch Mach-O exists only on x86 side; include it (can still run under Rosetta).
    copy_if_absent "$x86_path" "$out_path"
  fi
done < <(find "$x86_root" -type f -print0)


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
