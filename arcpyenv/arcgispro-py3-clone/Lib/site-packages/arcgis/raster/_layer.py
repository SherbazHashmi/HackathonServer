import json
import uuid
import datetime
import tempfile

from arcgis._impl.common._utils import _date_handler
from arcgis.gis import Layer
from arcgis.geometry import Geometry
from arcgis.features import FeatureSet
import logging
import arcgis as _arcgis
import base64

_LOGGER = logging.getLogger(__name__)


def _find_and_replace_mosaic_rule(fnarg_ra, mosaic_rule, url):
    for key,value in fnarg_ra.items():
        if key == "Raster" and isinstance(value,dict)  and not (value.keys() & {"url"}):
            return _find_and_replace_mosaic_rule(value["rasterFunctionArguments"], fnarg_ra)
        if key == "Rasters":
            if isinstance(value,list):
                for each_element in value:
                    return _find_and_replace_mosaic_rule(each_element["rasterFunctionArguments"], fnarg_ra)
        elif (key == "Raster"  or key == "Rasters"):
            if isinstance(value,dict):
                if value.keys() & {"url"}:
                    value["mosaicRule"] = mosaic_rule
            else:
                fnarg_ra[key]={}
                fnarg_ra[key]["url"] = url
                fnarg_ra[key]["mosaicRule"] = mosaic_rule

    return fnarg_ra

class ImageryLayer(Layer):
    def __init__(self, url, gis=None):
        self._datastore_raster = False
        self._uri = None
        if isinstance(url,bytes):
            url = base64.b64decode(url)
            url = url.decode("UTF-8")
            import ast
            url = ast.literal_eval(url)
        if '/fileShares/' in url or '/rasterStores/' in url or '/cloudStores/' in url or isinstance(url,dict) or '/vsi' in url or isinstance(url, bytes):
            self._gis = _arcgis.env.active_gis if gis is None else gis
            self._datastore_raster = True
            self._uri = url
            if isinstance(url,dict):
                encoded_dict = str(self._uri).encode('utf-8')
                self._uri = base64.b64encode(encoded_dict)
            gis = _arcgis.env.active_gis if gis is None else gis

            image_hosting_server_url = None
            raster_analytics_server_url = None
            hosting_server_url = None
            for ds in gis._datastores:
                if 'serverFunction' in ds._server.keys() and ds._server['serverFunction'] == 'ImageHosting':
                    image_hosting_server_url = ds._server['url']
                    break
                elif 'serverFunction' in ds._server.keys() and ds._server['serverFunction'] == 'RasterAnalytics':
                    raster_analytics_server_url = ds._server['url']
                elif 'serverFunction' in ds._server.keys() and ds._server['serverFunction'] == '':
                    hosting_server_url = ds._server['url']
            if image_hosting_server_url:
                url = image_hosting_server_url + "/rest/services/System/RasterRendering/ImageServer"
            elif raster_analytics_server_url:
                url = raster_analytics_server_url + "/rest/services/System/RasterRendering/ImageServer"
            else:
                url = hosting_server_url + "/rest/services/System/RasterRendering/ImageServer"

        super(ImageryLayer, self).__init__(url, gis)
        self._spatial_filter = None
        self._temporal_filter = None
        self._where_clause = '1=1'
        self._fn = None
        self._fnra = None
        self._filtered = False
        self._mosaic_rule = None
        self._extent = None
        self._uses_gbl_function = False
        self._other_outputs = {}

    @property
    def rasters(self):
        """
        Raster manager for this layer
        """
        if str(self.properties['capabilities']).lower().find('edit') > -1:
            return RasterManager(self)
        else:
            return None

    @property
    def tiles(self):
        """
        Imagery tile manager for this layer
        """
        if 'tileInfo' in self.properties:
            return ImageryTileManager(self)
        else:
            return None

    @property
    def service(self):
        """
        The service backing this imagery layer (if user can administer the service)
        """
        try:
            from arcgis.gis.server._service._adminfactory import AdminServiceGen
            return AdminServiceGen(service=self, gis=self._gis)
        except:
            return None

    #----------------------------------------------------------------------
    def catalog_item(self, id):
        """
        The Raster Catalog Item property represents a single raster catalog item

        =================     ====================================================================
        **Arguments**         **Description**
        -----------------     --------------------------------------------------------------------
        id                    required integer. The id is the 'raster id'.
        =================     ====================================================================

        """
        if self._datastore_raster:
            raise RuntimeError("This operation cannot be performed on a datastore raster")
        if str(self.properties['capabilities']).lower().find('catalog') == -1:
            return None
        return RasterCatalogItem(url="%s/%s" % (self._url, id),
                                 imglyr=self)


    @property
    def _lyr_json(self):
        url = self.url
        if self._token is not None:  # causing geoanalytics Invalid URL error
            url += '?token=' + self._token

        lyr_dict = {'type': type(self).__name__, 'url': url}

        options_dict = {
            "imageServiceParameters": {
            }
        }

        if self._fn is not None or self._mosaic_rule is not None:
            if self._fn is not None:
                options_dict["imageServiceParameters"]["renderingRule"] = self._fn

            if self._mosaic_rule is not None:
                options_dict["imageServiceParameters"]["mosaicRule"] = self._mosaic_rule

            lyr_dict.update({
                "options": json.dumps(options_dict)
            })
        lyr_dict.update({"uses_gbl": self._uses_gbl_function})
        return lyr_dict

    @classmethod
    def fromitem(cls, item):
        if not item.type == 'Image Service':
            raise TypeError("item must be a type of Image Service, not " + item.type)

        return cls(item.url, item._gis)

    @property
    def extent(self):
        """Area of interest. Used for displaying the imagery layer when queried"""
        if self._extent is None:
            if 'initialExtent' in self.properties:
                self._extent = self.properties.initialExtent
            elif 'extent' in self.properties:
                self._extent = self.properties.extent
        return self._extent

    @property
    def pixel_type(self):
        """returns pixel type of the imagery layer"""
        pixel_type = self.properties.pixelType
        return pixel_type

    @property
    def width(self):
        """returns width of the imagery layer"""
        width = self.properties.initialExtent["xmax"]-self.properties.initialExtent["xmin"]
        return width

    @property
    def height(self):
        """returns height of image service"""
        height = self.properties.initialExtent["ymax"]-self.properties.initialExtent["ymin"]
        return height

    @property
    def columns(self):
        """returns number of columns in the imagery layer"""
        number_of_columns = (self.properties.initialExtent["xmax"]-self.properties.initialExtent["xmin"])/self.properties.pixelSizeX
        return number_of_columns

    @property
    def rows(self):
        """returns number of rows in the imagery layer"""
        number_of_rows = (self.properties.initialExtent["ymax"]-self.properties.initialExtent["ymin"])/self.properties.pixelSizeY
        return number_of_rows

    @property
    def band_count(self):
        """returns the band count of the imagery layer"""
        band_count = self.properties.bandCount
        return band_count

    @property
    def histograms(self):
        """
        Returns the histograms of each band in the imagery layer as a list of dictionaries corresponding to each band.
        If not histograms is found, returns None. In this case, call the compute_histograms()
        :return:
            my_hist = imagery_layer.histograms()

            Structure of the return value:
            [
             { #band 1
              "size":256,
              "min":560,
              "max":24568,
              counts: [10,99,56,42200,125,....] #length of this list corresponds 'size'
             }
             { #band 3
              "size":256, #number of bins
              "min":8000,
              "max":15668,
              counts: [45,9,690,86580,857,....] #length of this list corresponds 'size'
             }
             ....
            ]

        """
        if self.properties.hasHistograms:
            #proceed
            url = self._url + "/histograms"
            params={'f':'json'}
            if self._datastore_raster:
                params["Raster"] =self._uri
            hist_return = self._con.post(url, params, token=self._token)

            #process this into a dict
            return hist_return['histograms']
        else:
            return None

    @extent.setter
    def extent(self, value):
        self._extent = value

    #----------------------------------------------------------------------
    def attribute_table(self, rendering_rule=None):
        """
        The attribute_table method returns categorical mapping of pixel
        values (for example, a class, group, category, or membership).

        =================     ====================================================================
        **Arguments**         **Description**
        -----------------     --------------------------------------------------------------------
        rendering_rule        Specifies the rendering rule for how the requested image should be
                              processed. The response is updated Layer info that reflects a
                              custom processing as defined by the rendering rule. For example, if
                              renderingRule contains an attributeTable function, the response
                              will indicate "hasRasterAttributeTable": true; if the renderingRule
                              contains functions that alter the number of bands, the response will
                              indicate a correct bandCount value.
        =================     ====================================================================

        :returns: dictionary

        """
        if "hasRasterAttributeTable" in self.properties and \
           self.properties["hasRasterAttributeTable"]:
            url = "%s/rasterAttributeTable" % self._url
            params = {'f' : 'json'}
            if rendering_rule is not None:
                params['renderingRule'] = rendering_rule
            elif self._fn is not None:
                params['renderingRule'] = self._fn

            if self._datastore_raster:
                params["Raster"]=self._uri
                if isinstance(self._uri, bytes):
                    del params['renderingRule']
                    params["Raster"]=self._uri

            return self._con.get(path=url,
                                 params=params)
        return None
    #----------------------------------------------------------------------
    @property
    def multidimensional_info(self):
        """
        The multidimensional_info property returns multidimensional
        informtion of the Layer. This property is supported if the
        hasMultidimensions property of the Layer is true.
        Common data sources for multidimensional image services are mosaic
        datasets created from netCDF, GRIB, and HDF data.
        """
        if "hasMultidimensions" in self.properties and \
           self.properties['hasMultidimensions'] == True:
            url = "%s/multiDimensionalInfo" % self._url
            params = {'f':'json'}
            if self._datastore_raster:
                params["Raster"]=self._uri
            return self._con.get(path=url, params=params)
        return None
    #----------------------------------------------------------------------
    def project(self,
                geometries,
                in_sr,
                out_sr):
        """
        The project operation is performed on an image layer method.
        This operation projects an array of input geometries from the input
        spatial reference to the output spatial reference. The response
        order of geometries is in the same order as they were requested.

        =================     ====================================================================
        **Arguments**         **Description**
        -----------------     --------------------------------------------------------------------
        geometries            required dictionary. The array of geometries to be projected.
        -----------------     --------------------------------------------------------------------
        in_sr                 required string, dictionary, SpatialReference.  The in_sr can accept a
                              multitudes of values.  These can be a WKID, image coordinate system
                              (ICSID), or image coordinate system in json/dict format.
                              Additionally the arcgis.geometry.SpatialReference object is also a
                              valid entry.
                              .. note :: An image coordinate system ID can be specified
                              using 0:icsid; for example, 0:64. The extra 0: is used to avoid
                              conflicts with wkid
        -----------------     --------------------------------------------------------------------
        out_sr                required string, dictionary, SpatialReference.  The in_sr can accept a
                              multitudes of values.  These can be a WKID, image coordinate system
                              (ICSID), or image coordinate system in json/dict format.
                              Additionally the arcgis.geometry.SpatialReference object is also a
                              valid entry.
                              .. note :: An image coordinate system ID can be specified
                              using 0:icsid; for example, 0:64. The extra 0: is used to avoid
                              conflicts with wkid
        =================     ====================================================================

        :returns: dictionary


        """
        url = "%s/project" % self._url
        params = {'f': 'json',
                  'inSR' : in_sr,
                  'outSR' : out_sr,
                  'geometries' : geometries
                  }
        if self._datastore_raster:
            params["Raster"]=self._uri
        return self._con.post(path=url,
                              postdata=params)
    #----------------------------------------------------------------------
    def identify(self,
                 geometry,
                 mosaic_rule=None,
                 rendering_rules=None,
                 pixel_size=None,
                 time_extent=None,
                 return_geometry=False,
                 return_catalog_items=True
                 ):
        """

        It identifies the content of an image layer for a given location
        and a given mosaic rule. The location can be a point or a polygon.

        The identify operation is supported by both mosaic dataset and
        raster dataset image services.

        The result of this operation includes the pixel value of the mosaic
        for a given mosaic rule, a resolution (pixel size), and a set of
        catalog items that overlap the given geometry. The single pixel
        value is that of the mosaic at the centroid of the specified
        location. If there are multiple rasters overlapping the location,
        the visibility of a raster is determined by the order of the
        rasters defined in the mosaic rule. It also contains a set of
        catalog items that overlap the given geometry. The catalog items
        are ordered based on the mosaic rule. A list of catalog item
        visibilities gives the percentage contribution of the item to
        overall mosaic.

        ====================  ====================================================================
        **Arguments**         **Description**
        --------------------  --------------------------------------------------------------------
        geometry              required dictionary/Point/Polygon.  A geometry that defines the
                              location to be identified. The location can be a point or polygon.
        --------------------  --------------------------------------------------------------------
        mosaic_rule           optional string or dict. Specifies the mosaic rule when defining how
                              individual images should be mosaicked. When a mosaic rule is not
                              specified, the default mosaic rule of the image layer will be used
                              (as advertised in the root resource: defaultMosaicMethod,
                              mosaicOperator, sortField, sortValue).
        --------------------  --------------------------------------------------------------------
        rendering_rules       optional dictionary/list. Specifies the rendering rule for how the
                              requested image should be rendered.
        --------------------  --------------------------------------------------------------------
        pixel_size            optional string or dict. The pixel level being identified (or the
                              resolution being looked at).
                              Syntax:
                               - JSON structure: pixelSize={point}
                               - Point simple syntax: pixelSize=<x>,<y>
        --------------------  --------------------------------------------------------------------
        time_extent           optional list of datetime objects or datetime object.  The time
                              instant or time extent of the raster to be identified. This
                              parameter is only valid if the image layer supports time.
        --------------------  --------------------------------------------------------------------
        return_geometry       optional boolean. Default is False.  Indicates whether or not to
                              return the raster catalog item's footprint. Set it to false when the
                              catalog item's footprint is not needed to improve the identify
                              operation's response time.
        --------------------  --------------------------------------------------------------------
        return_catalog_items  optional boolean.  Indicates whether or not to return raster catalog
                              items. Set it to false when catalog items are not needed to improve
                              the identify operation's performance significantly. When set to
                              false, neither the geometry nor attributes of catalog items will be
                              returned.
        ====================  ====================================================================

        :returns: dictionary

        """
        url = "%s/identify" % self._url
        params = {
            'f' : 'json',
            'geometry' : dict(geometry)
        }
        from arcgis.geometry._types import Point, Polygon
        if isinstance(geometry, Point):
            params['geometryType'] = 'esriGeometryPoint'
        if isinstance(geometry, Polygon):
            params['geometryType'] = 'esriGeometryPolygon'
        if mosaic_rule is not None:
            params['mosaicRule'] = mosaic_rule
        elif self._mosaic_rule is not None:
            params['mosaicRule'] = self._mosaic_rule

        if rendering_rules is not None:
            if isinstance(rendering_rules, dict):
                params['renderingRule'] = rendering_rules
            elif isinstance(rendering_rules, list):
                params['renderingRules'] = rendering_rules
            else:
                raise ValueError("Invalid Rendering Rules - It can be only be a dictionary or a list type object")
        elif self._fn:
            params['renderingRule'] = self._fn

        if pixel_size is not None:
            params['pixelSize'] = pixel_size
        if time_extent is not None:
            if isinstance(time_extent, datetime.datetime):
                time_extent = "%s" % int(time_extent.timestamp() * 1000)
            elif isinstance(time_extent, list):
                time_extent = "%s,%s" % (int(time_extent[0].timestamp() * 1000),
                                         int(time_extent[1].timestamp() * 1000))
            params['time'] = time_extent
        elif time_extent is None and \
             self._temporal_filter is not None:
            params['time'] = self._temporal_filter
        if isinstance(return_geometry, bool):
            params['returnGeometry'] = return_geometry
        if isinstance(return_catalog_items, bool):
            params['returnCatalogItems'] = return_catalog_items

        if self._datastore_raster:
            params["Raster"]=self._uri
            if isinstance(self._uri, bytes):
                del params['renderingRule']
                params["Raster"]=self._uri

        return self._con.post(path=url, postdata=params)

    #----------------------------------------------------------------------
    def measure(self,
                from_geometry,
                to_geometry=None,
                measure_operation=None,
                pixel_size=None,
                mosaic_rule=None,
                linear_unit=None,
                angular_unit=None,
                area_unit=None
                ):
        """
        The function lets a user measure distance, direction, area,
        perimeter, and height from an image layer. The result of this
        operation includes the name of the raster dataset being used,
        sensor name, and measured values.
        The measure operation can be supported by image services from
        raster datasets and mosaic datasets. Spatial reference is required
        to perform basic measurement (distance, area, and so on). Sensor
        metadata (geodata transformation) needs to be present in the data
        source used by an image layer to enable height measurement (for
        example, imagery with RPCs). The mosaic dataset or Layer needs to
        include DEM to perform 3D measure.

        =================     ====================================================================
        **Arguments**         **Description**
        -----------------     --------------------------------------------------------------------
        from_geometry         required Geomerty or dictionary. A geometry that defines the "from"
                              location of the measurement.
        -----------------     --------------------------------------------------------------------
        to_geometry           optional Geomerty. A geometry that defines the "to" location of the
                              measurement. The type of geometry must be the same as from_geometry.
        -----------------     --------------------------------------------------------------------
        measure_operation     optional string or dict. Specifies the type of measure being
                              performed.

                              Values: Point, DistanceAndAngle,AreaAndPerimeter,HeightFromBaseAndTop,
                              HeightFromBaseAndTopShadow,
                              HeightFromTopAndTopShadow,Centroid,
                              Point3D,DistanceAndAngle3D,
                              AreaAndPerimeter3D,Centroid3D

                              Different measureOperation types require different from and to
                              geometries:
                               - Point and Point3D-Require only
                                 from_geometry, type: {Point}
                               - DistanceAndAngle, DistanceAndAngle3D,
                               HeightFromBaseAndTop,
                               HeightFromBaseAndTopShadow, and
                               HeightFromTopAndTopShadow - Require both
                               from_geometry and to_geometry, type: {Point}
                               - AreaAndPerimeter,
                                 AreaAndPerimeter3D, Centroid, and
                                 Centroid3D - Require only from_geometry,
                                 type: {Polygon}, {Envelope}
                              Supported measure operations can be derived from the
                              mensurationCapabilities in the image layer root resource.
                              Basic capability supports Point,
                              DistanceAndAngle, AreaAndPerimeter,
                              and Centroid.
                              Basic and 3Dcapabilities support Point3D,
                              DistanceAndAngle3D,AreaAndPerimeter3D,
                              and Centroid3D.
                              Base-Top Height capability supports
                              HeightFromBaseAndTop.
                              Top-Top Shadow Height capability supports
                              HeightFromTopAndTopShadow.
                              Base-Top Shadow Height capability supports
                              HeightFromBaseAndTopShadow.
        -----------------     --------------------------------------------------------------------
        pixel_size            optional string or dict. The pixel level (resolution) being
                              measured. If pixel size is not specified, pixel_size will default to
                              the base resolution of the image layer. The raster at the specified pixel
                              size in the mosaic dataset will be used for measurement.
                              Syntax:
                               - JSON structure: pixelSize={point}
                               - Point simple syntax: pixelSize=<x>,<y>
                              Example:
                              pixel_size=0.18,0.18
        -----------------     --------------------------------------------------------------------
        mosaic_rule           optional string or dict. Specifies the mosaic rule when defining how
                              individual images should be mosaicked. When a mosaic rule is not
                              specified, the default mosaic rule of the image layer will be used
                              (as advertised in the root resource: defaultMosaicMethod,
                              mosaicOperator, sortField, sortValue). The first visible image is
                              used by measure.
        -----------------     --------------------------------------------------------------------
        linear_unit           optional string. The linear unit in which height, length, or
                              perimeters will be calculated. It can be any of the following
                              U constant. If the unit is not specified, the default is
                              Meters. The list of valid Units constants include:
                              Inches,Feet,Yards,Miles,NauticalMiles,
                              Millimeters,Centimeters,Decimeters,Meters,
                              Kilometers
        -----------------     --------------------------------------------------------------------
        angular_unit          optional string. The angular unit in which directions of line
                              segments will be calculated. It can be one of the following
                              DirectionUnits constants:
                              DURadians, DUDecimalDegrees
                              If the unit is not specified, the default is DUDecimalDegrees.
        -----------------     --------------------------------------------------------------------
        area_unit             optional string. The area unit in which areas of polygons will be
                              calculated. It can be any AreaUnits constant. If the unit is not
                              specified, the default is SquareMeters. The list of valid
                              AreaUnits constants include:
                              SquareInches,SquareFeet,SquareYards,Acres,
                              SquareMiles,SquareMillimeters,SquareCentimeters,
                              SquareDecimeters,SquareMeters,Ares,Hectares,
                              SquareKilometers
        =================     ====================================================================

        :returns: dictionary
        """
        if linear_unit is not None:
            linear_unit = "esri%s" % linear_unit
        if angular_unit is not None:
            angular_unit = "esri%s" % angular_unit
        if area_unit is not None:
            area_unit = "esri%s" % area_unit
        measure_operation = "esriMensuration%s" % measure_operation
        url = "%s/measure" % self._url
        params = {'f':'json',
                  'fromGeometry' : from_geometry}
        if self._datastore_raster:
            params["Raster"]=self._uri
        from arcgis.geometry._types import Polygon, Point, Envelope
        if isinstance(from_geometry, Polygon):
            params['geometryType'] = "esriGeometryPolygon"
        elif isinstance(from_geometry, Point):
            params['geometryType'] = "esriGeometryPoint"
        elif isinstance(from_geometry, Envelope):
            params['geometryType'] = "esriGeometryEnvelope"
        if to_geometry:
            params['toGeometry'] = to_geometry
        if measure_operation is not None:
            params['measureOperation'] = measure_operation
        if mosaic_rule is not None:
            params['mosaicRule'] = mosaic_rule
        elif self._mosaic_rule is not None:
            params['mosaicRule'] = self._mosaic_rule
        if pixel_size:
            params['pixelSize'] = pixel_size
        if linear_unit:
            params['linearUnit'] = linear_unit
        if area_unit:
            params['areaUnit'] = area_unit
        if angular_unit:
            params['angularUnit'] = angular_unit
        return self._con.post(path=url, postdata=params)


    def set_filter(self, where=None, geometry=None, time=None, lock_rasters=False, clear_filters=False):
        """
        Filters the rasters that will be used for applying raster functions.

        If lock_rasters is set True, the LockRaster mosaic rule will be applied to the layer, unless overridden

        =================     ====================================================================
        **Arguments**         **Description**
        -----------------     --------------------------------------------------------------------
        where                 optional string. A where clause on this layer to filter the imagery
                              layer by the selection sql statement. Any legal SQL where clause
                              operating on the fields in the raster
        -----------------     --------------------------------------------------------------------
        geometry              optional arcgis.geometry.filters. To filter results by a spatial
                              relationship with another geometry
        -----------------     --------------------------------------------------------------------
        time                  optional datetime, date, or timestamp. A temporal filter to this
                              layer to filter the imagery layer by time using the specified time
                              instant or the time extent.

                              Syntax: time_filter=<timeInstant>

                              Time extent specified as list of [<startTime>, <endTime>]
                              For time extents one of <startTime> or <endTime> could be None. A
                              None value specified for start time or end time will represent
                              infinity for start or end time respectively.
                              Syntax: time_filter=[<startTime>, <endTime>] ; specified as
                              datetime.date, datetime.datetime or timestamp in milliseconds
        -----------------     --------------------------------------------------------------------
        lock_rasters          optional boolean. If True, the LockRaster mosaic rule will be
                              applied to the layer, unless overridden
        -----------------     --------------------------------------------------------------------
        clear_filters         optional boolean. If True, the applied filters are cleared
        =================     ====================================================================


        """
        if self._datastore_raster:
            raise RuntimeError("This operation cannot be performed on a datastore raster")
        if clear_filters:
            self._filtered = False
            self._where_clause = None
            self._temporal_filter = None
            self._spatial_filter = None
            self._mosaic_rule = None
        else:
            self._filtered = True
            if where is not None:
                self._where_clause = where

            if geometry is not None:
                self._spatial_filter = geometry

            if time is not None:
                self._temporal_filter = time

            if lock_rasters:
                oids = self.query(where=self._where_clause,
                                  time_filter=self._temporal_filter,
                      geometry_filter=self._spatial_filter,
                      return_ids_only=True)['objectIds']
                self._mosaic_rule = {
                    "mosaicMethod" : "esriMosaicLockRaster",
                      "lockRasterIds": oids,
                      "ascending" : True,
                      "mosaicOperation" : "MT_FIRST"
                }

    def filter_by(self, where=None, geometry=None, time=None, lock_rasters=True):
        """
        Filters the layer by where clause, geometry and temporal filters

        =================     ====================================================================
        **Arguments**         **Description**
        -----------------     --------------------------------------------------------------------
        where                 optional string. A where clause on this layer to filter the imagery
                              layer by the selection sql statement. Any legal SQL where clause
                              operating on the fields in the raster
        -----------------     --------------------------------------------------------------------
        geometry              optional arcgis.geometry.filters. To filter results by a spatial
                              relationship with another geometry
        -----------------     --------------------------------------------------------------------
        time                  optional datetime, date, or timestamp. A temporal filter to this
                              layer to filter the imagery layer by time using the specified time
                              instant or the time extent.

                              Syntax: time_filter=<timeInstant>

                              Time extent specified as list of [<startTime>, <endTime>]
                              For time extents one of <startTime> or <endTime> could be None. A
                              None value specified for start time or end time will represent
                              infinity for start or end time respectively.
                              Syntax: time_filter=[<startTime>, <endTime>] ; specified as
                              datetime.date, datetime.datetime or timestamp in milliseconds
        -----------------     --------------------------------------------------------------------
        lock_rasters          optional boolean. If True, the LockRaster mosaic rule will be
                              applied to the layer, unless overridden
        =================     ====================================================================

        :return: ImageryLayer with filtered images meeting the filter criteria

        """
        if self._datastore_raster:
            raise RuntimeError("This operation cannot be performed on a datastore raster")
        newlyr = self._clone_layer()

        newlyr._where_clause = where
        newlyr._spatial_filter = geometry
        newlyr._temporal_filter = time

        if lock_rasters:
            oids = self.query(where=where,
                              time_filter=time,
                  geometry_filter=geometry,
                  return_ids_only=True)['objectIds']
            newlyr._mosaic_rule = {
                "mosaicMethod": "esriMosaicLockRaster",
                "lockRasterIds": oids,
                "ascending": True,
                "mosaicOperation": "MT_FIRST"
            }

        newlyr._filtered = True
        return newlyr

    def _clone_layer(self):
        if self._datastore_raster:
            newlyr = ImageryLayer(self._uri, self._gis)
        else:
            newlyr = ImageryLayer(self._url, self._gis)
        newlyr._lazy_properties = self.properties
        newlyr._hydrated = True
        newlyr._lazy_token = self._token

        newlyr._fn = self._fn
        newlyr._fnra = self._fnra
        newlyr._mosaic_rule = self._mosaic_rule
        newlyr._extent = self._extent

        # newlyr._where_clause = self._where_clause
        # newlyr._spatial_filter = self._spatial_filter
        # newlyr._temporal_filter = self._temporal_filter
        # newlyr._filtered = self._filtered

        return newlyr

    def filtered_rasters(self):
        """The object ids of the filtered rasters in this imagery layer, by applying the where clause, spatial and
        temporal filters. If no rasters are filtered, returns None. If all rasters are filtered, returns empty list"""

        if self._filtered:
            oids = self.query(where=self._where_clause,
                              time_filter=self._temporal_filter,
                  geometry_filter=self._spatial_filter,
                  return_ids_only=True)['objectIds']
            return oids #['$' + str(x) for x in oids]
        else:
            return None # return '$$'

    def export_image(self,
                     bbox=None,
                     image_sr=None,
                     bbox_sr=None,
                     size=None,
                     time=None,
                     export_format="jpgpng",
                     pixel_type=None,
                     no_data=None,
                     no_data_interpretation="esriNoDataMatchAny",
                     interpolation=None,
                     compression=None,
                     compression_quality=None,
                     band_ids=None,
                     mosaic_rule=None,
                     rendering_rule=None,
                     f="json",
                     save_folder=None,
                     save_file=None,
                     compression_tolerance=None,
                     adjust_aspect_ratio=None,
                     lerc_version=None
                     ):
        """
        The export_image operation is performed on an imagery layer.
        The result of this operation is an image method. This method
        provides information about the exported image, such as its URL,
        extent, width, and height.
        In addition to the usual response formats of HTML and JSON, you can
        also request the image format while performing this operation. When
        you perform an export with the image format , the server responds
        by directly streaming the image bytes to the client. With this
        approach, you don't get any information associated with the
        exported image other than the image itself.

        ======================  ====================================================================
        **Arguments**           **Description**
        ----------------------  --------------------------------------------------------------------
        bbox                    Optional dict or string. The extent (bounding box) of the exported
                                image. Unless the bbox_sr parameter has been specified, the bbox is
                                assumed to be in the spatial reference of the imagery layer.

                                The bbox should be specified as an arcgis.geometry.Envelope object,
                                it's json representation or as a list or string with this
                                format: '<xmin>, <ymin>, <xmax>, <ymax>'
                                If omitted, the extent of the imagery layer is used
        ----------------------  --------------------------------------------------------------------
        image_sr                optional string, SpatialReference. The spatial reference of the
                                exported image. The spatial reference can be specified as either a
                                well-known ID, it's json representation or as an
                                arcgis.geometry.SpatialReference object.
                                If the image_sr is not specified, the image will be exported in the
                                spatial reference of the imagery layer.
        ----------------------  --------------------------------------------------------------------
        bbox_sr                 optional string, SpatialReference. The spatial reference of the
                                bbox.
                                The spatial reference can be specified as either a well-known ID,
                                it's json representation or as an arcgis.geometry.SpatialReference
                                object.
                                If the image_sr is not specified, bbox is assumed to be in the
                                spatial reference of the imagery layer.
        ----------------------  --------------------------------------------------------------------
        size                    optional list. The size (width * height) of the exported image in
                                pixels. If size is not specified, an image with a default size of
                                1200*450 will be exported.
                                Syntax: list of [width, height]
        ----------------------  --------------------------------------------------------------------
        time                    optional datetime.date, datetime.datetime or timestamp string. The
                                time instant or the time extent of the exported image.
                                Time instant specified as datetime.date, datetime.datetime or
                                timestamp in milliseconds since epoch
                                Syntax: time=<timeInstant>

                                Time extent specified as list of [<startTime>, <endTime>]
                                For time extents one of <startTime> or <endTime> could be None. A
                                None value specified for start time or end time will represent
                                infinity for start or end time respectively.
                                Syntax: time=[<startTime>, <endTime>] ; specified as
                                datetime.date, datetime.datetime or timestamp
        ----------------------  --------------------------------------------------------------------
        export_format           optional string. The format of the exported image. The default
                                format is jpgpng. The jpgpng format returns a JPG if there are no
                                transparent pixels in the requested extent; otherwise, it returns a
                                PNG (png32).

                                Values: jpgpng,png,png8,png24,jpg,bmp,gif,tiff,png32,bip,bsq,lerc
        ----------------------  --------------------------------------------------------------------
        pixel_type              optional string. The pixel type, also known as data type, pertains
                                to the type of values stored in the raster, such as signed integer,
                                unsigned integer, or floating point. Integers are whole numbers,
                                whereas floating points have decimals.
        ----------------------  --------------------------------------------------------------------
        no_data                 optional float. The pixel value representing no information.
        ----------------------  --------------------------------------------------------------------
        no_data_interpretation  optional string. Interpretation of the no_data setting. The default
                                is NoDataMatchAny when no_data is a number, and NoDataMatchAll when
                                no_data is a comma-delimited string: NoDataMatchAny,NoDataMatchAll.
        ----------------------  --------------------------------------------------------------------
        interpolation           optional string. The resampling process of extrapolating the pixel
                                values while transforming the raster dataset when it undergoes
                                warping or when it changes coordinate space.
                                One of: RSP_BilinearInterpolation, RSP_CubicConvolution,
                                RSP_Majority, RSP_NearestNeighbor
        ----------------------  --------------------------------------------------------------------
        compression             optional string. Controls how to compress the image when exporting
                                to TIFF format: None, JPEG, LZ77. It does not control compression on
                                other formats.
        ----------------------  --------------------------------------------------------------------
        compression_quality     optional integer. Controls how much loss the image will be subjected
                                to by the compression algorithm. Valid value ranges of compression
                                quality are from 0 to 100.
        ----------------------  --------------------------------------------------------------------
        band_ids                optional list. If there are multiple bands, you can specify a single
                                band to export, or you can change the band combination (red, green,
                                blue) by specifying the band number. Band number is 0 based.
                                Specified as list of ints, eg [2,1,0]
        ----------------------  --------------------------------------------------------------------
        mosaic_rule             optional dict. Specifies the mosaic rule when defining how
                                individual images should be mosaicked. When a mosaic rule is not
                                specified, the default mosaic rule of the image layer will be used
                                (as advertised in the root resource: defaultMosaicMethod,
                                mosaicOperator, sortField, sortValue).
        ----------------------  --------------------------------------------------------------------
        rendering_rule          optional dict. Specifies the rendering rule for how the requested
                                image should be rendered.
        ----------------------  --------------------------------------------------------------------
        f                       optional string. The response format.  default is json
                                Values: json,image,kmz
                                If image format is chosen, the bytes of the exported image are
                                returned unless save_folder and save_file parameters are also
                                passed, in which case the image is written to the specified file
        ----------------------  --------------------------------------------------------------------
        save_folder             optional string. The folder in which the exported image is saved
                                when f=image
        ----------------------  --------------------------------------------------------------------
        save_file               optional string. The file in which the exported image is saved when
                                f=image
        ----------------------  --------------------------------------------------------------------
        compression_tolerance   optional float. Controls the tolerance of the lerc compression
                                algorithm. The tolerance defines the maximum possible error of pixel
                                values in the compressed image.
                                Example: compression_tolerance=0.5 is loseless for 8 and 16 bit
                                images, but has an accuracy of +-0.5 for floating point data. The
                                compression tolerance works for the LERC format only.
        ----------------------  --------------------------------------------------------------------
        adjust_aspect_ratio     optional boolean. Indicates whether to adjust the aspect ratio or
                                not. By default adjust_aspect_ratio is true, that means the actual
                                bbox will be adjusted to match the width/height ratio of size
                                paramter, and the response image has square pixels.
        ----------------------  --------------------------------------------------------------------
        lerc_version            optional integer. The version of the Lerc format if the user sets
                                the format as lerc.
                                Values: 1 or 2
                                If a version is specified, the server returns the matching version,
                                or otherwise the highest version available.
        ======================  ====================================================================

        :returns: dict or string

        """

        import datetime
        no_data_interpretation = "esri%s" % no_data_interpretation
        if size is None:
            size = [1200, 450]

        params = {
            "size": "%s,%s" % (size[0], size[1]),

        }

        if bbox is not None:
            if type(bbox) == str:
                params['bbox'] = bbox
            elif type(bbox) == list:
                params['bbox'] = "%s,%s,%s,%s" % (bbox[0], bbox[1], bbox[2], bbox[3])
            else: # json dict or Geometry Envelope object
                if bbox_sr is None:
                    if 'spatialReference' in bbox:
                        bbox_sr = bbox['spatialReference']

                bbox = "%s,%s,%s,%s" % (bbox['xmin'], bbox['ymin'], bbox['xmax'], bbox['ymax'])
                params['bbox'] = bbox



        else:
            params['bbox'] = self.extent # properties.initialExtent
            if bbox_sr is None:
                if 'spatialReference' in self.extent:
                    bbox_sr = self.extent['spatialReference']

        if image_sr is not None:
            params['imageSR'] = image_sr
        if bbox_sr is not None:
            params['bboxSR'] = bbox_sr
        if pixel_type is not None:
            params['pixelType'] = pixel_type

        url = self._url + "/exportImage"
        __allowedFormat = ["jpgpng", "png",
                           "png8", "png24",
                           "jpg", "bmp",
                           "gif", "tiff",
                           "png32", "bip", "bsq", "lerc"]
        __allowedPixelTypes = [
            "C128", "C64", "F32",
            "F64", "S16", "S32",
            "S8", "U1", "U16",
            "U2", "U32", "U4",
            "U8", "UNKNOWN"
        ]
        __allowednoDataInt = [
            "esriNoDataMatchAny",
            "esriNoDataMatchAll"
        ]
        __allowedInterpolation = [
            "RSP_BilinearInterpolation",
            "RSP_CubicConvolution",
            "RSP_Majority",
            "RSP_NearestNeighbor"
        ]
        __allowedCompression = [
            "JPEG", "LZ77"
        ]
        if mosaic_rule is not None:
            params["mosaicRule"] = mosaic_rule
        elif self._mosaic_rule is not None:
            params["mosaicRule"] = self._mosaic_rule

        if export_format in __allowedFormat:
            params['format'] = export_format

        if self._temporal_filter is not None:
            time = self._temporal_filter

        if time is not None:
            if type(time) is list:
                starttime = _date_handler(time[0])
                endtime = _date_handler(time[1])
                if starttime is None:
                    starttime = 'null'
                if endtime is None:
                    endtime = 'null'
                params['time'] = "%s,%s" % (starttime, endtime)
            else:
                params['time'] = _date_handler(time)

        if interpolation is not None and \
           interpolation in __allowedInterpolation and \
                        isinstance(interpolation, str):
            params['interpolation'] = interpolation

        if pixel_type is not None and \
           pixel_type in __allowedPixelTypes:
            params['pixelType'] = pixel_type

        if no_data_interpretation in __allowedInterpolation:
            params['noDataInterpretation'] = no_data_interpretation

        if no_data is not None:
            params['noData'] = no_data

        if compression is not None and \
           compression in __allowedCompression:
            params['compression'] = compression

        if band_ids is not None and \
           isinstance(band_ids, list):
            params['bandIds'] = ",".join([str(x) for x in band_ids])

        if rendering_rule is not None:
            if 'function_chain' in rendering_rule:
                params['renderingRule'] = rendering_rule['function_chain']
            else:
                params['renderingRule'] = rendering_rule

        elif self._fn is not None:
            if not self._uses_gbl_function:
                params['renderingRule'] = self._fn
            else:
                _LOGGER.warning("""Imagery layer object containing global functions in the function chain cannot be used for dynamic visualization.
                                   \nThe layer output must be saved as a new image service before it can be visualized. Use save() method of the layer object to create the processed output.""")
                return None

        if compression_tolerance is not None:
            params['compressionTolerance'] = compression_tolerance

        if compression_quality is not None:
            params['compressionQuality'] = compression_quality

        if adjust_aspect_ratio is not None:
            if adjust_aspect_ratio is True:
                params['adjustAspectRatio'] = 'true'
            else:
                params['adjustAspectRatio'] = 'false'

        params["f"] = f

        if lerc_version:
            params['lercVersion'] = lerc_version

        if self._datastore_raster:
            params["Raster"]=self._uri
            if isinstance(self._uri, bytes):
                del params['renderingRule']
                params["Raster"]=self._uri

        if f == "json":
            return self._con.post(url, params, token=self._token)
        elif f == "image":
            if save_folder is not None and save_file is not None:
                return self._con.post(url, params,
                                      out_folder=save_folder, try_json=False,
                                   file_name=save_file, token=self._token)
            else:
                return self._con.post(url, params,
                                      try_json=False, force_bytes=True,
                                     token=self._token)
        elif f == "kmz":
            return self._con.post(url, params,
                                  out_folder=save_folder,
                                 file_name=save_file, token=self._token)
        else:
            print('Unsupported output format')

    # ----------------------------------------------------------------------
    def query(self,
              where=None,
              out_fields="*",
              time_filter=None,
              geometry_filter=None,
              return_geometry=True,
              return_ids_only=False,
              return_count_only=False,
              pixel_size=None,
              order_by_fields=None,
              return_distinct_values=None,
              out_statistics=None,
              group_by_fields_for_statistics=None,
              out_sr=None,
              return_all_records=False,
              object_ids=None,
              multi_dimensional_def=None,
              result_offset=None,
              result_record_count=None,
              max_allowable_offset=None,
              true_curves=False
              ):
        """ queries an imagery layer by applying the filter specified by the user. The result of this operation is
         either a set of features or an array of raster IDs (if return_ids_only is set to True),
         count (if return_count_only is set to True), or a set of field statistics (if out_statistics is used).

        ==============================  ====================================================================
        **Arguments**                   **Description**
        ------------------------------  --------------------------------------------------------------------
        where                           optional string. A where clause on this layer to filter the imagery
                                        layer by the selection sql statement. Any legal SQL where clause
                                        operating on the fields in the raster
        ------------------------------  --------------------------------------------------------------------
        out_fields                      optional string. The attribute fields to return, comma-delimited
                                        list of field names.
        ------------------------------  --------------------------------------------------------------------
        time_filter                     optional datetime.date, datetime.datetime or timestamp in
                                        milliseconds. The time instant or the time extent of the exported
                                        image.

                                        Syntax: time_filter=<timeInstant>

                                        Time extent specified as list of [<startTime>, <endTime>]
                                        For time extents one of <startTime> or <endTime> could be None. A
                                        None value specified for start time or end time will represent
                                        infinity for start or end time respectively.
                                        Syntax: time_filter=[<startTime>, <endTime>] ; specified as
                                        datetime.date, datetime.datetime or timestamp in milliseconds
        ------------------------------  --------------------------------------------------------------------
        geometry_filter                 optional arcgis.geometry.filters. Spatial filter from
                                        arcgis.geometry.filters module to filter results by a spatial
                                        relationship with another geometry.
        ------------------------------  --------------------------------------------------------------------
        return_geometry                 optional boolean. True means a geometry will be returned, else just
                                        the attributes
        ------------------------------  --------------------------------------------------------------------
        return_ids_only                 optional boolean. False is default.  True means only OBJECTIDs will
                                        be returned
        ------------------------------  --------------------------------------------------------------------
        return_count_only               optional boolean. If True, then an integer is returned only based on
                                        the sql statement
        ------------------------------  --------------------------------------------------------------------
        pixel_size                      optional dict or list. Query visible rasters at a given pixel size.
                                        If pixel_size is not specified, rasters at all resolutions can be
                                        queried.
        ------------------------------  --------------------------------------------------------------------
        order_by_fields                 optional string. Order results by one or more field names. Use ASC
                                        or DESC for ascending or descending order, respectively.
        ------------------------------  --------------------------------------------------------------------
        return_distinct_values           optional boolean. If true, returns distinct values based on the
                                         fields specified in out_fields. This parameter applies only if the
                                         supportsAdvancedQueries property of the image layer is true.
        ------------------------------  --------------------------------------------------------------------
        out_statistics                  optional dict or string. The definitions for one or more field-based
                                        statistics to be calculated.
        ------------------------------  --------------------------------------------------------------------
        group_by_fields_for_statistics  optional dict/string. One or more field names using the
                                        values that need to be grouped for calculating the
                                        statistics.
        ------------------------------  --------------------------------------------------------------------
        out_sr                          optional dict, SpatialReference. If the returning geometry needs to
                                        be in a different spatial reference, provide the function with the
                                        desired WKID.
        ------------------------------  --------------------------------------------------------------------
        return_all_records              optional boolean. If True(default) all records will be returned.
                                        False means only the limit of records will be returned.
        ------------------------------  --------------------------------------------------------------------
        object_ids                      optional string. The object IDs of this raster catalog to be
                                        queried. When this parameter is specified, any other filter
                                        parameters (including where) are ignored.
                                        When this parameter is specified, setting return_ids_only=true is
                                        invalid.
                                        Syntax: objectIds=<objectId1>, <objectId2>
                                        Example: objectIds=37, 462
        ------------------------------  --------------------------------------------------------------------
        multi_dimensional_def           optional dict. The filters defined by multiple dimensional
                                        definitions.
        ------------------------------  --------------------------------------------------------------------
        result_offset                   optional integer. This option fetches query results by skipping a
                                        specified number of records. The query results start from the next
                                        record (i.e., resultOffset + 1). The Default value is None.
        ------------------------------  --------------------------------------------------------------------
        result_record_count             optional integer. This option fetches query results up to the
                                        resultRecordCount specified. When resultOffset is specified and this
                                        parameter is not, image layer defaults to maxRecordCount. The
                                        maximum value for this parameter is the value of the layer's
                                        maxRecordCount property.
                                        max_allowable_offset - This option can be used to specify the
                                        max_allowable_offset to be used for generalizing geometries returned
                                        by the query operation. The max_allowable_offset is in the units of
                                        the out_sr. If outSR is not specified, max_allowable_offset is
                                        assumed to be in the unit of the spatial reference of the Layer.
        ------------------------------  --------------------------------------------------------------------
        true_curves                     optional boolean. If true, returns true curves in output geometries,
                                        otherwise curves get converted to densified polylines or polygons.
        ==============================  ====================================================================

        :returns: A FeatureSet containing the footprints (features) matching the query when
                  return_geometry is True, else a dictionary containing the expected return
                  type.
         """

        if self._datastore_raster:
            raise RuntimeError("This operation cannot be performed on a datastore raster")

        params = {"f": "json",
                  "outFields": out_fields,
                  "returnGeometry": return_geometry,
                  "returnIdsOnly": return_ids_only,
                  "returnCountOnly": return_count_only,
                  }
        if object_ids:
            params['objectIds'] = object_ids
        if multi_dimensional_def:
            params['multidimensionalDefinition'] = multi_dimensional_def
        if result_offset:
            params['resultOffset'] = result_offset
        if result_record_count:
            params['resultRecordCount'] = result_record_count
        if max_allowable_offset:
            params['maxAllowableOffset'] = max_allowable_offset
        if true_curves:
            params['returnTrueCurves'] = true_curves
        if where is not None:
            params['where'] = where
        elif self._where_clause is not None:
            params['where'] = self._where_clause
        else:
            params['where'] = '1=1'

        if not group_by_fields_for_statistics is None:
            params['groupByFieldsForStatistics'] = group_by_fields_for_statistics
        if not out_statistics is None:
            params['outStatistics'] = out_statistics


        if self._temporal_filter is not None:
            time_filter = self._temporal_filter

        if time_filter is not None:
            if type(time_filter) is list:
                starttime = _date_handler(time_filter[0])
                endtime = _date_handler(time_filter[1])
                if starttime is None:
                    starttime = 'null'
                if endtime is None:
                    endtime = 'null'
                params['time'] = "%s,%s" % (starttime, endtime)
            else:
                params['time'] = _date_handler(time_filter)


        if self._spatial_filter is not None:
            geometry_filter = self._spatial_filter

        if not geometry_filter is None and \
           isinstance(geometry_filter, dict):
            gf = geometry_filter
            params['geometry'] = gf['geometry']
            params['geometryType'] = gf['geometryType']
            params['spatialRel'] = gf['spatialRel']
            if 'inSR' in gf:
                params['inSR'] = gf['inSR']

        if pixel_size is not None:
            params['pixelSize'] = pixel_size
        if order_by_fields is not None:
            params['orderByFields'] = order_by_fields
        if return_distinct_values is not None:
            params['returnDistinctValues'] = return_distinct_values
        if out_sr is not None:
            params['outSR'] = out_sr
        url = self._url + "/query"
        if return_all_records and \
           return_count_only == False:
            count = self.query(where=where, geometry_filter=geometry_filter,
                               time_filter=time_filter, return_count_only=True)
            if count > self.properties.maxRecordCount:
                n = count // self.properties.maxRecordCount
                if (count % self.properties.maxRecordCount) > 0:
                    n += 1
                records = None
                for i in range(n):
                    if records is None:
                        params['resultOffset'] = i * self.properties.maxRecordCount
                        params['resultRecordCount'] = self.properties.maxRecordCount
                        records = self._con.post(path=url,
                                                 postdata=params,
                                                token=self._token)

                    else:
                        params['resultOffset'] = i * self.properties.maxRecordCount
                        params['resultRecordCount'] = self.properties.maxRecordCount
                        res = self._con.post(path=url,
                                             postdata=params,
                                             token=self._token)
                        records['features'] += res['features']
                result = records
            else:
                result = self._con.post(path=url, postdata=params, token=self._token)
        else:
            result = self._con.post(path=url, postdata=params, token=self._token)

        if 'error' in result:
            raise ValueError(result)

        if return_count_only:
            return result['count']
        elif return_ids_only:
            return result
        elif return_geometry:
            return FeatureSet.from_dict(result)
        else:
            return result
    #----------------------------------------------------------------------
    def get_download_info(self,
                          raster_ids,
                          polygon=None,
                          extent=None,
                          out_format=None):
        """
        The Download Rasters operation returns information (the file ID)
        that can be used to download the raw raster files that are
        associated with a specified set of rasters in the raster catalog.

        =================     ====================================================================
        **Argument**          **Description**
        -----------------     --------------------------------------------------------------------
        raster_ids            required string. A comma-separated list of raster IDs whose files
                              are to be downloaded.
        -----------------     --------------------------------------------------------------------
        polygon               optional Polygon, The geometry to apply for clipping
        -----------------     --------------------------------------------------------------------
        extent                optional string. The geometry to apply for clipping
                              example: "-104,35.6,-94.32,41"
        -----------------     --------------------------------------------------------------------
        out_format            optional string. The format of the rasters returned. If not
                              specified, the rasters will be in their native format.
                              The format applies when the clip geometry is also specified, and the
                              format will be honored only when the raster is clipped.

                              To force the Download Rasters operation to convert source images to
                              a different format, append :Conversion after format string.
                              Valid formats include: TIFF, Imagine Image, JPEG, BIL, BSQ, BIP,
                              ENVI, JP2, GIF, BMP, and PNG.
                              Example: out_format='TIFF'
        =================     ====================================================================
        """
        if self._datastore_raster:
            raise RuntimeError("This operation cannot be performed on a datastore raster")

        url = "%s/download" % self._url
        if self.properties['capabilities'].lower().find('download') == -1:
            return
        params = {
            'f' : 'json',
            'rasterIds' : raster_ids,
        }
        if polygon is not None:
            params['geometry'] = polygon
            params['geometryType'] = "esriGeometryPolygon"
        if extent is not None:
            params['geometry'] = extent
            params['geometryType'] = "esriGeometryEnvelope"
        if out_format is not None:
            params['format'] = out_format
        return self._con.post(path=url, postdata=params)
    #----------------------------------------------------------------------
    def get_raster_file(self,
                        download_info,
                        out_folder=None):
        """
        The Raster File method represents a single raw raster file. The
        download_info is obtained by using the get_download_info operation.


        =================     ====================================================================
        **Argument**          **Description**
        -----------------     --------------------------------------------------------------------
        download_info         required dictionary. This is derived from the get_downlad_info().
        -----------------     --------------------------------------------------------------------
        out_folder            optional string. Path to the file save location. If the value is
                              None, the OS temporary directory is used.
        =================     ====================================================================

        :returns: list of files downloaded
        """
        if self._datastore_raster:
            raise RuntimeError("This operation cannot be performed on a datastore raster")

        import os
        import tempfile
        cap = self.properties['capabilities'].lower()
        if cap.find("download") == -1 or \
           cap.find('catalog') == -1:
            return None

        if out_folder is None:
            out_folder = tempfile.gettempdir()
        if out_folder and \
           os.path.isdir(out_folder) == False:
            os.makedirs(out_folder, exist_ok=True)
        url = "%s/file" % self._url
        params = {'f' : 'json'}
        p = []
        files = []
        if 'rasterFiles' in download_info:
            for f in download_info['rasterFiles']:
                params = {'f' : 'json'}
                params['id'] = f['id']
                for rid in f['rasterIds']:
                    params["rasterId"] = rid
                    files.append(self._con.get(path=url,
                                               params=params,
                                               out_folder=out_folder,
                                               file_name=os.path.basename(params['id']))
                                 )
                del f
        return files

    # ----------------------------------------------------------------------
    def compute_pixel_location(self,
                               raster_id,
                             geometries,
                             spatial_reference):
        """

        With given input geometries, it calculates corresponding pixel location
        in column and row on specific raster catalog item.
        A prerequisite is that the raster catalog item has valid icsToPixel resource.

        =================     ====================================================================
        **Arguments**         **Description**
        -----------------     --------------------------------------------------------------------
        raster_id             required integer. Specifies the objectId of image service's raster
                              catalog. This integer rasterId number will determine which raster's
                              image coordinate system will be used during the calculation and
                              which raster does the column and row of results represent.
        -----------------     --------------------------------------------------------------------
        geometries            The array of geometries for computing pixel locations.
                              All geometries in this array should be of the type defined by geometryType.

        -----------------     --------------------------------------------------------------------
        spatial_reference     required string, dictionary,
                              This specifies the spatial reference of the Geometries parameter above.
                              It can accept a multitudes of values.  These can be a WKID,
                              image coordinate system (ICSID), or image coordinate system in json/dict format.
                              Additionally the arcgis.geometry.SpatialReference object is also a
                              valid entry.
                              .. note :: An image coordinate system ID can be specified
                              using 0:icsid; for example, 0:64. The extra 0: is used to avoid
                              conflicts with wkid
        -----------------     --------------------------------------------------------------------

        :returns: dictionary, The result of this operation includes x and y values for the column
                  and row of each input geometry. It also includes a z value for the height at given
                  location based on elevation info that the catalog raster item has.


        """
        url = "%s/computePixelLocation" % self._url
        params = {'f': 'json',
                  'rasterId':raster_id,
                  'geometries' : geometries,
                  'spatialReference' : spatial_reference
                  }
        return self._con.post(path=url,
                              postdata=params)

    # ----------------------------------------------------------------------
    def _add_rasters(self,
                     raster_type,
                    item_ids=None,
                    service_url=None,
                    compute_statistics=False,
                    build_pyramids=False,
                    build_thumbnail=False,
                    minimum_cell_size_factor=None,
                    maximum_cell_size_factor=None,
                    attributes=None,
                    geodata_transforms=None,
                    geodata_transform_apply_method="esriGeodataTransformApplyAppend"
                    ):
        """
        This operation is supported at 10.1 and later.
        The Add Rasters operation is performed on an image layer method.
        The Add Rasters operation adds new rasters to an image layer
        (POST only).
        The added rasters can either be uploaded items, using the item_ids
        parameter, or published services, using the service_url parameter.
        If item_ids is specified, uploaded rasters are copied to the image
        Layer's dynamic image workspace location; if the service_url is
        specified, the image layer adds the URL to the mosaic dataset no
        raster files are copied. The service_url is required input for the
        following raster types: Image Layer, Map Service, WCS, and WMS.

        Inputs:

        item_ids - The upload items (raster files) to be added. Either
         item_ids or service_url is needed to perform this operation.
            Syntax: item_ids=<itemId1>,<itemId2>
            Example: item_ids=ib740c7bb-e5d0-4156-9cea-12fa7d3a472c,
                             ib740c7bb-e2d0-4106-9fea-12fa7d3a482c
        service_url - The URL of the service to be added. The image layer
         will add this URL to the mosaic dataset. Either item_ids or
         service_url is needed to perform this operation. The service URL is
         required for the following raster types: Image Layer, Map
         Service, WCS, and WMS.
            Example: service_url=http://myserver/arcgis/services/Portland/ImageServer
        raster_type - The type of raster files being added. Raster types
         define the metadata and processing template for raster files to be
         added. Allowed values are listed in image layer resource.
            Example: Raster Dataset,CADRG/ECRG,CIB,DTED,Image Layer,Map Service,NITF,WCS,WMS
        compute_statistics - If true, statistics for the rasters will be
         computed. The default is false.
            Values: false,true
        build_pyramids - If true, builds pyramids for the rasters. The
         default is false.
                Values: false,true
        build_thumbnail	 - If true, generates a thumbnail for the rasters.
         The default is false.
                Values: false,true
        minimum_cell_size_factor - The factor (times raster resolution) used
         to populate the MinPS field (maximum cell size above which the
         raster is visible).
                Syntax: minimum_cell_size_factor=<minimum_cell_size_factor>
                Example: minimum_cell_size_factor=0.1
        maximum_cell_size_factor - The factor (times raster resolution) used
         to populate MaxPS field (maximum cell size below which raster is
         visible).
                Syntax: maximum_cell_size_factor=<maximum_cell_size_factor>
                Example: maximum_cell_size_factor=10
        attributes - Any attribute for the added rasters.
                Syntax:
                {
                  "<name1>" : <value1>,
                  "<name2>" : <value2>
                }
                Example:
                {
                  "MinPS": 0,
                  "MaxPS": 20;
                  "Year" : 2002,
                  "State" : "Florida"
                }
        geodata_transforms - The geodata transformations applied on the
         added rasters. A geodata transformation is a mathematical model
         that performs a geometric transformation on a raster; it defines
         how the pixels will be transformed when displayed or accessed.
         Polynomial, projective, identity, and other transformations are
         available. The geodata transformations are applied to the dataset
         that is added.
                Syntax:
                [
                {
                  "geodataTransform" : "<geodataTransformName1>",
                  "geodataTransformArguments" : {<geodataTransformArguments1>}
                  },
                  {
                  "geodataTransform" : "<geodataTransformName2>",
                  "geodataTransformArguments" : {<geodataTransformArguments2>}
                  }
                ]
         The syntax of the geodataTransformArguments property varies based
         on the specified geodataTransform name. See Geodata Transformations
         documentation for more details.
        geodata_transform_apply_method - This parameter defines how to apply
         the provided geodataTransform. The default is
         esriGeodataTransformApplyAppend.
                Values: esriGeodataTransformApplyAppend |
                esriGeodataTransformApplyReplace |
                esriGeodataTransformApplyOverwrite
        """
        if self._datastore_raster:
            raise RuntimeError("This operation cannot be performed on a datastore raster")

        url = self._url + "/add"
        params = {
            "f": "json"
        }
        if item_ids is None and service_url is None:
            raise Exception("An itemId or service_url must be provided")
        if isinstance(item_ids, str):
            item_ids = [item_ids]
        if isinstance(service_url, str):
            service_url = [service_url]
        params['geodataTransformApplyMethod'] = geodata_transform_apply_method
        params['rasterType'] = raster_type
        params['buildPyramids'] = build_pyramids
        params['buildThumbnail'] = build_thumbnail
        params['minimumCellSizeFactor'] = minimum_cell_size_factor
        params['computeStatistics'] = compute_statistics
        params['maximumCellSizeFactor'] = maximum_cell_size_factor
        params['attributes'] = attributes
        params['geodataTransforms'] = geodata_transforms
        if not item_ids is None:
            params['itemIds'] = item_ids
        if not service_url is None:
            params['serviceUrl'] = service_url
        return self._con.post(url, params, token=self._token)
    #----------------------------------------------------------------------
    def _delete_rasters(self, raster_ids):
        """
        The Delete Rasters operation deletes one or more rasters in an image layer.

        =================     ====================================================================
        **Argument**          **Description**
        -----------------     --------------------------------------------------------------------
        raster_ids            required string. The object IDs of a raster catalog items to be
                              removed. This is a comma seperated string.
                              example 1: raster_ids='1,2,3,4' # Multiple IDs
                              example 2: raster_ids='10' # single ID
        =================     ====================================================================

        :returns: dictionary
        """
        if self._datastore_raster:
            raise RuntimeError("This operation cannot be performed on a datastore raster")
        params = {"f" : 'json',
                  "rasterIds" : raster_ids}
        url = "%s/delete" % self._url
        return self._con.post(path=url, postdata=params)
    #----------------------------------------------------------------------
    def _update_raster(self,
                       raster_id,
                      files=None,
                      item_ids=None,
                      service_url=None,
                      compute_statistics=False,
                      build_pyramids=False,
                      build_thumbnail=False,
                      minimum_cell_size_factor=None,
                      maximum_cell_size_factor=None,
                      attributes=None,
                      footprint=None,
                      geodata_transforms=None,
                      apply_method="esriGeodataTransformApplyAppend"
                      ):
        """
        The Update Raster operation updates rasters (attributes and
        footprints, or replaces existing raster files) in an image layer.
        In most cases, this operation is used to update attributes or
        footprints of existing rasters in an image layer. In cases where
        the original raster needs to be replaced, the new raster can either
        be items uploaded using the items parameter or URLs of published
        services using the serviceUrl parameter.

        =================     ====================================================================
        **Argument**          **Description**
        -----------------     --------------------------------------------------------------------
        raster_ids            required integer. The object IDs of a raster catalog items to be
                              updated.
        -----------------     --------------------------------------------------------------------
        files                 optional list. Local source location to the raster to replace the
                              dataset with.
                              Example: [r"<path>\data.tiff"]
        -----------------     --------------------------------------------------------------------
        item_ids              optional string.  The uploaded items (raster files) being used to
                              replace existing raster.
        -----------------     --------------------------------------------------------------------
        service_url           optional string. The URL of the layer to be uploaded to replace
                              existing raster data. The image layer will add this URL to the
                              mosaic dataset. The serviceUrl is required for the following raster
                              types: Image Layer, Map Service, WCS, and WMS.
        -----------------     --------------------------------------------------------------------
        compute_statistics    If true, statistics for the uploaded raster will be computed. The
                              default is false.
        -----------------     --------------------------------------------------------------------
        build_pyramids        optional boolean. If true, builds pyramids for the uploaded raster.
                              The default is false.
        -----------------     --------------------------------------------------------------------
        build_thumbnail       optional boolean. If true, generates a thumbnail for the uploaded
                              raster. The default is false.
        -----------------     --------------------------------------------------------------------
        minimum_cell_size_factor optional float. The factor (times raster resolution) used to
                                 populate MinPS field (minimum cell size above which raster is
                                 visible).
        -----------------     --------------------------------------------------------------------
        maximum_cell_size_factor optional float. The factor (times raster resolution) used to
                                 populate MaxPS field (maximum cell size below which raster is
                                 visible).
        -----------------     --------------------------------------------------------------------
        footprint             optional Polygon.  A JSON 2D polygon object that defines the
                              footprint of the raster. If the spatial reference is not defined, it
                              will default to the image layer's spatial reference.
        -----------------     --------------------------------------------------------------------
        attributes            optional dictionary.  Any attribute for the uploaded raster.
        -----------------     --------------------------------------------------------------------
        geodata_transforms    optional string. The geodata transformations applied on the updated
                              rasters. A geodata transformation is a mathematical model that
                              performs geometric transformation on a raster. It defines how the
                              pixels will be transformed when displayed or accessed, such as
                              polynomial, projective, or identity transformations. The geodata
                              transformations will be applied to the updated dataset.
        -----------------     --------------------------------------------------------------------
        apply_method          optional string. Defines how to apply the provided geodataTransform.
                              The default is esriGeodataTransformApplyAppend.
                              Values: esriGeodataTransformApplyAppend,
                                      esriGeodataTransformApplyReplace,
                                      esriGeodataTransformApplyOverwrite
        =================     ====================================================================

        :returns: dictionary
        """
        if self._datastore_raster:
            raise RuntimeError("This operation cannot be performed on a datastore raster")
        url = "%s/update" % self._url
        ids = []
        if files:
            for f in files:
                u = self._upload(fp=f)
                if u:
                    ids.append(u)
            item_ids = ",".join(ids)
        params = {
            "f" : "json",
            "rasterId" : raster_id,
        }
        if item_ids is not None:
            params['itemIds'] = item_ids
        if service_url is not None:
            params['serviceUrl'] = service_url
        if compute_statistics is not None:
            params['computeStatistics'] = compute_statistics
        if build_pyramids is not None:
            params['buildPyramids'] = build_pyramids
        if build_thumbnail is not None:
            params['buildThumbnail'] = build_thumbnail
        if minimum_cell_size_factor is not None:
            params['minimumCellSizeFactor'] = minimum_cell_size_factor
        if maximum_cell_size_factor is not None:
            params['maximumCellSizeFactor'] = maximum_cell_size_factor
        if footprint is not None:
            params['footprint'] = footprint
        if attributes is not None:
            params['attributes'] = attributes
        if geodata_transforms is not None:
            params['geodataTransforms'] = geodata_transforms
        if apply_method is not None:
            params['geodataTransformApplyMethod'] = apply_method
        return self._con.post(path=url, postdata=params)
    #----------------------------------------------------------------------
    def _upload(self, fp, description=None):
        """uploads a file to the image layer"""
        if self._datastore_raster:
            raise RuntimeError("This operation cannot be performed on a datastore raster")
        url = "%s/uploads/upload" % self._url
        params = {
            "f" : 'json'
        }
        if description:
            params['description'] = description
        files = {'file' : fp }
        res = self._con.post(path=url, postdata=params, files=files)
        if 'success' in res and res['success']:
            return res['item']['itemID']
        return None
    #----------------------------------------------------------------------
    def compute_stats_and_histograms(self,
                                     geometry,
                                     mosaic_rule=None,
                                     rendering_rule=None,
                                     pixel_size=None,
                                     ):
        """
        The result of this operation contains both statistics and histograms
        computed from the given extent.

        =================     ====================================================================
        **Argument**          **Description**
        -----------------     --------------------------------------------------------------------
        geometry              required Polygon or Extent. A geometry that defines the geometry
                              within which the histogram is computed. The geometry can be an
                              envelope or a polygon
        -----------------     --------------------------------------------------------------------
        mosaic_rule           optional dictionary.  Specifies the mosaic rule when defining how
                              individual images should be mosaicked. When a mosaic rule is not
                              specified, the default mosaic rule of the image layer will be used
                              (as advertised in the root resource: defaultMosaicMethod,
                              mosaicOperator, sortField, sortValue).
        -----------------     --------------------------------------------------------------------
        rendering_rule        optional dictionary. Specifies the rendering rule for how the
                              requested image should be rendered.
        -----------------     --------------------------------------------------------------------
        pixel_size            optional string or dict. The pixel level being used (or the
                              resolution being looked at). If pixel size is not specified, then
                              pixel_size will default to the base resolution of the dataset. The
                              raster at the specified pixel size in the mosaic dataset will be
                              used for histogram calculation.
        =================     ====================================================================

        :returns: dictionary

        """
        url = "%s/computeStatisticsHistograms" % self._url
        from arcgis.geometry import Polygon
        if isinstance(geometry, Polygon):
            gt = "esriGeometryPolygon"
        else:
            gt = "esriGeometryEnvelope"
        params = {
            'f' : 'json',
            'geometry' : geometry,
            'geometryType' : gt
        }
        if pixel_size is not None:
            params['pixelSize'] = pixel_size
        if rendering_rule is not None:
            params['renderingRule'] = rendering_rule
        elif self._fn is not None:
            params['renderingRule'] = self._fn
        if mosaic_rule is not None:
            params['mosaicRule'] = mosaic_rule
        elif self._mosaic_rule is not None:
            params['mosaicRule'] = self._mosaic_rule

        if self._datastore_raster:
            params["Raster"]=self._uri
            if isinstance(self._uri, bytes):
                del params['renderingRule']

        return self._con.post(path=url, postdata=params)
    #----------------------------------------------------------------------
    def compute_tie_points(self,
                           raster_id,
                           geodata_transforms):
        """
        The result of this operation contains tie points that can be used
        to match the source image to the reference image. The reference
        image is configured by the image layer publisher. For more
        information, see Fundamentals for georeferencing a raster dataset.

        ==================    ====================================================================
        **Argument**          **Description**
        ------------------    --------------------------------------------------------------------
        raster_id             required integer. Source raster ID.
        ------------------    --------------------------------------------------------------------
        geodata_transforms    required dictionary. The geodata transformation that provides a
                              rough fit of the source image to the reference image. For example, a
                              first order polynomial transformation that fits the source image to
                              the expected location.
        ==================    ====================================================================

        :returns: dictionary
        """

        if self._datastore_raster:
            raise RuntimeError("This operation cannot be performed on a datastore raster")
        url = "%s/computeTiePoints" % self._url
        params = {
            'f' : 'json',
            'rasterId' : raster_id,
            'geodataTransform' : geodata_transforms
        }
        return self._con.post(path=url, postdata=params)
    #----------------------------------------------------------------------
    def legend(self,
               band_ids=None,
               rendering_rule=None,
               as_html=False):
        """
        The legend information includes the symbol images and labels for
        each symbol. Each symbol is generally an image of size 20 x 20
        pixels at 96 DPI. Symbol sizes may vary slightly for some renderer
        types (e.g., Vector Field Renderer). Additional information in the
        legend response will include the layer name, layer type, label,
        and content type.
        The legend symbols include the base64 encoded imageData. The
        symbols returned in response to an image layer legend request
        reflect the default renderer of the image layer or the renderer
        defined by the rendering rule and band Ids.

        =================     ====================================================================
        **Argument**          **Description**
        -----------------     --------------------------------------------------------------------
        band_ids              optional string. If there are multiple bands, you can specify a
                              single band, or you can change the band combination (red, green,
                              blue) by specifying the band ID. Band ID is 0 based.
                              Example: bandIds=2,1,0
        -----------------     --------------------------------------------------------------------
        rendering_rule        optional dictionary. Specifies the rendering rule for how the
                              requested image should be rendered.
        -----------------     --------------------------------------------------------------------
        as_html               optional bool. Returns an HTML table if True
        =================     ====================================================================

        :returns: legend as a dictionary by default, or as an HTML table if as_html is True
        """
        url = "%s/legend" % self._url
        params = {'f' : 'json'}
        if band_ids is not None:
            params['bandIds'] = band_ids
        if rendering_rule is not None:
            params['renderingRule'] = rendering_rule
        elif self._fn is not None:
            params['renderingRule'] = self._fn

        if self._datastore_raster:
            params["Raster"]=self._uri
            if isinstance(self._uri, bytes):
                del params['renderingRule']

        legend = self._con.post(path=url, postdata=params)
        if as_html is True:
            legend_table = "<table>"
            for legend_element in legend['layers'][0]['legend']:
                thumbnail = "data:{0};base64,{1}".format(legend_element['contentType'],
                                                         legend_element['imageData'])
                width = legend_element['width']
                height = legend_element['height']
                imgtag = '<img src="{0}" width="{1}"  height="{2}" />'.format(thumbnail, width, height)
                legend_table += "<tr><td>" + imgtag + '</td><td>' + legend_element['label'] + '</td></tr>'
            legend_table += "</table>"
            return legend_table
        else:
            return legend

    # ----------------------------------------------------------------------
    def colormap(self):
        """
        The colormap method returns RGB color representation of pixel
        values. This method is supported if the hasColormap property of
        the layer is true.
        """
        if self.properties.hasColormap:
            url = self._url + "/colormap"
            params = {
                "f": "json"
            }
            if self._datastore_raster:
                params["Raster"]=self._uri
            return self._con.get(url, params, token=self._token)
        else:
            return None
    #----------------------------------------------------------------------
    def compute_class_stats(self,
                            descriptions,
                            mosaic_rule="defaultMosaicMethod",
                            rendering_rule=None,
                            pixel_size=None
                            ):
        """
        Compute class statistics signatures (used by the maximum likelihood
        classifier)

        ===============     ====================================================================
        **Argument**        **Description**
        ---------------     --------------------------------------------------------------------
        descriptions        Required list. Class descriptions are training site polygons and
                            their class descriptions. The structure of the geometry is the same
                            as the structure of the JSON geometry objects returned by the
                            ArcGIS REST API.

                            :Syntax:
                            {
                                "classes":  [  // An list of classes
                                  {
                                    "id" : <id>,
                                    "name" : "<name>",
                                    "geometry" : <geometry> //polygon
                                  },
                                  {
                                    "id" : <id>,
                                    "name" : "<name>",
                                   "geometry" : <geometry>  //polygon
                                  }
                                  ...
                                  ]
                            }

        ---------------     --------------------------------------------------------------------
        mosaic_rule         optional string. Specifies the mosaic rule when defining how
                            individual images should be mosaicked. When a mosaic rule is not
                            specified, the default mosaic rule of the image layer will be used
                            (as advertised in the root resource: defaultMosaicMethod,
                            mosaicOperator, sortField, sortValue).
                            See Mosaic rule objects help for more information:
                            http://resources.arcgis.com/en/help/arcgis-rest-api/index.html#//02r3000000s4000000
        ---------------     --------------------------------------------------------------------
        rendering_rule      optional dictionary. Specifies the rendering rule for how the
                            requested image should be rendered.
                            See the raster function objects for the JSON syntax and examples.
                            http://resources.arcgis.com/en/help/arcgis-rest-api/index.html#/Raster_function_objects/02r3000000rv000000/
        ---------------     --------------------------------------------------------------------
        pixel_size          optional list or dictionary. The pixel level being used (or the
                            resolution being looked at). If pixel size is not specified, then
                            pixel_size will default to the base resolution of the dataset.
                            The structure of the pixel_size parameter is the same as the
                            structure of the point object returned by the ArcGIS REST API.
                            In addition to the JSON structure, you can specify the pixel size
                            with a comma-separated syntax.

                            Syntax:
                               JSON structure: pixelSize={point}
                               Point simple syntax: pixelSize=<x>,<y>
                            Examples:
                               pixelSize={"x": 0.18, "y": 0.18}
                               pixelSize=0.18,0.18
        ===============     ====================================================================

        :returns: dictionary
        """
        url = self._url + "/computeClassStatistics"

        params = {
            'f': 'json',
            "classDescriptions" : descriptions,
            "mosaicRule" : mosaic_rule
        }
        if self._mosaic_rule is not None and \
           mosaic_rule is None:
            params['mosaicRule'] = self._mosaic_rule
        if rendering_rule is not None:
            params['renderingRule'] = rendering_rule
        if pixel_size is not None:
            params['pixelSize'] = pixel_size

        if self._datastore_raster:
            params["Raster"]=self._uri
            if isinstance(self._uri, bytes):
                del params['renderingRule']

        return self._con.post(path=url, postdata=params)
    # ----------------------------------------------------------------------
    def compute_histograms(self, geometry, mosaic_rule=None,
                           rendering_rule=None, pixel_size=None):
        """
        The compute_histograms operation is performed on an imagery layer
        method. This operation is supported by any imagery layer published with
        mosaic datasets or a raster dataset. The result of this operation contains
        both statistics and histograms computed from the given extent.

        =================     ====================================================================
        **Arguments**         **Description**
        -----------------     --------------------------------------------------------------------
        geometry              required Polygon or Extent. A geometry that defines the geometry
                              within which the histogram is computed. The geometry can be an
                              envelope or a polygon
        -----------------     --------------------------------------------------------------------
        mosaic_rule           optional string. Specifies the mosaic rule when defining how
                              individual images should be mosaicked. When a mosaic rule is not
                              specified, the default mosaic rule of the image layer will be used
                              (as advertised in the root resource: defaultMosaicMethod,
                              mosaicOperator, sortField, sortValue).
                              See Mosaic rule objects help for more information:
                              http://resources.arcgis.com/en/help/arcgis-rest-api/index.html#//02r3000000s4000000
        -----------------     --------------------------------------------------------------------
        rendering_rule        Specifies the rendering rule for how the requested image should be
                              processed. The response is updated Layer info that reflects a
                              custom processing as defined by the rendering rule. For example, if
                              renderingRule contains an attributeTable function, the response
                              will indicate "hasRasterAttributeTable": true; if the renderingRule
                              contains functions that alter the number of bands, the response will
                              indicate a correct bandCount value.
        -----------------     --------------------------------------------------------------------
        pixel_size            optional list or dictionary. The pixel level being used (or the
                              resolution being looked at). If pixel size is not specified, then
                              pixel_size will default to the base resolution of the dataset.
                              The structure of the pixel_size parameter is the same as the
                              structure of the point object returned by the ArcGIS REST API.
                              In addition to the JSON structure, you can specify the pixel size
                              with a comma-separated syntax.

                              Syntax:
                                 JSON structure: pixelSize={point}
                                 Point simple syntax: pixelSize=<x>,<y>
                              Examples:
                                 pixelSize={"x": 0.18, "y": 0.18}
                                 pixelSize=0.18,0.18
        =================     ====================================================================

        :returns: dict

        """

        url = self._url + "/computeHistograms"
        params = {
            "f": "json",
            "geometry": geometry,
        }

        if 'xmin' in geometry:
            params["geometryType"] = 'esriGeometryEnvelope'
        else:
            params["geometryType"] = 'esriGeometryPolygon'


        if mosaic_rule is not None:
            params["moasiacRule"] = mosaic_rule
        elif self._mosaic_rule is not None:
            params["moasiacRule"] = self._mosaic_rule

        if not rendering_rule is None:
            params["renderingRule"] = rendering_rule
        elif self._fn is not None:
            params['renderingRule'] = self._fn

        if not pixel_size is None:
            params["pixelSize"] = pixel_size

        if self._datastore_raster:
            params["Raster"]=self._uri
            if isinstance(self._uri, bytes):
                del params['renderingRule']

        return self._con.post(url, params, token=self._token)

        # ----------------------------------------------------------------------

    def get_samples(self, geometry, geometry_type=None,
                    sample_distance=None, sample_count=None, mosaic_rule=None,
                   pixel_size=None, return_first_value_only=None, interpolation=None,
                   out_fields=None):
        """
        The get_samples operation is supported by both mosaic dataset and raster
        dataset imagery layers.
        The result of this operation includes sample point locations, pixel
        values, and corresponding spatial resolutions of the source data for a
        given geometry. When the input geometry is a polyline, envelope, or
        polygon, sampling is based on sample_count or sample_distance; when the
        input geometry is a point or multipoint, the point or points are used
        directly.
        The number of sample locations in the response is based on the
        sample_distance or sample_count parameter and cannot exceed the limit of
        the image layer (the default is 1000, which is an approximate limit).

        =======================  =======================================================================
        **Argument**             **Description**
        -----------------------  -----------------------------------------------------------------------
        geometry                 A geometry that defines the location(s) to be sampled. The
                                 structure of the geometry is the same as the structure of the JSON
                                 geometry objects returned by the ArcGIS REST API. Applicable geometry
                                 types are point, multipoint, polyline, polygon, and envelope. When
                                 spatial reference is omitted in the input geometry, it will be assumed
                                 to be the spatial reference of the image layer.
        -----------------------  -----------------------------------------------------------------------
        geometry_type            optional string. The type of geometry specified by the geometry
                                 parameter.
                                 The geometry type can be point, multipoint, polyline, polygon, or
                                 envelope.
        -----------------------  -----------------------------------------------------------------------
        sample_distance          optional float. The distance interval used to sample points from
                                 the provided path. The unit is the same as the input geometry. If
                                 neither sample_count nor sample_distance is provided, no
                                 densification can be done for paths (polylines), and a default
                                 sample_count (100) is used for areas (polygons or envelopes).
        -----------------------  -----------------------------------------------------------------------
        sample_count             optional integer. The approximate number of sample locations from
                                 the provided path. If neither sample_count nor sample_distance is
                                 provided, no densification can be done for paths (polylines), and a
                                 default sample_count (100) is used for areas (polygons or envelopes).
        -----------------------  -----------------------------------------------------------------------
        mosaic_rule              optional dictionary.  Specifies the mosaic rule when defining how
                                 individual images should be mosaicked. When a mosaic rule is not
                                 specified, the default mosaic rule of the image layer will be used
                                 (as advertised in the root resource: defaultMosaicMethod,
                                 mosaicOperator, sortField, sortValue).
        -----------------------  -----------------------------------------------------------------------
        pixel_size               optional string or dict. The pixel level being used (or the
                                 resolution being looked at). If pixel size is not specified, then
                                 pixel_size will default to the base resolution of the dataset. The
                                 raster at the specified pixel size in the mosaic dataset will be
                                 used for histogram calculation.
        -----------------------  -----------------------------------------------------------------------
        return_first_value_only  optional boolean. Indicates whether to return all values at a
                                 point, or return the first non-NoData value based on the current
                                 mosaic rule.
                                 The default is true.
        -----------------------  -----------------------------------------------------------------------
        interpolation            optional string. The resampling method. Default is nearest neighbor.
                                 Values: RSP_BilinearInterpolation,RSP_CubicConvolution,
                                         RSP_Majority,RSP_NearestNeighbor
        -----------------------  -----------------------------------------------------------------------
        out_fields               optional string. The list of fields to be included in the response.
                                 This list is a comma-delimited list of field names. You can also
                                 specify the wildcard character (*) as the value of this parameter to
                                 include all the field values in the results.
        =======================  =======================================================================

        """

        if not isinstance(geometry, Geometry):
            geometry = Geometry(geometry)

        if geometry_type is None:
            geometry_type = 'esriGeometry' + geometry.type

        url = self._url + "/getSamples"
        params = {
            "f": "json",
            "geometry": geometry,
            "geometryType": geometry_type
        }

        if not sample_distance is None:
            params["sampleDistance"] = sample_distance
        if not sample_count is None:
            params["sampleCount"] = sample_count
        if not mosaic_rule is None:
            params["mosaicRule"] = mosaic_rule
        elif self._mosaic_rule is not None:
            params["moasiacRule"] = self._mosaic_rule
        if not pixel_size is None:
            params["pixelSize"] = pixel_size
        if not return_first_value_only is None:
            params["returnFirstValueOnly"] = return_first_value_only
        if not interpolation is None:
            params["interpolation"] = interpolation
        if not out_fields is None:
            params["outFields"] = out_fields
        if self._datastore_raster:
            params["Raster"]=self._uri

        sample_data = self._con.get(url, params, token=self._token)['samples']
        from copy import deepcopy
        new_sample_data = deepcopy(sample_data)
        # region: Try to convert values to list of numbers if it makes sense
        try:
            for element in new_sample_data:
                if 'value' in element and isinstance(element['value'], str):
                    pix_values_numbers = [float(s) for s in element['value'].split(' ')]
                    element['values'] = pix_values_numbers
            sample_data = new_sample_data
        except:
            pass  # revert and return the original data as is.

        # endregion
        return sample_data

    def key_properties(self, rendering_rule=None):
        """
        returns key properties of the imagery layer, such as band properties

        =================     ====================================================================
        **Argument**          **Description**
        -----------------     --------------------------------------------------------------------
        rendering_rule        optional dictionary. Specifies the rendering rule for how the
                              requested image should be rendered.
        =================     ====================================================================

        :return: key properties of the imagery layer
        """
        url = self._url + "/keyProperties"
        params = {
            "f": "json"
        }

        if rendering_rule is not None:
            params['renderingRule'] = rendering_rule
        elif self._fn is not None:
            params['renderingRule'] = self._fn

        if self._datastore_raster:
            params["Raster"]=self._uri
            if isinstance(self._uri, bytes):
                del params['renderingRule']

        return self._con.get(url, params, token=self._token)



    def mosaic_by(self, method=None, sort_by=None, sort_val=None, lock_rasters=None, viewpt=None, asc=True, where=None, fids=None,
                  muldidef=None, op="first", item_rendering_rule=None):
        """
        Defines how individual images in this layer should be mosaicked. It specifies selection,
        mosaic method, sort order, overlapping pixel resolution, etc. Mosaic rules are for mosaicking rasters in
        the mosaic dataset. A mosaic rule is used to define:

        * The selection of rasters that will participate in the mosaic (using where clause).
        * The mosaic method, e.g. how the selected rasters are ordered.
        * The mosaic operation, e.g. how overlapping pixels at the same location are resolved.

        =================     ====================================================================
        **Argument**          **Description**
        -----------------     --------------------------------------------------------------------
        method                optional string. Determines how the selected rasters are ordered.
                              str, can be none,center,nadir,northwest,seamline,viewpoint,
                              attribute,lock-raster
                              required if method is: center,nadir,northwest,seamline, optional
                              otherwise. If no method is passed "none" method is used, which uses
                              the order of records to sort
                              If sort_by and optionally sort_val parameters are specified,
                              "attribute" method is used
                              If lock_rasters are specified, "lock-raster" method is used
                              If a viewpt parameter is passed, "viewpoint" method is used.
        -----------------     --------------------------------------------------------------------
        sort_by               optional string. field name when sorting by attributes
        -----------------     --------------------------------------------------------------------
        sort_val              optional string. A constant value defining a reference or base value
                              for the sort field when sorting by attributes
        -----------------     --------------------------------------------------------------------
        lock_rasters          optional, an array of raster Ids. All the rasters with the given
                              list of raster Ids are selected to participate in the mosaic. The
                              rasters will be visible at all pixel sizes regardless of the minimum
                              and maximum pixel size range of the locked rasters.
        -----------------     --------------------------------------------------------------------
        viewpt                optional point, used as view point for viewpoint mosaicking method
        -----------------     --------------------------------------------------------------------
        asc                   optional bool, indicate whether to use ascending or descending
                              order. Default is ascending order.
        -----------------     --------------------------------------------------------------------
        where                 optional string. where clause to define a subset of rasters used in
                              the mosaic, be aware that the rasters may not be visible at all
                              scales
        -----------------     --------------------------------------------------------------------
        fids                  optional list of objectids, use the raster id list to define a
                              subset of rasters used in the mosaic, be aware that the rasters may
                              not be visible at all scales.
        -----------------     --------------------------------------------------------------------
        muldidef              optional array. multidemensional definition used for filtering by
                              variable/dimensions.
                              See http://resources.arcgis.com/en/help/arcgis-rest-api/index.html#//02r300000290000000
        -----------------     --------------------------------------------------------------------
        op                    optional string, first,last,min,max,mean,blend,sum mosaic operation
                              to resolve overlap pixel values: from first or last raster, use the
                              min, max or mean of the pixel values, or blend them.
        -----------------     --------------------------------------------------------------------
        item_rendering_rule   optional item rendering rule, applied on items before mosaicking.
        =================     ====================================================================

        :return: a mosaic rule defined in the format at
            http://resources.arcgis.com/en/help/arcgis-rest-api/#/Mosaic_rule_objects/02r3000000s4000000/
        Also see http://desktop.arcgis.com/en/arcmap/latest/manage-data/raster-and-images/understanding-the-mosaicking-rules-for-a-mosaic-dataset.htm#ESRI_SECTION1_ABDC9F3F6F724A4F8079051565DC59E
        """
        if self._datastore_raster:
            raise RuntimeError("This operation cannot be performed on a datastore raster")
        mosaic_rule = {
            "mosaicMethod": "esriMosaicNone",
            "ascending": asc,
            "mosaicOperation": 'MT_' + op.upper()
        }

        if where is not None:
            mosaic_rule['where'] = where

        if fids is not None:
            mosaic_rule['fids'] = fids

        if muldidef is not None:
            mosaic_rule['multidimensionalDefinition'] = muldidef

        if method in [ 'none', 'center', 'nadir', 'northwest', 'seamline']:
            mosaic_rule['mosaicMethod'] = 'esriMosaic' + method.title()

        if viewpt is not None:
            if not isinstance(viewpt, Geometry):
                viewpt = Geometry(viewpt)
            mosaic_rule['mosaicMethod'] = 'esriMosaicViewpoint'
            mosaic_rule['viewpoint'] = viewpt

        if sort_by is not None:
            mosaic_rule['mosaicMethod'] = 'esriMosaicAttribute'
            mosaic_rule['sortField'] = sort_by
            if sort_val is not None:
                mosaic_rule['sortValue'] = sort_val

        if lock_rasters is not None:
            mosaic_rule['mosaicMethod'] = 'esriMosaicLockRaster'
            mosaic_rule['lockRasterIds'] = lock_rasters

        if item_rendering_rule is not None:
            mosaic_rule['itemRenderingRule'] = item_rendering_rule

        if self._fnra is not None:
            self._fnra["rasterFunctionArguments"] = _find_and_replace_mosaic_rule(self._fnra["rasterFunctionArguments"], mosaic_rule, self._url)
        self._mosaic_rule = mosaic_rule


    def validate(self, rendering_rule = None, mosaic_rule = None):
        """
        validates rendering rule and/or mosaic rule of an image service.

        =================     ====================================================================
        **Argument**          **Description**
        -----------------     --------------------------------------------------------------------
        rendering_rule        optional dictionary. Specifies the rendering rule to be validated
        -----------------     --------------------------------------------------------------------
        mosaic_rule           optional dictionary. Specifies the mosaic rule to be validated
        =================     ====================================================================

        :return: dictionary showing whether the specified rendering rule and/or mosaic rule is valid
        """

        url = self._url + "/validate"

        params = {
            'f': 'json'
        }
        if mosaic_rule is not None:
            params['mosaicRule'] = mosaic_rule
        if rendering_rule is not None:
            params['renderingRule'] = rendering_rule

        if self._datastore_raster:
            params["Raster"]=self._uri
            if isinstance(self._uri, bytes):
                del params['renderingRule']

        return self._con.post(path=url, postdata=params)


    def calculate_volume(self, geometries, base_type = None, mosaic_rule = None, constant_z = None, pixel_size = None):
        """
        Performs volumetric calculation on an elevation service. Results are always in square meters (area) and cubic
        meters (volume). If a service does not have vertical spatial reference and z unit is not in meters, user
        needs to apply a conversion factor when interpreting results.

        =================     ====================================================================
        **Argument**          **Description**
        -----------------     --------------------------------------------------------------------
        geometries            required a list of Polygon geometry objects or a list of envelope geometry objects.
                              A geometry that defines the geometry
                              within which the volume is computed. The geometry can be an
                              envelope or a polygon
        -----------------     --------------------------------------------------------------------
        base_type              optional integer.
                               0 - constant z;
                               1 - best fitting plane;
                               2 - lowest elevation on the perimeter;
                               3 - highest elevation on the perimeter;
                               4 - average elevation on the perimeter
        -----------------     --------------------------------------------------------------------
        mosaic_rule           Optional dictionary. Used to select different DEMs in a mosaic dataset
        -----------------     --------------------------------------------------------------------
        constant_z            Optional integer. parameter to specify constant z value
        -----------------     --------------------------------------------------------------------
        pixel_size            Optional dictionary. Defines the spatial resolution at which volume calculation is performed
        =================     ====================================================================

        :returns: dictionary showing volume values for each geometry in the input geometries array

        """

        if self.properties.serviceDataType == "esriImageServiceDataTypeElevation":
            url = "%s/calculateVolume" % self._url
            from arcgis.geometry import Polygon
            if isinstance(geometries, list):
                geometry = geometries[0]
                if geometry:
                    if isinstance(geometry, Polygon):
                        gt = "esriGeometryPolygon"
                    else:
                        gt = "esriGeometryEnvelope"
            else:
                raise RuntimeError("Invalid geometries - required an array of Polygon geometry object or an array of envelope geometry object")
            params = {
                'f' : 'json',
                'geometries' : geometries,
                'geometryType' : gt
            }
            if base_type is not None:
                params['baseType'] = base_type

            if mosaic_rule is not None:
                params['mosaicRule'] = mosaic_rule
            elif self._mosaic_rule is not None:
                params['mosaicRule'] = self._mosaic_rule

            if constant_z is not None:
                params['constantZ'] = constant_z

            if pixel_size is not None:
                params['pixelSize'] = pixel_size

            if self._datastore_raster:
                params["Raster"]=self._uri

            return self._con.post(path=url, postdata=params)

        return None


    @property
    def mosaic_rule(self):
        """The mosaic rule used by the imagery layer to define:
        * The selection of rasters that will participate in the mosaic
        * The mosaic method, e.g. how the selected rasters are ordered.
        * The mosaic operation, e.g. how overlapping pixels at the same location are resolved.

        Set by calling the mosaic_by or filter_by methods on the layer
        """
        return self._mosaic_rule

    @mosaic_rule.setter
    def mosaic_rule(self, value):

        self._mosaic_rule = value

    def _mosaic_operation(self, op):
        """
        Sets how overlapping pixels at the same location are resolved

        :param op: string, one of first,last,min,max,mean,blend,sum

        :return: this imagery layer with mosaic operation set to op
        """

        if self._datastore_raster:
            raise RuntimeError("This operation cannot be performed on a datastore raster")
        newlyr = self._clone_layer()
        if self._mosaic_rule is not None:
            newlyr._mosaic_rule["mosaicOperation"] = 'MT_' + op.upper()
        return newlyr

    def first(self):
        """
        overlapping pixels at the same location are resolved by picking the first image
        :return: this imagery layer with mosaic operation set to 'first'
        """
        return self._mosaic_operation('first')

    def last(self):
        """
        overlapping pixels at the same location are resolved by picking the last image

        :return: this imagery layer with mosaic operation set to 'last'
        """
        return self._mosaic_operation('last')

    def min(self):
        """
        overlapping pixels at the same location are resolved by picking the min pixel value

        :return: this imagery layer with mosaic operation set to 'min'
        """
        return self._mosaic_operation('min')

    def max(self):
        """
        overlapping pixels at the same location are resolved by picking the max pixel value

        :return: this imagery layer with mosaic operation set to 'max'
        """
        return self._mosaic_operation('max')

    def mean(self):
        """
        overlapping pixels at the same location are resolved by choosing the mean of all overlapping pixels

        :return: this imagery layer with mosaic operation set to 'mean'
        """
        return self._mosaic_operation('mean')

    def blend(self):
        """
        overlapping pixels at the same location are resolved by blending all overlapping pixels

        :return: this imagery layer with mosaic operation set to 'blend'
        """
        return self._mosaic_operation('blend')

    def sum(self):
        """
        overlapping pixels at the same location are resolved by adding up all overlapping pixel values

        :return: this imagery layer with mosaic operation set to 'sum'
        """
        return self._mosaic_operation('sum')


    def save(self, output_name=None, for_viz=False,*, gis=None, **kwargs):
        """
        Persists this imagery layer to the GIS as an Imagery Layer item. If for_viz is True, a new Item is created that
        uses the applied raster functions for visualization at display resolution using on-the-fly image processing.
        If for_viz is False, distributed raster analysis is used for generating a new raster information product by
        applying raster functions at source resolution across the extent of the output imagery layer.

        =================     ====================================================================
        **Argument**          **Description**
        -----------------     --------------------------------------------------------------------
        output_name           optional string. If not provided, an Imagery Layer item is created
                              by the method and used as the output.
                              You can pass in the name of the output Imagery Layer that should be
                              created by this method to be used as the output for the tool.
                              Alternatively, if for_viz is False, you can pass in an existing
                              Image Layer Item from your GIS to use that instead.
                              A RuntimeError is raised if a layer by that name already exists
        -----------------     --------------------------------------------------------------------
        for_viz               optional boolean. If True, a new Item is created that uses the
                              applied raster functions for visualization at display resolution
                              using on-the-fly image processing.
                              If for_viz is False, distributed raster analysis is used for
                              generating a new raster information product for use in analysis and
                              visualization by applying raster functions at source resolution
                              across the extent of the output imagery layer.
        -----------------     --------------------------------------------------------------------
        gis                   optional arcgis.gis.GIS object. The GIS to be used for saving the
                              output
        =================     ====================================================================

        :return: output_raster - Image layer item
        """
        g  = _arcgis.env.active_gis if gis is None else gis
        layer_extent_set = False
        gr_output = None

        if for_viz:

            if g._con._auth.lower() != 'ANON'.lower() and g._con._auth is not None:
                text_data = {
                    "id": "resultLayer",
                    "visibility": True,
                    "bandIds": [],
                    "opacity": 1,
                    "title": output_name,
                    "timeAnimation": False,
                    "renderingRule": self._fn,
                    "mosaicRule": self._mosaic_rule
                }
                ext = self.properties.initialExtent

                item_properties = {
                    'title': output_name,
                    'type': 'Image Service',
                    'url' : self._url,
                    'description': self.properties.description,
                    'tags': 'imagery',
                    'extent': '{},{},{},{}'.format(ext['xmin'], ext['ymin'], ext['xmax'], ext['ymax']),
                    'spatialReference': self.properties.spatialReference.wkid,
                    'text': json.dumps(text_data)
                }

                return g.content.add(item_properties)
            else:
                raise RuntimeError('You need to be signed in to a GIS to create Items')
        else:
            from .analytics import is_supported, generate_raster, _save_ra
            if self._fnra is None:
                from .functions import identity
                identity_layer = identity(self)
                self._fnra = identity_layer._fnra

            if is_supported(g):
                if self._extent is not None and _arcgis.env.analysis_extent is None:
                    _arcgis.env.analysis_extent = dict(self._extent)
                    layer_extent_set = True
                try:
                    if (self._uses_gbl_function) and (("use_ra" in self._other_outputs.keys()) and self._other_outputs["use_ra"]==True):
                        gr_output = _save_ra(self._fnra,output_name=output_name, other_outputs=self._other_outputs, gis=g, **kwargs)
                    else:
                        gr_output = generate_raster(self._fnra, output_name=output_name, gis=g, **kwargs)
                except Exception:
                    if layer_extent_set:
                        _arcgis.env.analysis_extent = None
                        layer_extent_set = False
                    raise

                if layer_extent_set:
                    _arcgis.env.analysis_extent = None
                    layer_extent_set = False
                if gr_output is not None:
                    return gr_output
            else:
                raise RuntimeError('This GIS does not support raster analysis.')

    def to_features(self,
                    field="Value",
                    output_type="Polygon",
                    simplify=True,
                    output_name=None,
                    *,
                    gis=None,
                    **kwargs):
        """
        Converts this raster to a persisted feature layer of the specified type using Raster Analytics.

        Distributed raster analysis is used for generating a new feature layer by
        applying raster functions at source resolution across the extent of the raster
        and performing a raster to features conversion.

        =================     ====================================================================
        **Argument**          **Description**
        -----------------     --------------------------------------------------------------------
        field                 optional string. numerical or a string field on the input layer
                              that will be used for the conversion
        -----------------     --------------------------------------------------------------------
        output_type           string, type of output. Point, Line or Polygon
        -----------------     --------------------------------------------------------------------
        simplify              boolean, specify if features will be smoothed out
        -----------------     --------------------------------------------------------------------
        output_name           string, name of output feature layer
        -----------------     --------------------------------------------------------------------
        gis                   optional arcgis.gis.GIS object. The GIS to be used for saving the
                              output. The GIS must have Raster Analytics capability.
        =================     ====================================================================

        :return:  converted feature layer item

        """
        g = _arcgis.env.active_gis if gis is None else gis

        from arcgis.raster.analytics import convert_raster_to_feature
        input_raster_dict=None
        if "url" in self._lyr_dict:
            url = self._lyr_dict["url"]
        if "serviceToken" in self._lyr_dict:
            url = url+"?token="+ self._lyr_dict["serviceToken"]
        if self._fnra is None:
            return convert_raster_to_feature(url, field, output_type, simplify, output_name, gis=g, **kwargs)
        fnarg_ra = self._fnra['rasterFunctionArguments']
        fnarg = self._fn
        return convert_raster_to_feature({"url":url,"renderingRule":self._fn}, field, output_type, simplify, output_name, gis=g, **kwargs)


    def draw_graph(self,show_attributes=False,graph_size="14.25, 15.25"):
        """
        Displays a structural representation of the function chain and it's raster input values. If
        show_attributes is set to True, then the draw_graph function also displays the attributes
        of all the functions in the function chain, representing the rasters in a blue rectangular
        box, attributes in green rectangular box and the raster function names in yellow.

        =================     ====================================================================
        **Argument**          **Description**
        -----------------     --------------------------------------------------------------------
        show_attributes       optional boolean. If True, the graph displayed includes all the
                              attributes of the function and not only it's function name and raster
                              inputs
                              Set to False by default, to display only he raster function name and
                              the raster inputs to it.
        -----------------     --------------------------------------------------------------------
        graph_size            optional string. Maximum width and height of drawing, in inches,
                              seperated by a comma. If only a single number is given, this is used
                              for both the width and the height. If defined and the drawing is
                              larger than the given size, the drawing is uniformly scaled down so
                              that it fits within the given size.
        =================     ====================================================================

        :return: Graph
        """
        import re
        import numbers
        from operator import eq
        try:
            from graphviz import Digraph
        except:
            print("Graphviz needs to be installed. pip install graphviz")
        from .functions.utility import _find_object_ref

        global nodenumber,root
        nodenumber=root=0
        function_dictionary=self._fnra

        global dict_arg
        dict_arg={}

        if function_dictionary is None:
            return "No raster function has been applied on the Imagery Layer"
        def _raster_slicestring(slice_string,**kwargs):
            try:
                subString = re.search('/services/(.+?)/ImageServer', slice_string).group(1)
            except AttributeError:
                if slice_string.startswith("$"):
                    if "url" in kwargs.keys():
                        return _raster_slicestring(kwargs["url"])
                elif '/fileShares/' in slice_string or '/rasterStores/' in slice_string or '/cloudStores/' in slice_string or '/vsi' in url:
                    slice_string=slice_string.rsplit('/',1)[1]
                subString = slice_string
            return subString

        hidden_inputs = ["ToolName","PrimaryInputParameterName", "OutputRasterParameterName"]
        G = Digraph(comment='Raster Function Chain', format='svg') # To declare the graph
        G.clear() #clear all previous cases of the same named
        G.attr(rankdir='LR', len='1',splines='ortho',nodesep='0.5',size=graph_size)   #Display graph from Left to Right

        def _draw_graph(self, show_attributes,function_dictionary=None,G=None,dg_nodenumber=None, dg_root=None,**kwargs): #regular fnra
            global nodenumber,root

            if dg_nodenumber:
                nodenumber=dg_nodenumber

            if dg_root:
                root=dg_root

            def _toolname_slicestring(slice_string):
                try:
                    subString = re.search('(.+?)_sa', slice_string).group(1)
                except AttributeError:
                    subString = slice_string
                return subString

            def _raster_function_graph(rfa_value,rfa_key,connect,**kwargs):
                global nodenumber
                if isinstance(rfa_value,dict):
                    if "rasterFunction" in rfa_value.keys():
                        _function_graph(rfa_value,rfa_key,connect, **kwargs)

                    if "url" in rfa_value.keys():
                        nodenumber+=1
                        rastername=_raster_slicestring(str(rfa_value["url"]))
                        G.node(str(nodenumber), rastername, style=('filled'), shape='note',color='darkseagreen2',fillcolor='darkseagreen2', fontname="sans-serif")
                        G.edge(str(nodenumber),str(connect),color="silver", arrowsize="0.9", penwidth="1")

                    if "uri" in rfa_value.keys():
                        nodenumber+=1
                        rastername=_raster_slicestring(str(rfa_value["uri"]))
                        G.node(str(nodenumber), rastername, style=('filled'), shape='note',color='darkseagreen2',fillcolor='darkseagreen2', fontname="sans-serif")
                        G.edge(str(nodenumber),str(connect),color="silver", arrowsize="0.9", penwidth="1")

                    elif "function" in rfa_value.keys():
                        _rft_draw_graph(G, rfa_value,rfa_key, connect, show_attributes)

                elif isinstance(rfa_value,list):
                    for rfa_value_search_dict in rfa_value:
                        if isinstance(rfa_value_search_dict,dict):
                            for rfa_value_search_key in rfa_value_search_dict.keys():
                                if rfa_value_search_key=="rasterFunction":
                                    _function_graph(rfa_value_search_dict,rfa_key,connect, **kwargs)


                        elif isinstance(rfa_value_search_dict, numbers.Number) :
                            nodenumber+=1
                            rastername=str(rfa_value_search_dict)
                            G.node(str(nodenumber), rastername, style=('filled'),fixedsize="shape", width=".75", shape='circle',color='darkslategray2',fillcolor='darkslategray2', fontname="sans-serif")
                            G.edge(str(nodenumber),str(connect),color="silver", arrowsize="0.9", penwidth="1")
                        else:
                            nodenumber+=1
                            rastername=_raster_slicestring(str(rfa_value_search_dict))
                            G.node(str(nodenumber), rastername, style=('filled'), shape='note',color='darkseagreen2',fillcolor='darkseagreen2', fontname="sans-serif")
                            G.edge(str(nodenumber),str(connect),color="silver", arrowsize="0.9", penwidth="1")

                elif (isinstance(rfa_value,int) or isinstance(rfa_value,float)):
                    nodenumber+=1
                    rastername=str(rfa_value)
                    G.node(str(nodenumber), rastername, style=('filled'),fixedsize="shape", width=".75", shape='circle',color='darkslategray2',fillcolor='darkslategray2', fontname="sans-serif")
                    G.edge(str(nodenumber),str(connect),color="silver", arrowsize="0.9", penwidth="1")

                elif isinstance(rfa_value,str):
                    nodenumber+=1
                    if "url" in kwargs.keys():
                        rastername=_raster_slicestring(rfa_value,url=kwargs["url"])
                    else:
                        rastername=_raster_slicestring(rfa_value)
                    G.node(str(nodenumber), rastername, style=('filled'), shape='note',color='darkseagreen2',fillcolor='darkseagreen2', fontname="sans-serif")
                    G.edge(str(nodenumber),str(connect),color="silver", arrowsize="0.9", penwidth="1")


            def _attribute_function_graph(rfa_value,rfa_key,root):
                global nodenumber
                nodenumber+=1
                rastername=rfa_key+" = "+str(rfa_value)
                G.node(str(nodenumber), rastername, style=('filled'), shape='rectangle',color='antiquewhite',fillcolor='antiquewhite', fontname="sans-serif")
                G.edge(str(nodenumber),str(root),color="silver", arrowsize="0.9", penwidth="1")

            def _function_graph(dictionary,childnode,connect,**kwargs):
                global nodenumber,root
                if isinstance(dictionary, dict):
                    for dkey, dvalue in dictionary.items():
                        if dkey == "rasterFunction" and dvalue != "GPAdapter":
                            if (dvalue=="Identity" and "renderingRule" in dictionary["rasterFunctionArguments"]["Raster"]):
                                if "rasterFunction" in dictionary["rasterFunctionArguments"]["Raster"]["renderingRule"]:
                                    _function_graph(dictionary["rasterFunctionArguments"]["Raster"]["renderingRule"],"Raster",connect,url=dictionary["rasterFunctionArguments"]["Raster"]["url"])

                            else:
                                nodenumber+=1
                                G.node(str(nodenumber), dvalue, style=('rounded, filled'), shape='box', color='lightgoldenrod1', fillcolor='lightgoldenrod1', fontname="sans-serif")
                                if (connect>0):
                                    G.edge(str(nodenumber), str(connect),color="silver", arrowsize="0.9", penwidth="1")
                                connect=nodenumber
                                for dkey, dvalue in dictionary.items():  # Check dictionary again for rasterFunctionArguments
                                    if dkey == "rasterFunctionArguments":
                                        for key, value in dvalue.items():
                                            if (key == "Raster" or key=="Raster2" or key=="Rasters" or key=="PanImage" or key=="MSImage"):
                                                _raster_function_graph(value,key,connect,**kwargs)

                                            elif show_attributes==True:
                                                _attribute_function_graph(value,key,connect)

                        elif dkey == "rasterFunction" and dvalue == "GPAdapter": #To handle global function arguments
                            for rf_key, rf_value in dictionary.items():
                                if rf_key == "rasterFunctionArguments":
                                    for gbl_key, gbl_value in rf_value.items():
                                        if gbl_key=="toolName":
                                            toolname=_toolname_slicestring(gbl_value)
                                            nodenumber+=1
                                            G.node(str(nodenumber), toolname, style=('rounded, filled'), shape='box', color='lightgoldenrod1', fillcolor='lightgoldenrod1', fontname="sans-serif")
                                            G.edge(str(nodenumber), str(connect),color="silver", arrowsize="0.9", penwidth="1")
                                            connect=nodenumber
                                        elif gbl_key.endswith("_raster") or gbl_key.endswith("_data") or gbl_key.endswith("_features") : #To check if rasterFunctionArguments has rasters in it
                                            _raster_function_graph(gbl_value,gbl_key,connect,**kwargs)

                                        elif show_attributes==True and gbl_key != "PrimaryInputParameterName" and gbl_key != "OutputRasterParameterName":
                                            _attribute_function_graph(gbl_value,gbl_key,connect)
                        elif dkey == "function":
                            _rft_draw_graph(G, dictionary,nodenumber, connect, show_attributes)

                #To find first rasterFunction
            for dkey, dvalue in function_dictionary.items():
                if dkey == "rasterFunction" and dvalue != "GPAdapter": #To find first rasterFunction
                    if (dvalue=="Identity" and "renderingRule" in function_dictionary["rasterFunctionArguments"]["Raster"]):
                        if "rasterFunction" in function_dictionary["rasterFunctionArguments"]["Raster"]["renderingRule"]: #if the first raster function is a rendering rule applied on an image service
                            _function_graph(function_dictionary["rasterFunctionArguments"]["Raster"]["renderingRule"],None,root,url=function_dictionary["rasterFunctionArguments"]["Raster"]["url"])
                        else:
                            return "No raster function applied"
                    else:
                        #print("here")
                        root+=1
                        #print("1",root)
                        G.node(str(root), dvalue, style=('rounded, filled'), shape='box', color='lightgoldenrod1', fillcolor='lightgoldenrod1', fontname="sans-serif")  #create first rasterFunction graph node
                        nodenumber = root
                        if ((root-1)>0):
                            G.edge(str(root), str(dg_root),color="silver", arrowsize="0.9", penwidth="1")
                            temproot=root
                        for rf_key, rf_value in function_dictionary.items():
                            if rf_key == "rasterFunctionArguments":         #To check dictionary again for rasterFunctionArguments
                                for rfa_key, rfa_value in rf_value.items():
                                    if rfa_key=="rasterFunction":           #To check if rasterFunctionArguments has another rasterFunction chain in it
                                        _function_graph(rfa_value,rfa_key,nodenumber)
                                    elif rfa_key == "Raster" or rfa_key=="Raster2" or rfa_key=="Rasters" or rfa_key=="PanImage" or rfa_key=="MSImage": #To check if rasterFunctionArguments includes raster inputs in it
                                        #print("Raster",root)
                                        temproot=root
                                        _raster_function_graph(rfa_value,rfa_key,root)
                                        #print("Raster2",root)
                                    elif show_attributes==True:
                                        #print(root)
                                        _attribute_function_graph(rfa_value,rfa_key,temproot)

                elif dkey == "rasterFunction" and dvalue == "GPAdapter": #To handle global function arguments
                    for rf_key, rf_value in function_dictionary.items():
                        if rf_key == "rasterFunctionArguments":
                            for gbl_key, gbl_value in rf_value.items():
                                if gbl_key=="toolName":
                                    toolname=_toolname_slicestring(gbl_value)
                                    #To check if rasterFunctionArguments has another rasterFunction chain in it
                                    root+=1
                                    G.node(str(root), toolname, style=('rounded, filled'), shape='box', color='lightgoldenrod1', fillcolor='lightgoldenrod1', fontname="sans-serif")
                                    nodenumber = root
                                    if ((root-1)>0):
                                        G.edge(str(root), str(dg_root),color="silver", arrowsize="0.9", penwidth="1")
                                    nodenumber=root
                                elif gbl_key.endswith("_raster") or gbl_key.endswith("_data") or gbl_key.endswith("_features")  : #To check if rasterFunctionArguments includes raster inputs in it
                                    _raster_function_graph(gbl_value,gbl_key,root)
                                elif show_attributes==True and gbl_key != "PrimaryInputParameterName" and gbl_key != "OutputRasterParameterName":
                                    _attribute_function_graph(gbl_value,gbl_key,root)
                elif dkey == "function":
                    _rft_draw_graph(G, function_dictionary,nodenumber, root, show_attributes, **kwargs)

            return G

        def _rft_draw_graph(G,gdict,gnodenumber,groot,show_attributes, **kwargs): #rft fnra

            global nodenumber,connect,root
            global dict_arg
            def _rft_function_create(value,childnode, **kwargs):
                global nodenumber
                dict_temp_arg={}
                check_empty_graph=Digraph()
                list_arg=[]
                flag=0
                #save function chain in order to avoid function chain duplicating
                for k_func, v_func in value["function"].items():
                    if k_func=="name":
                        list_arg.append(k_func+str(v_func))
                for k_arg, v_arg in value["arguments"].items():
                    list_arg.append(k_arg+str(v_arg))

                list_arg.sort()
                list_arg_str=str(list_arg)
                if dict_arg is not None:  #if function chain is repeating connect to respective node
                    for k_check in dict_arg.keys():
                        if k_check == list_arg_str:
                            G.edge(str(dict_arg.get(k_check)),str(childnode),color="silver", arrowsize="0.9", penwidth="1")
                            flag=1

                if flag == 0: #New function chain
                    nodenumber+=1
                    G.node(str(nodenumber),value["function"]["name"], style=('rounded, filled'), shape='box', color='lightgoldenrod1', fillcolor='lightgoldenrod1', fontname="sans-serif")

                    if(nodenumber>0):
                        G.edge(str(nodenumber),str(childnode),color="silver", arrowsize="0.9", penwidth="1")

                    connect = nodenumber
                    dict_temp_arg={list_arg_str:connect}
                    dict_arg.update(dict_temp_arg)
                    if "isDataset" in value["arguments"].keys():
                        if(value["arguments"]["isDataset"] == False):
                            for arg_element in value["arguments"]["value"]["elements"]:
                                _rft_raster_function_graph(arg_element,connect, **kwargs)
                        elif (value["arguments"]["isDataset"] == True):
                            _rft_raster_function_graph(value["arguments"],connect, **kwargs) # Rf which only have 1 parameter

                    _rft_function_graph(value["arguments"],connect,**kwargs)

            def _rft_raster_function_graph(raster_dict, childnode, **kwargs): #If isDataset=True
                global nodenumber,connect
                if "rasterFunction" in raster_dict.keys():
                    _draw_graph(self,show_attributes,raster_dict,G,nodenumber,childnode)
                elif "value" in raster_dict.keys():
                    if raster_dict["value"] is not None:
                        if isinstance(raster_dict["value"], numbers.Number) or "value" in raster_dict["value"]: #***Handling Scalar rasters***
                            if isinstance(raster_dict["value"], numbers.Number):
                                nodenumber+=1
                                G.node(str(nodenumber), str(raster_dict["value"]) , style=('filled'),fontsize="12", shape='circle',fixedsize="shape",color='darkslategray2',fillcolor='darkslategray2', fontname="sans-serif")
                                G.edge(str(nodenumber),str(childnode),color="silver", arrowsize="0.9", penwidth="1")
                            elif isinstance(raster_dict["value"]["value"], numbers.Number):
                                nodenumber+=1
                                G.node(str(nodenumber), str(raster_dict["value"]["value"]) , style=('filled'),fontsize="12", shape='circle',fixedsize="shape",color='darkslategray2',fillcolor='darkslategray2', fontname="sans-serif")
                                G.edge(str(nodenumber),str(childnode),color="silver", arrowsize="0.9", penwidth="1")

                        elif "elements" in raster_dict["value"]:
                            ev_list='n'
                            if "elements" in raster_dict["value"]:
                                ev_list = raster_dict["value"]["elements"]
                            else:
                                ev_list = raster_dict["value"]
                            for e in ev_list:
                                if isinstance(e,dict):
                                    if "function" in e.keys(): # if function template inside
                                        _rft_function_graph(e,childnode)
                                    elif "url" in e.keys() or "uri" in e.keys() or ("type" in e and e["type"]=="Scalar"):
                                        _rft_raster_function_graph(e, childnode)
                                    else:  #if raster dataset inside raster array
                                        _rft_raster_function_graph(e, childnode)
                                else:
                                    nodenumber+=1
                                    G.node(str(nodenumber), str(e) , style=('filled'),fontsize="12", shape='circle',fixedsize="shape",color='darkslategray2',fillcolor='darkslategray2', fontname="sans-serif")
                                    G.edge(str(nodenumber),str(childnode),color="silver", arrowsize="0.9", penwidth="1")

                            if ev_list=='n': #if no value in rasters when the rft was made
                                nodenumber+=1
                                G.node(str(nodenumber),str(raster_dict["name"]), style=('filled'), shape='note',color='darkseagreen2',fillcolor='darkseagreen2', fontname="sans-serif")
                                G.edge(str(nodenumber),str(childnode),color="silver", arrowsize="0.9", penwidth="1")
                                # If elements is empty i.e Rasters has no value when rft was created

                        elif "function" in raster_dict["value"]:
                            _rft_function_graph(raster_dict,childnode)
                        elif "name" in raster_dict["value"]: #if raster properties are preserved
                            nodenumber+=1
                            G.node(str(nodenumber),str(raster_dict["value"]["name"]), style=('filled'), shape='note',color='darkseagreen2',fillcolor='darkseagreen2', fontname="sans-serif")
                            G.edge(str(nodenumber),str(childnode),color="silver", arrowsize="0.9", penwidth="1")
                        elif "url" in raster_dict["value"]: #if raster properties are preserved
                            nodenumber+=1
                            rastername=_raster_slicestring(str(raster_dict["value"]["url"]))
                            G.node(str(nodenumber),rastername, style=('filled'), shape='note',color='darkseagreen2',fillcolor='darkseagreen2', fontname="sans-serif")
                            G.edge(str(nodenumber),str(childnode),color="silver", arrowsize="0.9", penwidth="1")
                        elif "uri" in raster_dict["value"]: #if raster properties are preserved
                            nodenumber+=1
                            rastername=_raster_slicestring(str(raster_dict["value"]["uri"]))
                            G.node(str(nodenumber),rastername, style=('filled'), shape='note',color='darkseagreen2',fillcolor='darkseagreen2', fontname="sans-serif")
                            G.edge(str(nodenumber),str(childnode),color="silver", arrowsize="0.9", penwidth="1")
                        elif "datasetName" in raster_dict["value"]: #local image location
                            if "name" in raster_dict["value"]["datasetName"]:
                                nodenumber+=1
                                G.node(str(nodenumber),str(raster_dict["value"]["datasetName"]["name"]), style=('filled'), shape='note',color='darkseagreen2',fillcolor='darkseagreen2', fontname="sans-serif")
                                G.edge(str(nodenumber),str(childnode),color="silver", arrowsize="0.9", penwidth="1")

                        elif isinstance (raster_dict["value"], list): #raster_dict"value" does not have "value" or "elements" in it (ArcMap scalar rft case)
                            for x in raster_dict["value"]:
                                if isinstance(x, numbers.Number):  #Check if scalar float value
                                    nodenumber+=1
                                    G.node(str(nodenumber), str(x), style=('filled'), fontsize="12", shape='circle',fixedsize="shape", color='darkslategray2',fillcolor='darkslategray2', fontname="sans-serif")
                                    G.edge(str(nodenumber),str(childnode),color="silver", arrowsize="0.9", penwidth="1")

                                elif isinstance (x,dict):
                                    if ("url" in x or "uri" in x or ("type" in x and x["type"]=="Scalar") or ("isDataset" in x and x["isDataset"]==True) or("value" in x and  isinstance(x["value"],dict))):
                                        _rft_raster_function_graph(x, childnode,**kwargs)
                                    else:
                                        _rft_function_graph(x,childnode,**kwargs)


                elif "url" in raster_dict.keys(): #Handling Raster
                    nodenumber+=1
                    rastername=_raster_slicestring(str(raster_dict["url"]))
                    G.node(str(nodenumber), rastername, style=('filled'), shape='note',color='darkseagreen2',fillcolor='darkseagreen2', fontname="sans-serif")
                    G.edge(str(nodenumber),str(childnode),color="silver", arrowsize="0.9", penwidth="1")
                elif "uri" in raster_dict.keys():
                    nodenumber+=1
                    rastername=_raster_slicestring(str(raster_dict["uri"]))
                    G.node(str(nodenumber),rastername, style=('filled'), shape='note',color='darkseagreen2',fillcolor='darkseagreen2', fontname="sans-serif")
                    G.edge(str(nodenumber),str(childnode),color="silver", arrowsize="0.9", penwidth="1")
                elif "datasetName" in raster_dict.keys() and "name"  in raster_dict["datasetName"]: #if RasterInfo rf has data in it
                    rastername = str(raster_dict["datasetName"]["name"])
                    nodenumber+=1
                    G.node(str(nodenumber), rastername, style=('filled'), shape='note',color='darkseagreen2',fillcolor='darkseagreen2', fontname="sans-serif")
                    G.edge(str(nodenumber),str(childnode),color="silver", arrowsize="0.9", penwidth="1")
                elif "name" in raster_dict:
                    rastername = str(raster_dict["name"]) #Handling Raster
                    nodenumber+=1
                    G.node(str(nodenumber), rastername, style=('filled'), shape='note',color='darkseagreen2',fillcolor='darkseagreen2', fontname="sans-serif")
                    G.edge(str(nodenumber),str(childnode),color="silver", arrowsize="0.9", penwidth="1")

            def _rft_function_graph(dictionary, childnode, **kwargs):
                global nodenumber,connect
                count=0
                if "function" in dictionary:
                    _rft_function_create(dictionary,childnode)


                for key,value in dictionary.items():
                    if isinstance(value , dict):
                        if "isDataset" in value.keys():
                            if (value["isDataset"] == True)  or key == "Raster" or key == "Raster2" or key == "Rasters":
                                _rft_raster_function_graph(value, childnode)
                            elif (value["isDataset"] == False) and show_attributes == True:  #Show Parameters
                                if "value" in value.keys():
                                    if isinstance( value["value"],dict):
                                        if "elements" not in value["value"]:
                                            nodenumber+=1
                                            if "value" in value:
                                                if value["value"] is not None or isinstance(value["value"],bool):
                                                    atrr_name=str(value["name"])+" = "+str(value["value"])
                                            else:
                                                atrr_name=str(value["name"])
                                                G.node(str(nodenumber), atrr_name, style=('filled'), shape='rectangle',color='antiquewhite',fillcolor='antiquewhite', fontname="sans-serif")
                                                G.edge(str(nodenumber),str(childnode),color="silver", arrowsize="0.9", penwidth="1")
                                    else:
                                        if "name" in value and value["name"] not in hidden_inputs:
                                            nodenumber+=1
                                            if value["value"] is not None or isinstance(value["value"],bool):
                                                atrr_name=str(value["name"])+" = "+str(value["value"])
                                            else:
                                                atrr_name=str(value["name"])

                                            G.node(str(nodenumber), atrr_name, style=('filled'), shape='rectangle',color='antiquewhite',fillcolor='antiquewhite', fontname="sans-serif")
                                            G.edge(str(nodenumber),str(childnode),color="silver", arrowsize="0.9", penwidth="1")
                                else:
                                    nodenumber+=1
                                    atrr_name=str(value["name"])
                                    G.node(str(nodenumber), atrr_name, style=('filled'), shape='rectangle',color='antiquewhite',fillcolor='antiquewhite', fontname="sans-serif")
                                    G.edge(str(nodenumber),str(childnode),color="silver", arrowsize="0.9", penwidth="1")

                        elif "datasetName" in value.keys():
                            _rft_raster_function_graph(value, childnode)
                        elif "url" in value.keys():
                            _rft_raster_function_graph(value, childnode)
                        elif "function" in value.keys():  #Function Chain inside Raster
                            _rft_function_create(value,childnode)
                        elif "rasterFunction" in value.keys():
                            _draw_graph(self,show_attributes,value,G,nodenumber,childnode) #regular fnra




            #nodenumber=gnodenumber
            if "function" in gdict.keys():
                if (groot==0): # Check if graph is empty
                    flag_graph=1
                    root=groot+1
                    #print(gdict["function"])
                    if "name" in gdict["function"]:
                        G.node(str(root),gdict["function"]["name"], style=('rounded, filled'), shape='box', color='lightgoldenrod1', fillcolor='lightgoldenrod1', fontname="sans-serif")
                        nodenumber=root+1

                else:
                    flag_graph=2
                    root=groot
                if "isDataset" in gdict["arguments"]:
                    if(gdict["arguments"]["isDataset"] == False):
                        if "value" in gdict["arguments"]:
                            if "elements" in gdict["arguments"]["value"]:
                                if gdict["arguments"]["value"]["elements"]:
                                    for arg_element in gdict["arguments"]["value"]["elements"]:
                                        _rft_function_graph(arg_element,root,**kwargs)
                            else:
                                _rft_raster_function_graph(gdict["arguments"],root)
                        else:
                            _rft_raster_function_graph(gdict["arguments"],root)
                    else:
                        _rft_function_graph(gdict["arguments"]["value"],root,**kwargs)
                elif "datasetName" in gdict.keys():
                    _rft_raster_function_graph(gdict, root)

                if flag_graph==1:
                    _rft_function_graph(gdict["arguments"],root,**kwargs) # send only arguments of the first function to be processed
                else:
                    _rft_function_graph(gdict,root,**kwargs) #Send entire dictionary back to be processed


            return G
        return _draw_graph(self, show_attributes,function_dictionary,G)


    def _repr_jpeg_(self):
        bbox_sr = None
        if 'spatialReference' in self.extent:
            bbox_sr = self.extent['spatialReference']
        if not self._uses_gbl_function:
            return self.export_image(bbox=self._extent, bbox_sr=bbox_sr, size=[1200, 450], export_format='jpeg', f='image')

    def _repr_svg_(self):
        if self._uses_gbl_function:
            graph=self.draw_graph()
            svg_graph=graph.pipe().decode('utf-8')
            return svg_graph
        else:
            return None

    def __sub__(self, other):
        from arcgis.raster.functions import minus
        return minus([self, other])

    def __rsub__(self, other):
        from arcgis.raster.functions import minus
        return minus([other, self])

    def __add__(self, other):
        from arcgis.raster.functions import plus
        return plus([self, other])

    def __radd__(self, other):
        from arcgis.raster.functions import plus
        return plus([other, self])

    def __mul__(self, other):
        from arcgis.raster.functions import times
        return times([self, other])

    def __rmul__(self, other):
        from arcgis.raster.functions import times
        return times([other, self])

    def __div__(self, other):
        from arcgis.raster.functions import divide
        return divide([self, other])

    def __rdiv__(self, other):
        from arcgis.raster.functions import divide
        return divide([other, self])

    def __pow__(self, other):
        from arcgis.raster.functions import power
        return power([self, other])

    def __rpow__(self, other):
        from arcgis.raster.functions import power
        return power([other, self])

    def __abs__(self):
        from arcgis.raster.functions import abs
        return abs([self])

    def __lshift__(self, other):
        from arcgis.raster.functions import bitwise_left_shift
        return bitwise_left_shift([self, other])

    def __rlshift__(self, other):
        from arcgis.raster.functions import bitwise_left_shift
        return bitwise_left_shift([other, self])

    def __rshift__(self, other):
        from arcgis.raster.functions import bitwise_right_shift
        return bitwise_right_shift([self, other])

    def __rrshift__(self, other):
        from arcgis.raster.functions import bitwise_right_shift
        return bitwise_right_shift([other, self])

    def __floordiv__(self, other):
        from arcgis.raster.functions import floor_divide
        return floor_divide([self, other])

    def __rfloordiv__(self, other):
        from arcgis.raster.functions import floor_divide
        return floor_divide([other, self])

    def __truediv__(self, other):
        from arcgis.raster.functions import float_divide
        return float_divide([self, other])

    def __rtruediv__(self, other):
        from arcgis.raster.functions import float_divide
        return float_divide([other, self])

    def __mod__(self, other):
        from arcgis.raster.functions import mod
        return mod([self, other])

    def __rmod__(self, other):
        from arcgis.raster.functions import mod
        return mod([other, self])

    def __neg__(self):
        from arcgis.raster.functions import negate
        return negate([self])

    def __invert__(self):
        from arcgis.raster.functions import boolean_not
        return boolean_not(self)

    def __and__(self, other):
        from arcgis.raster.functions import boolean_and
        return boolean_and([self, other])

    def __rand__(self, other):
        from arcgis.raster.functions import boolean_and
        return boolean_and([other, self])

    def __xor__(self, other):
        from arcgis.raster.functions import boolean_xor
        return boolean_xor([self, other])

    def __rxor__(self, other):
        from arcgis.raster.functions import boolean_xor
        return boolean_xor([other, self])

    def __or__(self, other):
        from arcgis.raster.functions import boolean_or
        return boolean_or([self, other])

    def __ror__(self, other):
        from arcgis.raster.functions import boolean_or
        return boolean_or([other, self])

        # Raster.Raster.__pos__ = unaryPos         # +v
# Raster.Raster.__abs__ = Functions.Abs    # abs(v)
#
# Raster.Raster.__add__  = Functions.Plus  # +
# Raster.Raster.__radd__ = lambda self, lhs: Functions.Plus(lhs, self)
# Raster.Raster.__sub__  = Functions.Minus # -
# # TODO Huh?
# Raster.Raster.__rsub__ = Functions.Minus
# # Raster.Raster.__rsub__ = lambda self, lhs: Functions.Minus(lhs, self)
# Raster.Raster.__mul__  = Functions.Times # *
# Raster.Raster.__rmul__ = lambda self, lhs: Functions.Times(lhs, self)
# Raster.Raster.__pow__  = Functions.Power # **
# Raster.Raster.__rpow__ = lambda self, lhs: Functions.Power(lhs, self)
#
# Raster.Raster.__lshift__  = Functions.BitwiseLeftShift  # <<
# Raster.Raster.__rlshift__ = lambda self, lhs: Functions.BitwiseLeftShift(lhs, self)
# Raster.Raster.__rshift__  = Functions.BitwiseRightShift # >>
# Raster.Raster.__rrshift__ = lambda self, lhs: Functions.BitwiseRightShift(lhs, self)
#
# Raster.Raster.__div__       = Functions.Divide     # /
# Raster.Raster.__rdiv__      = lambda self, lhs: Functions.Divide(lhs, self)

# Raster.Raster.__floordiv__  = Functions.FloorDivide # //
# Raster.Raster.__rfloordiv__ = lambda self, lhs: Functions.FloorDivide(lhs, self)

# Raster.Raster.__truediv__   = Functions.FloatDivide # /
# Raster.Raster.__rtruediv__  = lambda self, lhs: Functions.FloatDivide(lhs, self)



# Raster.Raster.__mod__       = Functions.Mod        # %
# Raster.Raster.__rmod__      = lambda self, lhs: Functions.Mod(lhs, self)
# Raster.Raster.__divmod__    = returnNotImplemented # divmod()
# Raster.Raster.__rdivmod__   = returnNotImplemented
#
# # The Python bitwise operators are used for Raster boolean operators.
# Raster.Raster.__invert__ = Functions.BooleanNot # ~
# Raster.Raster.__and__    = Functions.BooleanAnd # &
# Raster.Raster.__rand__   = lambda self, lhs: Functions.BooleanAnd(lhs, self)
# Raster.Raster.__xor__    = Functions.BooleanXOr # ^
# Raster.Raster.__rxor__   = lambda self, lhs: Functions.BooleanXOr(lhs, self)
# Raster.Raster.__or__     = Functions.BooleanOr  # |
# Raster.Raster.__ror__    = lambda self, lhs: Functions.BooleanOr(lhs, self)
#
# # Python will use the non-augmented versions of these.
# Raster.Raster.__iadd__      = returnNotImplemented # +=
# Raster.Raster.__isub__      = returnNotImplemented # -=
# Raster.Raster.__imul__      = returnNotImplemented # *=
# Raster.Raster.__idiv__      = returnNotImplemented # /=
# Raster.Raster.__itruediv__  = returnNotImplemented # /=
# Raster.Raster.__ifloordiv__ = returnNotImplemented # //=
# Raster.Raster.__imod__      = returnNotImplemented # %=
# Raster.Raster.__ipow__      = returnNotImplemented # **=
# Raster.Raster.__ilshift__   = returnNotImplemented # <<=
# Raster.Raster.__irshift__   = returnNotImplemented # >>=
# Raster.Raster.__iand__      = returnNotImplemented # &=
# Raster.Raster.__ixor__      = returnNotImplemented # ^=
# Raster.Raster.__ior__       = returnNotImplemented # |=

########################################################################
class ImageryTileManager(object):
    """
    Manages the tiles for Cached Imagery Layers.

    .. note :: This class is not created by users directly. An instance of this class, called
      tiles , is available as a property of an ImageryLayer object. Users call methods on this
      tiles  object to create and access tiles from an ImageryLayer.


    =================     ====================================================================
    **Argument**          **Description**
    -----------------     --------------------------------------------------------------------
    imglyr                required ImageLayer. The imagery layer object that is cached.
    =================     ====================================================================



    """
    _service = None
    _url = None
    _con = None
    #----------------------------------------------------------------------
    def __init__(self, imglyr):
        """Constructor"""
        if isinstance(imglyr, ImageryLayer):
            self._service = imglyr
            self._url = imglyr._url
            self._con = imglyr._con
        else:
            raise ValueError("service must be of type ImageLayer")
    def _status(self, url, res):
        """
        checks the status of the service for async operations
        """
        import time
        if 'jobId' in res:
            url = url + "/jobs/%s" % res['jobId']
            while res["jobStatus"] not in ("esriJobSucceeded", "esriJobFailed"):
                res = self._con.get(path=url, params={'f' : 'json'})
                if res["jobStatus"] == "esriJobFailed":
                    return False, res
                if res['jobStatus'] == 'esriJobSucceeded':
                    return True, res
                time.sleep(2)
        return True, res
    #----------------------------------------------------------------------
    def export(self,
               tile_package=False,
               extent=None,
               optimize_for_size=True,
               compression=75,
               export_by="LevelID",
               levels=None,
               aoi=None
               ):
        """
        The export method allows client applications to download map tiles
        from server for offline use. This operation is performed on a
        Image Layer that allows clients to export cache tiles. The result
        of this operation is Image Layer Job.

        export can be enabled in a layer by using ArcGIS Desktop or the
        ArcGIS Server Administrative Site Directory. In ArcGIS Desktop,
        make an admin or publisher connection to the server, go to layer
        properties and enable "Allow Clients to Export Cache Tiles" in
        advanced caching page of the layer Editor. You can also specify
        the maximum tiles clients will be allowed to download. The default
        maximum allowed tile count is 100,000. To enable this capability
        using the ArcGIS Servers Administrative Site Directory, edit the
        layer and set the properties exportTilesAllowed=true and
        maxExportTilesCount=100000.

        =================     ====================================================================
        **Argument**          **Description**
        -----------------     --------------------------------------------------------------------
        tile_package          optional boolean.   Allows exporting either a tile package or a
                              cache raster data set. If the value is true output will be in tile
                              package format and if the value is false Cache Raster data set is
                              returned. The default value is false
        -----------------     --------------------------------------------------------------------
        extent                optional string. The extent (bounding box) of the tile package or
                              the cache dataset to be exported. If extent does not include a
                              spatial reference, the extent values are assumed to be in the
                              spatial reference of the map. The default value is full extent of
                              the tiled map service.

                              Syntax: <xmin>, <ymin>, <xmax>, <ymax>
                              Example: -104,35.6,-94.32,41
        -----------------     --------------------------------------------------------------------
        optimize_for_size     optional boolean. Use this parameter to enable compression of JPEG
                              tiles and reduce the size of the downloaded tile package or the
                              cache raster data set. Compressing tiles slightly compromises on the
                              quality of tiles but helps reduce the size of the download. Try out
                              sample compressions to determine the optimal compression before
                              using this feature.
        -----------------     --------------------------------------------------------------------
        compression           optional integer. When optimizeTilesForSize=true you can specify a
                              compression factor. The value must be between 0 and 100. Default is
                              75.
        -----------------     --------------------------------------------------------------------
        export_by             optional string. The criteria that will be used to select the tile
                              service levels to export. The values can be Level IDs, cache scales
                              or the Resolution (in the case of image services).
                              Values: LevelID,Resolution,Scale
                              Default: LevelID
        -----------------     --------------------------------------------------------------------
        levels                optional string. Specify the tiled service levels to export. The
                              values should correspond to Level IDs, cache scales or the
                              Resolution as specified in exportBy parameter. The values can be
                              comma separated values or a range.

                              Example 1: 1,2,3,4,5,6,7,8,9
                              Example 2: 1-4,7-9
        -----------------     --------------------------------------------------------------------
        aoi                   optional polygon. The areaOfInterest polygon allows exporting tiles
                              within the specified polygon areas. This parameter supersedes
                              extent parameter.
        =================     ====================================================================
        """
        if self._service.properties['exportTilesAllowed'] == False:
            return None

        url = "%s/%s" % (self._url, "exportTiles")
        if export_by is None:
            export_by = "LevelID"
        params = {
            "f" : "json",
            "tilePackage" : tile_package,
            "exportExtent" : extent,
            "optimizeTilesForSize" : optimize_for_size,
            "compressionQuality" : compression,
            "exportBy" : export_by,
            "levels" : levels
        }

        if aoi:
            params['areaOfInterest'] = aoi

        res = self._con.post(path=url, postdata=params)
        sid = res['jobId']
        success, res = self._status(url, res)
        if success == False:
            return res
        else:
            if "results" in res and \
               "out_service_url" in res['results']:
                rurl = url + "/jobs/%s/%s" % (sid, res['results']['out_service_url']['paramUrl'])
                result_url = self._con.get(path=rurl, params={'f': 'json'})['value']
                dl_res = self._con.get(path=result_url, params={'f' : 'json'})
                if 'files' in dl_res:
                    import tempfile
                    files = []
                    for f in dl_res['files']:
                        files.append(self._con.get(path=f['url'],
                                                   try_json=False,
                                                   out_folder=tempfile.gettempdir(),
                                                   file_name=f['name']))
                        del f
                    return files
                return []
            return res
    #----------------------------------------------------------------------
    def estimate_size(self,
                      tile_package=False,
                      extent=None,
                      optimize_for_size=True,
                      compression=75,
                      export_by="LevelID",
                      levels=None,
                      aoi=None
                      ):
        """
        The estimate_size operation is an asynchronous task that
        allows estimation of the size of the tile package or the cache data
        set that you download using the Export Tiles operation. This
        operation can also be used to estimate the tile count in a tile
        package and determine if it will exceced the maxExportTileCount
        limit set by the administrator of the layer. The result of this
        operation is the response size. This job response contains
        reference to Image Layer Result method that returns the total
        size of the cache to be exported (in bytes) and the number of tiles
        that will be exported.

        =================     ====================================================================
        **Argument**          **Description**
        -----------------     --------------------------------------------------------------------
        tile_package          optional boolean.  If the value is true output will be in tile
                              package format and if the value is false Cache Raster data set is
                              returned. The default value is false
        -----------------     --------------------------------------------------------------------
        extent                optional string. The extent (bounding box) of the tile package or
                              the cache dataset to be exported. If extent does not include a
                              spatial reference, the extent values are assumed to be in the
                              spatial reference of the map. The default value is full extent of
                              the tiled map service.

                              Syntax: <xmin>, <ymin>, <xmax>, <ymax>
                              Example: -104,35.6,-94.32,41
        -----------------     --------------------------------------------------------------------
        optimize_for_size     optional boolean. Use this parameter to enable compression of JPEG
                              tiles and reduce the size of the downloaded tile package or the
                              cache raster data set. Compressing tiles slightly compromises on the
                              quality of tiles but helps reduce the size of the download. Try out
                              sample compressions to determine the optimal compression before
                              using this feature.
        -----------------     --------------------------------------------------------------------
        compression           optional integer. When optimizeTilesForSize=true you can specify a
                              compression factor. The value must be between 0 and 100. Default is
                              75.
        -----------------     --------------------------------------------------------------------
        export_by             optional string. The criteria that will be used to select the tile
                              service levels to export. The values can be Level IDs, cache scales
                              or the Resolution (in the case of image services).
                              Values: LevelID,Resolution,Scale
                              Default: LevelID
        -----------------     --------------------------------------------------------------------
        levels                optional string. Specify the tiled service levels to export. The
                              values should correspond to Level IDs, cache scales or the
                              Resolution as specified in exportBy parameter. The values can be
                              comma separated values or a range.

                              Example 1: 1,2,3,4,5,6,7,8,9
                              Example 2: 1-4,7-9
        -----------------     --------------------------------------------------------------------
        aoi                   optional polygon. The areaOfInterest polygon allows exporting tiles
                              within the specified polygon areas. This parameter supersedes
                              extent parameter.
        =================     ====================================================================

        :returns: dictionary
        """
        if self._service.properties['exportTilesAllowed'] == False:
            return None
        url = "%s/%s" % (self._url, "estimateExportTilesSize")
        if export_by is None:
            export_by = "LevelID"
        params = {
            "f" : "json",
            "tilePackage" : tile_package,
            "exportExtent" : extent,
            "optimizeTilesForSize" : optimize_for_size,
            "compressionQuality" : compression,
            "exportBy" : export_by,
            "levels" : levels
        }

        if aoi:
            params['areaOfInterest'] = aoi
        res = self._con.post(path=url, postdata=params)
        sid = res['jobId']
        success, res = self._status(url, res)
        if success == False:
            return res
        else:
            if "results" in res and \
               "out_service_url" in res['results']:
                rurl = url + "/jobs/%s/%s" % (sid, res['results']['out_service_url']['paramUrl'])
                result_url = self._con.get(path=rurl, params={'f': 'json'})['value']
                return result_url
            else:
                return res
        return res
    #----------------------------------------------------------------------
    def _get_job(self, job_id):
        """
        Retrieves status and message information about a specific job.

        This is useful for checking jobs that have been launched manually.

        =================     ====================================================================
        **Argument**          **Description**
        -----------------     --------------------------------------------------------------------
        job_id                required string.  Unique ID of a job.
        =================     ====================================================================

        :returns: dictionary
        """
        url = "%s/jobs/%s" % (self._url, job_id)
        params = {'f' : 'json'}
        return self._con.get(url, params)
    #----------------------------------------------------------------------
    def _get_job_inputs(self, job_id, parameter):
        """
        The Image Layer input method represents an input parameter for
        a Image Layer Job. It provides information about the input
        parameter such as its name, data type, and value. The value is the
        most important piece of information provided by this method.

        =================     ====================================================================
        **Arguments**         **Description**
        -----------------     --------------------------------------------------------------------
        job_id                required string.  Unique ID of a job.
        -----------------     --------------------------------------------------------------------
        parameter             required string.  Name of the job parameter to retrieve.
        =================     ====================================================================

        :returns: dictionary

        :Example Output Format:

        {"paramName" : "<paramName>","dataType" : "<dataType>","value" : <valueLiteralOrObject>}

        """
        url = "%s/jobs/%s/inputs/%s" % (self._url, job_id, parameter)
        params = {'f' : 'json'}
        return self._con.get(url, params)
    #----------------------------------------------------------------------
    def _get_job_result(self, job_id, parameter):
        """
        The Image Layer input method represents an input parameter for
        a Image Layer Job. It provides information about the input
        parameter such as its name, data type, and value. The value is the
        most important piece of information provided by this method.

        =================     ====================================================================
        **Arguments**         **Description**
        -----------------     --------------------------------------------------------------------
        job_id                required string.  Unique ID of a job.
        -----------------     --------------------------------------------------------------------
        parameter             required string.  Name of the job parameter to retrieve.
        =================     ====================================================================

        :returns: dictionary

        :Example Output Format:

        {"paramName" : "<paramName>","dataType" : "<dataType>","value" : <valueLiteralOrObject>}

        """
        url = "%s/jobs/%s/results/%s" % (self._url, job_id, parameter)
        params = {'f' : 'json'}
        return self._con.get(url, params)
    #----------------------------------------------------------------------
    def image_tile(self, level, row, column, blank_tile=False):
        """
        For cached image services, this method represents a single cached
        tile for the image. The image bytes for the tile at the specified
        level, row, and column are directly streamed to the client. If the
        tile is not found, an HTTP status code of 404 .

        =================     ====================================================================
        **Arguments**         **Description**
        -----------------     --------------------------------------------------------------------
        level                 required integer. The level of detail ID.
        -----------------     --------------------------------------------------------------------
        row                   required integer. The row of the cache to pull from.
        -----------------     --------------------------------------------------------------------
        column                required integer. The column of the cache to pull from.
        -----------------     --------------------------------------------------------------------
        blank_tile            optional boolean.  Default is False. This parameter applies only to
                              cached image services that are configured with the ability to return
                              blank or missing tiles for areas where cache is not available. When
                              False, the server will return a resource not found (HTTP 404)
                              response instead of a blank or missing tile. When this parameter is
                              not set, the response will contain the header blank-tile : true
                              for a blank/missing tile.
        =================     ====================================================================

        :returns: None or file path (string)
        """
        import tempfile, uuid
        fname = "%s.jpg" % uuid.uuid4().hex
        params = {'blankTile' : blank_tile}
        url = "%s/tile/%s/%s/%s" % (self._url, level, row, column)
        out_folder = tempfile.gettempdir()
        return self._con.get(path=url,
                             out_folder=out_folder,
                             file_name=fname,
                             params=params,
                             try_json=False)

########################################################################
class RasterCatalogItem(object):
    """
    Represents a single catalog item on an Image Layer.  This class is only
    to be used with Imagery Layer objects that have 'Catalog' in the layer's
    capabilities property.


    =================     ====================================================================
    **Argument**          **Description**
    -----------------     --------------------------------------------------------------------
    url                   required string. Web address to the catalog item.
    -----------------     --------------------------------------------------------------------
    imglyr                required ImageryLayer. The imagery layer object.
    -----------------     --------------------------------------------------------------------
    initialize            optional boolean. Default is true. If false, the properties of the
                          item will not be loaded until requested.
    =================     ====================================================================

    """
    _properties = None
    _con = None
    _url = None
    _service = None
    _json_dict = None
    def __init__(self, url, imglyr, initialize=True):
        """class initializer"""
        self._url = url
        self._con = imglyr._con
        self._service = imglyr
        if initialize:
            self._init(self._con)
    #----------------------------------------------------------------------
    def _init(self, connection=None):
        """loads the properties into the class"""
        from arcgis._impl.common._mixins import PropertyMap
        if connection is None:
            connection = self._con
        params = {"f":"json"}
        try:
            result = connection.get(path=self._url,
                                    params=params)
            if isinstance(result, dict):
                self._json_dict = result
                self._properties = PropertyMap(result)
            else:
                self._json_dict = {}
                self._properties = PropertyMap({})
        except HTTPError as err:
            raise RuntimeError(err)
        except:
            self._json_dict = {}
            self._properties = PropertyMap({})
    #----------------------------------------------------------------------
    def __str__(self):
        return '<%s at %s>' % (type(self).__name__, self._url)
    #----------------------------------------------------------------------
    def __repr__(self):
        return '<%s at %s>' % (type(self).__name__, self._url)
    #----------------------------------------------------------------------
    @property
    def properties(self):
        """
        returns the object properties
        """
        if self._properties is None:
            self._init()
        return self._properties
    #----------------------------------------------------------------------
    def __getattr__(self, name):
        """adds dot notation to any class"""
        if self._properties is None:
            self._init()
        try:
            return self._properties.__getitem__(name)
        except:
            for k,v in self._json_dict.items():
                if k.lower() == name.lower():
                    return v
            raise AttributeError("'%s' object has no attribute '%s'" % (type(self).__name__, name))
    #----------------------------------------------------------------------
    def __getitem__(self, key):
        """helps make object function like a dictionary object"""
        try:
            return self._properties.__getitem__(key)
        except KeyError:
            for k,v in self._json_dict.items():
                if k.lower() == key.lower():
                    return v
            raise AttributeError("'%s' object has no attribute '%s'" % (type(self).__name__,
                                                                        key))
        except:
            raise AttributeError("'%s' object has no attribute '%s'" % (type(self).__name__,
                                                                        key))
    #----------------------------------------------------------------------
    @property
    def info(self):
        """
        The info property returns information about the associated raster
        such as its width, height, number of bands, and pixel type.
        """
        url = "%s/info" % self._url
        params = {'f' : 'json'}
        return self._con.get(url, params)
    #----------------------------------------------------------------------
    @property
    def key_properties(self):
        """
        The raster key_properties property returns key properties of the
        associated raster in an image layer.
        """
        url = "%s/info/keyProperties" % self._url
        params = {'f' : 'json'}
        return self._con.get(url, params)
    #----------------------------------------------------------------------
    @property
    def thumbnail(self):
        """returns a thumbnail of the current item"""
        import tempfile
        folder = tempfile.gettempdir()
        url = "%s/thumbnail" % self._url
        params = {}
        return self._con.get(path=url,
                             params={},
                             try_json=False,
                             out_folder=folder,
                             file_name="thumbnail.png"
                             )
    #----------------------------------------------------------------------
    def image(self,
              bbox,
              return_format="JSON",
              bbox_sr=None,
              size=None,
              image_sr=None,
              image_format="png",
              pixel_type=None,
              no_data=None,
              interpolation=None,
              compression=75
              ):
        """
        The Raster Image method returns a composite image for a single
        raster catalog item. You can use this method for generating
        dynamic images based on a single catalog item.
        This method provides information about the exported image, such
        as its URL, width and height, and extent.
        Apart from the usual response formats of html and json, you can
        also request a format called image for the image. When you specify
        image as the format, the server responds by directly streaming the
        image bytes to the client. With this approach, you don't get any
        information associated with the image other than the actual image.

        =================     ====================================================================
        **Arguments**         **Description**
        -----------------     --------------------------------------------------------------------
        return_format         optional string.  The response can either be IMAGER or JSON. Image
                              will return the image file to disk where as the JSON value will
                              The default value is JSON.
        -----------------     --------------------------------------------------------------------
        bbox                  required string. The extent (bounding box) of the exported image.
                              Unless the bbox_sr parameter has been specified, the bbox is assumed
                              to be in the spatial reference of the image layer.
                              Syntax: <xmin>, <ymin>, <xmax>, <ymax>
                              Example: bbox=-104,35.6,-94.32,41
        -----------------     --------------------------------------------------------------------
        bbox_sr               optional string.  The spatial reference of the bbox.
        -----------------     --------------------------------------------------------------------
        size                  optional string.The size (width * height) of the exported image in
                              pixels. If the size is not specified, an image with a default size
                              of 400 * 400 will be exported.
                              Syntax: <width>, <height>
                              Example: size=600,550
        -----------------     --------------------------------------------------------------------
        image_sr              optional string/integer.  The spatial reference of the image.
        -----------------     --------------------------------------------------------------------
        format                optional string. The format of the exported image. The default
                              format is png.
                              Values: png, png8, png24, jpg, bmp, gif
        -----------------     --------------------------------------------------------------------
        pixel_type            optional string. The pixel type, also known as data type, that
                              pertains to the type of values stored in the raster, such as signed
                              integer, unsigned integer, or floating point. Integers are whole
                              numbers; floating points have decimals.
                              Values: C128, C64, F32, F64, S16, S32, S8, U1, U16, U2, U32, U4,
                              U8, UNKNOWN
        -----------------     --------------------------------------------------------------------
        no_data               optional float. The pixel value representing no information.
        -----------------     --------------------------------------------------------------------
        interpolation         optional string. The resampling process of extrapolating the pixel
                              values while transforming the raster dataset when it undergoes
                              warping or when it changes coordinate space.
                              Values: RSP_BilinearInterpolation,
                              RSP_CubicConvolution, RSP_Majority, RSP_NearestNeighbor
        -----------------     --------------------------------------------------------------------
        compression           optional integer. Controls how much loss the image will be subjected
                              to by the compression algorithm. Valid value ranges of compression
                              quality are from 0 to 100.
        =================     ====================================================================

        """
        import json
        try_json = True
        out_folder = None
        out_file = None
        url = "%s/image" % self._url
        if return_format is None:
            return_format = 'json'
        elif return_format.lower() == 'image':
            return_format = 'image'
            out_folder = tempfile.gettempdir()
            if image_format is None:
                ext = "png"
            elif image_format.lower() in ('png', 'png8', 'png24'):
                ext = 'png'
            else:
                ext = image_format
            try_json = False
            out_file = "%s.%s" % (uuid.uuid4().hex, ext)
        else:
            return_format = 'json'
        params = {
            'f' : return_format
        }
        if bbox is not None:
            params['bbox'] = bbox
        if bbox_sr is not None:
            params['bboxSR'] = bbox_sr
        if size is not None:
            params['size'] = size
        if image_sr is not None:
            params['imageSR'] = image_sr
        if image_format is not None:
            params['format'] = image_format
        if pixel_type is not None:
            params['pixelType'] = pixel_type
        if no_data is not None:
            params['noData'] = no_data

        return self._con.get(path=url,
                             params=params,
                             try_json=try_json,
                             file_name=out_file,
                             out_folder=out_folder)
    #----------------------------------------------------------------------
    @property
    def ics(self):
        """
        The raster ics property returns the image coordinate system of the
        associated raster in an image layer. The returned ics can be used
        as the SR parameter.


        """
        url = "%s/info/ics" % self._url
        return self._con.get(path=url, params={'f': 'json'})
    #----------------------------------------------------------------------
    @property
    def metadata(self):
        """
        The metadata property returns metadata of the image layer or a
        raster catalog item. The output format is always XML.
        """
        url = "%s/info/metadata" % self._url
        out_folder = tempfile.gettempdir()
        out_file = "metadata.xml"
        return self._con.get(path=url, params={}, try_json=False,
                             file_name=out_file, out_folder=out_folder)

    #----------------------------------------------------------------------
    @property
    def ics_to_pixel(self):
        """
        returns coefficients to build up mathematic model for geometric
        transformation. With this transformation, ICS coordinates based
        from the catalog item raster can be used to calculate the original
        column and row numbers on the corresponding image.

        """
        url = "%s/info/icsToPixel" % self._url
        return self._con.get(path=url, params={'f': 'json'})
########################################################################
class RasterManager(object):
    """
    This class allows users to update, add, and delete rasters to an
    ImageryLayer object.  The functions are only available if the
    layer has 'Edit' on it's capabilities property.

    .. note :: This class is not created by users directly. An instance of this class, called  rasters ,
     is available as a property of an ImageryLayer object. Users call methods on this  rasters  object
     to  update, add and delete rasters from an ImageryLayer

    =================     ====================================================================
    **Argument**          **Description**
    -----------------     --------------------------------------------------------------------
    imglyr                required ImageryLayer. The imagery layer object where 'Edit' is in
                          the capabilities.
    =================     ====================================================================
    """
    _service = None
    #----------------------------------------------------------------------
    def __init__(self, imglyr):
        """Constructor"""
        self._service = imglyr
    #----------------------------------------------------------------------
    def add(self,
            raster_type,
            item_ids=None,
            service_url=None,
            compute_statistics=False,
            build_pyramids=False,
            build_thumbnail=False,
            minimum_cell_size_factor=None,
            maximum_cell_size_factor=None,
            attributes=None,
            geodata_transforms=None,
            geodata_transform_apply_method="esriGeodataTransformApplyAppend"
            ):
        """
        This operation is supported at 10.1 and later.
        The Add Rasters operation is performed on an image layer method.
        The Add Rasters operation adds new rasters to an image layer
        (POST only).
        The added rasters can either be uploaded items, using the item_ids
        parameter, or published services, using the service_url parameter.
        If item_ids is specified, uploaded rasters are copied to the image
        Layer's dynamic image workspace location; if the service_url is
        specified, the image layer adds the URL to the mosaic dataset no
        raster files are copied. The service_url is required input for the
        following raster types: Image Layer, Map Service, WCS, and WMS.

        Inputs:

        item_ids - The upload items (raster files) to be added. Either
         item_ids or service_url is needed to perform this operation.
            Syntax: item_ids=<itemId1>,<itemId2>
            Example: item_ids=ib740c7bb-e5d0-4156-9cea-12fa7d3a472c,
                             ib740c7bb-e2d0-4106-9fea-12fa7d3a482c
        service_url - The URL of the service to be added. The image layer
         will add this URL to the mosaic dataset. Either item_ids or
         service_url is needed to perform this operation. The service URL is
         required for the following raster types: Image Layer, Map
         Service, WCS, and WMS.
            Example: service_url=http://myserver/arcgis/services/Portland/ImageServer
        raster_type - The type of raster files being added. Raster types
         define the metadata and processing template for raster files to be
         added. Allowed values are listed in image layer resource.
            Example: Raster Dataset,CADRG/ECRG,CIB,DTED,Image Layer,Map Service,NITF,WCS,WMS
        compute_statistics - If true, statistics for the rasters will be
         computed. The default is false.
            Values: false,true
        build_pyramids - If true, builds pyramids for the rasters. The
         default is false.
                Values: false,true
        build_thumbnail	 - If true, generates a thumbnail for the rasters.
         The default is false.
                Values: false,true
        minimum_cell_size_factor - The factor (times raster resolution) used
         to populate the MinPS field (maximum cell size above which the
         raster is visible).
                Syntax: minimum_cell_size_factor=<minimum_cell_size_factor>
                Example: minimum_cell_size_factor=0.1
        maximum_cell_size_factor - The factor (times raster resolution) used
         to populate MaxPS field (maximum cell size below which raster is
         visible).
                Syntax: maximum_cell_size_factor=<maximum_cell_size_factor>
                Example: maximum_cell_size_factor=10
        attributes - Any attribute for the added rasters.
                Syntax:
                {
                  "<name1>" : <value1>,
                  "<name2>" : <value2>
                }
                Example:
                {
                  "MinPS": 0,
                  "MaxPS": 20;
                  "Year" : 2002,
                  "State" : "Florida"
                }
        geodata_transforms - The geodata transformations applied on the
         added rasters. A geodata transformation is a mathematical model
         that performs a geometric transformation on a raster; it defines
         how the pixels will be transformed when displayed or accessed.
         Polynomial, projective, identity, and other transformations are
         available. The geodata transformations are applied to the dataset
         that is added.
                Syntax:
                [
                {
                  "geodataTransform" : "<geodataTransformName1>",
                  "geodataTransformArguments" : {<geodataTransformArguments1>}
                  },
                  {
                  "geodataTransform" : "<geodataTransformName2>",
                  "geodataTransformArguments" : {<geodataTransformArguments2>}
                  }
                ]
         The syntax of the geodataTransformArguments property varies based
         on the specified geodataTransform name. See Geodata Transformations
         documentation for more details.
        geodata_transform_apply_method - This parameter defines how to apply
         the provided geodataTransform. The default is
         esriGeodataTransformApplyAppend.
                Values: esriGeodataTransformApplyAppend |
                esriGeodataTransformApplyReplace |
                esriGeodataTransformApplyOverwrite

        """
        return self._service._add_rasters(raster_type,
                                          item_ids,
                                          service_url,
                                          compute_statistics,
                                          build_pyramids,
                                          build_thumbnail,
                                          minimum_cell_size_factor,
                                          maximum_cell_size_factor,
                                          attributes,
                                          geodata_transforms,
                                          geodata_transform_apply_method)
    #----------------------------------------------------------------------
    def delete(self, raster_ids):
        """
        The Delete Rasters operation deletes one or more rasters in an image layer.

        =================     ====================================================================
        **Argument**          **Description**
        -----------------     --------------------------------------------------------------------
        raster_ids            required string. The object IDs of a raster catalog items to be
                              removed. This is a comma seperated string.
                              example 1: raster_ids='1,2,3,4' # Multiple IDs
                              example 2: raster_ids='10' # single ID
        =================     ====================================================================

        :returns: dictionary
        """
        return self._service._delete_rasters(raster_ids)
    #----------------------------------------------------------------------
    def update(self,
               raster_id,
               files=None,
               item_ids=None,
               service_url=None,
               compute_statistics=False,
               build_pyramids=False,
               build_thumbnail=False,
               minimum_cell_size_factor=None,
               maximum_cell_size_factor=None,
               attributes=None,
               footprint=None,
               geodata_transforms=None,
               apply_method="esriGeodataTransformApplyAppend"):
        """
        The Update Raster operation updates rasters (attributes and
        footprints, or replaces existing raster files) in an image layer.
        In most cases, this operation is used to update attributes or
        footprints of existing rasters in an image layer. In cases where
        the original raster needs to be replaced, the new raster can either
        be items uploaded using the items parameter or URLs of published
        services using the serviceUrl parameter.

        ========================  ====================================================================
        **Argument**              **Description**
        ------------------------  --------------------------------------------------------------------
        raster_ids                required integer. The object IDs of a raster catalog items to be
                                  updated.
        ------------------------  --------------------------------------------------------------------
        files                     optional list. Local source location to the raster to replace the
                                  dataset with.
                                  Example: [r"<path>\data.tiff"]
        ------------------------  --------------------------------------------------------------------
        item_ids                  optional string.  The uploaded items (raster files) being used to
                                  replace existing raster.
        ------------------------  --------------------------------------------------------------------
        service_url               optional string. The URL of the layer to be uploaded to replace
                                  existing raster data. The image layer will add this URL to the
                                  mosaic dataset. The serviceUrl is required for the following raster
                                  types: Image Layer, Map Service, WCS, and WMS.
        ------------------------  --------------------------------------------------------------------
        compute_statistics        If true, statistics for the uploaded raster will be computed. The
                                  default is false.
        ------------------------  --------------------------------------------------------------------
        build_pyramids            optional boolean. If true, builds pyramids for the uploaded raster.
                                  The default is false.
        ------------------------  --------------------------------------------------------------------
        build_thumbnail           optional boolean. If true, generates a thumbnail for the uploaded
                                  raster. The default is false.
        ------------------------  --------------------------------------------------------------------
        minimum_cell_size_factor  optional float. The factor (times raster resolution) used to
                                  populate MinPS field (minimum cell size above which raster is
                                  visible).
        ------------------------  --------------------------------------------------------------------
        maximum_cell_size_factor  optional float. The factor (times raster resolution) used to
                                  populate MaxPS field (maximum cell size below which raster is
                                  visible).
        ------------------------  --------------------------------------------------------------------
        footprint                 optional Polygon.  A JSON 2D polygon object that defines the
                                  footprint of the raster. If the spatial reference is not defined, it
                                  will default to the image layer's spatial reference.
        ------------------------  --------------------------------------------------------------------
        attributes                optional dictionary.  Any attribute for the uploaded raster.
        ------------------------  --------------------------------------------------------------------
        geodata_transforms        optional string. The geodata transformations applied on the updated
                                  rasters. A geodata transformation is a mathematical model that
                                  performs geometric transformation on a raster. It defines how the
                                  pixels will be transformed when displayed or accessed, such as
                                  polynomial, projective, or identity transformations. The geodata
                                  transformations will be applied to the updated dataset.
        ------------------------  --------------------------------------------------------------------
        apply_method              optional string. Defines how to apply the provided geodataTransform.
                                  The default is esriGeodataTransformApplyAppend.
                                  Values: esriGeodataTransformApplyAppend,
                                      esriGeodataTransformApplyReplace,
                                      esriGeodataTransformApplyOverwrite
        ========================  ====================================================================

        :returns: dictionary
        """
        return self._service._update_raster(raster_id=raster_id,
                                            files=files,
                                            item_ids=item_ids,
                                            service_url=service_url,
                                            compute_statistics=compute_statistics,
                                            build_pyramids=build_pyramids,
                                            build_thumbnail=build_thumbnail,
                                            minimum_cell_size_factor=minimum_cell_size_factor,
                                            maximum_cell_size_factor=maximum_cell_size_factor,
                                            attributes=attributes,
                                            footprint=footprint,
                                            geodata_transforms=geodata_transforms,
                                            apply_method=apply_method)
