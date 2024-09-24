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
rm -Rf ${VIRTUAL_ENV}
rm -Rf ${LOC}/.buildozer
rm -Rf ${LOC}/bin
rm -Rf ${LOC}/Payload

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
  #CFLAGS="-I$(xcrun --show-sdk-path)/usr/include" LDFLAGS="-L$(brew --prefix sqlite)/lib" pyenv install ${PYTHON_VERSION}
  pyenv install ${PYTHON_VERSION}
fi
pyenv local ${PYTHON_VERSION}
export PATH=${BIN}:${PATH}
python -m venv venv

# Install mapview and patch, if not done already.
if [ ! -d "${SRC}/kivy_garden" ]; then
  ../install_mapview.sh
fi

# Prep build environment.
cp -R ${SRC} ${VIRTUAL_ENV}
cp ${LOC}/buildozer.spec ${TRG}/

echo "Building app..."
cd ${TRG}

pip install --upgrade pip kivy-ios virtualenv buildozer

buildozer ios debug

echo "xode build done. Check the following files before proceeding (hit ENTER when done):"
echo "- diff ${LOC}/flightlogviewer-Info.plist ${TRG}/.buildozer/ios/platform/kivy-ios/flightlogviewer-ios/flightlogviewer-Info.plist"
echo "- diff ${LOC}/main.m ${TRG}/.buildozer/ios/platform/kivy-ios/flightlogviewer-ios/main.m"
read

cp ${LOC}/flightlogviewer-Info.plist ${TRG}/.buildozer/ios/platform/kivy-ios/flightlogviewer-ios/
cp ${LOC}/main.m ${TRG}/.buildozer/ios/platform/kivy-ios/flightlogviewer-ios/
cp ${TRG}/assets/app-icon256.png ${TRG}/.buildozer/ios/platform/kivy-ios/flightlogviewer-ios/icon.png
cd ${TRG}
buildozer ios xcode

echo "Once done with your xcode build, hit ENTER to proceed..."
echo "Steps:"
echo "- Under General, disable Automatically manage signing"
echo "- Under Build Settings, Set Code Signing Identities to blank value"
echo "- Under Build Settings, Set iOS Deployment Target to version 12 or greater"
echo "- Run Product / Build for Any iOS Device - arm64"
read

echo "Creating .ipa..."
rm -Rf ../../Payload
mkdir ../../Payload
#find .buildozer/ios/platform/kivy-ios/flightlogviewer-*intermediates -name "flightlogviewer.app" -exec cp -R {} ../../Payload \;
find ~/Library/Developer/Xcode/DerivedData/flightlogviewer-*/Build/Products/Debug-iphoneos -name "flightlogviewer.app" -exec cp -R {} ../../Payload \;
cd ../..
zip -qq -r -9 flightlogviewer.ipa Payload

# Clean up
#${LOC}/../remove_build_artifacts.sh
