'''
Custom Widgets - Developers: Chris Raynak, Koen Aerts
'''
import math
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.properties import NumericProperty, BoundedNumericProperty, StringProperty
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.scatter import Scatter
from kivy.uix.widget import Widget

import kivy_garden.graph
from kivy_garden.graph import BarPlot


# monkey patch to change axis label behaviour
import inspect
__ylabels__ = None
__xlabels__ = None
def __identity__(value):
    curframe = inspect.currentframe()
    callerframe = inspect.getouterframes(curframe, 2)
    callerlineno = callerframe[1][2]
    if callerlineno in [367, 380]:
        i = int(value)
        if __ylabels__ and len(__ylabels__) > 0:
            return "" if i >= len(__ylabels__) else __ylabels__[i] # Return label name instead of tick value
        else:
            return str(i)
    if callerlineno in [395, 407]:
        i = int(value)
        if __xlabels__ and len(__xlabels__) > 0:
            return "" if i >= len(__xlabels__) else __xlabels__[i] # Return label name instead of tick value
        else:
            return str(i)
    return value # Return tick value
kivy_garden.graph.identity = __identity__


def dist_val(uom, num):
    if num is None:
        return None
    return num if uom == 'm' else num * 3.28084


# Override Graph to change axis labels.
class CustGraph(kivy_garden.graph.Graph):
    def __init__(self, ylabels, xlabels, **kwargs):
        global __ylabels__
        global __xlabels__
        super().__init__(**kwargs)
        __ylabels__ = ylabels
        __xlabels__ = xlabels
        self.precision = "%s"
    def _update_labels(self):
        return super()._update_labels()


class MaxDistGraph():
    def __init__(self, imports):
        self.imports = imports
    def buildGraph(self, uom):
        distplot = BarPlot(color=[.5, .7, 0, 1], bar_spacing=.8, bar_width=dp(30))
        counter = 0
        maxdist = None
        xlabels = []
        for importRef in self.imports:
            dist = 0 if importRef[5] is None else int(dist_val(uom, importRef[5]))
            xlabels.append(f"[size=12dp][i]{importRef[1][4:]}[/i][/size]")
            if maxdist is None or dist > maxdist:
                maxdist = dist
            distplot.points.append([counter, dist])
            counter = counter + 1
        topdist = math.ceil(maxdist / 100) * 100 # round up to nearest 100.
        ticks = topdist / 10
        graph = CustGraph(ylabels=[], xlabels=xlabels, draw_border=True, label_options={"color":[0,0,0,1],"bold":True,"markup":True}, xlabel='Date', ylabel=f'Max Distance ({uom})', x_ticks_major=1, x_ticks_minor=2, y_ticks_major=ticks, y_ticks_minor=2, ymin=0, ymax=topdist, xmin=0, xmax=counter, y_grid_label=True, x_grid_label=True, x_grid=False, y_grid=True)
        graph.height = dp(50)
        graph.add_plot(distplot)
        #distplot.bind_to_graph(graph)
        return graph


class TotDistGraph():
    def __init__(self, imports):
        self.imports = imports
    def buildGraph(self, uom):
        distplot = BarPlot(color=[.5, 0, .7, 1], bar_spacing=.8, bar_width=dp(30))
        counter = 0
        maxdist = None
        xlabels = []
        for importRef in self.imports:
            dist = 0 if importRef[9] is None else int(dist_val(uom, importRef[9]))
            xlabels.append(f"[size=12dp][i]{importRef[1][4:]}[/i][/size]")
            if maxdist is None or dist > maxdist:
                maxdist = dist
            distplot.points.append([counter, dist])
            counter = counter + 1
        topdist = math.ceil(maxdist / 100) * 100 # round up to nearest 100.
        ticks = topdist / 10
        graph = CustGraph(ylabels=[], xlabels=xlabels, draw_border=True, label_options={"color":[0,0,0,1],"bold":True,"markup":True}, xlabel='Date', ylabel=f'Total Distance ({uom})', x_ticks_major=1, x_ticks_minor=2, y_ticks_major=ticks, y_ticks_minor=2, ymin=0, ymax=topdist, xmin=0, xmax=counter, y_grid_label=True, x_grid_label=True, x_grid=False, y_grid=True)
        graph.height = dp(50)
        graph.add_plot(distplot)
        return graph


class TotDurationGraph():
    def __init__(self, imports):
        self.imports = imports
    def buildGraph(self, uom):
        durplot = BarPlot(color=[0, .5, .7, 1], bar_spacing=.8, bar_width=dp(30))
        counter = 0
        maxdur = None
        xlabels = []
        for importRef in self.imports:
            dur = 0 if importRef[5] is None else int(round(dist_val(uom, importRef[3])/60))
            xlabels.append(f"[size=12dp][i]{importRef[1][4:]}[/i][/size]")
            if maxdur is None or dur > maxdur:
                maxdur = dur
            durplot.points.append([counter, dur])
            counter = counter + 1
        topdur = math.ceil(maxdur / 10) * 10 # round up to nearest 10.
        ticks = topdur / 10
        graph = CustGraph(ylabels=[], xlabels=xlabels, draw_border=True, label_options={"color":[0,0,0,1],"bold":True,"markup":True}, xlabel='Date', ylabel='Total Flight Minutes', x_ticks_major=1, x_ticks_minor=2, y_ticks_major=ticks, y_ticks_minor=2, ymin=0, ymax=topdur, xmin=0, xmax=counter, y_grid_label=True, x_grid_label=True, x_grid=False, y_grid=True)
        graph.add_plot(durplot)
        return graph


class SplashScreen():
    def __init__(self, window=None, text=None):
        self.splash_img = Image(source="assets/splash.png", fit_mode="scale-down")
        self.splash_text = None
        self.splash_win = None
        if window:
            self.splash_win = window
        if text:
            self.splash_text = Label(text=f"{text}", pos_hint={"center_x": .5, "center_y": .25}, font_size=dp(50))
    def show(self, seconds=5):
        if self.splash_win:
            self.splash_win.add_widget(self.splash_img)
            if self.splash_text:
                self.splash_win.add_widget(self.splash_text)
            Clock.schedule_once(self.remove_splash_image, seconds)
    def remove_splash_image(self, dt):
        '''
        Close the splash screen.
        '''
        if self.splash_win:
            self.splash_win.remove_widget(self.splash_img)
            if self.splash_text:
                self.splash_win.remove_widget(self.splash_text)


class DistGauge(Widget):
    '''
    Distance Gauge
    '''    
    display_unit = StringProperty("")
    unit = NumericProperty(1.8)
    value = BoundedNumericProperty(0, min=0, max=99000, errorvalue=0)

    def __init__(self, **kwargs):
        super(DistGauge, self).__init__(**kwargs)
        self.file_gauge = "assets/Distance_Background.png"
        self.file_needle_long = "assets/LongNeedleAltimeter1a.png"
        self.file_needle_short = "assets/SmallNeedleAltimeter1a.png"
        self._gauge = Scatter(
            size=self.size,
            do_rotation=False,
            do_scale=False,
            do_translation=False
        )
        self._img_gauge = Image(
            source=self.file_gauge,
            size=self.size,
        )
        self._needleL = Scatter(
            size=self.size,
            do_rotation=False,
            do_scale=False,
            do_translation=False
        )
        self._needleS = Scatter(
            size=self.size,
            do_rotation=False,
            do_scale=False,
            do_translation=False
        )
        self._img_needle_short = Image(
            source=self.file_needle_short,
            size=self.size,
        )
        self._img_needle_long = Image(
            source=self.file_needle_long,
            size=self.size,
        )
        self._glab = Label(font_size=dp(14), markup=True, color=[1, 1, 1, 1])
        self._glab2 = Label(font_size=dp(12), markup=True, color=[1, 1, 1, 1])
        self._gauge.add_widget(self._img_gauge)
        self._needleS.add_widget(self._img_needle_short)
        self._needleL.add_widget(self._img_needle_long)
        self.add_widget(self._gauge)
        self.add_widget(self._needleS)
        self.add_widget(self._needleL)
        self.add_widget(self._glab)
        self.add_widget(self._glab2)
        self.bind(pos=self._update)
        self.bind(size=self._update)
        self.bind(value=self._turn)

    def _update(self, *args): # Update gauge and needle positions after sizing or positioning.
        self._glab.font_size = dp(14) if self.height > dp(100) else dp(12) if self.height > dp(75) else dp(10)
        self._glab2.font_size = dp(12) if self.height > dp(75) else dp(10)
        self._gauge.size = self.size
        self._img_gauge.size = self.size
        self._needleL.size = self.size
        self._needleS.size = self.size
        self._img_needle_short.size = self.size
        self._img_needle_long.size = self.size
        self._gauge.pos = self.pos
        self._needleL.pos = (self.x, self.y)
        self._needleL.center = self._gauge.center
        self._needleS.pos = (self.x, self.y)
        self._needleS.center = self._gauge.center
        self._glab.center_x = self._gauge.center_x - dp(28)/dp(150)*self.size[0]
        self._glab.center_y = self._gauge.center_y + dp(1)/dp(150)*self.size[1]
        self._glab2.center_x = self._gauge.center_x
        self._glab2.center_y = self._gauge.center_y - dp(15)/dp(150)*self.size[1]

    def _turn(self, *args): # Turn needle
        self._needleS.center_x = self._gauge.center_x
        self._needleS.center_y = self._gauge.center_y
        self._needleS.rotation = ((1 * self.unit) - (self.value * self.unit * 2)/10)
        self._needleL.center_x = self._gauge.center_x
        self._needleL.center_y = self._gauge.center_y
        self._needleL.rotation = (1 * self.unit) - (self.value * self.unit * 2)        
        self._glab.text = "[b]{0:04d}[/b]".format(self.value)
        self._glab2.text = self.display_unit


class AltGauge(Widget):
    '''
    Altitude Gauge
    '''
    display_unit = StringProperty("")
    unit = NumericProperty(1.8)
    value = BoundedNumericProperty(0, min=0, max=8000, errorvalue=0)
    size_text = NumericProperty(10)

    def __init__(self, **kwargs):
        super(AltGauge, self).__init__(**kwargs)
        self.file_gauge = "assets/Altimeter_Background2.png"
        self.file_needle_long = "assets/LongNeedleAltimeter1a.png"
        self.file_needle_short = "assets/SmallNeedleAltimeter1a.png"
        self._gauge = Scatter(
            size=self.size,
            do_rotation=False,
            do_scale=False,
            do_translation=False
        )
        self._img_gauge = Image(
            source=self.file_gauge,
            size=self.size,
        )
        self._needleL = Scatter(
            size=self.size,
            do_rotation=False,
            do_scale=False,
            do_translation=False
        )
        self._needleS = Scatter(
            size=self.size,
            do_rotation=False,
            do_scale=False,
            do_translation=False
        )
        self._img_needle_short = Image(
            source=self.file_needle_short,
            size=self.size
        )
        self._img_needle_long = Image(
            source=self.file_needle_long,
            size=self.size
        )
        self._glab = Label(font_size=dp(14), markup=True, color=[1, 1, 1, 1])
        self._glab2 = Label(font_size=dp(12), markup=True, color=[1, 1, 1, 1])
        self._gauge.add_widget(self._img_gauge)
        self._needleS.add_widget(self._img_needle_short)
        self._needleL.add_widget(self._img_needle_long)
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
        self._glab.font_size = dp(14) if self.height > dp(100) else dp(12) if self.height > dp(75) else dp(10)
        self._glab2.font_size = dp(12) if self.height > dp(75) else dp(10)
        self._gauge.size = self.size
        self._img_gauge.size = self.size
        self._needleL.size = self.size
        self._needleS.size = self.size
        self._img_needle_short.size = self.size
        self._img_needle_long.size = self.size
        self._gauge.pos = self.pos
        self._needleL.pos = (self.x, self.y)
        self._needleL.center = self._gauge.center
        self._needleS.pos = (self.x, self.y)
        self._needleS.center = self._gauge.center
        self._glab.center_x = self._gauge.center_x - dp(28)/dp(150)*self.size[0]
        self._glab.center_y = self._gauge.center_y + dp(1)/dp(150)*self.size[1]
        self._glab2.center_x = self._gauge.center_x
        self._glab2.center_y = self._gauge.center_y - dp(16)/dp(150)*self.size[1]

    def _turn(self, *args): # Turn needle
        self._needleS.center_x = self._gauge.center_x
        self._needleS.center_y = self._gauge.center_y
        self._needleS.rotation = ((1 * self.unit) - (self.value * self.unit * 2)/10)
        self._needleL.center_x = self._gauge.center_x
        self._needleL.center_y = self._gauge.center_y
        self._needleL.rotation = (1 * self.unit) - (self.value * self.unit * 2)        
        self._glab.text = "[b]{0:04d}[/b]".format(self.value)
        self._glab2.text = self.display_unit


class HGauge(Widget):
    '''
    Horizontal Speed Gauge
    '''
    display_unit = StringProperty("")
    unit = NumericProperty(1.8)
    value = BoundedNumericProperty(0, min=-400, max=400, errorvalue=0)
    size_text = NumericProperty(10)

    def __init__(self, **kwargs):
        super(HGauge, self).__init__(**kwargs)
        self.file_gauge = "assets/AirSpeedIndicator_Background_H.png"
        self.file_needle = "assets/needle.png"
        self._gauge = Scatter(
            size=self.size,
            do_rotation=False,
            do_scale=False,
            do_translation=False
        )
        self._img_gauge = Image(
            source=self.file_gauge,
            size=self.size
        )
        self._needle = Scatter(
            size=self.size,
            do_rotation=False,
            do_scale=False,
            do_translation=False
        )
        self._img_needle = Image(
            source=self.file_needle,
            size=self.size
        )
        self._glab = Label(font_size=dp(14), markup=True)
        self._glab2 = Label(font_size=dp(12), markup=True, color=[1, 1, 1, 1])
        self._gauge.add_widget(self._img_gauge)
        self._needle.add_widget(self._img_needle)
        self.add_widget(self._gauge)
        self.add_widget(self._needle)
        self.add_widget(self._glab2)
        self.bind(pos=self._update)
        self.bind(size=self._update)
        self.bind(value=self._turn)

    def _update(self, *args): # Update gauge and needle positions after sizing or positioning.
        self._glab2.font_size = dp(12) if self.height > dp(75) else dp(10)
        self._gauge.size = self.size
        self._img_gauge.size = self.size
        self._needle.size = self.size
        self._img_needle.size = self.size
        self._gauge.pos = self.pos
        self._needle.pos = (self.x, self.y)
        self._needle.center = self._gauge.center
        self._glab.center_x = self._gauge.center_x
        self._glab.center_y = self._gauge.center_y
        self._glab2.center_x = self._gauge.center_x
        self._glab2.center_y = self._gauge.center_y - dp(20)/dp(150)*self.size[1]

    def _turn(self, *args): # Turn needle
        self._needle.center_x = self._gauge.center_x
        self._needle.center_y = self._gauge.center_y
        self._needle.rotation = (100 * self.unit) - (self.value * self.unit * 4)
        self._glab2.text = self.display_unit


class VGauge(Widget):
    '''
    Vertical Speed Gauge
    '''
    display_unit = StringProperty("")
    unit = NumericProperty(1.8)
    value = BoundedNumericProperty(0, min=-14, max=14, errorvalue=0)
    size_text = NumericProperty(10)

    def __init__(self, **kwargs):
        super(VGauge, self).__init__(**kwargs)
        self.file_gauge = "assets/AirSpeedIndicator_Background_V.png"
        self.file_needle = "assets/needle.png"
        self._gauge = Scatter(
            size=self.size,
            do_rotation=False,
            do_scale=False,
            do_translation=False
        )
        self._img_gauge = Image(
            source=self.file_gauge,
            size=self.size
        )
        self._needle = Scatter(
            size=self.size,
            do_rotation=False,
            do_scale=False,
            do_translation=False
        )
        self._img_needle = Image(
            source=self.file_needle,
            size=self.size
        )
        self._glab = Label(font_size=dp(14), markup=True)
        self._glab2 = Label(font_size=dp(12), markup=True, color=[1, 1, 1, 1])
        self._gauge.add_widget(self._img_gauge)
        self._needle.add_widget(self._img_needle)
        self.add_widget(self._gauge)
        self.add_widget(self._needle)
        self.add_widget(self._glab2)
        self.bind(pos=self._update)
        self.bind(size=self._update)
        self.bind(value=self._turn)

    def _update(self, *args): # Update gauge and needle positions after sizing or positioning.
        self._glab2.font_size = dp(12) if self.height > dp(75) else dp(10)
        self._gauge.size = self.size
        self._img_gauge.size = self.size
        self._needle.size = self.size
        self._img_needle.size = self.size
        self._gauge.pos = self.pos
        self._needle.pos = (self.x, self.y)
        self._needle.center = self._gauge.center
        self._glab.center_x = self._gauge.center_x
        self._glab.center_y = self._gauge.center_y
        self._glab2.center_x = self._gauge.center_x
        self._glab2.center_y = self._gauge.center_y - dp(20)/dp(150)*self.size[1]

    def _turn(self, *args): # Turn needle
        self._needle.center_x = self._gauge.center_x
        self._needle.center_y = self._gauge.center_y
        self._needle.rotation = -(self.value * self.unit * 5.5)
        self._glab2.text = self.display_unit


class HeadingGauge(Widget):
    '''
    Heading Gauge (direction drone is travelling as opposed to direction drone is looking)
    '''
    unit = NumericProperty(1.8)
    value = BoundedNumericProperty(0, min=0, max=400, errorvalue=0)
    drotation = BoundedNumericProperty(0, min=0, max=400, errorvalue=0) #Rotational position of drone
    size_text = NumericProperty(10)

    def __init__(self, **kwargs):
        super(HeadingGauge, self).__init__(**kwargs)
        self.file_gauge = "assets/HeadingIndicator_Background1.png"
        self.file_heading_ring = "assets/HeadingRing.png"
        self.file_heading_aircraft = "assets/Heading_drone3a.png"
        self.size_gauge = dp(150)
        self._gauge = Scatter(
            size=self.size,
            do_rotation=False,
            do_scale=False,
            do_translation=False
        )
        self._img_gauge = Image(
            source=self.file_gauge,
            size=self.size
        )
        self._headingR = Scatter(
            size=self.size,
            do_rotation=False,
            do_scale=False,
            do_translation=False
        )
        self._aircrafT = Scatter(
            size=self.size,
            do_rotation=False,
            do_scale=False,
            do_translation=False
        )
        self._img_aircraft = Image(
            source=self.file_heading_aircraft,
            size=self.size
         )
        self._img_heading_ring = Image(
            source=self.file_heading_ring,
            size=self.size
        )
        self._gauge.add_widget(self._img_gauge)
        self._headingR.add_widget(self._img_heading_ring)
        self._aircrafT.add_widget(self._img_aircraft)
        self.add_widget(self._gauge)
        self.add_widget(self._headingR)
        self.add_widget(self._aircrafT)        
        self.bind(pos=self._update)
        self.bind(size=self._update)
        self.bind(value=self._turn)

    def _update(self, *args): # Update positioning.
        self._gauge.size = self.size
        self._img_gauge.size = self.size
        self._headingR.size = self.size
        self._aircrafT.size = self.size
        self._img_aircraft.size = self.size
        self._img_heading_ring.size = self.size
        self._gauge.pos = self.pos
        self._headingR.pos = (self.x, self.y)
        self._headingR.center = self._gauge.center
        self._aircrafT.pos = (self.x, self.y)

    def _turn(self, *args): # Turn
        self._headingR.center_x = self._gauge.center_x
        self._headingR.center_y = self._gauge.center_y
        self._headingR.rotation = (1 * self.unit) - (self.value * 1)
