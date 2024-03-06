#!/bin/bash
cd $(dirname "$0")
LOC=$(pwd)
echo "Removing all build artifacts..."
rm -Rf ${LOC}/../src/.buildozer ${LOC}/../src/bin ${LOC}/../src/cache ${LOC}/../src/main.ini ${LOC}/../src/main.spec ${LOC}/../src/buildozer.spec