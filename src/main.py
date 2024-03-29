import os
import glob
import shutil
import struct
import math
import datetime
import tempfile
import time
import re
import threading
import locale

from enum import Enum

from kivy.core.window import Window
Window.allow_screensaver = False

from platformdirs import user_config_dir

from kivy.utils import platform
from kivy.config import Config
from kivymd.app import MDApp
from kivymd.uix.screen import MDScreen
from kivymd.uix.menu import MDDropdownMenu
from kivymd.uix.snackbar import MDSnackbar, MDSnackbarText
from kivymd.uix.label import MDLabel
from kivy.metrics import dp
from kivy_garden.mapview import MapSource, MapMarker, MarkerMapLayer
from kivy_garden.mapview.geojson import GeoJsonMapLayer
from kivy_garden.mapview.utils import haversine

if platform == 'android':
    from android.permissions import request_permissions, Permission
    from androidstorage4kivy import SharedStorage, Chooser
else:
    Window.maximize()
    from plyer import filechooser

from pathlib import Path, PurePath
from zipfile import ZipFile


class MotorStatus(Enum):
  UNKNOWN = 'Unknown'
  OFF = 'Off'
  IDLE = 'Idle'
  LIFT = 'Flying'


class SelectableMetrics(Enum):
  BASIC = 'Basic'
  ADVANCED = 'Advanced'
  DIAGNOSTICS = 'Diagnostics'


class SelectableTileServer(Enum):
  OPENSTREETMAP = 'OpenStreetMap'
  GOOGLE_STANDARD = 'Google Standard'
  GOOGLE_SATELLITE = 'Google Satellite'
  OPEN_TOPO = 'Open Topo'


class SelectablePlaybackSpeeds(Enum):
  REALTIME = 'Real-Time'
  FAST = 'Fast'
  FAST2 = 'Fast 2x'
  FAST4 = 'Fast 4x'
  FAST8 = 'Fast 8x'
  FAST16 = 'Fast 16x'
  FAST32 = 'Fast 32x'


class BaseScreen(MDScreen):
    ...


class MainApp(MDApp):

    '''
    Global variables and constants.
    '''
    appVersion = "v2.0.0-alpha"
    appName = "Flight Log Viewer"
    appTitle = f"{appName} - {appVersion}"
    defaultMapZoom = 3
    pathWidths = [ "1.0", "1.5", "2.0", "2.5", "3.0" ]
    assetColors = [ "#ed1c24", "#0000ff", "#22b14c", "#7f7f7f", "#ffffff", "#c3c3c3", "#000000", "#ffff00", "#a349a4", "#aad2fa" ]
    displayMode = "ATOM"
    columns = ('recnum', 'recid', 'flight','timestamp','tod','time','flightstatus','distance1','dist1lat','dist1lon','distance2','dist2lat','dist2lon','distance3','altitude1','altitude2','speed1','speed1lat','speed1lon','speed2','speed2lat','speed2lon','speed1vert','speed2vert','satellites','ctrllat','ctrllon','homelat','homelon','dronelat','dronelon','rssi','channel','flightctrlconnected','remoteconnected','gps','inuse','motor1status','motor2status','motor3status','motor4status')
    showColsBasicDreamer = ('flight','tod','time','altitude1','distance1','satellites','homelat','homelon','dronelat','dronelon')
    configFilename = 'FlightLogViewer.ini'


    '''
    Parse Atom based logs.
    '''
    def parse_atom_logs(self, droneModel, selectedFile):
        binLog = os.path.join(tempfile.gettempdir(), "flightdata")
        shutil.rmtree(binLog, ignore_errors=True) # Delete old temp files if they were missed before.

        with ZipFile(selectedFile, 'r') as unzip:
            unzip.extractall(path=binLog)

        self.reset()
        self.displayMode = "ATOM"
        self.zipFilename = selectedFile

        # First read the FPV file. The presence of this file is optional. The format of this
        # file differs slightly based on the mobile platform it was created on: Android vs iOS.
        # Example filenames:
        #   - 20230819190421-AtomSE-iosSystem-iPhone13Pro-FPV.bin
        #   - 20230826161313-Atom SE-Android-(samsung)-FPV.bin
        fpvStat = {}
        files = sorted(glob.glob(os.path.join(binLog, '**/*-FPV.bin'), recursive=True))
        for file in files:
            with open(file, mode='rb') as fpvFile:
                while True:
                    fpvRecord = fpvFile.readline().decode("utf-8")
                    if not fpvRecord:
                        break
                    reclen = len(fpvRecord)
                    if (reclen == 19):
                        binval = fpvRecord[15:18].encode("ascii")
                        hex1 = ('0' + hex(binval[0])[2:])[-2:]
                        hex2 = ('0' + hex(binval[1])[2:])[-2:]
                        hex3 = ('0' + hex(binval[2])[2:])[-2:]
                        fpvStat[fpvRecord[:14]] = f'00{hex1}{hex2}{hex3}' # iOS
                    elif (reclen == 24):
                        fpvStat[fpvRecord[:14]] = fpvRecord[15:] # Android
            fpvFile.close()

        # Read the Flight Status files. These files are required to be present.
        files = sorted(glob.glob(os.path.join(binLog, '**/*-FC.bin'), recursive=True) + glob.glob(os.path.join(binLog, '**/*-FC.fc'), recursive=True))
        if (len(files) == 0):
            self.show_error_message(message=f'Log file is empty: {selectedFile}')
            return

        timestampMarkers = []

        # First grab timestamps from the filenames. Those are used to calculate the real timestamps with the elapsed time from each record.
        for file in files:
            timestampMarkers.append(datetime.datetime.strptime(re.sub("-.*", "", Path(file).stem), '%Y%m%d%H%M%S'))

        filenameTs = timestampMarkers[0]
        prevReadingTs = timestampMarkers[0]
        firstTs = None
        maxDist = 0
        maxAlt = 0
        maxSpeed = 0
        self.pathCoords = []
        self.flightStarts = {}
        self.flightEnds = {}
        self.flightStats = []
        pathCoord = []
        isNewPath = True
        isFlying = False
        recordCount = 0
        tableLen = 0
        for file in files:
            offset1 = 0
            offset2 = 0
            if file.endswith(".fc"):
                offset1 = -6
                offset2 = -10
            with open(file, mode='rb') as flightFile:
                while True:
                    fcRecord = flightFile.read(512)
                    if (len(fcRecord) < 512):
                        break

                    recordCount = recordCount + 1
                    recordId = struct.unpack('<I', fcRecord[0:4])[0] # This incremental record count is generated by the Potensic Pro app. All other fields are generated directly on the drone itself. The Potensic App saves these drone logs to the .bin files on the mobile device.
                    elapsed = struct.unpack('<Q', fcRecord[5:13])[0] # Microseconds elapsed since previous reading.
                    if (elapsed == 0):
                        continue # handle rare case of invalid record
                    satellites = struct.unpack('<B', fcRecord[46:47])[0] # Number of satellites.
                    dronelat = struct.unpack('<i', fcRecord[53+offset1:57+offset1])[0]/10000000 # Drone coords.
                    dronelon = struct.unpack('<i', fcRecord[57+offset1:61+offset1])[0]/10000000
                    ctrllat = struct.unpack('<i', fcRecord[159+offset2:163+offset2])[0]/10000000 # Controller coords.
                    ctrllon = struct.unpack('<i', fcRecord[163+offset2:167+offset2])[0]/10000000
                    homelat = struct.unpack('<i', fcRecord[435+offset2:439+offset2])[0]/10000000 # Home Point coords (for Return To Home).
                    homelon = struct.unpack('<i', fcRecord[439+offset2:443+offset2])[0]/10000000
                    dist1lat = self.dist_val(struct.unpack('f', fcRecord[235+offset2:239+offset2])[0]) # Distance home point vs controller??
                    dist1lon = self.dist_val(struct.unpack('f', fcRecord[239+offset2:243+offset2])[0])
                    dist2lat = self.dist_val(struct.unpack('f', fcRecord[319+offset2:323+offset2])[0]) # Distance home point vs controller??
                    dist2lon = self.dist_val(struct.unpack('f', fcRecord[323+offset2:327+offset2])[0])
                    dist1 = round(math.sqrt(math.pow(dist1lat, 2) + math.pow(dist1lon, 2)), 2) # Pythagoras to calculate real distance.
                    dist2 = round(math.sqrt(math.pow(dist2lat, 2) + math.pow(dist2lon, 2)), 2) # Pythagoras to calculate real distance.
                    dist3 = self.dist_val(struct.unpack('f', fcRecord[431+offset2:435+offset2])[0]) # Distance from home point, as reported by the drone.
                    gps = struct.unpack('f', fcRecord[279+offset2:283+offset2])[0] # GPS (-1 = no GPS, 0 = GPS ready, 2 and up = GPS in use)
                    gpsStatus = 'Yes' if gps >= 0 else 'No'
                    #sdff = (special - 2) * 4 * 60 * 1000
                    #elms = 0 if sdff < 0 else datetime.timedelta(milliseconds=sdff) # possibly elapsed flight time??
                    #flightCount = struct.unpack('<B', fcRecord[303+offset2:304+offset2])[0] # Some sort of counter.
                    #spec4 = struct.unpack('<B', fcRecord[304+offset2:305+offset2])[0] # ?
                    #spec5 = struct.unpack('<B', fcRecord[305+offset2:306+offset2])[0] # ?
                    #spec6 = struct.unpack('<B', fcRecord[306+offset2:307+offset2])[0] # ?
                    #spec7 = struct.unpack('<B', fcRecord[307+offset2:308+offset2])[0] # ?
                    motor1Stat = struct.unpack('<B', fcRecord[312+offset2:313+offset2])[0] # Motor 1 speed (3 = off, 4 = idle, 5 = low, 6 = medium, 7 = high)
                    motor2Stat = struct.unpack('<B', fcRecord[314+offset2:315+offset2])[0] # Motor 2 speed (3 = off, 4 = idle, 5 = low, 6 = medium, 7 = high)
                    motor3Stat = struct.unpack('<B', fcRecord[316+offset2:317+offset2])[0] # Motor 3 speed (3 = off, 4 = idle, 5 = low, 6 = medium, 7 = high)
                    motor4Stat = struct.unpack('<B', fcRecord[318+offset2:319+offset2])[0] # Motor 4 speed (3 = off, 4 = idle, 5 = low, 6 = medium, 7 = high)
                    droneInUse = struct.unpack('<B', fcRecord[295+offset2:296+offset2])[0] # Drone is detected "in action" (0 = flying or in use, 1 = not in use).
                    inUse = 'Yes' if droneInUse == 0 else 'No'

                    if (dist3 > maxDist):
                        maxDist = dist3
                    alt1 = round(self.dist_val(-struct.unpack('f', fcRecord[243+offset2:247+offset2])[0]), 2) # Relative height from controller vs distance to ground??
                    alt2 = round(self.dist_val(-struct.unpack('f', fcRecord[343+offset2:347+offset2])[0]), 2) # Relative height from controller vs distance to ground??
                    if (alt2 > maxAlt):
                        maxAlt = alt2
                    speed1lat = self.speed_val(struct.unpack('f', fcRecord[247+offset2:251+offset2])[0])
                    speed1lon = self.speed_val(struct.unpack('f', fcRecord[251+offset2:255+offset2])[0])
                    speed2lat = self.speed_val(struct.unpack('f', fcRecord[327+offset2:331+offset2])[0])
                    speed2lon = self.speed_val(struct.unpack('f', fcRecord[331+offset2:335+offset2])[0])
                    speed1 = round(math.sqrt(math.pow(speed1lat, 2) + math.pow(speed1lon, 2)), 2) # Pythagoras to calculate real speed.
                    speed2 = round(math.sqrt(math.pow(speed2lat, 2) + math.pow(speed2lon, 2)), 2) # Pythagoras to calculate real speed.
                    if (speed2 > maxSpeed):
                        maxSpeed = speed2
                    speed1vert = self.speed_val(-struct.unpack('f', fcRecord[255+offset2:259+offset2])[0])
                    speed2vert = self.speed_val(-struct.unpack('f', fcRecord[347+offset2:351+offset2])[0])

                    # Some checks to handle cases with bad or incomplete GPS data.
                    hasDroneCoords = dronelat != 0.0 and dronelon != 0.0
                    hasCtrlCoords = ctrllat != 0.0 and ctrllon != 0.0
                    hasHomeCoords = homelat != 0.0 and homelon != 0.0
                    sanDist = 0
                    if (hasDroneCoords and hasHomeCoords):
                        try:
                            sanDist = haversine(homelon, homelat, dronelon, dronelat)
                        except:
                            sanDist = 9999
                    elif (hasDroneCoords and hasCtrlCoords):
                        try:
                            sanDist = haversine(ctrllon, ctrllat, dronelon, dronelat)
                        except:
                            sanDist = 9999

                    hasValidCoords = sanDist < 20 and hasDroneCoords and (hasCtrlCoords or hasHomeCoords)

                    droneMotorStatus = MotorStatus.UNKNOWN
                    if motor1Stat > 4 or motor2Stat > 4 or motor3Stat > 4 or motor4Stat > 4:
                        droneMotorStatus = MotorStatus.LIFT
                    elif motor1Stat == 4 or motor2Stat == 4 or motor3Stat == 4 or motor4Stat == 4:
                        droneMotorStatus = MotorStatus.IDLE
                    elif motor1Stat == 3 and motor2Stat == 3 and motor3Stat == 3 and motor4Stat == 3:
                        droneMotorStatus = MotorStatus.OFF
                    statusChanged = False
                    if isFlying:
                        if droneMotorStatus == MotorStatus.OFF:
                            isFlying = False
                            statusChanged = True
                            firstTs = None
                    elif droneMotorStatus == MotorStatus.LIFT:
                        isFlying = True
                        statusChanged = True
                    else:
                        firstTs = None

                    # Calculate timestamp for the record.
                    readingTs = filenameTs + datetime.timedelta(milliseconds=(elapsed/1000))
                    while (readingTs < prevReadingTs):
                        # Line up to the next valid timestamp marker (pulled from the filenames).
                        try:
                            filenameTs = timestampMarkers.pop(0)
                            readingTs = filenameTs + datetime.timedelta(milliseconds=(elapsed/1000))
                        except:
                            # Handle rare case where log files contain mismatched "elapsed" indicators and times in bin filenames.
                            readingTs = prevReadingTs

                    # Calculate elapsed time for the flight.
                    if firstTs is None:
                        firstTs = readingTs
                    elapsedTs = readingTs - firstTs
                    elapsedTsRounded = elapsedTs - datetime.timedelta(microseconds=elapsedTs.microseconds) # truncate to milliseconds
                    prevReadingTs = readingTs

                    # Build paths for each flight and keep metric summaries of each path (flight), as well as for the entire log file.
                    pathNum = 0
                    if pathNum == len(self.flightStats):
                        self.flightStats.append([dist3, alt2, speed2, None, dronelat, dronelon, dronelat, dronelon])
                    else:
                        if dist3 > self.flightStats[pathNum][0]: # Overall Max distance
                            self.flightStats[pathNum][0] = dist3
                        if alt2 > self.flightStats[pathNum][1]: # Overall Max altitude
                            self.flightStats[pathNum][1] = alt2
                        if speed2 > self.flightStats[pathNum][2]: # Overall Max speed
                            self.flightStats[pathNum][2] = speed2
                        if dronelat < self.flightStats[pathNum][4]: # Overall Min latitude
                            self.flightStats[pathNum][4] = dronelat
                        if dronelon < self.flightStats[pathNum][5]: # Overall Min longitude
                            self.flightStats[pathNum][5] = dronelon
                        if dronelat > self.flightStats[pathNum][6]: # Overall Max latitude
                            self.flightStats[pathNum][6] = dronelat
                        if dronelon > self.flightStats[pathNum][7]: # Overall Max longitude
                            self.flightStats[pathNum][7] = dronelon
                    if (hasValidCoords):
                        if (statusChanged): # start new flight path if current one ends or new one begins.
                            if (len(pathCoord) > 0):
                                self.pathCoords.append(pathCoord)
                                pathCoord = []
                                isNewPath = True
                        if (isFlying): # Only trace path when the drone's motors are spinning faster than idle speeds.
                            pathNum = len(self.pathCoords)+1
                            if len(pathCoord) == 0:
                                pathCoord.append([])
                            lastSegment = pathCoord[len(pathCoord)-1]
                            lastCoord = lastSegment[len(lastSegment)-1] if len(lastSegment) > 0 else [9999, 9999]
                            if lastCoord[0] != dronelon or lastCoord[1] != dronelat: # Only include the point if it is different from the previous (i.e. drone moved)
                                if len(lastSegment) >= 200: # Break flight paths into segments because the map widget cannot handle too many points per path otherwise.
                                    lastCoord = lastSegment[len(lastSegment)-1]
                                    pathCoord.append([])
                                    lastSegment = pathCoord[len(pathCoord)-1]
                                    lastSegment.append(lastCoord)
                                lastSegment.append([dronelon, dronelat])
                            if pathNum == len(self.flightStats):
                                self.flightStats.append([dist3, alt2, speed2, elapsedTs, dronelat, dronelon, dronelat, dronelon])
                            else:
                                if dist3 > self.flightStats[pathNum][0]: # Flight Max distance
                                    self.flightStats[pathNum][0] = dist3
                                if alt2 > self.flightStats[pathNum][1]: # Flight Max altitude
                                    self.flightStats[pathNum][1] = alt2
                                if speed2 > self.flightStats[pathNum][2]: # Flight Max speed
                                    self.flightStats[pathNum][2] = speed2
                                self.flightStats[pathNum][3] = elapsedTsRounded # Flight duration
                                if dronelat < self.flightStats[pathNum][4]: # Flight Min latitude
                                    self.flightStats[pathNum][4] = dronelat
                                if dronelon < self.flightStats[pathNum][5]: # Flight Min longitude
                                    self.flightStats[pathNum][5] = dronelon
                                if dronelat > self.flightStats[pathNum][6]: # Flight Max latitude
                                    self.flightStats[pathNum][6] = dronelat
                                if dronelon > self.flightStats[pathNum][7]: # Flight Max longitude
                                    self.flightStats[pathNum][7] = dronelon

                    # Get corresponding record from the controller. There may not be one, or any at all. Match up to 5 seconds ago.
                    fpvRssi = ""
                    fpvChannel = ""
                    #fpvWirelessConnected = ""
                    fpvFlightCtrlConnected = ""
                    fpvRemoteConnected = ""
                    #fpvHighDbm = ""
                    fpvRecord = fpvStat.get(readingTs.strftime('%Y%m%d%H%M%S'))
                    secondsAgo = -1
                    while (not fpvRecord):
                        fpvRecord = fpvStat.get((readingTs + datetime.timedelta(seconds=secondsAgo)).strftime('%Y%m%d%H%M%S'))
                        if (secondsAgo <= -5):
                            break
                        secondsAgo = secondsAgo - 1
                    if (fpvRecord):
                        fpvRssi = str(int(fpvRecord[2:4], 16))
                        fpvChannel = str(int(fpvRecord[4:6], 16))
                        fpvFlags = int(fpvRecord[6:8], 16)
                        #fpvWirelessConnected = "1" if fpvFlags & 1 == 1 else "0"
                        fpvFlightCtrlConnected = "1" if fpvFlags & 2 == 2 else "0" # Drone to controller connection.
                        fpvRemoteConnected = "1" if fpvFlags & 4 == 4 else "0"
                        #fpvHighDbm = "1" if fpvFlags & 32 == 32 else "0"

                    flightDesc = f'{pathNum}'
                    if (isNewPath and len(pathCoord) > 0):
                        self.flightOptions.append(flightDesc)
                        self.flightStarts[flightDesc] = tableLen
                        isNewPath = False
                    if pathNum > 0:
                        self.flightEnds[flightDesc] = tableLen
                    self.logdata.append([recordCount, recordId, pathNum, readingTs.isoformat(sep=' '), readingTs.strftime('%X'), elapsedTs, droneMotorStatus.value, f"{self.fmt_num(dist1)}", f"{self.fmt_num(dist1lat)}", f"{self.fmt_num(dist1lon)}", f"{self.fmt_num(dist2)}", f"{self.fmt_num(dist2lat)}", f"{self.fmt_num(dist2lon)}", f"{self.fmt_num(dist3)}", f"{self.fmt_num(alt1)}", f"{self.fmt_num(alt2)}", f"{self.fmt_num(speed1)}", f"{self.fmt_num(speed1lat)}", f"{self.fmt_num(speed1lon)}", f"{self.fmt_num(speed2)}", f"{self.fmt_num(speed2lat)}", f"{self.fmt_num(speed2lon)}", f"{self.fmt_num(speed1vert)}", f"{self.fmt_num(speed2vert)}", str(satellites), str(ctrllat), str(ctrllon), str(homelat), str(homelon), str(dronelat), str(dronelon), fpvRssi, fpvChannel, fpvFlightCtrlConnected, fpvRemoteConnected, gpsStatus, inUse, motor1Stat, motor2Stat, motor3Stat, motor4Stat])
                    tableLen = tableLen + 1

            flightFile.close()

        shutil.rmtree(binLog, ignore_errors=True) # Delete temp files.

        self.title = f"{self.appTitle} - {PurePath(selectedFile).name}"
        if (len(pathCoord) > 0):
            self.pathCoords.append(pathCoord)
        self.generate_map_layers()
        if len(self.flightOptions) > 0:
            self.root.ids.selected_path.text = self.flightOptions[0]
        self.select_flight()
        for i in range(1, len(self.flightStats)):
            if self.flightStats[0][3] == None:
                self.flightStats[0][2] = self.flightStats[i][2]
                self.flightStats[0][3] = self.flightStats[i][3]
                self.flightStats[0][4] = self.flightStats[i][4]
                self.flightStats[0][5] = self.flightStats[i][5]
                self.flightStats[0][6] = self.flightStats[i][6]
                self.flightStats[0][7] = self.flightStats[i][7]
            else:
                self.flightStats[0][3] = self.flightStats[0][3] + self.flightStats[i][3]
                if self.flightStats[i][2] > self.flightStats[0][2]:
                    self.flightStats[0][2] = self.flightStats[i][2]
                if self.flightStats[i][4] < self.flightStats[0][4]:
                    self.flightStats[0][4] = self.flightStats[i][4]
                if self.flightStats[i][5] < self.flightStats[0][5]:
                    self.flightStats[0][5] = self.flightStats[i][5]
                if self.flightStats[i][6] > self.flightStats[0][6]:
                    self.flightStats[0][6] = self.flightStats[i][6]
                if self.flightStats[i][7] > self.flightStats[0][7]:
                    self.flightStats[0][7] = self.flightStats[i][7]

        self.root.ids.flight_stats_grid.add_widget(MDLabel(text="Flight", bold=True))
        self.root.ids.flight_stats_grid.add_widget(MDLabel(text="Duration", bold=True))
        self.root.ids.flight_stats_grid.add_widget(MDLabel(text="Max Distance", bold=True))
        self.root.ids.flight_stats_grid.add_widget(MDLabel(text="Max Altitude", bold=True))
        self.root.ids.flight_stats_grid.add_widget(MDLabel(text="Max Speed", bold=True))
        for i in range(0, len(self.flightStats)):
            self.root.ids.flight_stats_grid.add_widget(MDLabel(text=(f"Flight #{i}" if i > 0 else "Overall")))
            self.root.ids.flight_stats_grid.add_widget(MDLabel(text=str(self.flightStats[i][3])))
            self.root.ids.flight_stats_grid.add_widget(MDLabel(text=f"{self.fmt_num(self.flightStats[i][0])} {self.dist_unit()}"))
            self.root.ids.flight_stats_grid.add_widget(MDLabel(text=f"{self.fmt_num(self.flightStats[i][1])} {self.dist_unit()}"))
            self.root.ids.flight_stats_grid.add_widget(MDLabel(text=f"{self.fmt_num(self.flightStats[i][2])} {self.speed_unit()}"))


    '''
    Open the selected Flight Data Zip file.
    '''
    def parse_file(self, selectedFile):
        zipFile = Path(selectedFile)
        if (not zipFile.is_file()):
            self.show_error_message(message=f'Not a valid file specified: {selectedFile}')
            return
        droneModel = re.sub(r"[0-9]*-(.*)-Drone.*", r"\1", PurePath(selectedFile).name) # Pull drone model from zip filename.
        droneModel = re.sub(r"[^\w]", r" ", droneModel) # Remove non-alphanumeric characters from the model name.
        lcDM = droneModel.lower()
        if ('p1a' in lcDM):
            self.parse_dreamer_logs(droneModel, selectedFile)
        else:
            if (not 'atom' in lcDM):
                self.show_warning_message(message=f'This drone model may not be supported in this software: {droneModel}')
            self.parse_atom_logs(droneModel, selectedFile)


    '''
    Open a file dialog.
    '''
    def open_file_dialog(self):
        self.stop_flight(True)
        if platform == 'android':
            # Open Android Shared Storage. This opens in a separate thread so we wait here
            # until that dialog has closed. Otherwise the map drawing will be triggered from
            # a thread other than the main Kivy one and it will complain about that.
            # Note that "plyer" also supports Android File Manager but it seems to have some
            # issues, so we're using androidstorage4kivy instead.
            self.chosenFile = None
            self.chooser.choose_content("application/zip")
            self.chooser_open = True
            while (self.chooser_open):
                time.sleep(0.2)
            if self.chosenFile is not None:
                self.parse_file(self.chosenFile)
        else:
            oldwd = os.getcwd() # Remember current workdir. Windows File Explorer is nasty and changes it, causing all sorts of mapview issues.
            myFiles = filechooser.open_file(title="Select a log zip file.", filters=[("Zip files", "*.zip")], mime_type="zip")
            newwd = os.getcwd()
            if oldwd != newwd:
                os.chdir(oldwd) # Change it back!
            if myFiles and len(myFiles) > 0 and os.path.isfile(myFiles[0]):
                self.parse_file(myFiles[0])


    '''
    File Chooser, called when a file has been selected on the Android device.
    '''
    def chooser_callback(self, uri_list):
        try:
            ss = SharedStorage()
            for uri in uri_list:
                self.chosenFile = ss.copy_from_shared(uri) # copy to private storage
                break # Only open the first file from the selection.
        except Exception as e:
            print(f"File Chooser Error: {e}")
        self.chooser_open = False


    '''
    Map Source dropdown functions.
    '''
    def open_mapsource_selection(self, item):
        menu_items = []
        for mapOption in SelectableTileServer:
            menu_items.append({"text": mapOption.value, "on_release": lambda x=mapOption.value: self.mapsource_selection_callback(x)})
        self.mapsource_selection_menu = MDDropdownMenu(caller = item, items = menu_items)
        self.mapsource_selection_menu.open()
    def mapsource_selection_callback(self, text_item):
        self.root.ids.selected_mapsource.text = text_item
        self.mapsource_selection_menu.dismiss()
        Config.set('preferences', 'map_tile_server', text_item)
        Config.write()
        self.select_map_source()
    def select_map_source(self):
        tileSource = self.root.ids.selected_mapsource.text
        mapSource = None
        if (tileSource == SelectableTileServer.GOOGLE_STANDARD.value):
            mapSource = MapSource(url="https://mt0.google.com/vt/lyrs=m&hl=en&x={x}&y={y}&z={z}&s=Ga", cache_key="gmn", min_zoom=0, max_zoom=22, attribution="Google Maps") # Google Maps Normal 
        elif (tileSource == SelectableTileServer.GOOGLE_SATELLITE.value):
            mapSource = MapSource(url="https://mt0.google.com/vt/lyrs=s&hl=en&x={x}&y={y}&z={z}&s=Ga", cache_key="gms", min_zoom=0, max_zoom=22, attribution="Google Maps") # Google Maps Satellite
        elif (tileSource == SelectableTileServer.OPEN_TOPO.value):
            mapSource = MapSource(url="https://tile.opentopomap.org/{z}/{x}/{y}.png", cache_key="otm", min_zoom=0, max_zoom=18, attribution="Open Topo Map") # Open Topo Map
        else:
            mapSource = MapSource(cache_key="osm") # OpenStreetMap (default)
        self.root.ids.map.map_source = mapSource


    '''
    Called when checkbox for Path view is selected (to show or hide drone path on the map).
    '''
    def generate_map_layers(self):
        self.flightPaths = []
        if not self.pathCoords:
            return
        color = self.assetColors[int(self.root.ids.selected_flight_path_color.value)]
        for pathCoord in self.pathCoords:
            flightPath = []
            for pathSegment in pathCoord:
                geojson = {
                    "geojson": {
                        "type": "Feature",
                        "properties": {
                            "stroke": color,
                            "stroke-width": self.pathWidths[int(self.root.ids.selected_flight_path_width.value)]
                        },
                        "geometry": {
                            "type": "LineString",
                            "coordinates": pathSegment
                        }
                    }
                }
                maplayer = GeoJsonMapLayer(**geojson)
                flightPath.append(maplayer)
            self.flightPaths.append(flightPath)


    '''
    Clear out the Map. Remove all markers, flight paths and layers.
    '''
    def clear_map(self):
        self.stop_flight(True)
        if self.flightPaths:
            for flightPath in self.flightPaths:
                for maplayer in flightPath:
                    try:
                        self.root.ids.map.remove_layer(maplayer)
                    except:
                        ... # Do nothing
        if self.layer_home:
            self.root.ids.map.remove_marker(self.homemarker)
            self.root.ids.map.remove_layer(self.layer_home)
            self.layer_home = None
            self.homemarker = None
        if self.layer_ctrl:
            self.root.ids.map.remove_marker(self.ctrlmarker)
            self.root.ids.map.remove_layer(self.layer_ctrl)
            self.layer_ctrl = None
            self.ctrlmarker = None
        if self.layer_drone:
            self.root.ids.map.remove_marker(self.dronemarker)
            self.root.ids.map.remove_layer(self.layer_drone)
            self.layer_drone = None
            self.dronemarker = None


    '''
    Build layers on the Map with markers and flight paths.
    '''
    def init_map_layers(self):
        if not self.flightPaths:
            return
        self.stop_flight(True)
        # Home Marker
        self.layer_home = MarkerMapLayer()
        self.layer_home.opacity = 1 if self.root.ids.selected_home_marker.active else 0
        self.homemarker = MapMarker(source=f"assets/Home-{str(int(self.root.ids.selected_marker_home_color.value)+1)}.png", anchor_y=0.5)
        self.root.ids.map.add_layer(self.layer_home)
        self.root.ids.map.add_marker(self.homemarker, self.layer_home)
        # Controller Marker
        self.layer_ctrl = MarkerMapLayer()
        self.layer_ctrl.opacity = 1 if self.root.ids.selected_ctrl_marker.active else 0
        self.ctrlmarker = MapMarker(source=f"assets/Controller-{str(int(self.root.ids.selected_marker_ctrl_color.value)+1)}.png", anchor_y=0.5)
        self.root.ids.map.add_layer(self.layer_ctrl)
        self.root.ids.map.add_marker(self.ctrlmarker, self.layer_ctrl)
        # Flight Paths
        flightNum = 0 if (self.root.ids.selected_path.text == '--') else int(re.sub(r"[^0-9]", r"", self.root.ids.selected_path.text))
        if (flightNum == 0):
            # Show all flight paths in the log file.
            for flightPath in self.flightPaths:
                for maplayer in flightPath:
                    self.root.ids.map.add_layer(maplayer)
        else:
            # Show selected flight path.
            flightNum = int(re.sub(r"[^0-9]", r"", self.root.ids.selected_path.text))
            flightPath = self.flightPaths[flightNum-1]
            for maplayer in flightPath:
                self.root.ids.map.add_layer(maplayer)
        # Drone Marker. This layer is always visible.
        self.layer_drone = MarkerMapLayer()
        self.dronemarker = MapMarker(source=f"assets/Drone-{str(int(self.root.ids.selected_marker_drone_color.value)+1)}.png", anchor_y=0.5)
        self.root.ids.map.add_layer(self.layer_drone)
        self.root.ids.map.add_marker(self.dronemarker, self.layer_drone)


    '''
    Zooms the map so that the entire flight path will fit.
    '''
    def zoom_to_fit(self):
        flightNum = 0 if (self.root.ids.selected_path.text == '--') else int(re.sub(r"[^0-9]", r"", self.root.ids.selected_path.text))
        # Find appropriate zoom level that shows the entire flight path.
        zoom = self.root.ids.map.map_source.max_zoom
        self.root.ids.map.zoom = zoom
        self.root.ids.map.center_on(self.centerlat, self.centerlon)
        while zoom > self.root.ids.map.map_source.min_zoom:
            bbox = self.root.ids.map.get_bbox()
            if self.flightStats[flightNum][4] >= bbox[0] and self.flightStats[flightNum][5] >= bbox[1] and self.flightStats[flightNum][6] <= bbox[2] and self.flightStats[flightNum][7] <= bbox[3]:
                break
            zoom = zoom - 1
            self.root.ids.map.zoom = zoom


    '''
    Center the map at the last known center point.
    '''
    def center_map(self):
        if self.flightOptions and len(self.flightOptions) > 0:
            self.zoom_to_fit()
        else:
            self.root.ids.map.center_on(self.centerlat, self.centerlon)


    '''
    Zoom in/out when the zoom buttons on the map are selected. Only for desktop view.
    '''
    def map_zoom(self, zoomin):
        if zoomin:
            if self.root.ids.map.zoom < self.root.ids.map.map_source.max_zoom:
                self.root.ids.map.zoom = self.root.ids.map.zoom + 1
        else:
            if self.root.ids.map.zoom > self.root.ids.map.map_source.min_zoom:
                self.root.ids.map.zoom = self.root.ids.map.zoom - 1


    '''
    Update ctrl/home/drone markers on the map as well as other labels with flight information.
    '''
    def set_markers(self, updateSlider=True):
        if not self.currentRowIdx:
            return
        record = self.logdata[self.currentRowIdx]
        self.root.ids.value1_alt.text = f"{record[15]} {self.dist_unit()}"
        self.root.ids.value2_alt.text = f"Alt: {record[15]} {self.dist_unit()}"
        self.root.ids.value1_dist.text = f"{record[13]} {self.dist_unit()}"
        self.root.ids.value2_dist.text = f"Dist: {record[13]} {self.dist_unit()}"
        self.root.ids.value1_hspeed.text = f"{record[19]} {self.speed_unit()}"
        self.root.ids.value2_hspeed.text = f"HS: {record[19]} {self.speed_unit()}"
        self.root.ids.value1_vspeed.text = f"{record[23]} {self.speed_unit()}"
        self.root.ids.value2_vspeed.text = f"VS: {record[23]} {self.speed_unit()}"
        self.root.ids.value2_sats.text = f"Sats: {record[24]}"
        elapsed = record[5]
        elapsed = elapsed - datetime.timedelta(microseconds=elapsed.microseconds) # truncate to milliseconds
        self.root.ids.value1_elapsed.text = str(elapsed)
        self.root.ids.value2_elapsed.text = str(elapsed)
        if updateSlider:
            if self.root.ids.value_duration.text != "":
                durstr = self.root.ids.value_duration.text.split(":")
                durval = datetime.timedelta(hours=int(durstr[0]), minutes=int(durstr[1]), seconds=int(durstr[2]))
                if durval != 0: # Prevent division by zero
                    self.root.ids.flight_progress.value = elapsed / durval * 100
                else:
                    self.root.ids.flight_progress.value = 0
        # Controller Marker.
        try:
            ctrllat = float(record[self.columns.index('ctrllat')])
            ctrllon = float(record[self.columns.index('ctrllon')])
            self.ctrlmarker.lat = ctrllat
            self.ctrlmarker.lon = ctrllon
        except:
            ... # Do nothing
        # Drone Home (RTH) Marker.
        try:
            homelat = float(record[self.columns.index('homelat')])
            homelon = float(record[self.columns.index('homelon')])
            self.homemarker.lat = homelat
            self.homemarker.lon = homelon
        except:
            ... # Do nothing
        # Drone marker.
        try:
            dronelat = float(record[self.columns.index('dronelat')])
            dronelon = float(record[self.columns.index('dronelon')])
            self.dronemarker.lat = dronelat
            self.dronemarker.lon = dronelon
        except:
            ... # Do nothing
        self.root.ids.map.trigger_update(False)


    '''
    Update ctrl/home/drone markers on the map with the next set of coordinates in the table list.
    '''
    def set_frame(self):
        refreshRate = float(re.sub("[^0-9\.]", "", self.root.ids.selected_refresh_rate.text))
        totalTimeElapsed = self.logdata[self.currentRowIdx][self.columns.index('time')]
        prevTs = None
        timeElapsed = None
        while (not self.stopRequested) and (self.currentRowIdx < self.currentEndIdx):
            self.set_markers()
            time.sleep(refreshRate)
            now = datetime.datetime.now()
            timeElapsed = now - prevTs if prevTs else datetime.timedelta()
            if self.playback_speed > 1:
                timeElapsed = timeElapsed * self.playback_speed
            totalTimeElapsed = totalTimeElapsed + timeElapsed
            prevTs = now
            while self.currentRowIdx <= self.currentEndIdx and self.logdata[self.currentRowIdx][self.columns.index('time')] < totalTimeElapsed:
                self.currentRowIdx = self.currentRowIdx + 1
        self.isPlaying = False
        self.stopRequested = False


    def select_flight_progress(self, slider, coords):
        if (slider.is_updating): # Check if slider value is being updated from outside the slider (i.e. playback)
            return
        if len(self.logdata) == 0:
            return # Do nothing
        if (self.root.ids.selected_path.text == '--'):
            return # Do nothing
        # Determine approximate selected duration based on slider position
        durstr = self.root.ids.value_duration.text.split(":")
        durval = datetime.timedelta(hours=int(durstr[0]), minutes=int(durstr[1]), seconds=int(durstr[2]))
        newdur = durval / 100 * slider.value
        minDiff = None
        nearestIdx = -1
        for idx in range(self.currentStartIdx, self.currentEndIdx+1):
            dur = self.logdata[idx][self.columns.index('time')]
            diff = abs(dur-newdur)
            if not minDiff:
                minDiff = diff
                nearestIdx = idx
            elif diff < minDiff:
                minDiff = diff
                nearestIdx = idx
            elif diff > minDiff:
                break
        if nearestIdx >= 0:
            self.currentRowIdx = nearestIdx
            self.set_markers(False)


    def change_playback_speed(self):
        if self.playback_speed == 1:
            self.playback_speed = 2
        elif self.playback_speed == 2:
            self.playback_speed = 4
        elif self.playback_speed == 4:
            self.playback_speed = 8
        else:
            self.playback_speed = 1
        self.root.ids.speed_indicator.icon = f"numeric-{self.playback_speed}-box"


    '''
    Jump to beginning of current flight, or the end of the previous one.
    '''
    def jump_prev_flight(self):
        if len(self.logdata) == 0:
            self.show_warning_message(message="No data to play back.")
            return
        if (self.root.ids.selected_path.text == '--'):
            self.show_info_message(message="No flight selected.")
            return
        self.stop_flight(True)
        if self.currentRowIdx > self.currentStartIdx:
            self.currentRowIdx = self.currentStartIdx
            self.root.ids.flight_progress.is_updating = True
            self.set_markers(False)
            self.root.ids.flight_progress.value = 0
            self.root.ids.flight_progress.is_updating = False
            return
        flightNum = int(re.sub(r"[^0-9]", r"", self.root.ids.selected_path.text))
        if flightNum > 1:
            self.root.ids.selected_path.text = str(flightNum - 1)
            self.root.ids.flight_progress.is_updating = True
            self.select_flight(True)
            self.set_markers(False)
            self.root.ids.flight_progress.value = 100
            self.root.ids.flight_progress.is_updating = False
        else:
            self.show_info_message(message="No previous flight.")


    '''
    Jump to end of current flight, or the beginning of the next one.
    '''
    def jump_next_flight(self):
        if len(self.logdata) == 0:
            self.show_warning_message(message="No data to play back.")
            return
        if (self.root.ids.selected_path.text == '--'):
            self.show_info_message(message="No flight selected.")
            return
        self.stop_flight(True)
        if self.currentRowIdx < self.currentEndIdx:
            self.currentRowIdx = self.currentEndIdx
            self.root.ids.flight_progress.is_updating = True
            self.set_markers(False)
            self.root.ids.flight_progress.value = 100
            self.root.ids.flight_progress.is_updating = False
            return
        flightNum = int(re.sub(r"[^0-9]", r"", self.root.ids.selected_path.text))
        if flightNum < len(self.flightOptions):
            self.root.ids.selected_path.text = str(flightNum + 1)
            self.root.ids.flight_progress.is_updating = True
            self.select_flight()
            self.set_markers(False)
            self.root.ids.flight_progress.value = 0
            self.root.ids.flight_progress.is_updating = False
        else:
            self.show_info_message(message="No next flight.")


    '''
    Start or resume playback of the selected flight. If flight is finished, restart from beginning.
    '''
    def play_flight(self):
        self.stopRequested = False
        if (self.isPlaying):
            self.stop_flight(True)
            return
        if len(self.logdata) == 0:
            self.show_warning_message(message="No data to play back.")
            return
        if (self.root.ids.selected_path.text == '--'):
            self.show_info_message(message="Select a flight to play back.")
            return
        if self.currentRowIdx == self.currentEndIdx:
            self.currentRowIdx = self.currentStartIdx
        self.root.ids.flight_progress.is_updating = True
        self.isPlaying = True
        self.root.ids.playbutton.icon = "pause"
        threading.Thread(target=self.set_frame, args=()).start()


    '''
    Stop flight playback.
    '''
    def stop_flight(self, wait=False):
        if not self.isPlaying:
            return
        self.stopRequested = True
        if wait:
            while (self.isPlaying):
                time.sleep(0.25)
        self.root.ids.flight_progress.is_updating = False
        self.root.ids.playbutton.icon = "play"


    '''
    Change Flight Path Line Width (Preferences).
    '''
    def flight_path_width_selection(self, slider, coords):
        Config.set('preferences', 'flight_path_width', int(slider.value))
        Config.write()
        self.clear_map()
        self.generate_map_layers()
        self.init_map_layers()
        self.set_markers()


    '''
    Flight Path Colours functions.
    '''
    def flight_path_color_selection(self, slider, coords):
        colorIdx = int(slider.value)
        slider.track_active_color = self.assetColors[colorIdx]
        slider.track_inactive_color = self.assetColors[colorIdx]
        Config.set('preferences', 'flight_path_color', colorIdx)
        Config.write()
        self.clear_map()
        self.generate_map_layers()
        self.init_map_layers()
        self.set_markers()


    '''
    Drone Marker Colour functions.
    '''
    def marker_drone_color_selection(self, slider, coords):
        colorIdx = int(slider.value)
        slider.track_active_color = self.assetColors[colorIdx]
        slider.track_inactive_color = self.assetColors[colorIdx]
        Config.set('preferences', 'marker_drone_color', colorIdx)
        Config.write()
        self.stop_flight(True)
        if self.dronemarker:
            self.dronemarker.source=f"assets/Drone-{str(int(self.root.ids.selected_marker_drone_color.value)+1)}.png"
            self.set_markers()


    '''
    Controller Marker Colour functions.
    '''
    def marker_ctrl_color_selection(self, slider, coords):
        colorIdx = int(slider.value)
        slider.track_active_color = self.assetColors[colorIdx]
        slider.track_inactive_color = self.assetColors[colorIdx]
        Config.set('preferences', 'marker_ctrl_color', colorIdx)
        Config.write()
        self.stop_flight(True)
        if self.ctrlmarker:
            self.ctrlmarker.source=f"assets/Controller-{str(int(self.root.ids.selected_marker_ctrl_color.value)+1)}.png"
            self.set_markers()


    '''
    Home Marker Colour functions.
    '''
    def marker_home_color_selection(self, slider, coords):
        colorIdx = int(slider.value)
        slider.track_active_color = self.assetColors[colorIdx]
        slider.track_inactive_color = self.assetColors[colorIdx]
        Config.set('preferences', 'marker_home_color', colorIdx)
        Config.write()
        self.stop_flight(True)
        if self.homemarker:
            self.homemarker.source=f"assets/Home-{str(int(self.root.ids.selected_marker_home_color.value)+1)}.png"
            self.set_markers()


    '''
    Flight Path dropdown functions.
    '''
    def open_flight_selection(self, item):
        if self.flightOptions is None:
            return
        menu_items = []
        menu_items.append({"text": "--", "on_release": lambda x="--": self.flight_selection_callback(x)})
        for flightOption in self.flightOptions:
            menu_items.append({"text": flightOption, "on_release": lambda x=flightOption: self.flight_selection_callback(x)})
        self.flight_selection_menu = MDDropdownMenu(caller = item, items = menu_items)
        self.flight_selection_menu.open()
    def flight_selection_callback(self, text_item):
        self.root.ids.selected_path.text = text_item
        self.flight_selection_menu.dismiss()
        self.select_flight()
    def select_flight(self, skip_to_end=False):
        self.clear_map()
        self.init_map_layers()
        flightNum = 0 if (self.root.ids.selected_path.text == '--') else int(re.sub(r"[^0-9]", r"", self.root.ids.selected_path.text))
        if (flightNum != 0):
            self.currentStartIdx = self.flightStarts[self.root.ids.selected_path.text]
            self.currentEndIdx = self.flightEnds[self.root.ids.selected_path.text]
            if skip_to_end:
                self.currentRowIdx = self.currentEndIdx
            else:
                self.currentRowIdx = self.currentStartIdx
            self.set_markers()
        if self.flightStats and len(self.flightStats) > 0:
            self.centerlat = (self.flightStats[flightNum][4] + self.flightStats[flightNum][6]) / 2
            self.centerlon = (self.flightStats[flightNum][5] + self.flightStats[flightNum][7]) / 2
            self.zoom_to_fit()
            # Show flight stats.
            self.root.ids.value_maxdist.text = f"{self.fmt_num(self.flightStats[flightNum][0])} {self.dist_unit()}"
            self.root.ids.value_maxalt.text = f"{self.fmt_num(self.flightStats[flightNum][1])} {self.dist_unit()}"
            self.root.ids.value_maxspeed.text = f"{self.fmt_num(self.flightStats[flightNum][2])} {self.speed_unit()}"
            self.root.ids.value_duration.text = str(self.flightStats[flightNum][3])


    '''
    Change Unit of Measure (Preferences).
    '''
    def uom_selection(self, item):
        menu_items = []
        for pathWidth in ['metric', 'imperial']:
            menu_items.append({"text": pathWidth, "on_release": lambda x=pathWidth: self.uom_selection_callback(x)})
        self.uom_selection_menu = MDDropdownMenu(caller = item, items = menu_items)
        self.uom_selection_menu.open()
    def uom_selection_callback(self, text_item):
        self.root.ids.selected_uom.text = text_item
        self.uom_selection_menu.dismiss()
        Config.set('preferences', 'unit_of_measure', text_item)
        Config.write()
        self.stop_flight(True)
        self.show_info_message(message="Re-open the log file for the changes to take effect.")


    '''
    Change Display of Home Marker (Preferences).
    '''
    def refresh_rate_selection(self, item):
        menu_items = []
        for refreshRate in ['0.50s', '1.00s', '1.50s', '2.00s']:
            menu_items.append({"text": refreshRate, "on_release": lambda x=refreshRate: self.refresh_rate_selection_callback(x)})
        self.refresh_rate_selection_menu = MDDropdownMenu(caller = item, items = menu_items)
        self.refresh_rate_selection_menu.open()
    def refresh_rate_selection_callback(self, text_item):
        self.root.ids.selected_refresh_rate.text = text_item
        self.refresh_rate_selection_menu.dismiss()
        Config.set('preferences', 'refresh_rate', text_item)
        Config.write()
        self.stop_flight(True)


    '''
    Change Display of Home Marker (Preferences).
    '''
    def home_marker_selection(self, item):
        Config.set('preferences', 'show_marker_home', item.active)
        Config.write()
        self.stop_flight(True)
        if self.layer_home:
            self.layer_home.opacity = 1 if self.root.ids.selected_home_marker.active else 0


    '''
    Change Display of Controller Marker (Preferences).
    '''
    def ctrl_marker_selection(self, item):
        Config.set('preferences', 'show_marker_ctrl', item.active)
        Config.write()
        self.stop_flight(True)
        if self.layer_ctrl:
            self.layer_ctrl.opacity = 1 if self.root.ids.selected_ctrl_marker.active else 0


    '''
    Enabled or disable rounding of values (Preferences).
    '''
    def rounding_selection(self, item):
        Config.set('preferences', 'rounded_readings', item.active)
        Config.write()
        self.stop_flight(True)
        self.show_info_message(message="Re-open the log file for the changes to take effect.")


    '''
    Return specified distance in the proper Unit (metric vs imperial).
    '''
    def dist_val(self, num):
        return num * 3.28084 if self.root.ids.selected_uom.text == 'imperial' else num


    '''
    Return selected distance unit of measure.
    '''
    def dist_unit(self):
        return "ft" if self.root.ids.selected_uom.text == 'imperial' else "m"


    '''
    Format number based on selected rounding option.
    '''
    def fmt_num(self, num):
        if (num is None):
            return ''
        return locale.format_string("%.0f", num, True) if self.root.ids.selected_rounding.active else locale.format_string("%.2f", num, True)


    '''
    Return specified speed in the proper Unit (metric vs imperial).
    '''
    def speed_val(self, num):
        return num * 2.236936 if self.root.ids.selected_uom.text == 'imperial' else num * 3.6


    '''
    Return selected speed unit of measure.
    '''
    def speed_unit(self):
        return "mph" if self.root.ids.selected_uom.text == 'imperial' else "kph"


    '''
    Reset the application as it were before opening a file.
    '''
    def reset(self):
        self.centerlat = 51.50722
        self.centerlon = -0.1275
        self.playback_speed = 1
        if self.root:
            self.root.ids.selected_path.text = '--'
            self.zoom = self.defaultMapZoom
            self.clear_map()
            self.root.ids.value_maxdist.text = ""
            self.root.ids.value_maxalt.text = ""
            self.root.ids.value_maxspeed.text = ""
            self.root.ids.value_duration.text = ""
            self.root.ids.value1_alt.text = ""
            self.root.ids.value2_alt.text = ""
            self.root.ids.value1_dist.text = ""
            self.root.ids.value2_dist.text = ""
            self.root.ids.value1_hspeed.text = ""
            self.root.ids.value2_hspeed.text = ""
            self.root.ids.value1_vspeed.text = ""
            self.root.ids.value2_vspeed.text = ""
            self.root.ids.value2_sats.text = ""
            self.root.ids.value1_elapsed.text = ""
            self.root.ids.value2_elapsed.text = ""
            self.root.ids.flight_progress.value = 0
            self.root.ids.flight_stats_grid.clear_widgets()
            self.root.ids.speed_indicator.icon = f"numeric-{self.playback_speed}-box"
        self.flightOptions = []
        self.title = self.appTitle
        self.logdata = []
        self.flightPaths = None
        self.pathCoords = None
        self.flightStarts = None
        self.flightEnds = None
        self.zipFilename = None
        self.flightStats = None
        self.playStartTs = None
        self.currentRowIdx = None
        if self.root:
            self.center_map()


    '''
    Show info/warning/error messages.
    '''
    def show_info_message(self, message: str):
        MDSnackbar(MDSnackbarText(text=message), y=dp(24), pos_hint={"center_x": 0.5}, size_hint_x=0.8).open()
    def show_warning_message(self, message: str):
        MDSnackbar(MDSnackbarText(text=message), y=dp(24), pos_hint={"center_x": 0.5}, size_hint_x=0.8).open()
    def show_error_message(self, message: str):
        MDSnackbar(MDSnackbarText(text=message), y=dp(24), pos_hint={"center_x": 0.5}, size_hint_x=0.8).open()


    '''
    Capture keyboard input.
    '''
    def events(self, instance, keyboard, keycode, text, modifiers):
        '''Called when buttons are pressed on the mobile device.'''
        if keyboard in (1001, 27):
            self.stop()
        return True


    '''
    Constructor
    '''
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        locale.setlocale(locale.LC_ALL, '')
        configDir = user_config_dir("FlightLogViewer", "FlightLogViewer")
        if not os.path.exists(configDir):
            Path(configDir).mkdir(parents=True, exist_ok=True)
        self.configFile = os.path.join(configDir, self.configFilename)
        if platform == 'android':
            request_permissions([Permission.INTERNET, Permission.WRITE_EXTERNAL_STORAGE, Permission.READ_EXTERNAL_STORAGE])
            self.chosenFile = None
            self.chooser_open = False # To track Android File Manager (Chooser)
            self.chooser = Chooser(self.chooser_callback)
        Config.read(self.configFile)
        Config.set('kivy', 'window_icon', 'assets/app-icon256.png')
        Config.setdefaults('preferences', {
            'unit_of_measure': "metric",
            'rounded_readings': True,
            'flight_path_width': 0,
            'flight_path_color': 0,
            'marker_drone_color': 0,
            'marker_ctrl_color': 0,
            'marker_home_color': 0,
            'refresh_rate': "1.00s",
            'show_flight_path': True,
            'show_marker_home': True,
            'show_marker_ctrl': False,
            'map_tile_server': SelectableTileServer.OPENSTREETMAP.value
        })
        Window.bind(on_keyboard=self.events)
        self.flightPaths = None
        self.pathCoords = None
        self.flightOptions = None
        self.isPlaying = False
        self.currentRowIdx = None
        self.layer_ctrl = None
        self.ctrlmarker = None
        self.layer_home = None
        self.homemarker = None
        self.layer_drone = None
        self.dronemarker = None
        self.flightStats = None
        self.stopRequested = False
        self.playback_speed = 1


    def build(self):
        self.icon = 'assets/app-icon256.png'
        self.root.ids.selected_uom.text = Config.get('preferences', 'unit_of_measure')
        self.root.ids.selected_home_marker.active = Config.getboolean('preferences', 'show_marker_home')
        self.root.ids.selected_ctrl_marker.active = Config.getboolean('preferences', 'show_marker_ctrl')
        self.root.ids.selected_flight_path_width.value = Config.get('preferences', 'flight_path_width')
        self.root.ids.selected_flight_path_color.value = Config.getint('preferences', 'flight_path_color')
        self.root.ids.selected_marker_drone_color.value = Config.getint('preferences', 'marker_drone_color')
        self.root.ids.selected_marker_ctrl_color.value = Config.getint('preferences', 'marker_ctrl_color')
        self.root.ids.selected_marker_home_color.value = Config.getint('preferences', 'marker_home_color')
        self.root.ids.selected_rounding.active = Config.getboolean('preferences', 'rounded_readings')
        self.root.ids.selected_mapsource.text = Config.get('preferences', 'map_tile_server')
        self.root.ids.selected_refresh_rate.text = Config.get('preferences', 'refresh_rate')


    def on_start(self):
        self.root.ids.selected_path.text = '--'
        self.reset()
        return super().on_start()


    def on_pause(self):
        self.stop_flight(True)
        return True


    '''
    Called when the app is exited.
    '''
    def on_stop(self):
        self.stop_flight(True)
        return super().on_stop()


if __name__ == "__main__":
    MainApp().run()