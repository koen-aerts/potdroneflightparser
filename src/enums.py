'''
enums - Developer: Koen Aerts
'''
from enum import Enum

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
