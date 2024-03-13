#!/bin/bash

# Initialize
cd $(dirname "$0")
LOC=$(pwd)
SRC=${LOC}/../src/

echo "Downloading mapview..."
cd ${SRC}
curl -OL https://github.com/kivy-garden/mapview/archive/refs/tags/1.0.6.zip
unzip 1.0.6.zip
mv mapview-1.0.6/kivy_garden .
rm -Rf 1.0.6.zip mapview-1.0.6

echo "Applying patch..."
cd ${LOC}
cp mapview_constants.py ${SRC}/kivy_garden/mapview/constants.py
