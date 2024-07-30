# Flight Log Viewer
Flight Log Viewer that can read from Potensic flight-log files.

Models confirmed working are the Atom and Atom SE (both first and second generations).

![Screenshot Map](<resources/screenshot1.png> "Screenshot Map")

![Screenshot Log Files](<resources/screenshot2.png> "Screenshot Log Files")

This project is based on reverse engineering of the Potensic flight bin files (mainly based on a first generation Atom SE as well as log files shared by contributors for other Potensic models), and by trial and error. Not all available metrics are currently pulled from this proprietary file format as not everything has been identified yet.

# 1. Using the app

![App Log Buttons](<resources/buttons2.png> "App Log Buttons")

![App File Buttons](<resources/buttons1.png> "App File Buttons")

# 2. Installing the app
## 2.1. Pre-Built
On Windows, MacOS (x64/ARM), Android, or iOS, you can download and run one of the executables from the [Releases](<../../releases> "Releases") section.

### 2.1.1 Windows
Download the zip file and unpack it. Run the .exe installer like you would any other app. You may see Windows Defender or your virus scanner warn you about running content from the Internet and try to scare you away from proceeding with the install. If you carefully read the messages, you should be able to get past this and run the installer. Sometimes the options on proceeding with the running of the .exe are hidden behind other links or buttons in the alert windows and may not seem intuitive.

To uninstall, run the uninstaller that comes with the app. In many cases, it should be located here: ```C:\Program Files (x86)\Flight Log Viewer\uninstaller.exe```

You can also delete the app's configuration and cache, which is usally located at: ```C:\Users\[your_user_name]\AppData\Local\FlightLogViewer```

If you are updating the app to a newer version, you should be able to install on top of the existing app, so basically just install as if you were doing it for the first time. In case this does not work, you can uninstall the app first, then install the new version. Your existing data should not be affected unless you deleted the directory described above.

You may see a warning about dangerous content you downloaded from the Internet, or Microsoft Defender can raise a false positive about the binary being infected. The binaries are not signed (because I'm not willing to pay Microsoft for this) and contain Python binaries, which also tend to throw off Defender. It should give you the option to ignore and continue.

![Windows Defender Warning](<resources/wd1.png> "Windows Defender Warning")

![Windows Defender Run Anyway](<resources/wd2.png> "Windows Defender Run Anyway")

Likewise, any other virus scanner could flag a false positive on any binary you download from the Internet. You should be able to tell your scanner to ignore the warning. If you are unsure, you may be able to upload the contents of the "Flight Log Viewer" directory under "C:\Program Files (x86)" to your virus scanner website and ask for it to be whitelisted. They will analyse the app and whitelist it if deemed safe.

### 2.1.2 MacOS
Download the zip file and unpack it. Run the .dmg package and slide the App's icon into the Application folder. After that you should unmount/eject the .dmg volume in Finder. You may see MacOS warn you about running content from the Internet but you should be able to accept this and run the app.

To uninstall, delete FlightLogViewer from your Applications just like you would with any other application.

You can also delete the app's configuration and cache, which is usally located at: ```/Users/[your_user_name]/Library/Application Support/FlightLogViewer``` and ```/Users/[your_user_name]/Library/Caches/FlightLogViewer```.

If you are updating the app to a newer version, you should be able to install on top of the existing app, so basically just install as if you were doing it for the first time. In case this does not work, you can uninstall the app first, then install the new version. Your existing data should not be affected unless you deleted the directory described above.

You may see warnings or errors that will prevent you from running the app. This is a standard defense mechanism to prevent users from accidentally running arbitrary content that comes from the Internet. Depending on your OS version, the message may be misleading and could say something along the lines of the app is broken or dangerous, and it will prevent you from executing it and instead give you a cancel or delete option.

![MacOS Application Warning](<resources/broken_app_message.png> "MacOS Application Warning")

To solve this, you can remove the Extended Attributes from the file. You will have to open a Terminal and use the xattr command to remove the attributes. Example:

```sh
% cd ~/Downloads
% xattr -r -c ./FlightLogViewer_macos_[arch]_v[x].[x].[x].zip
% unzip ./FlightLogViewer_macos_[arch]_v[x].[x].[x].zip
```

### 2.2.3 Android
Download the .apk file to your device and open it. Depending on your Android version and settings, you will see several warnings about running content from the Internet. You may need to allow the app from which you are launching the apk (web browser or file browser) to launch the apk, and in addition, you will have to read the warnings that will try to stop you from installing the app. There will be options along the way to accept the risk and proceed with the install, albeit those options may not appear until you click on certain links or buttons in the alert pop-ups. You may miss it the first time, so simply try again. It is anything but intuitive, however, there are not too many different options to select from. Most devices will allow you to install anything you want, but will attempt to discourage you to do so.

Uninstalling the app is the same as you would for any other mobile app. This action will also delete all the data that is stored within the app, which includes imported log files and preferences.

If you are updating the app to a newer version, you should be able to install on top of the existing app. If this does not work, use the app's backup feature first to back up your data. It will be saved to a zip file, so make sure you pay attention where you save it. Then you can uninstall the app and install the new version. Once you have the new version running, you will be able to import the backup zip file into the app to restore your data.


### 2.2.4 iOS
Option 1: Download the .ipa file to your Mac or Windows computer. Use [Sideloadly](<https://sideloadly.io/> "Sideloadly") to side-load it to your iPhone or iPad. No jailbreak required but you need to re-sync the app from your computer every 7 days.

Option 2: Install [Trollstore](<https://ios.cfw.guide/installing-trollstore/> "Trollstore") on your mobile device.

![iOS Apps](<resources/ios_desktop1.png> "iOS Apps")

Then download the .ipa file to your device and install it via the Trollstore app. No jailbreak required.

Option 3: [Jailbreak](<https://ios.cfw.guide/get-started/> "iOS Jailbreak Guide") your iOS device, allowing you to install many 3rd party apps that are not available through the Apple Store.

Note about the iOS version of this app. Unlike on the other platforms, the app does not open a File Browser when you want to import a log file or save a CSV or backup. Instead, you use the standard File Browser on your device to copy files in and out of the Flight Log Viewer Documents folder. You copy the log zip files into that folder, then use the app's import button to import one log file at a time.

![iOS File Browser](<resources/ios_file_browser1.png> "iOS File Browser")

Once imported, the log file will disappear from the Documents folder. Similarly, when you export a CSV file or a backup, the file will be created in the app's Documents folder, from where you can then copy it to other locations.

![App Documents Folder](<resources/ios_file_browser2.png> "App Documents Folder")

## 2.2. From Source
You can run the app directly from source. Use Python 3.11 or greater.

First, you need to [install Python](<https://www.python.org/downloads/> "Download Python") on your platform. Version 3.11 or greater is recommended.

Then cd to the src directory and install the dependencies:
```sh
pip install -r requirements.txt
```
Once you have those, you can run the app as follows:
```sh
python main.py
```

![selfie from a Potensic Atom SE](<src/assets/app-icon256.png> "Atom SE selfie")


# More Info
Check [here](<https://koenaerts.ca/micro-drones/parsing-potensic-flight-data-files/> "Parsing Potensic Flight Data Files").


# Problems or have questions?
Join the [Potensic Atom Flight Log Viewer](<https://www.facebook.com/groups/2607329356109479>) Facebook group.


# Acknowledgements
Many thanks to Rob Pritt and Chris Raynak for their very significant contributions to the project, and the many other users for their feedback and willingness to share their log files that help make this app better with each release.

A special thank-you goes to the following people who kindly provided the following languages for the app:

- French: PJ Guyot
- Spanish: Pepito Ruiz
- Italian: Stefano Rapegno
- Indonesian: Lio
