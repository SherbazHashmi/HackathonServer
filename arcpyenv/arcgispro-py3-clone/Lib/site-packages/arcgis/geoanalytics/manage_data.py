"""

These tools are used for the day-to-day management of geographic and tabular data.

copy_to_data_store copies data to your ArcGIS Data Store and creates a layer in your web GIS.
"""
import json as _json
import logging as _logging
import arcgis as _arcgis
from arcgis.features import FeatureSet as _FeatureSet
from arcgis.geoprocessing._support import _execute_gp_tool
from ._util import _id_generator, _feature_input, _set_context, _create_output_service

_log = _logging.getLogger(__name__)

_use_async = True

def run_python_script(code, layers=None, gis=None):
    """

    The `run_python_script` method executes a Python script on your ArcGIS
    GeoAnalytics Server site. In the script, you can create an analysis
    pipeline by chaining together multiple GeoAnalytics Tools without
    writing intermediate results to a data store. You can also use other
    Python functionality in the script that can be distributed across your
    GeoAnalytics Server.

    For example, suppose that each week you receive a new dataset of
    vehicle locations containing billions of point features. Each time you
    receive a new dataset, you must perform the same workflow involving
    multiple GeoAnalytics Tools to create an information product that you
    share within your organization. This workflow creates several large
    intermediate layers that take up lots of space in your data store. By
    scripting this workflow in Python and executing the code in the Run
    Python Script task, you can avoid creating these unnecessary
    intermediate layers, while simplifying the steps to create the
    information product.

    When you use Run Python Script, the Python code is executed on your
    GeoAnalytics Server. The script runs with the Python 3.6 environment
    that is installed with GeoAnalytics Server, and all console output is
    returned as job messages. Some Python modules can be used in your
    script to execute code across multiple cores of one or more machines
    in your GeoAnalytics Server using Spark 2.2.0(the compute platform that
    distributes analysis for GeoAnalytics Tools).

    A geoanalytics module is available and allows you to run GeoAnalytics
    Tools in the script. This package is imported automatically when you
    use Run Python Script.

    To interact directly with Spark in the Run Python Script task, use the
    pyspark module, which is imported automatically when you run the task.
    The pyspark module is the Python API for Spark and provides a
    collection of distributed analysis tools for data management,
    clustering, regression, and more that can be called in Run Python
    Script and run across your GeoAnalytics Server.

    When using the geoanalytics and pyspark packages, most functions return
    analysis results in memory as Spark DataFrames. Spark data frames can be
    written to a data store or used in the script. This allows for the
    chaining together of multiple geoanalytics and pyspark tools, while only
    writing out the final result to a data store, eliminating the need to
    create any intermediate result layers.

    For advanced users, an instance of SparkContext is instantiated
    automatically as sc and can be used in the script to interact with Spark.
    This allows for the execution of custom distributed analysis across your
    GeoAnalytics Server.

    It is recommended that you use an integrated development environment
    (IDE) to write your Python script, and copy the script text into the Run
    Python Script tool. This makes it easier to identify syntax errors and
    typos prior to running your script. It is also recommended that you run
    your script using a small subset of the input data first to verify that
    there are no logic errors or exceptions. You can use the Describe
    Dataset task to create a sample layer for this purpose.

    ================  ===============================================================
    code              Required String/Python Method. Python code to execute.
    ----------------  ---------------------------------------------------------------
    layers            Optional List. A list of FeatureLayers to operate on.
    ----------------  ---------------------------------------------------------------
    gis               optional GIS. The GIS object where the analysis will take place.
    ================  ===============================================================

    :returns: Dictionary of messages from the code provided.


    """
    if layers is None:
        layers = []
    import inspect
    params = {'f': 'json'}

    if inspect.isfunction(code):
        params['code'] = inspect.getsource(code)
    elif isinstance(code, str):
        params['code'] = code
    else:
        raise ValueError("code must be a string or Python Function.")

    if isinstance(layers, (tuple, list)):
        params['layers'] = layers
    else:
        raise ValueError("layers must be a list or tuple")

    tool_name = "RunPythonScript"
    gis = _arcgis.env.active_gis if gis is None else gis
    url = gis.properties.helperServices.geoanalytics.url

    _set_context(params)

    param_db = {
        "layers": (_FeatureSet, "inputLayers"),
        "code" : (str, "pythonScript"),
        "context": (str, "context"),
    }

    try:
        res, msg = _execute_gp_tool(gis, tool_name, params, param_db, [], _use_async, url, True, return_messages=True)
        return msg
    except:
        raise
    return None

def dissolve_boundaries(input_layer,
                        dissolve_fields=None,
                        summary_fields=None,
                        multipart=False,
                        output_name=None,
                        gis=None):
    """

    The Dissolve Boundaries task finds polygons that intersect or have the same field values and merges them together to form a single polygon.

    Examples:

        A city council wants to control liquor sales by refusing new licenses to stores within 1,000 feet of schools, libraries, and parks. After creating a 1,000-foot buffer around the schools, libraries, and parks, the buffered layers can be joined together and the boundaries can be dissolved to create a single layer of restricted areas.

    Usage Notes:



    Only available at ArcGIS Enterprise 10.7 and later.

    ================  ===============================================================
    **Argument**      **Description**
    ----------------  ---------------------------------------------------------------
    input_layer       required FeatureLayer. The point, line or polygon features.
    ----------------  ---------------------------------------------------------------
    dissolve_fields   Optional string. A comma seperated list of strings for each
                      field that you want to dissolve on.
    ----------------  ---------------------------------------------------------------
    summary_fields    Optional list. Calculate one or more statistics for the
                      dissolved areas by using the summary_fields parameter. The
                      input is a list of key/value pairs in the following format:

                         [{"statisticType" : "<stat>", "onStatisticField" : "<field name>"}]

                      Allows statistics are:

                        + Any (string fields only)
                        + Count
                        + Sum
                        + Minimum
                        + Maximum
                        + Average
                        + Variance
                        + Standard Deviation

                      Example:

                       summary_fields = [{"statisticType" : "Sum", "onStatisticField" : "quadrat_area_km2"},
                                         {"statisticType" : "Mean", "onStatisticField" : "soil_depth_cm"},
                                         {"statisticType" : "Any", "onStatisticField" : "quadrat_desc"}]
    ----------------  ---------------------------------------------------------------
    multipart         Optional boolean. If True, the output service can contain
                      multipart features. If False (default):, the output service
                      will only contain single-part features, and individual features
                      will be created for each part.
    ----------------  ---------------------------------------------------------------
    output_name       optional string. The task will create a feature service of the results. You define the name of the service.
    ----------------  ---------------------------------------------------------------
    gis               optional GIS. The GIS object where the analysis will take place.
    ================  ===============================================================

    :returns: FeatureLayer
    """
    kwargs = locals()
    tool_name = "DissolveBoundaries"
    gis = _arcgis.env.active_gis if gis is None else gis
    url = gis.properties.helperServices.geoanalytics.url
    params = {
        "f" : "json",
    }
    for key, value in kwargs.items():
        if value is not None:
            params[key] = value

    if output_name is None:
        output_service_name = 'Dissolve_Bounds_' + _id_generator()
        output_name = output_service_name.replace(' ', '_')
    else:
        output_service_name = output_name.replace(' ', '_')

    output_service = _create_output_service(gis, output_name, output_service_name, 'Merge Layers')

    params['output_name'] = _json.dumps({
        "serviceProperties": {"name" : output_name, "serviceUrl" : output_service.url},
        "itemProperties": {"itemId" : output_service.itemid}})

    _set_context(params)

    param_db = {
        "input_layer": (_FeatureSet, "inputLayer"),
        "multipart": (bool, "multipart"),
        "summary_fields": (list, "summaryFields"),
        "dissolve_fields" : (list, "dissolveFields"),
        "output_name": (str, "OutputName"),
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

def merge_layers(input_layer, merge_layer, merge_attributes=None, output_name=None, gis=None):
    """
    The Merge Layers task combines two feature layers to create a single output layer. The tool
    requires that both layers have the same geometry type (tabular, point, line, or polygon). If
    time is enabled on one layer, the other must also be time enabled and have the same time type
    (instant or interval). The result will always contain all fields from the input layer. All
    fields from the merge layer will be included by default, or you can specify custom merge rules
    to define the resulting schema. For example:

    - I have three layers for England, Wales, and Scotland and I want a single layer of Great
      Britain. I can use Merge Layers to combine the areas and maintain all fields from each area.
    - I have two layers containing parcel information for contiguous townships. I want to join them
      together into a single layer, keeping only the fields that have the same name and type in the
      two layers.

    Only available at **ArcGIS Enterprise 10.7** and later.

    ================  ===============================================================
    **Argument**      **Description**
    ----------------  ---------------------------------------------------------------
    input_layer       Required FeatureLayer. The point, line or polygon features.
    ----------------  ---------------------------------------------------------------
    merge_layer       Required FeatureLayer. The point, line, or polygon features to
                      merge with the input_layer. The merge_layer must contain the
                      same geometry type (tabular, point, line, or polygon) and the
                      same time type (none, instant, or interval) as the input_layer.
                      All fields in the merge_layer will be included in the result
                      layer by default or you can define merge_attributes to
                      customize the resulting schema.
    ----------------  ---------------------------------------------------------------
    merge_attributes  Optional list. Defines how the fields in mergeLayer will be
                      modified. By default, all fields from both inputs will be
                      included in the output layer.

                      If a field exists in one layer but not the other, the output
                      layer will still contain the field. The output field will
                      contain null values for the input features that did not have the
                      field. For example, if the input_layer contains a field named
                      TYPE but the merge_layer does not contain TYPE, the output will
                      contain TYPE, but its values will be null for all the features
                      copied from the merge_layer.

                      You can control how fields in the merge_layer are written to the
                      output layer using the following merge types that operate on a
                      specified merge_layer field:

                      + Remove - The field in the merge_layer will be removed from the output layer.
                      + Rename - The field in the merge_layer will be renamed in the output layer. You cannot rename a field in the merge_layer to a field in the inputLayer. If you want to make field names equivalent, use Match.
                      + Match - A field in the merge_layer is made equivalent to a field in the input_layer specified by mergeValue. For example, the input_layer has a field named CODE and the merge_layer has a field named STATUS. You can match STATUS to CODE, and the output will contain the CODE field with values of the STATUS field used for features copied from the merge_layer. Type casting is supported (for example, double to integer, integer to string) except for string to numeric.
                      REST web example:

                      Syntax: This example matches Average_Sales to Mean_Sales,
                              removesBonus, and renamesField4 to Errors.

                      ```

                        [{
                            "mergeLayerField": "Mean_Sales",
                            "mergeType": "Match",
                            "mergeValue": "Average_Sales"
                        },
                        {
                            "mergeLayerField": "Bonus",
                            "mergeType": "Remove",
                        },
                        {
                            "mergeLayerField": "Field4",
                            "mergeType": "Rename",
                            "mergeValue": "Errors"
                        }]

                      ```

    ----------------  ---------------------------------------------------------------
    output_name       Optional string. The task will create a feature service of the results. You define the name of the service.
    ----------------  ---------------------------------------------------------------
    gis               Optional GIS. The GIS object where the analysis will take place.
    ================  ===============================================================

    :returns: FeatureLayer
    """
    kwargs = locals()
    tool_name = "MergeLayers"
    gis = _arcgis.env.active_gis if gis is None else gis
    url = gis.properties.helperServices.geoanalytics.url
    params = {
        "f" : "json",
    }
    for key, value in kwargs.items():

        if value is not None:
            params[key] = value
        elif key == 'merge_attributes' and value is None:
            params[key] = []
    if output_name is None:
        output_service_name = 'Merge_Layers_' + _id_generator()
        output_name = output_service_name.replace(' ', '_')
    else:
        output_service_name = output_name.replace(' ', '_')

    output_service = _create_output_service(gis, output_name, output_service_name, 'Merge Layers')

    params['output_name'] = _json.dumps({
        "serviceProperties": {"name" : output_name, "serviceUrl" : output_service.url},
        "itemProperties": {"itemId" : output_service.itemid}})

    _set_context(params)

    param_db = {
        "input_layer": (_FeatureSet, "inputLayer"),
        "merge_layer": (_FeatureSet, "mergeLayer"),
        "merge_attributes" : (list, "mergingAttributes"),
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


def clip_layer(input_layer, clip_layer, output_name=None, gis=None):
    """
    Clip_layer features from one layer to the extent of a boundary layer. Use this tool to cut out a piece
    of one feature class using one or more of the features in another feature class as a cookie
    cutter. This is particularly useful for creating a new feature layers - also referred to as study
    area or area of interest (AOI)- that contains a geographic subset of the features in another,
    larger feature class.

    Only available at **ArcGIS Enterprise 10.7** and later.

    ================  ===============================================================
    **Argument**      **Description**
    ----------------  ---------------------------------------------------------------
    input_layer       required FeatureLayer. The point, line or polygon features.
    ----------------  ---------------------------------------------------------------
    clip_layer        required FeatureLayer. The features that will be clipping the input_layer features.
    ----------------  ---------------------------------------------------------------
    output_name       optional string. The task will create a feature service of the results. You define the name of the service.
    ----------------  ---------------------------------------------------------------
    gis               optional GIS. The GIS object where the analysis will take place.
    ================  ===============================================================

    :returns: FeatureLayer

    """
    kwargs = locals()
    tool_name = "ClipLayer"
    gis = _arcgis.env.active_gis if gis is None else gis
    url = gis.properties.helperServices.geoanalytics.url
    params = {
        "f" : "json",
    }
    for key, value in kwargs.items():
        if value is not None:
            params[key] = value
    if output_name is None:
        output_service_name = 'Clip_Layers_' + _id_generator()
        output_name = output_service_name.replace(' ', '_')
    else:
        output_service_name = output_name.replace(' ', '_')

    output_service = _create_output_service(gis, output_name, output_service_name, 'Overlay Layers')

    params['output_name'] = _json.dumps({
        "serviceProperties": {"name" : output_name, "serviceUrl" : output_service.url},
        "itemProperties": {"itemId" : output_service.itemid}})

    _set_context(params)

    param_db = {
        "input_layer": (_FeatureSet, "inputLayer"),
        "clip_layer": (_FeatureSet, "clipLayer"),
        "outputType" : (str, 'outputType'),
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


def overlay_data(input_layer, overlay_layer, overlay_type="intersect", output_name=None, gis=None):
    """
    Only available at ArcGIS Enterprise 10.6.1 and later.

    ================  ===============================================================
    **Argument**      **Description**
    ----------------  ---------------------------------------------------------------
    input_layer       required FeatureLayer. The point, line or polygon features.
    ----------------  ---------------------------------------------------------------
    overlay_layer     required FeatureLayer. The features that will be overlaid with the input_layer features.
    ----------------  ---------------------------------------------------------------
    overlay_type      optional string. The type of overlay to be performed.
                      Values: intersect, erase

                      + intersect - Computes a geometric intersection of the input layers. Features or portions of features that overlap in both the inputLayer and overlayLayer layers will be written to the output layer. This is the default.
                      + erase - Only those features or portions of features in the overlay_layer that are not within the features in the input_layer layer are written to the output.
                      + union - Computes a geometric union of the input_layer and overlay_layer. All features and their attributes will be written to the layer.
                      + identity - Computes a geometric intersection of the input features and identity features. Features or portions of features that overlap in both input_layer and overlay_layer will be written to the output layer.
                      + symmetricaldifference - Features or portions of features in the input_layer and overlay_layer that do not overlap will be written to the output layer.

    ----------------  ---------------------------------------------------------------
    output_name       optional string. The task will create a feature service of the results. You define the name of the service.
    ----------------  ---------------------------------------------------------------
    gis               optional GIS. The GIS object where the analysis will take place.
    ================  ===============================================================

    :returns: FeatureLayer
    """
    kwargs = locals()
    tool_name = "OverlayLayers"
    gis = _arcgis.env.active_gis if gis is None else gis
    url = gis.properties.helperServices.geoanalytics.url
    params = {
        "f" : "json",
        "outputType" : "Input",
        'tolerance' : 0,
        'snapToInput' : 'false'
    }
    for key, value in kwargs.items():
        if value is not None:
            params[key] = value

    if output_name is None:
        output_service_name = 'Overlay_Layers_' + _id_generator()
        output_name = output_service_name.replace(' ', '_')
    else:
        output_service_name = output_name.replace(' ', '_')

    output_service = _create_output_service(gis, output_name, output_service_name, 'Overlay Layers')

    params['output_name'] = _json.dumps({
        "serviceProperties": {"name" : output_name, "serviceUrl" : output_service.url},
        "itemProperties": {"itemId" : output_service.itemid}})

    _set_context(params)

    param_db = {
        "input_layer": (_FeatureSet, "inputLayer"),
        "overlay_layer": (_FeatureSet, "overlayLayer"),
        "outputType" : (str, 'outputType'),
        "overlay_type" : (str, "overlayType"),
        "output_name": (str, "OutputName"),
        "context": (str, "context"),
        'tolerance' : (int, 'tolerance'),
        "output": (_FeatureSet, "output"),
        'snapToInput' : (str, 'snapToInput')
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


def append_data(input_layer, append_layer, field_mapping=None, gis=None):
    """
    Only available at ArcGIS Enterprise 10.6.1 and later.

    The Append Data task appends tabular, point, line, or polygon data to an existing layer.
    The input layer must be a hosted feature layer. The tool will add the appended data as
    rows to the input layer. No new output layer is created.

    ================  ===============================================================
    **Argument**      **Description**
    ----------------  ---------------------------------------------------------------
    input_layer       required FeatureLayer , The table, point, line or polygon features.
    ----------------  ---------------------------------------------------------------
    append_layer      required FeatureLayer. The table, point, line, or polygon features
                      to be appended to the input_layer. To append geometry, the
                      append_layer must have the same geometry type as the
                      input_layer. If the geometry types are not the same, the
                      append_layer geometry will be removed and all other matching
                      fields will be appended. The geometry of the input_layer will
                      always be maintained.
    ----------------  ---------------------------------------------------------------
    field_mapping     Defines how the fields in append_layer are appended to the
                      input_layer.

                      The following are set by default:

                        - All append_layer fields that match input_layer schema will be appended.
                        - Fields that exist in the input_layer and not in the append_layer will be appended with null values.
                        - Fields that exist in the append_layer and not in the input_layer will not be appended.

                      Optionally choose how input_layer fields will be appended from the following:

                      - AppendField - Matches the input_layer field with an append_layer field of a different name. Field types must match.
                      - Expression - Calculates values for the resulting field. Values are calculated using Arcade expressions. To assign null values, use 'null'.
    ----------------  ---------------------------------------------------------------
    gis               optional GIS, the GIS on which this tool runs. If not
                      specified, the active GIS is used.
    ================  ===============================================================

    :returns: boolean

    """
    kwargs = locals()
    tool_name = "AppendData"
    gis = _arcgis.env.active_gis if gis is None else gis
    url = gis.properties.helperServices.geoanalytics.url
    params = {
        "f" : "json"
    }
    for key, value in kwargs.items():
        if value is not None:
            params[key] = value

    _set_context(params)

    param_db = {
        "input_layer": (_FeatureSet, "inputLayer"),
        "append_layer": (_FeatureSet, "appendLayer"),
        "field_mapping" : (str, "fieldMapping"),
        "context": (str, "context")
    }
    return_values = [
    ]
    try:
        _execute_gp_tool(gis, tool_name, params, param_db, return_values, _use_async, url, True)
        return True
    except:
        raise

    return False


def calculate_fields(input_layer,
                     field_name,
                     data_type,
                     expression,
                     track_aware=False,
                     track_fields=None,
                     time_boundary_split=None,
                     time_split_unit=None,
                     time_reference=None,
                     output_name=None,
                     gis=None
                     ):
    """
    The Calculate Field task works with a layer to create and populate a
    new field. The output is a new feature layer, that is the same as the
    input features, with the additional field added.

    ==========================   ===============================================================
    **Argument**                 **Description**
    --------------------------   ---------------------------------------------------------------
    input_layer                  required service , The table, point, line or polygon features
                                 containing potential incidents.
    --------------------------   ---------------------------------------------------------------
    field_name                   required string, A string representing the name of the new
                                 field. If the name already exists in the dataset, then a
                                 numeric value will be appended to the field name.
    --------------------------   ---------------------------------------------------------------
    data_type                    required string, the type for the new field.
                                 Values: Date, Double, Integer, String
    --------------------------   ---------------------------------------------------------------
    expression                   required string, An Arcade expression used to calculate the new
                                 field values. You can use any of the Date, Logical,
                                 Mathematical or Text function available with Arcade.
    --------------------------   ---------------------------------------------------------------
    track_aware                  optional boolean, Boolean value denoting if the expression is
                                 track aware.
                                 Default: False
    --------------------------   ---------------------------------------------------------------
    track_fields                 optional string, The fields used to identify distinct tracks.
                                 There can be multiple track_fields. track_fields are only
                                 required when track_aware is true.
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
    ==========================  ================================================================

    :returns:
       Feature Layer
    """
    kwargs = locals()
    tool_name = "CalculateField"
    gis = _arcgis.env.active_gis if gis is None else gis
    url = gis.properties.helperServices.geoanalytics.url
    params = {
        "f" : "json"
    }
    for key, value in kwargs.items():
        if value is not None:
            params[key] = value

    if output_name is None:
        output_service_name = 'Calculate_Fields_' + _id_generator()
        output_name = output_service_name.replace(' ', '_')
    else:
        output_service_name = output_name.replace(' ', '_')

    output_service = _create_output_service(gis, output_name, output_service_name, 'Calculate Fields')

    params['output_name'] = _json.dumps({
        "serviceProperties": {"name" : output_name, "serviceUrl" : output_service.url},
        "itemProperties": {"itemId" : output_service.itemid}})

    _set_context(params)

    param_db = {
        "input_layer": (_FeatureSet, "inputLayer"),
        "field_name" : (str, "fieldName"),
        "data_type" : (str, "dataType"),
        "expression" : (str, "expression"),
        "track_aware" : (bool, "trackAware"),
        "track_fields" : (str, "trackFields"),
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

def copy_to_data_store(
    input_layer,
    output_name = None,
    gis = None):
    """

    Copies an input feature layer or table to an ArcGIS Data Store and creates a layer in your web GIS.

    For example

    * Copy a collection of .csv files in a big data file share to the spatiotemporal data store for visualization.

    * Copy the features in the current map extent that are stored in the spatiotemporal data store to the relational data store.

    This tool will take an input layer and copy it to a data store. Data will be copied to the ArcGIS Data Store and will be stored in your relational or spatiotemporal data store.

    For example, you could copy features that are stored in a big data file share to a relational data store and specify that only features within the current map extent will be copied. This would create a hosted feature service with only those features that were within the specified map extent.

   Parameters:

   input_layer: Input Layer (feature layer). Required parameter.

   output_name: Output Layer Name (str). Required parameter.

   gis: Optional, the GIS on which this tool runs. If not specified, the active GIS is used.


Returns:
   output - Output Layer as a feature layer collection item


    """
    kwargs = locals()

    gis = _arcgis.env.active_gis if gis is None else gis
    url = gis.properties.helperServices.geoanalytics.url

    params = {}
    for key, value in kwargs.items():
        if value is not None:
            params[key] = value

    if output_name is None:
        output_service_name = 'Data Store Copy_' + _id_generator()
        output_name = output_service_name.replace(' ', '_')
    else:
        output_service_name = output_name.replace(' ', '_')

    output_service = _create_output_service(gis, output_name, output_service_name, 'Copy To Data Store')

    params['output_name'] = _json.dumps({
        "serviceProperties": {"name" : output_name, "serviceUrl" : output_service.url},
        "itemProperties": {"itemId" : output_service.itemid}})

    _set_context(params)

    param_db = {
        "input_layer": (_FeatureSet, "inputLayer"),
        "output_name": (str, "outputName"),
        "context": (str, "context"),
        "output": (_FeatureSet, "Output Layer"),
    }
    return_values = [
        {"name": "output", "display_name": "Output Layer", "type": _FeatureSet},
    ]
    try:
        _execute_gp_tool(gis, "CopyToDataStore", params, param_db, return_values, _use_async, url, True)
        return output_service
    except:
        output_service.delete()
        raise

copy_to_data_store.__annotations__ = {
    'output_name': str}





