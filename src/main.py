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
import sqlite3
import gettext
import webbrowser 

from enum import Enum
from PIL import Image as PILImage

from kivy.core.window import Window
Window.allow_screensaver = False

from kivy.utils import platform
from kivy.config import Config
from kivymd.app import MDApp
from kivy.uix.widget import Widget
from kivymd.uix.dialog import MDDialog, MDDialogHeadlineText, MDDialogButtonContainer, MDDialogContentContainer
from kivymd.uix.progressindicator.progressindicator import MDCircularProgressIndicator
from kivymd.uix.screen import MDScreen
from kivymd.uix.menu import MDDropdownMenu
from kivymd.uix.snackbar import MDSnackbar, MDSnackbarText
from kivymd.uix.label import MDLabel
from kivymd.uix.button import MDButton, MDButtonText, MDIconButton
from kivy.metrics import dp
from kivy.clock import mainthread
from kivy_garden.mapview import MapSource, MapMarker, MarkerMapLayer
from kivy_garden.mapview.geojson import GeoJsonMapLayer
from kivy_garden.mapview.utils import haversine

from kivy.properties import NumericProperty, BoundedNumericProperty, StringProperty
from kivy.uix.scatter import Scatter
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.boxlayout import BoxLayout
from kivy.clock import Clock
from kivy.uix.slider import Slider



if platform == 'android': # Android
    from android.permissions import request_permissions, Permission
    from androidstorage4kivy import SharedStorage, Chooser, ShareSheet
    from platformdirs import user_config_dir, user_data_dir, user_cache_dir
elif platform == 'ios': # iOS
    from plyer import storagepath
else: # Windows, MacOS, Linux
    Window.maximize()
    from plyer import filechooser
    from platformdirs import user_config_dir, user_data_dir, user_cache_dir

from pathlib import Path
from zipfile import ZipFile


class MotorStatus(Enum):
  UNKNOWN = 'Unknown'
  OFF = 'Off'
  IDLE = 'Idling'
  LIFT = 'Running'


class DroneStatus(Enum):
  UNKNOWN = 'Unknown'
  OFF = 'Motors Off'
  IDLE = 'Idling'
  LIFT = 'Taking Off'
  LANDING = 'Landing'
  FLYING = 'Flying'


class FlightMode(Enum):
  UNKNOWN = 'Unknown'
  NORMAL = 'Normal'
  VIDEO = 'Video'
  SPORT = 'Sport'


class PositionMode(Enum):
  UNKNOWN = 'Unknown'
  GPS = 'GPS'
  OPTI = 'Vision'
  ATTI = 'Attitude'


class SelectableTileServer(Enum):
  OPENSTREETMAP = 'OpenStreetMap'
  GOOGLE_STANDARD = 'Google Standard'
  GOOGLE_SATELLITE = 'Google Satellite'
  OPEN_TOPO = 'Open Topo'


class BaseScreen(MDScreen):
    ...


class MainApp(MDApp):

    '''
    Global variables and constants.
    '''
    appVersion = "v2.3.0"
    appName = "Flight Log Viewer"
    appPathName = "FlightLogViewer"
    appTitle = f"{appName} - {appVersion}"
    defaultMapZoom = 3
    pathWidths = [ "1.0", "1.5", "2.0", "2.5", "3.0" ]
    assetColors = [ "#ed1c24", "#0000ff", "#22b14c", "#7f7f7f", "#ffffff", "#c3c3c3", "#000000", "#ffff00", "#a349a4", "#aad2fa" ]
    columns = ('recnum', 'recid', 'flight','timestamp','tod','time','distance1','dist1lat','dist1lon','distance2','dist2lat','dist2lon','distance3','altitude1','altitude2','speed1','speed1lat','speed1lon','speed2','speed2lat','speed2lon','speed1vert','speed2vert','satellites','ctrllat','ctrllon','homelat','homelon','dronelat','dronelon','orientation','motor1status','motor2status','motor3status','motor4status','motorstatus','dronestatus','droneaction','rssi','channel','flightctrlconnected','remoteconnected','droneconnected','rth','positionmode','gps','inuse','traveled','batterylevel','flightmode','flightcounter')
    showColsBasicDreamer = ('flight','tod','time','altitude1','distance1','satellites','homelat','homelon','dronelat','dronelon')
    configFilename = "FlightLogViewer.ini"
    dbFilename = "FlightLogData.db"
    languages = {
        'en_GB': 'English (GB)',
        'en_US': 'English (US)',
        'fr_FR': 'Français',
        'es_ES': 'Español (ES)',
        'es_MX': 'Español (MX)',
        'it_IT': 'Italiano',
        'nl_NL': 'Nederlands',
        'id_ID': 'Indonesia'
    }
    head_lat_2 = 0
    head_lon_2 = 0


    '''
    Parse Atom based logs.
    '''
    def parse_atom_logs(self, importRef):
        self.zipFilename = importRef
        fpvFiles = self.execute_db("SELECT filename FROM log_files WHERE importref = ? AND bintype = 'FPV' ORDER BY filename", (importRef,))
        binFiles = self.execute_db("SELECT filename FROM log_files WHERE importref = ? AND bintype IN ('BIN','FC') ORDER BY filename", (importRef,))

        # First read the FPV file. The presence of this file is optional. The format of this
        # file differs slightly based on the mobile platform it was created on: Android vs iOS.
        # Example filenames:
        #   - 20230819190421-AtomSE-iosSystem-iPhone13Pro-FPV.bin
        #   - 20230826161313-Atom SE-Android-(samsung)-FPV.bin
        fpvStat = {}
        for fileRef in fpvFiles:
            file = fileRef[0]
            with open(os.path.join(self.logfileDir, file), mode='rb') as fpvFile:
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

        timestampMarkers = []

        # First grab timestamps from the filenames. Those are used to calculate the real timestamps with the elapsed time from each record.
        for fileRef in binFiles:
            file = fileRef[0]
            timestampMarkers.append(datetime.datetime.strptime(re.sub("-.*", "", file), '%Y%m%d%H%M%S'))

        if len(timestampMarkers) == 0:
            # Code should not get here, unless empty files were imported in older versions of this app.
            self.show_warning_message(message=_('no_data_in_zip_file'))
            return

        filenameTs = timestampMarkers[0]
        prevReadingTs = timestampMarkers[0]
        firstTs = None
        distTraveled = 0
        self.pathCoords = []
        self.flightStarts = {}
        self.flightEnds = {}
        self.flightStats = []
        pathCoord = []
        isNewPath = True
        isFlying = False
        recordCount = 0
        tableLen = 0
        for fileRef in binFiles:
            file = fileRef[0]
            with open(os.path.join(self.logfileDir, file), mode='rb') as flightFile:
                while True:
                    fcRecord = flightFile.read(512)
                    if (len(fcRecord) < 512):
                        break

                    recordCount = recordCount + 1
                    recordId = struct.unpack('<I', fcRecord[0:4])[0] # This incremental record count is generated by the Potensic Pro app. All other fields are generated directly on the drone itself. The Potensic App saves these drone logs to the .bin files on the mobile device.
                    elapsed = struct.unpack('<Q', fcRecord[5:13])[0] # Microseconds elapsed since previous reading.
                    if (elapsed == 0):
                        continue # handle rare case of invalid record
                    isLegacyLog = struct.unpack('<B', fcRecord[509:510])[0] == 0 and struct.unpack('<B', fcRecord[510:511])[0] == 0 and struct.unpack('<B', fcRecord[511:512])[0] == 0
                    offset1 = 0
                    offset2 = 0
                    offset3 = 0
                    if not isLegacyLog: # 0,0,0 = legacy, 3,3,0 = new
                        offset1 = -6
                        offset2 = -10
                        offset3 = -14
                    flightCounter = struct.unpack('<H', fcRecord[17:19])[0] # Drone's flight counter. Increments each time it initiates a new flight.
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
                    dist3metric = struct.unpack('f', fcRecord[431+offset2:435+offset2])[0]# Distance from home point, as reported by the drone.
                    dist3 = self.dist_val(dist3metric)
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
                    droneConnected = struct.unpack('<B', fcRecord[469+offset3:470+offset3])[0] # Drone connected to controller, 1 = Yes, 0 = No.
                    batteryLevel = struct.unpack('<B', fcRecord[481+offset3:482+offset3])[0] # Battery level.
                    flightMode = struct.unpack('<B', fcRecord[448+offset2:449+offset2])[0] # Flight mode: normal, video, sports.
                    flightModeDesc = FlightMode.VIDEO.value if flightMode == 7 else FlightMode.NORMAL.value if flightMode == 8 else FlightMode.SPORT.value if flightMode == 9 else ''
                    droneAction = struct.unpack('<B', fcRecord[486+offset3:487+offset3])[0] # Drone action: 0 = motors off, 1 = grounded or taking off, 2 = flying, 3 = landing. # Field @ offset 443 looks the same?
                    rth = 0 if droneAction != 2 else struct.unpack('<B', fcRecord[444+offset2:445+offset2])[0] # Home or Return to Home, 1 = Yes, 0 = No.
                    positionMode = struct.unpack('<B', fcRecord[487+offset3:488+offset3])[0] # Unidentified - GPS/ATTI mode? Almost the same @ offset 445
                    inUse = 'Yes' if droneInUse == 0 else 'No'
                    posModeDesc = PositionMode.GPS.value if positionMode == 3 else PositionMode.OPTI.value if positionMode == 2 else positionMode # TODO - don't know value yet for ATTI, probably 1??

                    alt1 = round(self.dist_val(-struct.unpack('f', fcRecord[243+offset2:247+offset2])[0]), 2) # Relative height from controller vs distance to ground??
                    alt2metric = -struct.unpack('f', fcRecord[343+offset2:347+offset2])[0] # Relative height from controller vs distance to ground??
                    alt2 = round(self.dist_val(alt2metric), 2)
                    speed1lat = self.speed_val(struct.unpack('f', fcRecord[247+offset2:251+offset2])[0])
                    speed1lon = self.speed_val(struct.unpack('f', fcRecord[251+offset2:255+offset2])[0])
                    speed2latmetric = struct.unpack('f', fcRecord[327+offset2:331+offset2])[0]
                    speed2lat = self.speed_val(speed2latmetric)
                    speed2lonmetric = struct.unpack('f', fcRecord[331+offset2:335+offset2])[0]
                    speed2lon = self.speed_val(speed2lonmetric)
                    # Offset 335 + 339 (float)
                    # Offset 351 + 355 (float)
                    # Offset 371 + 375 (float)
                    speed1 = round(math.sqrt(math.pow(speed1lat, 2) + math.pow(speed1lon, 2)), 2) # Pythagoras to calculate real speed.
                    speed2metric = round(math.sqrt(math.pow(speed2latmetric, 2) + math.pow(speed2lonmetric, 2)), 2)
                    speed2 = round(math.sqrt(math.pow(speed2lat, 2) + math.pow(speed2lon, 2)), 2) # Pythagoras to calculate real speed.
                    speed1vert = self.speed_val(-struct.unpack('f', fcRecord[255+offset2:259+offset2])[0])
                    speed2vertmetric = -struct.unpack('f', fcRecord[347+offset2:351+offset2])[0] # Vertical speed
                    speed2vertmetricabs = abs(speed2vertmetric)
                    speed2vert = self.speed_val(speed2vertmetric)
                    if self.root.ids.selected_rounding.active and speed2vert < 0 and round(speed2vert) == 0:
                        speed2vert = 0
                    orientation = struct.unpack('f', fcRecord[391+offset2:395+offset2])[0] # Drone orientation in radians.

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
                            distTraveled = 0
                    elif droneMotorStatus == MotorStatus.LIFT:
                        isFlying = True
                        statusChanged = True
                    else:
                        firstTs = None
                        distTraveled = 0

                    droneActionDesc = DroneStatus.UNKNOWN
                    if droneAction == 0:
                        droneActionDesc = DroneStatus.OFF
                    elif droneAction == 1 and droneMotorStatus == MotorStatus.IDLE:
                        droneActionDesc = DroneStatus.IDLE
                    elif droneAction == 1 and droneMotorStatus == MotorStatus.LIFT:
                        droneActionDesc = DroneStatus.LIFT
                    elif droneAction == 2:
                        droneActionDesc = DroneStatus.FLYING
                    elif droneAction == 3:
                        droneActionDesc = DroneStatus.LANDING

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
                        self.flightStats.append([dist3metric, alt2metric, speed2metric, None, dronelat, dronelon, dronelat, dronelon, speed2vertmetricabs, None])
                    else:
                        if dist3metric > self.flightStats[pathNum][0]: # Overall Max distance
                            self.flightStats[pathNum][0] = dist3metric
                        if alt2metric > self.flightStats[pathNum][1]: # Overall Max altitude
                            self.flightStats[pathNum][1] = alt2metric
                        if speed2metric > self.flightStats[pathNum][2]: # Overall Max speed
                            self.flightStats[pathNum][2] = speed2metric
                        if dronelat < self.flightStats[pathNum][4]: # Overall Min latitude
                            self.flightStats[pathNum][4] = dronelat
                        if dronelon < self.flightStats[pathNum][5]: # Overall Min longitude
                            self.flightStats[pathNum][5] = dronelon
                        if dronelat > self.flightStats[pathNum][6]: # Overall Max latitude
                            self.flightStats[pathNum][6] = dronelat
                        if dronelon > self.flightStats[pathNum][7]: # Overall Max longitude
                            self.flightStats[pathNum][7] = dronelon
                        if speed2vertmetricabs > self.flightStats[pathNum][8]: # Vertical Max speed (could be up or down)
                            self.flightStats[pathNum][8] = speed2vertmetricabs
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
                                if lastCoord[0] != 9999:
                                    distTraveled = distTraveled + (haversine(lastCoord[0], lastCoord[1], dronelon, dronelat) * 1000)
                            if pathNum == len(self.flightStats):
                                self.flightStats.append([dist3metric, alt2metric, speed2metric, elapsedTs, dronelat, dronelon, dronelat, dronelon, speed2vertmetricabs, distTraveled])
                            else:
                                if dist3metric > self.flightStats[pathNum][0]: # Flight Max distance
                                    self.flightStats[pathNum][0] = dist3metric
                                if alt2metric > self.flightStats[pathNum][1]: # Flight Max altitude
                                    self.flightStats[pathNum][1] = alt2metric
                                if speed2metric > self.flightStats[pathNum][2]: # Flight Horizontal Max speed
                                    self.flightStats[pathNum][2] = speed2metric
                                self.flightStats[pathNum][3] = elapsedTsRounded # Flight duration
                                if dronelat < self.flightStats[pathNum][4]: # Flight Min latitude
                                    self.flightStats[pathNum][4] = dronelat
                                if dronelon < self.flightStats[pathNum][5]: # Flight Min longitude
                                    self.flightStats[pathNum][5] = dronelon
                                if dronelat > self.flightStats[pathNum][6]: # Flight Max latitude
                                    self.flightStats[pathNum][6] = dronelat
                                if dronelon > self.flightStats[pathNum][7]: # Flight Max longitude
                                    self.flightStats[pathNum][7] = dronelon
                                if speed2vertmetricabs > self.flightStats[pathNum][8]: # Vertical Max speed (could be up or down)
                                    self.flightStats[pathNum][8] = speed2vertmetricabs
                                self.flightStats[pathNum][9] = distTraveled # Distance Travelled

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
                    self.logdata.append([recordCount, recordId, pathNum, readingTs.isoformat(sep=' '), readingTs.strftime('%X'), elapsedTs, f"{self.fmt_num(dist1)}", f"{self.fmt_num(dist1lat)}", f"{self.fmt_num(dist1lon)}", f"{self.fmt_num(dist2)}", f"{self.fmt_num(dist2lat)}", f"{self.fmt_num(dist2lon)}", f"{self.fmt_num(dist3)}", f"{self.fmt_num(alt1)}", f"{self.fmt_num(alt2)}", f"{self.fmt_num(speed1)}", f"{self.fmt_num(speed1lat)}", f"{self.fmt_num(speed1lon)}", f"{self.fmt_num(speed2)}", f"{self.fmt_num(speed2lat)}", f"{self.fmt_num(speed2lon)}", f"{self.fmt_num(speed1vert)}", f"{self.fmt_num(speed2vert)}", str(satellites), str(ctrllat), str(ctrllon), str(homelat), str(homelon), str(dronelat), str(dronelon), orientation, motor1Stat, motor2Stat, motor3Stat, motor4Stat, droneMotorStatus.value, droneActionDesc.value, droneAction, fpvRssi, fpvChannel, fpvFlightCtrlConnected, fpvRemoteConnected, droneConnected, rth, posModeDesc, gpsStatus, inUse, f"{self.fmt_num(self.dist_val(distTraveled))}", batteryLevel, flightModeDesc, flightCounter])
                    tableLen = tableLen + 1

            flightFile.close()

        if (len(pathCoord) > 0):
            self.pathCoords.append(pathCoord)
        dbRows = self.execute_db("""
            SELECT flight_number, duration, max_distance, max_altitude, max_h_speed, max_v_speed, traveled
            FROM flight_stats WHERE importref = ?
            """, (importRef,)
        )
        hasData = dbRows is not None and len(dbRows) > 0
        for i in range(1, len(self.flightStats)):
            if not hasData:
                # These stats are used in the log file list to show metrics for each file.
                self.execute_db("""
                    INSERT INTO flight_stats(importref, flight_number, duration, max_distance, max_altitude, max_h_speed, max_v_speed, traveled)
                    VALUES(?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (importRef, i, self.flightStats[i][3].total_seconds(), self.flightStats[i][0], self.flightStats[i][1], self.flightStats[i][2], self.flightStats[i][8], self.flightStats[i][9])
                )
            if self.flightStats[0][3] == None:
                self.flightStats[0][2] = self.flightStats[i][2] # Flight Horizontal Max speed
                self.flightStats[0][3] = self.flightStats[i][3] # Flight duration (total)
                self.flightStats[0][4] = self.flightStats[i][4] # Flight Min latitude
                self.flightStats[0][5] = self.flightStats[i][5] # Flight Min longitude
                self.flightStats[0][6] = self.flightStats[i][6] # Flight Max latitude
                self.flightStats[0][7] = self.flightStats[i][7] # Flight Max longitude
                self.flightStats[0][8] = self.flightStats[i][8] # Vertical Max speed (could be up or down)
                self.flightStats[0][9] = self.flightStats[i][9] # Distance Travelled (total)
            else:
                self.flightStats[0][3] = self.flightStats[0][3] + self.flightStats[i][3] # Total duration
                if self.flightStats[i][2] > self.flightStats[0][2]: # Flight Horizontal Max speed
                    self.flightStats[0][2] = self.flightStats[i][2]
                if self.flightStats[i][4] < self.flightStats[0][4]: # Flight Min latitude
                    self.flightStats[0][4] = self.flightStats[i][4]
                if self.flightStats[i][5] < self.flightStats[0][5]: # Flight Min longitude
                    self.flightStats[0][5] = self.flightStats[i][5]
                if self.flightStats[i][6] > self.flightStats[0][6]: # Flight Max latitude
                    self.flightStats[0][6] = self.flightStats[i][6]
                if self.flightStats[i][7] > self.flightStats[0][7]: # Flight Max longitude
                    self.flightStats[0][7] = self.flightStats[i][7]
                if self.flightStats[i][8] > self.flightStats[0][8]: # Vertical Max speed (could be up or down)
                    self.flightStats[0][8] = self.flightStats[i][8]
                self.flightStats[0][9] = self.flightStats[0][9] + self.flightStats[i][9] # Total Distance Travelled

        mainthread(self.show_flight_date)(importRef)
        mainthread(self.show_flight_stats)()
        mainthread(self.init_gauges)()


    def show_flight_date(self, importRef):
        logDate = re.sub(r"-.*", r"", importRef) # Extract date section from log (zip) filename.
        self.root.ids.value_date.text = datetime.date.fromisoformat(logDate).strftime("%x")
        #self.root.ids.map_metrics1.text = f" {importRef} / {_('map_date')} {self.root.ids.value_date.text}"


    def show_flight_stats(self):
        self.title = self.appTitle + " - " + self.zipFilename
        self.root.ids.flight_stats_grid.add_widget(MDLabel(text=_('flight_flight'), bold=True, max_lines=1, halign="left", valign="center", padding=[dp(10),0,0,0]))
        self.root.ids.flight_stats_grid.add_widget(MDLabel(text=_('flight_duration'), bold=True, max_lines=1, halign="right", valign="center"))
        self.root.ids.flight_stats_grid.add_widget(MDLabel(text=_('flight_distance_flown'), bold=True, max_lines=1, halign="right", valign="center"))
        self.root.ids.flight_stats_grid.add_widget(MDLabel(text=_('flight_maximum_distance'), bold=True, max_lines=1, halign="right", valign="center"))
        self.root.ids.flight_stats_grid.add_widget(MDLabel(text=_('flight_maximum_altitude'), bold=True, max_lines=1, halign="right", valign="center"))
        self.root.ids.flight_stats_grid.add_widget(MDLabel(text=_('flight_maximum_horizontal_speed'), bold=True, max_lines=1, halign="right", valign="center"))
        self.root.ids.flight_stats_grid.add_widget(MDLabel(text=_('flight_maximum_vertical_speed'), bold=True, max_lines=1, halign="right", valign="center", padding=[0,0,dp(10),0]))
        rowcount = len(self.flightStats)
        for i in range(0 if rowcount > 2 else 1, rowcount):
            self.root.ids.flight_stats_grid.add_widget(MDLabel(text=(_('flight_flight_number').format(flight_number=i) if i > 0 else _('flight_overall')), max_lines=1, halign="left", valign="center", padding=[dp(10),0,0,0]))
            self.root.ids.flight_stats_grid.add_widget(MDLabel(text=str(self.flightStats[i][3]), max_lines=1, halign="right", valign="center"))
            self.root.ids.flight_stats_grid.add_widget(MDLabel(text=f"{self.fmt_num(self.dist_val(self.flightStats[i][9]))} {self.dist_unit()}", max_lines=1, halign="right", valign="center"))
            self.root.ids.flight_stats_grid.add_widget(MDLabel(text=f"{self.fmt_num(self.dist_val(self.flightStats[i][0]))} {self.dist_unit()}", max_lines=1, halign="right", valign="center"))
            self.root.ids.flight_stats_grid.add_widget(MDLabel(text=f"{self.fmt_num(self.dist_val(self.flightStats[i][1]))} {self.dist_unit()}", max_lines=1, halign="right", valign="center"))
            self.root.ids.flight_stats_grid.add_widget(MDLabel(text=f"{self.fmt_num(self.speed_val(self.flightStats[i][2]))} {self.speed_unit()}", max_lines=1, halign="right", valign="center"))
            self.root.ids.flight_stats_grid.add_widget(MDLabel(text=f"{self.fmt_num(self.speed_val(self.flightStats[i][8]))} {self.speed_unit()}", max_lines=1, halign="right", valign="center", padding=[0,0,dp(10),0]))


    '''
    Import the selected Flight Data Zip file.
    '''
    def initiate_import_file(self, selectedFile):
        if not os.path.isfile(selectedFile):
            self.show_error_message(message=_('no_valid_file_specified').format(filename=selectedFile))
            return
        zipBaseName = os.path.basename(selectedFile)
        droneModel = re.sub(r"[0-9]*-(.*)-Drone.*", r"\1", zipBaseName) # Pull drone model from zip filename.
        droneModel = re.sub(r"[^\w]", r" ", droneModel) # Remove non-alphanumeric characters from the model name.
        lcDM = droneModel.lower()
        if 'p1a' in lcDM or 'atom' in lcDM:
            already_imported = self.execute_db("SELECT importedon FROM imports WHERE importref = ?", (zipBaseName,))
            if already_imported is None or len(already_imported) == 0:
                self.dialog_wait.open()
                threading.Thread(target=self.import_file, args=(droneModel, zipBaseName, selectedFile)).start()
            else:
                self.post_import_cleanup(selectedFile)
                self.show_warning_message(message=_('file_already_imported_on').format(timestamp=already_imported[0][0]))
                return


    def import_file(self, droneModel, zipBaseName, selectedFile):
        hasFc = False
        lcDM = droneModel.lower()
        fpvList = []
        # Extract the bin files and copy to the app data directory, then update the DB references.
        binLog = os.path.join(tempfile.gettempdir(), "flightdata")
        shutil.rmtree(binLog, ignore_errors=True) # Delete old temp files if they were missed before.
        with ZipFile(selectedFile, 'r') as unzip:
            unzip.extractall(path=binLog)
        for binFile in glob.glob(os.path.join(binLog, '**/*'), recursive=True):
            binBaseName = os.path.basename(binFile)
            binType = "FPV" if binBaseName.endswith("-FPV.bin") else (
                "BIN" if binBaseName.endswith("-FC.bin") else (
                "FC" if binBaseName.endswith("-FC.fc") else None))
            if binType is not None:
                if binType == 'FPV':
                    fpvList.append(binFile)
                else:
                    if not hasFc:
                        logDate = re.sub(r"-.*", r"", zipBaseName) # Extract date section from zip filename.
                        self.execute_db("INSERT OR IGNORE INTO models(modelref) VALUES(?)", (droneModel,))
                        self.execute_db(
                            "INSERT OR IGNORE INTO imports(importref, modelref, dateref, importedon) VALUES(?,?,?,?)",
                            (zipBaseName, droneModel, logDate, datetime.datetime.now().isoformat())
                        )
                        hasFc = True
                    shutil.copyfile(binFile, os.path.join(self.logfileDir, binBaseName))
                    self.execute_db(
                        "INSERT INTO log_files(filename, importref, bintype) VALUES(?,?,?)",
                        (binBaseName, zipBaseName, binType)
                    )
        if hasFc:
            # Once we have FC bin/fc files, we will also import FVP files as well.
            for fpvFile in fpvList:
                fpvBaseName = os.path.basename(fpvFile)
                shutil.copyfile(fpvFile, os.path.join(self.logfileDir, fpvBaseName))
                self.execute_db(
                    "INSERT INTO log_files(filename, importref, bintype) VALUES(?,?,?)",
                    (fpvBaseName, zipBaseName, "FPV")
                )
        shutil.rmtree(binLog, ignore_errors=True) # Delete temp files.
        if hasFc:
            self.show_info_message(message=_('log_import_completed'))
            self.map_rebuild_required = False
            mainthread(self.open_view)("Screen_Map")
            if ('p1a' in lcDM):
                self.parse_dreamer_logs(zipBaseName) # TODO - port over from app version 1.4.2
            else:
                if (not 'atom' in lcDM):
                    self.show_warning_message(message=_('drone_not_supported').format(modelname=droneModel))
                self.parse_atom_logs(zipBaseName)
            mainthread(self.set_default_flight)()
            mainthread(self.generate_map_layers)()
            mainthread(self.select_flight)()
            mainthread(self.select_drone_model)(droneModel)
            mainthread(self.list_log_files)()
        else:
            self.show_warning_message(message=_('nothing_to_import'))
        self.post_import_cleanup(selectedFile)
        self.dialog_wait.dismiss()


    '''
    Delete the import zip file. Applies to iOS only.
    '''
    def post_import_cleanup(self, selectedFile):
        if platform == 'ios':
            os.remove(selectedFile)


    def ios_doc_path(self):
        return storagepath.get_documents_dir()[7:] # remove "file://" from URL to create a Python-friendly path.


    '''
    Open a file import dialog (import zip file).
    '''
    def open_file_import_dialog(self):
        if self.is_android:
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
                self.initiate_import_file(self.chosenFile)
        elif self.is_ios:
            # iOS File Dialog is currently not supported through the Kivy framework. Instead,
            # grab the zip file through the exposed app's Documents directory where users can
            # drop the file via the OS File Browser or through iTunes. Load oldest file first.
            gotFile = False
            for zipFile in sorted(glob.glob(os.path.join(self.ios_doc_path(), '*.zip'), recursive=False)):
                if not "_Backup_" in os.path.basename(zipFile): # Ignore backup zip files.
                    self.initiate_import_file(zipFile)
                    break
            if not gotFile:
                self.show_warning_message(message=_('ios_nothing_to_import'))
        else:
            oldwd = os.getcwd() # Remember current workdir. Windows File Explorer is nasty and changes it, causing all sorts of mapview issues.
            myFiles = filechooser.open_file(title=_('select_log_zip_file'), filters=[(_('zip_files'), "*.zip")], mime_type="zip")
            newwd = os.getcwd()
            if oldwd != newwd:
                os.chdir(oldwd) # Change it back!
            if myFiles and len(myFiles) > 0 and os.path.isfile(myFiles[0]):
                self.initiate_import_file(myFiles[0])


    '''
    Save the flight data in a CSV file.
    '''
    def save_csv_file(self, csvFilename):
        with open(csvFilename, 'w') as f:
            head = ''
            for col in self.columns:
                if len(head) > 0:
                    head = head + ','
                head = head + col
            f.write(head)
            for record in self.logdata:
                hasWritten = False
                f.write('\n')
                for col in record:
                    if (hasWritten):
                        f.write(',')
                    f.write('"' + str(col) + '"')
                    hasWritten = True
        f.close()


    '''
    Open a file export dialog (export csv file).
    '''
    def open_file_export_dialog(self):
        csvFilename = re.sub("\.zip$", "", self.zipFilename) + ".csv"
        if self.is_android:
            csvFile = os.path.join(self.shared_storage.get_cache_dir(), csvFilename)
            try:
                self.save_csv_file(csvFile)
                url = self.shared_storage.copy_to_shared(csvFile)
                ShareSheet().share_file(url)
                self.show_info_message(message=_('data_exported_to').format(filename=csvFile))
            except Exception as e:
                msg = _('error_saving_export_csv').format(filename=csvFile, error=e)
                print(msg)
                self.show_error_message(message=msg)
        elif self.is_ios:
            csvFile = os.path.join(self.ios_doc_path(), csvFilename)
            try:
                self.save_csv_file(csvFile)
                self.show_info_message(message=_('export_csv_file_saved').format(filename=csvFile))
            except Exception as e:
                msg = _('error_saving_export_csv').format(filename=csvFile, error=e)
                print(msg)
                self.show_error_message(message=msg)
        elif self.is_windows: # For windows, use "save_file" interface in plyer filechooser.
            oldwd = os.getcwd() # Remember current workdir. Windows File Explorer is nasty and changes it, causing all sorts of mapview issues.
            myFiles = filechooser.save_file(title=_('save_export_csv_file'), filters=["*.csv"], path=csvFilename)
            newwd = os.getcwd()
            if oldwd != newwd:
                os.chdir(oldwd) # Change it back!
            if myFiles and len(myFiles) > 0:
                try:
                    self.save_csv_file(myFiles[0])
                    self.show_info_message(message=_('data_exported_to').format(filename=myFiles[0]))
                except Exception as e:
                    msg = _('error_saving_export_csv').format(filename=myFiles[0], error=e)
                    print(msg)
                    self.show_error_message(message=msg)
        else: # For non-windows, use "choose_dir" interface in plyer filechooser because plyer does currently not set the desired filename.
            oldwd = os.getcwd() # Remember current workdir in case the OS File browser changes it, causing all sorts of mapview issues.
            myFiles = filechooser.choose_dir(title=_('save_export_csv_file'))
            newwd = os.getcwd()
            if oldwd != newwd:
                os.chdir(oldwd) # Change it back!
            if myFiles and len(myFiles) > 0 and os.path.isdir(myFiles[0]):
                csvFile = os.path.join(myFiles[0], csvFilename)
                try:
                    self.save_csv_file(csvFile)
                    self.show_info_message(message=_('data_exported_to').format(filename=csvFile))
                except Exception as e:
                    msg = _('error_saving_export_csv').format(filename=csvFile, error=e)
                    print(msg)
                    self.show_error_message(message=msg)


    '''
    File Chooser, called when a file has been selected on the Android device.
    '''
    def import_android_chooser_callback(self, uri_list):
        try:
            for uri in uri_list:
                self.chosenFile = self.shared_storage.copy_from_shared(uri) # copy to private storage
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
        if self.layer_drone:
            self.root.ids.map.remove_marker(self.dronemarker)
            self.root.ids.map.remove_layer(self.layer_drone)
            self.layer_drone = None
            self.dronemarker = None
        if self.flightPaths:
            for flightPath in self.flightPaths:
                for maplayer in flightPath:
                    try:
                        self.root.ids.map.remove_layer(maplayer)
                    except:
                        ... # Do nothing
        if self.layer_ctrl:
            self.root.ids.map.remove_marker(self.ctrlmarker)
            self.root.ids.map.remove_layer(self.layer_ctrl)
            self.layer_ctrl = None
            self.ctrlmarker = None
        if self.layer_home:
            self.root.ids.map.remove_marker(self.homemarker)
            self.root.ids.map.remove_layer(self.layer_home)
            self.layer_home = None
            self.homemarker = None


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


    def init_gauges(self):
        print("INIT GAUGES")
        self.root.ids.HSPDgauge.display_unit = self.speed_unit()
        self.root.ids.VSPDgauge.display_unit = self.speed_unit()
        self.root.ids.ALgauge.display_unit = self.dist_unit()
        self.root.ids.DSgauge.display_unit = self.dist_unit()


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


    def open_view(self, view_name):
        self.root.ids.screen_manager.current = view_name


    '''
    Called when map screen is opened.
    '''
    def entered_screen_map(self):
        self.app_view = "map"
        if self.map_rebuild_required:
            self.clear_map()
            self.generate_map_layers()
            self.init_map_layers()
            self.set_markers()
            self.map_rebuild_required = False


    '''
    Called when map screen is navigated away from.
    '''
    def left_screen_map(self):
        self.stop_flight()
        self.map_rebuild_required = False


    '''
    Called when flight summary screen is opened.
    '''
    def entered_screen_summary(self):
        self.app_view = "sum"


    '''
    Called when log file screen is opened.
    '''
    def entered_screen_log(self):
        self.app_view = "log"


    '''
    Called when map screen is closed.
    '''
    def close_map_screen(self):
        self.reset()
        self.root.ids.screen_manager.current = "Screen_Log_Files"


    '''
    Update ctrl/home/drone markers on the map as well as other labels with flight information.
    '''
    def set_markers(self, updateSlider=True):
        if not self.currentRowIdx:
            return
        record = self.logdata[self.currentRowIdx]
        rthDesc = "RTH" if record[self.columns.index('rth')] == 1 else ''
        batteryLevel = record[self.columns.index('batterylevel')]
        batLevelRnd = math.floor(batteryLevel / 10 + 0.5) * 10 # round to nearest 10.
        flightMode = record[self.columns.index('flightmode')]
        dronestatus = record[self.columns.index('dronestatus')]
        positionMode = record[self.columns.index('positionmode')]

        self.root.ids.value1_alt.text = f"{record[self.columns.index('altitude2')]} {self.dist_unit()}"
        self.root.ids.value1_traveled.text = f"{record[self.columns.index('traveled')]} {self.dist_unit()}"
        self.root.ids.value1_traveled_short.text = f"({self.shorten_dist_val(record[self.columns.index('traveled')])} {self.dist_unit_km()})"
        self.root.ids.value1_flightmode.text = flightMode
        self.root.ids.value1_dist.text = f"{record[self.columns.index('distance3')]} {self.dist_unit()}"
        self.root.ids.value1_dist_short.text = f"({self.shorten_dist_val(record[self.columns.index('distance3')])} {self.dist_unit_km()})"
        self.root.ids.value1_hspeed.text = f"{record[self.columns.index('speed2')]} {self.speed_unit()}"
        self.root.ids.value1_vspeed.text = f"{record[self.columns.index('speed2vert')]} {self.speed_unit()}"
        self.root.ids.value1_batterylevel.text = f"{record[self.columns.index('batterylevel')]}%"  # rob
        self.root.ids.value1_rth_desc.text = dronestatus if len(rthDesc) == 0 else rthDesc # rob
        elapsed = record[5]
        elapsed = elapsed - datetime.timedelta(microseconds=elapsed.microseconds) # truncate to milliseconds
        self.root.ids.value1_elapsed.text = str(elapsed)

        self.root.ids.battery_level.icon = "battery" if batLevelRnd == 100 else f"battery-{batLevelRnd}"
        self.root.ids.flight_mode.icon = "alpha-v-box" if flightMode == FlightMode.VIDEO.value else "alpha-s-box" if flightMode == FlightMode.SPORT.value else "alpha-n-box" if flightMode == FlightMode.NORMAL.value else ""
        self.root.ids.drone_connection.icon = "signal" if record[self.columns.index('droneconnected')] == 1 else "signal-off"
        self.root.ids.drone_action.icon = "airplane-marker" if record[self.columns.index('rth')] == 1 else "airplane-takeoff" if dronestatus == DroneStatus.LIFT.value else "airplane-landing" if dronestatus == DroneStatus.LANDING.value else "airplane" if dronestatus == DroneStatus.FLYING.value else "car-break-parking" if dronestatus == DroneStatus.IDLE.value else ""
        self.root.ids.position_mode.icon = "satellite-uplink" if positionMode == PositionMode.GPS.value else "eye" if positionMode == PositionMode.OPTI.value else "panorama-fisheye" if positionMode == PositionMode.ATTI.value else ""

        # Set horizontal, vertical and altitude gauge values. Use rounded values.
        self.root.ids.HSPDgauge.value = round(locale.atof(record[self.columns.index('speed2')]))
        self.root.ids.VSPDgauge.value = round(locale.atof(record[self.columns.index('speed2vert')]))
        self.root.ids.ALgauge.value = round(locale.atof(record[self.columns.index('altitude2')]))
        self.root.ids.DSgauge.value = round(locale.atof(record[self.columns.index('traveled')]))

        # Set up vars for HDgauge calcs
        if self.root.ids.value_duration.text == "":
            self.head_lat_2 = float(record[self.columns.index('dronelat')])
            self.head_lon_2 = float(record[self.columns.index('dronelon')])
        else:
            head_lat_1 = self.head_lat_2
            head_lon_1 = self.head_lon_2
            self.head_lat_2 = float(record[self.columns.index('dronelat')])
            self.head_lon_2 = float(record[self.columns.index('dronelon')])
            # determine bearing.
            dLon = (self.head_lon_2 - head_lon_1)
            x = math.cos(math.radians(self.head_lat_2)) * math.sin(math.radians(dLon))
            y = math.cos(math.radians(head_lat_1)) * math.sin(math.radians(self.head_lat_2)) - math.sin(math.radians(head_lat_1)) * math.cos(math.radians(self.head_lat_2)) * math.cos(math.radians(dLon))
            brng = math.atan2(x,y)
            brng = math.degrees(brng)
            if self.root.ids.HSPDgauge.value != 0:
                if brng < 0:
                    brng = 360 + brng
                    self.root.ids.HDgauge.value = brng

        rthFullDesc = "" if len(rthDesc) == 0 else f" | {rthDesc}"
        self.root.ids.map_metrics2.text = f" {_('map_time')} {'{:>8}'.format(str(elapsed))} | {_('map_dist')[:5]} {(record[self.columns.index('distance3')])} {self.dist_unit()} | {_('map_alt')[:4]} {(record[self.columns.index('altitude2')])} {self.dist_unit()} | {_('map_hs')[:3]} {(record[self.columns.index('speed2')])} {self.speed_unit()} | {_('map_vs')[:3]} {(record[self.columns.index('speed2vert')])} {self.speed_unit()} | {_('map_flightmode')} {flightMode} | {_('map_battery')} {record[self.columns.index('batterylevel')]}% | {record[self.columns.index('dronestatus')]}{rthFullDesc} | {record[self.columns.index('positionmode')]} | {_('map_sats')[:5]} {(record[self.columns.index('satellites')])}"

        if updateSlider:
            if self.root.ids.value_duration.text != "":
                durstr = self.root.ids.value_duration.text.split(":")
                durval = datetime.timedelta(hours=int(durstr[0]), minutes=int(durstr[1]), seconds=int(durstr[2]))
                if durval != 0: # Prevent division by zero
                    self.root.ids.flight_progress.value = elapsed / durval * 100
                    self.root.ids.flight_progress.slider.value = elapsed / durval * 100
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
            self.dronemarker.source = self.get_drone_icon_source()
        except:
            ... # Do nothing
        self.root.ids.map.trigger_update(False)


    '''
    Update ctrl/home/drone markers on the map with the next set of coordinates in the table list.
    '''
    def set_frame(self):
        self.root.ids.flight_progress.is_updating = True
        self.isPlaying = True
        self.root.ids.playbutton.icon = "pause"
        refreshRate = float(re.sub("[^0-9\.]", "", self.root.ids.selected_refresh_rate.text))
        totalTimeElapsed = self.logdata[self.currentRowIdx][self.columns.index('time')]
        prevTs = None
        timeElapsed = None
        while (not self.stopRequested) and (self.currentRowIdx < self.currentEndIdx):
            mainthread(self.set_markers)()
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
        self.root.ids.playbutton.icon = "play"
        self.root.ids.flight_progress.is_updating = False


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


    def on_progress_slider_value_change(self, instance, value):
       # if (slider.is_updating): # Check if slider value is being updated from outside the slider (i.e. playback)
        #    return
        if len(self.logdata) == 0:
            return # Do nothing
        if (self.root.ids.selected_path.text == '--'):
            return # Do nothing
        # Determine approximate selected duration based on slider position
        durstr = self.root.ids.value_duration.text.split(":")
        durval = datetime.timedelta(hours=int(durstr[0]), minutes=int(durstr[1]), seconds=int(durstr[2]))
        newdur = durval / 100 * self.root.ids.flight_progress.slider.value
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
            self.show_warning_message(message=_('no_data_to_play_back'))
            return
        if (self.root.ids.selected_path.text == '--'):
            self.show_info_message(message=_('no_flight_selected'))
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
            self.show_info_message(message=_('no_previous_flight'))


    '''
    Jump to end of current flight, or the beginning of the next one.
    '''
    def jump_next_flight(self):
        if len(self.logdata) == 0:
            self.show_warning_message(message=_('no_data_to_play_back'))
            return
        if (self.root.ids.selected_path.text == '--'):
            self.show_info_message(message=_('no_flight_selected'))
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
            self.show_info_message(message=_('no_next_flight'))


    '''
    Start or resume playback of the selected flight. If flight is finished, restart from beginning.
    '''
    def play_flight(self):
        self.stopRequested = False
        if (self.isPlaying):
            self.stop_flight(True)
            return
        if len(self.logdata) == 0:
            self.show_warning_message(message=_('no_data_to_play_back'))
            return
        if (self.root.ids.selected_path.text == '--'):
            self.show_info_message(message=_('select_flight_to_play_back'))
            return
        if self.currentRowIdx == self.currentEndIdx:
            self.currentRowIdx = self.currentStartIdx
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


    '''
    Change Flight Path Line Width (Preferences).
    '''
    def flight_path_width_selection(self, slider, coords):
        Config.set('preferences', 'flight_path_width', int(slider.value))
        Config.write()
        self.map_rebuild_required = True


    '''
    Flight Path Colours functions.
    '''
    def flight_path_color_selection(self, slider, coords):
        colorIdx = int(slider.value)
        slider.track_active_color = self.assetColors[colorIdx]
        slider.track_inactive_color = self.assetColors[colorIdx]
        Config.set('preferences', 'flight_path_color', colorIdx)
        Config.write()
        self.map_rebuild_required = True


    '''
    Return reference to the drone icon image. If it needs to be rotated, it will be generated from the base icon image.
    '''
    def get_drone_icon_source(self):
        base_filename = f"Drone-{str(int(self.root.ids.selected_marker_drone_color.value)+1)}"
        if not self.currentRowIdx:
            # Return base image if there is no current rotation (orientation).
            return f"assets/{base_filename}.png"
        record = self.logdata[self.currentRowIdx]
        orientation = round(math.degrees(record[self.columns.index('orientation')])) # Drone orientation in degrees, -180 to 180.
        rotation = abs(orientation) if orientation <= 0 else 360 - orientation # Convert to 0 - 359 range.
        rotated_filename = os.path.join(self.root.ids.map.cache_dir, f"{base_filename}-{rotation}.png")
        if not os.path.exists(rotated_filename):
            drone_base_icon = PILImage.open(f"assets/{base_filename}.png")
            drone_rotated_icon = drone_base_icon.rotate(rotation, expand=True)
            drone_rotated_icon.save(rotated_filename)
        return rotated_filename


    '''
    Drone Marker Colour functions.
    '''
    def marker_drone_color_selection(self, slider, coords):
        colorIdx = int(slider.value)
        slider.track_active_color = self.assetColors[colorIdx]
        slider.track_inactive_color = self.assetColors[colorIdx]
        Config.set('preferences', 'marker_drone_color', colorIdx)
        Config.write()
        if self.dronemarker:
            self.dronemarker.source = self.get_drone_icon_source()
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


    def set_default_flight(self):
        if len(self.flightOptions) > 0:
            self.root.ids.selected_path.text = self.flightOptions[0]
        else:
            self.root.ids.selected_path.text = "--"


    def select_flight(self, skip_to_end=False):
        self.clear_map()
        self.init_map_layers()
        flightNum = 0 if (self.root.ids.selected_path.text == '--') else int(re.sub(r"[^0-9]", r"", self.root.ids.selected_path.text))
        if (flightNum == 0):
            self.root.ids.flight_progress.is_updating = True
            self.root.ids.flight_progress.value = 0
            self.root.ids.flight_progress.is_updating = False
            self.root.ids.value1_elapsed.text = ""
            self.root.ids.value1_alt.text = ""
            self.root.ids.value1_traveled.text = ""
            self.root.ids.value1_traveled_short.text = ""
            self.root.ids.value1_rth_desc.text = "" # rob
            self.root.ids.value1_batterylevel.text = "" # rob
            self.root.ids.value1_flightmode.text = "" # rob
            self.root.ids.value1_dist.text = ""
            self.root.ids.value1_dist_short.text = ""
            self.root.ids.value1_hspeed.text = ""
            self.root.ids.value1_vspeed.text = ""
            #self.root.ids.map_metrics1.text = ""
            self.root.ids.map_metrics2.text = ""
        else:
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
            self.root.ids.value_maxdist.text = f"{self.fmt_num(self.dist_val(self.flightStats[flightNum][0]))} {self.dist_unit()}"
            self.root.ids.value_maxdist_short.text = f"({self.shorten_dist_val(self.fmt_num(self.dist_val(self.flightStats[flightNum][0])))} {self.dist_unit_km()})"
            self.root.ids.value_maxalt.text = f"{self.fmt_num(self.dist_val(self.flightStats[flightNum][1]))} {self.dist_unit()}"
            self.root.ids.value_maxhspeed.text = f"{self.fmt_num(self.speed_val(self.flightStats[flightNum][2]))} {self.speed_unit()}"
            self.root.ids.value_duration.text = str(self.flightStats[flightNum][3])
            self.root.ids.value_tottraveled.text = f"{self.fmt_num(self.dist_val(self.flightStats[flightNum][9]))} {self.dist_unit()}"
            self.root.ids.value_tottraveled_short.text = f"({self.shorten_dist_val(self.dist_val(self.flightStats[flightNum][9]))} {self.dist_unit_km()})"


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
        self.show_info_message(message=_('reopen_log_for_changes_to_take_effect'))


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


    '''
    Change Display of Home Marker (Preferences).
    '''
    def home_marker_selection(self, item):
        Config.set('preferences', 'show_marker_home', item.active)
        Config.write()
        self.map_rebuild_required = True
        if self.layer_home:
            self.layer_home.opacity = 1 if self.root.ids.selected_home_marker.active else 0


    '''
    Change Display of Controller Marker (Preferences).
    '''
    def ctrl_marker_selection(self, item):
        Config.set('preferences', 'show_marker_ctrl', item.active)
        Config.write()
        self.map_rebuild_required = True
        if self.layer_ctrl:
            self.layer_ctrl.opacity = 1 if self.root.ids.selected_ctrl_marker.active else 0


    '''
    Enable or disable rounding of values (Preferences).
    '''
    def rounding_selection(self, item):
        Config.set('preferences', 'rounded_readings', item.active)
        Config.write()
        self.stop_flight(True)
        self.show_info_message(message=_('reopen_log_for_changes_to_take_effect'))


    '''
    Enable or disable analog gauges (Preferences).
    '''
    def gauges_selection(self, item):
        Config.set('preferences', 'gauges', item.active)
        Config.write()


    '''
    Enable or disable circular gauges (Preferences).
    '''
    def statusicons_selection(self, item):
        Config.set('preferences', 'statusicons', item.active)
        Config.write()


    '''    
    Return specified distance in the proper Unit (metric vs imperial).
    '''
    def dist_val(self, num):
        if num is None:
            return None
        return num * 3.28084 if self.root.ids.selected_uom.text == 'imperial' else num


    '''
    Convert ft to miles or m to km.
    '''
    def shorten_dist_val(self, numval):
        if numval is None:
            return ""
        num = locale.atof(numval) if isinstance(numval, str) else numval
        return self.fmt_num(num / 5280.0, True) if self.root.ids.selected_uom.text == 'imperial' else self.fmt_num(num / 1000.0, True)


    '''
    Return selected distance unit of measure.
    '''
    def dist_unit(self):
        return "ft" if self.root.ids.selected_uom.text == 'imperial' else "m"


    '''
    Return selected distance unit of measure.
    '''
    def dist_unit_km(self):
        return "mi" if self.root.ids.selected_uom.text == 'imperial' else "km"


    '''
    Format number based on selected rounding option.
    '''
    def fmt_num(self, num, decimal=False):
        if num is None:
            return ""
        return locale.format_string("%.0f", num, grouping=True, monetary=False) if self.root.ids.selected_rounding.active and not decimal else locale.format_string("%.2f", num, grouping=True, monetary=False)


    '''
    Return specified speed in the proper Unit (metric vs imperial).
    '''
    def speed_val(self, num):
        if num is None:
            return None
        return num * 2.236936 if self.root.ids.selected_uom.text == 'imperial' else num * 3.6


    '''
    Return selected speed unit of measure.
    '''
    def speed_unit(self):
        return "mph" if self.root.ids.selected_uom.text == 'imperial' else "kph"


    '''
    Change Language (Preferences).
    '''
    def language_selection(self, item):
        menu_items = []
        for languageId in self.languages:
            menu_items.append({"text": self.languages.get(languageId), "on_release": lambda x=languageId: self.language_selection_callback(x)})
        self.language_selection_menu = MDDropdownMenu(caller = item, items = menu_items)
        self.language_selection_menu.open()
    def language_selection_callback(self, lang_id):
        self.root.ids.selected_language.text = self.languages.get(lang_id)
        self.language_selection_menu.dismiss()
        Config.set('preferences', 'language', lang_id)
        Config.write()
        self.show_info_message(message=_('reopen_app_for_changes_to_take_effect'))


    '''
    Dropdown selection with different drone models determined from the imported log files.
    Model names are slightly inconsistent based on the version of the Potensic app they were generated in.
    '''
    def model_selection(self, item):
        models = self.execute_db("SELECT modelref FROM models ORDER BY modelref")
        menu_items = []
        for modelRef in models:
            menu_items.append({"text": modelRef[0], "on_release": lambda x=modelRef[0]: self.model_selection_callback(x)})
        self.model_selection_menu = MDDropdownMenu(caller = item, items = menu_items)
        self.model_selection_menu.open()
    def model_selection_callback(self, text_item):
        self.select_drone_model(text_item)
        self.model_selection_menu.dismiss()
        self.stop_flight(True)
        self.list_log_files()


    def select_drone_model(self, model_name):
        self.root.ids.selected_model.text = model_name
        Config.set('preferences', 'selected_model', model_name)
        Config.write()


    '''
    Retrieve and display all flight logs imported to the app.
    '''
    def list_log_files(self):
        imports = self.execute_db("""
            SELECT i.importref, i.dateref, count(s.flight_number), sum(duration), max(duration), max(max_distance), max(max_altitude), max(max_h_speed), max(max_v_speed), sum(traveled)
            FROM imports i
            LEFT OUTER JOIN flight_stats s ON s.importref = i.importref
            WHERE modelref = ?
            GROUP BY i.importref, i.dateref
            ORDER BY i.dateref DESC
            """, (self.root.ids.selected_model.text,)
        )
        role = "medium" if self.is_desktop else "small"
        iconsize = [dp(40), dp(40)] if self.is_desktop else [dp(30), dp(30)]
        self.root.ids.log_files.clear_widgets()
        self.root.ids.log_files.add_widget(MDLabel(text=_('logs_date'), bold=True, max_lines=1, halign="left", valign="top", role=role, padding=[dp(24),0,0,0]))
        self.root.ids.log_files.add_widget(MDLabel(text=_('logs_number_flights'), bold=True, max_lines=1, halign="right", valign="top", role=role))
        self.root.ids.log_files.add_widget(MDLabel(text=_('logs_total_flown'), bold=True, max_lines=1, halign="right", valign="top", role=role))
        self.root.ids.log_files.add_widget(MDLabel(text=_('logs_total_time'), bold=True, max_lines=1, halign="right", valign="top", role=role))
        self.root.ids.log_files.add_widget(MDLabel(text=_('logs_maximum_distance'), bold=True, max_lines=1, halign="right", valign="top", role=role))
        self.root.ids.log_files.add_widget(MDLabel(text=_('logs_maximum_altitude'), bold=True, max_lines=1, halign="right", valign="top", role=role))
        self.root.ids.log_files.add_widget(MDLabel(text=_('logs_maximum_horizontal_speed'), bold=True, max_lines=1, halign="right", valign="top", role=role))
        self.root.ids.log_files.add_widget(MDLabel(text=_('logs_maximum_vertical_speed'), bold=True, max_lines=1, halign="right", valign="top", role=role))
        self.root.ids.log_files.add_widget(MDLabel(text="", bold=True))
        for importRef in imports:
            dt = datetime.date.fromisoformat(importRef[1]).strftime("%x")
            button1 = MDButton(MDButtonText(text=f"{dt}"), on_release=self.initiate_log_file, style="text", size_hint=(None, None))
            button1.value = importRef[0]
            self.root.ids.log_files.add_widget(button1)
            countVal = "" if importRef[3] is None else f"{importRef[2]}" # Check an aggregated field for None
            self.root.ids.log_files.add_widget(MDLabel(text=countVal, max_lines=1, halign="right", valign="top", role=role))
            durVal = "" if importRef[9] is None else f"{self.fmt_num(self.dist_val(importRef[9]))} {self.dist_unit()}"
            self.root.ids.log_files.add_widget(MDLabel(text=durVal, max_lines=1, halign="right", valign="top", role=role))
            durVal = "" if importRef[3] is None else f"{datetime.timedelta(seconds=importRef[3])}"
            self.root.ids.log_files.add_widget(MDLabel(text=durVal, max_lines=1, halign="right", valign="top", role=role))
            distVal = "" if importRef[4] is None else f"{self.fmt_num(self.dist_val(importRef[5]))} {self.dist_unit()}"
            self.root.ids.log_files.add_widget(MDLabel(text=distVal, max_lines=1, halign="right", valign="top", role=role))
            distVal = "" if importRef[5] is None else f"{self.fmt_num(self.dist_val(importRef[6]))} {self.dist_unit()}"
            self.root.ids.log_files.add_widget(MDLabel(text=distVal, max_lines=1, halign="right", valign="top", role=role))
            speedVal = "" if importRef[6] is None else f"{self.fmt_num(self.speed_val(importRef[7]))} {self.speed_unit()}"
            self.root.ids.log_files.add_widget(MDLabel(text=speedVal, max_lines=1, halign="right", valign="center", role=role))
            speedVal = "" if importRef[7] is None else f"{self.fmt_num(self.speed_val(importRef[8]))} {self.speed_unit()}"
            self.root.ids.log_files.add_widget(MDLabel(text=speedVal, max_lines=1, halign="right", valign="center", role=role))
            button2 = MDIconButton(style="standard", icon="delete", on_release=self.open_delete_log_dialog, size=iconsize)
            button2.value = importRef[0]
            self.root.ids.log_files.add_widget(button2)


    '''
    Called when a log file has been selected. It will be opened, parsed and displayed on the map screen.
    '''
    def initiate_log_file(self, buttonObj):
        self.dialog_wait.open()
        threading.Thread(target=self.select_log_file, args=(buttonObj.value,)).start()


    def select_log_file(self, importRef):
        lcDM = self.root.ids.selected_model.text.lower()
        self.map_rebuild_required = False
        mainthread(self.open_view)("Screen_Map")
        if ('p1a' in lcDM):
            self.parse_dreamer_logs(importRef)
        else:
            self.parse_atom_logs(importRef)
        mainthread(self.set_default_flight)()
        mainthread(self.generate_map_layers)()
        mainthread(self.select_flight)()
        self.dialog_wait.dismiss()


    def open_delete_log_dialog(self, buttonObj):
        okBtn = MDButton(MDButtonText(text=_('delete')), style="text", on_release=self.delete_log_file)
        okBtn.value = buttonObj.value
        self.dialog_delete = MDDialog(
            MDDialogHeadlineText(
                text = _('delete_file').format(filename=buttonObj.value),
                halign="left",
            ),
            MDDialogButtonContainer(
                Widget(),
                MDButton(MDButtonText(text=_('cancel')), style="text", on_release=self.close_delete_log_dialog),
                okBtn,
                spacing="8dp",
            ),
        )
        self.dialog_delete.open()


    def close_delete_log_dialog(self, *args):
        self.dialog_delete.dismiss()
        self.dialog_delete = None


    def delete_log_file(self, buttonObj):
        logFiles = self.execute_db("SELECT filename FROM log_files WHERE importref = ?", (buttonObj.value,))
        for fileRef in logFiles:
            file = fileRef[0]
            os.remove(os.path.join(self.logfileDir, file))
        modelRef = self.execute_db("SELECT modelref FROM imports WHERE importref = ?", (buttonObj.value,))
        self.execute_db("DELETE FROM flight_stats WHERE importref = ?", (buttonObj.value,))
        self.execute_db("DELETE FROM log_files WHERE importref = ?", (buttonObj.value,))
        self.execute_db("DELETE FROM imports WHERE importref = ?", (buttonObj.value,))
        if modelRef is not None and len(modelRef) > 0:
            importRef = self.execute_db("SELECT count (1) FROM imports WHERE modelref = ?", (modelRef[0][0],))
            if importRef is None or len(importRef) == 0 or importRef[0][0] == 0:
                self.execute_db("DELETE FROM models WHERE modelref = ?", (modelRef[0][0],))
                self.select_drone_model("--")
        self.list_log_files()
        self.close_delete_log_dialog(None)


    def open_backup_dialog(self):
        self.dialog_backup = MDDialog(
            MDDialogHeadlineText(
                text = _('backup_system_data'),
                halign="left",
            ),
            MDDialogButtonContainer(
                Widget(),
                MDButton(MDButtonText(text=_('cancel')), style="text", on_release=self.close_backup_dialog),
                MDButton(MDButtonText(text=_('backup')), style="text", on_release=self.backup_data),
                spacing="8dp",
            ),
        )
        self.dialog_backup.open()


    def close_backup_dialog(self, *args):
        self.dialog_backup.dismiss()
        self.dialog_backup = None


    def backup_data(self, buttonObj):
        self.close_backup_dialog(None)
        dtpart = re.sub("[^0-9]", "", datetime.datetime.now().isoformat())
        backupName = f"{self.appPathName}_{self.appVersion}_Backup_{dtpart}.zip"
        if self.is_android:
            cache_dir = user_cache_dir(self.appPathName, self.appPathName)
            zipFile = os.path.join(cache_dir, backupName)
            try:
                with ZipFile(zipFile, 'w') as zip:
                    zip.write(self.dbFile, os.path.basename(self.dbFile))
                    zip.write(self.configFile, os.path.basename(self.configFile))
                    for bin_file in self.get_dir_content(self.logfileDir):
                        zip.write(bin_file, os.path.basename(bin_file))
                url = self.shared_storage.copy_to_shared(zipFile)
                ShareSheet().share_file(url)
            except Exception as e:
                msg = _('error_saving_backup_zip').format(filename=zipFile, error=e)
                print(msg)
                self.show_error_message(message=msg)
        elif self.is_ios:
            zipFile = os.path.join(self.ios_doc_path(), backupName)
            try:
                with ZipFile(zipFile, 'w') as zip:
                    zip.write(self.dbFile, os.path.basename(self.dbFile))
                    zip.write(self.configFile, os.path.basename(self.configFile))
                    for bin_file in self.get_dir_content(self.logfileDir):
                        zip.write(bin_file, os.path.basename(bin_file))
            except Exception as e:
                msg = _('error_saving_backup_zip').format(filename=zipFile, error=e)
                print(msg)
                self.show_error_message(message=msg)
        else:
            oldwd = os.getcwd() # Remember current workdir. Windows File Explorer is nasty and changes it, causing all sorts of mapview issues.
            myFiles = filechooser.choose_dir(title=_('save_backup_file'))
            newwd = os.getcwd()
            if oldwd != newwd:
                os.chdir(oldwd) # Change it back!
            if myFiles and len(myFiles) > 0 and os.path.isdir(myFiles[0]):
                zipFile = os.path.join(myFiles[0], backupName)
                try:
                    with ZipFile(zipFile, 'w') as zip:
                        zip.write(self.dbFile, os.path.basename(self.dbFile))
                        zip.write(self.configFile, os.path.basename(self.configFile))
                        for bin_file in self.get_dir_content(self.logfileDir):
                            zip.write(bin_file, os.path.basename(bin_file))
                except Exception as e:
                    msg = _('error_saving_backup_zip').format(filename=zipFile, error=e)
                    print(msg)
                    self.show_error_message(message=msg)


    def get_dir_content(self, directory):
        file_paths = [] 
        for root, directories, files in os.walk(directory):
            for filename in files:
                filepath = os.path.join(root, filename)
                file_paths.append(filepath)
        return file_paths


    def open_restore_dialog(self):
        self.dialog_restore = MDDialog(
            MDDialogHeadlineText(
                text = _('restore_system_data'),
                halign="left",
            ),
            MDDialogButtonContainer(
                Widget(),
                MDButton(MDButtonText(text=_('cancel')), style="text", on_release=self.close_restore_dialog),
                MDButton(MDButtonText(text=_('restore')), style="text", on_release=self.open_restore_file_dialog),
                spacing="8dp",
            ),
        )
        self.dialog_restore.open()


    def close_restore_dialog(self, *args):
        self.dialog_restore.dismiss()
        self.dialog_restore = None


    def open_restore_file_dialog(self, buttonObj):
        self.close_restore_dialog(None)
        if self.is_android:
            # Open Android Shared Storage.
            self.chosenFile = None
            self.chooser.choose_content("application/zip")
            self.chooser_open = True
            while (self.chooser_open):
                time.sleep(0.2)
            if self.chosenFile is not None:
                self.restore_data(self.chosenFile)
        elif self.is_ios:
            gotFile = False
            # Restore from the most recent backup file, if there are multiple.
            for zipFile in sorted(glob.glob(os.path.join(self.ios_doc_path(), '*.zip'), recursive=False), reverse=True):
                if "_Backup_" in os.path.basename(zipFile): # Ignore zip files that are not backups.
                    self.restore_data(zipFile)
                    gotFile = True
                    break
            if not gotFile:
                self.show_warning_message(message=_('nothing_to_import'))
        else:
            oldwd = os.getcwd() # Remember current workdir. Windows File Explorer is nasty and changes it, causing all sorts of mapview issues.
            myFiles = filechooser.open_file(title=_('select_backup_zip_file'), filters=[(_('zip_files'), "*.zip")], mime_type="zip")
            newwd = os.getcwd()
            if oldwd != newwd:
                os.chdir(oldwd) # Change it back!
            if myFiles and len(myFiles) > 0 and os.path.isfile(myFiles[0]):
                self.restore_data(myFiles[0])


    '''
    Restore data from a backup file.
    '''
    def restore_data(self, selectedFile):
        if not os.path.isfile(selectedFile):
            self.show_error_message(message=_('not_valid_backup_file_specified').format(filename=selectedFile))
            return
        resDir = os.path.join(tempfile.gettempdir(), "restoredata")
        shutil.rmtree(resDir, ignore_errors=True) # Delete old temp files if they were missed before.
        with ZipFile(selectedFile, 'r') as unzip:
            unzip.extractall(path=resDir)
        oldDbFile = os.path.join(resDir, self.dbFilename)
        oldCfFile = os.path.join(resDir, self.configFilename)
        if os.path.isfile(oldDbFile) and os.path.isfile(oldCfFile):
            for binFile in glob.glob(os.path.join(resDir, '**/*'), recursive=True):
                binBaseName = os.path.basename(binFile)
                if binBaseName == self.dbFilename:
                    shutil.copy(binFile, self.dbFile)
                elif binBaseName == self.configFilename:
                    shutil.copy(binFile, self.configFile)
                else:
                    shutil.copy(binFile, os.path.join(self.logfileDir, binBaseName))
            self.show_info_message(message=_('restored_from').format(filename=selectedFile))
            Config.read(self.configFile)
            self.init_prefs()
            self.reset()
        else:
            self.show_error_message(message=_('not_valid_backup_zip_file_specified').format(filename=selectedFile))
        shutil.rmtree(resDir, ignore_errors=True) # Delete temp files.


    '''
    Called when map screen is closed.
    '''
    def close_pref_screen(self):
        if self.app_view == "map":
            self.open_view("Screen_Map")
        elif self.app_view == "sum":
            self.open_view("Screen_Day_Summary")
        elif self.app_view == "log":
            self.open_view("Screen_Log_Files")


    '''
    Run a SQL command and return results.
    '''
    def execute_db(self, expression, params=None):
        con = sqlite3.connect(self.dbFile)
        cur = con.cursor()
        if (params):
            cur.execute(expression, params)
        else:
            cur.execute(expression)
        results = cur.fetchall()
        con.commit()
        con.close()
        return results


    '''
    Create the DB and schema.
    '''
    def init_db(self):
        self.execute_db("""
            CREATE TABLE IF NOT EXISTS models(
                modelref TEXT PRIMARY KEY
            )
        """)
        self.execute_db("""
            CREATE TABLE IF NOT EXISTS imports(
                importref TEXT PRIMARY KEY,
                modelref TEXT NOT NULL,
                dateref TEXT NOT NULL,
                importedon TEXT NOT NULL,
                FOREIGN KEY (modelref) REFERENCES models(modelref) ON DELETE CASCADE ON UPDATE NO ACTION
            )
        """)
        self.execute_db("""
            CREATE TABLE IF NOT EXISTS log_files(
                filename TEXT PRIMARY KEY,
                importref TEXT NOT NULL,
                bintype TEXT NOT NULL,
                FOREIGN KEY (importref) REFERENCES imports(importref) ON DELETE CASCADE ON UPDATE NO ACTION
            )
        """)
        self.execute_db("""
            CREATE TABLE IF NOT EXISTS flight_stats(
                importref TEXT NOT NULL,
                flight_number INTEGER NOT NULL,
                duration INTEGER NOT NULL,
                max_distance REAL NOT NULL,
                max_altitude REAL NOT NULL,
                max_h_speed REAL NOT NULL,
                max_v_speed REAL NOT NULL,
                traveled REAL NOT NULL,
                FOREIGN KEY (importref) REFERENCES imports(importref) ON DELETE CASCADE ON UPDATE NO ACTION
            )
        """)
        self.execute_db("CREATE INDEX IF NOT EXISTS flight_stats_index ON flight_stats(importref)")


    '''
    Read from config (ini) file.
    '''
    def init_prefs(self):
        self.root.ids.selected_uom.text = Config.get('preferences', 'unit_of_measure')
        self.root.ids.selected_home_marker.active = Config.getboolean('preferences', 'show_marker_home')
        self.root.ids.selected_ctrl_marker.active = Config.getboolean('preferences', 'show_marker_ctrl')
        self.root.ids.selected_flight_path_width.value = Config.get('preferences', 'flight_path_width')
        self.root.ids.selected_flight_path_color.value = Config.getint('preferences', 'flight_path_color')
        self.root.ids.selected_marker_drone_color.value = Config.getint('preferences', 'marker_drone_color')
        self.root.ids.selected_marker_ctrl_color.value = Config.getint('preferences', 'marker_ctrl_color')
        self.root.ids.selected_marker_home_color.value = Config.getint('preferences', 'marker_home_color')
        self.root.ids.selected_rounding.active = Config.getboolean('preferences', 'rounded_readings')
        self.root.ids.selected_gauges.active = Config.getboolean('preferences', 'gauges')
        self.root.ids.selected_statusicons.active = Config.getboolean('preferences', 'statusicons')
        self.root.ids.selected_mapsource.text = Config.get('preferences', 'map_tile_server')
        self.root.ids.selected_refresh_rate.text = Config.get('preferences', 'refresh_rate')
        self.root.ids.selected_model.text = Config.get('preferences', 'selected_model')
        self.root.ids.selected_language.text = self.languages.get(Config.get('preferences', 'language'))


    '''
    Reset the application as it were before opening a file.
    '''
    def reset(self):
        self.centerlat = 51.50722
        self.centerlon = -0.1275
        self.playback_speed = 1
        self.map_rebuild_required = True
        if self.root:
            self.title = self.appTitle
            self.root.ids.selected_path.text = '--'
            self.zoom = self.defaultMapZoom
            self.clear_map()
            self.root.ids.value_date.text = ""
            self.root.ids.value_maxdist.text = ""
            self.root.ids.value_maxdist_short.text = ""
            self.root.ids.value_maxalt.text = ""
            self.root.ids.value_maxhspeed.text = ""
            self.root.ids.value_duration.text = ""
            self.root.ids.value_tottraveled.text = ""
            self.root.ids.value_tottraveled_short.text = ""
            self.root.ids.value1_alt.text = ""
            self.root.ids.value1_traveled.text = ""
            self.root.ids.value1_traveled_short.text = ""
            self.root.ids.value1_rth_desc.text = "" # rob
            self.root.ids.value1_batterylevel.text = "" # rob
            self.root.ids.value1_flightmode.text = ""   # rob
            self.root.ids.value1_dist.text = ""
            self.root.ids.value1_dist_short.text = ""
            self.root.ids.value1_hspeed.text = ""
            self.root.ids.value1_vspeed.text = ""
            self.root.ids.value1_elapsed.text = ""
            #self.root.ids.map_metrics1.text = ""
            self.root.ids.map_metrics2.text = ""
            self.root.ids.flight_progress.is_updating = True
            self.root.ids.flight_progress.value = 0
            self.root.ids.flight_progress.is_updating = False
            self.root.ids.flight_stats_grid.clear_widgets()
            self.root.ids.speed_indicator.icon = f"numeric-{self.playback_speed}-box"
        self.flightOptions = []
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
            self.root.ids.screen_manager.current = "Screen_Log_Files"
            self.center_map()


    '''
    Delete unreferenced log files. Delete unreferenced DB records.
    '''
    def cleanup_orphaned_refs(self):
        importedFiles = []
        for fileRef in self.execute_db("SELECT filename FROM log_files"):
            importedFiles.append(fileRef[0])
        filesOnDisk = []
        for binFile in glob.glob(os.path.join(self.logfileDir, '*'), recursive=False):
            binBasename = os.path.basename(binFile)
            if binBasename in importedFiles:
                filesOnDisk.append(binBasename)
            else:
                print(f"Deleting unreferenced file {binBasename}")
                os.remove(binFile)
        for importedFile in importedFiles:
            if importedFile not in filesOnDisk:
                print(f"Deleting orphaned reference to {importedFile}")
                importRefRecs = self.execute_db("SELECT importref FROM log_files WHERE filename = ?", (importedFile,))
                importRef = importRefRecs[0][0] if importRefRecs is not None and len(importRefRecs) > 0 else None
                if importRef is not None:
                    logFiles = self.execute_db("SELECT filename FROM log_files WHERE importref = ?", (importRef,))
                    for fileRef in logFiles:
                        file = fileRef[0]
                        try:
                            os.remove(os.path.join(self.logfileDir, file))
                        except:
                            # Do nothing.
                            ...
                    modelRef = self.execute_db("SELECT modelref FROM imports WHERE importref = ?", (importRef,))
                    self.execute_db("DELETE FROM flight_stats WHERE importref = ?", (importRef,))
                    self.execute_db("DELETE FROM log_files WHERE importref = ?", (importRef,))
                    self.execute_db("DELETE FROM imports WHERE importref = ?", (importRef,))
                    if modelRef is not None and len(modelRef) > 0:
                        importRef = self.execute_db("SELECT count (1) FROM imports WHERE modelref = ?", (modelRef[0][0],))
                        if importRef is None or len(importRef) == 0 or importRef[0][0] == 0:
                            self.execute_db("DELETE FROM models WHERE modelref = ?", (modelRef[0][0],))
                else:
                    self.execute_db("DELETE FROM log_files WHERE filename = ?", (importedFile,))


    '''
    Show info/warning/error messages.
    '''
    @mainthread
    def show_info_message(self, message: str):
        MDSnackbar(MDSnackbarText(text=message), y=dp(24), pos_hint={"center_x": 0.5}, size_hint_x=0.8).open()
    @mainthread
    def show_warning_message(self, message: str):
        MDSnackbar(MDSnackbarText(text=message), y=dp(24), pos_hint={"center_x": 0.5}, size_hint_x=0.8).open()
    @mainthread
    def show_error_message(self, message: str):
        MDSnackbar(MDSnackbarText(text=message), y=dp(24), pos_hint={"center_x": 0.5}, size_hint_x=0.8).open()


    '''
    Close the spash screen.
    '''
    def remove_splash_image(self, dt):
        self.root_window.remove_widget(self.splash_img)
        self.root_window.remove_widget(self.splash_ver)


    '''
    Open help page on the project home page and for the matching version of the app.
    '''
    def show_help(self):
        #webbrowser.open(f"https://github.com/koen-aerts/potdroneflightparser/tree/{self.appVersion}")
        webbrowser.open("https://github.com/koen-aerts/potdroneflightparser/blob/Chris_2_2_3/help/guide.md")


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
        self.is_ios = platform == 'ios'
        self.is_android = platform == 'android'
        self.is_windows = platform == 'win'
        self.is_desktop = self.is_windows or platform in ('linux', 'macosx')
        self.title = self.appTitle
        self.dataDir = os.path.join(self.ios_doc_path(), '.data') if self.is_ios else user_data_dir(self.appPathName, self.appPathName)
        self.logfileDir = os.path.join(self.dataDir, "logfiles") # Place where log bin files go.
        if not os.path.exists(self.logfileDir):
            Path(self.logfileDir).mkdir(parents=True, exist_ok=True)
        self.dbFile = os.path.join(self.dataDir, self.dbFilename) # sqlite DB file.
        self.init_db()
        configDir = self.dataDir if self.is_ios else user_config_dir(self.appPathName, self.appPathName) # Place where app ini config file goes.
        if not os.path.exists(configDir):
            Path(configDir).mkdir(parents=True, exist_ok=True)
        self.configFile = os.path.join(configDir, self.configFilename) # ini config file.
        if self.is_android:
            request_permissions([Permission.INTERNET, Permission.WRITE_EXTERNAL_STORAGE, Permission.READ_EXTERNAL_STORAGE])
            self.shared_storage = SharedStorage()
            self.chosenFile = None
            self.chooser_open = False # To track Android File Manager (Chooser)
            self.chooser = Chooser(self.import_android_chooser_callback)
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
            'map_tile_server': SelectableTileServer.OPENSTREETMAP.value,
            'selected_model': '--',
            'language': 'en_US',
            'gauges': True,
            'statusicons': True
        })
        langcode = Config.get('preferences', 'language')
        langpath = os.path.join(os.path.dirname(__file__), 'languages')
        lang = gettext.translation('messages', localedir=langpath, languages=[langcode])
        try:
            locale.setlocale(locale.LC_ALL, langcode)
        except:
            print(f"Using fallback locale. Unsupported: {langcode}")
            locale.setlocale(locale.LC_ALL, '') # Fallback
        lang.install()
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
        self.dialog_wait = MDDialog(
            MDDialogHeadlineText(
                text=_('parsing_log_file')
            ),
            MDDialogContentContainer(
                MDCircularProgressIndicator(
                    size_hint = (None, None),
                    pos_hint = {"center_x": 0.5, "center_y": 0.5},
                    size = [dp(48), dp(48)]
                ),
                orientation="vertical"
            )
        )
        self.dialog_wait.auto_dismiss = False
        self.cleanup_orphaned_refs()


    def build(self):
        self.icon = 'assets/app-icon256.png'
        self.init_prefs()


    def on_start(self):
        if self.is_desktop:
            self.splash_img = Image(source="assets/splash1_alt1.png", fit_mode="scale-down")
            self.splash_ver = Label(text=f"{self.appVersion}", pos_hint={"center_x": .5, "center_y": .25}, font_size=dp(50))
            self.root_window.add_widget(self.splash_img)
            self.root_window.add_widget(self.splash_ver)
            Clock.schedule_once(self.remove_splash_image, 5)
        self.root.ids.selected_path.text = '--'
        self.reset()
        self.select_map_source()
        self.list_log_files()
        self.app_view = "log"
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


'''
Distance Gauge
'''    
class DistGauge(Widget):
    display_unit = StringProperty("")
    unit = NumericProperty(1.8)
    value = BoundedNumericProperty(0, min=0, max=99000, errorvalue=0)
    file_gauge = StringProperty("assets/Distance_Background.png")
    file_needle_long = StringProperty("assets/LongNeedleAltimeter1a.png")
    file_needle_short = StringProperty("assets/SmallNeedleAltimeter1a.png")
    size_gauge = dp(180)

    def __init__(self, **kwargs):
        super(DistGauge, self).__init__(**kwargs)
        self._gauge = Scatter(
            size=(self.size_gauge, self.size_gauge),
            do_rotation=False,
            do_scale=False,
            do_translation=False
        )
        _img_gauge = Image(
            source=self.file_gauge,
            size=(self.size_gauge, self.size_gauge)
        )
        self._needleL = Scatter(
            size=(self.size_gauge, self.size_gauge),
            do_rotation=False,
            do_scale=False,
            do_translation=False
        )
        self._needleS = Scatter(
            size=(self.size_gauge, self.size_gauge),
            do_rotation=False,
            do_scale=False,
            do_translation=False
        )
        _img_needle_short = Image(
            source=self.file_needle_short,
            size=(self.size_gauge, self.size_gauge)
        )
        _img_needle_long = Image(
            source=self.file_needle_long,
            size=(self.size_gauge, self.size_gauge)
        )
        self._glab = Label(font_size=dp(14), markup=True, color=[0.41, 0.42, 0.74, 1])
        self._glab2 = Label(font_size=dp(12), markup=True, color=[1, 1, 1, 1])
        self._gauge.add_widget(_img_gauge)
        self._needleS.add_widget(_img_needle_short)
        self._needleL.add_widget(_img_needle_long)
        self.add_widget(self._gauge)
        self.add_widget(self._needleS)
        self.add_widget(self._needleL)
        self.add_widget(self._glab)
        self.add_widget(self._glab2)
        self.bind(pos=self._update)
        self.bind(size=self._update)
        self.bind(value=self._turn)

    def _update(self, *args): # Update gauge and needle positions after sizing or positioning.
        self._gauge.pos = self.pos
        self._needleL.pos = (self.x, self.y)
        self._needleL.center = self._gauge.center
        self._needleS.pos = (self.x, self.y)
        self._needleS.center = self._gauge.center
        self._glab.center_x = self._gauge.center_x - dp(28)
        self._glab.center_y = self._gauge.center_y + dp(1)
        self._glab2.center_x = self._gauge.center_x
        self._glab2.center_y = self._gauge.center_y - dp(20)

    def _turn(self, *args): # Turn needle
        self._needleS.center_x = self._gauge.center_x
        self._needleS.center_y = self._gauge.center_y
        self._needleS.rotation = ((1 * self.unit) - (self.value * self.unit * 2)/10)
        self._needleL.center_x = self._gauge.center_x
        self._needleL.center_y = self._gauge.center_y
        self._needleL.rotation = (1 * self.unit) - (self.value * self.unit * 2)        
        self._glab.text = "[b]{0:04d}[/b]".format(self.value)
        self._glab2.text = self.display_unit


'''
Altitude Gauge
'''
class AltGauge(Widget):
    display_unit = StringProperty("")
    unit = NumericProperty(1.8)
    value = BoundedNumericProperty(0, min=0, max=8000, errorvalue=0)
    file_gauge = StringProperty("assets/Altimeter_Background2.png")
    file_needle_long = StringProperty("assets/LongNeedleAltimeter1a.png")
    file_needle_short = StringProperty("assets/SmallNeedleAltimeter1a.png")
    size_gauge = dp(180)
    size_text = NumericProperty(10)

    def __init__(self, **kwargs):
        super(AltGauge, self).__init__(**kwargs)
        self._gauge = Scatter(
            size=(self.size_gauge, self.size_gauge),
            do_rotation=False,
            do_scale=False,
            do_translation=False
        )
        _img_gauge = Image(
            source=self.file_gauge,
            size=(self.size_gauge, self.size_gauge)
        )
        self._needleL = Scatter(
            size=(self.size_gauge, self.size_gauge),
            do_rotation=False,
            do_scale=False,
            do_translation=False
        )
        self._needleS = Scatter(
            size=(self.size_gauge, self.size_gauge),
            do_rotation=False,
            do_scale=False,
            do_translation=False
        )        
        _img_needle_short = Image(
            source=self.file_needle_short,
            size=(self.size_gauge, self.size_gauge)
        )
        _img_needle_long = Image(
            source=self.file_needle_long,
            size=(self.size_gauge, self.size_gauge)
        )
        self._glab = Label(font_size=dp(14), markup=True, color=[0.41, 0.42, 0.74, 1])
        self._glab2 = Label(font_size=dp(12), markup=True, color=[1, 1, 1, 1])
        self._gauge.add_widget(_img_gauge)
        self._needleS.add_widget(_img_needle_short)
        self._needleL.add_widget(_img_needle_long)
        self.add_widget(self._gauge)
        self.add_widget(self._needleS)
        self.add_widget(self._needleL)
        self.add_widget(self._glab)
        self.add_widget(self._glab2)
        self.bind(pos=self._update)
        self.bind(size=self._update)
        self.bind(value=self._turn)
        self.bind(display_unit=self._turn)

    def _update(self, *args): # Update gauge and needle positions after sizing or positioning.
        self._gauge.pos = self.pos
        self._needleL.pos = (self.x, self.y)
        self._needleL.center = self._gauge.center
        self._needleS.pos = (self.x, self.y)
        self._needleS.center = self._gauge.center
        self._glab.center_x = self._gauge.center_x - dp(28)
        self._glab.center_y = self._gauge.center_y + dp(1)
        self._glab2.center_x = self._gauge.center_x
        self._glab2.center_y = self._gauge.center_y - dp(20)

    def _turn(self, *args): # Turn needle
        self._needleS.center_x = self._gauge.center_x
        self._needleS.center_y = self._gauge.center_y
        self._needleS.rotation = ((1 * self.unit) - (self.value * self.unit * 2)/10)
        self._needleL.center_x = self._gauge.center_x
        self._needleL.center_y = self._gauge.center_y
        self._needleL.rotation = (1 * self.unit) - (self.value * self.unit * 2)        
        self._glab.text = "[b]{0:04d}[/b]".format(self.value)
        self._glab2.text = self.display_unit


'''
Horizontal Speed Gauge
'''
class HGauge(Widget):
    display_unit = StringProperty("")
    unit = NumericProperty(1.8)
    value = BoundedNumericProperty(0, min=-400, max=400, errorvalue=0)
    file_gauge = StringProperty("assets/AirSpeedIndicator_Background_H.png")
    file_needle = StringProperty("assets/needle.png")
    size_gauge = dp(180)
    size_text = NumericProperty(10)

    def __init__(self, **kwargs):
        super(HGauge, self).__init__(**kwargs)
        self._gauge = Scatter(
            size=(self.size_gauge, self.size_gauge),
            do_rotation=False,
            do_scale=False,
            do_translation=False
        )
        _img_gauge = Image(
            source=self.file_gauge,
            size=(self.size_gauge, self.size_gauge)
        )
        self._needle = Scatter(
            size=(self.size_gauge, self.size_gauge),
            do_rotation=False,
            do_scale=False,
            do_translation=False
        )
        _img_needle = Image(
            source=self.file_needle,
            size=(self.size_gauge, self.size_gauge)
        )
        self._glab = Label(font_size=dp(14), markup=True)
        self._glab2 = Label(font_size=dp(12), markup=True, color=[1, 1, 1, 1])
        self._gauge.add_widget(_img_gauge)
        self._needle.add_widget(_img_needle)
        self.add_widget(self._gauge)
        self.add_widget(self._needle)
        self.add_widget(self._glab2)
        self.bind(pos=self._update)
        self.bind(size=self._update)
        self.bind(value=self._turn)

    def _update(self, *args): # Update gauge and needle positions after sizing or positioning.
        self._gauge.pos = self.pos
        self._needle.pos = (self.x, self.y)
        self._needle.center = self._gauge.center
        self._glab.center_x = self._gauge.center_x
        self._glab.center_y = self._gauge.center_y
        self._glab2.center_x = self._gauge.center_x
        self._glab2.center_y = self._gauge.center_y - dp(20)

    def _turn(self, *args): # Turn needle
        self._needle.center_x = self._gauge.center_x
        self._needle.center_y = self._gauge.center_y
        self._needle.rotation = (100 * self.unit) - (self.value * self.unit * 4)
        self._glab2.text = self.display_unit


'''
Vertical Speed Gauge
'''
class VGauge(Widget):
    display_unit = StringProperty("")
    unit = NumericProperty(1.8)
    value = BoundedNumericProperty(0, min=-10, max=400, errorvalue=0)
    file_gauge = StringProperty("assets/AirSpeedIndicator_Background_V.png")
    file_needle = StringProperty("assets/needle.png")
    size_gauge = dp(180)
    size_text = NumericProperty(10)

    def __init__(self, **kwargs):
        super(VGauge, self).__init__(**kwargs)
        self._gauge = Scatter(
            size=(self.size_gauge, self.size_gauge),
            do_rotation=False,
            do_scale=False,
            do_translation=False
        )
        _img_gauge = Image(
            source=self.file_gauge,
            size=(self.size_gauge, self.size_gauge)
        )
        self._needle = Scatter(
            size=(self.size_gauge, self.size_gauge),
            do_rotation=False,
            do_scale=False,
            do_translation=False
        )
        _img_needle = Image(
            source=self.file_needle,
            size=(self.size_gauge, self.size_gauge)
        )
        self._glab = Label(font_size=dp(14), markup=True)
        self._glab2 = Label(font_size=dp(12), markup=True, color=[1, 1, 1, 1])
        self._gauge.add_widget(_img_gauge)
        self._needle.add_widget(_img_needle)
        self.add_widget(self._gauge)
        self.add_widget(self._needle)
        self.add_widget(self._glab2)
        self.bind(pos=self._update)
        self.bind(size=self._update)
        self.bind(value=self._turn)

    def _update(self, *args): # Update gauge and needle positions after sizing or positioning.
        self._gauge.pos = self.pos
        self._needle.pos = (self.x, self.y)
        self._needle.center = self._gauge.center
        self._glab.center_x = self._gauge.center_x
        self._glab.center_y = self._gauge.center_y
        self._glab2.center_x = self._gauge.center_x
        self._glab2.center_y = self._gauge.center_y - dp(20)

    def _turn(self, *args): # Turn needle
        self._needle.center_x = self._gauge.center_x
        self._needle.center_y = self._gauge.center_y
        #self._needle.rotation = (100 * self.unit) - (self.value * self.unit * 20)
        self._needle.rotation = -(self.value * self.unit * 10)
        self._glab2.text = self.display_unit


'''
Heading Gauge (direction drone is travelling as opposed to direction drone is looking)
'''
class HeadingGauge(Widget):
    unit = NumericProperty(1.8)
    value = BoundedNumericProperty(0, min=0, max=400, errorvalue=0)
    drotation = BoundedNumericProperty(0, min=0, max=400, errorvalue=0) #Rotational position of drone
    file_gauge = StringProperty("assets/HeadingIndicator_Background1.png")
    file_heading_ring = StringProperty("assets/HeadingRing.png")
    file_heading_aircraft = StringProperty("assets/Heading_drone3a.png")  #HeadingIndicator_Aircraft1c.png
    size_gauge = dp(180)
    size_text = NumericProperty(10)

    def __init__(self, **kwargs):
        super(HeadingGauge, self).__init__(**kwargs)
        self._gauge = Scatter(
            size=(self.size_gauge, self.size_gauge),
            do_rotation=False,
            do_scale=False,
            do_translation=False
        )
        _img_gauge = Image(
            source=self.file_gauge,
            size=(self.size_gauge, self.size_gauge)
        )
        self._headingR = Scatter(
            size=(self.size_gauge, self.size_gauge),
            do_rotation=False,
            do_scale=False,
            do_translation=False
        )
        self._aircrafT = Scatter(
            size=(self.size_gauge, self.size_gauge),
            do_rotation=False,
            do_scale=False,
            do_translation=False
        )
        _img_aircraft = Image(
            source=self.file_heading_aircraft,
            size=(self.size_gauge, self.size_gauge)
        )
        _img_heading_ring = Image(
            source=self.file_heading_ring,
            size=(self.size_gauge, self.size_gauge)
        )
        self._gauge.add_widget(_img_gauge)
        self._headingR.add_widget(_img_heading_ring)
        self._aircrafT.add_widget(_img_aircraft)
        self.add_widget(self._gauge)
        self.add_widget(self._headingR)
        self.add_widget(self._aircrafT)        
        self.bind(pos=self._update)
        self.bind(size=self._update)
        self.bind(value=self._turn)

    def _update(self, *args): # Update positioning.
        self._gauge.pos = self.pos
        self._headingR.pos = (self.x, self.y)
        self._headingR.center = self._gauge.center
        self._aircrafT.pos = (self.x, self.y)

    def _turn(self, *args): # Turn
        self._headingR.center_x = self._gauge.center_x
        self._headingR.center_y = self._gauge.center_y
        self._headingR.rotation = (1 * self.unit) + (self.value * 1)
        self._aircrafT.center_y = self._gauge.center_y
        self._aircrafT.rotation = (1 * self.unit) + (self.drotation * 1)


class ProgressSlider(BoxLayout):
    def __init__(self, **kwargs):
        super(ProgressSlider, self).__init__(**kwargs)
        self.orientation = 'vertical'  
        self.slider = Slider(min=0, max=100, value=0, size_hint=(1.8, None))
        self.slider.bind(value=self.on_progress_slider_value_change)
        #self.slider.observe(self.on_value_change, names='value')
        self.slider.cursor_image = 'assets/slider3.png'
        self.slider.track_active_color = (1, 0, 0, 1)
        self.slider.track_inactive_color: "#aaaaaa"
        self.slider.track_active_color: "#444444"
        self.slider.background_normal = ''
        self.slider.cursor_color = (1, 0, 0, 1)
        self.add_widget(self.slider)

    def on_progress_slider_value_change(self, instance, value):
        MDApp.get_running_app().on_progress_slider_value_change(instance, value)  

    def on_touch_move(self, touch):
        if self.collide_point(touch.x, touch.y):
            #print("Touch down on the slider!")
            play_button = MDApp.get_running_app().root.ids['playbutton']
            icon_name = play_button.icon
            if icon_name == "play":
                return
            else:
                play_button.trigger_action(duration=0.1)

    def on_value_throttled(self, instance, value):
        print(f"Value throttled: {value}")

    def on_value(self, instance, value):
        print(f"Slider value changed to {value}")

    def update_value(self, new_value):
        if new_value < self.slider.min:
            self.value = self.min
        elif new_value > self.slider.max:
            self.slider.value = self.slider.max
        else:
            self.slider.value = new_value


"""  
Linearly interpolate between two points (x0, y0) and (x1, y1) to generate num_points values.  
Future for smoothing operation of gauges based on capability of threading.

Args:  
    x0 (float): x-coordinate of the first point  
    y0 (float): y-coordinate of the first point  
    x1 (float): x-coordinate of the second point  
    y1 (float): y-coordinate of the second point  
    num_points (int): number of points to generate  

Returns:  
    list of tuples: [(x, y) for each interpolated point]  
"""  
def linear_interpolation(x0, y0, x1, y1, num_points):
    x_values = []
    y_values = []
    for i in range(num_points):
        t = i / (num_points - 1)  # interpolation parameter
        x = x0 + t * (x1 - x0)
        y = y0 + t * (y1 - y0)
        x_values.append(x)
        y_values.append(y)
    return list(zip(x_values, y_values))


if __name__ == "__main__":
    MainApp().run()