#!/bin/bash

PYTHON_VERSION=3.11.8

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
  #CFLAGS="-I$(xcrun --show-sdk-path)/usr/include" LDFLAGS="-L$(brew --prefix sqlite)/lib" pyenv install ${PYTHON_VERSION}
  pyenv install ${PYTHON_VERSION}
fi
pyenv local ${PYTHON_VERSION}
python -m venv venv
export PATH=${BIN}:${PATH}

# Install mapview and patch, if not done already.
if [ ! -d "${SRC}/kivy_garden" ]; then
  ../install_mapview.sh
fi

# Copy source code to venv
cp -R ${SRC} ${VIRTUAL_ENV}

# Prep build environment.
cp ${LOC}/buildozer.spec ${TRG}/

echo "Building app..."
cd ${TRG}

pip install --upgrade pip kivy-ios virtualenv buildozer
#../bin/pip3 install --upgrade sqlite

#pip3 install --upgrade buildozer
#pip3 install --upgrade kivy-ios wheel pip setuptools virtualenv

buildozer ios debug

cp ${LOC}/flightlogviewer-Info.plist ${TRG}/.buildozer/ios/platform/kivy-ios/flightlogviewer-ios/
cp ${LOC}/main.m ${TRG}/.buildozer/ios/platform/kivy-ios/flightlogviewer-ios/
cp ${TRG}/assets/app-icon256.png ${TRG}/.buildozer/ios/platform/kivy-ios/flightlogviewer-ios/icon.png
cd ${TRG}
buildozer ios xcode

# cp -R ../venv/src/.buildozer/ios/platform/kivy-ios/flightlogviewer-2.1.1.intermediates/flightlogviewer-2.1.1.xcarchive/Products/Applications/flightlogviewer.app .
# zip -qq -r -9 flightlogviewer.ipa Payload

# Clean up
#${LOC}/../remove_build_artifacts.sh
