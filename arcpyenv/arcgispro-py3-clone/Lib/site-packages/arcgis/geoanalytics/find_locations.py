"""
These tools are used to identify areas that meet a number of different criteria you specify.

find_similar_locations finds locations most similar to one or more reference locations based on criteria you specify.
"""
import json as _json

import logging as _logging
import arcgis as _arcgis
from arcgis.features import FeatureSet as _FeatureSet
from arcgis.geoprocessing._support import _execute_gp_tool
from ._util import _id_generator, _feature_input, _set_context, _create_output_service
import datetime
_log = _logging.getLogger(__name__)

# url = "https://dev003153.esri.com/gax/rest/services/System/GeoAnalyticsTools/GPServer"

_use_async = True

def geocode_locations(input_layer,
                      country=None,
                      category=None,
                      include_attributes=True,
                      locator_parameters=None,
                      output_name=None,
                      geocode_service=None,
                      geocode_parameters=None,
                      gis=None):
    """
    The Geocode Locations task geocodes a table from a big data file share. The task uses a geocode
    utility service configured with your portal.

    For more information on setting up a geocoding service see:
    http://server.arcgis.com/en/portal/latest/administer/windows/configure-portal-to-geocode-addresses.htm

    ==========================   ===============================================================
    **Argument**                 **Description**
    --------------------------   ---------------------------------------------------------------
    input_layer                  required Layer, URL, Item of address locations to geocode.
    --------------------------   ---------------------------------------------------------------
    country                      optional string.  If all your data is in one country, this helps
                                 improve performance for locators that accept that variable.
    --------------------------   ---------------------------------------------------------------
    category                     optional string. Enter a category for more precise geocoding
                                 results, if applicable. Some geocoding services do not support
                                 category, and the available options depend on your geocode service.
    --------------------------   ---------------------------------------------------------------
    include_attributes           optional boolean. A boolean value to return the output fields
                                 from the geocoding service in the results.
    --------------------------   ---------------------------------------------------------------
    locator_parameters           optional dictionary. Additional parameters specific to your
                                 locator.
    --------------------------   ---------------------------------------------------------------
    output_name                  optional string, The task will create a feature service of the
                                 results. You define the name of the service.
    --------------------------   ---------------------------------------------------------------
    geocode_service              optional string or Geocoder.  URL endpoint of the Geocoding
                                 Service of GeoCoder object. If none is provided, the service
                                 will use the first geocoder registered with portal that has
                                 batch enabled.
    --------------------------   ---------------------------------------------------------------
    geocode_parameters           optional dictionary.  This includes parameters that help parse
                                 the input data, as well the field lengths and a field mapping.
                                 This value is the output from the AnalyzeGeocodeInput tool
                                 available on your server designated to geocode. It is important
                                 to inspect the field mapping closely and adjust them accordingly
                                 before submitting your job, otherwise your geocoding results may
                                 not be accurate. It is recommended to use the output from
                                 AnalyzeGeocodeInput and modify the field mapping instead of
                                 constructing this JSON by hand.

                                 **Values**

                                 **field_info** - A list of triples with the field names of your input
                                 data, the field type (usually TEXT), and the allowed length
                                 (usually 255).
                                 Example: [['ObjectID', 'TEXT', 255], ['Address', 'TEXT', 255],
                                          ['Region', 'TEXT', 255], ['Postal', 'TEXT', 255]]

                                 **header_row_exists** - Enter true or false.

                                 **column_names** - Submit the column names of your data if your data
                                 does not have a header row.

                                 **field_mapping** - Field mapping between each input field and
                                 candidate fields on the geocoding service.
                                 Example: [['ObjectID', 'OBJECTID'], ['Address', 'Address'],
                                          ['Region', 'Region'], ['Postal', 'Postal']]
    --------------------------   ---------------------------------------------------------------
    gis                          optional GIS, the GIS on which this tool runs. If not
                                 specified, the active GIS is used.
    ==========================   ===============================================================


    :returns: Feature Layer

    """
    from arcgis.features.layer import Layer
    from arcgis.gis import Item
    from arcgis.geocoding._functions import Geocoder
    kwargs = locals()
    tool_name = "GeocodeLocations"
    gis = _arcgis.env.active_gis if gis is None else gis
    url = gis.properties.helperServices.geoanalytics.url
    params = {
        "f" : "json"
    }
    for key, value in kwargs.items():
        if value is not None:
            params[key] = value
    if output_name is None:
        output_service_name = 'Geocoding_Results_' + _id_generator()
        output_service_name = output_service_name.replace(' ', '_')
    else:
        output_service_name = output_name.replace(' ', '_')

    if isinstance(input_layer, str):
        input_layer = {'url' : input_layer}
    elif isinstance(input_layer, Item):
        input_layer = input_layer.layers[0]._lyr_dict
        if 'type' in input_layer:
            input_layer.pop('type')
    elif isinstance(input_layer, Layer):
        input_layer = input_layer._lyr_dict
        if 'type' in input_layer:
            input_layer.pop('type')
    elif isinstance(input_layer, dict) and \
         not "url" in input_layer:
        raise ValueError("Invalid Input: input_layer dictionary" + \
                         " must have format {'url' : <url>}")
    elif isinstance(input_layer, dict) and "url" in input_layer:
        pass
    else:
        raise ValueError("Invalid input_layer input. Please pass an Item, " + \
                         "Big DataStore Layer or Big DataStore URL to geocode.")

    if geocode_service is None:
        for service in gis.properties.helperServices.geocode:
            if 'batch' in service and service['batch'] == True:
                geocode_service_url = service["url"]
                break
        if geocode_service_url is None:
            raise ValueError("A geocoder with batch enabled must be configured" + \
                             " with this portal to use this service.")
        params['geocode_service_url'] = geocode_service_url
    elif isinstance(geocode_service, Geocoder):
        geocode_service = geocode_service.url
        params['geocode_service_url'] = geocode_service_url
    elif isinstance(geocode_service, str):
        params['geocode_service_url'] = geocode_service
    else:
        raise ValueError("geocode_service_url must be a string or GeoCoder")

    if geocode_parameters is None:
        from arcgis.geoprocessing._tool import Toolbox
        analyze_geocode_url = gis.properties.helperServices.asyncGeocode.url
        tbx = Toolbox(url=analyze_geocode_url, gis=gis)
        geocode_parameters = tbx.analyze_geocode_input(input_table=input_layer,
                                                       geocode_service_url=geocode_service_url)
        params['geocode_parameters'] = geocode_parameters
    output_service = _create_output_service(gis, output_name,
                                            output_service_name, 'Geocoded Locations')
    params['output_name'] = _json.dumps({
        "serviceProperties": {"name" : output_name, "serviceUrl" : output_service.url},
        "itemProperties": {"itemId" : output_service.itemid}})

    _set_context(params)

    param_db = {
        "input_layer": (_FeatureSet, "inputLayer"),
        "geocode_service_url": (str, "geocodeServiceURL"),
        "geocode_parameters": (str, "geocodeParameters"),
        "country": (str, "sourceCountry"),
        "category": (str, "category"),
        "include_attributes" : (bool, "includeAttributes"),
        "locator_parameters" : (str, "locatorParameters"),
        "output_name": (str, "outputName"),
        "output": (_FeatureSet, "output"),
        "context": (str, "context")
    }
    return_values = [
        {"name": "output", "display_name": "Output Features", "type": _FeatureSet},
    ]
    try:
        res = _execute_gp_tool(gis, tool_name, params, param_db,
                               return_values, _use_async, url, True)
        return output_service
    except:
        output_service.delete()
        raise
    return

def detect_incidents(input_layer,
                     track_fields,
                     start_condition_expression,
                     end_condition_expression=None,
                     output_mode="AllFeatures",
                     time_boundary_split=None,
                     time_split_unit=None,
                     time_reference=None,
                     output_name=None,
                     gis=None):
    """
    The Detect Incidents task works with a time-enabled layer of points,
    lines, areas, or tables that represents an instant in time. Using
    sequentially ordered features, called tracks, this tool determines
    which features are incidents of interest. Incidents are determined by
    conditions that you specify. First, the tool determines which features
    belong to a track using one or more fields. Using the time at each
    feature, the tracks are ordered sequentially and the incident condition
    is applied. Features that meet the starting incident condition are
    marked as an incident. You can optionally apply an ending incident
    condition; when the end condition is true, the feature is no longer
    an incident. The results will be returned with the original features
    with new columns representing the incident name and indicate which
    feature meets the incident condition. You can return all original
    features, only the features that are incidents, or all of the features
    within tracks where at least one incident occurred.

    For example, suppose you have GPS measurements of hurricanes every 10
    minutes. Each GPS measurement records the hurricane's name, location,
    time of recording, and wind speed. Using these fields, you could create
    an incident where any measurement with a wind speed greater than 208
    km/h is an incident titled Catastrophic. By not setting an end
    condition, the incident would end if the feature no longer meets the
    start condition (wind speed slows down to less than 208).

    Using another example, suppose you were monitoring concentrations of a
    chemical in your local water supply using a field called
    contanimateLevel. You know that the recommended levels are less than
    0.01 mg/L, and dangerous levels are above 0.03 mg/L. To detect
    incidents, where a value above 0.03mg/L is an incident, and remains an
    incident until contamination levels are back to normal, you create an
    incident using a start condition of contanimateLevel > 0.03 and an end
    condition of contanimateLevel < 0.01. This will mark any sequence where
    values exceed 0.03mg/L until they return to a value less than 0.01.

    ==========================   ===============================================================
    **Argument**                 **Description**
    --------------------------   ---------------------------------------------------------------
    input_layer                  required FeatureSet, The table, point, line or polygon features
                                 containing potential incidents.
    --------------------------   ---------------------------------------------------------------
    track_fields                 required string, The fields used to identify distinct tracks.
                                 There can be multiple track_fields.
    --------------------------   ---------------------------------------------------------------
    start_condition_expression   The condition used to identify incidents. If there
                                 is no endConditionExpression specified, any feature
                                 that meets this condition is an incident. If there
                                 is an end condition, any feature that meets the
                                 start_condition_expression and does not meet the
                                 end_condition_expression is an incident.
                                 The expressions are Arcade expressions.
    --------------------------   ---------------------------------------------------------------
    end_condition_expression     The condition used to identify incidents. If there is
                                 no endConditionExpression specified, any feature that
                                 meets this condition is an incident. If there is an
                                 end condition, any feature that meets the
                                 start_condition_expression and does not meet the
                                 end_condition_expression is an incident. This is an
                                 Arcade expression.
    --------------------------   ---------------------------------------------------------------
    output_mode                  optional string, default value is AllFeatures.  Determines
                                 which features are returned. Two modes are available:

                                 - AllFeatures - All of the input features are returned.
                                 - Incidents - Only features that were found to be incidents
                                   are returned.
    --------------------------   ---------------------------------------------------------------
    time_boundary_split          Optional Int.  A time boundary to detect and incident.
    --------------------------   ---------------------------------------------------------------
    time_split_unit              Optional String.  The unit to detect an incident is `time_boundary_split` is used.
                                 Allowed values: Years, Months, Weeks, Days, Hours, Minutes, Seconds, Milliseconds
    --------------------------   ---------------------------------------------------------------
    time_reference               Optional Datetime. The starting date/time where analysis will
                                 begin from.
    --------------------------   ---------------------------------------------------------------
    output_name                  optional string, The task will create a feature service of the
                                 results. You define the name of the service.
    --------------------------   ---------------------------------------------------------------
    gis                          optional GIS, the GIS on which this tool runs. If not
                                 specified, the active GIS is used.
    ==========================   ===============================================================

    :returns:
       Output feature layer item
    """
    kwargs = locals()
    tool_name = "DetectIncidents"
    gis = _arcgis.env.active_gis if gis is None else gis
    url = gis.properties.helperServices.geoanalytics.url
    params = {
        "f" : "json"
    }
    for key, value in kwargs.items():
        if value is not None:
            params[key] = value

    if output_name is None:
        output_service_name = 'Detect_Incidents_' + _id_generator()
        output_name = output_service_name.replace(' ', '_')
    else:
        output_service_name = output_name.replace(' ', '_')

    output_service = _create_output_service(gis, output_name, output_service_name, 'Detect Track Incidents')

    params['output_name'] = _json.dumps({
        "serviceProperties": {"name" : output_name, "serviceUrl" : output_service.url},
        "itemProperties": {"itemId" : output_service.itemid}})

    _set_context(params)

    param_db = {
        "input_layer": (_FeatureSet, "inputLayer"),
        "track_fields": (str, "trackFields"),
        "start_condition_expression": (str, "startConditionExpression"),
        "end_condition_expression": (str, "endConditionExpression"),
        "output_mode": (str, "outputMode"),
        "time_boundary_split" : (int, "timeBoundarySplit"),
        "time_split_unit" : (str, "timeBoundarySplitUnit"),
        "time_reference" : (datetime.datetime, "timeBoundaryReference"),
        "output_name": (str, "outputName"),
        "output": (_FeatureSet, "output"),
        "context": (str, "context")
    }
    return_values = [
        {"name": "output", "display_name": "Output Features", "type": _FeatureSet},
    ]
    try:
        _execute_gp_tool(gis, tool_name, params, param_db, return_values, _use_async, url, True)
        return output_service
    except:
        output_service.delete()
        raise

    return

def find_similar_locations(
    input_layer,
    search_layer,
    analysis_fields,
    most_or_least_similar = """MostSimilar""",
    match_method = """AttributeValues""",
    number_of_results = 10,
    append_fields = None,
    output_name = None,
    gis = None):
    """

    Based on criteria you specify, find similar locations by measuring the similarity of locations in your candidate search layer to one or more reference locations.

    For example

    * Find the ten most similar stores by examining the number of employees and the annual sales.

    * Find the 100 most similar cities by examining the relationship between population, annual growth, and tax revenue.


   Parameters:

   input_layer: Input Layer (feature layer). Required parameter.

   search_layer: Search Layer (feature layer). Required parameter.

   analysis_fields: Analysis Fields (str). Required parameter.

   most_or_least_similar: Most Or Least Similar (str). Required parameter.
      Choice list:['MostSimilar', 'LeastSimilar', 'Both']

   match_method: Match Method (str). Required parameter.
      Choice list:['AttributeValues', 'AttributeProfiles']

   number_of_results: Number Of Results (int). Required parameter.

   append_fields: Fields To Append To Output (str). Optional parameter.

   output_name: Output Features Name (str). Required parameter.

   gis: Optional, the GIS on which this tool runs. If not specified, the active GIS is used.


Returns:
   output - Output feature layer Item


    """
    kwargs = locals()

    gis = _arcgis.env.active_gis if gis is None else gis
    url = gis.properties.helperServices.geoanalytics.url

    params = {}
    for key, value in kwargs.items():
        if value is not None:
            params[key] = value

    if output_name is None:
        output_service_name = 'Similar Locations_' + _id_generator()
        output_name = output_service_name.replace(' ', '_')
    else:
        output_service_name = output_name.replace(' ', '_')

    output_service = _create_output_service(gis, output_name, output_service_name, 'Find Similar Locations')

    params['output_name'] = _json.dumps({
        "serviceProperties": {"name" : output_name, "serviceUrl" : output_service.url},
        "itemProperties": {"itemId" : output_service.itemid}})

    _set_context(params)

    param_db = {
        "input_layer": (_FeatureSet, "inputLayer"),
        "search_layer": (_FeatureSet, "searchLayer"),
        "analysis_fields": (str, "analysisFields"),
        "most_or_least_similar": (str, "mostOrLeastSimilar"),
        "match_method": (str, "matchMethod"),
        "number_of_results": (int, "numberOfResults"),
        "append_fields": (str, "appendFields"),
        "output_name": (str, "outputName"),
        "context": (str, "context"),
        "output": (_FeatureSet, "Output Features"),
    }
    return_values = [
        {"name": "output", "display_name": "Output Features", "type": _FeatureSet},
    ]
    try:
        _execute_gp_tool(gis, "FindSimilarLocations", params, param_db, return_values, _use_async, url, True)
        return output_service
    except:
        output_service.delete()
        raise

find_similar_locations.__annotations__ = {
    'most_or_least_similar': str,
    'match_method': str,
    'number_of_results': int,
    'append_fields': str,
    'output_name': str}

