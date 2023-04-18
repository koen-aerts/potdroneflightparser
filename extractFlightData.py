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

#import pandas as pd

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
  defaultDroneZoom = 18
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


  '''
  Calculate distance between 2 sets of coordinates (lat/lon). Note: Can't find the distance in the flight data itself.
  '''
  def haversine(self, lat1: float, long1: float, lat2: float, long2: float):
    degree_to_rad = float(pi / 180.0)
    d_lat = (lat2 - lat1) * degree_to_rad
    d_long = (long2 - long1) * degree_to_rad
    a = pow(sin(d_lat / 2), 2) + cos(lat1 * degree_to_rad) * cos(lat2 * degree_to_rad) * pow(sin(d_long / 2), 2)
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    km = 6367 * c
    #mi = 3956 * c
    return km


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
    self.zipFilename = None


  '''
  Update drone/home markers on the map as well as other labels with flight information.
  '''
  def setMarkers(self, row):
    item = self.tree.item(row)
    record = item['values']
    homelat = float(record[2])
    homelon = float(record[3])
    dronelat = float(record[4])
    dronelon = float(record[5])
    if (self.homemarker):
      self.homemarker.set_position(homelat, homelon)
    else:
      self.homemarker = self.map_widget.set_marker(homelat, homelon, text=self.homelabel)
    if (self.dronemarker):
      self.dronemarker.set_position(dronelat, dronelon)
    else:
      self.dronemarker = self.map_widget.set_marker(dronelat, dronelon, text=self.dronelabel)
    self.labelTimestamp['text'] = 'Time: ' + record[0]
    self.labelDistance['text'] = 'Distance: ' + str(record[1])


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
      f.write("Timestamp,Distance (m),Home Lat,Home Lon,Drone Lat,Drone Lon")
      for rowid in self.tree.get_children():
        vals = self.tree.item(rowid)['values']
        f.write("\n"+str(vals[0])+","+str(vals[1])+","+str(vals[2])+","+str(vals[3])+","+str(vals[4])+","+str(vals[5]))
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

    '''
    timestampDict = {};
    files = glob.glob(os.path.join(binLog, '**/*-FPV.bin'), recursive=True)
    for file in files:
      print("FILE: " + file);
      totalFCRecords = 0;
      totOnRecs = 0;
      with open(file, mode='rb') as fpvFile:
        recordCount = 0;
        while True:
          fpvRecord = fpvFile.readline().decode("utf-8");
          if not fpvRecord:
            break
          recordCount+=1;
          vals = fpvRecord.split(" ");
          #packets = int(vals[1][0:8], 16);
          #if (vals[1][7:8] == '7'):
          #  totOnRecs+=1;
          #  packets = int(vals[1][0:8], 16);
          #else:
          #  packets = 0;
          #packets = int(vals[1][2:4], 16);
          timestampDict[vals[0]] = packets;
          #totalFCRecords += packets;
          #print("Line{}: {} {}".format(recordCount, fpvRecord.strip(), packets))
      fpvFile.close();
      #print("Total FC Records: {}".format(totalFCRecords))
      #print("Total FC rec ON: {}".format(totOnRecs))
    '''


    # Read the Flight Status files.
    files = sorted(glob.glob(os.path.join(binLog, '**/*-FC.bin'), recursive=True))
    #df = pd.DataFrame([[i] for i in range(512)], columns =['idx']);
    timestampMarkers = []

    # First grab timestamps from the filenames. Those are used to calculate the real timestamps with the elapsed time from each record.
    for file in files:
      timestampMarkers.append(datetime.datetime.strptime(re.sub("-.*", "", Path(file).stem), '%Y%m%d%H%M%S'))

    filenameTs = timestampMarkers[0]
    prevReadingTs = timestampMarkers[0]
    for file in files:
      with open(file, mode='rb') as flightFile:
        prevElapsed = 0
        while True:
          fcRecord = flightFile.read(512)
          if (len(fcRecord) < 512):
            break

          recordCount = struct.unpack('<I', fcRecord[0:4])[0] # not sure if this is 2 bytes or 4 bytes.
          elapsed = struct.unpack('<Q', fcRecord[5:13])[0]
          dronelat = struct.unpack('<i', fcRecord[53:57])[0]/10000000
          dronelon = struct.unpack('<i', fcRecord[57:61])[0]/10000000
          homelat = struct.unpack('<i', fcRecord[159:163])[0]/10000000
          homelon = struct.unpack('<i', fcRecord[163:167])[0]/10000000
          dist = round(self.haversine(homelat, homelon, dronelat, dronelon) * 1000, 4) # Don't know if distance is recorded in the data somewhere.
          if (dist > 10000):
            # Weed out unrealistic distances, for instance due to invalid GPS coordinates.
            dist = 0

          # Line up to the next valid timestamp marker (pulled from the filenames).
          if (elapsed < prevElapsed):
            while (timestampMarkers[0] < prevReadingTs):
              timestampMarkers.pop(0)
            filenameTs = timestampMarkers.pop(0)

          readingTs = filenameTs + datetime.timedelta(milliseconds=(elapsed/1000))
          prevElapsed = elapsed
          prevReadingTs = readingTs
          self.tree.insert('', tk.END, value=(str(readingTs), str(dist), str(homelat), str(homelon), str(dronelat), str(dronelon)))
          if (sethome and dist > 0):
            self.dronelabel = re.sub(r"[0-9]*-(.*)\.[^\.]*", r"\1", PurePath(selectedFile).name)
            self.map_widget.set_zoom(self.defaultDroneZoom)
            self.map_widget.set_position(homelat, homelon)
            self.homemarker = self.map_widget.set_marker(homelat, homelon, text=self.homelabel)
            sethome = False

          '''
          if (dist > 0 and dist < 700 and recordCount % 5 == 0):
            #print("    " + str(recordCount) + " -- " + str(readingTs) + " -- " + str(elapsed) + " -- " + str(dist) + " -- " + str(homelat) + " ; " + str(homelon) + " ; " + str(dronelat) + " ; " + str(dronelon));
            if (df.shape[1] < 20):
              mycol = {}
              for i in range(505):
                if (i == 0):
                  number = dist;
                elif (i == 1):
                  number = 0; #dist * 39.37008;
                elif (i == 2):
                  number = 0; #dist * 3.28084;
                else:
                  #number = int.from_bytes(fcRecord[i:8+i], "little", signed=False);
                  #number = round(struct.unpack('<f', fcRecord[i:4+i])[0], 2);
                  number = struct.unpack('<Q', fcRecord[i:8+i])[0];
                  #number = struct.unpack('<I', fcRecord[i:4+i])[0];
                  #number = struct.unpack('<L', fcRecord[i:4+i])[0];
                  #number = struct.unpack('<H', fcRecord[i:2+i])[0];
                  #number = struct.unpack('<B', fcRecord[i:1+i])[0];
                mycol[i] = str(number);
              df[str(recordCount)] = df['idx'].map(mycol);
          '''

      flightFile.close()

    '''    
    for i in range(df.shape[1]-1, 0, -1):
      if (i > 1):
        for j in range(df.shape[0]):
          #print("'"+str(df.iat[j,i-1])+"'")
          if (str(df.iat[j,i-1]) != "nan" and str(df.iat[j,i]) != "nan"):
            if (float(df.iat[j,i-1]) != 0):
              df.iat[j,i] = str(round(float(df.iat[j,i]) / float(df.iat[j,i-1]), 2));
          #print(str(df.iloc[j,i]))
          #df[i][j] = df[i][j] / df[i-1][j];
    print(df.to_string());
    '''

    shutil.rmtree(binLog)


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
    self.geometry('800x600')
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
    
    columns = ('timestamp','distance','homelat','homelon','dronelat','dronelon')
    self.tree = ttk.Treeview(dataFrame, columns=columns, show='headings')
    self.tree.heading('timestamp', text='Timestamp')
    self.tree.heading('distance', text='Distance (m)')
    self.tree.heading('homelat', text='Home Lat')
    self.tree.heading('homelon', text='Home Lon')
    self.tree.heading('dronelat', text='Drone Lat')
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

    playbackFrame = ttk.Frame(mapFrame, height=60)
    playbackFrame.pack(fill=tk.BOTH, expand=False)
    self.selectPlaySpeeds = ttk.Combobox(playbackFrame, textvariable=tk.StringVar())
    self.selectPlaySpeeds.grid(row=0, column=0, sticky=tk.E, padx=5, pady=5)
    self.selectPlaySpeeds['values'] = ('Real-Time', 'Fast', 'Fast 2x', 'Fast 4x', 'Fast 10x', 'Fast 25x')
    buttonPlay = ttk.Button(playbackFrame, text='Play', command=self.play)
    buttonPlay.grid(row=0, column=1, sticky=tk.EW, padx=5, pady=5)
    buttonStop = ttk.Button(playbackFrame, text='Stop', command=self.stop)
    buttonStop.grid(row=0, column=2, sticky=tk.W, padx=5, pady=5)
    self.labelTimestamp = ttk.Label(playbackFrame, text='')
    self.labelTimestamp.grid(row=0, column=3, sticky=tk.W, padx=5, pady=5)
    self.labelDistance = ttk.Label(playbackFrame, text='')
    self.labelDistance.grid(row=0, column=4, sticky=tk.W, padx=5, pady=5)

    self.reset();


if __name__ == '__main__':
  extract = ExtractFlightData()
  extract.mainloop()
