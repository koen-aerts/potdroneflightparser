# Flight Log Viewer
Flight Log Viewer that can read from Potensic flight-log files.

Models confirmed working are the Atom and Atom SE (both first and second generations).

![Example Screenshot](<resources/screenshot1.png> "Example Screenshot")

This project is based on reverse engineering of the Potensic flight bin files (mainly based on a first generation Atom SE as well as log files shared by contributors for other Potensic models), and by trial and error. Not all available metrics are currently pulled from this proprietary file format as not everything has been identified yet.

# 1. How to run
## 1.1. Pre-Built
On Windows, MacOS (x64/ARM), or Android devices, you can download and run one of the executables from the [Releases](<../../releases> "Releases") section.

### 1.1.1 Windows
Download the zip file and unpack it. Run the .exe installer like you would any other app. You may see Windows Defender or your virus scanner warn you about running content from the Internet and try to scare you away from proceeding with the install. If you carefully read the messages, you should be able to get past this and run the installer. Sometimes the options on proceeding with the running of the .exe are hidden behind other links or buttons in the alert windows and may not seem intuitive.

To uninstall, run the uninstaller that comes with the app. In many cases, it should be located here: C:\Program Files (x86)\Flight Log Viewer\uninstaller.exe

You can also delete the app's configuration and cache, which is usally located at: C:\Users\[your_user_name]\AppData\Local\FlightLogViewer

### 1.1.2 MacOS
Download the zip file and unpack it. Run the .dmg package and slide the App's icon into the Application folder. After that you should unmount/eject the .dmg volume in Finder. You may see MacOS warn you about running content from the Internet but you should be able to accept this and run the app.

To uninstall, delete FlightLogViewer from your Applications.

You can also delete the app's configuration and cache, which is usally located at: /Users/[your_user_name]/Library/Application Support/FlightLogViewer and /Users/[your_user_name]/Library/Caches/FlightLogViewer.

### 1.2.3 Android
Download the .apk file to your device and open it. Depending on your Android version and settings, you will see several warnings about running content from the Internet. You may need to allow the app from which you are launching the apk (web browser or file browser) to launch the apk, and in addition, you will have to read the warnings that will try to stop you from installing the app. There will be options along the way to accept the risk and proceed with the install, albeit those options may not appear until you click on certain links or buttons in the alert popup. You may miss it the first time, so simply try again. It is anything but intuitive, however, there are not too many options to select from.

Uninstalling the app is the same as you would for any other app.

## 1.2. From Source
You can run the app directly from source. Use Python 3.11 or greater.

First, you need to [install Python](<https://www.python.org/downloads/> "Download Python") on your platform. Version 3.11 or greater is recommended.

Then install the dependencies:
```sh
pip3 install platformdirs==4.2.0
pip3 install kivy==2.3.0
pip3 install https://github.com/kivymd/KivyMD/archive/master.zip#sha256=1f4afa03664d6af76dba6ba24d70bd2e6b2692a6c394a0ba672a9f0fdce1ccc6
pip3 install mapview==1.0.6
```
Once you have those, you can run the app as follows:
```sh
python3 main.py
```

![selfie from a Potensic Atom SE](<src/assets/app-icon256.png> "Atom SE selfie")

# More Info
Check [here](<https://koenaerts.ca/micro-drones/parsing-potensic-flight-data-files/> "Parsing Potensic Flight Data Files").

# Acknowledgements
Many thanks to Rob Pritt for contributing to the project.
