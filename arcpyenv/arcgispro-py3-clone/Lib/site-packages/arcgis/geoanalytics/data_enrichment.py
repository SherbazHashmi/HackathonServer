"""

These tools are used for data enrichment using geoanalytics

"""
import json as _json
import logging as _logging
import arcgis as _arcgis
from arcgis.features import FeatureSet as _FeatureSet
from arcgis.geoprocessing._support import _execute_gp_tool
from arcgis.geoanalytics._util import _id_generator, _feature_input, _set_context, _create_output_service

_log = _logging.getLogger(__name__)

_use_async = True

def enrich_from_grid(input_layer,
                     grid_layer,
                     enrichment_attributes=None,
                     output_name=None,
                     gis=None):
    """
    The Enrich From Multi-Variable Grid task joins attributes from a multi-variable grid to a point
    layer. The multi-variable grid must be created using the Build Multi-Variable Grid task.
    Metadata from the multi-variable grid is used to efficiently enrich the input point features,
    making it faster than the Join Features task. Attributes in the multi-variable grid are joined
    to the input point features when the features intersect the grid.

    The attributes in the multi-variable grid can be used as explanatory variables when modeling
    spatial relationships with your input point features, and this task allows you to join those
    attributes to the point features quickly.

        Usage Notes:

        Only available at ArcGIS Enterprise 10.7 and later.

    ======================  ===============================================================
    **Argument**            **Description**
    ----------------------  ---------------------------------------------------------------
    input_layer             required FeatureLayer. The point features that will be enriched
                            by the multi-variable grid.
    ----------------------  ---------------------------------------------------------------
    grid_layer              required FeatureLayer. The multi-variable grid layer.
    ----------------------  ---------------------------------------------------------------
    enrichment_attributes   optional String. A list of fields in the multi-variable grid
                            that will be joined to the input point features. If the
                            attributes are not provided, all fields in the multi-variable
                            grid will be joined to the input point features.
    ----------------------  ---------------------------------------------------------------
    output_name             optional string. The task will create a feature service of the
                            results. You define the name of the service.
    ----------------------  ---------------------------------------------------------------
    gis                     optional GIS. The GIS object where the analysis will take place.
    ======================  ===============================================================

    :returns: FeatureLayer

    """
    kwargs = locals()
    tool_name = "EnrichFromMultiVariableGrid"
    gis = _arcgis.env.active_gis if gis is None else gis
    url = gis.properties.helperServices.geoanalytics.url
    params = {
        "f" : "json",
    }
    for key, value in kwargs.items():
        if value is not None:
            params[key] = value

    if output_name is None:
        output_service_name = 'Enrich_Grid_' + _id_generator()
        output_name = output_service_name.replace(' ', '_')
    else:
        output_service_name = output_name.replace(' ', '_')

    output_service = _create_output_service(gis, output_name, output_service_name, 'Enrich Grid Layers')

    params['output_name'] = _json.dumps({
        "serviceProperties": {"name" : output_name, "serviceUrl" : output_service.url},
        "itemProperties": {"itemId" : output_service.itemid}})

    _set_context(params)

    param_db = {
        "input_layer": (_FeatureSet, "inputFeatures"),
        "grid_layer" : (_FeatureSet, "gridLayer"),
        "enrichment_attributes" : (str, "enrichAttributes"),
        "output_name": (str, "outputName"),
        "context": (str, "context"),
        "output": (_FeatureSet, "output"),
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
