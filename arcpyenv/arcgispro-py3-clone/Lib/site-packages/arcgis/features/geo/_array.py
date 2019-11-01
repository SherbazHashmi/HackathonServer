import operator
import json
import numpy as np

from pandas.core.arrays import ExtensionArray
from pandas.core.dtypes.dtypes import ExtensionDtype
from arcgis.geometry import Geometry
import pandas as pd
from .parser import _to_geo_array



class NumPyBackedExtensionArrayMixin(ExtensionArray):
    """
    Geo-Specific Extension Array Mixin
    """
    @property
    def dtype(self):
        """The dtype for this extension array, GeoType"""
        return self._dtype

    @classmethod
    def _from_sequence(cls, scalars):
        return cls(scalars)

    @classmethod
    def _constructor_from_sequence(cls, scalars):
        return cls(scalars)

    @classmethod
    def _from_factorized(cls, values, original):
        return cls(values)

    @property
    def shape(self):
        return (len(self.data),)

    def __len__(self):
        return len(self.data)

    def __getitem__(self, *args):
        result = operator.getitem(self.data, *args)
        if isinstance(result, (dict, Geometry)):
            return result
        elif isinstance(result, type(None)) or \
             isinstance(result, type(np.nan)):
            return None
        elif not isinstance(result, GeoArray):
            return GeoArray(result)
        return result


    def setitem(self, indexer, value):
        """Set the 'value' inplace.
        """

        self[indexer] = value
        return self

    @property
    def nbytes(self):
        return self._itemsize * len(self)

    def _formatting_values(self):
        return np.array(self._format_values(), dtype='object')

    def copy(self, deep=False):
        return type(self)(self.data.copy())

    @classmethod
    def _concat_same_type(cls, to_concat):
        return cls(np.concatenate([array.data for array in to_concat]))

    def tolist(self):
        return self.data.tolist()

    def argsort(self, axis=-1, kind='quicksort', order=None):
        return self.data.argsort()

    def unique(self):
        _, indices = np.unique(self.data, return_index=True)
        data = self.data.take(np.sort(indices))
        return self._from_ndarray(data)

class GeoType(ExtensionDtype):
    name = 'geometry'
    type = Geometry
    kind = 'O'
    _record_type = np.dtype('O')
    na_value = None

    @classmethod
    def construct_from_string(cls, string):
        if string == cls.name:
            return cls()
        else:
            raise TypeError("Cannot construct a '{}' from "
                            "'{}'".format(cls, string))

class GeoArray(NumPyBackedExtensionArrayMixin):
    """Array for Geometry data.
    """
    _dtype = GeoType()
    _itemsize = 8
    ndim = 1
    can_hold_na = True

    def __init__(self, values, copy=True):
        self.data = np.array(values, dtype='O', copy=copy)

    @classmethod
    def _from_ndarray(cls, data, copy=False):
        return cls(data, copy=copy)

    @property
    def na_value(self):
        return self.dtype.na_value

    def __repr__(self):
        formatted = self._format_values()
        return "GeoArray({!r})".format(formatted)

    def __str__(self):
        return self.__repr__()

    def _format_values(self):
        if self.data.ndim == 0:
            return ""
        return [_format(x) if x else None for x in self.data]

    @classmethod
    def from_geometry(cls, data, copy=False):
        """"""
        if copy:
            data = data.copy()
        new = GeoArray([])
        new.data = np.array(data)
        return new

    def __setitem__(self, key, value):
        if value is None or  \
           (isinstance(value, str) and value == ""):
            self.data[key] = value
        else:
            value = Geometry(value)
            self.data[key] = value

    def __iter__(self):
        return iter(self.data.tolist())

    def __eq__(self, other):
        return self.data == other

    def equals(self, other):
        if not isinstance(other, type(self)):
            raise TypeError
        return (self.data == other.data).all()

    def _values_for_factorize(self):
        # Should hit pandas' UInt64Hashtable
        return self, 0

    def isna(self):
        return (self.data == self._dtype.na_value)

    @property
    def _parser(self):
        return lambda x: x

    def take(self, indexer, allow_fill=True, fill_value=None):
        mask = indexer == -1
        result = self.data.take(indexer)
        result[mask] = self.dtype.na_value
        return type(self)(result, copy=False)

    def _formatting_values(self):
        return np.array(self._format_values(), dtype='object')

    @classmethod
    def _concat_same_type(cls, to_concat):
        return cls(np.concatenate([array.data for array in to_concat]))

    def take_nd(self, indexer, allow_fill=True, fill_value=None):
        return self.take(indexer, allow_fill=allow_fill, fill_value=fill_value)

    def copy(self, deep=False):
        return type(self)(self.data.copy())

    from arcgis.geometry import BaseGeometry
    #----------------------------------------------------------------------
    @property
    def size(self):
        """returns the length of the data"""
        return len(self.data)

    @property
    def is_valid(self):
        """Checks if the Geometry is Valid"""
        return pd.Series([g.is_valid() for g in self])

    #----------------------------------------------------------------------
    def _call_property(self, prop, as_ga=False):
        """accesses a property on a dataframe"""
        fn = lambda g: getattr(g, prop, None)
        vals = np.vectorize(fn,otypes='O')(self.data)
        if as_ga:
            s = pd.Series(GeoArray(values=vals))
        else:
            s = pd.Series(vals)
        s.name = prop
        return s
    #----------------------------------------------------------------------
    def _call_method(self, name, is_ga=False, **kwargs):
        """accesses a method on a dataframe"""
        import warnings
        warnings.simplefilter("ignore")
        fn = lambda g, n: getattr(g, n, None)(**kwargs) \
            if g is not None else None
        vals = np.vectorize(fn, otypes='O')(self.data, name)
        if is_ga:
            s = pd.Series(GeoArray(values=vals, copy=False))
        else:
            s = pd.Series(vals)
        s.name = name
        return s
    #----------------------------------------------------------------------
    @property
    def area(self):
        """returns the geometry area"""
        return self._call_property('area')
    #----------------------------------------------------------------------
    @property
    def as_arcpy(self):
        """returns the geometry area"""
        return self._call_property('as_arcpy')
    #----------------------------------------------------------------------
    @property
    def as_shapely(self):
        """returns the geometry area"""
        return self._call_property('as_shapely')
    #----------------------------------------------------------------------
    @property
    def centroid(self):
        """returns Geometry centroid"""
        return self._call_property('centroid')
    #----------------------------------------------------------------------
    @property
    def extent(self):
        """returns the extent of the geometry"""
        return self._call_property("extent")
    #----------------------------------------------------------------------
    @property
    def first_point(self):
        """
        The first coordinate point of the geometry for each entry.
        """
        return self._call_property("first_point", as_ga=True)
    #----------------------------------------------------------------------
    @property
    def geoextent(self):
        return self._call_property("geoextent")
    #----------------------------------------------------------------------
    @property
    def geometry_type(self):
        return self._call_property("geometry_type")
    #----------------------------------------------------------------------
    @property
    def hull_rectangle(self):
        return self._call_property("hull_rectangle")
    #----------------------------------------------------------------------
    @property
    def is_empty(self):
        return self._call_property("is_empty")
    #----------------------------------------------------------------------
    @property
    def is_multipart(self):
        return self._call_property("is_multipart")
    ##----------------------------------------------------------------------
    #@property
    #def is_valid(self):
    #    return self._call_property("is_valid")
    #----------------------------------------------------------------------
    @property
    def JSON(self):
        return self._call_property("JSON")
    #----------------------------------------------------------------------
    @property
    def label_point(self):
        return self._call_property("label_point", as_ga=True)
    #----------------------------------------------------------------------
    @property
    def last_point(self):
        return self._call_property("last_point", as_ga=True)
    #----------------------------------------------------------------------
    @property
    def length(self):
        return self._call_property("length", as_ga=False)
    #----------------------------------------------------------------------
    @property
    def length3D(self):
        return self._call_property("length3D", as_ga=False)
    #----------------------------------------------------------------------
    @property
    def part_count(self):
        return self._call_property("part_count")
    #----------------------------------------------------------------------
    @property
    def point_count(self):
        return self._call_property("point_count")
    #----------------------------------------------------------------------
    @property
    def spatial_reference(self):
        return self._call_property("spatial_reference")
    #----------------------------------------------------------------------
    @property
    def true_centroid(self):
        return self._call_property("true_centroid", as_ga=True)
    #----------------------------------------------------------------------
    @property
    def WKB(self):
        return self._call_property("WKB")
    #----------------------------------------------------------------------
    @property
    def WKT(self):
        return self._call_property("WKT")
    #----------------------------------------------------------------------
    def angle_distance_to(self, second_geometry, method="GEODESIC"):
        """
        Returns a tuple of angle and distance to another point using a
        measurement type.

        ===============     ====================================================================
        **Argument**        **Description**
        ---------------     --------------------------------------------------------------------
        second_geometry     Required Geometry.  A arcgis.Geometry object.
        ---------------     --------------------------------------------------------------------
        method              Optional String. PLANAR measurements reflect the projection of geographic
                            data onto the 2D surface (in other words, they will not take into
                            account the curvature of the earth). GEODESIC, GREAT_ELLIPTIC,
                            LOXODROME, and PRESERVE_SHAPE measurement types may be chosen as
                            an alternative, if desired.
        ===============     ====================================================================

        :returns: a tuple of angle and distance to another point using a measurement type.
        """
        return self._call_method(name='angle_distance_to',
                                 is_ga=False,
                                 **{'second_geometry' : second_geometry,
                                    'method' : method})
    #----------------------------------------------------------------------
    def boundary(self):
        """
        Constructs the boundary of the geometry.

        :returns: arcgis.geometry.Polyline
        """

        return self._call_method(name='boundary', is_ga=True)
    #----------------------------------------------------------------------
    def buffer(self, distance):
        """
        Constructs a polygon at a specified distance from the geometry.

        ===============     ====================================================================
        **Argument**        **Description**
        ---------------     --------------------------------------------------------------------
        distance            Required float. The buffer distance. The buffer distance is in the
                            same units as the geometry that is being buffered.
                            A negative distance can only be specified against a polygon geometry.
        ===============     ====================================================================

        :returns: arcgis.geometry.Polygon
        """
        return self._call_method(name='buffer',
                                 is_ga=True,
                                 **{'distance' : distance})
    #----------------------------------------------------------------------
    def clip(self, envelope):
        """
        Constructs the intersection of the geometry and the specified extent.

        ===============     ====================================================================
        **Argument**        **Description**
        ---------------     --------------------------------------------------------------------
        envelope            required tuple. The tuple must have (XMin, YMin, XMax, YMax) each value
                            represents the lower left bound and upper right bound of the extent.
        ===============     ====================================================================

        :returns: output geometry clipped to extent

        """
        return self._call_method(name='clip',
                                 is_ga=True,
                                 **{'envelope' : envelope})
    #----------------------------------------------------------------------
    def contains(self, second_geometry, relation=None):
        """
        Indicates if the base geometry contains the comparison geometry.

        ===============     ====================================================================
        **Argument**        **Description**
        ---------------     --------------------------------------------------------------------
        second_geometry     Required arcgis.geometry.Geometry. A second geometry
        ---------------     --------------------------------------------------------------------
        relation            Optional string. The spatial relationship type.

                            + BOUNDARY - Relationship has no restrictions for interiors or boundaries.
                            + CLEMENTINI - Interiors of geometries must intersect. Specifying CLEMENTINI is equivalent to specifying None. This is the default.
                            + PROPER - Boundaries of geometries must not intersect.
        ===============     ====================================================================

        :returns: boolean
        """
        return self._call_method(name='contains',
                                 is_ga=False,
                                 **{'second_geometry' : second_geometry,
                                    'relation' : relation})
    #----------------------------------------------------------------------
    def convex_hull(self):
        """
        Constructs the geometry that is the minimal bounding polygon such
        that all outer angles are convex.
        """
        return self._call_method(name='convex_hull',
                                 is_ga=True)
    #----------------------------------------------------------------------
    def crosses(self, second_geometry):
        """
        Indicates if the two geometries intersect in a geometry of a lesser
        shape type.

        ===============     ====================================================================
        **Argument**        **Description**
        ---------------     --------------------------------------------------------------------
        second_geometry     Required arcgis.geometry.Geometry. A second geometry
        ===============     ====================================================================

        :returns: boolean

        """
        return self._call_method(name='crosses',
                                 is_ga=False,
                                 **{'second_geometry' : second_geometry})
    #----------------------------------------------------------------------
    def cut(self, cutter):
        """
        Splits this geometry into a part left of the cutting polyline, and
        a part right of it.

        ===============     ====================================================================
        **Argument**        **Description**
        ---------------     --------------------------------------------------------------------
        cutter              Required Polyline. The cuttin polyline geometry
        ===============     ====================================================================

        :returns: a list of two geometries

        """
        return self._call_method(name='cut',
                                 is_ga=True,
                                 **{'cutter' : cutter})
    #----------------------------------------------------------------------
    def densify(self, method, distance, deviation):
        """
        Creates a new geometry with added vertices

        ===============     ====================================================================
        **Argument**        **Description**
        ---------------     --------------------------------------------------------------------
        method              Required String. The type of densification, DISTANCE, ANGLE, or GEODESIC
        ---------------     --------------------------------------------------------------------
        distance            Required float. The maximum distance between vertices. The actual
                            distance between vertices will usually be less than the maximum
                            distance as new vertices will be evenly distributed along the
                            original segment. If using a type of DISTANCE or ANGLE, the
                            distance is measured in the units of the geometry's spatial
                            reference. If using a type of GEODESIC, the distance is measured
                            in meters.
        ---------------     --------------------------------------------------------------------
        deviation           Required float. Densify uses straight lines to approximate curves.
                            You use deviation to control the accuracy of this approximation.
                            The deviation is the maximum distance between the new segment and
                            the original curve. The smaller its value, the more segments will
                            be required to approximate the curve.
        ===============     ====================================================================

        :returns: arcgis.geometry.Geometry

        """
        return self._call_method(name='densify',
                                 is_ga=True,
                                 **{'method' : method,
                                    'distance' : distance,
                                    'deviation' : deviation})
    #----------------------------------------------------------------------
    def difference(self, second_geometry):
        """
        Constructs the geometry that is composed only of the region unique
        to the base geometry but not part of the other geometry. The
        following illustration shows the results when the red polygon is the
        source geometry.

        ===============     ====================================================================
        **Argument**        **Description**
        ---------------     --------------------------------------------------------------------
        second_geometry     Required arcgis.geometry.Geometry. A second geometry
        ===============     ====================================================================

        :returns: arcgis.geometry.Geometry

        """
        return self._call_method(name='difference',
                                 is_ga=True,
                                 **{'second_geometry' : second_geometry})
    #----------------------------------------------------------------------
    def disjoint(self, second_geometry):
        """
        Indicates if the base and comparison geometries share no points in
        common.

        ===============     ====================================================================
        **Argument**        **Description**
        ---------------     --------------------------------------------------------------------
        second_geometry     Required arcgis.geometry.Geometry. A second geometry
        ===============     ====================================================================

        :returns: boolean

        """
        return self._call_method(name='disjoint',
                                 is_ga=False,
                                 **{'second_geometry' : second_geometry})
    #----------------------------------------------------------------------
    def distance_to(self, second_geometry):
        """
        Returns the minimum distance between two geometries. If the
        geometries intersect, the minimum distance is 0.
        Both geometries must have the same projection.

        ===============     ====================================================================
        **Argument**        **Description**
        ---------------     --------------------------------------------------------------------
        second_geometry     Required arcgis.geometry.Geometry. A second geometry
        ===============     ====================================================================

        :returns: float

        """
        return self._call_method(name='distance_to',
                                 is_ga=False,
                                 **{'second_geometry' : second_geometry})
    #----------------------------------------------------------------------
    def equals(self, second_geometry):
        """
        Indicates if the base and comparison geometries are of the same
        shape type and define the same set of points in the plane. This is
        a 2D comparison only; M and Z values are ignored.

        ===============     ====================================================================
        **Argument**        **Description**
        ---------------     --------------------------------------------------------------------
        second_geometry     Required arcgis.geometry.Geometry. A second geometry
        ===============     ====================================================================

        :returns: boolean


        """
        return self._call_method(name='equals',
                                 is_ga=False,
                                 **{'second_geometry' : second_geometry})
    #----------------------------------------------------------------------
    def generalize(self, max_offset):
        """
        Creates a new simplified geometry using a specified maximum offset
        tolerance.

        ===============     ====================================================================
        **Argument**        **Description**
        ---------------     --------------------------------------------------------------------
        max_offset          Required float. The maximum offset tolerance.
        ===============     ====================================================================

        :returns: arcgis.geometry.Geometry

        """
        return self._call_method(name='generalize',
                                 is_ga=True,
                                 **{'max_offset' : max_offset})
    #----------------------------------------------------------------------
    def get_area(self, method, units=None):
        """
        Returns the area of the feature using a measurement type.

        ===============     ====================================================================
        **Argument**        **Description**
        ---------------     --------------------------------------------------------------------
        method              Required String. LANAR measurements reflect the projection of
                            geographic data onto the 2D surface (in other words, they will not
                            take into account the curvature of the earth). GEODESIC,
                            GREAT_ELLIPTIC, LOXODROME, and PRESERVE_SHAPE measurement types
                            may be chosen as an alternative, if desired.
        ---------------     --------------------------------------------------------------------
        units               Optional String. Areal unit of measure keywords: ACRES | ARES | HECTARES
                            | SQUARECENTIMETERS | SQUAREDECIMETERS | SQUAREINCHES | SQUAREFEET
                            | SQUAREKILOMETERS | SQUAREMETERS | SQUAREMILES |
                            SQUAREMILLIMETERS | SQUAREYARDS
        ===============     ====================================================================

        :returns: float

        """
        return self._call_method(name='get_area',
                                 is_ga=False,
                                 **{'method' : method,
                                    'units' : units})
    #----------------------------------------------------------------------
    def get_length(self, method, units):
        """
        Returns the length of the feature using a measurement type.

        ===============     ====================================================================
        **Argument**        **Description**
        ---------------     --------------------------------------------------------------------
        method              Required String. PLANAR measurements reflect the projection of
                            geographic data onto the 2D surface (in other words, they will not
                            take into account the curvature of the earth). GEODESIC,
                            GREAT_ELLIPTIC, LOXODROME, and PRESERVE_SHAPE measurement types
                            may be chosen as an alternative, if desired.
        ---------------     --------------------------------------------------------------------
        units               Required String. Linear unit of measure keywords: CENTIMETERS |
                            DECIMETERS | FEET | INCHES | KILOMETERS | METERS | MILES |
                            MILLIMETERS | NAUTICALMILES | YARDS
        ===============     ====================================================================

        :returns: float

        """
        return self._call_method(name='get_length',
                                 is_ga=False,
                                 **{'method' : method,
                                    'units' : units})
    #----------------------------------------------------------------------
    def get_part(self, index=None):
        """
        Returns an array of point objects for a particular part of geometry
        or an array containing a number of arrays, one for each part.

        **requires arcpy**

        ===============     ====================================================================
        **Argument**        **Description**
        ---------------     --------------------------------------------------------------------
        index               Required Integer. The index position of the geometry.
        ===============     ====================================================================

        :return: arcpy.Array

        """
        return self._call_method(name='get_part',
                                 is_ga=False,
                                 **{'index' : index})
    #----------------------------------------------------------------------
    def intersect(self, second_geometry, dimension=1):
        """
        Constructs a geometry that is the geometric intersection of the two
        input geometries. Different dimension values can be used to create
        different shape types. The intersection of two geometries of the
        same shape type is a geometry containing only the regions of overlap
        between the original geometries.

        ===============     ====================================================================
        **Argument**        **Description**
        ---------------     --------------------------------------------------------------------
        second_geometry     Required arcgis.geometry.Geometry. A second geometry
        ---------------     --------------------------------------------------------------------
        dimension           Required Integer. The topological dimension (shape type) of the
                            resulting geometry.

                            + 1  -A zero-dimensional geometry (point or multipoint).
                            + 2  -A one-dimensional geometry (polyline).
                            + 4  -A two-dimensional geometry (polygon).

        ===============     ====================================================================

        :returns: boolean

        """
        return self._call_method(name='intersect',
                                 is_ga=True,
                                 **{'second_geometry' : second_geometry,
                                    'dimension' : dimension})
    #----------------------------------------------------------------------
    def measure_on_line(self, second_geometry, as_percentage=False):
        """
        Returns a measure from the start point of this line to the in_point.

        ===============     ====================================================================
        **Argument**        **Description**
        ---------------     --------------------------------------------------------------------
        second_geometry     Required arcgis.geometry.Geometry. A second geometry
        ---------------     --------------------------------------------------------------------
        as_percentage       Optional Boolean. If False, the measure will be returned as a
                            distance; if True, the measure will be returned as a percentage.
        ===============     ====================================================================

        :return: float

        """
        return self._call_method(name='measure_on_line',
                                 is_ga=False,
                                 **{'second_geometry' : second_geometry,
                                    'as_percentage' : as_percentage})
    #----------------------------------------------------------------------
    def overlaps(self, second_geometry):
        """
        Indicates if the intersection of the two geometries has the same
        shape type as one of the input geometries and is not equivalent to
        either of the input geometries.

        ===============     ====================================================================
        **Argument**        **Description**
        ---------------     --------------------------------------------------------------------
        second_geometry     Required arcgis.geometry.Geometry. A second geometry
        ===============     ====================================================================

        :return: boolean

        """
        return self._call_method(name='overlaps',
                                 is_ga=False,
                                 **{'second_geometry' : second_geometry})
    #----------------------------------------------------------------------
    def point_from_angle_and_distance(self, angle, distance, method='GEODESCIC'):
        """
        Returns a point at a given angle and distance in degrees and meters
        using the specified measurement type.

        ===============     ====================================================================
        **Argument**        **Description**
        ---------------     --------------------------------------------------------------------
        angle               Required Float. The angle in degrees to the returned point.
        ---------------     --------------------------------------------------------------------
        distance            Required Float. The distance in meters to the returned point.
        ---------------     --------------------------------------------------------------------
        method              Optional String. PLANAR measurements reflect the projection of geographic
                            data onto the 2D surface (in other words, they will not take into
                            account the curvature of the earth). GEODESIC, GREAT_ELLIPTIC,
                            LOXODROME, and PRESERVE_SHAPE measurement types may be chosen as
                            an alternative, if desired.
        ===============     ====================================================================

        :return: arcgis.geometry.Geometry


        """
        return self._call_method(name='point_from_angle_and_distance',
                                 is_ga=True,
                                 **{'angle' : angle,
                                    'distance' : distance,
                                    'method' : method})
    #----------------------------------------------------------------------
    def position_along_line(self, value, use_percentage=False):
        """
        Returns a point on a line at a specified distance from the beginning
        of the line.

        ===============     ====================================================================
        **Argument**        **Description**
        ---------------     --------------------------------------------------------------------
        value               Required Float. The distance along the line.
        ---------------     --------------------------------------------------------------------
        use_percentage      Optional Boolean. The distance may be specified as a fixed unit
                            of measure or a ratio of the length of the line. If True, value
                            is used as a percentage; if False, value is used as a distance.
                            For percentages, the value should be expressed as a double from
                            0.0 (0%) to 1.0 (100%).
        ===============     ====================================================================

        :return: arcgis.gis.Geometry

        """
        return self._call_method(name='position_along_line',
                                 is_ga=True,
                                 **{'value' : value,
                                    'use_percentage' : use_percentage})
    #----------------------------------------------------------------------
    def project_as(self, spatial_reference, transformation_name=None):
        """
        Projects a geometry and optionally applies a geotransformation.

        ====================     ====================================================================
        **Argument**             **Description**
        --------------------     --------------------------------------------------------------------
        spatial_reference        Required SpatialReference. The new spatial reference. This can be a
                                 SpatialReference object or the coordinate system name.
        --------------------     --------------------------------------------------------------------
        transformation_name      Required String. The geotransformation name.
        ====================     ====================================================================

        :returns: arcgis.geometry.Geometry
        """
        return self._call_method(name='project_as',
                                 is_ga=True,
                                 **{'spatial_reference' : spatial_reference,
                                    'transformation_name' : transformation_name}
                                 )
    #----------------------------------------------------------------------
    def query_point_and_distance(self, second_geometry,
                                 use_percentage=False):
        """
        Finds the point on the polyline nearest to the in_point and the
        distance between those points. Also returns information about the
        side of the line the in_point is on as well as the distance along
        the line where the nearest point occurs.

        ===============     ====================================================================
        **Argument**        **Description**
        ---------------     --------------------------------------------------------------------
        second_geometry     Required arcgis.geometry.Geometry. A second geometry
        ---------------     --------------------------------------------------------------------
        as_percentage       Optional boolean - if False, the measure will be returned as
                            distance, True, measure will be a percentage
        ===============     ====================================================================

        :return: tuple

        """
        return self._call_method(name='query_point_and_distance',
                                 is_ga=False,
                                 **{'second_geometry' : second_geometry,
                                    'use_percentage' : use_percentage})
    #----------------------------------------------------------------------
    def segment_along_line(self, start_measure,
                           end_measure, use_percentage=False):
        """
        Returns a Polyline between start and end measures. Similar to
        Polyline.positionAlongLine but will return a polyline segment between
        two points on the polyline instead of a single point.

        ===============     ====================================================================
        **Argument**        **Description**
        ---------------     --------------------------------------------------------------------
        start_measure       Required Float. The starting distance from the beginning of the line.
        ---------------     --------------------------------------------------------------------
        end_measure         Required Float. The ending distance from the beginning of the line.
        ---------------     --------------------------------------------------------------------
        use_percentage      Optional Boolean. The start and end measures may be specified as
                            fixed units or as a ratio.
                            If True, start_measure and end_measure are used as a percentage; if
                            False, start_measure and end_measure are used as a distance. For
                            percentages, the measures should be expressed as a double from 0.0
                            (0 percent) to 1.0 (100 percent).
        ===============     ====================================================================

        :returns: Geometry

        """
        return self._call_method(name='segment_along_line',
                                 is_ga=True,
                                 **{'start_measure' : start_measure,
                                    'end_measure' : end_measure,
                                    'use_percentage' : use_percentage})
    #----------------------------------------------------------------------
    def snap_to_line(self, second_geometry):
        """
        Returns a new point based on in_point snapped to this geometry.

        ===============     ====================================================================
        **Argument**        **Description**
        ---------------     --------------------------------------------------------------------
        second_geometry     Required arcgis.geometry.Geometry. A second geometry
        ===============     ====================================================================

        :return: arcgis.gis.Geometry

        """
        return self._call_method(name='snap_to_line',
                                 is_ga=True,
                                 **{'second_geometry' : second_geometry})
    #----------------------------------------------------------------------
    def symmetric_difference (self, second_geometry):
        """
        Constructs the geometry that is the union of two geometries minus the
        instersection of those geometries.

        The two input geometries must be the same shape type.

        ===============     ====================================================================
        **Argument**        **Description**
        ---------------     --------------------------------------------------------------------
        second_geometry     Required arcgis.geometry.Geometry. A second geometry
        ===============     ====================================================================

        :return: arcgis.gis.Geometry
        """
        return self._call_method(name='symmetric_difference',
                                 is_ga=True,
                                 **{'second_geometry' : second_geometry})
    #----------------------------------------------------------------------
    def touches(self, second_geometry):
        """
        Indicates if the boundaries of the geometries intersect.


        ===============     ====================================================================
        **Argument**        **Description**
        ---------------     --------------------------------------------------------------------
        second_geometry     Required arcgis.geometry.Geometry. A second geometry
        ===============     ====================================================================

        :return: boolean
        """
        return self._call_method(name='touches',
                                 is_ga=False,
                                 **{'second_geometry' : second_geometry})
    #----------------------------------------------------------------------
    def union(self, second_geometry):
        """
        Constructs the geometry that is the set-theoretic union of the input
        geometries.


        ===============     ====================================================================
        **Argument**        **Description**
        ---------------     --------------------------------------------------------------------
        second_geometry     Required arcgis.geometry.Geometry. A second geometry
        ===============     ====================================================================

        :return: arcgis.gis.Geometry
        """
        return self._call_method(name='union',
                                 is_ga=True,
                                 **{'second_geometry' : second_geometry})
    #----------------------------------------------------------------------
    def within(self, second_geometry, relation=None):
        """
        Indicates if the base geometry is within the comparison geometry.

        ===============     ====================================================================
        **Argument**        **Description**
        ---------------     --------------------------------------------------------------------
        second_geometry     Required arcgis.geometry.Geometry. A second geometry
        ---------------     --------------------------------------------------------------------
        relation            Optional String. The spatial relationship type.

                            - BOUNDARY  - Relationship has no restrictions for interiors or boundaries.
                            - CLEMENTINI  - Interiors of geometries must intersect. Specifying CLEMENTINI is equivalent to specifying None. This is the default.
                            - PROPER  - Boundaries of geometries must not intersect.

        ===============     ====================================================================

        :return: boolean

        """
        return self._call_method(name='within',
                                 is_ga=False,
                                 **{'second_geometry' : second_geometry,
                                    'relation' : relation})

def _format(g):
    if g in {None, np.nan}:
        return ""
    return json.dumps(g)

