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
from tkinter import Menu
from tkinter.messagebox import showinfo, showwarning, showerror

import tkintermapview

from pathlib import Path, PurePath
from zipfile import ZipFile
from math import pi,sqrt,sin,cos,atan2,modf

class ExtractFlightData(tk.Tk):


  '''
  Global variables and constants.
  '''
  defaultDroneZoom = 14
  defaultBlankMapZoom = 1
  zipFilename = None
  tree = None
  map_widget = None
  selectPlaySpeeds = None
  homemarker = None
  dronemarker = None
  homelabel = None
  dronelabel = None
  isPlaying = False
  currentRow = None
  labelTimestamp = None
  labelDistance = None
  labelAltitude = None
  labelSpeed = None
  labelMaxDistance = None
  labelMaxAltitude = None
  labelMaxSpeed = None
  labelFilename = None


  '''
  Update home/drone markers on the map with the next set of coordinates in the table list.
  '''
  def setFrame(self):
    while self.isPlaying and self.currentRow != None:
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
          diff = datetime.datetime.strptime(self.tree.item(nextRow)['values'][0], '%Y-%m-%d %H:%M:%S.%f') - datetime.datetime.strptime(self.tree.item(self.currentRow)['values'][0], '%Y-%m-%d %H:%M:%S.%f')
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
    self.homelabel = 'Home'
    self.dronelabel = 'Drone'
    self.selectPlaySpeeds.set('Fast 4x')
    self.tree.delete(*self.tree.get_children())
    self.map_widget.set_zoom(self.defaultBlankMapZoom)
    self.map_widget.set_position(51.50722, -0.1275)
    if (self.homemarker):
      self.homemarker.delete()
    if (self.dronemarker):
      self.dronemarker.delete()
    self.labelTimestamp['text'] = ''
    self.labelDistance['text'] = ''
    self.labelAltitude['text'] = ''
    self.labelSpeed['text'] = ''
    self.labelMaxDistance['text'] = ''
    self.labelMaxAltitude['text'] = ''
    self.labelMaxSpeed['text'] = ''
    self.labelFilename['text'] = ''
    self.zipFilename = None


  '''
  Update drone/home markers on the map as well as other labels with flight information.
  '''
  def setMarkers(self, row):
    item = self.tree.item(row)
    record = item['values']
    homelat = float(record[9])
    homelon = float(record[10])
    dronelat = float(record[11])
    dronelon = float(record[12])
    if (self.homemarker):
      self.homemarker.set_position(homelat, homelon)
    else:
      self.homemarker = self.map_widget.set_marker(homelat, homelon, text=self.homelabel)
    if (self.dronemarker):
      self.dronemarker.set_position(dronelat, dronelon)
    else:
      self.dronemarker = self.map_widget.set_marker(dronelat, dronelon, text=self.dronelabel)
    self.labelTimestamp['text'] = 'Time: ' + datetime.datetime.strptime(record[0], '%Y-%m-%d %H:%M:%S.%f').isoformat(sep=' ', timespec='seconds')
    self.labelDistance['text'] = 'Distance (m): ' + str(record[2])
    self.labelAltitude['text'] = 'Altitude (m): ' + str(record[1])
    self.labelSpeed['text'] = 'Speed (m/s): ' + str(record[5])


  '''
  Update markers on the map if a row in the table list has been selected.
  '''
  def item_selected(self, event):
    for selected_item in self.tree.selection():
      self.setMarkers(selected_item)
      break


  '''
  Save the flight data in a CSV file.
  '''
  def saveFile(self, csvFilename):
    with open(csvFilename, 'w') as f:
      f.write("Timestamp,Altitude (m),Distance (m),Distance Lat (m),Distance Lon (m),Speed (m/s),Speed Lat (m/s),Speed Lon (m/s),Satellites,Home Lat,Home Lon,Drone Lat,Drone Lon")
      for rowid in self.tree.get_children():
        vals = self.tree.item(rowid)['values']
        f.write("\n"+str(vals[0])+","+str(vals[1])+","+str(vals[2])+","+str(vals[3])+","+str(vals[4])+","+str(vals[5])+","+str(vals[6])+","+str(vals[7])+","+str(vals[8])+","+str(vals[9])+","+str(vals[10])+","+str(vals[11])+","+str(vals[12]))
    f.close()
    showinfo(title='Export Completed', message='Data has been exported to ' + csvFilename)


  '''
  Open the selected Flight Data Zip file.
  '''
  def parseFile(self, selectedFile):
    sethome = True
    zipFile = Path(selectedFile);
    if (not zipFile.is_file()):
      showerror(title='Invalid File', message='Not a valid file specified: ' + selectedFile)
      return

    binLog = os.path.join(tempfile.gettempdir(), "flightdata")

    with ZipFile(selectedFile, 'r') as unzip:
      unzip.extractall(path=binLog)

    self.reset()
    self.zipFilename = selectedFile

    # First read the FPV file.
    files = glob.glob(os.path.join(binLog, '**/*-FPV.bin'), recursive=True)
    for file in files:
      self.homelabel = re.sub(r"[0-9]*-(.*)\.[^\.]*", r"\1", PurePath(file).name)

    # Read the Flight Status files.
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
    for file in files:
      with open(file, mode='rb') as flightFile:
        prevElapsed = 0
        while True:
          fcRecord = flightFile.read(512)
          if (len(fcRecord) < 512):
            break

          recordCount = struct.unpack('<I', fcRecord[0:4])[0] # not sure if this is 2 bytes or 4 bytes.
          elapsed = struct.unpack('<Q', fcRecord[5:13])[0]
          satellites = struct.unpack('<B', fcRecord[46:47])[0];
          dronelat = struct.unpack('<i', fcRecord[53:57])[0]/10000000
          dronelon = struct.unpack('<i', fcRecord[57:61])[0]/10000000
          homelat = struct.unpack('<i', fcRecord[159:163])[0]/10000000
          homelon = struct.unpack('<i', fcRecord[163:167])[0]/10000000
          distlat = struct.unpack('f', fcRecord[235:239])[0]
          distlon = struct.unpack('f', fcRecord[239:243])[0]
          dist = round(math.sqrt(math.pow(distlat, 2) + math.pow(distlon, 2)), 2) # Pythagoras to calculate real distance.
          if (dist > maxDist):
            maxDist = dist
          alt = round(-struct.unpack('f', fcRecord[243:247])[0], 2)
          if (alt > maxAlt):
            maxAlt = alt
          speedlat = struct.unpack('f', fcRecord[247:251])[0]
          speedlon = struct.unpack('f', fcRecord[251:255])[0]
          speed = round(math.sqrt(math.pow(speedlat, 2) + math.pow(speedlon, 2)), 2) # Pythagoras to calculate real speed.
          if (speed > maxSpeed):
            maxSpeed = speed

          # Line up to the next valid timestamp marker (pulled from the filenames).
          if (elapsed < prevElapsed):
            while (timestampMarkers[0] < prevReadingTs):
              timestampMarkers.pop(0)
            filenameTs = timestampMarkers.pop(0)

          readingTs = filenameTs + datetime.timedelta(milliseconds=(elapsed/1000))
          prevElapsed = elapsed
          prevReadingTs = readingTs
          self.tree.insert('', tk.END, value=(readingTs.isoformat(sep=' '), f"{alt:.2f}", f"{dist:.2f}", f"{distlat:.2f}", f"{distlon:.2f}", f"{speed:.2f}", f"{speedlat:.2f}", f"{speedlon:.2f}", str(satellites), str(homelat), str(homelon), str(dronelat), str(dronelon)))
          if (sethome and dist > 0):
            self.dronelabel = re.sub(r"[0-9]*-(.*)\.[^\.]*", r"\1", PurePath(selectedFile).name)
            self.map_widget.set_zoom(self.defaultDroneZoom)
            self.map_widget.set_position(homelat, homelon)
            self.homemarker = self.map_widget.set_marker(homelat, homelon, text=self.homelabel)
            sethome = False

      flightFile.close()

    shutil.rmtree(binLog)
    self.labelMaxDistance['text'] = f'Max Distance: {maxDist:.2f}'
    self.labelMaxAltitude['text'] = f'Max Altitude: {maxAlt:.2f}'
    self.labelMaxSpeed['text'] = f'Max Speed: {maxSpeed:.2f}'
    self.labelFilename['text'] = 'File: ' + PurePath(selectedFile).name


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
    self.title("Flight Data Viewer")
    self.protocol("WM_DELETE_WINDOW", self.exitApp)
    self.geometry('1200x800')
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
    
    columns = ('timestamp','altitude','distance','distlat','distlon','speed','speedlat','speedlon','satellites','homelat','homelon','dronelat','dronelon')
    self.tree = ttk.Treeview(dataFrame, columns=columns, show='headings')
    self.tree.column("timestamp", anchor=tk.W, stretch=tk.NO, width=200)
    self.tree.heading('timestamp', text='Timestamp')
    self.tree.column("altitude", anchor=tk.E, stretch=tk.NO, width=70)
    self.tree.heading('altitude', text='Alt (m)')
    self.tree.column("distance", anchor=tk.E, stretch=tk.NO, width=80)
    self.tree.heading('distance', text='Dist (m)')
    self.tree.column("distlat", anchor=tk.E, stretch=tk.NO, width=80)
    self.tree.heading('distlat', text='Lat Dist (m)')
    self.tree.column("distlon", anchor=tk.E, stretch=tk.NO, width=80)
    self.tree.heading('distlon', text='Lon Dist (m)')
    self.tree.column("speed", anchor=tk.E, stretch=tk.NO, width=70)
    self.tree.heading('speed', text='Speed (m/s)')
    self.tree.column("speedlat", anchor=tk.E, stretch=tk.NO, width=70)
    self.tree.heading('speedlat', text='Lat S (m/s)')
    self.tree.column("speedlon", anchor=tk.E, stretch=tk.NO, width=70)
    self.tree.heading('speedlon', text='Lon S (m/s)')
    self.tree.column("satellites", anchor=tk.E, stretch=tk.NO, width=50)
    self.tree.heading('satellites', text='Sat')
    self.tree.column("homelat", anchor=tk.W, stretch=tk.NO, width=100)
    self.tree.heading('homelat', text='Home Lat')
    self.tree.column("homelon", anchor=tk.W, stretch=tk.NO, width=100)
    self.tree.heading('homelon', text='Home Lon')
    self.tree.column("dronelat", anchor=tk.W, stretch=tk.NO, width=100)
    self.tree.heading('dronelat', text='Drone Lat')
    self.tree.column("dronelon", anchor=tk.W, stretch=tk.NO, width=100)
    self.tree.heading('dronelon', text='Drone Lon')
    self.tree.bind('<<TreeviewSelect>>', self.item_selected)
    self.tree.grid(row=0, column=0, sticky=tk.NSEW)
    scrollbar = ttk.Scrollbar(dataFrame, orient=tk.VERTICAL, command=self.tree.yview)
    self.tree.configure(yscroll=scrollbar.set)
    scrollbar.grid(row=0, column=1, sticky=tk.NS)


    self.map_widget = tkintermapview.TkinterMapView(mapFrame, corner_radius=0)
    self.map_widget.pack(fill=tk.BOTH, expand=True)

    # TODO - integrate these as selectable options.
    #self.map_widget.set_tile_server("https://a.tile.openstreetmap.org/{z}/{x}/{y}.png")  # OpenStreetMap (default)
    #self.map_widget.set_tile_server("https://mt0.google.com/vt/lyrs=m&hl=en&x={x}&y={y}&z={z}&s=Ga", max_zoom=22)  # google normal
    #self.map_widget.set_tile_server("https://mt0.google.com/vt/lyrs=s&hl=en&x={x}&y={y}&z={z}&s=Ga", max_zoom=22)  # google satellite

    playbackFrame = ttk.Frame(mapFrame, height=20)
    playbackFrame.pack(fill=tk.BOTH, expand=False)
    self.selectPlaySpeeds = ttk.Combobox(playbackFrame, textvariable=tk.StringVar())
    self.selectPlaySpeeds.grid(row=0, column=0, sticky=tk.E, padx=5, pady=5)
    self.selectPlaySpeeds['values'] = ('Real-Time', 'Fast', 'Fast 2x', 'Fast 4x', 'Fast 10x', 'Fast 25x')
    buttonPlay = ttk.Button(playbackFrame, text='Play', command=self.play)
    buttonPlay.grid(row=0, column=1, sticky=tk.EW, padx=5, pady=5)
    buttonStop = ttk.Button(playbackFrame, text='Stop', command=self.stop)
    buttonStop.grid(row=0, column=2, sticky=tk.W, padx=5, pady=5)
    self.labelDistance = ttk.Label(playbackFrame, text='')
    self.labelDistance.grid(row=0, column=3, sticky=tk.W, padx=5, pady=5)
    self.labelAltitude = ttk.Label(playbackFrame, text='')
    self.labelAltitude.grid(row=0, column=4, sticky=tk.W, padx=5, pady=5)
    self.labelSpeed = ttk.Label(playbackFrame, text='')
    self.labelSpeed.grid(row=0, column=5, sticky=tk.W, padx=5, pady=5)
    self.labelTimestamp = ttk.Label(playbackFrame, text='')
    self.labelTimestamp.grid(row=0, column=6, sticky=tk.W, padx=5, pady=5)

    fileInfoFrame = ttk.Frame(mapFrame, height=20)
    fileInfoFrame.pack(fill=tk.BOTH, expand=False)
    self.labelMaxDistance = ttk.Label(fileInfoFrame, text='')
    self.labelMaxDistance.grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
    self.labelMaxAltitude = ttk.Label(fileInfoFrame, text='')
    self.labelMaxAltitude.grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)
    self.labelMaxSpeed = ttk.Label(fileInfoFrame, text='')
    self.labelMaxSpeed.grid(row=0, column=2, sticky=tk.W, padx=5, pady=5)
    self.labelFilename = ttk.Label(fileInfoFrame, text='')
    self.labelFilename.grid(row=0, column=3, sticky=tk.W, padx=5, pady=5)

    self.reset();


if __name__ == '__main__':
  extract = ExtractFlightData()
  extract.mainloop()
