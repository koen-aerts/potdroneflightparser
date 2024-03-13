#!/bin/bash

# Initialize
cd $(dirname "$0")
LOC=$(pwd)
SRC=${LOC}/../../src/

# Clean up
${LOC}/../remove_build_artifacts.sh

# Prep build environment.
cp ${LOC}/buildozer.spec ${SRC}

# Install mapview and patch, if not done already.
if [ ! -d "${SRC}/kivy_garden" ]; then
  ../install_mapview.sh
fi

# Build builder image if there isn't one.
ic=$(docker images | grep -c fdv-apk-builder)
if [ ${ic} -eq 0 ]; then
  echo "Building docker build image..."
  docker build -t fdv-apk-builder --progress plain -f ${LOC}/Dockerfile ${SRC}
  ${LOC}/../remove_build_artifacts.sh
fi

# Run the build container.
echo "Running docker build container..."
docker run -it -u builder -v ${SRC}:/home/builder/source fdv-apk-builder:latest /bin/sh -lc "cd source; buildozer android debug"

# Grab the generated apk.
APKNAME=`ls ${SRC}/bin/*.apk | sed -E "s/.*\/([^-]+-[^-]+)[^\.]*.(.*)/\1.\2/"`
mv ${SRC}/bin/*.apk ${LOC}/${APKNAME}

# Clean up
#${LOC}/../remove_build_artifacts.sh
