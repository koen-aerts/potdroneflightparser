#!/bin/bash
cd $(dirname "$0")
LOC=$(pwd)
echo "Removing all build artifacts..."
rm -Rf ${LOC}/../src/__pycache__ ${LOC}/../src/.buildozer ${LOC}/../src/bin ${LOC}/../src/cache rm -Rf ${LOC}/../src/build ${LOC}/../src/dist ${LOC}/../src/*.ini ${LOC}/../src/*.spec ${LOC}/../src/*.dmg