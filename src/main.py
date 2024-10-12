'''
Main app with UI logic - Developers: Koen Aerts, Rob Pritt
'''
import os
import subprocess
import glob
import shutil
import math
import datetime
import tempfile
import time
import re
import threading
import locale
import gettext
import json
import requests
import webbrowser

from enums import DroneStatus, FlightMode, SelectableTileServer
from exports import ExportCsv, ExportKml
from widgets import SplashScreen, MaxDistGraph, TotDistGraph, TotDurationGraph
from common import Common
from parser import AtomBaseLogParser, DreamerBaseLogParser
from db import Db
from pathlib import Path
from zipfile import ZipFile
from PIL import Image as PILImage

from kivy.core.window import Window
Window.allow_screensaver = False

from kivy.clock import mainthread, Clock
from kivy.config import Config
from kivy.metrics import dp
from kivy.uix.widget import Widget
from kivy.utils import platform
from kivymd.app import MDApp
from kivymd.uix.button import MDButton, MDButtonText, MDIconButton
from kivymd.uix.dialog import MDDialog, MDDialogHeadlineText, MDDialogButtonContainer, MDDialogContentContainer
from kivymd.uix.gridlayout import MDGridLayout
from kivymd.uix.label import MDLabel
from kivymd.uix.menu import MDDropdownMenu
from kivymd.uix.progressindicator.progressindicator import MDCircularProgressIndicator
from kivymd.uix.screen import MDScreen
from kivymd.uix.snackbar import MDSnackbar, MDSnackbarText
from kivy_garden.mapview import MapSource, MapMarker, MapMarkerPopup, MarkerMapLayer
from kivy_garden.mapview.geojson import GeoJsonMapLayer
from kivy_garden.mapview.utils import haversine

# Platform specific imports.
if platform == 'android': # Android
    from android.permissions import request_permissions, Permission
    from androidstorage4kivy import SharedStorage, Chooser, ShareSheet
    class MyChooser(Chooser): # override chooser to fix black screen issue when cancelling the dialog.
        def __init__(self, callback = None, **kwargs):
            super().__init__(callback, **kwargs)
        def intent_callback(self, requestCode, resultCode, intent):
            super().intent_callback(requestCode, resultCode, intent)
            if resultCode != -1: # on_resume event not triggered when the dialog is cancelled without selecting a file.
                self.callback([])
    from platformdirs import user_config_dir, user_data_dir, user_cache_dir
elif platform == 'ios': # iOS
    from plyer import storagepath
else: # Windows, MacOS, Linux
    os.chdir(os.path.dirname(os.path.realpath(__file__)))
    Window.maximize()
    from plyer import filechooser
    from platformdirs import user_config_dir, user_data_dir, user_cache_dir


class BaseScreen(MDScreen):
    ...


class MainApp(MDApp):

    # Global variables and constants.
    appVersion = "v2.4.0"
    appName = "Flight Log Viewer"
    appPathName = "FlightLogViewer"
    appTitle = f"{appName} - {appVersion}"
    defaultMapZoom = 3
    pathWidths = [ "1.0", "1.5", "2.0", "2.5", "3.0" ]
    refreshRates = ['0.125s', '0.25s', '0.50s', '1.00s', '1.50s', '2.00s']
    assetColors = [ "#ed1c24", "#0000ff", "#22b14c", "#7f7f7f", "#ffffff", "#c3c3c3", "#000000", "#ffff00", "#a349a4", "#aad2fa" ]
    columns = ('recnum', 'recid', 'flight','timestamp','tod','time','distance1','dist1lat','dist1lon','distance2','dist2lat','dist2lon','distance3','altitude1','altitude2','altitude2metric','speed1','speed1lat','speed1lon','speed2','speed2lat','speed2lon','speed1vert','speed2vert','satellites','ctrllat','ctrllon','homelat','homelon','dronelat','dronelon','orientation1','orientation2','roll','winddirection','motor1status','motor2status','motor3status','motor4status','motorstatus','dronestatus','droneaction','rssi','channel','flightctrlconnected','remoteconnected','droneconnected','rth','positionmode','gps','inuse','traveled','batterylevel','batterytemp','batterycurrent','batteryvoltage','batteryvoltage1','batteryvoltage2','flightmode','flightcounter')
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


    def parse_atom_logs(self, importRef):
        parser = AtomBaseLogParser(self)
        parser.parse(importRef)
        mainthread(self.show_flight_date)(importRef)
        mainthread(self.show_flight_stats)()
        mainthread(self.init_gauges)()


    def parse_dreamer_logs(self, importRef):
        parser = DreamerBaseLogParser(self)
        parser.parse(importRef)
        mainthread(self.show_flight_date)(importRef)
        mainthread(self.show_flight_stats)()
        mainthread(self.init_gauges)()


    def show_flight_date(self, importRef):
        logDate = re.sub(r"-.*", r"", importRef) # Extract date section from log (zip) filename.
        self.root.ids.value_date.text = datetime.date.fromisoformat(logDate).strftime("%x")


    def show_flight_stats(self):
        self.root.ids.map_title.text = self.zipFilename
        self.root.ids.flights_title.text = self.zipFilename
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
            self.root.ids.flight_stats_grid.add_widget(MDLabel(text=f"{self.common.fmt_num(self.common.dist_val(self.flightStats[i][9]))} {self.common.dist_unit()}", max_lines=1, halign="right", valign="center"))
            self.root.ids.flight_stats_grid.add_widget(MDLabel(text=f"{self.common.fmt_num(self.common.dist_val(self.flightStats[i][0]))} {self.common.dist_unit()}", max_lines=1, halign="right", valign="center"))
            self.root.ids.flight_stats_grid.add_widget(MDLabel(text=f"{self.common.fmt_num(self.common.dist_val(self.flightStats[i][1]))} {self.common.dist_unit()}", max_lines=1, halign="right", valign="center"))
            self.root.ids.flight_stats_grid.add_widget(MDLabel(text=f"{self.common.fmt_num(self.common.speed_val(self.flightStats[i][2]))} {self.common.speed_unit()}", max_lines=1, halign="right", valign="center"))
            self.root.ids.flight_stats_grid.add_widget(MDLabel(text=f"{self.common.fmt_num(self.common.speed_val(self.flightStats[i][8]))} {self.common.speed_unit()}", max_lines=1, halign="right", valign="center", padding=[0,0,dp(10),0]))


    def initiate_import_file(self, selectedFile):
        '''
        Import the selected Flight Data Zip file.
        '''
        if not os.path.isfile(selectedFile):
            self.show_error_message(message=_('no_valid_file_specified').format(filename=selectedFile))
            return
        zipBaseName = os.path.basename(selectedFile)
        droneModel = re.sub(r"[0-9]*-(.*)-Drone.*", r"\1", zipBaseName) # Pull drone model from zip filename.
        droneModel = re.sub(r"[^\w]", r" ", droneModel) # Remove non-alphanumeric characters from the model name.
        lcDM = droneModel.lower()
        if 'p1a' in lcDM or 'atom' in lcDM:
            already_imported = self.db.execute("SELECT importedon FROM imports WHERE importref = ?", (zipBaseName,))
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
        shutil.rmtree(self.tempDir, ignore_errors=True) # Delete old temp files if they were missed before.
        with ZipFile(selectedFile, 'r') as unzip:
            unzip.extractall(path=self.tempDir)
        for binFile in glob.glob(os.path.join(self.tempDir, '**/*'), recursive=True):
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
                        self.db.execute("INSERT OR IGNORE INTO models(modelref) VALUES(?)", (droneModel,))
                        self.db.execute(
                            "INSERT OR IGNORE INTO imports(importref, modelref, dateref, importedon) VALUES(?,?,?,?)",
                            (zipBaseName, droneModel, logDate, datetime.datetime.now().isoformat())
                        )
                        hasFc = True
                    shutil.copyfile(binFile, os.path.join(self.logfileDir, binBaseName))
                    self.db.execute(
                        "INSERT INTO log_files(filename, importref, bintype) VALUES(?,?,?)",
                        (binBaseName, zipBaseName, binType)
                    )
        if hasFc:
            # Once we have FC bin/fc files, we will also import FVP files as well.
            for fpvFile in fpvList:
                fpvBaseName = os.path.basename(fpvFile)
                shutil.copyfile(fpvFile, os.path.join(self.logfileDir, fpvBaseName))
                self.db.execute(
                    "INSERT INTO log_files(filename, importref, bintype) VALUES(?,?,?)",
                    (fpvBaseName, zipBaseName, "FPV")
                )
        shutil.rmtree(self.tempDir, ignore_errors=True) # Delete temp files.
        if hasFc:
            self.show_info_message(message=_('log_import_completed'))
            self.map_rebuild_required = False
            mainthread(self.open_view)("Screen_Map")
            if ('p1a' in lcDM):
                self.parse_dreamer_logs(zipBaseName)
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


    def post_import_cleanup(self, selectedFile):
        '''
        Delete the import zip file. Applies to iOS only.
        '''
        if self.is_ios:
            os.remove(selectedFile)


    def ios_doc_path(self):
        return storagepath.get_documents_dir()[7:] # remove "file://" from URL to create a Python-friendly path.


    def open_file_import_dialog(self):
        '''
        Open a file import dialog (import zip file).
        '''
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


    def open_csv_file_export_dialog(self):
        '''
        Open a file export dialog (export csv file).
        '''
        csvFilename = re.sub(r"\.zip$", "", self.zipFilename) + ".csv"
        export = ExportCsv(columnnames=self.columns, rows=self.logdata)
        if self.is_android:
            csvFile = os.path.join(self.shared_storage.get_cache_dir(), csvFilename)
            try:
                export.save(csvFile)
                url = self.shared_storage.copy_to_shared(csvFile)
                ShareSheet().share_file(url)
                self.show_info_message(message=_('data_exported_to').format(filename=csvFile))
            except Exception as e:
                msg = _('error_saving_export_csv').format(filename=csvFile, error=e)
                print(f"{msg}: {e}")
                self.show_error_message(message=msg)
        elif self.is_ios:
            csvFile = os.path.join(self.ios_doc_path(), csvFilename)
            try:
                export.save(csvFile)
                self.show_info_message(message=_('export_csv_file_saved').format(filename=csvFile))
            except Exception as e:
                msg = _('error_saving_export_csv').format(filename=csvFile, error=e)
                print(f"{msg}: {e}")
                self.show_error_message(message=msg)
        elif self.is_windows: # For windows, use "save_file" interface in plyer filechooser.
            oldwd = os.getcwd() # Remember current workdir. Windows File Explorer is nasty and changes it, causing all sorts of mapview issues.
            myFiles = filechooser.save_file(title=_('save_export_csv_file'), filters=["*.csv"], path=csvFilename)
            newwd = os.getcwd()
            if oldwd != newwd:
                os.chdir(oldwd) # Change it back!
            if myFiles and len(myFiles) > 0:
                try:
                    export.save(myFiles[0])
                    self.show_info_message(message=_('data_exported_to').format(filename=myFiles[0]))
                except Exception as e:
                    msg = _('error_saving_export_csv').format(filename=myFiles[0], error=e)
                    print(f"{msg}: {e}")
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
                    export.save(csvFile)
                    self.show_info_message(message=_('data_exported_to').format(filename=csvFile))
                except Exception as e:
                    msg = _('error_saving_export_csv').format(filename=csvFile, error=e)
                    print(f"{msg}: {e}")
                    self.show_error_message(message=msg)


    def open_kml_file_export_dialog(self):
        '''
        Open a file export dialog (export KML file).
        '''
        kmlFilename = re.sub(r"\.zip$", "", self.zipFilename) + ".kml"
        export = ExportKml(
            commonlib=self.common,
            columnnames=self.columns,
            rows=self.logdata,
            name=f"{self.root.ids.selected_model.text} logs of {self.root.ids.value_date.text}",
            description=f'Logfile: {self.zipFilename}<br><br>Exported: {datetime.datetime.now().isoformat()}<br><br>{ExportKml.appRef}',
            pathcolor=self.assetColors[int(self.root.ids.selected_flight_path_color.value)],
            pathwidth=self.pathWidths[int(self.root.ids.selected_flight_path_width.value)],
            homecolorref=str(int(self.root.ids.selected_marker_home_color.value)+1),
            ctrlcolorref=str(int(self.root.ids.selected_marker_ctrl_color.value)+1),
            dronecolorref=str(int(self.root.ids.selected_marker_drone_color.value)+1),
            flightstarts=self.flightStarts,
            flightends=self.flightEnds,
            flightstats=self.flightStats,
            uom=self.root.ids.selected_uom.text
        )
        if self.is_android:
            kmlFile = os.path.join(self.shared_storage.get_cache_dir(), kmlFilename)
            try:
                export.save(kmlFile)
                url = self.shared_storage.copy_to_shared(kmlFile)
                ShareSheet().share_file(url)
                self.show_info_message(message=_('data_exported_to').format(filename=kmlFile))
            except Exception as e:
                msg = _('error_saving_export_kml').format(filename=kmlFile, error=e)
                print(f"{msg}: {e}")
                self.show_error_message(message=msg)
        elif self.is_ios:
            kmlFile = os.path.join(self.ios_doc_path(), kmlFilename)
            try:
                export.save(kmlFile)
                self.show_info_message(message=_('export_kml_file_saved').format(filename=kmlFile))
            except Exception as e:
                msg = _('error_saving_export_kml').format(filename=kmlFile, error=e)
                print(f"{msg}: {e}")
                self.show_error_message(message=msg)
        elif self.is_windows: # For windows, use "save_file" interface in plyer filechooser.
            oldwd = os.getcwd() # Remember current workdir. Windows File Explorer is nasty and changes it, causing all sorts of mapview issues.
            myFiles = filechooser.save_file(title=_('save_export_kml_file'), filters=["*.kml"], path=kmlFilename)
            newwd = os.getcwd()
            if oldwd != newwd:
                os.chdir(oldwd) # Change it back!
            if myFiles and len(myFiles) > 0:
                try:
                    export.save(myFiles[0])
                    self.show_info_message(message=_('data_exported_to').format(filename=myFiles[0]))
                except Exception as e:
                    msg = _('error_saving_export_kml').format(filename=myFiles[0], error=e)
                    print(f"{msg}: {e}")
                    self.show_error_message(message=msg)
        else: # For non-windows, use "choose_dir" interface in plyer filechooser because plyer does currently not set the desired filename.
            oldwd = os.getcwd() # Remember current workdir. Windows File Explorer is nasty and changes it, causing all sorts of mapview issues.
            myFiles = filechooser.choose_dir(title=_('save_export_kml_file'))
            newwd = os.getcwd()
            if oldwd != newwd:
                os.chdir(oldwd) # Change it back!
            if myFiles and len(myFiles) > 0 and os.path.isdir(myFiles[0]):
                kmlFile = os.path.join(myFiles[0], kmlFilename)
                try:
                    export.save(kmlFile)
                    self.show_info_message(message=_('data_exported_to').format(filename=kmlFile))
                except Exception as e:
                    msg = _('error_saving_export_kml').format(filename=kmlFile, error=e)
                    print(f"{msg}: {e}")
                    self.show_error_message(message=msg)


    def import_android_chooser_callback(self, uri_list):
        '''
        File Chooser, called when a file has been selected on the Android device.
        '''
        try:
            for uri in uri_list:
                self.chosenFile = self.shared_storage.copy_from_shared(uri) # copy to private storage
                break # Only open the first file from the selection.
        except Exception as e:
            print(f"File Chooser Error: {e}")
        self.chooser_open = False


    def open_mapsource_selection(self, item):
        '''
        Map Source dropdown functions.
        '''
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
        self.root.ids.waymap.map_source = mapSource


    def generate_map_layers(self):
        '''
        Called when checkbox for Path view is selected (to show or hide drone path on the map).
        '''
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


    def clear_map(self):
        '''
        Clear out the Map. Remove all markers, flight paths and layers.
        '''
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


    def init_map_layers(self):
        '''
        Build layers on the Map with markers and flight paths.
        '''
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
        self.root.ids.HSPDgauge.display_unit = self.common.speed_unit()
        self.root.ids.VSPDgauge.display_unit = self.common.speed_unit()
        self.root.ids.ALgauge.display_unit = self.common.dist_unit()
        self.root.ids.DSgauge.display_unit = self.common.dist_unit()


    def zoom_to_fit(self):
        '''
        Zooms the map so that the entire flight path will fit.
        '''
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


    def center_map(self):
        '''
        Center the map at the last known center point.
        '''
        if self.flightOptions and len(self.flightOptions) > 0:
            self.zoom_to_fit()
        else:
            self.root.ids.map.center_on(self.centerlat, self.centerlon)


    def map_zoom(self, zoomin):
        '''
        Zoom in/out when the zoom buttons on the map are selected. Only for desktop view.
        '''
        if zoomin:
            if self.root.ids.map.zoom < self.root.ids.map.map_source.max_zoom:
                self.root.ids.map.zoom = self.root.ids.map.zoom + 1
        else:
            if self.root.ids.map.zoom > self.root.ids.map.map_source.min_zoom:
                self.root.ids.map.zoom = self.root.ids.map.zoom - 1


    def open_view(self, view_name):
        self.root.ids.screen_manager.current = view_name


    def entered_screen_map(self):
        '''
        Called when map screen is opened.
        '''
        self.app_view = "map"
        if self.map_rebuild_required:
            self.clear_map()
            self.generate_map_layers()
            self.init_map_layers()
            self.set_markers()
            self.map_rebuild_required = False


    def left_screen_map(self):
        '''
        Called when map screen is navigated away from.
        '''
        self.stop_flight()
        self.map_rebuild_required = False


    def entered_screen_summary(self):
        '''
        Called when flight summary screen is opened.
        '''
        self.app_view = "sum"


    def entered_screen_log(self):
        '''
        Called when log file screen is opened.
        '''
        self.app_view = "log"


    def entered_screen_gstats(self):
        '''
        Called when global stats screen is opened.
        '''
        self.app_view = "gstats"
        self.generate_gstat_graphs()


    def close_gstats_screen(self):
        '''
        Called when global stats screen is closed.
        '''
        self.open_view("Screen_Log_Files")
        self.destroy_gstat_graphs()


    def entered_screen_waypoints(self):
        '''
        Called when map screen is opened.
        '''
        self.app_view = "waypoints"


    def close_waypoints_screen(self):
        '''
        Called when waypoints screen is closed.
        '''
        shutil.rmtree(self.tempDir, ignore_errors=True) # Delete temp files.
        self.potdb = None
        self.waypoints = None
        self.remove_waylayer()
        self.root.ids.btn_retrieve_waypoints.disabled = False
        self.root.ids.btn_save_waypoints.disabled = True
        self.root.ids.btn_save_waypoints.disabled = True
        self.root.ids.selected_waypoint.disabled = True
        self.root.ids.add_waypoint_marker.disabled = True
        self.root.ids.add_waypoint_path.disabled = True
        self.root.ids.delete_waypoint_path.disabled = True
        self.root.ids.adb_output.text = ""
        self.root.ids.selected_waypoint.text = "--"
        self.open_view("Screen_Log_Files")


    def left_screen_waypoints(self):
        '''
        Called when map screen is navigated away from.
        '''


    def entered_screen_loading(self):
        '''
        Called when loading screen is opened.
        '''
        self.app_view = "loading"


    def close_map_screen(self):
        '''
        Called when map screen is closed.
        '''
        self.reset()
        self.open_view("Screen_Log_Files")


    def set_markers(self, updateSlider=True):
        '''
        Update ctrl/home/drone markers on the map as well as other labels with flight information.
        '''
        if not self.currentRowIdx:
            return
        record = self.logdata[self.currentRowIdx]
        rthDesc = "RTH" if record[self.columns.index('rth')] == 1 else ''
        batteryLevel = record[self.columns.index('batterylevel')]
        batLevelRnd = math.floor(batteryLevel / 10 + 0.5) * 10 # round to nearest 10.
        batteryTemp = record[self.columns.index('batterytemp')]
        batteryVoltage = locale.format_string("%.1f", round(record[self.columns.index('batteryvoltage')], 1), grouping=True, monetary=False)
        batteryCurrent = locale.format_string("%.1f", round(record[self.columns.index('batterycurrent')]/1000, 1), grouping=True, monetary=False)
        flightMode = record[self.columns.index('flightmode')]
        dronestatus = record[self.columns.index('dronestatus')]

        self.root.ids.value1_alt.text = f"{record[self.columns.index('altitude2')]} {self.common.dist_unit()}"
        self.root.ids.value1_traveled.text = f"{record[self.columns.index('traveled')]} {self.common.dist_unit()}"
        self.root.ids.value1_traveled_short.text = f"({self.common.shorten_dist_val(record[self.columns.index('traveled')])} {self.common.dist_unit_km()})"
        self.root.ids.value1_flightmode.text = flightMode
        self.root.ids.value1_dist.text = f"{record[self.columns.index('distance3')]} {self.common.dist_unit()}"
        self.root.ids.value1_hspeed.text = f"{record[self.columns.index('speed2')]} {self.common.speed_unit()}"
        self.root.ids.value1_vspeed.text = f"{record[self.columns.index('speed2vert')]} {self.common.speed_unit()}"

        self.root.ids.value1_batterylevel1.text = f"{record[self.columns.index('batterylevel')]}% / {batteryVoltage}V"
        self.root.ids.value1_batterylevel2.text = f"{batteryTemp}C / {batteryCurrent}A"
        self.root.ids.value1_rth_desc.text = dronestatus if len(rthDesc) == 0 else rthDesc
        elapsed = record[5]
        elapsed = elapsed - datetime.timedelta(microseconds=elapsed.microseconds) # truncate to milliseconds
        self.root.ids.value1_elapsed.text = str(elapsed)

        self.root.ids.battery_level.icon = "battery" if batLevelRnd == 100 else f"battery-{batLevelRnd}"
        self.root.ids.battery_level.icon_color = "red" if batteryLevel < 30 else "orange" if batteryLevel < 65 else "green"
        self.root.ids.flight_mode.icon = "alpha-v-box" if flightMode == FlightMode.VIDEO.value else "alpha-s-box" if flightMode == FlightMode.SPORT.value else "alpha-n-box" if flightMode == FlightMode.NORMAL.value else "crosshairs-question"
        self.root.ids.flight_mode.icon_color = "green" if flightMode == FlightMode.VIDEO.value else "orange" if flightMode == FlightMode.SPORT.value else "blue" if flightMode == FlightMode.NORMAL.value else "red"
        self.root.ids.drone_connection.icon = "signal" if record[self.columns.index('droneconnected')] == 1 else "signal-off"
        self.root.ids.drone_connection.icon_color = "green" if record[self.columns.index('droneconnected')] == 1 else "red"
        self.root.ids.drone_action.icon = "airplane-marker" if record[self.columns.index('rth')] == 1 else "airplane-takeoff" if dronestatus == DroneStatus.LIFT.value else "airplane-landing" if dronestatus == DroneStatus.LANDING.value else "airplane" if dronestatus == DroneStatus.FLYING.value else "car-break-parking" if dronestatus == DroneStatus.IDLE.value else "crosshairs-question"
        self.root.ids.drone_action.icon_color = "red" if record[self.columns.index('rth')] == 1 else "orange" if dronestatus == DroneStatus.LIFT.value else "orange" if dronestatus == DroneStatus.LANDING.value else "green" if dronestatus == DroneStatus.FLYING.value else "blue" if dronestatus == DroneStatus.IDLE.value else "red"

        # TODO - Implement later, need new widgets
        #self.root.ids.map_img_roll.source = self.get_roll_icon_source()
        #self.root.ids.map_img_wind.source = self.get_wind_icon_source()

        if self.root.ids.selected_gauges.active:
            # Set horizontal, vertical and altitude gauge values. Use rounded values.
            self.root.ids.HSPDgauge.value = round(locale.atof(record[self.columns.index('speed2')]))
            # "peg out" the gauge if beyond the vertical limits
            if abs(round(locale.atof(record[self.columns.index('speed2vert')])) > 14):
                self.root.ids.VSPDgauge.value = 14
            else: 
                self.root.ids.VSPDgauge.value = round(locale.atof(record[self.columns.index('speed2vert')]))

            self.root.ids.ALgauge.value = round(locale.atof(record[self.columns.index('altitude2')]))
            self.root.ids.DSgauge.value = round(locale.atof(record[self.columns.index('distance3')]))

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
                G_orientation = round(math.degrees(record[self.columns.index('orientation2')])) # Drone orientation in degrees, -180 to 180.
                G_rotation = abs(G_orientation) if G_orientation <= 0 else 360 - G_orientation # Convert to 0 - 359 range.
                self.root.ids.HDgauge.value = G_rotation

        if self.is_desktop:
            self.root.ids.map_metrics_ribbon.text = f" {_('map_time')} {'{:>6}'.format(str(elapsed))[-5:]} | {_('map_dist')} {'{:>9}'.format(record[self.columns.index('distance3')])} {self.common.dist_unit()} | {_('map_alt')} {'{:>6}'.format(record[self.columns.index('altitude2')])} {self.common.dist_unit()} | {_('map_hs')} {'{:>5}'.format(record[self.columns.index('speed2')])} {self.common.speed_unit()} | {_('map_vs')} {'{:>6}'.format(record[self.columns.index('speed2vert')])} {self.common.speed_unit()} | {_('map_sats')} {'{:>2}'.format(record[self.columns.index('satellites')])} | {_('map_distance_flown')} {self.common.shorten_dist_val(record[self.columns.index('traveled')])} {self.common.dist_unit_km()}"
        else:
            self.root.ids.map_metrics_ribbon.text = f" {_('map_time')} {'{:>6}'.format(str(elapsed))[-5:]} | {_('map_dist')} {'{:>9}'.format(record[self.columns.index('distance3')])} {self.common.dist_unit()} | {_('map_alt')} {'{:>6}'.format(record[self.columns.index('altitude2')])} {self.common.dist_unit()} | {_('map_hs')} {'{:>5}'.format(record[self.columns.index('speed2')])} {self.common.speed_unit()} | {_('map_sats')} {'{:>2}'.format(record[self.columns.index('satellites')])} | {_('map_distance_flown')} {self.common.shorten_dist_val(record[self.columns.index('traveled')])} {self.common.dist_unit_km()}"

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
            self.dronemarker.source = self.get_drone_icon_source()
        except:
            ... # Do nothing
        self.root.ids.map.trigger_update(False)


    def set_frame(self):
        '''
        Update ctrl/home/drone markers on the map with the next set of coordinates in the table list.
        '''
        self.root.ids.flight_progress.is_updating = True
        self.isPlaying = True
        self.root.ids.playbutton.icon = "pause"
        refreshRate = float(re.sub(r"[^0-9\.]", "", self.root.ids.selected_refresh_rate.text))
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


    def change_playback_speed(self):
        self.playback_speed = self.playback_speed << 1 if self.playback_speed < 16 else 1
        self.root.ids.speed_indicator.icon = f"numeric-{self.playback_speed}-box" if self.playback_speed < 16 else f"rocket-launch"


    def jump_prev_flight(self):
        '''
        Jump to beginning of current flight, or the end of the previous one.
        '''
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


    def jump_next_flight(self):
        '''
        Jump to end of current flight, or the beginning of the next one.
        '''
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


    def play_flight(self):
        '''
        Start or resume playback of the selected flight. If flight is finished, restart from beginning.
        '''
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


    def stop_flight(self, wait=False):
        '''
        Stop flight playback.
        '''
        if not self.isPlaying:
            return
        self.stopRequested = True
        if wait:
            while (self.isPlaying):
                time.sleep(0.25)


    def flight_path_width_selection(self, slider, coords):
        '''
        Change Flight Path Line Width (Preferences).
        '''
        Config.set('preferences', 'flight_path_width', int(slider.value))
        Config.write()
        self.map_rebuild_required = True


    def flight_path_color_selection(self, slider, coords):
        '''
        Flight Path Colours functions.
        '''
        colorIdx = int(slider.value)
        slider.track_active_color = self.assetColors[colorIdx]
        slider.track_inactive_color = self.assetColors[colorIdx]
        Config.set('preferences', 'flight_path_color', colorIdx)
        Config.write()
        self.map_rebuild_required = True


    def get_drone_icon_source(self):
        '''
        Return reference to the drone icon image. If it needs to be rotated, it will be generated from the base icon image.
        '''
        base_filename = f"Drone-{str(int(self.root.ids.selected_marker_drone_color.value)+1)}"
        if not self.currentRowIdx:
            # Return base image if there is no current rotation (orientation).
            return f"assets/{base_filename}.png"
        record = self.logdata[self.currentRowIdx]
        orientation = round(math.degrees(record[self.columns.index('orientation2')])) # Drone orientation in degrees, -180 to 180.
        rotation = abs(orientation) if orientation <= 0 else 360 - orientation # Convert to 0 - 359 range.
        rotated_filename = os.path.join(self.root.ids.map.cache_dir, f"{base_filename}-{rotation}.png")
        if not os.path.exists(rotated_filename):
            drone_base_icon = PILImage.open(f"assets/{base_filename}.png")
            drone_rotated_icon = drone_base_icon.rotate(rotation, expand=True)
            drone_rotated_icon.save(rotated_filename)
        return rotated_filename


    def get_roll_icon_source(self):
        '''
        Return reference to the roll icon image. If it needs to be rotated, it will be generated from the base icon image.
        '''
        base_filename = f"roll"
        if not self.currentRowIdx:
            # Return base image if there is no current rotation (orientation).
            return f"assets/{base_filename}.png"
        record = self.logdata[self.currentRowIdx]
        orientation = round(math.degrees(record[self.columns.index('roll')])) # Drone roll in degrees, -180 to 180.
        rotation = abs(orientation) if orientation <= 0 else 360 - orientation # Convert to 0 - 359 range.
        rotated_filename = os.path.join(self.root.ids.map.cache_dir, f"{base_filename}-{rotation}.png")
        if not os.path.exists(rotated_filename):
            drone_base_icon = PILImage.open(f"assets/{base_filename}.png")
            drone_rotated_icon = drone_base_icon.rotate(rotation, expand=False)
            drone_rotated_icon.save(rotated_filename)
        return rotated_filename


    def get_wind_icon_source(self):
        '''
        Return reference to the wind direction icon image. If it needs to be rotated, it will be generated from the base icon image.
        '''
        base_filename = f"wind"
        if not self.currentRowIdx:
            # Return base image if there is no current rotation (orientation).
            return f"assets/{base_filename}.png"
        record = self.logdata[self.currentRowIdx]
        orientation = round(math.degrees(record[self.columns.index('winddirection')])) # Wind Direction in degrees, -180 to 180.
        rotation = abs(orientation) if orientation <= 0 else 360 - orientation # Convert to 0 - 359 range.
        rotated_filename = os.path.join(self.root.ids.map.cache_dir, f"{base_filename}-{rotation}.png")
        if not os.path.exists(rotated_filename):
            drone_base_icon = PILImage.open(f"assets/{base_filename}.png")
            drone_rotated_icon = drone_base_icon.rotate(rotation, expand=False)
            drone_rotated_icon.save(rotated_filename)
        return rotated_filename


    def marker_drone_color_selection(self, slider, coords):
        '''
        Drone Marker Colour functions.
        '''
        colorIdx = int(slider.value)
        slider.track_active_color = self.assetColors[colorIdx]
        slider.track_inactive_color = self.assetColors[colorIdx]
        Config.set('preferences', 'marker_drone_color', colorIdx)
        Config.write()
        if self.dronemarker:
            self.dronemarker.source = self.get_drone_icon_source()
            self.set_markers()


    def marker_ctrl_color_selection(self, slider, coords):
        '''
        Controller Marker Colour functions.
        '''
        colorIdx = int(slider.value)
        slider.track_active_color = self.assetColors[colorIdx]
        slider.track_inactive_color = self.assetColors[colorIdx]
        Config.set('preferences', 'marker_ctrl_color', colorIdx)
        Config.write()
        if self.ctrlmarker:
            self.ctrlmarker.source=f"assets/Controller-{str(int(self.root.ids.selected_marker_ctrl_color.value)+1)}.png"
            self.set_markers()


    def marker_home_color_selection(self, slider, coords):
        '''
        Home Marker Colour functions.
        '''
        colorIdx = int(slider.value)
        slider.track_active_color = self.assetColors[colorIdx]
        slider.track_inactive_color = self.assetColors[colorIdx]
        Config.set('preferences', 'marker_home_color', colorIdx)
        Config.write()
        if self.homemarker:
            self.homemarker.source=f"assets/Home-{str(int(self.root.ids.selected_marker_home_color.value)+1)}.png"
            self.set_markers()


    def open_flight_selection(self, item):
        '''
        Flight Path dropdown functions.
        '''
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
            self.root.ids.value1_rth_desc.text = ""
            self.root.ids.value1_batterylevel1.text = ""
            self.root.ids.value1_batterylevel2.text = ""
            self.root.ids.value1_flightmode.text = ""
            self.root.ids.value1_dist.text = ""
            self.root.ids.value1_hspeed.text = ""
            self.root.ids.value1_vspeed.text = ""
            self.root.ids.map_metrics_ribbon.text = ""
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
            self.root.ids.value_maxdist.text = f"{self.common.fmt_num(self.common.dist_val(self.flightStats[flightNum][0]))} {self.common.dist_unit()}"
            self.root.ids.value_maxdist_short.text = f"({self.common.shorten_dist_val(self.common.fmt_num(self.common.dist_val(self.flightStats[flightNum][0])))} {self.common.dist_unit_km()})"
            self.root.ids.value_maxalt.text = f"{self.common.fmt_num(self.common.dist_val(self.flightStats[flightNum][1]))} {self.common.dist_unit()}"
            self.root.ids.value_maxhspeed.text = f"{self.common.fmt_num(self.common.speed_val(self.flightStats[flightNum][2]))} {self.common.speed_unit()}"
            self.root.ids.value_duration.text = str(self.flightStats[flightNum][3])
            self.root.ids.value_tottraveled.text = f"{self.common.fmt_num(self.common.dist_val(self.flightStats[flightNum][9]))} {self.common.dist_unit()}"
            self.root.ids.value_tottraveled_short.text = f"({self.common.shorten_dist_val(self.common.dist_val(self.flightStats[flightNum][9]))} {self.common.dist_unit_km()})"


    def uom_selection(self, item):
        '''
        Change Unit of Measure (Preferences).
        '''
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


    def refresh_rate_selection(self, item):
        '''
        Change Display of Home Marker (Preferences).
        '''
        menu_items = []
        for refreshRate in self.refreshRates:
            menu_items.append({"text": refreshRate, "on_release": lambda x=refreshRate: self.refresh_rate_selection_callback(x)})
        self.refresh_rate_selection_menu = MDDropdownMenu(caller = item, items = menu_items)
        self.refresh_rate_selection_menu.open()
    def refresh_rate_selection_callback(self, text_item):
        self.root.ids.selected_refresh_rate.text = text_item
        self.refresh_rate_selection_menu.dismiss()
        Config.set('preferences', 'refresh_rate', text_item)
        Config.write()


    def home_marker_selection(self, item):
        '''
        Change Display of Home Marker (Preferences).
        '''
        Config.set('preferences', 'show_marker_home', item.active)
        Config.write()
        self.map_rebuild_required = True
        if self.layer_home:
            self.layer_home.opacity = 1 if self.root.ids.selected_home_marker.active else 0


    def ctrl_marker_selection(self, item):
        '''
        Change Display of Controller Marker (Preferences).
        '''
        Config.set('preferences', 'show_marker_ctrl', item.active)
        Config.write()
        self.map_rebuild_required = True
        if self.layer_ctrl:
            self.layer_ctrl.opacity = 1 if self.root.ids.selected_ctrl_marker.active else 0


    def rounding_selection(self, item):
        '''
        Enable or disable rounding of values (Preferences).
        '''
        Config.set('preferences', 'rounded_readings', item.active)
        Config.write()
        self.stop_flight(True)
        self.show_info_message(message=_('reopen_log_for_changes_to_take_effect'))


    def gauges_selection(self, item):
        '''
        Enable or disable analog gauges (Preferences).
        '''
        Config.set('preferences', 'gauges', item.active)
        Config.write()


    def splash_selection(self, item):
        '''
        Enable or disable splash (Preferences).
        '''
        Config.set('preferences', 'splash', item.active)
        Config.write()


    def language_selection(self, item):
        '''
        Change Language (Preferences).
        '''
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


    def model_selection(self, item):
        '''
        Dropdown selection with different drone models determined from the imported log files.
        Model names are slightly inconsistent based on the version of the Potensic app they were generated in.
        '''
        models = self.db.execute("SELECT modelref FROM models ORDER BY modelref")
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


    def list_log_files(self):
        '''
        Retrieve and display all flight logs imported to the app.
        '''
        imports = self.db.execute("""
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
            durVal = "" if importRef[9] is None else f"{self.common.fmt_num(self.common.dist_val(importRef[9]))} {self.common.dist_unit()}"
            self.root.ids.log_files.add_widget(MDLabel(text=durVal, max_lines=1, halign="right", valign="top", role=role))
            durVal = "" if importRef[3] is None else f"{datetime.timedelta(seconds=importRef[3])}"
            self.root.ids.log_files.add_widget(MDLabel(text=durVal, max_lines=1, halign="right", valign="top", role=role))
            distVal = "" if importRef[4] is None else f"{self.common.fmt_num(self.common.dist_val(importRef[5]))} {self.common.dist_unit()}"
            self.root.ids.log_files.add_widget(MDLabel(text=distVal, max_lines=1, halign="right", valign="top", role=role))
            distVal = "" if importRef[5] is None else f"{self.common.fmt_num(self.common.dist_val(importRef[6]))} {self.common.dist_unit()}"
            self.root.ids.log_files.add_widget(MDLabel(text=distVal, max_lines=1, halign="right", valign="top", role=role))
            speedVal = "" if importRef[6] is None else f"{self.common.fmt_num(self.common.speed_val(importRef[7]))} {self.common.speed_unit()}"
            self.root.ids.log_files.add_widget(MDLabel(text=speedVal, max_lines=1, halign="right", valign="center", role=role))
            speedVal = "" if importRef[7] is None else f"{self.common.fmt_num(self.common.speed_val(importRef[8]))} {self.common.speed_unit()}"
            self.root.ids.log_files.add_widget(MDLabel(text=speedVal, max_lines=1, halign="right", valign="center", role=role))
            button2 = MDIconButton(style="standard", icon="delete", on_release=self.open_delete_log_dialog, size=iconsize)
            button2.value = importRef[0]
            self.root.ids.log_files.add_widget(button2)


    def generate_gstat_graphs(self):
        '''
        Generate global statistics from the displayed log files.
        '''
        imports = self.db.execute("""
            SELECT i.importref, i.dateref, count(s.flight_number), sum(duration), max(duration), max(max_distance), max(max_altitude), max(max_h_speed), max(max_v_speed), sum(traveled)
            FROM imports i
            LEFT OUTER JOIN flight_stats s ON s.importref = i.importref
            WHERE modelref = ?
            GROUP BY i.importref, i.dateref
            ORDER BY i.dateref DESC
            """, (self.root.ids.selected_model.text,)
        )
        self.root.ids.gstat_graphs.width = (dp(40) * len(imports)) + dp(100)
        self.root.ids.gstat_graphs.add_widget(MaxDistGraph(imports).buildGraph(self.common.dist_unit()))
        self.root.ids.gstat_graphs.add_widget(TotDistGraph(imports).buildGraph(self.common.dist_unit()))
        self.root.ids.gstat_graphs.add_widget(TotDurationGraph(imports).buildGraph(self.common.dist_unit()))


    def destroy_gstat_graphs(self):
        self.root.ids.gstat_graphs.clear_widgets()


    def initiate_log_file(self, buttonObj):
        '''
        Called when a log file has been selected. It will be opened, parsed and displayed on the map screen.
        '''
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
        logFiles = self.db.execute("SELECT filename FROM log_files WHERE importref = ?", (buttonObj.value,))
        for fileRef in logFiles:
            file = fileRef[0]
            os.remove(os.path.join(self.logfileDir, file))
        modelRef = self.db.execute("SELECT modelref FROM imports WHERE importref = ?", (buttonObj.value,))
        self.db.execute("DELETE FROM flight_stats WHERE importref = ?", (buttonObj.value,))
        self.db.execute("DELETE FROM log_files WHERE importref = ?", (buttonObj.value,))
        self.db.execute("DELETE FROM imports WHERE importref = ?", (buttonObj.value,))
        if modelRef is not None and len(modelRef) > 0:
            importRef = self.db.execute("SELECT count (1) FROM imports WHERE modelref = ?", (modelRef[0][0],))
            if importRef is None or len(importRef) == 0 or importRef[0][0] == 0:
                self.db.execute("DELETE FROM models WHERE modelref = ?", (modelRef[0][0],))
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
                    zip.write(self.db.dataFile(), os.path.basename(self.db.dataFile()))
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
                    zip.write(self.db.dataFile(), os.path.basename(self.db.dataFile()))
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
                        zip.write(self.db.dataFile(), os.path.basename(self.db.dataFile()))
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


    def restore_data(self, selectedFile):
        '''
        Restore data from a backup file.
        '''
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
                    shutil.copy(binFile, self.db.dataFile())
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


    def get_waypoints(self, button):
        adbexe = self.root.ids.adb_path.text
        prc = subprocess.run([adbexe, "devices"], capture_output=True, text=True)
        if len(prc.stderr) > 0:
            self.root.ids.adb_output.text = prc.stderr
        else:
            self.root.ids.adb_output.text = prc.stdout
            shutil.rmtree(self.tempDir, ignore_errors=True) # Delete temp files.
            if not os.path.exists(self.tempDir):
                Path(self.tempDir).mkdir(parents=False, exist_ok=True)
            dbbasename = "map.db"
            dbfilelocal = os.path.join(self.tempDir, dbbasename)
            prc = subprocess.run([adbexe, "pull", f"/data/data/com.ipotensic.potensicpro/databases/{dbbasename}", self.tempDir], capture_output=True, text=True)
            if len(prc.stderr) > 0:
                self.root.ids.adb_output.text = self.root.ids.adb_output.text + "\n" + prc.stderr
            if not os.path.exists(dbfilelocal):
                prc = subprocess.run([
                    adbexe, "shell", "run-as", "com.ipotensic.potensicpro", "sh", "-c",
                    f"'mkdir /storage/emulated/0/Android/data/com.ipotensic.potensicpro/files/PotensicPro/transfer; cp databases/{dbbasename} /storage/emulated/0/Android/data/com.ipotensic.potensicpro/files/PotensicPro/transfer/;'"
                    ], capture_output=True, text=True)
                if len(prc.stderr) > 0:
                    self.root.ids.adb_output.text = self.root.ids.adb_output.text + "\n" + prc.stderr
                prc = subprocess.run([adbexe, "pull", f"/storage/emulated/0/Android/data/com.ipotensic.potensicpro/files/PotensicPro/transfer/{dbbasename}", self.tempDir], capture_output=True, text=True)
                if len(prc.stderr) > 0:
                    self.root.ids.adb_output.text = self.root.ids.adb_output.text + "\n" + prc.stderr
                prc = subprocess.run([
                    adbexe, "shell", "run-as", "com.ipotensic.potensicpro", "sh", "-c",
                    f"'rm /storage/emulated/0/Android/data/com.ipotensic.potensicpro/files/PotensicPro/transfer/{dbbasename}; rmdir /storage/emulated/0/Android/data/com.ipotensic.potensicpro/files/PotensicPro/transfer;'"
                    ], capture_output=True, text=True)
                if not os.path.exists(dbfilelocal):
                    self.root.ids.adb_output.text = self.root.ids.adb_output.text + "\n" + "Could not download waypoints file from the device."
                    return

            self.potdb = Db(dbfilelocal, extdb=True) # sqlite DB file.
            self.root.ids.btn_retrieve_waypoints.disabled = True
            self.root.ids.btn_save_waypoints.disabled = False
            self.root.ids.btn_save_waypoints.disabled = False
            self.root.ids.selected_waypoint.disabled = False
            self.root.ids.add_waypoint_marker.disabled = False
            self.root.ids.add_waypoint_path.disabled = False
            self.root.ids.delete_waypoint_path.disabled = False
            self.waypoints = []
            for waypointInfo in self.potdb.execute("SELECT id,date,duration,height,mileage,num,speed FROM flightrecordbean ORDER BY id"):
                if waypointInfo[1] is not None:
                    markers = []
                    for marker in self.potdb.execute("SELECT id,lat,lng FROM multipointbean WHERE flightrecordbean_id = ? ORDER BY id", (waypointInfo[0],)):
                        markers.append({
                            "lat": marker[1],
                            "lon": marker[2]
                        })
                    self.waypoints.append({
                        "date": waypointInfo[1],
                        "duration": waypointInfo[2],
                        "height": waypointInfo[3],
                        "mileage": waypointInfo[4],
                        "num": waypointInfo[5],
                        "speed": waypointInfo[6],
                        "markers": markers
                    })


    def waypoint_selection(self, item):
        menu_items = []
        if self.waypoints:
            for idx, waypointInfo in enumerate(self.waypoints):
                menu_items.append({"text": f"{waypointInfo['date']} - {waypointInfo['num']} - {waypointInfo['mileage']} - {waypointInfo['duration']}", "on_release": lambda x=idx: self.waypoint_selection_callback(x)})
        if len(menu_items) == 0:
            menu_items.append({"text": "--", "on_release": lambda x=None: self.waypoint_selection_callback(x)})
        self.waypoint_selection_menu = MDDropdownMenu(caller = item, items = menu_items)
        self.waypoint_selection_menu.open()
    def waypoint_selection_callback(self, waypointidx):
        self.waypoint_selection_menu.dismiss()
        if waypointidx is None:
            self.root.ids.adb_output.text = "Retrieve the waypoints from the device first."
            self.root.ids.selected_waypoint.text = "--"
            return
        wpinfo = self.waypoints[waypointidx]
        self.root.ids.selected_waypoint.text = f"{wpinfo['date']} - {wpinfo['num']} - {wpinfo['mileage']} - {wpinfo['duration']}"
        self.reset_waylayer()
        self.waylayer.value = waypointidx
        minlat = None
        maxlat = None
        minlon = None
        maxlon = None
        count = 0
        for waypoint in self.waypoints[waypointidx]['markers']:
            marker = MapMarkerPopup(lat=waypoint['lat'], lon=waypoint['lon'], popup_size=(dp(180), dp(60)))
            if minlat is None or marker.lat < minlat:
                minlat = marker.lat
            if minlon is None or marker.lon < minlon:
                minlon = marker.lon
            if maxlat is None or marker.lat > maxlat:
                maxlat = marker.lat
            if maxlon is None or marker.lon > maxlon:
                maxlon = marker.lon
            count = count + 1
            marker.value = count
            widget = MDGridLayout(size_hint=(1,1), md_bg_color=self.theme_cls.backgroundColor, cols=1)
            widget.add_widget(MDLabel(text=f"Target: #{count}", bold=True, max_lines=1))
            widget.add_widget(MDButton(MDButtonText(text="Delete"), style="filled", on_release=self.delete_waypoint_marker))
            marker.add_widget(widget)
            self.root.ids.waymap.add_marker(marker, self.waylayer)
        if count > 0:
            zoom = self.root.ids.waymap.map_source.max_zoom
            self.root.ids.waymap.zoom = zoom
            self.root.ids.waymap.center_on((minlat + maxlat) / 2,  (minlon + maxlon) / 2)
            while zoom > self.root.ids.waymap.map_source.min_zoom:
                bbox = self.root.ids.waymap.get_bbox()
                if minlat >= bbox[0] and minlon >= bbox[1] and maxlat <= bbox[2] and maxlon <= bbox[3]:
                    break
                zoom = zoom - 1
                self.root.ids.waymap.zoom = zoom


    def waymap_touch(self, mapObj, touch):
        if mapObj.collide_point(*touch.pos) and self.waylayer and self.wait_for_marker_add_click:
            lat, lon = mapObj.get_latlon_at(touch.pos[0], touch.pos[1])
            marker = MapMarkerPopup(lat=lat, lon=lon, popup_size=(dp(180), dp(60)))
            marker.value = len(self.waylayer.children)+1
            widget = MDGridLayout(size_hint=(1,1), md_bg_color=self.theme_cls.backgroundColor, cols=1)
            widget.add_widget(MDLabel(text=f"Target: #{marker.value}", bold=True, max_lines=1))
            widget.add_widget(MDButton(MDButtonText(text="Delete"), style="filled", on_release=self.delete_waypoint_marker))
            marker.add_widget(widget)
            self.root.ids.waymap.add_marker(marker, self.waylayer)
            self.update_waypoints()
        self.wait_for_marker_add_click = False


    def add_waypoint_marker(self, buttonObj):
        self.wait_for_marker_add_click = True


    def delete_waypoint_marker(self, buttonObj):
        if not self.waylayer:
            return
        deletedmarker = buttonObj.parent.parent.parent
        deletednumber = deletedmarker.value
        self.root.ids.waymap.remove_marker(deletedmarker)
        for marker in self.waylayer.children:
            if marker.value > deletednumber:
                marker.value = marker.value - 1
                marker.placeholder.children[0].children[1].text = f"Target: #{marker.value}"
        self.update_waypoints()


    def add_waypoints(self, buttonObj):
        if self.potdb is None:
            return
        self.reset_waylayer()
        self.waylayer.value = len(self.waypoints)
        self.waypoints.append({
            "date": None,
            "duration": None,
            "height": None,
            "mileage": None,
            "num": 0,
            "speed": None,
            "markers": []
        })
        self.root.ids.selected_waypoint.text = "-- NEW --"

    def remove_waylayer(self):
        if self.waylayer:
            self.reset_waylayer()
            self.root.ids.waymap.remove_layer(self.waylayer)
            self.waylayer = None


    def reset_waylayer(self):
        if self.waylayer:
            while len(self.waylayer.children) > 0:
                self.waylayer.children[0].detach()
            self.waylayer.value = None
        else:
            self.waylayer = MarkerMapLayer()
            self.root.ids.waymap.add_layer(self.waylayer)


    def delete_waypoints(self, buttonObj):
        if not self.waylayer:
            return
        self.waypoints.pop(self.waylayer.value)
        self.reset_waylayer()
        self.root.ids.selected_waypoint.text = "--"


    def waymap_zoom(self, zoomin):
        '''
        Zoom in/out when the zoom buttons on the waypoint map are selected.
        '''
        if zoomin:
            if self.root.ids.waymap.zoom < self.root.ids.waymap.map_source.max_zoom:
                self.root.ids.waymap.zoom = self.root.ids.waymap.zoom + 1
        else:
            if self.root.ids.waymap.zoom > self.root.ids.waymap.map_source.min_zoom:
                self.root.ids.waymap.zoom = self.root.ids.waymap.zoom - 1


    def update_waypoints(self):
        if not self.waylayer:
            return
        # Update the current waypoints.
        markers = None
        if len(self.waylayer.children) > 0:
            markers = [None] * len(self.waylayer.children)
            for marker in self.waylayer.children:
                markers[marker.value-1] = { "lat": marker.lat, "lon": marker.lon }
        else:
            markers = []
        self.waypoints[self.waylayer.value]['markers'] = markers
        totdist = 0
        prevmarker = None
        for marker in markers:
            if prevmarker is not None:
                totdist = totdist + haversine(marker['lon'], marker['lat'], prevmarker['lon'], prevmarker['lat'])
            prevmarker = marker
        totdist = int(round(totdist * 1000))
        duration = int(totdist * 36) # short for distance (m) * 3600 / 100km/h
        self.waypoints[self.waylayer.value]['date'] = datetime.datetime.now().strftime('%d,%m,%Y')
        self.waypoints[self.waylayer.value]['duration'] = duration
        self.waypoints[self.waylayer.value]['height'] = '50m'
        self.waypoints[self.waylayer.value]['mileage'] = f"{totdist}m"
        self.waypoints[self.waylayer.value]['num'] = len(self.waypoints[self.waylayer.value]['markers'])
        self.waypoints[self.waylayer.value]['speed'] = '100km/h'


    def save_waypoints(self, button):
        if not self.waylayer or not self.potdb:
            return
        # Replace all waypoint data in the tables.
        self.potdb.execute("DELETE FROM multipointbean")
        self.potdb.execute("DELETE FROM flightrecordbean")
        flightid = 1
        markerid = 1
        for waypointInfo in self.waypoints:
            self.potdb.execute(
                "INSERT INTO flightrecordbean(id,date,duration,height,mileage,num,speed) VALUES(?,?,?,?,?,?,?)",
                (flightid, waypointInfo['date'], waypointInfo['duration'], waypointInfo['height'], waypointInfo['mileage'], waypointInfo['num'], waypointInfo['speed'])
            )
            for marker in waypointInfo['markers']:
                self.potdb.execute(
                    "INSERT INTO multipointbean(id,flightrecordbean_id,lat,lng) VALUES (?,?,?,?)",
                    (markerid, flightid, marker['lat'], marker['lon'])
                )
                markerid = markerid + 1
            flightid = flightid + 1

        # Push the waypoint db file to the device. If direct file transfer via rooted device does not work, attempt file upload if the potensic app is debuggable.
        adbexe = self.root.ids.adb_path.text
        dbbasename = "map.db"
        prc = subprocess.run([adbexe, "push", self.potdb.dataFile(), f"/data/data/com.ipotensic.potensicpro/databases/"], capture_output=True, text=True)
        if len(prc.stderr) > 0:
            self.root.ids.adb_output.text = prc.stderr
        else:
            self.root.ids.adb_output.text = prc.stdout
        print(f"RETURNCODE1: {prc.returncode}")
        if prc.returncode == 0:
            prc = subprocess.run([adbexe, "push", "shell", "run-as", "com.ipotensic.potensicpro", "sh", "-c", f"chmod 666 /data/data/com.ipotensic.potensicpro/databases/{dbbasename}"], capture_output=True, text=True)
            if len(prc.stderr) > 0:
                self.root.ids.adb_output.text = self.root.ids.adb_output.text + "\n" + prc.stderr
        else:
            prc = subprocess.run([
                adbexe, "shell", "run-as", "com.ipotensic.potensicpro", "sh", "-c",
                f"'mkdir /storage/emulated/0/Android/data/com.ipotensic.potensicpro/files/PotensicPro/transfer;'"
                ], capture_output=True, text=True)
            if len(prc.stderr) > 0:
                self.root.ids.adb_output.text = self.root.ids.adb_output.text + "\n" + prc.stderr
            prc = subprocess.run([adbexe, "push", self.potdb.dataFile(), f"/storage/emulated/0/Android/data/com.ipotensic.potensicpro/files/PotensicPro/transfer/"], capture_output=True, text=True)
            if len(prc.stderr) > 0:
                self.root.ids.adb_output.text = self.root.ids.adb_output.text + "\n" + prc.stderr
            prc = subprocess.run([
                adbexe, "shell", "run-as", "com.ipotensic.potensicpro", "sh", "-c",
                f"'cp /storage/emulated/0/Android/data/com.ipotensic.potensicpro/files/PotensicPro/transfer/{dbbasename} /data/data/com.ipotensic.potensicpro/databases/; rm /storage/emulated/0/Android/data/com.ipotensic.potensicpro/files/PotensicPro/transfer/{dbbasename}; rmdir /storage/emulated/0/Android/data/com.ipotensic.potensicpro/files/PotensicPro/transfer;'"
                ], capture_output=True, text=True)
            if len(prc.stderr) > 0:
                self.root.ids.adb_output.text = self.root.ids.adb_output.text + "\n" + prc.stderr


    def close_pref_screen(self):
        '''
        Called when map screen is closed.
        '''
        if self.app_view == "map":
            self.open_view("Screen_Map")
        elif self.app_view == "sum":
            self.open_view("Screen_Day_Summary")
        elif self.app_view == "log":
            self.open_view("Screen_Log_Files")
        elif self.app_view == "waypoints":
            self.open_view("Screen_Waypoints")


    def init_prefs(self):
        '''
        Read from config (ini) file.
        '''
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
        self.root.ids.selected_splashscreen.active = Config.getboolean('preferences', 'splash')
        self.root.ids.selected_mapsource.text = Config.get('preferences', 'map_tile_server')
        self.root.ids.selected_refresh_rate.text = Config.get('preferences', 'refresh_rate')
        self.root.ids.selected_model.text = Config.get('preferences', 'selected_model')
        self.root.ids.selected_language.text = self.languages.get(Config.get('preferences', 'language'))
        self.root.ids.adb_path.text = Config.get('preferences', 'adbpath')


    def reset(self):
        '''
        Reset the application as it were before opening a file.
        '''
        self.centerlat = 51.50722
        self.centerlon = -0.1275
        self.playback_speed = 1
        self.map_rebuild_required = True
        if self.root:
            self.root.ids.map_title.text = f"{self.appName} - {_('title_map')}"
            self.root.ids.flights_title.text = f"{self.appName} - {_('title_flights')}"
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
            self.root.ids.value1_rth_desc.text = ""
            self.root.ids.value1_batterylevel1.text = ""
            self.root.ids.value1_batterylevel2.text = ""
            self.root.ids.value1_flightmode.text = ""
            self.root.ids.value1_dist.text = ""
            self.root.ids.value1_hspeed.text = ""
            self.root.ids.value1_vspeed.text = ""
            self.root.ids.value1_elapsed.text = ""
            self.root.ids.map_metrics_ribbon.text = ""
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
        if self.root and self.root.ids.screen_manager.current != "Screen_Loading":
            self.open_view("Screen_Log_Files")
            self.center_map()


    def cleanup_orphaned_refs(self):
        '''
        Delete unreferenced log files. Delete unreferenced DB records.
        '''
        importedFiles = []
        for fileRef in self.db.execute("SELECT filename FROM log_files"):
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
                importRefRecs = self.db.execute("SELECT importref FROM log_files WHERE filename = ?", (importedFile,))
                importRef = importRefRecs[0][0] if importRefRecs is not None and len(importRefRecs) > 0 else None
                if importRef is not None:
                    logFiles = self.db.execute("SELECT filename FROM log_files WHERE importref = ?", (importRef,))
                    for fileRef in logFiles:
                        file = fileRef[0]
                        try:
                            os.remove(os.path.join(self.logfileDir, file))
                        except:
                            # Do nothing.
                            ...
                    modelRef = self.db.execute("SELECT modelref FROM imports WHERE importref = ?", (importRef,))
                    self.db.execute("DELETE FROM flight_stats WHERE importref = ?", (importRef,))
                    self.db.execute("DELETE FROM log_files WHERE importref = ?", (importRef,))
                    self.db.execute("DELETE FROM imports WHERE importref = ?", (importRef,))
                    if modelRef is not None and len(modelRef) > 0:
                        importRef = self.db.execute("SELECT count (1) FROM imports WHERE modelref = ?", (modelRef[0][0],))
                        if importRef is None or len(importRef) == 0 or importRef[0][0] == 0:
                            self.db.execute("DELETE FROM models WHERE modelref = ?", (modelRef[0][0],))
                else:
                    self.db.execute("DELETE FROM log_files WHERE filename = ?", (importedFile,))


    def clear_cache(self):
        '''
        Clear the cache directory (where drone icons and map tiles are stored).
        '''
        print(f"Clearing cache: {self.root.ids.map.cache_dir}")
        for root, dirs, files in os.walk(self.root.ids.map.cache_dir, topdown=False):
            for name in files:
                os.remove(os.path.join(root, name))
            for name in dirs:
                os.rmdir(os.path.join(root, name))
        self.show_info_message(message=_('cache_cleared'))


    def check_for_updates(self):
        '''
        Check if a newer version of this app is available for the platform.
        '''
        print("Checking for software update...")
        try:
            response = requests.get(
                "https://api.github.com/repos/koen-aerts/potdroneflightparser/releases",
                headers = { "Accept": "application/vnd.github+json" },
                params = { "per_page": "1", "page": "1" }
            )
            if response.status_code == 200:
                relObj = json.loads(response.content)
                latestVersion = relObj[0]["name"]
                latestVersionParts = latestVersion.split(".")
                currentVersionParts = self.appVersion.split(".")
                hasUpdate = False
                if len(latestVersionParts) != len(currentVersionParts):
                    hasUpdate = True
                else:
                    latestVerNum = 0
                    currentVerNum = 0
                    for idx in range(len(latestVersionParts)):
                        latestVerPt = int(re.sub("[^0-9]*", "", latestVersionParts[idx]))
                        currentVerPt = int(re.sub("[^0-9]*", "", currentVersionParts[idx]))
                        latestVerNum = (latestVerNum * 100) + latestVerPt
                        currentVerNum = (currentVerNum * 100) + currentVerPt
                    if latestVerNum > currentVerNum:
                        hasUpdate = True
                if hasUpdate:
                    print(f"Current version: {self.appVersion}. Latest version: {latestVersion}")
                    isPreRel = relObj[0]["prerelease"] == "true"
                    if not isPreRel: # Pre-releases are excluded as they are not considered stable.
                        downloadUrl = relObj[0]["html_url"]
                        platform = None
                        for asset in relObj[0]["assets"]: # Find matching platform
                            assetName = asset["name"]
                            if assetName.endswith(".apk") and self.is_android:
                                platform = "Android"
                                break
                            elif assetName.endswith(".api") and self.is_ios:
                                platform = "iOS"
                                break
                            elif '_macos_' in assetName and self.is_macos:
                                platform = "MacOS"
                                break
                            elif '_win64_' in assetName and self.is_windows:
                                platform = "Windows"
                                break
                            elif '_linux_' in assetName and self.is_linux:
                                platform = "Linux"
                                break
                        # Only show new version alert if it includes one for the platform the app is running on.
                        if platform is not None:
                            mainthread(self.open_upgrade_dialog)(latestVersion, platform, downloadUrl)
                elif latestVersion != self.appVersion:
                    print(f"Current version: {self.appVersion} (unreleased). Latest version: {latestVersion}")
            else:
                print(f"Received status code of {response.status_code} while checking for updates.")
        except Exception as e:
            print(f"Failed to check for app updates: {e}")


    def open_upgrade_dialog(self, version, platform, downloadUrl):
        downloadBtn = MDButton(MDButtonText(text=_('download')), style="text", on_release=self.download_upgrade)
        downloadBtn.value = downloadUrl
        self.dialog_upgrade = MDDialog(
            MDDialogHeadlineText(
                text = _('upgrade_notice').format(version=version, platform=platform),
                halign="left",
            ),
            MDDialogButtonContainer(
                Widget(),
                downloadBtn,
                MDButton(MDButtonText(text=_('later')), style="text", on_release=self.close_upgrade_dialog),
                spacing="8dp",
            ),
        )
        self.dialog_upgrade.open()


    def close_upgrade_dialog(self, *args):
        self.dialog_upgrade.dismiss()
        self.dialog_upgrade = None


    def download_upgrade(self, buttonObj):
        self.close_upgrade_dialog(None)
        print(f"Downloading new app version: {buttonObj.value}")
        webbrowser.open(buttonObj.value)


    @mainthread
    def show_info_message(self, message: str):
        '''
        Show info messages.
        '''
        MDSnackbar(MDSnackbarText(text=message), y=dp(24), pos_hint={"center_x": 0.5}, size_hint_x=0.8).open()
    @mainthread
    def show_warning_message(self, message: str):
        '''
        Show warning messages.
        '''
        MDSnackbar(MDSnackbarText(text=message), y=dp(24), pos_hint={"center_x": 0.5}, size_hint_x=0.8).open()
    @mainthread
    def show_error_message(self, message: str):
        '''
        Show error messages.
        '''
        MDSnackbar(MDSnackbarText(text=message), y=dp(24), pos_hint={"center_x": 0.5}, size_hint_x=0.8).open()


    def show_help(self):
        '''
        Open help page on the project home page and for the matching version of the app.
        '''
        webbrowser.open(f"https://htmlpreview.github.io/?https://github.com/koen-aerts/potdroneflightparser/blob/{self.appVersion}/docs/guide.html")


    def on_file_drop(self, widget, importfilename, x, y, *args):
        '''
        If called multiple times because more than 1 file is dragged, subsequent calls will be ignored. File drop is ignored
        if we're not on the log list screen or file is not a zip file. Maybe in the future allow file drops on map view also.
        '''
        now = datetime.datetime.now()
        filename = importfilename.decode('utf-8')
        if self.lastdrop and (now - self.lastdrop) < datetime.timedelta(seconds = 5):
            print(f"Ignored concurrent filedrop: {filename}")
            return
        self.lastdrop = now
        if self.root.ids.screen_manager.current == "Screen_Log_Files" and filename.lower().endswith(".zip"):
            mainthread(self.initiate_import_file)(filename)
        else:
            print(f"Ignored invalid filedrop: {filename}")


    def allow_app_interaction(self, dt):
        '''
        Bring the app out of the Loading page.
        '''
        self.open_view("Screen_Log_Files")
        self.center_map()


    def swap_fullscreen_mode(self):
        self.root_window.fullscreen = not self.root_window.fullscreen


    def keyboard_event(self, instance, keyboard, keycode, text, modifiers):
        '''
        Capture keyboard input. Called when buttons are pressed on the mobile device.
        '''
        if keyboard in (1001, 27):
            if Window.fullscreen:
                Window.fullscreen = False
            else:
                self.stop()
        return True


    def __init__(self, **kwargs):
        '''
        Constructor
        '''
        super().__init__(**kwargs)
        self.lastdrop = None
        self.ts_init = datetime.datetime.now()
        self.common = Common(self)
        self.is_ios = platform == 'ios'
        self.is_android = platform == 'android'
        self.is_windows = platform == 'win'
        self.is_macos = platform == 'macosx'
        self.is_linux = platform == 'linux'
        self.is_desktop = self.is_windows or self.is_macos or self.is_linux
        self.title = self.appTitle
        self.tempDir = os.path.join(tempfile.gettempdir(), "flightdata")
        self.dataDir = os.path.join(self.ios_doc_path(), '.data') if self.is_ios else user_data_dir(self.appPathName, self.appPathName)
        self.logfileDir = os.path.join(self.dataDir, "logfiles") # Place where log bin files go.
        if not os.path.exists(self.logfileDir):
            Path(self.logfileDir).mkdir(parents=True, exist_ok=True)
        self.db = Db(os.path.join(self.dataDir, self.dbFilename)) # sqlite DB file.
        self.potdb = None
        configDir = self.dataDir if self.is_ios else user_config_dir(self.appPathName, self.appPathName) # Place where app ini config file goes.
        if not os.path.exists(configDir):
            Path(configDir).mkdir(parents=True, exist_ok=True)
        self.configFile = os.path.join(configDir, self.configFilename) # ini config file.
        if self.is_android:
            request_permissions([Permission.INTERNET, Permission.WRITE_EXTERNAL_STORAGE, Permission.READ_EXTERNAL_STORAGE])
            self.shared_storage = SharedStorage()
            self.chosenFile = None
            self.chooser_open = False # To track Android File Manager (Chooser)
            self.chooser = MyChooser(self.import_android_chooser_callback)
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
            'splash': False,
            'adbpath': "adb"
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
        Window.bind(on_keyboard=self.keyboard_event)
        self.waypoints = None
        self.waylayer = None
        self.wait_for_marker_add_click = None
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


    def build(self):
        self.icon = 'assets/app-icon256.png'
        self.init_prefs()


    def on_start(self):
        self.cleanup_orphaned_refs()
        threading.Thread(target=self.check_for_updates).start() # No need to hold up the app while checking for updates.
        if self.is_desktop:
            Window.bind(on_drop_file = self.on_file_drop)
            if not Config.getboolean('preferences', 'splash'):
                self.splash = SplashScreen(text=self.appVersion, window=self.root_window)
                self.splash.show()
        self.root.ids.selected_path.text = '--'
        self.reset()
        self.select_map_source()
        self.list_log_files()
        self.app_view = "loading"
        Clock.schedule_once(self.allow_app_interaction)
        return super().on_start()


    def on_pause(self):
        self.stop_flight(True)
        return True


    def on_stop(self):
        '''
        Called when the app is exited.
        '''
        self.stop_flight(True)
        shutil.rmtree(self.tempDir, ignore_errors=True) # Delete temp files.
        return super().on_stop()


if __name__ == "__main__":
    MainApp().run()