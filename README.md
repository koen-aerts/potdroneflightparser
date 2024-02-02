# Flight Data Viewer
Flight Data Viewer that can read from Potensic flight-log files.

Models confirmed working are the Atom and Atom SE (both first and second generations).

Incomplete and experimental support for P1A (Dreamer).

![Example Screenshot](<resources/screenshot1.png> "Example Screenshot")

This project is based on reverse engineering of the Potensic flight bin files (mainly based on a first generation Atom SE as well as log files shared by contributors for other Potensic models), and by trial and error. Not all available metrics are currently pulled from this proprietary file format as not everything has been identified yet.

# How to run
## Pre-Built
On Windows or MacOS (x64/ARM) you can download and run one of the executables from the [Releases](<../../releases> "Releases") section.

On MacOS, you may see warnings or errors that will prevent you from running the app. This is a standard defense mechanism to prevent users from accidentally running arbitrary content that comes from the Internet. Depending on your version, the message could say something along the lines of the app is broken or dangerous, and it will prevent you from executing it and instead give you a cancel or delete option.

![MacOS Application Warning](<resources/broken_app_message.png> "MacOS Application Warning")

To solve this, you can remove the Extended Attributes from the file. You will have to open a Terminal and use the xattr command to remove the attributes. Example:

```sh
% cd ~/Downloads
% unzip ./extractFlightData_macos_x86_v1.2.0.zip
% xattr -r -d "com.apple.quarantine" extractFlightData.app
% sudo mv extractFlightData.app /Applications
```

On Windows, your may see a similar warning about dangerous content from the Internet, or Microsoft Defender can raise a false positive about the binary being infected. The binaries are not signed (because I'm not willing to pay Microsoft for this) and contain Python binaries, which also tend to throw off Defender. It should give you the option to ignore and continue.

## From Source
If you don't have MacOS or Windows, you can run the application directly on almost any other platform that supports Python.

First, you need to [install Python](<https://www.python.org/downloads/> "Download Python") on your platform. Version 3.11 or greater is recommended.

The basic steps for running the app are something along the following:
```sh
pip3 install platformdirs
pip3 install tkintermapview
python3 extractFlightData.py
```

You can also run this software on Android devices that can run [Pydroid 3](<https://play.google.com/store/apps/details?id=ru.iiec.pydroid3> "Google Play - Pydroid 3 - IDE for Python 3"). Make sure to use the pip function in Pydroid to install the dependency shown in the above commands before you can run this software. Refer to the [PDF with screenshots](<resources/android_install.pdf> "Android Installation Steps") for more details.

![Android Screenshot](<resources/screenshot2.jpg> "Android Screenshot")

# How to build binaries (optional)
## MacOS
```sh
pip3 install platformdirs
pip3 install pyinstaller
pyinstaller extractFlightData.py --noconsole --onefile -i ./resources/app-icon256.png
sed -i -- "s/0\.0\.0/1.3.2/" dist/extractFlightData.app/Contents/Info.plist
```

## Windows
```sh
pip3 install platformdirs
pip3 install pyinstaller
pip3 install pyinstaller-versionfile
create-version-file ./resources/app-version.yml --outfile file_version_info.txt
pyinstaller extractFlightData.py --noconsole --onefile -i ./resources/app-icon256.png --version-file file_version_info.txt
```

![selfie from a Potensic Atom SE](<resources/app-icon256.png> "Atom SE selfie")

# More Info
Check [here](<https://koenaerts.ca/micro-drones/parsing-potensic-flight-data-files/> "Parsing Potensic Flight Data Files").

# Acknowledgements
Many thanks to Rob Pritt for contributing to the project.
