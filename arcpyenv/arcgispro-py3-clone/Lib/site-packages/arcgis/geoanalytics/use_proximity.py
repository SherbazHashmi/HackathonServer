"""
These tools help answer one of the most common questions posed in spatial analysis: What is near what?

create_buffers() creates areas of a specified distance from features.
"""
import json as _json

import logging as _logging
import arcgis as _arcgis
from arcgis.features import FeatureSet as _FeatureSet, FeatureCollection
from arcgis.geoprocessing._support import _execute_gp_tool
from ._util import _id_generator, _feature_input, _set_context, _create_output_service

_log = _logging.getLogger(__name__)

_use_async = True

def create_buffers(
    input_layer,
    distance = 1,
    distance_unit = "Miles",
    field = None,
    method = """Planar""",
    dissolve_option = """None""",
    dissolve_fields = None,
    summary_fields = None,
    multipart = False,
    output_name = None,
    context = None,
    gis = None):
    """

    A buffer is an area that covers a given distance from a point, line, or polygon feature.

    Buffers are typically used to create areas that can be further analyzed using other tools. For example, if the question is What buildings are within 1 mile of the school?, the answer can be found by creating a 1-mile buffer around the school and overlaying the buffer with the layer containing building footprints. The end result is a layer of those buildings within 1 mile of the school.

    For example

    * Using linear river features, buffer each river by 50 times the width of the river to determine a proposed riparian boundary.

    * Given areas representing countries, buffer each country by 200 nautical miles to determine the maritime boundary.



Parameters:

   input_layer: Input Features (_FeatureSet). Required parameter.

   distance: Buffer Distance (float). Optional parameter.

   distance_unit: Buffer Distance Unit (str). Optional parameter.
      Choice list:['Feet', 'Yards', 'Miles', 'Meters', 'Kilometers', 'NauticalMiles']

   field: Buffer Distance Field (str). Optional parameter.

   method: Method (str). Required parameter.
      Choice list:['Geodesic', 'Planar']

   dissolve_option: Dissolve Option (str). Optional parameter.
      Choice list:['All', 'List', 'None']

   dissolve_fields: Dissolve Fields (str). Optional parameter.

   summary_fields: Summary Statistics (str). Optional parameter.

   multipart: Allow Multipart Geometries (bool). Optional parameter.

   output_name: Output Features Name (str). Required parameter.


   gis: Optional, the GIS on which this tool runs. If not specified, the active GIS is used.


Returns:
   output - Output Features as a feature layer collection item


    """
    kwargs = locals()


    gis = _arcgis.env.active_gis if gis is None else gis
    url = gis.properties.helperServices.geoanalytics.url

    if isinstance(input_layer, FeatureCollection) and \
       'layers' in input_layer.properties and \
       len(input_layer.properties.layers) > 0:
        input_layer = _FeatureSet.from_dict(
            featureset_dict=input_layer._lazy_properties.layers[0].featureSet)

    params = {}
    for key, value in kwargs.items():
        if value is not None:
            params[key] = value

    if output_name is None:
        output_service_name = 'Create Buffers Analysis_' + _id_generator()
        output_name = output_service_name.replace(' ', '_')
    else:
        output_service_name = output_name.replace(' ', '_')

    output_service = _create_output_service(gis, output_name, output_service_name, 'Create Buffers')

    params['output_name'] = _json.dumps({
        "serviceProperties": {"name" : output_name, "serviceUrl" : output_service.url},
        "itemProperties": {"itemId" : output_service.itemid}})

    _set_context(params)
    param_db = {
        "input_layer": (_FeatureSet, "inputLayer"),
        "distance": (float, "distance"),
        "distance_unit": (str, "distanceUnit"),
        "field": (str, "field"),
        "method": (str, "method"),
        "dissolve_option": (str, "dissolveOption"),
        "dissolve_fields": (str, "dissolveFields"),
        "summary_fields": (str, "summaryFields"),
        "multipart": (bool, "multipart"),
        "output_name": (str, "outputName"),
        "context": (str, "context"),
        "output": (_FeatureSet, "Output Features"),
    }
    return_values = [
        {"name": "output", "display_name": "Output Features", "type": _FeatureSet},
    ]

    try:
        _execute_gp_tool(gis, "CreateBuffers", params, param_db, return_values, _use_async, url, True)
        return output_service
    except:
        output_service.delete()
        raise

create_buffers.__annotations__ = {
    'distance': float,
    'distance_unit': str,
    'field': str,
    'method': str,
    'dissolve_option': str,
    'dissolve_fields': str,
    'summary_fields': str,
    'multipart': bool,
    'output_name': str,
    'context': str}