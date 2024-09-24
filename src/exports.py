'''
Export functioncality for CSV and KML - Developer: Koen Aerts
'''
import datetime
import xml.etree.ElementTree as ET


class ExportCsv:
    '''
    Save the flight data in a CSV file.
    '''
    def __init__(self, columnnames=[], rows=[]):
        self.columns = columnnames
        self.rows = rows
    def save(self, csvFilename):
        with open(csvFilename, 'w') as f:
            head = ''
            for col in self.columns:
                if len(head) > 0:
                    head = head + ','
                head = head + col
            f.write(head)
            for record in self.rows:
                hasWritten = False
                f.write('\n')
                for col in record:
                    if (hasWritten):
                        f.write(',')
                    f.write('"' + str(col) + '"')
                    hasWritten = True
        f.close()


class ExportKml:
    '''
    Save the flight data in a KML file.
    '''
    appRef = '<a href="https://github.com/koen-aerts/potdroneflightparser">Flight Log Viewer</a>'
    appAssetSrc = "https://raw.githubusercontent.com/koen-aerts/potdroneflightparser/v2.2.0/src/assets"
    def __init__(
        self, commonlib, columnnames=[], rows=[], name="Flight Logs", description=appRef, pathcolor="#ff0000",
        pathwidth="1", homecolorref="1", ctrlcolorref="1", dronecolorref="1", flightstarts=[],
        flightends=[], flightstats=[], uom="metric"
    ):
        self.common = commonlib
        self.columns = columnnames
        self.rows = rows
        self.logName = name
        self.logDescription = description
        self.homeColor = homecolorref
        self.ctrlColor = ctrlcolorref
        self.droneColor = dronecolorref
        self.pathColor = pathcolor
        self.pathWidth = pathwidth
        self.flightStarts = flightstarts
        self.flightEnds = flightends
        self.flightStats = flightstats
        self.uom = uom

    def save(self, kmlFilename):
        root = ET.Element("kml", xmlns="http://www.opengis.net/kml/2.2")
        doc = ET.SubElement(root, "Document")
        ET.SubElement(doc, "name").text = self.logName
        ET.SubElement(doc, "description").append(ET.Comment(f' --><![CDATA[{self.logDescription}]]><!-- '))
        style = ET.SubElement(doc, "Style", id="pathStyle")
        lineStyle = ET.SubElement(style, "LineStyle")
        ET.SubElement(lineStyle, "color").text = f"ff{self.pathColor[5:7]}{self.pathColor[3:5]}{self.pathColor[1:3]}"
        ET.SubElement(lineStyle, "width").text = self.pathWidth
        style = ET.SubElement(doc, "Style", id="homeStyle")
        iconStyle = ET.SubElement(style, "IconStyle")
        icon = ET.SubElement(iconStyle, "Icon")
        ET.SubElement(icon, "href").text = f"{self.appAssetSrc}/Home-{self.homeColor}.png"
        ET.SubElement(iconStyle, "hotSpot", x="0.5", y="0.5", xunits="fraction", yunits="fraction")
        style = ET.SubElement(doc, "Style", id="ctrlStyle")
        iconStyle = ET.SubElement(style, "IconStyle")
        icon = ET.SubElement(iconStyle, "Icon")
        ET.SubElement(icon, "href").text = f"{self.appAssetSrc}/Controller-{self.ctrlColor}.png"
        ET.SubElement(iconStyle, "hotSpot", x="0.5", y="0.5", xunits="fraction", yunits="fraction")
        style = ET.SubElement(doc, "Style", id="droneStyle")
        iconStyle = ET.SubElement(style, "IconStyle")
        icon = ET.SubElement(iconStyle, "Icon")
        ET.SubElement(icon, "href").text = f"{self.appAssetSrc}/Drone-{self.droneColor}.png"
        ET.SubElement(iconStyle, "hotSpot", x="0.5", y="0.5", xunits="fraction", yunits="fraction")
        style = ET.SubElement(doc, "Style", id="hidePoints")
        listStyle = ET.SubElement(style, "ListStyle")
        ET.SubElement(listStyle, "listItemType").text = "checkHideChildren"
        flightNo = 1
        while flightNo <= len(self.flightStarts):
            coords = ''
            self.currentStartIdx = self.flightStarts[f"{flightNo}"]
            self.currentEndIdx = self.flightEnds[f"{flightNo}"]
            folder = ET.SubElement(doc, "Folder")
            ET.SubElement(folder, "name").text = f"Flight #{flightNo}"
            ET.SubElement(folder, "description").append(ET.Comment(f' --><![CDATA[Duration: {str(self.flightStats[flightNo][3])}<br>Distance flown: {self.common.fmt_num(self.common.dist_val(self.flightStats[flightNo][9]))} {self.common.dist_unit()}]]><!-- '))
            ET.SubElement(folder, "styleUrl").text = "#hidePoints"
            ET.SubElement(folder, "visibility").text = "0"
            prevtimestamp = None
            maxelapsedms = datetime.timedelta(microseconds=500000)
            isfirstrow = True
            for rowIdx in range(self.currentStartIdx, self.currentEndIdx+1):
                row = self.rows[rowIdx]
                thistimestamp = datetime.datetime.fromisoformat(row[self.columns.index('timestamp')]).astimezone(datetime.timezone.utc) # Get timestamp in UTC.
                elapsedFrame = None if prevtimestamp is None else thistimestamp - prevtimestamp # elasped microseconds since last frame.
                if elapsedFrame is None or elapsedFrame > maxelapsedms: # Omit frames that are within maxelapsedms microseconds from each other.
                    timestampstr = f"{thistimestamp.isoformat(sep='T', timespec='milliseconds')}"
                    dronelon = row[self.columns.index('dronelon')]
                    dronelat = row[self.columns.index('dronelat')]
                    dronealt = row[self.columns.index('altitude2metric')] # KML uses metric units.
                    if isfirstrow:
                        lookAt = ET.SubElement(folder, "LookAt")
                        ET.SubElement(lookAt, "longitude").text = dronelon
                        ET.SubElement(lookAt, "latitude").text = dronelat
                        ET.SubElement(lookAt, "altitude").text = "200" # Viewing altitude
                        ET.SubElement(lookAt, "heading").text = "0" # Look North
                        ET.SubElement(lookAt, "tilt").text = "45" # Look down 45 degrees
                        ET.SubElement(lookAt, "range").text = str((self.flightStats[flightNo][0]*2)+500) # Determine potential good viewing distance.
                        ET.SubElement(lookAt, "altitudeMode").text = "relativeToGround"
                        isfirstrow = False
                    placeMark = ET.SubElement(folder, "Placemark") # Drone marker.
                    timest = ET.SubElement(placeMark, "TimeStamp")
                    ET.SubElement(timest, "when").text = timestampstr
                    ET.SubElement(placeMark, "styleUrl").text = "#droneStyle"
                    point = ET.SubElement(placeMark, "Point")
                    ET.SubElement(point, "altitudeMode").text = "relativeToGround"
                    ET.SubElement(point, "coordinates").text = f"{dronelon},{dronelat},{dronealt}"
                    if (len(coords) > 0):
                        coords += '\n'
                    coords += f"{dronelon},{dronelat},{dronealt}" # flight path coordinates and altitude.
                    homelon = row[self.columns.index('homelon')]
                    homelat = row[self.columns.index('homelat')]
                    if homelon != '0.0' and homelat != '0.0': # Home marker.
                        placeMark = ET.SubElement(folder, "Placemark")
                        timest = ET.SubElement(placeMark, "TimeStamp")
                        ET.SubElement(timest, "when").text = timestampstr
                        ET.SubElement(placeMark, "styleUrl").text = "#homeStyle"
                        point = ET.SubElement(placeMark, "Point")
                        ET.SubElement(point, "altitudeMode").text = "relativeToGround"
                        ET.SubElement(point, "coordinates").text = f"{homelon},{homelat},0"
                    ctrllon = row[self.columns.index('ctrllon')]
                    ctrllat = row[self.columns.index('ctrllat')]
                    if ctrllon != '0.0' and ctrllat != '0.0': # Controller marker.
                        placeMark = ET.SubElement(folder, "Placemark")
                        timest = ET.SubElement(placeMark, "TimeStamp")
                        ET.SubElement(timest, "when").text = timestampstr
                        ET.SubElement(placeMark, "styleUrl").text = "#ctrlStyle"
                        point = ET.SubElement(placeMark, "Point")
                        ET.SubElement(point, "altitudeMode").text = "relativeToGround"
                        ET.SubElement(point, "coordinates").text = f"{ctrllon},{ctrllat},1.5" # Assume average human holds controller 1.5 meters from ground.
                    prevtimestamp = thistimestamp
            placeMark = ET.SubElement(folder, "Placemark")
            ET.SubElement(placeMark, "name").text = f"Flight Path {flightNo}"
            ET.SubElement(placeMark, "styleUrl").text = "#pathStyle"
            lineString = ET.SubElement(placeMark, "LineString")
            ET.SubElement(lineString, "tessellate").text = "1"
            ET.SubElement(lineString, "altitudeMode").text = "relativeToGround"
            ET.SubElement(lineString, "coordinates").text = coords
            flightNo = flightNo + 1
        xml = ET.ElementTree(root)
        xml.write(kmlFilename, encoding='UTF-8', xml_declaration=True)
