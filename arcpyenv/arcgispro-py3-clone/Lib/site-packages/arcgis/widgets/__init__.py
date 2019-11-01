try:
    from arcgis.widgets._mapview import MapView
except ImportError:
    class MapView:
        pass
