from kivy.clock import Clock
from kivy.metrics import dp
from kivy.properties import NumericProperty, BoundedNumericProperty, StringProperty
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.scatter import Scatter
from kivy.uix.widget import Widget

class SplashScreen():
    splash_img = Image(source="assets/splash.png", fit_mode="scale-down")
    splash_text = None
    splash_win = None
    def __init__(self, window=None, text=None):
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
        Close the spash screen.
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
    file_gauge = StringProperty("assets/Distance_Background.png")
    file_needle_long = StringProperty("assets/LongNeedleAltimeter1a.png")
    file_needle_short = StringProperty("assets/SmallNeedleAltimeter1a.png")
    size_gauge = dp(150)

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
            size=(dp(self.size_gauge), dp(self.size_gauge)),
            do_rotation=False,
            do_scale=False,
            do_translation=False
        )
        self._needleS = Scatter(
            size=(dp(self.size_gauge), dp(self.size_gauge)),
            do_rotation=False,
            do_scale=False,
            do_translation=False
        )
        _img_needle_short = Image(
            source=self.file_needle_short,
            size=(dp(self.size_gauge), dp(self.size_gauge))
        )
        _img_needle_long = Image(
            source=self.file_needle_long,
            size=(dp(self.size_gauge), dp(self.size_gauge))
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


class AltGauge(Widget):
    '''
    Altitude Gauge
    '''
    display_unit = StringProperty("")
    unit = NumericProperty(1.8)
    value = BoundedNumericProperty(0, min=0, max=8000, errorvalue=0)
    file_gauge = StringProperty("assets/Altimeter_Background2.png")
    file_needle_long = StringProperty("assets/LongNeedleAltimeter1a.png")
    file_needle_short = StringProperty("assets/SmallNeedleAltimeter1a.png")
    size_gauge = dp(150)
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
            size=(dp(self.size_gauge), dp(self.size_gauge)),
            do_rotation=False,
            do_scale=False,
            do_translation=False
        )
        self._needleS = Scatter(
            size=(dp(self.size_gauge), dp(self.size_gauge)),
            do_rotation=False,
            do_scale=False,
            do_translation=False
        )        
        _img_needle_short = Image(
            source=self.file_needle_short,
            size=(dp(self.size_gauge), dp(self.size_gauge))
        )
        _img_needle_long = Image(
            source=self.file_needle_long,
            size=(dp(self.size_gauge), dp(self.size_gauge))
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


class HGauge(Widget):
    '''
    Horizontal Speed Gauge
    '''
    display_unit = StringProperty("")
    unit = NumericProperty(1.8)
    value = BoundedNumericProperty(0, min=-400, max=400, errorvalue=0)
    file_gauge = StringProperty("assets/AirSpeedIndicator_Background_H.png")
    file_needle = StringProperty("assets/needle.png")
    size_gauge = dp(150)
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


class VGauge(Widget):
    '''
    Vertical Speed Gauge
    '''
    display_unit = StringProperty("")
    unit = NumericProperty(1.8)
    value = BoundedNumericProperty(0, min=-14, max=14, errorvalue=0)
    file_gauge = StringProperty("assets/AirSpeedIndicator_Background_V.png")
    file_needle = StringProperty("assets/needle.png")
    size_gauge = dp(150)
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
        self._needle.rotation = -(self.value * self.unit * 5.5)
        self._glab2.text = self.display_unit


class HeadingGauge(Widget):
    '''
    Heading Gauge (direction drone is travelling as opposed to direction drone is looking)
    '''
    unit = NumericProperty(1.8)
    value = BoundedNumericProperty(0, min=0, max=400, errorvalue=0)
    drotation = BoundedNumericProperty(0, min=0, max=400, errorvalue=0) #Rotational position of drone
    file_gauge = StringProperty("assets/HeadingIndicator_Background1.png")
    file_heading_ring = StringProperty("assets/HeadingRing.png")
    file_heading_aircraft = StringProperty("assets/Heading_drone3a.png")
    size_gauge = dp(150)
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
            size=(dp(self.size_gauge), dp(self.size_gauge)),
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
        self._headingR.rotation = (1 * self.unit) - (self.value * 1)
