import glob
import os
import sys
import shutil
import struct
import tempfile
import re
import datetime
import threading
import time
import math

import tkinter as tk
from tkinter import ttk
from tkinter import filedialog
from tkinter import font
from tkinter import Menu
from tkinter.messagebox import showinfo, showwarning, showerror
from tkinter.font import nametofont

import tkintermapview

from pathlib import Path, PurePath
from zipfile import ZipFile


class ExtractFlightData(tk.Tk):


  '''
  Global variables and constants.
  '''
  version = "v1.0.3"
  defaultDroneZoom = 14
  defaultBlankMapZoom = 1
  ctrlMarkerColor1 = "#5b96f7"
  ctrlMarkerColor2 = "#aaccf6"
  homeMarkerColor1 = "#9B261E"
  homeMarkerColor2 = "#C5542D"
  droneMarkerColor1 = "#f59e00"
  droneMarkerColor2 = "#c6dfb3"
  displayMode = "ATOM"
  columns = ('timestamp','altitude1','altitude2','distance1','dist1lat','dist1lon','distance2','dist2lat','dist2lon','distance3','speed1','speed1lat','speed1lon','speed2','speed2lat','speed2lon','speed1vert','speed2vert','satellites','ctrllat','ctrllon','homelat','homelon','dronelat','dronelon','rssi','channel','flightctrlconnected','remoteconnected')
  showColsAtom = ('timestamp','altitude2','distance3','speed2','satellites','ctrllat','ctrllon','homelat','homelon','dronelat','dronelon','rssi','flightctrlconnected')
  showColsDreamer = ('timestamp','altitude1','distance1','satellites','homelat','homelon','dronelat','dronelon')
  zipFilename = None
  tree = None
  map_widget = None
  selectPlaySpeeds = None
  flightPaths = None
  pathCoords = None
  flightStarts = None
  ctrlmarker = None
  homemarker = None
  dronemarker = None
  ctrllabel = None
  homelabel = None
  dronelabel = None
  isPlaying = False
  currentRow = None
  labelFlight = None
  selectedTile = None
  selectPath = None
  selectedPath = None
  showMarkerCtrl = None
  showMarkerHome = None
  showPath = None
  showAll = None
  labelFile = None


  '''
  Update ctrl/home/drone markers on the map with the next set of coordinates in the table list.
  '''
  def setFrame(self):
    while self.isPlaying and self.currentRow != None:
      self.tree.see(self.currentRow)
      self.tree.selection_set(self.currentRow)
      self.setMarkers(self.currentRow)
      speed = self.selectPlaySpeeds.get() # skip frames to play faster.
      skipFrames = 1
      pause = False
      if (speed == 'Real-Time'):
        pause = True
      elif (speed != 'Fast'):
        skipFrames = int(re.sub("[^0-9]", "", speed))
      rows = self.tree.get_children()
      oldIdx = self.tree.index(self.currentRow)
      nextIdx = oldIdx + skipFrames
      if (len(rows) > nextIdx+1):
        nextRow = rows[nextIdx]
        if (pause):
          diff = self.getDatetime(self.tree.item(nextRow)['values'][self.columns.index('timestamp')]) - self.getDatetime(self.tree.item(self.currentRow)['values'][self.columns.index('timestamp')])
          seconds = diff.total_seconds()/1000;
          if (seconds > 1):
            seconds = 1
          time.sleep(seconds)
        self.currentRow = nextRow
      else:
        self.currentRow = None
        self.isPlaying = False
    self.currentRow = None
    self.isPlaying = False


  '''
  Start flight playback.
  '''
  def play(self):
    if (self.isPlaying):
      return
    self.currentRow = None
    allRows = self.tree.get_children()
    if (len(allRows) == 0):
      return
    selectedRows = self.tree.selection()
    self.currentRow = allRows[0] if len(selectedRows) == 0 else selectedRows[0]
    self.isPlaying = True;
    threading.Thread(target=self.setFrame, args=()).start()


  '''
  Stop flight playback.
  '''
  def stop(self):
    self.isPlaying = False;


  '''
  Reset the application as it were before opening a file.
  '''
  def reset(self):
    self.ctrllabel = 'Ctrl'
    self.homelabel = 'Home'
    self.dronelabel = 'Drone'
    self.selectPlaySpeeds.set('Fast 4x')
    self.tree.delete(*self.tree.get_children())
    self.map_widget.set_zoom(self.defaultBlankMapZoom)
    self.map_widget.set_position(51.50722, -0.1275)
    if (self.flightPaths):
      for flightPath in self.flightPaths:
        flightPath.delete()
        flightPath = None
      self.flightPaths = None
    if (self.ctrlmarker):
      self.ctrlmarker.delete()
      self.ctrlmarker = None
    if (self.homemarker):
      self.homemarker.delete()
      self.homemarker = None
    if (self.dronemarker):
      self.dronemarker.delete()
      self.dronemarker = None
    self.pathCoords = None
    self.flightStarts = None
    self.selectPath['values'] = ('--')
    self.selectedPath.set('--')
    self.labelFlight['text'] = ''
    self.labelFile['text'] = ''
    self.zipFilename = None


  '''
  Update ctrl/home/drone markers on the map as well as other labels with flight information.
  '''
  def setMarkers(self, row):
    item = self.tree.item(row)
    record = item['values']
    # Controller Marker.
    if (self.showMarkerCtrl and self.showMarkerCtrl.get() == 'Y'):
      try:
        ctrllat = float(record[self.columns.index('ctrllat')])
        ctrllon = float(record[self.columns.index('ctrllon')])
        if (self.ctrlmarker):
          self.ctrlmarker.set_position(ctrllat, ctrllon)
        else:
          self.ctrlmarker = self.map_widget.set_marker(
            ctrllat, ctrllon, text=self.ctrllabel,
            marker_color_circle=self.ctrlMarkerColor1,
            marker_color_outside=self.ctrlMarkerColor2)
      except:
        self.ctrlmarker = None # Handle bad coordinates.
    else:
      if (self.ctrlmarker):
        self.ctrlmarker.delete()
        self.ctrlmarker = None
    # Drone Home (RTH) Marker.
    if (self.showMarkerHome and self.showMarkerHome.get() == 'Y'):
      try:
        homelat = float(record[self.columns.index('homelat')])
        homelon = float(record[self.columns.index('homelon')])
        if (self.homemarker):
          self.homemarker.set_position(homelat, homelon)
        else:
          self.homemarker = self.map_widget.set_marker(
            homelat, homelon, text=self.homelabel,
            marker_color_circle=self.homeMarkerColor1,
            marker_color_outside=self.homeMarkerColor2)
      except:
        self.homemarker = None # Handle bad coordinates.
    else:
      if (self.homemarker):
        self.homemarker.delete()
        self.homemarker = None
    # Drone marker.
    try:
      dronelat = float(record[self.columns.index('dronelat')])
      dronelon = float(record[self.columns.index('dronelon')])
      if (self.dronemarker):
        self.dronemarker.set_position(dronelat, dronelon)
      else:
        self.dronemarker = self.map_widget.set_marker(
          dronelat, dronelon, text=self.dronelabel,
          marker_color_circle=self.droneMarkerColor1,
          marker_color_outside=self.droneMarkerColor2)
    except:
      self.dronemarker = None # Handle bad coordinates.
    dist = record[self.columns.index('distance3')]
    alt = record[self.columns.index('altitude2')]
    speed = record[self.columns.index('speed2')]
    flightTs = self.getDatetime(record[self.columns.index('timestamp')]).isoformat(sep=' ', timespec='seconds')
    self.labelFlight['text'] = f'    Time: {flightTs}   /   Distance (m): {dist}   /   Altitude (m): {alt}   /   Speed (m/s): {speed}'


  '''
  Called when a flight path has been selected from the dropdown.
  '''
  def choosePath(self, event):
    if (self.selectedPath.get() == '--'):
      return
    idx = self.flightStarts[self.selectedPath.get()]
    gotoRow = self.tree.get_children()[idx]
    self.tree.see(gotoRow)
    self.tree.selection_set(gotoRow)
    # Center the map at the drone lift-off position.
    item = self.tree.item(gotoRow)
    record = item['values']
    dronelat = float(record[self.columns.index('dronelat')])
    dronelon = float(record[self.columns.index('dronelon')])
    self.map_widget.set_position(dronelat, dronelon)


  '''
  Convenience function to return the datetime from a string.
  '''
  def getDatetime(self, stringVal):
    dt = None
    try:
      dt = datetime.datetime.strptime(stringVal, '%Y-%m-%d %H:%M:%S.%f')
    except:
      dt = datetime.datetime.strptime(stringVal, '%Y-%m-%d %H:%M:%S')
    return dt


  '''
  Update markers on the map if a row in the table list has been selected.
  '''
  def item_selected(self, event):
    for selected_item in self.tree.selection():
      self.setMarkers(selected_item)
      break


  '''
  Called when Map Tile choice selection changes.
  '''
  def setTileSource(self, event):
    tileSource = self.selectedTile.get()
    if (tileSource == 'Google Standard'):
      self.map_widget.set_tile_server("https://mt0.google.com/vt/lyrs=m&hl=en&x={x}&y={y}&z={z}&s=Ga", max_zoom=22)  # google normal
    elif (tileSource == 'Google Satellite'):
      self.map_widget.set_tile_server("https://mt0.google.com/vt/lyrs=s&hl=en&x={x}&y={y}&z={z}&s=Ga", max_zoom=22)  # google satellite
    elif (tileSource == 'Open Topo'):
      self.map_widget.set_tile_server("https://tile.opentopomap.org/{z}/{x}/{y}.png")
    else:
      self.map_widget.set_tile_server("https://a.tile.openstreetmap.org/{z}/{x}/{y}.png")  # OpenStreetMap (default)


  '''
  Called when checkbox to show all drone metrics is selected.
  '''
  def setShowAll(self):
    if (self.showAll.get() == 'Y'):
      self.tree['displaycolumns'] = self.columns
    else:
      if (self.displayMode == "DREAMER"):
        self.tree['displaycolumns'] = self.showColsDreamer
      else:
        self.tree['displaycolumns'] = self.showColsAtom


  '''
  Called when checkbox for Path view is selected (to show or hide drone path on the map).
  '''
  def setPathView(self):
    if (self.showPath.get() == 'Y'):
      colors = ["#417dd6","#ab27a9","#e54f14","#ffa900","#00a31f"]
      self.flightPaths = []
      idx = 0
      for pathCoord in self.pathCoords:
        self.flightPaths.append(self.map_widget.set_path(width=1, position_list=pathCoord, color=colors[idx%len(colors)]))
        idx = idx + 1
    else:
      if (self.flightPaths):
        for flightPath in self.flightPaths:
          flightPath.delete()
          flightPath = None
        self.flightPaths = None


  '''
  Save the flight data in a CSV file.
  '''
  def saveFile(self, csvFilename):
    with open(csvFilename, 'w') as f:
      head = ''
      for colref in self.tree['displaycolumns']:
        colTitle = self.tree.heading(colref)['text']
        if len(head) > 0:
          head = head + ','
        head = head + colTitle
      f.write(head)
      for rowid in self.tree.get_children():
        vals = self.tree.item(rowid)['values']
        hasWritten = False
        colIdx = 0
        f.write('\n')
        for colref in self.tree['columns']:
          if colref in self.tree['displaycolumns']:
            if (hasWritten):
              f.write(',')
            f.write('"' + str(vals[colIdx]) + '"')
            hasWritten = True
          colIdx = colIdx + 1;
    f.close()
    showinfo(title='Export Completed', message=f'Data has been exported to {csvFilename}')


  '''
  Open the selected Flight Data Zip file.
  '''
  def parseFile(self, selectedFile):
    zipFile = Path(selectedFile);
    if (not zipFile.is_file()):
      showerror(title='Invalid File', message=f'Not a valid file specified: {selectedFile}')
      return

    droneModel = re.sub(r"[0-9]*-(.*)-Drone.*", r"\1", PurePath(selectedFile).name) # Pull drone model from zip filename.
    droneModel = re.sub(r"[^\w]", r" ", droneModel) # Remove non-alphanumeric characters from the model name.
    lcDM = droneModel.lower()
    if ('atom' in droneModel.lower()):
      self.parseAtomLogs(droneModel, selectedFile)
    elif ('p1a' in droneModel.lower()):
      self.parseDreamerLogs(droneModel, selectedFile)
    else:
      showwarning(title='Unsupported Model', message=f'This drone model may not be supported in this software: {droneModel}')
      self.parseAtomLogs(droneModel, selectedFile)



  '''
  Parse Atom based logs.
  '''
  def parseAtomLogs(self, droneModel, selectedFile):
    setctrl = True

    binLog = os.path.join(tempfile.gettempdir(), "flightdata")
    shutil.rmtree(binLog, ignore_errors=True) # Delete old temp files if they were missed before.

    with ZipFile(selectedFile, 'r') as unzip:
      unzip.extractall(path=binLog)

    self.stop()
    self.reset()
    self.displayMode = "ATOM"
    self.setShowAll()
    self.zipFilename = selectedFile

    # First read the FPV file. The presence of this file is optional. The format of this
    # file differs slightly based on the mobile platform it was created on: Android vs iOS.
    # Example filenames:
    #   - 20230819190421-AtomSE-iosSystem-iPhone13Pro-FPV.bin
    #   - 20230826161313-Atom SE-Android-(samsung)-FPV.bin
    fpvStat = {}
    files = glob.glob(os.path.join(binLog, '**/*-FPV.bin'), recursive=True)
    for file in files:
      self.ctrllabel = re.sub(r".*-\(?([^\)-]+)\)?-.*", r"\1", PurePath(file).name)
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
    files = sorted(glob.glob(os.path.join(binLog, '**/*-FC.bin'), recursive=True))
    timestampMarkers = []

    # First grab timestamps from the filenames. Those are used to calculate the real timestamps with the elapsed time from each record.
    for file in files:
      timestampMarkers.append(datetime.datetime.strptime(re.sub("-.*", "", Path(file).stem), '%Y%m%d%H%M%S'))

    filenameTs = timestampMarkers[0]
    prevReadingTs = timestampMarkers[0]
    maxDist = 0;
    maxAlt = 0;
    maxSpeed = 0;
    self.pathCoords = []
    self.flightStarts = {}
    pathCoord = []
    isNewPath = True
    for file in files:
      with open(file, mode='rb') as flightFile:
        while True:
          fcRecord = flightFile.read(512)
          if (len(fcRecord) < 512):
            break

          recordCount = struct.unpack('<I', fcRecord[0:4])[0] # This incremental record count is generated by the Potensic Pro app. All other fields are generated directly on the drone itself. The Potensic App saves these drone logs to the .bin files on the mobile device.
          elapsed = struct.unpack('<Q', fcRecord[5:13])[0] # Microseconds elapsed since previous reading. 
          satellites = struct.unpack('<B', fcRecord[46:47])[0] # Number of satellites.
          dronelat = struct.unpack('<i', fcRecord[53:57])[0]/10000000 # Drone coords.
          dronelon = struct.unpack('<i', fcRecord[57:61])[0]/10000000
          ctrllat = struct.unpack('<i', fcRecord[159:163])[0]/10000000 # Controller coords.
          ctrllon = struct.unpack('<i', fcRecord[163:167])[0]/10000000
          homelat = struct.unpack('<i', fcRecord[435:439])[0]/10000000 # Home Point coords (for Return To Home).
          homelon = struct.unpack('<i', fcRecord[439:443])[0]/10000000
          dist1lat = struct.unpack('f', fcRecord[235:239])[0] # Distance home point vs controller??
          dist1lon = struct.unpack('f', fcRecord[239:243])[0]
          dist2lat = struct.unpack('f', fcRecord[319:323])[0] # Distance home point vs controller??
          dist2lon = struct.unpack('f', fcRecord[323:327])[0]
          dist1 = round(math.sqrt(math.pow(dist1lat, 2) + math.pow(dist1lon, 2)), 2) # Pythagoras to calculate real distance.
          dist2 = round(math.sqrt(math.pow(dist2lat, 2) + math.pow(dist2lon, 2)), 2) # Pythagoras to calculate real distance.
          dist3 = struct.unpack('f', fcRecord[431:435])[0] # Distance as reported by the drone.

          if (dist3 > maxDist):
            maxDist = dist3
          alt1 = round(-struct.unpack('f', fcRecord[243:247])[0], 2) # Relative height from controller vs distance to ground??
          alt2 = round(-struct.unpack('f', fcRecord[343:347])[0], 2) # Relative height from controller vs distance to ground??
          if (alt2 > maxAlt):
            maxAlt = alt2
          speed1lat = struct.unpack('f', fcRecord[247:251])[0]
          speed1lon = struct.unpack('f', fcRecord[251:255])[0]
          speed2lat = struct.unpack('f', fcRecord[327:331])[0]
          speed2lon = struct.unpack('f', fcRecord[331:335])[0]
          speed1 = round(math.sqrt(math.pow(speed1lat, 2) + math.pow(speed1lon, 2)), 2) # Pythagoras to calculate real speed.
          speed2 = round(math.sqrt(math.pow(speed2lat, 2) + math.pow(speed2lon, 2)), 2) # Pythagoras to calculate real speed.
          if (speed2 > maxSpeed):
            maxSpeed = speed2
          speed1vert = -struct.unpack('f', fcRecord[255:259])[0]
          speed2vert = -struct.unpack('f', fcRecord[347:351])[0]

          hasValidCoords = dronelat != 0.0 and dronelon != 0.0 and ctrllat != 0.0 and ctrllon != 0.0

          # Build paths for each flight. TODO - improve this logic as it's not always correct.
          if (hasValidCoords):
            if (dist3 == 0): # distance is zero when ctrl coords are refreshed.
              if (len(pathCoord) > 0):
                self.pathCoords.append(pathCoord)
                pathCoord = []
                isNewPath = True
            elif (alt2 > 0): # Only trace path where the drone is off the ground.
              pathCoord.append((dronelat, dronelon))

          readingTs = filenameTs + datetime.timedelta(milliseconds=(elapsed/1000))
          while (readingTs < prevReadingTs):
            # Line up to the next valid timestamp marker (pulled from the filenames).
            filenameTs = timestampMarkers.pop(0)
            readingTs = filenameTs + datetime.timedelta(milliseconds=(elapsed/1000))

          # Get corresponding record from the controller. There may not be one, or any at all. Match up to 5 seconds ago.
          fpvRssi = ""
          fpvChannel = ""
          #fpvWirelessConnected = ""
          fpvFlightCtrlConnected = ""
          fpvRemoteConnected = ""
          #fpvHighDbm = ""
          fpvRecord = fpvStat.get(readingTs.strftime('%Y%m%d%H%M%S'));
          secondsAgo = -1;
          while (not fpvRecord):
            fpvRecord = fpvStat.get((readingTs + datetime.timedelta(seconds=secondsAgo)).strftime('%Y%m%d%H%M%S'));
            if (secondsAgo <= -5):
              break;
            secondsAgo = secondsAgo - 1;
          if (fpvRecord):
            fpvRssi = str(int(fpvRecord[2:4], 16))
            fpvChannel = str(int(fpvRecord[4:6], 16))
            fpvFlags = int(fpvRecord[6:8], 16)
            #fpvWirelessConnected = "1" if fpvFlags & 1 == 1 else "0"
            fpvFlightCtrlConnected = "1" if fpvFlags & 2 == 2 else "0" # Drone to controller connection.
            fpvRemoteConnected = "1" if fpvFlags & 4 == 4 else "0"
            #fpvHighDbm = "1" if fpvFlags & 32 == 32 else "0"

          prevReadingTs = readingTs
          if (isNewPath and len(pathCoord) > 0):
            self.flightStarts[f'Flight {len(self.pathCoords)+1}'] = len(self.tree.get_children())
            isNewPath = False
          self.tree.insert('', tk.END, value=(readingTs.isoformat(sep=' '), f"{alt1:.2f}", f"{alt2:.2f}", f"{dist1:.2f}", f"{dist1lat:.2f}", f"{dist1lon:.2f}", f"{dist2:.2f}", f"{dist2lat:.2f}", f"{dist2lon:.2f}", f"{dist3:.2f}", f"{speed1:.2f}", f"{speed1lat:.2f}", f"{speed1lon:.2f}", f"{speed2:.2f}", f"{speed2lat:.2f}", f"{speed2lon:.2f}", f"{speed1vert:.2f}", f"{speed2vert:.2f}", str(satellites), str(ctrllat), str(ctrllon), str(homelat), str(homelon), str(dronelat), str(dronelon), fpvRssi, fpvChannel, fpvFlightCtrlConnected, fpvRemoteConnected))
          if (setctrl and hasValidCoords and alt2 > 0): # Record home location from the moment the drone ascends.
            self.dronelabel = droneModel
            self.map_widget.set_zoom(self.defaultDroneZoom)
            self.map_widget.set_position(dronelat, dronelon)
            self.ctrlmarker = self.map_widget.set_marker(
              ctrllat, ctrllon, text=self.ctrllabel,
              marker_color_circle=self.ctrlMarkerColor1,
              marker_color_outside=self.ctrlMarkerColor2)
            setctrl = False

      flightFile.close()

    shutil.rmtree(binLog, ignore_errors=True) # Delete temp files.

    if (len(pathCoord) > 0):
      self.pathCoords.append(pathCoord)
    self.setPathView()
    self.labelFile['text'] = f'    Max Dist (m): {maxDist:8.2f}   /   Max Alt (m): {maxAlt:7.2f}   /   Max Speed (m/s): {maxSpeed:6.2f}   /   File: {PurePath(selectedFile).name}'
    pathNames = list(self.flightStarts.keys())
    self.selectPath['values'] = pathNames
    self.selectedPath.set(pathNames[0])



  '''
  Parse Dreamer based logs.
  '''
  def parseDreamerLogs(self, droneModel, selectedFile):
    setctrl = True

    binLog = os.path.join(tempfile.gettempdir(), "flightdata")
    shutil.rmtree(binLog, ignore_errors=True) # Delete old temp files if they were missed before.

    with ZipFile(selectedFile, 'r') as unzip:
      unzip.extractall(path=binLog)

    self.stop()
    self.reset()
    self.displayMode = "DREAMER"
    self.setShowAll()
    self.zipFilename = selectedFile

    # First read the FPV file. The presence of this file is optional.
    fpvStat = {}
    files = glob.glob(os.path.join(binLog, '**/*-FPV.bin'), recursive=True)
    for file in files:
      self.ctrllabel = re.sub(r".*-\(?([^\)-]+)\)?-.*", r"\1", PurePath(file).name)
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
    files = sorted(glob.glob(os.path.join(binLog, '**/*-FC.bin'), recursive=True))
    timestampMarkers = []

    # First grab timestamps from the filenames. Those are used to calculate the real timestamps with the elapsed time from each record.
    for file in files:
      timestampMarkers.append(datetime.datetime.strptime(re.sub("-.*", "", Path(file).stem), '%Y%m%d%H%M%S'))

    filenameTs = timestampMarkers[0]
    prevReadingTs = timestampMarkers[0]
    readingTs = timestampMarkers[0]
    maxDist = 0;
    maxAlt = 0;
    maxSpeed = 0;
    self.pathCoords = []
    self.flightStarts = {}
    pathCoord = []
    isNewPath = True
    for file in files:
      with open(file, mode='rb') as flightFile:
        while True:
          fcRecord = flightFile.read(512)
          if (len(fcRecord) < 512):
            break

          recordCount = struct.unpack('<I', fcRecord[0:4])[0] # 4 bytes.
          elapsed = struct.unpack('<I', fcRecord[33:37])[0]
          satellites = struct.unpack('<B', fcRecord[7:8])[0]
          dronelon = struct.unpack('f', fcRecord[145:149])[0]
          dronelat = struct.unpack('f', fcRecord[149:153])[0]
          alt1 = struct.unpack('<h', fcRecord[39:41])[0] / 10
          alt2 = struct.unpack('<h', fcRecord[59:61])[0] / 10
          dist1lat = struct.unpack('<h', fcRecord[37:39])[0] / 10
          dist1lon = struct.unpack('<h', fcRecord[41:43])[0] / 10
          dist2lat = struct.unpack('<h', fcRecord[57:59])[0] / 10
          dist2lon = struct.unpack('<h', fcRecord[61:63])[0] / 10
          dist1 = round(math.sqrt(math.pow(dist1lat, 2) + math.pow(dist1lon, 2)), 2) # Pythagoras to calculate real distance.
          dist2 = round(math.sqrt(math.pow(dist2lat, 2) + math.pow(dist2lon, 2)), 2) # Pythagoras to calculate real distance.
          earth_radius_in_km = 6367 # 6378.137
          coeff = (1 / ((2 * math.pi / 360) * earth_radius_in_km)) / 1000
          real1lat = dronelat + ((dist1lat) * coeff)
          real1lon = dronelon + (((dist1lon) * coeff) / (math.cos(dronelat * math.pi / 180)))
          #real1lon = dronelon + (((dist1lon) * coeff) / (math.cos(dronelat * 0.018)))

          if (dist1 > maxDist):
            maxDist = dist1
          if (alt1 > maxAlt):
            maxAlt = alt1

          hasValidCoords = dronelat != 0.0 and dronelon != 0.0

          # Build paths for each flight. TODO - improve this logic as it's not always correct.
          if (hasValidCoords):
            if (dist1 == 0): # distance is zero when ctrl coords are refreshed.
              if (len(pathCoord) > 0):
                self.pathCoords.append(pathCoord)
                pathCoord = []
                isNewPath = True
            elif (alt1 > 0): # Only trace path where the drone is off the ground.
              pathCoord.append((real1lat, real1lon))

          readingTs = readingTs + datetime.timedelta(milliseconds=(elapsed/1000000))
          while (readingTs < prevReadingTs):
            # Line up to the next valid timestamp marker (pulled from the filenames).
            filenameTs = timestampMarkers.pop(0)
            readingTs = filenameTs + datetime.timedelta(milliseconds=(elapsed/1000000))

          # Get corresponding record from the controller. There may not be one, or any at all. Match up to 5 seconds ago.
          fpvRssi = ""
          fpvChannel = ""
          #fpvWirelessConnected = ""
          fpvFlightCtrlConnected = ""
          fpvRemoteConnected = ""
          #fpvHighDbm = ""
          fpvRecord = fpvStat.get(readingTs.strftime('%Y%m%d%H%M%S'));
          secondsAgo = -1;
          while (not fpvRecord):
            fpvRecord = fpvStat.get((readingTs + datetime.timedelta(seconds=secondsAgo)).strftime('%Y%m%d%H%M%S'));
            if (secondsAgo <= -5):
              break;
            secondsAgo = secondsAgo - 1;
          if (fpvRecord):
            fpvRssi = str(int(fpvRecord[2:4], 16))
            fpvChannel = str(int(fpvRecord[4:6], 16))
            fpvFlags = int(fpvRecord[6:8], 16)
            #fpvWirelessConnected = "1" if fpvFlags & 1 == 1 else "0"
            fpvFlightCtrlConnected = "1" if fpvFlags & 2 == 2 else "0" # Drone to controller connection.
            fpvRemoteConnected = "1" if fpvFlags & 4 == 4 else "0"
            #fpvHighDbm = "1" if fpvFlags & 32 == 32 else "0"

          prevReadingTs = readingTs
          if (isNewPath and len(pathCoord) > 0):
            self.flightStarts[f'Flight {len(self.pathCoords)+1}'] = len(self.tree.get_children())
            isNewPath = False
          self.tree.insert('', tk.END, value=(readingTs.isoformat(sep=' '), f"{alt1:.2f}", f"{alt2:.2f}", f"{dist1:.2f}", f"{dist1lat:.2f}", f"{dist1lon:.2f}", f"{dist2:.2f}", f"{dist2lat:.2f}", f"{dist2lon:.2f}", "", "", "", "", "", "", "", "", "", str(satellites), "", "", str(dronelat), str(dronelon), str(real1lat), str(real1lon)))
          if (setctrl and hasValidCoords and alt1 > 0): # Record home location from the moment the drone ascends.
            self.dronelabel = droneModel
            self.map_widget.set_zoom(self.defaultDroneZoom)
            self.map_widget.set_position(real1lat, real1lon)
            self.ctrlmarker = self.map_widget.set_marker(
              dronelat, dronelon, text=self.ctrllabel,
              marker_color_circle=self.ctrlMarkerColor1,
              marker_color_outside=self.ctrlMarkerColor2)
            setctrl = False

      flightFile.close()

    shutil.rmtree(binLog, ignore_errors=True) # Delete temp files.

    if (len(pathCoord) > 0):
      self.pathCoords.append(pathCoord)
    self.setPathView()
    self.labelFile['text'] = f'    Max Dist (m): {maxDist:8.2f}   /   Max Alt (m): {maxAlt:7.2f}   /   File: {PurePath(selectedFile).name}'
    pathNames = list(self.flightStarts.keys())
    self.selectPath['values'] = pathNames
    self.selectedPath.set(pathNames[0])



  '''
  File Dialog to ask for the Flight Data Zip file.
  '''
  def askForFlightFile(self):
    selectedZipfile = filedialog.askopenfilename(title='Open Flight File',filetypes=(('zip files', '*.zip'),('All files', '*.*')))
    self.parseFile(selectedZipfile)


  '''
  File Dialog to ask where to save the flight data to.
  '''
  def askForExportFile(self):
    if (self.zipFilename != None):
      selectedExportfile = filedialog.asksaveasfilename(title='Export Flight Data',filetypes=(('CSV files', '*.csv'),('All files', '*.*')))
      self.saveFile(selectedExportfile)
    else:
      showwarning(title='Nothing to Export', message='There is nothing to Export. Please open a Flight Data file first (.zip file).')


  '''
  Export file based on zip filename.
  '''
  def exportFlightFile(self):
    if (self.zipFilename != None):
      self.saveFile(re.sub("\.zip$", "", self.zipFilename) + ".csv")
    else:
      showwarning(title='Nothing to Export', message='There is nothing to Export. Please open a Flight Data file first (.zip file).')


  '''
  Gracefully clean up before exiting.
  '''
  def exitApp(self):
    self.stop()
    while (self.isPlaying):
      time.sleep(0.5)
    self.destroy()


  '''
  Initialize.
  '''
  def __init__(self):
    super().__init__()
    screen_width = self.winfo_screenwidth()
    screen_height = self.winfo_screenheight()
    # Determine target device
    if (screen_width >= 1280):
      device = "desktop"
    elif (screen_width >= 768):
      device = "tablet"
    else:
      device = "mobile"

    # Scale widgets based on device.
    if (device == 'desktop'):
      fontFamily = 'Helvetica'
      nametofont("TkMenuFont").configure(family=fontFamily, size=14)
      nametofont("TkDefaultFont").configure(family=fontFamily, size=14)
      nametofont("TkHeadingFont").configure(family=fontFamily, size=14)
      nametofont("TkTextFont").configure(family=fontFamily, size=14)
      colWidth1 = 200
      colWidth2 = 120
      colWidth3 = 90
      colWidth4 = 120
      colWidth5 = 50
    elif (device == 'tablet'):
      fontFamily = 'Helvetica'
      nametofont("TkMenuFont").configure(family=fontFamily, size=12)
      nametofont("TkDefaultFont").configure(family=fontFamily, size=12)
      nametofont("TkHeadingFont").configure(family=fontFamily, size=12)
      nametofont("TkTextFont").configure(family=fontFamily, size=12)
      colWidth1 = 170
      colWidth2 = 90
      colWidth3 = 80
      colWidth4 = 70
      colWidth5 = 50
    else:
      fontFamily = 'Helvetica'
      nametofont("TkMenuFont").configure(family=fontFamily, size=8)
      nametofont("TkDefaultFont").configure(family=fontFamily, size=8) 
      nametofont("TkHeadingFont").configure(family=fontFamily, size=8)
      nametofont("TkTextFont").configure(family=fontFamily, size=8)
      colWidth1 = 100
      colWidth2 = 70
      colWidth3 = 60
      colWidth4 = 50
      colWidth5 = 30

    self.title(f"Flight Data Viewer - {self.version}")
    self.protocol("WM_DELETE_WINDOW", self.exitApp)
    self.state('zoomed')
    self.resizable(True, True)

    style = ttk.Style(self)
    style.theme_use('classic')

    pw = ttk.PanedWindow(orient=tk.VERTICAL)

    dataFrame = ttk.Frame(self, height=200)
    dataFrame.columnconfigure(0, weight=1)
    dataFrame.rowconfigure(0, weight=1)

    mapFrame = ttk.Frame(self, height=400)

    pw.add(dataFrame)
    pw.add(mapFrame)
    pw.pack(fill=tk.BOTH, expand=True)

    menubar = Menu(self)
    self.config(menu=menubar)
    file_menu = Menu(menubar, tearoff=False)
    file_menu.add_command(label='Open...', command=self.askForFlightFile)
    file_menu.add_separator()
    file_menu.add_command(label='Export', command=self.exportFlightFile)
    file_menu.add_command(label='Export As...', command=self.askForExportFile)
    file_menu.add_separator()
    file_menu.add_command(label='Close', command=self.reset)
    file_menu.add_separator()
    file_menu.add_command(label='Exit', command=self.exitApp)
    menubar.add_cascade(label='File', menu=file_menu)
    
    self.tree = ttk.Treeview(dataFrame, columns=self.columns, show='headings', selectmode='browse', displaycolumns=self.showColsAtom)
    self.tree.column("timestamp", anchor=tk.W, stretch=tk.NO, width=colWidth1)
    self.tree.heading('timestamp', text='Timestamp')
    self.tree.column("altitude1", anchor=tk.E, stretch=tk.NO, width=colWidth4)
    self.tree.heading('altitude1', text='Alt1 (m)')
    self.tree.column("altitude2", anchor=tk.E, stretch=tk.NO, width=colWidth4)
    self.tree.heading('altitude2', text='Alt2 (m)')
    self.tree.column("distance1", anchor=tk.E, stretch=tk.NO, width=colWidth3)
    self.tree.heading('distance1', text='Dist1 (m)')
    self.tree.column("dist1lat", anchor=tk.E, stretch=tk.NO, width=colWidth3)
    self.tree.heading('dist1lat', text='Lat Dist1 (m)')
    self.tree.column("dist1lon", anchor=tk.E, stretch=tk.NO, width=colWidth3)
    self.tree.heading('dist1lon', text='Lon Dist1 (m)')
    self.tree.column("distance2", anchor=tk.E, stretch=tk.NO, width=colWidth3)
    self.tree.heading('distance2', text='Dist2 (m)')
    self.tree.column("dist2lat", anchor=tk.E, stretch=tk.NO, width=colWidth3)
    self.tree.heading('dist2lat', text='Lat Dist2 (m)')
    self.tree.column("dist2lon", anchor=tk.E, stretch=tk.NO, width=colWidth3)
    self.tree.heading('dist2lon', text='Lon Dist2 (m)')
    self.tree.column("distance3", anchor=tk.E, stretch=tk.NO, width=colWidth3)
    self.tree.heading('distance3', text='Dist3 (m)')
    self.tree.column("speed1", anchor=tk.E, stretch=tk.NO, width=colWidth4)
    self.tree.heading('speed1', text='Speed1 (m/s)')
    self.tree.column("speed1lat", anchor=tk.E, stretch=tk.NO, width=colWidth4)
    self.tree.heading('speed1lat', text='Lat S1 (m/s)')
    self.tree.column("speed1lon", anchor=tk.E, stretch=tk.NO, width=colWidth4)
    self.tree.heading('speed1lon', text='Lon S1 (m/s)')
    self.tree.column("speed2", anchor=tk.E, stretch=tk.NO, width=colWidth4)
    self.tree.heading('speed2', text='Speed2 (m/s)')
    self.tree.column("speed2lat", anchor=tk.E, stretch=tk.NO, width=colWidth4)
    self.tree.heading('speed2lat', text='Lat S2 (m/s)')
    self.tree.column("speed2lon", anchor=tk.E, stretch=tk.NO, width=colWidth4)
    self.tree.heading('speed2lon', text='Lon S2 (m/s)')
    self.tree.column("speed1vert", anchor=tk.E, stretch=tk.NO, width=colWidth4)
    self.tree.heading('speed1vert', text='Speed1 Vert (m/s)')
    self.tree.column("speed2vert", anchor=tk.E, stretch=tk.NO, width=colWidth4)
    self.tree.heading('speed2vert', text='Speed2 Vert (m/s)')
    self.tree.column("satellites", anchor=tk.E, stretch=tk.NO, width=colWidth5)
    self.tree.heading('satellites', text='Sat')
    self.tree.column("ctrllat", anchor=tk.W, stretch=tk.NO, width=colWidth2)
    self.tree.heading('ctrllat', text='Ctrl Lat')
    self.tree.column("ctrllon", anchor=tk.W, stretch=tk.NO, width=colWidth2)
    self.tree.heading('ctrllon', text='Ctrl Lon')
    self.tree.column("homelat", anchor=tk.W, stretch=tk.NO, width=colWidth2)
    self.tree.heading('homelat', text='Home Lat')
    self.tree.column("homelon", anchor=tk.W, stretch=tk.NO, width=colWidth2)
    self.tree.heading('homelon', text='Home Lon')
    self.tree.column("dronelat", anchor=tk.W, stretch=tk.NO, width=colWidth2)
    self.tree.heading('dronelat', text='Drone Lat')
    self.tree.column("dronelon", anchor=tk.W, stretch=tk.NO, width=colWidth2)
    self.tree.heading('dronelon', text='Drone Lon')
    self.tree.column("rssi", anchor=tk.W, stretch=tk.NO, width=colWidth5)
    self.tree.heading('rssi', text='RSSI')
    self.tree.column("channel", anchor=tk.W, stretch=tk.NO, width=colWidth5)
    self.tree.heading('channel', text='Chn')
    #self.tree.column("wirelessconnected", anchor=tk.W, stretch=tk.NO, width=120)
    #self.tree.heading('wirelessconnected', text='Wireless Connected')
    self.tree.column("flightctrlconnected", anchor=tk.W, stretch=tk.NO, width=colWidth2)
    self.tree.heading('flightctrlconnected', text='Drone Connected')
    self.tree.column("remoteconnected", anchor=tk.W, stretch=tk.NO, width=colWidth2)
    self.tree.heading('remoteconnected', text='Remote Connected')
    #self.tree.column("highdbm", anchor=tk.W, stretch=tk.NO, width=120)
    #self.tree.heading('highdbm', text='High Dbm')
    self.tree.bind('<<TreeviewSelect>>', self.item_selected)
    self.tree.grid(row=0, column=0, sticky=tk.NSEW)
    scrollbar = ttk.Scrollbar(dataFrame, orient=tk.VERTICAL, command=self.tree.yview)
    self.tree.configure(yscroll=scrollbar.set)
    scrollbar.grid(row=0, column=1, sticky=tk.NS)

    playbackFrame = ttk.Frame(mapFrame, height=10, padding=(5, 0, 5, 0))
    playbackFrame.pack(fill=tk.BOTH, expand=False)
    self.selectPlaySpeeds = ttk.Combobox(playbackFrame, state="readonly", exportselection=0, width=16)
    self.selectPlaySpeeds.grid(row=0, column=0, sticky=tk.E, padx=7, pady=0)
    self.selectPlaySpeeds['values'] = ('Real-Time', 'Fast', 'Fast 2x', 'Fast 4x', 'Fast 10x', 'Fast 25x')
    buttonPlay = ttk.Button(playbackFrame, text='Play', command=self.play, width=4)
    buttonPlay.grid(row=0, column=1, sticky=tk.EW, padx=0, pady=0)
    buttonStop = ttk.Button(playbackFrame, text='Stop', command=self.stop, width=4)
    buttonStop.grid(row=0, column=2, sticky=tk.W, padx=0, pady=0)
    self.showMarkerCtrl = tk.StringVar()
    markerCtrlView = ttk.Checkbutton(playbackFrame, text='Controller', variable=self.showMarkerCtrl, onvalue='Y', offvalue='N')
    markerCtrlView.grid(row=0, column=3, sticky=tk.E, padx=4, pady=0)
    self.showMarkerCtrl.set('Y')
    self.showMarkerHome = tk.StringVar()
    markerHomeView = ttk.Checkbutton(playbackFrame, text='Home', variable=self.showMarkerHome, onvalue='Y', offvalue='N')
    markerHomeView.grid(row=0, column=4, sticky=tk.E, padx=4, pady=0)
    self.showMarkerHome.set('N')
    self.labelFlight = ttk.Label(playbackFrame, text='')
    self.labelFlight.grid(row=0, column=5, sticky=tk.W, padx=2, pady=0)

    fileInfoFrame = ttk.Frame(mapFrame, height=10, padding=(5, 0, 5, 5))
    fileInfoFrame.pack(fill=tk.BOTH, expand=False)
    self.selectedTile = tk.StringVar()
    selectTileSource = ttk.Combobox(fileInfoFrame, textvariable=self.selectedTile, state="readonly", exportselection=0, width=16)
    selectTileSource.grid(row=0, column=0, sticky=tk.E, padx=7, pady=0)
    selectTileSource['values'] = ('OpenStreetMap', 'Google Standard', 'Google Satellite', 'Open Topo')
    selectTileSource.bind('<<ComboboxSelected>>', self.setTileSource)
    self.selectedTile.set('OpenStreetMap')
    self.selectedPath = tk.StringVar()
    self.selectPath = ttk.Combobox(fileInfoFrame, textvariable=self.selectedPath, state="readonly", exportselection=0, width=14)
    self.selectPath.grid(row=0, column=1, sticky=tk.E, padx=7, pady=0)
    self.selectPath.bind('<<ComboboxSelected>>', self.choosePath)
    self.showPath = tk.StringVar()
    pathView = ttk.Checkbutton(fileInfoFrame, text='Flight Paths', command=self.setPathView, variable=self.showPath, onvalue='Y', offvalue='N')
    pathView.grid(row=0, column=2, sticky=tk.E, padx=2, pady=0)
    self.showPath.set('Y')
    self.showAll = tk.StringVar()
    allMetricView = ttk.Checkbutton(fileInfoFrame, text='All Metrics', command=self.setShowAll, variable=self.showAll, onvalue='Y', offvalue='N')
    allMetricView.grid(row=0, column=3, sticky=tk.E, padx=4, pady=0)
    self.showAll.set('N')
    self.labelFile = ttk.Label(fileInfoFrame, text='')
    self.labelFile.grid(row=0, column=4, sticky=tk.W, padx=2, pady=0)

    self.map_widget = tkintermapview.TkinterMapView(mapFrame, corner_radius=0)
    self.map_widget.pack(fill=tk.BOTH, expand=True)

    self.reset();


if __name__ == '__main__':
  extract = ExtractFlightData()
  extract.mainloop()
