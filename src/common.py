'''
Functions commonly used in the app - Developer: Koen Aerts
'''
import locale

class Common():

    def __init__(self, parent):
        self.parent = parent

    def dist_val(self, num):
        '''
        Return specified distance in the proper Unit (metric vs imperial).
        '''
        if num is None:
            return None
        return num * 3.28084 if self.parent.root.ids.selected_uom.text == 'imperial' else num


    def shorten_dist_val(self, numval):
        '''
        Convert ft to miles or m to km.
        '''
        if numval is None:
            return ""
        num = locale.atof(numval) if isinstance(numval, str) else numval
        return self.fmt_num(num / 5280.0, True) if self.parent.root.ids.selected_uom.text == 'imperial' else self.fmt_num(num / 1000.0, True)


    def dist_unit(self):
        '''
        Return selected distance unit of measure.
        '''
        return "ft" if self.parent.root.ids.selected_uom.text == 'imperial' else "m"


    def dist_unit_km(self):
        '''
        Return selected distance unit of measure.
        '''
        return "mi" if self.parent.root.ids.selected_uom.text == 'imperial' else "km"


    def fmt_num(self, num, decimal=False):
        '''
        Format number based on selected rounding option.
        '''
        if num is None:
            return ""
        return locale.format_string("%.0f", num, grouping=True, monetary=False) if self.parent.root.ids.selected_rounding.active and not decimal else locale.format_string("%.2f", num, grouping=True, monetary=False)


    def speed_val(self, num):
        '''
        Return specified speed in the proper Unit (metric vs imperial).
        '''
        if num is None:
            return None
        return num * 2.236936 if self.parent.root.ids.selected_uom.text == 'imperial' else num * 3.6


    def speed_unit(self):
        '''
        Return selected speed unit of measure.
        '''
        return "mph" if self.parent.root.ids.selected_uom.text == 'imperial' else "kph"
