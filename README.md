# Flight Data Viewer
Flight Data Viewer that can read from Potensic flight-log files.

![Example Screenshot](<resources/screenshot1.png> "Example Screenshot")

This project is based on reverse engineering of the Potensic flight bin files and by trial and error. Only some of the basic metrics are currently pulled from this proprietary file format as not everything has been identified yet.

# How to run
On Windows or MacOS (x64) you can download and run one of the executables from the [Releases](<releases> "Releases") section.

On any platform or if you don't want or can't run the executables:
```sh
pip3 install tkintermapview
python3 extractFlightData.py
```

# How to build

MacOS:
```sh
pip3 install pyinstaller
pyinstaller extractFlightData.py --noconsole --onefile -i ./resources/app-icon256.png
sed -i -- "s/0\.0\.0/0.3.0-alpha/" dist/extractFlightData.app/Contents/Info.plist
```

Windows:
```sh
pip3 install pyinstaller
pip3 install pyinstaller-versionfile
create-version-file ./resources/app-version.yml --outfile file_version_info.txt
pyinstaller extractFlightData.py --noconsole --onefile -i ./resources/app-icon256.png --version-file file_version_info.txt
```

![selfie from a Potensic Atom SE](<resources/app-icon256.png> "Atom SE selfie")

# More Info

Check [here](<https://koenaerts.ca/micro-drones/parsing-potensic-flight-data-files/> "Parsing Potensic Flight Data Files").