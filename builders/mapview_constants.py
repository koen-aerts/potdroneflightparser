from kivy.utils import platform
IS_IOS = platform == 'ios'
if IS_IOS:
    import os
    from plyer import storagepath
else:
    from platformdirs import user_cache_dir

MIN_LATITUDE = -90.0
MAX_LATITUDE = 90.0
MIN_LONGITUDE = -180.0
MAX_LONGITUDE = 180.0
CACHE_DIR = os.path.join(storagepath.get_documents_dir()[7:], '.data', 'cache') if IS_IOS else user_cache_dir("FlightLogViewer", "FlightLogViewer")
