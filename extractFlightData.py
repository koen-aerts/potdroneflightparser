import glob
import os
import sys
import shutil
import struct
import tempfile
import re
import datetime

import pandas as pd

from pathlib import Path
from zipfile import ZipFile
from math import pi,sqrt,sin,cos,atan2,modf

def haversine(lat1: float, long1: float, lat2: float, long2: float):
    degree_to_rad = float(pi / 180.0)
    d_lat = (lat2 - lat1) * degree_to_rad
    d_long = (long2 - long1) * degree_to_rad
    a = pow(sin(d_lat / 2), 2) + cos(lat1 * degree_to_rad) * cos(lat2 * degree_to_rad) * pow(sin(d_long / 2), 2)
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    km = 6367 * c
    #mi = 3956 * c
    return km

def main() -> int:
  if (len(sys.argv) < 2):
    print("Require filename to the Potensic Flight Log zip file.");
    return -1;

  zipFile = Path(sys.argv[1]);
  if (not zipFile.is_file()):
    print("Not a valid file specified.");
    return -1;

  binLog = os.path.join(tempfile.gettempdir(), "flightdata");

  with ZipFile(sys.argv[1], 'r') as unzip:
    unzip.extractall(path=binLog)

  # Read the Flight Status files.
  files = sorted(glob.glob(os.path.join(binLog, '**/*-FC.bin'), recursive=True))
  #df = pd.DataFrame([[i] for i in range(512)], columns =['idx']);
  timestampMarkers = [];

  # First grab timestamps from the filenames. Those are used to calculate the real timestamps with the elapsed time from each record.
  for file in files:
    timestampMarkers.append(datetime.datetime.strptime(re.sub("-.*", "", Path(file).stem), '%Y%m%d%H%M%S'));

  print("Timestamp,Distance (m),Home Lat,Home Lon,Drone Lat,Drone Lon");
  filenameTs = timestampMarkers[0];
  prevReadingTs = timestampMarkers[0];
  for file in files:
    with open(file, mode='rb') as flightFile:
      prevElapsed = 0;
      while True:
        fcRecord = flightFile.read(512);
        if (len(fcRecord) < 512):
          break;

        recordCount = struct.unpack('<I', fcRecord[0:4])[0]; # not sure if this is 2 bytes or 4 bytes.
        elapsed = struct.unpack('<Q', fcRecord[5:13])[0];
        dronelat = struct.unpack('<i', fcRecord[53:57])[0]/10000000;
        dronelon = struct.unpack('<i', fcRecord[57:61])[0]/10000000;
        homelat = struct.unpack('<i', fcRecord[159:163])[0]/10000000;
        homelon = struct.unpack('<i', fcRecord[163:167])[0]/10000000;
        dist = round(haversine(homelat, homelon, dronelat, dronelon) * 1000, 4); # Don't know if distance is recorded in the data somewhere.
        if (dist > 10000):
          # Weed out unrealistic distances, for instance due to invalid GPS coordinates.
          dist = 0;

        # Line up to the next valid timestamp marker (pulled from the filenames).
        if (elapsed < prevElapsed):
          while (timestampMarkers[0] < prevReadingTs):
            timestampMarkers.pop(0);
          filenameTs = timestampMarkers.pop(0);

        readingTs = filenameTs + datetime.timedelta(milliseconds=(elapsed/1000));
        prevElapsed = elapsed;
        prevReadingTs = readingTs;
        #print("    " + str(recordCount) + " -- " + str(readingTs) + " -- " + str(elapsed) + " -- " + str(dist) + " -- " + str(homelat) + " ; " + str(homelon) + " ; " + str(dronelat) + " ; " + str(dronelon));
        print(str(readingTs) + "," + str(dist) + "," + str(homelat) + "," + str(homelon) + "," + str(dronelat) + "," + str(dronelon));

    flightFile.close();

  shutil.rmtree(binLog);

  return 0;

if __name__ == '__main__':
  sys.exit(main())
