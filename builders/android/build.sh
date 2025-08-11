#!/bin/bash

# Initialize
cd $(dirname "$0")
LOC=$(pwd)
SRC=${LOC}/../../src
TRG=${LOC}/src

# Clean up
${LOC}/../remove_build_artifacts.sh
rm -Rf ${TRG}
cc=$(docker ps -a | grep -c fdv-apk-builder)
if [ ${cc} -ne 0 ]; then
  echo "Removing old build container..."
  docker rm fdv-apk-builder
fi
ic=$(docker images | grep -c fdv-apk-builder)
if [ ${ic} -ne 0 ]; then
  echo "Removing old build image..."
  docker rmi fdv-apk-builder
fi

# Install mapview and patch, if not done already.
if [ ! -d "${SRC}/kivy_garden" ]; then
  ../install_mapview.sh
fi

# Prep build environment.
cp -R ${SRC} ${LOC}
rm -Rf ${TRG}/venv
cp ${LOC}/buildozer.spec ${TRG}/

# Build builder image if there isn't one.
ic=$(docker images | grep -c fdv-apk-builder)
if [ ${ic} -eq 0 ]; then
  echo "Building APK in docker image..."
  docker buildx build --platform linux/amd64 -t fdv-apk-builder --progress plain -f ${LOC}/Dockerfile ${TRG}
fi

# Run the build container.
echo "Pulling APK from the docker build image..."
docker run --name fdv-apk-builder -it -u builder -v ${LOC}:/home/builder/out fdv-apk-builder:latest /bin/sh -lc "cp source/bin/*.apk /home/builder/out/"

ls -al ${LOC}
APKNAME=`ls ${LOC}/*.apk | sed -E "s/.*\/([^-]+).*\.(.*)/\1.\2/"`
mv ${LOC}/*.apk ${LOC}/${APKNAME}
ls -al ${LOC}

# Clean up
${LOC}/../remove_build_artifacts.sh
cc=$(docker ps -a | grep -c fdv-apk-builder)
if [ ${cc} -ne 0 ]; then
  echo "Removing build container..."
  docker rm fdv-apk-builder
fi
ic=$(docker images | grep -c fdv-apk-builder)
if [ ${ic} -ne 0 ]; then
  echo "Removing build image..."
  docker rmi fdv-apk-builder
fi