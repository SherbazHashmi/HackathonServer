from arcgis._impl.common._mixins import PropertyMap
from arcgis.features import FeatureLayer, FeatureLayerCollection
from arcgis.features._version import Version, VersionManager

########################################################################
class ParcelFabricManager(object):
    """
    The Parcel Fabric Server is responsible for exposing parcel management
    capabilities to support a variety of workflows from different clients
    and systems.

    ====================     ====================================================================
    **Argument**             **Description**
    --------------------     --------------------------------------------------------------------
    url                      Required String. The URI to the service endpoint.
    --------------------     --------------------------------------------------------------------
    gis                      Required GIS. The enterprise connection.
    --------------------     --------------------------------------------------------------------
    version                  Required Version. This is the version object where the modification
                             will occur.
    --------------------     --------------------------------------------------------------------
    flc                      Required FeatureLayerCollection. This is the parent container for
                             ParcelFabricManager.
    ====================     ====================================================================

    """
    _con = None
    _flc = None
    _gis = None
    _url = None
    _version = None
    _properties = None
    #----------------------------------------------------------------------
    def __init__(self,
                 url,
                 gis,
                 version,
                 flc):
        """Constructor"""
        self._url = url
        self._gis = gis
        self._con = gis._portal.con
        self._version = version
        self._flc = flc
    #----------------------------------------------------------------------
    def __str__(self):
        return "<ParcelFabricManager @ %s>" % self._url
    #----------------------------------------------------------------------
    def __repr__(self):
        return self.__str__()
    #----------------------------------------------------------------------
    def __enter__(self):
        return self
    #----------------------------------------------------------------------
    def __exit__(self, type, value, traceback):
        return
    #----------------------------------------------------------------------
    @property
    def layer(self):
        """returns the Parcel Layer for the service"""
        if "controllerDatasetLayers" in self._flc.properties and \
           "parcelLayerId" in self._flc.properties.controllerDatasetLayers:
            url = "%s/%s" % (self._flc.url,
                             self._flc.properties.controllerDatasetLayers.parcelLayerId)
            return FeatureLayer(url=url, gis=self._gis)
        return None
    #----------------------------------------------------------------------
    @property
    def properties(self):
        """returns the properties of the service"""
        if self._properties is None:

            res = self._con.get(self._url, {'f':'json'})
            self._properties = PropertyMap(res)
        return self._properties
    #----------------------------------------------------------------------
    def build(self,
              extent=None,
              moment=None,
              return_errors=False):
        """
        A `build` will fix known parcel fabric errors.

        For example, if a parcel polygon exists without lines, then build will
        construct the missing lines. If lines are missing, the polygon row(s)
        are created. When constructing this objects, build will attribute the
        related keys as appropriate. Build also maintains `lineage` and `record`
        features. The parcel fabric must have sufficient information for build
        to work correctly. Ie, source reference document, and connected lines.

        Build provides options to increase performance. The process can just
        work on specific parcels, geometry types or only respond to parcel point
        movement in the case of an adjustment.

        ====================     ====================================================================
        **Argument**             **Description**
        --------------------     --------------------------------------------------------------------
        extent                   Optional Envelope. The extent to build.

                                 Syntax: {"xmin":X min,"ymin": y min, "xmax": x max, "ymax": y max,
                                         "spatialReference": <wkt of spatial reference>}

        --------------------     --------------------------------------------------------------------
        moment                   Optional String. This should only be specified by the client when
                                 they do not want to use the current moment
        --------------------     --------------------------------------------------------------------
        return_errors            Optional Boolean. If True, a verbose response will be given if errors
                                 occured.  The default is False
        ====================     ====================================================================


        :return: Boolean

        """
        url = "{base}/build".format(base=self._url)
        params = {
            "gdbVersion" : self._version.properties.versionName,
            "sessionId" : self._version._guid,
            "moment" : moment,
            "buildExtent" : extent,
            "returnErrors" : return_errors,
            "f": "json"
        }
        return self._con.post(url, params)
    #----------------------------------------------------------------------
    def clip(self,
             parent_parcels,
             clip_record=None,
             clipping_parcels=None,
             geometry=None,
             moment=None,
             ):
        """

        Clip cuts a new child parcel into existing parent parcels. Commonly
        it retires the parent parcel(s) it cuts into to generate a reminder
        child parcel. This type of split is often part of a `parcel split
        metes and bounds` record driven workflow.

        =======================     ====================================================================
        **Argument**                **Description**
        -----------------------     --------------------------------------------------------------------
        parent_parcels              parent parcels that will be clipped into.
                                    Syntax:  parentParcels= <parcel (guid)+layer (name)...>
        -----------------------     --------------------------------------------------------------------
        clip_record                 Optional String. It is the GUID for the active legal record.
        -----------------------     --------------------------------------------------------------------
        clipping_parcels            Optional List. A list of child parcels that will be used to clip
                                    into the parent parcels. Parcel lineage is created if the child
                                    'clipping_parcels' and the parcels being clipped are of the same
                                    parcel type.

                                    Syntax: clippingParcels= < id : parcel guid, layered: <layer id>...>

                                    Example:

                                    [{"id":"{D01D3F47-5FE2-4E39-8C07-E356B46DBC78}","layerId":"16"}]

                                    **Either clipping_parcels or geometry is required.**
        -----------------------     --------------------------------------------------------------------
        geometry                    Optional Polygon. Allows for the clipping a parcel based on geometry instead of
                                    'clippingParcels' geometry. No parcel lineage is created.

                                    **Either clipping_parcels or geometry is required.**
        -----------------------     --------------------------------------------------------------------
        moment                      Optional String. This should only be specified by the client when
                                    they do not want to use the current moment
        =======================     ====================================================================

        :returns: Dictionary


        """
        gdb_version = self._version.properties.versionName
        session_id = self._version._guid
        url = "{base}/clip".format(base=self._url)
        params = {
            "gdbVersion": gdb_version,
            "sessionId": session_id,
            "parentParcels": parent_parcels,
            "moment" : moment,
            "clipRecord" : clip_record,
            "clippingParcels" : clipping_parcels,
            "clippingGeometry" : geometry,
            "f": "json"
        }
        return self._con.post(url, params)
    #----------------------------------------------------------------------
    def merge(self,
              parent_parcels,
              target_parcel_type,
              attribute_overrides=None,
              child_name=None,
              default_area_unit=None,
              merge_record=None,
              merge_into=None,
              moment=None):
        """
        Merge combines 2 or more parent parcels into onenew child parcel. Merge
        sums up legal areas of parent parcels to the new child parcel legal
        area (using default area units as dictated by client). The child parcel
        lines arecomposed from the outer boundaries of the parent parcels.
        Merge can create multipart parcels as well as proportion lines (partial
        overlap of parent parcels). Record footprint is updated to match the
        child parcel.

        ====================     ====================================================================
        **Argument**             **Description**
        --------------------     --------------------------------------------------------------------
        parent_parcels           Required String. It is the parcel(guid)+layer(name) identifiers to
                                 merge.
        --------------------     --------------------------------------------------------------------
        target_parcel_type       Required String. Layer where parcel is merged to.  History is
                                 created when parents and child are of the same parcel type
        --------------------     --------------------------------------------------------------------
        attribute_overrides      Optional List. A list of attributes to set on the child parcel, if
                                 they exist. Pairs of field name and value.

                                 Syntax: attributeOverrides= [{ "type":"PropertySet","propertySetItems":[<field name>,<field value>]}]

                                 * to set subtype, include subtype value in this list.
        --------------------     --------------------------------------------------------------------
        child_name               Optional String. A descript of the child layer.
        --------------------     --------------------------------------------------------------------
        default_area_unit        Optional String. The area units of the child parcel.
        --------------------     --------------------------------------------------------------------
        merge_record             Optional String. Record identifier (guid).  If missing, no history
                                 is created.
        --------------------     --------------------------------------------------------------------
        merge_into               Optional String. A parcel identifier (guid). Invalid to have a
                                 record id.
        --------------------     --------------------------------------------------------------------
        moment                   Optional String. This parameter represents the session moment (the
                                 default is the version current moment). This should only be
                                 specified by the client when they do not want to use the current
                                 moment.
        ====================     ====================================================================


        :return: Dictionary

        """
        gdb_version = self._version.properties.versionName
        session_id = self._version._guid
        url = "{base}/merge".format(base=self._url)
        params = {
            "gdbVersion" : gdb_version,
            "sessionId" : session_id,
            "parentParcels" : parent_parcels,
            "mergeRecord" : merge_record,
            "moment" : moment,
            "targetParcelType" : target_parcel_type,
            "mergeInto" : merge_into,
            "childName" : child_name,
            "defaultAreaUnit" : default_area_unit,
            "attributeOverrides" : attribute_overrides,
            "f": "json"
        }
        return self._con.post(url, params)
    #----------------------------------------------------------------------
    def copy_lines_to_parcel_type(self,
                                  parent_parcels,
                                  record,
                                  target_type,
                                  moment=None,
                                  mark_historic=False,
                                  use_source_attributes=False,
                                  attribute_overrides=None):
        """

        Copy lines to parcel type is used when the construction of the
        child parcel is based on parent parcel geometry. It creates a
        copy of the parent parcels lines that the user can modify (insert,
        delete, update) before they build the child parcels. If the source
        parcel type and the target parcel type are identical (common)
        parcel lineage is created.

        =======================     ====================================================================
        **Argument**                **Description**
        -----------------------     --------------------------------------------------------------------
        parent_parcels              Required String. Parcel parcels from which lines are copied.
        -----------------------     --------------------------------------------------------------------
        record                      Required String. The unique identifier (guid) of the active legal
                                    record.
        -----------------------     --------------------------------------------------------------------
        target_type                 Required String. The target parcel layer to which the lines will be
                                    copied to.
        -----------------------     --------------------------------------------------------------------
        moment                      Optional String. This parameter represents the session moment (the
                                    default is the version current moment). This should only be
                                    specified by the client when they do not want to use the current
                                    moment.
        -----------------------     --------------------------------------------------------------------
        mark_historic               Optional Boolean. Mark the parent parcels historic. The default is
                                    False.
        -----------------------     --------------------------------------------------------------------
        use_source_attributes       Optional Boolean. If the source and the target line schema match,
                                    attributes from the parent parcel lines will be copied to the new
                                    child parcel lines when it is set to  True. The default is False.

        -----------------------     --------------------------------------------------------------------
        attribute_overrides         Optional Dictionary. To set fields on the child parcel lines with a
                                    specific value. Uses a key/value pair of FieldName/Value.

                                    Example:

                                    {'type' : "PropertySet", "propertySetItems" : []}
        =======================     ====================================================================

        :returns: boolean


        """
        gdb_version = self._version.properties.versionName
        session_id = self._version._guid
        url = "{base}/copyLinesToParcelType".format(base=self._url)
        params = {
            "gdbVersion": gdb_version,
            "sessionId": session_id,
            "parentFeatures": parent_parcels,
            "record" : record,
            "markParentAsHistoric" : mark_historic,
            "useSourceAttributes": use_source_attributes,
            "targetParcelType" : target_type,
            "attributeOverrides": attribute_overrides,
            "moment" : moment,
            "f": "json"
        }
        return self._con.post(url, params)
    #----------------------------------------------------------------------
    def change_type(self,
                    parcels,
                    target_type,
                    parcel_subtype=0,
                    moment=None):
        """

        Changes a set of parcels to a new parcel type. It creates new
        polygons and lines and deletes them from the source type. This
        is used when a parcel was associated in the wrong parcel type subtype
        and/or when creating multiple parcels as part of a build process.
        Example: when lot parcels are created as part of a subdivision, the
        road parcel is moved to the encumbrance (easement) parcel type.

        =======================     ====================================================================
        **Argument**                **Description**
        -----------------------     --------------------------------------------------------------------
        parcels                     Required List. Parcels list that will change type
        -----------------------     --------------------------------------------------------------------
        target_type                 Required String. The target parcel layer
        -----------------------     --------------------------------------------------------------------
        target_subtype              Optional Integer. Target parcel subtype. The default is 0 meaning
                                    no subtype required.
        -----------------------     --------------------------------------------------------------------
        moment                      Optional String. This parameter represents the session moment (the
                                    default is the version current moment). This should only be
                                    specified by the client when they do not want to use the current
                                    moment.
        =======================     ====================================================================

        :returns: Dictionary


        """
        gdb_version = self._version.properties.versionName
        session_id = self._version._guid
        url = "{base}/changeType".format(base=self._url)
        params = {
            "gdbVersion": gdb_version,
            "sessionId": session_id,
            "parcels" : parcels,
            "targetParcelType" : target_type,
            "targetParcelSubtype" : parcel_subtype,
            "moment" : moment,
            "f": "json"
        }
        return self._con.post(url, params)
    #----------------------------------------------------------------------
    def delete(self, parcels, moment=None):
        """

        Delete a set of parcels, removing associated or unused lines, and
        connected points.

        =======================     ====================================================================
        **Argument**                **Description**
        -----------------------     --------------------------------------------------------------------
        parcels                     Required List. The parcels to erase.
        -----------------------     --------------------------------------------------------------------
        moment                      Optional String. This parameter represents the session moment (the
                                    default is the version current moment). This should only be
                                    specified by the client when they do not want to use the current
                                    moment.
        =======================     ====================================================================

        :returns: Boolean


        """
        gdb_version = self._version.properties.versionName
        session_id = self._version._guid
        url = "{base}/deleteParcels".format(base=self._url)
        params = {
            "gdbVersion": gdb_version,
            "sessionId": session_id,
            "parcels" : parcels,
            "moment" : moment,
            "f": "json"
        }
        return self._con.post(url, params)['success']