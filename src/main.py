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
import configparser
import locale
from enum import Enum
from decimal import Decimal

from multiprocessing.connection import wait
from kivy.core.window import Window
#Window.fullscreen = False
#Window.maximize()

from kivy.utils import platform
from kivy.config import Config
from kivymd.app import MDApp
from kivymd.uix.screen import MDScreen
from kivymd.uix.menu import MDDropdownMenu
from kivymd.uix.filemanager import MDFileManager
from kivymd.uix.snackbar import MDSnackbar, MDSnackbarText
from kivymd.uix.label import MDLabel
from kivy.metrics import dp
from kivy_garden.mapview import MapSource, MapMarker
from kivy_garden.mapview.geojson import GeoJsonMapLayer
from kivy_garden.mapview.utils import haversine

if platform == 'android':
    from android.permissions import request_permissions, Permission
    from androidstorage4kivy import SharedStorage, Chooser

#from platformdirs import user_data_dir
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
    print(f"MDScreen:{MDScreen}")


class MainApp(MDApp):

    '''
    Global variables and constants.
    '''
    appVersion = "v2.0.0"
    appName = "Flight Log Viewer"
    appTitle = f"{appName} - {appVersion}"
    defaultMapZoom = 3
    pathColors = [
        ["#417dd6","#ab27a9","#e54f14","#ffa900","#00a31f"],
        ["#c6c6c6","#cfcfcf","#e0e0e0","#4c4c4c","#2d2d2d"],
        ["#ffed49","#ffcb00","#ffa800","#ff6e2c","#fa5b46"],
        ["#ff0000","#00ff00","#0000ff","#ffff00","#000000","#ffffff"],
        ["#00ff00","#0000ff","#ffff00","#000000","#ffffff","#ff0000"],
        ["#0000ff","#ffff00","#000000","#ffffff","#ff0000","#00ff00"],
        ["#ffff00","#000000","#ffffff","#ff0000","#00ff00","#0000ff"],
        ["#000000","#ffffff","#ff0000","#00ff00","#0000ff","#ffff00"],
        ["#ffffff","#ff0000","#00ff00","#0000ff","#ffff00","#000000"]
    ]
    displayMode = "ATOM"
    columns = ('recnum', 'recid', 'flight','timestamp','tod','time','flightstatus','distance1','dist1lat','dist1lon','distance2','dist2lat','dist2lon','distance3','altitude1','altitude2','speed1','speed1lat','speed1lon','speed2','speed2lat','speed2lon','speed1vert','speed2vert','satellites','ctrllat','ctrllon','homelat','homelon','dronelat','dronelon','rssi','channel','flightctrlconnected','remoteconnected','gps','inuse','motor1status','motor2status','motor3status','motor4status')
    showColsBasicDreamer = ('flight','tod','time','altitude1','distance1','satellites','homelat','homelon','dronelat','dronelon')
    configFilename = 'extractFlightData.ini'


    '''
    Parse Atom based logs.
    '''
    def parse_atom_logs(self, droneModel, selectedFile):
        print("parse_atom_logs begin")
        setctrl = True

        binLog = os.path.join(tempfile.gettempdir(), "flightdata")
        shutil.rmtree(binLog, ignore_errors=True) # Delete old temp files if they were missed before.

        with ZipFile(selectedFile, 'r') as unzip:
            unzip.extractall(path=binLog)

        #self.stop()
        self.reset()
        self.displayMode = "ATOM"
        #self.setTableView(None)
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
                    speed1lat = self.dist_val(struct.unpack('f', fcRecord[247+offset2:251+offset2])[0])
                    speed1lon = self.dist_val(struct.unpack('f', fcRecord[251+offset2:255+offset2])[0])
                    speed2lat = self.dist_val(struct.unpack('f', fcRecord[327+offset2:331+offset2])[0])
                    speed2lon = self.dist_val(struct.unpack('f', fcRecord[331+offset2:335+offset2])[0])
                    speed1 = round(math.sqrt(math.pow(speed1lat, 2) + math.pow(speed1lon, 2)), 2) # Pythagoras to calculate real speed.
                    speed2 = round(math.sqrt(math.pow(speed2lat, 2) + math.pow(speed2lon, 2)), 2) # Pythagoras to calculate real speed.
                    if (speed2 > maxSpeed):
                        maxSpeed = speed2
                    speed1vert = self.dist_val(-struct.unpack('f', fcRecord[255+offset2:259+offset2])[0])
                    speed2vert = self.dist_val(-struct.unpack('f', fcRecord[347+offset2:351+offset2])[0])

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
                                #print(f"{pathCoord}")
                                pathCoord = []
                                isNewPath = True
                        if (isFlying): # Only trace path when the drone's motors are spinning faster than idle speeds.
                            pathNum = len(self.pathCoords)+1
                            lastCoord = pathCoord[len(pathCoord)-1] if len(pathCoord) > 0 else [0, 0]
                            distMoved = haversine(lastCoord[0], lastCoord[1], dronelon, dronelat)
                            if distMoved >= 0.0015:
                                pathCoord.append([dronelon, dronelat])
                            #print(f"{sanDist},{recordCount},{dronelon},{dronelat}")
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

                    flightDesc = f'Flight {pathNum}'
                    if (isNewPath and len(pathCoord) > 0):
                        self.flightOptions.append(flightDesc)
                        self.flightStarts[flightDesc] = tableLen
                        isNewPath = False
                    if pathNum > 0:
                        self.flightEnds[flightDesc] = tableLen
                    self.logdata.append([recordCount, recordId, pathNum, readingTs.isoformat(sep=' '), readingTs.strftime('%X'), elapsedTs, droneMotorStatus.value, f"{self.fmt_num(dist1)}", f"{self.fmt_num(dist1lat)}", f"{self.fmt_num(dist1lon)}", f"{self.fmt_num(dist2)}", f"{self.fmt_num(dist2lat)}", f"{self.fmt_num(dist2lon)}", f"{self.fmt_num(dist3)}", f"{self.fmt_num(alt1)}", f"{self.fmt_num(alt2)}", f"{self.fmt_num(speed1)}", f"{self.fmt_num(speed1lat)}", f"{self.fmt_num(speed1lon)}", f"{self.fmt_num(speed2)}", f"{self.fmt_num(speed2lat)}", f"{self.fmt_num(speed2lon)}", f"{self.fmt_num(speed1vert)}", f"{self.fmt_num(speed2vert)}", str(satellites), str(ctrllat), str(ctrllon), str(homelat), str(homelon), str(dronelat), str(dronelon), fpvRssi, fpvChannel, fpvFlightCtrlConnected, fpvRemoteConnected, gpsStatus, inUse, motor1Stat, motor2Stat, motor3Stat, motor4Stat])
                    tableLen = tableLen + 1
                    if (setctrl and hasValidCoords and alt2 > 0): # Record home location from the moment the drone ascends.
                        setctrl = False

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
            self.root.ids.flight_stats_grid.add_widget(MDLabel(text=(f"Flight {i}" if i > 0 else "Overall")))
            self.root.ids.flight_stats_grid.add_widget(MDLabel(text=str(self.flightStats[i][3])))
            self.root.ids.flight_stats_grid.add_widget(MDLabel(text=f"{self.fmt_num(self.flightStats[i][0])} {self.dist_unit()}"))
            self.root.ids.flight_stats_grid.add_widget(MDLabel(text=f"{self.fmt_num(self.flightStats[i][1])} {self.dist_unit()}"))
            self.root.ids.flight_stats_grid.add_widget(MDLabel(text=f"{self.fmt_num(self.flightStats[i][2])} {self.speed_unit()}"))
        print("parse_atom_logs end")


    '''
    Map Source dropdown functions.
    '''
    def open_mapsource_selection(self, item):
        menu_items = []
        for mapOption in SelectableTileServer:
            menu_items.append({"text": mapOption.value, "on_release": lambda x=mapOption.value: self.mapsource_selection_callback(x)})
        MDDropdownMenu(caller = item, items = menu_items).open()
    def mapsource_selection_callback(self, text_item):
        self.root.ids.selected_mapsource.text = text_item
        self.config.set('preferences', 'map_tile_server', text_item)
        self.config.write()
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
    Change Flight Path Line Width (Preferences).
    '''
    def flight_path_width_selection(self, item):
        menu_items = []
        for pathWidth in ['0.5', '1.0', '1.5', '2.0', '2.5', '3.0']:
            menu_items.append({"text": pathWidth, "on_release": lambda x=pathWidth: self.flight_path_width_selection_callback(x)})
        MDDropdownMenu(caller = item, items = menu_items).open()
    def flight_path_width_selection_callback(self, text_item):
        self.root.ids.selected_flight_path_width.text = text_item
        self.config.set('preferences', 'flight_path_width', text_item)
        self.config.write()
        self.stop_flight(True)
        self.remove_layers()
        self.generate_map_layers()
        self.select_flight()


    '''
    Called when checkbox for Path view is selected (to show or hide drone path on the map).
    '''
    def generate_map_layers(self):
        self.flightPaths = []
        if not self.pathCoords:
            return
        colors = self.pathColors[0]
        idx = 0
        for pathCoord in self.pathCoords:
            geojson = {
                "geojson": {
                    "type": "Feature",
                    "properties": {
                        "stroke": colors[idx%len(colors)],
                        "stroke-width": self.root.ids.selected_flight_path_width.text
                    },
                    "geometry": {
                        "type": "LineString",
                        "coordinates": pathCoord
                    }
                }
            }
            maplayer = GeoJsonMapLayer(**geojson)
            self.flightPaths.append(maplayer)
            idx = idx + 1


    '''
    Clear all the flight paths from the map.
    '''
    def remove_layers(self):
        if not self.flightPaths:
            return
        for maplayer in self.flightPaths:
            try:
                self.root.ids.map.remove_layer(maplayer)
            except:
                ... # Do nothing


    '''
    Remove the map markers.
    '''
    def remove_markers(self):
        if self.ctrlmarker:
            try:
                self.root.ids.map.remove_marker(self.ctrlmarker)
            except:
                ... # Do nothing
        if self.homemarker:
            try:
                self.root.ids.map.remove_marker(self.homemarker)
            except:
                ... # Do nothing
        if self.dronemarker:
            try:
                self.root.ids.map.remove_marker(self.dronemarker)
            except:
                ... # Do nothing


    '''
    Add the map markers.
    '''
    def add_markers(self):
        if self.root.ids.selected_ctrl_marker.active:
            self.root.ids.map.add_marker(self.ctrlmarker)
        if self.root.ids.selected_home_marker.active:
            self.root.ids.map.add_marker(self.homemarker)
        self.root.ids.map.add_marker(self.dronemarker)


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
    Flight Path dropdown functions.
    '''
    def open_flight_selection(self, item):
        if self.flightOptions is None:
            return
        menu_items = []
        menu_items.append({"text": "--", "on_release": lambda x="--": self.flight_selection_callback(x)})
        for flightOption in self.flightOptions:
            menu_items.append({"text": flightOption, "on_release": lambda x=flightOption: self.flight_selection_callback(x)})
        MDDropdownMenu(caller = item, items = menu_items).open()
    def flight_selection_callback(self, text_item):
        self.root.ids.selected_path.text = text_item
        self.select_flight()
    def select_flight(self):
        self.stop_flight(True)
        self.remove_markers()
        self.remove_layers()
        flightNum = 0 if (self.root.ids.selected_path.text == '--') else int(re.sub(r"[^0-9]", r"", self.root.ids.selected_path.text))
        if (flightNum == 0):
            # TODO - map does not always refresh right away...
            for maplayer in self.flightPaths:
                self.root.ids.map.add_layer(maplayer)
        else:
            flightNum = int(re.sub(r"[^0-9]", r"", self.root.ids.selected_path.text))
            maplayer = self.flightPaths[flightNum-1]
            self.root.ids.map.add_layer(maplayer)
            self.currentStartIdx = self.flightStarts[self.root.ids.selected_path.text]
            self.currentEndIdx = self.flightEnds[self.root.ids.selected_path.text]
            self.currentRowIdx = self.currentStartIdx
            self.add_markers()
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
    Center the map at the last known center point.
    '''
    def center_map(self):
        if self.flightOptions and len(self.flightOptions) > 0:
            self.zoom_to_fit()
        else:
            self.root.ids.map.center_on(self.centerlat, self.centerlon)


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
    Change Unit of Measure (Preferences).
    '''
    def uom_selection(self, item):
        menu_items = []
        for pathWidth in ['metric', 'imperial']:
            menu_items.append({"text": pathWidth, "on_release": lambda x=pathWidth: self.uom_selection_callback(x)})
        MDDropdownMenu(caller = item, items = menu_items).open()
    def uom_selection_callback(self, text_item):
        self.root.ids.selected_uom.text = text_item
        self.config.set('preferences', 'unit_of_measure', text_item)
        self.config.write()
        self.stop_flight(True)
        self.show_info_message(message="Re-open the log file for the changes to take effect.")


    '''
    Change Display of Home Marker (Preferences).
    '''
    def refresh_rate_selection(self, item):
        menu_items = []
        for refreshRate in ['0.25s', '0.50s', '0.75s', '1.00s', '1.25s', '1.50s']:
            menu_items.append({"text": refreshRate, "on_release": lambda x=refreshRate: self.refresh_rate_selection_callback(x)})
        MDDropdownMenu(caller = item, items = menu_items).open()
    def refresh_rate_selection_callback(self, text_item):
        self.root.ids.selected_refresh_rate.text = text_item
        self.config.set('preferences', 'refresh_rate', text_item)
        self.config.write()
        self.stop_flight(True)


    '''
    Change Display of Home Marker (Preferences).
    '''
    def home_marker_selection(self, item):
        self.config.set('preferences', 'show_marker_home', item.active)
        self.config.write()
        self.stop_flight(True)
        self.remove_markers()
        self.add_markers()


    '''
    Change Display of Controller Marker (Preferences).
    '''
    def ctrl_marker_selection(self, item):
        self.config.set('preferences', 'show_marker_ctrl', item.active)
        self.config.write()
        self.stop_flight(True)
        self.remove_markers()
        self.add_markers()


    '''
    Enabled or disable rounding of values (Preferences).
    '''
    def rounding_selection(self, item):
        self.config.set('preferences', 'rounded_readings', item.active)
        self.config.write()
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
        #return f"{num:.0f}" if self.root.ids.selected_rounding.active else f"{num:.2f}"
        return locale.format_string("%.0f", num, True) if self.root.ids.selected_rounding.active else locale.format_string("%.2f", num, True)


    '''
    Return specified speed in the proper Unit (metric vs imperial).
    '''
    def speed_val(self, num):
        return num * 2.236936 if self.root.ids.selected_uom.text == 'imperial' else num


    '''
    Return selected speed unit of measure.
    '''
    def speed_unit(self):
        return "mph" if self.root.ids.selected_uom.text == 'imperial' else "m/s"


    '''
    Reset the application as it were before opening a file.
    '''
    def reset(self):
        self.centerlat = 51.50722
        self.centerlon = -0.1275
        if self.root:
            self.root.ids.selected_path.text = '--'
            self.zoom = self.defaultMapZoom
            self.remove_markers()
            self.remove_layers()
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
            self.root.ids.flight_stats_grid.clear_widgets()
        self.flightOptions = []
        #self.root.ids.selected_path.text = '--'
        #self.title(f"Flight Data Viewer - {self.version}")
        self.title = self.appTitle
        self.logdata = []
        self.flightPaths = None
        self.pathCoords = None
        self.flightStarts = None
        self.flightEnds = None
        self.zipFilename = None
        self.flightStats = None
        self.playStartTs = None
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
    def set_markers(self):
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
        if self.playStartTs:
            elapsed = datetime.datetime.now() - self.playStartTs
            elapsed = elapsed - datetime.timedelta(microseconds=elapsed.microseconds) # truncate to milliseconds
            self.root.ids.value1_elapsed.text = str(elapsed)
            self.root.ids.value2_elapsed.text = str(elapsed)
        # Controller Marker.
        if self.root.ids.selected_ctrl_marker.active:
            try:
                ctrllat = float(record[self.columns.index('ctrllat')])
                ctrllon = float(record[self.columns.index('ctrllon')])
                self.ctrlmarker.lat = ctrllat
                self.ctrlmarker.lon = ctrllon
            except:
                ... # Do nothing
        # Drone Home (RTH) Marker.
        if self.root.ids.selected_home_marker.active:
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
            self.root.ids.map.trigger_update(False)
        except:
            ... # Do nothing


    '''
    Update ctrl/home/drone markers on the map with the next set of coordinates in the table list.
    '''
    def set_frame(self):        
        refreshRate = float(re.sub("[^0-9\.]", "", self.root.ids.selected_refresh_rate.text))
        while self.isPlaying and self.currentRowIdx < self.currentEndIdx:
            self.set_markers()
            time.sleep(refreshRate)
            runningTs = datetime.datetime.now() - self.playStartTs
            while self.currentRowIdx <= self.currentEndIdx and self.logdata[self.currentRowIdx][self.columns.index('time')] < runningTs:
                self.currentRowIdx = self.currentRowIdx + 1
        self.isPlaying = False


    '''
    Start or resume playback of the selected flight. If flight is finished, restart from beginning.
    '''
    def play_flight(self):
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
        self.playStartTs = datetime.datetime.now() - self.logdata[self.currentRowIdx][self.columns.index('time')]
        self.isPlaying = True
        self.root.ids.playbutton.icon = "pause"
        threading.Thread(target=self.set_frame, args=()).start()


    '''
    Stop flight playback.
    '''
    def stop_flight(self, wait):
        self.isPlaying = False
        if wait:
            while (self.isPlaying):
                time.sleep(0.5)
        self.root.ids.playbutton.icon = "play"


    '''
    Open a file dialog.
    '''
    def open_file_dialog(self):
        if platform == 'android':
            # Open Android Shared Storage. This opens in a separate thread so we wait here
            # until that dialog has closed. Otherwise the map drawing will be triggered from
            # a thread other than the main Kivy one and it will complain about that.
            self.chosenFile = None
            self.chooser.choose_content("application/zip")
            self.chooser_open = True
            while (self.chooser_open):
                time.sleep(0.2)
            if self.chosenFile is not None:
                self.parse_file(self.chosenFile)
        else:
            # Open standard file manager on non-android platform
            myPath = os.path.expanduser("~")
            print(f"file_manager_open path1 {myPath}")
            self.file_manager.show(myPath)  # output manager to the screen
            #self.file_manager.show(os.path.curdir)  # output manager to the screen
            self.manager_open = True


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
            print(f"Error: {e}")
        self.chooser_open = False


    '''
    File Manager, called when a file has been selected on a non-android platform.
    '''
    def file_manager_callback(self, path: str):
        self.exit_manager()
        self.parse_file(path)
        #MDSnackbar(MDSnackbarText(text=path), y=dp(24), pos_hint={"center_x": 0.5}, size_hint_x=0.8).open()


    '''
    Closes the File Manager.
    '''
    def exit_manager(self, *args):
        '''Called when the user reaches the root of the directory tree.'''
        self.manager_open = False
        self.file_manager.close()


    '''
    Capture keyboard input.
    '''
    def events(self, instance, keyboard, keycode, text, modifiers):
        '''Called when buttons are pressed on the mobile device.'''
        if keyboard in (1001, 27):
            if self.manager_open:
                self.file_manager.back()
            else:
                self.stop()
        return True


    def on_start(self):
        self.root.ids.selected_path.text = '--'
        self.select_map_source()
        return super().on_start()


    '''
    Called when the app is exited.
    '''
    def on_stop(self):
        self.stop_flight(True)
        return super().on_stop()


    '''
    Read configs from storage.
    '''
    def readConfig(self):
        self.root.ids.selected_uom.text = self.config.get('preferences', 'unit_of_measure')
        self.root.ids.selected_home_marker.active = self.config.getboolean('preferences', 'show_marker_home')
        self.root.ids.selected_ctrl_marker.active = self.config.getboolean('preferences', 'show_marker_ctrl')
        self.root.ids.selected_flight_path_width.text = self.config.get('preferences', 'flight_path_width')
        self.root.ids.selected_rounding.active = self.config.getboolean('preferences', 'rounded_readings')
        self.root.ids.selected_mapsource.text = self.config.get('preferences', 'map_tile_server')
        self.root.ids.selected_refresh_rate.text = self.config.get('preferences', 'refresh_rate')


    '''
    Constructor
    '''
    def __init__(self, **kwargs):
        print("constructor...")
        super().__init__(**kwargs)
        locale.setlocale(locale.LC_ALL, '')
        if platform == 'android':
            request_permissions([Permission.INTERNET, Permission.WRITE_EXTERNAL_STORAGE, Permission.READ_EXTERNAL_STORAGE])
            self.chosenFile = None
            self.chooser_open = False # To track Android File Manager (Chooser)
        else:
            self.manager_open = False # To track non-Android File Manager
            self.file_manager = MDFileManager(exit_manager = self.exit_manager, select_path = self.file_manager_callback, ext = ['.zip'])
        Window.bind(on_keyboard=self.events)
        self.ctrlmarker = MapMarker(source="assets/Arturo-Wibawa-Akar-Game-controller.48.png", anchor_y=0.5)
        self.homemarker = MapMarker(source="assets/Custom-Icon-Design-Mono-General-3-Home.48.png", anchor_y=0.5)
        self.dronemarker = MapMarker(source="assets/Iconoir-Team-Iconoir-Drone.48.png", anchor_y=0.5)
        cfgloc = self.get_application_config()
        print(f"cfg loc: {cfgloc}")
        self.flightPaths = None
        self.flightOptions = None
        self.isPlaying = False


    '''
    Generate a config file with default settings.
    '''
    def build_config(self, config):
        print(f"build_config {config}")
        config.setdefaults('preferences', {
            'unit_of_measure': "metric",
            'rounded_readings': True,
            'flight_path_width': "1.0",
            'refresh_rate': "1.00s",
            'show_flight_path': True,
            'show_marker_home': True,
            'show_marker_ctrl': False,
            'map_tile_server': SelectableTileServer.OPENSTREETMAP.value
        })


    def build(self):
        print("build...")
        print(self.root.ids.map.cache_dir)
        if platform == 'android':
            self.chooser = Chooser(self.chooser_callback)
        self.readConfig()
        self.reset()

if __name__ == "__main__":
    #print(Config.get('graphics', 'fullscreen'))
    #print(Config.get('graphics', 'window_state'))
    #Config.set('graphics', 'fullscreen', 0)
    #Config.set('graphics', 'window_state', 'maximized')
    MainApp().run()