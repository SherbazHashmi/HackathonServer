"Functions for calling the Raster Analysis Tools. The RasterAnalysisTools service is used by ArcGIS Server to provide distributed raster analysis."

from arcgis.geoprocessing._support import _analysis_job, _analysis_job_results, \
                                          _analysis_job_status, _layer_input
import json as _json
import arcgis as _arcgis
import string as _string
import random as _random
import collections
from arcgis.gis import Item
from arcgis.raster._util import _set_context, _id_generator


def get_datastores(gis=None):
    """
    Returns a helper object to manage raster analytics datastores in the GIS.
    If a gis isn't specified, returns datastore manager of arcgis.env.active_gis
    """
    gis = _arcgis.env.active_gis if gis is None else gis

    for ds in gis._datastores:
        if 'RasterAnalytics' in ds._server['serverFunction']:
            return ds

    return None


def is_supported(gis=None):
    """
    Returns True if the GIS supports raster analytics. If a gis isn't specified,
    checks if arcgis.env.active_gis supports raster analytics
    """
    gis = _arcgis.env.active_gis if gis is None else gis
    if 'rasterAnalytics' in gis.properties.helperServices:
        return True
    else:
        return False

def _id_generator(size=6, chars=_string.ascii_uppercase + _string.digits):
    return ''.join(_random.choice(chars) for _ in range(size))

        
def _create_output_image_service(gis, output_name, task, folder=None):
    ok = gis.content.is_service_name_available(output_name, "Image Service")
    if not ok:
        raise RuntimeError("An Image Service by this name already exists: " + output_name)

    create_parameters = {
        "name": output_name,
        "description": "",
        "capabilities": "Image",
        "properties": {
            "path": "@",
            "description": "",
            "copyright": ""
        }
    }

    output_service = gis.content.create_service(output_name, create_params=create_parameters,
                                                      service_type="imageService", folder=folder)
    description = "Image Service generated from running the " + task + " tool."
    item_properties = {
        "description": description,
        "tags": "Analysis Result, " + task,
        "snippet": "Analysis Image Service generated from " + task
    }
    output_service.update(item_properties)
    return output_service

def _create_output_feature_service(gis, output_name, output_service_name='Analysis feature service', task='GeoAnalytics', folder=None):
    ok = gis.content.is_service_name_available(output_name, 'Feature Service')
    if not ok:
        raise RuntimeError("A Feature Service by this name already exists: " + output_name)

    createParameters = {
            "currentVersion": 10.2,
            "serviceDescription": "",
            "hasVersionedData": False,
            "supportsDisconnectedEditing": False,
            "hasStaticData": True,
            "maxRecordCount": 2000,
            "supportedQueryFormats": "JSON",
            "capabilities": "Query",
            "description": "",
            "copyrightText": "",
            "allowGeometryUpdates": False,
            "syncEnabled": False,
            "editorTrackingInfo": {
                "enableEditorTracking": False,
                "enableOwnershipAccessControl": False,
                "allowOthersToUpdate": True,
                "allowOthersToDelete": True
            },
            "xssPreventionInfo": {
                "xssPreventionEnabled": True,
                "xssPreventionRule": "InputOnly",
                "xssInputRule": "rejectInvalid"
            },
            "tables": [],
            "name": output_service_name.replace(' ', '_')
        }

    output_service = gis.content.create_service(output_name, create_params=createParameters, service_type="featureService", folder=folder)
    description = "Feature Service generated from running the " + task + " tool."
    item_properties = {
            "description" : description,
            "tags" : "Analysis Result, " + task,
            "snippet": output_service_name
            }
    output_service.update(item_properties)
    return output_service


def _flow_direction_analytics_converter(raster_function,output_name=None, other_outputs=None,gis=None, **kwargs):
    input_surface_raster = forceFlow = flowDirectionType = output_flow_direction_raster = output_drop_name = None

    input_surface_raster = raster_function['rasterFunctionArguments']['in_surface_raster']
    if 'force_flow' in raster_function['rasterFunctionArguments'].keys():
        forceFlow = raster_function['rasterFunctionArguments']['force_flow']
    if 'flow_direction_type' in raster_function['rasterFunctionArguments'].keys():
        flowDirectionType = raster_function['rasterFunctionArguments']['flow_direction_type']
    output_flow_direction_raster = output_name
    if "out_drop_raster" in other_outputs.keys():
        output_drop_name = "out_drop_raster" + '_' + _id_generator()
    return _flow_direction(input_surface_raster, forceFlow, flowDirectionType, output_flow_direction_raster, output_drop_name, gis=gis, **kwargs)

def _calculate_travel_cost_analytics_converter(raster_function,output_name=None, other_outputs=None,gis=None, **kwargs):
    input_source = None
    input_cost_raster=None
    input_surface_raster=None
    maximum_distance=None
    input_horizonal_raster=None
    horizontal_factor=None
    input_vertical_raster=None
    vertical_factor=None
    source_cost_multiplier=None
    source_start_cost=None
    source_resistance_rate=None
    source_capacity=None
    source_direction=None
    allocation_field=None
    output_backlink_name=None
    output_allocation_name=None
    output_distance_name=None

    if raster_function['rasterFunctionArguments']['in_source_data'] is not None:
        input_source = raster_function['rasterFunctionArguments']['in_source_data']
    if 'in_cost_raster' in raster_function['rasterFunctionArguments'].keys():
        input_cost_raster = raster_function['rasterFunctionArguments']['in_cost_raster']
    if 'in_surface_raster' in raster_function['rasterFunctionArguments'].keys():
        input_surface_raster = raster_function['rasterFunctionArguments']['in_surface_raster']
    if 'maximum_distance' in raster_function['rasterFunctionArguments'].keys():
        maximum_distance = raster_function['rasterFunctionArguments']['maximum_distance']
    if 'in_horizontal_raster' in raster_function['rasterFunctionArguments'].keys():
        input_horizonal_raster = raster_function['rasterFunctionArguments']['in_horizontal_raster']
    if 'horizontal_factor' in raster_function['rasterFunctionArguments'].keys():
        horizontal_factor = raster_function['rasterFunctionArguments']['horizontal_factor']
    if 'in_vertical_raster' in raster_function['rasterFunctionArguments'].keys():
        input_vertical_raster = raster_function['rasterFunctionArguments']['in_vertical_raster']
    if 'vertical_factor' in raster_function['rasterFunctionArguments'].keys():
        vertical_factor = raster_function['rasterFunctionArguments']['vertical_factor']
    if 'source_cost_multiplier' in raster_function['rasterFunctionArguments'].keys():
        source_cost_multiplier = raster_function['rasterFunctionArguments']['source_cost_multiplier']
    if 'source_start_cost' in raster_function['rasterFunctionArguments'].keys():
        source_start_cost = raster_function['rasterFunctionArguments']['source_start_cost']
    if 'source_resistance_rate' in raster_function['rasterFunctionArguments'].keys():
        source_resistance_rate = raster_function['rasterFunctionArguments']['source_resistance_rate']
    if 'source_capacity' in raster_function['rasterFunctionArguments'].keys():
        source_capacity = raster_function['rasterFunctionArguments']['source_capacity']
    if 'source_direction' in raster_function['rasterFunctionArguments'].keys():
        source_direction = raster_function['rasterFunctionArguments']['source_direction']
    if 'allocation_field' in raster_function['rasterFunctionArguments'].keys():
        allocation_field = raster_function['rasterFunctionArguments']['allocation_field']
    output_distance_name = output_name

    if "out_backlink_raster" in other_outputs.keys():
        if other_outputs["out_backlink_raster"] is True:
            output_backlink_name = "out_backlink" + '_' + _id_generator()

    if "out_allocation_raster" in other_outputs.keys():
        if other_outputs["out_allocation_raster"] is True:
            output_allocation_name = "out_allocation" + '_' + _id_generator()

    return _calculate_travel_cost(input_source, input_cost_raster, input_surface_raster,
                                  maximum_distance, input_horizonal_raster, horizontal_factor,
                                  input_vertical_raster, vertical_factor, source_cost_multiplier,
                                  source_start_cost, source_resistance_rate, source_capacity,
                                  source_direction, allocation_field, output_distance_name,
                                  output_backlink_name, output_allocation_name, gis=gis,  **kwargs)

def _calculate_distance_analytics_converter(raster_function,output_name=None, other_outputs=None,gis=None, **kwargs):
    input_source = None
    maximum_distance=None
    output_cell_size=None
    allocation_field=None
    output_allocation_name=None
    output_direction_name=None
    output_distance_name=None

    if raster_function['rasterFunctionArguments']['in_source_data'] is not None:
        input_source = raster_function['rasterFunctionArguments']['in_source_data']
    if 'maximum_distance' in raster_function['rasterFunctionArguments'].keys():
        maximum_distance = raster_function['rasterFunctionArguments']['maximum_distance']
    if 'allocation_field' in raster_function['rasterFunctionArguments'].keys():
        allocation_field = raster_function['rasterFunctionArguments']['allocation_field']
    if 'output_cell_size' in raster_function['rasterFunctionArguments'].keys():
        output_cell_size = raster_function['rasterFunctionArguments']['output_cell_size']
    output_distance_name = output_name

    if "out_direction_raster" in other_outputs.keys():
        if other_outputs["out_direction_raster"] is True:
            output_direction_name = "out_direction" + '_' + _id_generator()

    if "out_allocation_raster" in other_outputs.keys():
        if other_outputs["out_allocation_raster"] is True:
            output_allocation_name = "out_allocation" + '_' + _id_generator()

    return _calculate_distance(input_source, 
                               maximum_distance, 
                               output_cell_size, 
                               allocation_field, 
                               output_distance_name,
                               output_direction_name, 
                               output_allocation_name, 
                               gis=gis,  
                               **kwargs)


def _return_output(num_returns, output_dict ,return_value_names):
    if num_returns == 1:
        return output_dict[return_value_names[0]]
 
    else:
        ret_names = []
        for return_value in return_value_names:
            ret_names.append(return_value)
        NamedTuple = collections.namedtuple('FunctionOutput', ret_names)
        function_output = NamedTuple(**output_dict)
        return function_output

def _set_output_raster(output_name, task, gis, output_properties=None):
    output_service = None
    output_raster = None
    
    if task == "GenerateRaster":
        task_name = "GeneratedRasterProduct"
    else:
        task_name = task

    folder = None
    folderId = None

    if output_properties is not None:
        if "folder" in output_properties:
            folder = output_properties["folder"]
    if folder is not None:
        if isinstance(folder, dict):
            if "id" in folder:
                folderId = folder["id"]
                folder=folder["title"]
        else:
            owner = gis.properties.user.username
            folderId = gis._portal.get_folder_id(owner, folder)
        if folderId is None:
            folder_dict = gis.content.create_folder(folder, owner)
            folder = folder_dict["title"]
            folderId = folder_dict["id"]

    if output_name is None:
        output_name = str(task_name) + '_' + _id_generator()
        output_service = _create_output_image_service(gis, output_name, task, folder=folder)
        output_raster = {"serviceProperties": {"name" : output_service.name, "serviceUrl" : output_service.url}, "itemProperties": {"itemId" : output_service.itemid}}
    elif isinstance(output_name, str):
        output_service = _create_output_image_service(gis, output_name, task, folder=folder)
        output_raster = {"serviceProperties": {"name" : output_service.name, "serviceUrl" : output_service.url}, "itemProperties": {"itemId" : output_service.itemid}}
    elif isinstance(output_name, _arcgis.gis.Item):
        output_service = output_name
        output_raster = {"itemProperties":{"itemId":output_service.itemid}}
    else:
        raise TypeError("output_raster should be a string (service name) or Item") 

    if folderId is not None:
        output_raster["itemProperties"].update({"folderId":folderId})
    output_raster = _json.dumps(output_raster)
    return output_raster, output_service

def _save_ra(raster_function,output_name=None, other_outputs=None,gis=None, **kwargs):
    if raster_function['rasterFunctionArguments']['toolName'] is "FlowDirection_sa":
        return _flow_direction_analytics_converter(raster_function, output_name=output_name, other_outputs = other_outputs, gis =gis, **kwargs)
    if raster_function['rasterFunctionArguments']['toolName'] is "CalculateTravelCost_sa":
        return _calculate_travel_cost_analytics_converter(raster_function, output_name=output_name, other_outputs = other_outputs, gis =gis, **kwargs)
    if raster_function['rasterFunctionArguments']['toolName'] is "CalculateDistance_sa":
        return _calculate_distance_analytics_converter(raster_function, output_name=output_name, other_outputs = other_outputs, gis =gis, **kwargs)

def _build_param_dictionary(gis, params, input_rasters, raster_type_name, raster_type_params = None, image_collection_properties = None, use_input_rasters_by_ref = False):
    
    inputRasterSpecified = False
    # input rasters
    if isinstance(input_rasters, list):
        # extract the IDs of all the input items
        # and then convert the list to JSON
        item_id_list = []
        url_list = []
        uri_list = []
        for item in input_rasters:
            if isinstance(item, Item):
                item_id_list.append(item.itemid)
            elif isinstance(item, str):
                if 'http:' in item or 'https:' in item:
                    url_list.append(item)
                else:
                    uri_list.append(item)        
        
        if len(item_id_list) > 0:
            params["inputRasters"] = {"itemIds" : item_id_list }
            inputRasterSpecified = True
        elif len(url_list) > 0:
            params["inputRasters"] = {"urls" : url_list}
            inputRasterSpecified = True
        elif len(uri_list) > 0:
            params["inputRasters"] = {"uris" : uri_list}
            inputRasterSpecified = True
    elif isinstance(input_rasters, str):
        # the input_rasters is a folder name; try and extract the folderID
        owner = gis.properties.user.username
        folderId = gis._portal.get_folder_id(owner, input_rasters)
        if folderId is None:
            if 'http:' in input_rasters or 'https:' in input_rasters:
                params["inputRasters"] = {"url" : input_rasters}
            else:
                params["inputRasters"] = {"uri" : input_rasters}
        else:
            params["inputRasters"] = {"folderId" : folderId}
        inputRasterSpecified = True

    if inputRasterSpecified is False:
        raise RuntimeError("Input raster list to be added to the collection must be specified")
    else:
        if use_input_rasters_by_ref:
            params["inputRasters"].update({"byref":True})

    # raster_type
    if not isinstance(raster_type_name, str):
        raise RuntimeError("Invalid input raster_type parameter")

    elevation_set = 0
    if raster_type_params is not None:
        for element in raster_type_params.keys():
            if(element.lower() == "constantz"):
                value = raster_type_params[element]
                del raster_type_params[element]
                raster_type_params.update({"ConstantZ":value})

                elevation_set = 1
                break
            elif(element.lower() == "averagezdem"):
                value = raster_type_params[element]
                del raster_type_params[element]
                raster_type_params.update({"averagezdem":value})
                elevation_set = 1
                break

        if(elevation_set == 0):
            if "orthomappingElevation" in gis.properties.helperServices.keys():
                raster_type_params["averagezdem"] = gis.properties.helperServices["orthomappingElevation"]
            else:
                raster_type_params["averagezdem"] = {"url":"https://elevation3d.arcgis.com/arcgis/rest/services/WorldElevation3D/Terrain3D/ImageServer"}
    else:
        if "orthomappingElevation" in gis.properties.helperServices.keys():
            raster_type_params = {"averagezdem" : gis.properties.helperServices["orthomappingElevation"]}
        else:
            raster_type_params = {"averagezdem": {"url":"https://elevation3d.arcgis.com/arcgis/rest/services/WorldElevation3D/Terrain3D/ImageServer"}}


    params["rasterType"] = { "rasterTypeName" : raster_type_name, "rasterTypeParameters" : raster_type_params }
    if image_collection_properties is not None:
        if "rasterType" in params:
            params["rasterType"].update({"imageCollectionProps":image_collection_properties})

    params["rasterType"] = _json.dumps(params["rasterType"])
    return


###################################################################################################
###################################################################################################
def _set_image_collection_param(gis, params, image_collection):
    if isinstance(image_collection, str):
        #doesnotexist = gis.content.is_service_name_available(image_collection, "Image Service")
        #if doesnotexist:
            #raise RuntimeError("The input image collection does not exist")
        if 'http:' in image_collection or 'https:' in image_collection:
            params['imageCollection'] = _json.dumps({ 'url' : image_collection })
        else:
            params['imageCollection'] = _json.dumps({ 'uri' : image_collection })
    elif isinstance(image_collection, Item):
        params['imageCollection'] = _json.dumps({ "itemId" : image_collection.itemid })
    else:
        raise TypeError("image_collection should be a string (url or uri) or Item")

    return


# def monitor_vegetation(input_raster,
#                        method_to_use='NDVI',
#                        nir_band=1,
#                        red_band=2,
#                        options={},
#                        output_name=None,
#                        gis=None):
#     """
#
#     :param input_raster: multiband raster layer. Make sure the input raster has the appropriate bands available.
#
#     :param method_to_use: one of NDVI, GEMI, GVI, PVI, SAVI, MSAVI2, TSAVI, SULTAN.
#          the method used to create the vegetation index layer. The different vegetation indexes can help highlight
#          certain features, or help reduce various noise.
#
#         * GEMI - Global Environmental Monitoring Index - GEMI is a nonlinear vegetation index for global environmental
#             monitoring from satellite imagery. It is similar to NDVI, but it is less sensitive to atmospheric
#             effects. It is affected by bare soil; therefore, it is not recommended for use in areas of sparse or
#             moderately dense vegetation.
#         * GVI - Green Vegetation Index - Landsat TM - GVI was originally designed from Landsat MSS imagery but has been
#             modified for use with Landsat TM imagery. It is also known as the Landsat TM Tasseled Cap green
#             vegetation index. This monitoring index can also be used with imagery whose bands share the same
#             spectral characteristics.
#         * MSAVI2 - Modified Soil Adjusted Vegetation Index - MSAVI2 is a vegetation index that tries to minimize bare soil
#             influences of the SAVI method.
#         * NDVI - Normalized Difference Vegetation Index - NDVI is a standardized index allowing you to generate an image
#             displaying greenness, relative biomass. This index takes advantage of the contrast of the
#             characteristics of two bands from a multispectral raster dataset; the chlorophyll pigment absorptions
#             in the red band and the high reflectivity of plant materials in the near-infrared (NIR) band.
#         * PVI - Perpendicular Vegetation Index - PVI is similar to a difference vegetation index; however, it is sensitive
#             to atmospheric variations. When using this method to compare different images, it should only be used on
#             images that have been atmospherically corrected. This information can be provided by your data vendor.
#         * SAVI - Soil-Adjusted Vegetation Index - SAVI is a vegetation index that attempts to minimize soil brightness
#             influences using a soil-brightness correction factor. This is often used in arid regions where
#             vegetative cover is low.
#         * SULTAN - Sultan's Formula - The Sultan's Formula process takes a six-band 8-bit image and applied a specific
#             algorithm to it to produce a three-band 8-bit image. The resulting image highlights rock formations
#             called ophiolites on coastlines. This formula was designed based on the TM and ETM bands of a Landsat 5
#             or 7 scene.
#         * TSAVI - Transformed Soil-Adjusted Vegetation Index - Transformed-SAVI is a vegetation index that attempts to
#             minimize soil brightness influences by assuming the soil line has an arbitrary slope and intercept.
#
#     :param nir_band: the band indexes for the near-infrared (NIR) band.
#     :param red_band: the band indexes for the Red band.
#     :param options: additional parameters such as slope, intercept
#         * intercept is the value of near infrared (NIR) when the reflection value of the red (Red) band is 0 for the particular soil lines.
#         (a = NIR - sRed) , when Red is 0.
#         This parameter is only valid for Transformed Soil-Adjusted Vegetation Index.
#
#         * slope - Slope of soil line
#         The slope of the soil line. The slope is the approximate linear relationship between the NIR and red bands on a scatterplot.
#         This parameter is only valid for Transformed Soil-Adjusted Vegetation Index.
#
#         *
#     :param output_name:
#     :param gis:
#     :return:
#     """
#     NDVI
#     {"rasterFunction": "BandArithmetic", "rasterFunctionArguments": {"Method": 1, "BandIndexes": "1 2"}}
#
#     GEMI
#     {"rasterFunction": "BandArithmetic", "rasterFunctionArguments": {"Method": 5, "BandIndexes": "1 2 3 4 5 6"}}
#
#     GVI
#     {"rasterFunction": "BandArithmetic", "rasterFunctionArguments": {"Method": 7, "BandIndexes": "1 2"}}
#
#     MSAVI
#     {"rasterFunction": "BandArithmetic", "rasterFunctionArguments": {"Method": 4, "BandIndexes": "1 2"}}
#
#     PVI
#     {"rasterFunction": "BandArithmetic", "rasterFunctionArguments": {"Method": 6, "BandIndexes": "1 2 111 222"}}
#
#     SAVI
#     {"rasterFunction": "BandArithmetic", "rasterFunctionArguments": {"Method": 2, "BandIndexes": "1 2 111"}}
#
#     SULTAN
#     {"rasterFunction": "BandArithmetic", "rasterFunctionArguments": {"Method": 8, "BandIndexes": "1 2 3 4 5 6"}}
#
#     TSAVI
#     {"rasterFunction": "BandArithmetic", "rasterFunctionArguments": {"Method": 3, "BandIndexes": "1 2 111 222 333"}}
#
#     raster_function = {"rasterFunction":"BandArithmetic","rasterFunctionArguments":{"Method":1,"BandIndexes":"1 2"}}
#
#     function_args = {'Raster': _layer_input(input_raster)}
#
#     return generate_raster(raster_function, function_args, output_name=output_name, gis=gis)

def generate_raster(raster_function,
                    function_arguments=None,
                    output_raster_properties=None,
                    output_name=None,
                    *,
                    gis=None,
                    **kwargs):
    """


    Parameters
    ----------
    raster_function : Required, see http://resources.arcgis.com/en/help/rest/apiref/israsterfunctions.html

    function_arguments : Optional,  for specifying input Raster alone, portal Item can be passed

    output_raster_properties : Optional
    
    output_name : Optional. If not provided, an Image Service is created by the method and used as the output raster. 
        You can pass in an existing Image Service Item from your GIS to use that instead.

        Alternatively, you can pass in the name of the output Image Service that should be created by this method to be
        used as the output for the tool.

        A RuntimeError is raised if a service by that name already exists

    gis: Optional, the GIS on which this tool runs. If not specified, the active GIS is used.


    Returns
    -------
    output_raster : Image layer item
    """

    task = "GenerateRaster"

    gis = _arcgis.env.active_gis if gis is None else gis
    url = gis.properties.helperServices.rasterAnalytics.url
    gptool = _arcgis.gis._GISResource(url, gis)

    output_raster, output_service = _set_output_raster(output_name, task, gis, kwargs)

    if isinstance(function_arguments, _arcgis.gis.Item):
        if function_arguments.type.lower() == 'image service':
            function_arguments = {"Raster": {"itemId": function_arguments.itemid}}
        else:
            raise TypeError("The item type of function_arguments must be an image service")

    params = {}

    params["rasterFunction"] = raster_function

    params["outputName"] = output_raster
    if function_arguments is not None:
        params["functionArguments"] = function_arguments
    if output_raster_properties is not None:
        params["outputRasterProperties"] = output_raster_properties
    _set_context(params)

    task_url, job_info, job_id = _analysis_job(gptool, task, params)

    job_info = _analysis_job_status(gptool, task_url, job_info)
    job_values = _analysis_job_results(gptool, task_url, job_info, job_id)
    item_properties = {
        "properties": {
            "jobUrl": task_url + '/jobs/' + job_info['jobId'],
            "jobType": "GPServer",
            "jobId": job_info['jobId'],
            "jobStatus": "completed"
        }
    }
    output_service.update(item_properties)
    return output_service


def convert_feature_to_raster(input_feature,
                              output_cell_size,
                              value_field=None,
                              output_name=None,
                              *,
                              gis=None,
                              **kwargs):
    """
    Creates a new raster dataset from an existing feature dataset.
    Any feature class containing point, line, or polygon features can be converted to a raster dataset.
    The cell center is used to decide the value of the output raster pixel. The input field type determines
    the type of output raster. If the field is integer, the output raster will be integer;
    if it is floating point, the output will be floating point.

    Parameters
    ----------
    input_feature : Required. The input feature layer to convert to a raster dataset.

    output_cell_size : Required LinearUnit. The cell size and unit for the output rasters.
                       The available units are Feet, Miles, Meters, and Kilometers.
                       eg - {"distance":60,"units":meters}

    value_field : Optional string.  The field that will be used to assign values to the output raster.

    output_name : Optional. The name of the layer that will be created in My Content.
        If not provided, an Image Service is created by the method and used as the output raster.
        You can pass in an existing Image Service Item from your GIS to use that instead.
        Alternatively, you can pass in the name of the output Image Service that should be created by this method to be used as the output for the tool.
        A RuntimeError is raised if a service by that name already exists

    gis: Optional, the GIS on which this tool runs. If not specified, the active GIS is used.

    Returns
    -------
    output_raster : Image layer item 
    """

    task = "ConvertFeatureToRaster"

    gis = _arcgis.env.active_gis if gis is None else gis
    url = gis.properties.helperServices.rasterAnalytics.url
    gptool = _arcgis.gis._GISResource(url, gis)

    output_service = None

    output_raster, output_service = _set_output_raster(output_name, task, gis, kwargs)

    params = {}

    params["inputFeature"] = _layer_input(input_feature) 

    params["outputName"] = output_raster

    params["outputCellSize"] = output_cell_size
    if value_field is not None:
        params["valueField"] = value_field
    _set_context(params)

    task_url, job_info, job_id = _analysis_job(gptool, task, params)

    job_info = _analysis_job_status(gptool, task_url, job_info)
    job_values = _analysis_job_results(gptool, task_url, job_info, job_id)
    item_properties = {
        "properties": {
            "jobUrl": task_url + '/jobs/' + job_info['jobId'],
            "jobType": "GPServer",
            "jobId": job_info['jobId'],
            "jobStatus": "completed"
        }
    }
    output_service.update(item_properties)
    return output_service


def copy_raster(input_raster,
                output_cellsize=None,
                resampling_method="NEAREST",
                clip_setting=None,
                output_name=None,
                *,
                gis=None,
                **kwargs):
    """


    Parameters
    ----------
    input_raster : Required string

    output_cellsize : Optional string

    resampling_method : Optional string
        One of the following: ['NEAREST', 'BILINEAR', 'CUBIC', 'MAJORITY']
    clip_setting : Optional string

    output_name : Optional. If not provided, an Image Service is created by the method and used as the output raster.
        You can pass in an existing Image Service Item from your GIS to use that instead.
        Alternatively, you can pass in the name of the output Image Service that should be created by this method to be used as the output for the tool.
        A RuntimeError is raised if a service by that name already exists

    gis: Optional, the GIS on which this tool runs. If not specified, the active GIS is used.


    Returns
    -------
    output_raster : Image layer item 
    """

    task = "CopyRaster"

    gis = _arcgis.env.active_gis if gis is None else gis
    url = gis.properties.helperServices.rasterAnalytics.url
    gptool = _arcgis.gis._GISResource(url, gis)

    output_service = None

    output_raster, output_service = _set_output_raster(output_name, task, gis, kwargs)

    params = {}

    params["outputName"] = output_raster

    params["inputRaster"] = _layer_input(input_raster)

    if output_cellsize is not None:
        params["outputCellsize"] = output_cellsize
    if resampling_method is not None:
        params["resamplingMethod"] = resampling_method
    if clip_setting is not None:
        params["clipSetting"] = clip_setting
    _set_context(params)

    task_url, job_info, job_id = _analysis_job(gptool, task, params)

    job_info = _analysis_job_status(gptool, task_url, job_info)
    job_values = _analysis_job_results(gptool, task_url, job_info, job_id)
    item_properties = {
        "properties": {
            "jobUrl": task_url + '/jobs/' + job_info['jobId'],
            "jobType": "GPServer",
            "jobId": job_info['jobId'],
            "jobStatus": "completed"
        }
    }
    output_service.update(item_properties)
    return output_service


def summarize_raster_within(input_zone_layer,
                            input_raster_layer_to_summarize,
                            zone_field="Value",
                            statistic_type="Mean",
                            ignore_missing_values=True,
                            output_name=None,
                            *,
                            gis=None,
                            **kwargs):
    """


    Parameters
    ----------
    input_zone_layer : Required layer - area layer to summarize a raster layer within defined boundaries.
        The layer that defines the boundaries of the areas, or zones, that will be summarized.
        The layer can be a raster or feature data. For rasters, the zones are defined by all locations in the input that
        have the same cell value. The areas do not have to be contiguous.

    input_raster_layer_to_summarize : Required  - raster layer to summarize.
        The raster cells in this layer will be summarized by the areas (zones) that they fall within.

    zone_field : Required string -  field to define the boundaries. This is the attribute of the layer that will be used
        to define the boundaries of the areas. For example, suppose the first input layer defines the management unit
        boundaries, with attributes that define the region, the district, and the parcel ID of each unit. You also have
        a raster layer defining a biodiversity index for each location. With the field you select, you can decide to
        calculate the average biodiversity at local, district, or regional levels.

    statistic_type : Optional string - statistic to calculate.
        You can calculate statistics of any numerical attribute of the points, lines, or areas within the input area
        layer. The available statistics types when the selected field is integer are
        Mean, Maximum, Median, Minimum, Minority, Range, Standard deviation(STD), Sum, and Variety. If the field is
        floating point, the options are Mean, Maximum, Minimum, Range, Standard deviation, and Sum.
        One of the following:
        ['Mean', 'Majority', 'Maximum', 'Median', 'Minimum', 'Minority', 'Range', 'STD', 'SUM', 'Variety']

    ignore_missing_values : Optional bool.
        If you choose to ignore missing values, only the cells that have a value in the layer to be summarized will be
        used in determining the output value for that area. Otherwise, if there are missing values anywhere in an area,
        it is deemed that there is insufficient information to perform statistical calculations for all the cells in
        that zone, and that area will receive a null (NoData) value in the output.

    output_name : Optional. If not provided, an Image Service is created by the method and used as the output raster.
        You can pass in an existing Image Service Item from your GIS to use that instead.
        Alternatively, you can pass in the name of the output Image Service that should be created by this method to be used as the output for the tool.
        A RuntimeError is raised if a service by that name already exists

    gis: Optional, the GIS on which this tool runs. If not specified, the active GIS is used.


    Returns
    -------
    output_raster : Image layer item 
    """

    task = "SummarizeRasterWithin"

    gis = _arcgis.env.active_gis if gis is None else gis
    url = gis.properties.helperServices.rasterAnalytics.url
    gptool = _arcgis.gis._GISResource(url, gis)


    output_raster, output_service = _set_output_raster(output_name, task, gis, kwargs)

    params = {}

    #    _json.dumps({"serviceProperties": {"name" : output_name, "serviceUrl" : output_service.url}, "itemProperties": {"itemId" : output_service.itemid}}) 
    params["OutputName"] = output_raster


    params["inputZoneLayer"] = _layer_input(input_zone_layer)
    params["zoneField"] = zone_field
    params["inputRasterLayertoSummarize"] = _layer_input(input_raster_layer_to_summarize)

    if statistic_type is not None:
        params["statisticType"] = statistic_type
    if ignore_missing_values is not None:
        params["ignoreMissingValues"] = ignore_missing_values
    _set_context(params)

    task_url, job_info, job_id = _analysis_job(gptool, task, params)

    job_info = _analysis_job_status(gptool, task_url, job_info)
    job_values = _analysis_job_results(gptool, task_url, job_info, job_id)
    item_properties = {
        "properties": {
            "jobUrl": task_url + '/jobs/' + job_info['jobId'],
            "jobType": "GPServer",
            "jobId": job_info['jobId'],
            "jobStatus": "completed"
        }
    }
    output_service.update(item_properties)
    return output_service


def convert_raster_to_feature(input_raster,
                              field="Value",
                              output_type="Polygon",
                              simplify=True,
                              output_name=None,
                              *,
                              gis=None,
                              **kwargs):
    """
    This service tool converts imagery data to feature class vector data.

    Parameters
    ----------
    input_raster : Required. The input raster that will be converted to a feature dataset.

    field : Optional string - field that specifies which value will be used for the conversion.
        It can be any integer or a string field.
        A field containing floating-point values can only be used if the output is to a point dataset.
        Default is "Value"

    output_type : Optional string
        One of the following: ['Point', 'Line', 'Polygon']

    simplify : Optional bool, This option that specifies how the features should be smoothed. It is 
               only available for line and polygon output.
               True, then the features will be smoothed out. This is the default.
               if False, then The features will follow exactly the cell boundaries of the raster dataset.

    output_name : Optional. If not provided, an Feature layer is created by the method and used as the output .
        You can pass in an existing Feature Service Item from your GIS to use that instead.
        Alternatively, you can pass in the name of the output Feature Service that should be created by this method
        to be used as the output for the tool.
        A RuntimeError is raised if a service by that name already exists

    gis: Optional, the GIS on which this tool runs. If not specified, the active GIS is used.


    Returns
    -------
    output_features : Image layer item 
    """

    task = "ConvertRasterToFeature"

    gis = _arcgis.env.active_gis if gis is None else gis
    url = gis.properties.helperServices.rasterAnalytics.url
    gptool = _arcgis.gis._GISResource(url, gis)

    params = {}

    params["inputRaster"] = _layer_input(input_raster)

    if output_name is None:
        output_service_name = 'RasterToFeature_' + _id_generator()
        output_name = output_service_name.replace(' ', '_')
    else:
        output_service_name = output_name.replace(' ', '_')
    folderId = None
    folder = None
    if kwargs is not None:
        if "folder" in kwargs:
                folder = kwargs["folder"]
        if folder is not None:
            if isinstance(folder, dict):
                if "id" in folder:
                    folderId = folder["id"]
                    folder=folder["title"]
            else:
                owner = gis.properties.user.username
                folderId = gis._portal.get_folder_id(owner, folder)
            if folderId is None:
                folder_dict = gis.content.create_folder(folder, owner)
                folder = folder_dict["title"]
                folderId = folder_dict["id"]

    output_service = _create_output_feature_service(gis, output_name, output_service_name, 'Convert Raster To Feature', folder)

    if folderId is not None:
        params["outputName"] = _json.dumps({"serviceProperties": {"name": output_service_name, "serviceUrl": output_service.url},
                                       "itemProperties": {"itemId": output_service.itemid}, "folderId":folderId})
    else:
        params["outputName"] = _json.dumps({"serviceProperties": {"name": output_service_name, "serviceUrl": output_service.url},
                                       "itemProperties": {"itemId": output_service.itemid}})

    if field is not None:
        params["field"] = field
    if output_type is not None:
        params["outputType"] = output_type
    if simplify is not None:
        params["simplifyLinesOrPolygons"] = simplify
    _set_context(params)


    task_url, job_info, job_id = _analysis_job(gptool, task, params)

    job_info = _analysis_job_status(gptool, task_url, job_info)
    job_values = _analysis_job_results(gptool, task_url, job_info, job_id)
    item_properties = {
        "properties": {
            "jobUrl": task_url + '/jobs/' + job_info['jobId'],
            "jobType": "GPServer",
            "jobId": job_info['jobId'],
            "jobStatus": "completed"
        }
    }
    output_service.update(item_properties)
    return output_service

def calculate_density(input_point_or_line_features,
                      count_field=None,
                      search_distance=None,
                      output_area_units=None,
                      output_cell_size=None,
                      output_name=None,
                      *,
                      gis=None,
                      **kwargs):
    """
    Density analysis takes known quantities of some phenomenon and creates a density map by spreading
    these quantities across the map. You can use this tool, for example, to show concentrations of
    lightning strikes or tornadoes, access to health care facilities, and population densities.

    This tool creates a density map from point or line features by spreading known quantities of some
    phenomenon (represented as attributes of the points or lines) across the map. The result is a
    layer of areas classified from least dense to most dense.

    For point input, each point should represent the location of some event or incident, and the
    result layer represents a count of the incident per unit area. A larger density value in a new
    location means that there are more points near that location. In many cases, the result layer can
    be interpreted as a risk surface for future events. For example, if the input points represent
    locations of lightning strikes, the result layer can be interpreted as a risk surface for future
    lightning strikes.

    For line input, the line density surface represents the total amount of line that is near each
    location. The units of the calculated density values are the length of line-per-unit area.
    For example, if the lines represent rivers, the result layer will represent the total length
    of rivers that are within the search radius. This result can be used to identify areas that are
    hospitable to grazing animals.

    Other use cases of this tool include the following:

    *   Creating crime density maps to help police departments properly allocate resources to high crime
        areas.
    *   Calculating densities of hospitals within a county. The result layer will show areas with
        high and low accessibility to hospitals, and this information can be used to decide where
        new hospitals should be built.
    *   Identifying areas that are at high risk of forest fires based on historical locations of
        forest fires.
    *   Locating communities that are far from major highways in order to plan where new roads should
        be constructed.

    Parameters
    ----------
    input_point_or_line_features : Required feature layer - The input point or line layer that will be used to calculate
        the density layer.

    count_field : Optional string - count field
        Provide a field specifying the number of incidents at each location. For example, if you have points that
        represent cities, you can use a field representing the population of the city as the count field, and the
        resulting population density layer will calculate larger population densities near cities with
        larger populations. If the default choice of None is used, then each location will be assumed to represent a
        single count.

    search_distance : Optional LinearUnit - Search distance
        Enter a distance specifying how far to search to find point or line features when calculating density values.
        For example, if you provide a search distance of 10,000 meters, the density of any location in the output layer
        is calculated based on features that are within 10,000 meters of the location. Any location that does not have
        any incidents within 10,000 meters will receive a density value of zero.
        If no distance is provided, a default will be calculated that is based on the locations of the input features
        and the values in the count field (if a count field is provided).

    output_area_units : Optional string - Output area units
        Specify the output area unit. Density is count divided by area, and this parameter specifies the unit of the
        area in the density calculation. The available areal units are Square Miles and Square Kilometers.

    output_cell_size : Optional LinearUnit - Output cell size
        Enter the cell size and unit for the output rasters.

    output_name : Optional. If not provided, an Image Service is created by the method and used as the output raster.
        You can pass in an existing Image Service Item from your GIS to use that instead.
        Alternatively, you can pass in the name of the output Image Service that should be created by this method to be used as the output for the tool.
        A RuntimeError is raised if a service by that name already exists

    gis: Optional, the GIS on which this tool runs. If not specified, the active GIS is used.


    Returns
    -------
    output_raster : Image layer item 
    """

    task = "CalculateDensity"

    gis = _arcgis.env.active_gis if gis is None else gis
    url = gis.properties.helperServices.rasterAnalytics.url
    gptool = _arcgis.gis._GISResource(url, gis)

    output_raster, output_service = _set_output_raster(output_name, task, gis, kwargs)

    params = {}

    params["outputName"] = output_raster


    params["inputPointOrLineFeatures"] = _layer_input(input_point_or_line_features)

    if count_field is not None:
        params["countField"] = count_field
    if search_distance is not None:
        params["searchDistance"] = search_distance
    if output_area_units is not None:
        params["outputAreaUnits"] = output_area_units
    if output_cell_size is not None:
        params["outputCellSize"] = output_cell_size
    _set_context(params)


    task_url, job_info, job_id = _analysis_job(gptool, task, params)

    job_info = _analysis_job_status(gptool, task_url, job_info)
    job_values = _analysis_job_results(gptool, task_url, job_info, job_id)
    item_properties = {
        "properties": {
            "jobUrl": task_url + '/jobs/' + job_info['jobId'],
            "jobType": "GPServer",
            "jobId": job_info['jobId'],
            "jobStatus": "completed"
        }
    }
    output_service.update(item_properties)
    return output_service


def create_viewshed(input_elevation_surface,
                    input_observer_features,
                    optimize_for=None,
                    maximum_viewing_distance=None,
                    maximum_viewing_distance_field=None,
                    minimum_viewing_distance=None,
                    minimum_viewing_distance_field=None,
                    viewing_distance_is_3d=None,
                    observers_elevation=None,
                    observers_elevation_field=None,
                    observers_height=None,
                    observers_height_field=None,
                    target_height=None,
                    target_height_field=None,
                    above_ground_level_output_name=None,
                    output_name=None,
                    *,
                    gis=None,
                    **kwargs):
    """
    Compute visibility for an input elevation raster using geodesic method.

    Parameters
    ----------
    input_elevation_surface : Required string

    input_observer_features : Required FeatureSet

    optimize_for : Optional string
        One of the following: ['SPEED', 'ACCURACY']
    maximum_viewing_distance : Optional LinearUnit

    maximum_viewing_distance_field : Optional string

    minimum_viewing_distance : Optional LinearUnit

    minimum_viewing_distance_field : Optional string

    viewing_distance_is_3d : Optional bool

    observers_elevation : Optional LinearUnit

    observers_elevation_field : Optional string

    observers_height : Optional LinearUnit

    observers_height_field : Optional string

    target_height : Optional LinearUnit

    target_height_field : Optional string

    above_ground_level_output_name : Optional string

    output_name : Optional. If not provided, an Image Service is created by the method and used as the output raster.
        You can pass in an existing Image Service Item from your GIS to use that instead.
        Alternatively, you can pass in the name of the output Image Service that should be created by this method to be used as the output for the tool.
        A RuntimeError is raised if a service by that name already exists

    gis: Optional, the GIS on which this tool runs. If not specified, the active GIS is used.


    Returns
    -------
    dict with the following keys:
       "output_raster" : layer
       "output_above_ground_level_raster" : layer
    """

    task = "CreateViewshed"

    gis = _arcgis.env.active_gis if gis is None else gis
    url = gis.properties.helperServices.rasterAnalytics.url
    gptool = _arcgis.gis._GISResource(url, gis)
    return_value_names = ["output_raster"]

    output_raster, output_service = _set_output_raster(output_name, task, gis, kwargs)

    params = {}

    params["outputName"] = output_raster


    params["inputElevationSurface"] = _layer_input(input_elevation_surface)
    params["inputObserverFeatures"] = _layer_input(input_observer_features)

    if optimize_for is not None:
        params["optimizeFor"] = optimize_for
    if maximum_viewing_distance is not None:
        params["maximumViewingDistance"] = maximum_viewing_distance
    if maximum_viewing_distance_field is not None:
        params["maximumViewingDistanceField"] = maximum_viewing_distance_field
    if minimum_viewing_distance is not None:
        params["minimumViewingDistance"] = minimum_viewing_distance
    if minimum_viewing_distance_field is not None:
        params["minimumViewingDistanceField"] = minimum_viewing_distance_field
    if viewing_distance_is_3d is not None:
        params["viewingDistanceIs3D"] = viewing_distance_is_3d
    if observers_elevation is not None:
        params["observersElevation"] = observers_elevation
    if observers_elevation_field is not None:
        params["observersElevationField"] = observers_elevation_field
    if observers_height is not None:
        params["observersHeight"] = observers_height
    if observers_height_field is not None:
        params["observersHeightField"] = observers_height_field
    if target_height is not None:
        params["targetHeight"] = target_height
    if target_height_field is not None:
        params["targetHeightField"] = target_height_field
    if above_ground_level_output_name is not None:
        above_ground_level_raster, above_ground_level_service = _set_output_raster(above_ground_level_output_name, task, gis, kwargs)
        params["aboveGroundLevelOutputName"] = above_ground_level_raster
        return_value_names.extend(["output_above_ground_level_raster"])
    _set_context(params)


    task_url, job_info, job_id = _analysis_job(gptool, task, params)

    job_info = _analysis_job_status(gptool, task_url, job_info)
    job_values = _analysis_job_results(gptool, task_url, job_info, job_id)
    
    item_properties = {
        "properties": {
            "jobUrl": task_url + '/jobs/' + job_info['jobId'],
            "jobType": "GPServer",
            "jobId": job_info['jobId'],
            "jobStatus": "completed"
        }
    }
    output_service.update(item_properties)
    outputs = {"output_raster" : output_service}
    if above_ground_level_output_name is not None:
        above_ground_level_service.update(item_properties)
        outputs.update({"output_above_ground_level_raster" : above_ground_level_service})

    num_returns = len(outputs)

    return _return_output(num_returns,outputs,return_value_names)


def interpolate_points(input_point_features,
                       interpolate_field,
                       optimize_for="BALANCE",
                       transform_data=False,
                       size_of_local_models=None,
                       number_of_neighbors=None,
                       output_cell_size=None,
                       output_prediction_error=False,
                       output_name=None,
                       *,
                       gis=None,
                       **kwargs):
    """
    This tool allows you to predict values at new locations based on measurements from a collection of points. The tool
    takes point data with values at each point and returns a raster of predicted values:

    * An air quality management district has sensors that measure pollution levels. Interpolate Points can be used to
        predict pollution levels at locations that don't have sensors, such as locations with at-risk populations-
        schools or hospitals, for example.
    * Predict heavy metal concentrations in crops based on samples taken from individual plants.
    * Predict soil nutrient levels (nitrogen, phosphorus, potassium, and so on) and other indicators (such as electrical
        conductivity) in order to study their relationships to crop yield and prescribe precise amounts of fertilizer
        for each location in the field.
    * Meteorological applications include prediction of temperatures, rainfall, and associated variables (such as acid
        rain).

    Parameters
    ----------
    input_point_features : Required point layer containing locations with known values
        The point layer that contains the points where the values have been measured.

    interpolate_field : Required string -  field to interpolate
        Choose the field whose values you wish to interpolate. The field must be numeric.

    optimize_for : Optional string - Choose your preference for speed versus accuracy.
        More accurate predictions take longer to calculate. This parameter alters the default values of several other
        parameters of Interpolate Points in order to optimize speed of calculation, accuracy of results, or a balance of
        the two. By default, the tool will optimize for balance.
        One of the following: ['SPEED', 'BALANCE', 'ACCURACY']

    transform_data : Optional bool - Choose whether to transform your data to the normal distribution.
        Interpolation is most accurate for data that follows a normal (bell-shaped) distribution. If your data does not
        appear to be normally distributed, you should perform a transformation.

    size_of_local_models : Optional int - Size of local models
        Interpolate Points works by building local interpolation models that are mixed together to create the final
        prediction map. This parameter controls how many points will be contained in each local model. Smaller values
        will make results more local and can reveal small-scale effects, but it may introduce some instability in the
        calculations. Larger values will be more stable, but some local effects may be missed.
        The value can range from 30 to 500, but typical values are between 50 and 200.

    number_of_neighbors : Optional int - Number of Neighbors
        Predictions are calculated based on neighboring points. This parameter controls how many points will be used in
        the calculation. Using a larger number of neighbors will generally produce more accurate results, but the
        results take longer to calculate.
        This value can range from 1 to 64, but typical values are between 5 and 15.

    output_cell_size : Optional LinearUnit - Output cell size
        Enter the cell size and unit for the output rasters.
        The available units are Feet, Miles, Meters, and Kilometers.

    output_prediction_error : Optional bool - Output prediction error
        Choose whether you want to create a raster of standard errors for the predicted values.
        Standard errors are useful because they provide information about the reliability of the predicted values.
        A simple rule of thumb is that the true value will fall within two standard errors of the predicted value 95
        percent of the time. For example, suppose a new location gets a predicted value of 50 with a standard error of
        5. This means that this tool's best guess is that the true value at that location is 50, but it reasonably could
        be as low as 40 or as high as 60. To calculate this range of reasonable values, multiply the standard error by
        2, add this value to the predicted value to get the upper end of the range, and subtract it from the predicted
        value to get the lower end of the range.

    output_name : Optional. If not provided, an Image Service is created by the method and used as the output raster.
        You can pass in an existing Image Service Item from your GIS to use that instead.
        Alternatively, you can pass in the name of the output Image Service that should be created by this method to be used as the output for the tool.
        A RuntimeError is raised if a service by that name already exists

    gis: Optional, the GIS on which this tool runs. If not specified, the active GIS is used.


    Returns
    -------
    named tuple with name values being :

     - output_raster (the output_raster item description is updated with the process_info),

     - process_info (if run in a non-Jupyter environment, use process_info.data to get the HTML data) and 

     - output_error_raster (if output_prediction_error is set to True).   
    
    """

    task = "InterpolatePoints"

    gis = _arcgis.env.active_gis if gis is None else gis
    url = gis.properties.helperServices.rasterAnalytics.url
    gptool = _arcgis.gis._GISResource(url, gis)
    return_value_names = ["output_raster"]
    output_raster, output_service = _set_output_raster(output_name, task, gis, kwargs)

    params = {}

    params["outputName"] = output_raster


    params["inputPointFeatures"] = _layer_input(input_point_features)
    params["interpolateField"] = interpolate_field

    if optimize_for is not None:
        params["optimizeFor"] = optimize_for
    if transform_data is not None:
        params["transformData"] = transform_data
    if size_of_local_models is not None:
        params["sizeOfLocalModels"] = size_of_local_models
    if number_of_neighbors is not None:
        params["numberOfNeighbors"] = number_of_neighbors
    if output_cell_size is not None:
        params["outputCellSize"] = output_cell_size
    if output_prediction_error is not None:
        params["outputPredictionError"] = output_prediction_error
    _set_context(params)


    task_url, job_info, job_id = _analysis_job(gptool, task, params)

    job_info = _analysis_job_status(gptool, task_url, job_info)
    job_values = _analysis_job_results(gptool, task_url, job_info, job_id)

    #return output_service

    output_raster = output_service

    output_error_raster = job_values['outputErrorRaster']

    process_info = job_values['processInfo']

    outputs={}

    if output_raster is not None:
        outputs.update({"output_raster":output_raster})

    if (output_error_raster is not None) and output_error_raster is not '':
        output_error_raster_item = gis.content.get(output_error_raster["itemId"])
        outputs.update({"output_error_raster":output_error_raster_item})
        return_value_names.extend(["output_error_raster"])

    if (process_info is not None) and process_info is not '':
        html_final="<b>The following table contains cross validation statistics:</b><br></br><table style='width: 250px;margin-left: 2.5em;'><tbody>"
        import json
        for row in process_info:
            temp_dict=json.loads(row)
            if isinstance(temp_dict["message"],list):
                html_final+="<tr><td>"+temp_dict["message"][0]+"</td><td style='float:right'>"+temp_dict["params"][temp_dict["message"][1].split("${")[1].split("}")[0]]+"</td></tr>"
        
        html_final+="</tbody></table><br></br>"
        from IPython.display import HTML
        process_info_html = HTML(html_final)
        outputs.update({"process_info":process_info_html})
        return_value_names.extend(["process_info"])

    num_returns = len(outputs)

    item_properties = {
        "properties": {
            "jobUrl": task_url + '/jobs/' + job_info['jobId'],
            "jobType": "GPServer",
            "jobId": job_info['jobId'],
            "jobStatus": "completed"
        },
        "description":html_final
    }
    output_service.update(item_properties)

    return _return_output(num_returns, outputs, return_value_names)


def classify(input_raster,
             input_classifier_definition,
             additional_input_raster=None,
             output_name=None,
             *,
             gis=None,
             **kwargs):
    """


    Parameters
    ----------
    input_raster : Required string

    input_classifier_definition : Required string

    additional_input_raster : Optional string

    output_name : Optional. If not provided, an Image Service is created by the method and used as the output raster.
        You can pass in an existing Image Service Item from your GIS to use that instead.
        Alternatively, you can pass in the name of the output Image Service that should be created by this method to be used as the output for the tool.
        A RuntimeError is raised if a service by that name already exists

    gis: Optional, the GIS on which this tool runs. If not specified, the active GIS is used.


    Returns
    -------
    output_raster : Image layer item 
    """

    task = "Classify"

    gis = _arcgis.env.active_gis if gis is None else gis
    url = gis.properties.helperServices.rasterAnalytics.url
    gptool = _arcgis.gis._GISResource(url, gis)

    output_raster, output_service = _set_output_raster(output_name, task, gis, kwargs)

    params = {}

    params["outputName"] = output_raster


    params["inputRaster"] = _layer_input(input_raster)
    params["inputClassifierDefinition"] = input_classifier_definition

    if additional_input_raster is not None:
        params["additionalInputRaster"] = _layer_input(additional_input_raster)

    task_url, job_info, job_id = _analysis_job(gptool, task, params)

    job_info = _analysis_job_status(gptool, task_url, job_info)
    job_values = _analysis_job_results(gptool, task_url, job_info, job_id)
    item_properties = {
        "properties": {
            "jobUrl": task_url + '/jobs/' + job_info['jobId'],
            "jobType": "GPServer",
            "jobId": job_info['jobId'],
            "jobStatus": "completed"
        }
    }
    output_service.update(item_properties)
    return output_service


def segment(input_raster, spectral_detail=15.5, spatial_detail=15, minimum_segment_size_in_pixels=20,
            band_indexes=[0,1,2], remove_tiling_artifacts=False, output_name=None,
            *, gis=None, **kwargs):

    """
    Groups together adjacent pixels having similar spectral and spatial characteristics into
    segments, known as objects.

    ================================     ====================================================================
    **Argument**                         **Description**
    --------------------------------     --------------------------------------------------------------------
    input_raster                         Required ImageryLayer object
    --------------------------------     --------------------------------------------------------------------
    spectral_detail                      Optional float. Default is 15.5.
                                         Set the level of importance given to the spectral differences of
                                         features in your imagery. Valid values range from 1.0 to 20.0. A high
                                         value is appropriate when you have features you want to classify
                                         separately but have somewhat similar spectral characteristics.
                                         Smaller values create spectrally smoother outputs.

                                         For example, setting a higher spectral detail value for a forested
                                         scene, will preserve greater discrimination between the different tree
                                         species, resulting in more segments.
    --------------------------------     --------------------------------------------------------------------
    spatial_detail                       Optional float. Default is 15.
                                         Set the level of importance given to the proximity between features
                                         in your imagery. Valid values range from 1 to 20. A high value is
                                         appropriate for a scene where your features of interest are small
                                         and clustered together. Smaller values create spatially smoother
                                         outputs.

                                         For example, in an urban scene, you could classify an impervious
                                         surface using a smaller spatial detail, or you could classify
                                         buildings and roads as separate classes using a higher spatial detail.
    --------------------------------     --------------------------------------------------------------------
    minimum_segment_size_in_pixels       Optional float. Default is 20.
                                         Merge segments smaller than this size with their best fitting
                                         neighbor segment. This is related to the minimum mapping unit for a
                                         mapping project. Units are in pixels.
    --------------------------------     --------------------------------------------------------------------
    band_indexes                         Optional List of integers. Default is [0,1,2]
                                         Define which 3 bands are used in segmentation. Choose the bands that
                                         visually discriminate your features of interest best.
    --------------------------------     --------------------------------------------------------------------
    remove_tiling_artifacts              Optional Bool. Default is False.
                                         If False, the tool will not run to remove tiling artifacts after
                                         segmentation. The result may seem blocky at some tiling boundaries.
    --------------------------------     --------------------------------------------------------------------
    output_name                          Optional String. If specified, an Imagery Layer of given name is
                                         created. Else, an Image Service is created by the method and used
                                         as the output raster. You can pass in an existing Image Service Item
                                         from your GIS to use that instead. Alternatively, you can pass in
                                         the name of the output Image Service that should be created by this
                                         method to be used as the output for the tool. A RuntimeError is raised
                                         if a service by that name already exists
    --------------------------------     --------------------------------------------------------------------
    gis                                  Optional GIS object. If not speficied, the currently active connection
                                         is used.
    ================================     ====================================================================

    :return:
       output_raster : Imagery Layer item
    """

    task = "Segment"

    gis = _arcgis.env.active_gis if gis is None else gis
    url = gis.properties.helperServices.rasterAnalytics.url
    gptool = _arcgis.gis._GISResource(url, gis)

    output_raster, output_service = _set_output_raster(output_name, task, gis, kwargs)

    params = {}

    params["outputName"] = output_raster


    params["inputRaster"] = _layer_input(input_raster)

    if isinstance(spectral_detail, (float, int)):
        spectral_detail = str(spectral_detail)
    params["spectralDetail"] = spectral_detail

    if isinstance(spatial_detail, (float,int)):
        spatial_detail = str(spatial_detail)
    params["spatialDetail"] = spatial_detail

    if isinstance(minimum_segment_size_in_pixels, (float, int)):
        minimum_segment_size_in_pixels = str(minimum_segment_size_in_pixels)
    params["minimumSegmentSizeInPixels"] = minimum_segment_size_in_pixels

    if isinstance(band_indexes, (list, tuple)):
        band_indexes = ','.join(str(e) for e in band_indexes)
    params["bandIndexes"] = band_indexes

    if isinstance(remove_tiling_artifacts, bool):
        remove_tiling_artifacts = str(remove_tiling_artifacts).lower()
    params["removeTilingArtifacts"] = remove_tiling_artifacts

    task_url, job_info, job_id = _analysis_job(gptool, task, params)

    job_info = _analysis_job_status(gptool, task_url, job_info)
    job_values = _analysis_job_results(gptool, task_url, job_info, job_id)
    item_properties = {
        "properties": {
            "jobUrl": task_url + '/jobs/' + job_info['jobId'],
            "jobType": "GPServer",
            "jobId": job_info['jobId'],
            "jobStatus": "completed"
        }
    }
    output_service.update(item_properties)
    return output_service


def train_classifier(input_raster,
                     input_training_sample_json,
                     classifier_parameters,
                     segmented_raster=None,
                     segment_attributes="COLOR;MEAN",
                     *,
                     gis=None,
                     **kwargs):
    """


    Parameters
    ----------
    input_raster : Required string

    input_training_sample_json : Required string

    segmented_raster : Optional string

    classifier_parameters : Required string

    segment_attributes : Required string

    gis: Optional, the GIS on which this tool runs. If not specified, the active GIS is used.

    Returns
    -------
    output_classifier_definition
    """

    task = "TrainClassifier"

    gis = _arcgis.env.active_gis if gis is None else gis
    url = gis.properties.helperServices.rasterAnalytics.url
    gptool = _arcgis.gis._GISResource(url, gis)

    params = {}

    params["inputRaster"] = _layer_input(input_raster)
    params["inputTrainingSampleJSON"] = input_training_sample_json
    if segmented_raster is not None:
        params["segmentedRaster"] = _layer_input(segmented_raster)
    params["classifierParameters"] = classifier_parameters
    params["segmentAttributes"] = segment_attributes

    task_url, job_info, job_id = _analysis_job(gptool, task, params)

    job_info = _analysis_job_status(gptool, task_url, job_info)
    job_values = _analysis_job_results(gptool, task_url, job_info, job_id)
    # print(job_values)
    return job_values['outputClassifierDefinition']


###################################################################################################
## Create image collection
###################################################################################################
def create_image_collection(image_collection,
                            input_rasters, 
                            raster_type_name,
                            raster_type_params = None,
                            out_sr = None,
                            context = None,
                            *,
                            gis=None,
                            **kwargs):
                            
    """
    Create a collection of images that will participate in the ortho-mapping project.
    Provides provision to use input rasters by reference 
    and to specify image collection properties through context parameter.

    ==================                   ====================================================================
    **Argument**                         **Description**
    ------------------                   --------------------------------------------------------------------
    image_collection                     Required, the name of the image collection to create.
                  
                                         The image collection can be an existing image service, in 
                                         which the function will create a mosaic dataset and the existing 
                                         hosted image service will then point to the new mosaic dataset.

                                         If the image collection does not exist, a new multi-tenant
                                         service will be created.

                                         This parameter can be the Item representing an existing image_collection
                                         or it can be a string representing the name of the image_collection
                                         (either existing or to be created.)
    ------------------                   --------------------------------------------------------------------
    input_rasters                        Required, the list of input rasters to be added to
                                         the image collection being created. This parameter can
                                         be any one of the following:
                                         - List of portal Items of the images
                                         - An image service URL
                                         - Shared data path (this path must be accessible by the server)
                                         - Name of a folder on the portal
    ------------------                   --------------------------------------------------------------------
    raster_type_name                     Required, the name of the raster type to use for adding data to 
                                         the image collection.
    ------------------                   --------------------------------------------------------------------
    raster_type_params                   Optional,  additional raster_type specific parameters.
        
                                         The process of add rasters to the image collection can be
                                         controlled by specifying additional raster type arguments.

                                         The raster type parameters argument is a dictionary.
    ------------------                   --------------------------------------------------------------------
    out_sr                               Optional, additional parameters of the service.
                            
                                         The following additional parameters can be specified:
                                         - Spatial reference of the image_collection; The well-known ID of 
                                         the spatial reference or a spatial reference dictionary object for the 
                                         input geometries.
                                         If the raster type name is set to "UAV/UAS", the spatial reference of the
                                         output image collection will be determined by the raster type parameters defined.
    ------------------                   --------------------------------------------------------------------
    context                               Optional, The context parameter is used to provide additional input parameters
                                            {"image_collection_properties": {"imageCollectionType":"Satellite"},"byref":True}
                                            
                                            use image_collection_properties key to set value for imageCollectionType.
                                            Note: the "imageCollectionType" property is important for image collection that will later on be adjusted by orthomapping system service. 
                                            Based on the image collection type, the orthomapping system service will choose different algorithm for adjustment. 
                                            Therefore, if the image collection is created by reference, the requester should set this 
                                            property based on the type of images in the image collection using the following keywords. 
                                            If the imageCollectionType is not set, it defaults to "UAV/UAS"

                                            If byref is set to True, the data will not be uploaded. If it is not set, the default is False
    ------------------                   --------------------------------------------------------------------
    gis                                  Optional GIS. The GIS on which this tool runs. If not specified, the active GIS is used.
    ==================                   ====================================================================

    :return:
        The imagery layer item

    """

    gis = _arcgis.env.active_gis if gis is None else gis
    url = gis.properties.helperServices.rasterAnalytics.url
    gptool = _arcgis.gis._GISResource(url, gis)
    folder = None
    folderId = None

    params = {}
    image_collection_properties = None
    use_input_rasters_by_ref = None
    task = "CreateImageCollection"

    if context is not None:
        if "image_collection_properties" in context:
            image_collection_properties = context["image_collection_properties"]
            del context["image_collection_properties"]
        if "byref" in context:
            use_input_rasters_by_ref = context["byref"]
            del context["byref"]

    if isinstance(image_collection, Item):
        params["imageCollection"] = _json.dumps({"itemId": image_collection.itemid})
    elif isinstance(image_collection, str):
        if ("/") in image_collection or ("\\") in image_collection:
            if 'http:' in image_collection or 'https:' in image_collection:
                params['imageCollection'] = _json.dumps({ 'url' : image_collection })
            else:
                params['imageCollection'] = _json.dumps({ 'uri' : image_collection })
        else:
            result = gis.content.search("title:"+str(image_collection), item_type = "Imagery Layer")
            image_collection_result = None
            for element in result:
                if str(image_collection) == element.title:
                    image_collection_result = element
            if image_collection_result is not None:
                params["imageCollection"]= _json.dumps({"itemId": image_collection_result.itemid})
            else:
                doesnotexist = gis.content.is_service_name_available(image_collection, "Image Service") 
                if doesnotexist:
                    if kwargs is not None:
                        if "folder" in kwargs:
                            folder = kwargs["folder"]
                    if folder is not None:
                        if isinstance(folder, dict):
                            if "id" in folder:
                                folderId = folder["id"]
                                folder=folder["title"]
                        else:
                            owner = gis.properties.user.username
                            folderId = gis._portal.get_folder_id(owner, folder)
                        if folderId is None:
                            folder_dict = gis.content.create_folder(folder, owner)
                            folder = folder_dict["title"]
                            folderId = folder_dict["id"]
                        params["imageCollection"] =  _json.dumps({"serviceProperties": {"name" : image_collection}, "itemProperties": {"folderId" : folderId}})
                    else:
                        params["imageCollection"] = _json.dumps({"serviceProperties": {"name" : image_collection}})
                    
    _build_param_dictionary(gis, params, input_rasters, raster_type_name, raster_type_params, image_collection_properties, use_input_rasters_by_ref)

    # context

    if out_sr is not None:
        if isinstance(out_sr, int):
            if context is not None:
                context.update({'outSR':{'wkid': out_sr}})
            else:
                context = {}
                context["outSR"]={'wkid': out_sr}
        else:
            if context is not None:
                context.update({'outSR':out_sr})
            else:
                context = {}
                context["outSR"]=out_sr

    _set_context(params, context)

    # Create the task to execute   
    task_url, job_info, job_id = _analysis_job(gptool, task, params)

    job_info = _analysis_job_status(gptool, task_url, job_info)
    job_values = _analysis_job_results(gptool, task_url, job_info, job_id)
    item_properties = {
        "properties":{
            "jobUrl": task_url + '/jobs/' + job_info['jobId'],
            "jobType": "GPServer",
            "jobId": job_info['jobId'],
            "jobStatus": "completed"
            }
        }
    output_service= gis.content.get(job_values["result"]["itemId"])

    return  output_service


###################################################################################################
## Add image
###################################################################################################
def add_image(image_collection,
              input_rasters, 
              raster_type_name=None, 
              raster_type_params=None, 
              context = None,
              *,
              gis=None,
              **kwargs):
    """
    Add a collection of images to an existing image_collection. Provides provision to use input rasters by reference 
    and to specify image collection properties through context parameter.

    It can be used when new data is available to be included in the same 
    orthomapping project. When new data is added to the image collection
    the entire image collection must be reset to the original state.

    ==================                   ====================================================================
    **Argument**                         **Description**
    ------------------                   --------------------------------------------------------------------
    input_rasters                        Required, the list of input rasters to be added to
                                         the image collection being created. This parameter can
                                         be any one of the following:
                                         - List of portal Items of the images
                                         - An image service URL
                                         - Shared data path (this path must be accessible by the server)
                                         - Name of a folder on the portal
    ------------------                   --------------------------------------------------------------------
    image_collection                     Required, the item representing the image collection to add input_rasters to.
                  
                                         The image collection must be an existing image collection.
                                         This is the output image collection (mosaic dataset) item or url or uri
    ------------------                   --------------------------------------------------------------------
    raster_type_name                     Required, the name of the raster type to use for adding data to 
                                         the image collection.
    ------------------                   --------------------------------------------------------------------
    raster_type_params                   Optional,  additional raster_type specific parameters.
        
                                         The process of add rasters to the image collection can be
                                         controlled by specifying additional raster type arguments.

                                         The raster type parameters argument is a dictionary.
    ------------------                   --------------------------------------------------------------------
    context                               Optional, The context parameter is used to provide additional input parameters
                                            {"image_collection_properties": {"imageCollectionType":"Satellite"},"byref":True}
                                            
                                            use image_collection_properties key to set value for imageCollectionType.
                                            Note: the "imageCollectionType" property is important for image collection that will later on be adjusted by orthomapping system service. 
                                            Based on the image collection type, the orthomapping system service will choose different algorithm for adjustment. 
                                            Therefore, if the image collection is created by reference, the requester should set this 
                                            property based on the type of images in the image collection using the following keywords. 
                                            If the imageCollectionType is not set, it defaults to "UAV/UAS"

                                            If byref is set to True, the data will not be uploaded. If it is not set, the default is False
    ------------------                   --------------------------------------------------------------------
    gis                                  Optional GIS. The GIS on which this tool runs. If not specified, the active GIS is used.
    ==================                   ====================================================================

    :return:
        The imagery layer item

    """

    gis = _arcgis.env.active_gis if gis is None else gis
    url = gis.properties.helperServices.rasterAnalytics.url
    gptool = _arcgis.gis._GISResource(url, gis)

    params = {}
    image_collection_properties = None
    use_input_rasters_by_ref = None
    if context is not None:
        if "image_collection_properties" in context:
            image_collection_properties = context["image_collection_properties"]
            del context["image_collection_properties"]
        if "byref" in context:
            use_input_rasters_by_ref = context["byref"]
            del context["byref"]

    _set_image_collection_param(gis, params, image_collection)
    _build_param_dictionary(gis, params, input_rasters, raster_type_name, raster_type_params, image_collection_properties, use_input_rasters_by_ref)

    _set_context(params, context)

    # Create the task to execute
    task = 'AddImage'

    task_url, job_info, job_id = _analysis_job(gptool, task, params)

    job_info = _analysis_job_status(gptool, task_url, job_info)
    job_values = _analysis_job_results(gptool, task_url, job_info, job_id)
    item_properties = {
        "properties":{
            "jobUrl": task_url + '/jobs/' + job_info['jobId'],
            "jobType": "GPServer",
            "jobId": job_info['jobId'],
            "jobStatus": "completed"
            }
        }

    return job_values["result"]["url"]

###################################################################################################
## Delete image
###################################################################################################
def delete_image(image_collection, 
                 where, 
                 *,
                 gis=None,
                 **kwargs):
    """
    delete_image allows users to remove existing images from the image collection (mosaic dataset). 
    The function will only delete the raster item in the mosaic dataset and will not remove the
    source image.

    ==================     ====================================================================
    **Argument**           **Description**
    ------------------     --------------------------------------------------------------------
    image_collection       Required, the input image collection from which to delete images
                           This can be the 'itemID' of an exisiting portal item or a url
                           to an Image Service or a uri
    ------------------     --------------------------------------------------------------------
    where                  Required string,  a SQL 'where' clause for selecting the images 
                           to be deleted from the image collection
    ------------------     --------------------------------------------------------------------
    gis                    Optional GIS. The GIS on which this tool runs. If not specified, the active GIS is used.
    ==================     ====================================================================

    :return:
        The imagery layer url

    """

    gis = _arcgis.env.active_gis if gis is None else gis
    url = gis.properties.helperServices.rasterAnalytics.url
    gptool = _arcgis.gis._GISResource(url, gis)

    params = {}

    _set_image_collection_param(gis, params, image_collection)

    if where is not None:
        params['where'] = where

    task = "DeleteImage"
    task_url, job_info, job_id = _analysis_job(gptool, task, params)

    job_info = _analysis_job_status(gptool, task_url, job_info)
    job_values = _analysis_job_results(gptool, task_url, job_info, job_id)
    item_properties = {
        "properties":{
            "jobUrl": task_url + '/jobs/' + job_info['jobId'],
            "jobType": "GPServer",
            "jobId": job_info['jobId'],
            "jobStatus": "completed"
            }
        }

    return job_values["result"]["url"]


###################################################################################################
## Delete image collection
###################################################################################################
def delete_image_collection(image_collection,
                            *,
                            gis=None,
                            **kwargs):
    '''
    Delete the image collection. This service tool will delete the image collection
    image service, that is, the portal-hosted image layer item. It will not delete 
    the source images that the image collection references.

    ==================     ====================================================================
    **Argument**           **Description**
    ------------------     --------------------------------------------------------------------
    image_collection       Required, the input image collection to delete.

                           The image_collection can be a portal Item or an image service URL or a URI.
                            
                           The image_collection must exist.
    ------------------     --------------------------------------------------------------------
    gis                    Optional GIS. The GIS on which this tool runs. If not specified, the active GIS is used.
    ==================     ====================================================================

    :return:
        Boolean value indicating whether the deletion was successful or not

    '''

    gis = _arcgis.env.active_gis if gis is None else gis
    url = gis.properties.helperServices.rasterAnalytics.url
    gptool = _arcgis.gis._GISResource(url, gis)

    params = {}

    _set_image_collection_param(gis, params, image_collection)

    task = 'DeleteImageCollection'

    task_url, job_info, job_id = _analysis_job(gptool, task, params)

    job_info = _analysis_job_status(gptool, task_url, job_info)
    job_values = _analysis_job_results(gptool, task_url, job_info, job_id)
    item_properties = {
        "properties":{
            "jobUrl": task_url + '/jobs/' + job_info['jobId'],
            "jobType": "GPServer",
            "jobId": job_info['jobId'],
            "jobStatus": "completed"
            }
        }


    return job_values["result"]


def _flow_direction(input_surface_raster,
                   force_flow= False,
                   flow_direction_type= "D8",
                   output_flow_direction_name=None,
                   output_drop_name=None,
                   *,
                   gis=None,
                   **kwargs):
    """
    Replaces cells of a raster corresponding to a mask 
    with the values of the nearest neighbors.

    Parameters
    ----------
    input_surface_raster : The input raster representing a continuous surface.

    force_flow  : Boolean, Specifies if edge cells will always flow outward or follow normal flow rules.

    flow_direction_type : Specifies which flow direction type to use.
						  D8 - Use the D8 method. This is the default.
						  MFD - Use the Multi Flow Direction (MFD) method.
						  DINF - Use the D-Infinity method.

    output_drop_name : An optional output drop raster . 
					   The drop raster returns the ratio of the maximum change in elevation from each cell 
					   along the direction of flow to the path length between centers of cells, expressed in percentages.

    output_flow_direction_name : Optional. If not provided, an Image Service is created by the method and used as the output raster.
        You can pass in an existing Image Service Item from your GIS to use that instead.
        Alternatively, you can pass in the name of the output Image Service that should be created by this method to be used as the output for the tool.
        A RuntimeError is raised if a service by that name already exists

    gis: Optional, the GIS on which this tool runs. If not specified, the active GIS is used.

    Returns
    -------
    output_raster : Image layer item 
    """

    task = "FlowDirection"

    gis = _arcgis.env.active_gis if gis is None else gis
    url = gis.properties.helperServices.rasterAnalytics.url
    gptool = _arcgis.gis._GISResource(url, gis)
    return_value_names = ["output_flow_direction_service"]
    params = {}

    output_flow_direction_raster, output_flow_direction_service = _set_output_raster(output_flow_direction_name, task, gis, kwargs)  
    params["outputFlowDirectionName"] = output_flow_direction_raster 

    params["inputSurfaceRaster"] = _layer_input(input_surface_raster)
    
    if output_drop_name is not None:
        output_drop_raster, output_drop_service = _set_output_raster(output_drop_name, task, gis, kwargs) 
        params["outputDropName"] = output_drop_raster
        return_value_names.extend(["output_drop_service"])

    if force_flow is not None:
        if isinstance(force_flow, bool):
            params["forceFlow"] = force_flow
        elif isinstance(force_flow, str):
            if force_flow == "NORMAL":
                params["forceFlow"] = False
            elif force_flow == "FORCE":
                params["forceFlow"] = True
    
    flow_direction_type_AllowedValues= {"D8", "MFD", "DINF"}
    
    if not flow_direction_type in flow_direction_type_AllowedValues:
            raise RuntimeError('flow_direction_type can only be one of the following: '.join(flow_direction_type_AllowedValues))
    params["flowDirectionType"] = flow_direction_type
    
    _set_context(params)

    task_url, job_info, job_id = _analysis_job(gptool, task, params)    

    job_info = _analysis_job_status(gptool, task_url, job_info)
    job_values = _analysis_job_results(gptool, task_url, job_info)
    item_properties = {
        "properties": {
            "jobUrl": task_url + '/jobs/' + job_info['jobId'],
            "jobType": "GPServer",
            "jobId": job_info['jobId'],
            "jobStatus": "completed"
        }
    }
    output_flow_direction_service.update(item_properties)
    outputs = {"output_flow_direction_service" : output_flow_direction_service}
    if output_drop_name is not None:
        output_drop_service.update(item_properties)
        outputs.update({"output_drop_service" : output_drop_service})

    num_returns = len(outputs)

    return _return_output(num_returns,outputs,return_value_names)


def _calculate_travel_cost(input_source,
                          input_cost_raster=None,
                          input_surface_raster=None,
                          maximum_distance=None,
                          input_horizonal_raster=None,
                          horizontal_factor="BINARY",
                          input_vertical_raster=None,
                          vertical_factor="BINARY",
                          source_cost_multiplier=None,
                          source_start_cost=None,
                          source_resistance_rate=None,
                          source_capacity=None,
                          source_direction="FROM_SOURCE",
                          allocation_field=None,
                          output_distance_name=None,
                          output_backlink_name=None,
                          output_allocation_name=None,
                          *,
                          gis=None,
                          **kwargs):
    """

    Parameters
    ----------
    input_source : The layer that defines the sources to calculate the distance too. The layer 
				   can be raster or feature.

    input_cost_raster  : A raster defining the impedance or cost to move planimetrically through each cell.

    input_surface_raster : A raster defining the elevation values at each cell location.

    maximum_distance : The maximum distance to calculate out to. If no distance is provided, a default will 
	                   be calculated that is based on the locations of the input sources.

    input_horizonal_raster : A raster defining the horizontal direction at each cell.

    horizontal_factor : The Horizontal Factor defines the relationship between the horizontal cost 
						factor and the horizontal relative moving angle.

    input_vertical_raster : A raster defining the vertical (z) value for each cell.

    vertical_factor : The Vertical Factor defines the relationship between the vertical cost factor and 
					  the vertical relative moving angle (VRMA).

    source_cost_multiplier : Multiplier to apply to the cost values.

    source_start_cost : The starting cost from which to begin the cost calculations.

    source_resistance_rate : This parameter simulates the increase in the effort to overcome costs 
							as the accumulative cost increases.

    source_capacity : Defines the cost capacity for the traveler for a source.

    source_direction : Defines the direction of the traveler when applying horizontal and vertical factors, 
					   the source resistance rate, and the source starting cost.

    allocation_field : A field on theinputSourceRasterOrFeatures layer that holds the values that define each source.

    output_backlink_name  : This is the output image service name that will be created.

    output_allocation_name : This is the output image service name that will be created.

    output_distance_name : Optional. If not provided, an Image Service is created by the method and used as the output raster.
        You can pass in an existing Image Service Item from your GIS to use that instead.
        Alternatively, you can pass in the name of the output Image Service that should be created by this method to be used as the output for the tool.
        A RuntimeError is raised if a service by that name already exists

    gis: Optional, the GIS on which this tool runs. If not specified, the active GIS is used.

    Returns
    -------
    output_raster : Image layer item 
    """

    task = "CalculateTravelCost"

    gis = _arcgis.env.active_gis if gis is None else gis
    url = gis.properties.helperServices.rasterAnalytics.url
    gptool = _arcgis.gis._GISResource(url, gis)
    return_value_names = ["output_distance_service"]
    params = {}

    output_distance_raster, output_distance_service = _set_output_raster(output_distance_name, task, gis, kwargs)  
    params["outputDistanceName"] = output_distance_raster 

    if input_source is not None:
        params["inputSourceRasterOrFeatures"] = _layer_input(input_source)

    if input_cost_raster is not None:
        params["inputCostRaster"] = _layer_input(input_cost_raster)

    if input_surface_raster is not None:
        params["inputSurfaceRaster"] = _layer_input(input_surface_raster)

    if maximum_distance is not None:
        params["maximumDistance"] = maximum_distance

    if input_horizonal_raster is not None:
        params["inputHorizonalRaster"] = _layer_input(input_horizonal_raster)

    if horizontal_factor is not None:
        params["horizontalFactor"] = horizontal_factor

    if input_vertical_raster is not None:
        params["inputVerticalRaster"] = _layer_input(input_vertical_raster)

    if vertical_factor is not None:
        params["verticalFactor"] = vertical_factor

    if source_cost_multiplier is not None:
        params["sourceCostMultiplier"] = source_cost_multiplier

    if source_start_cost is not None:
        params["sourceStartCost"] = source_start_cost

    if source_resistance_rate is not None:
        params["sourceResistanceRate"] = source_resistance_rate

    if source_capacity is not None:
        params["sourceCapacity"] = source_capacity

    if source_direction is not None:
        params["sourceDirection"] = source_direction

    if allocation_field is not None:
        params["allocationField"] = allocation_field

    if output_backlink_name is not None:
        #output_backlink_service = None
        #if isinstance(output_backlink_name, str):
        #    output_backlink_service = _create_output_image_service(gis, output_backlink_name, task)
        #elif isinstance(output_backlink_name, _arcgis.gis.Item):
        #    output_backlink_service = output_backlink_name
        #else:
        #    raise TypeError("output_backlink_name should be a string (service name) or Item")
        
        #output_backlink_raster = _json.dumps({"serviceProperties": {"name" : output_backlink_name, "serviceUrl" : output_backlink_service.url}, "itemProperties": {"itemId" : output_backlink_service.itemid}}) 
        #output_backlink_raster = _json.dumps({"serviceProperties": {"name" : output_backlink_name}})
        output_backlink_raster, output_backlink_service = _set_output_raster(output_backlink_name, task, gis, kwargs)
        params["outputBacklinkName"] = output_backlink_raster
        return_value_names.extend(["output_backlink_service"])

    if output_allocation_name is not None:
        #output_allocation_service = None
        #if isinstance(output_allocation_name, str):
        #    output_allocation_service = _create_output_image_service(gis, output_allocation_name, task)
        #elif isinstance(output_allocation_name, _arcgis.gis.Item):
        #    output_allocation_service = output_allocation_name
        #else:
        #    raise TypeError("output_allocation_name should be a string (service name) or Item")
        
        #output_allocation_raster = _json.dumps({"serviceProperties": {"name" : output_allocation_name, "serviceUrl" : output_allocation_service.url}, "itemProperties": {"itemId" : output_allocation_service.itemid}}) 
        output_allocation_raster, out_allocation_service = _set_output_raster(output_allocation_name, task, gis, kwargs) 
        params["outputAllocationName"] = output_allocation_raster
        return_value_names.extend(["output_allocation_service"])

    _set_context(params)

    task_url, job_info, job_id = _analysis_job(gptool, task, params)

    job_info = _analysis_job_status(gptool, task_url, job_info)
    job_values = _analysis_job_results(gptool, task_url, job_info)
    item_properties = {
        "properties": {
            "jobUrl": task_url + '/jobs/' + job_info['jobId'],
            "jobType": "GPServer",
            "jobId": job_info['jobId'],
            "jobStatus": "completed"
        }
    }
    output_distance_service.update(item_properties)
    outputs={"output_distance_service" : output_distance_service}
    if output_backlink_name is not None:
       output_backlink_service.update(item_properties)
       outputs.update({"output_backlink_service":output_backlink_service})
    if output_allocation_name is not None:
       out_allocation_service.update(item_properties)
       outputs.update({"output_allocation_service" : out_allocation_service})
    num_returns = len(outputs)

    return _return_output(num_returns, outputs, return_value_names)


def optimum_travel_cost_network(input_regions_raster,
                                input_cost_raster,
                                output_optimum_network_name=None,
                                output_neighbor_network_name=None,
                                context=None,
                                *,
                                gis=None,
                                **kwargs):

    """
    calculates the optimum cost network from a set of input regions.

    Parameters
    ----------
    input_regions_raster : The layer that defines the regions to find the optimum travel cost netork for. 
						   The layer can be raster or feature.

    input_cost_raster  : A raster defining the impedance or cost to move planimetrically through each cell.

    output_optimum_network_name : Optional. If not provided, a feature layer is created by the method and used as the output.
        You can pass in an existing feature layer Item from your GIS to use that instead.
        Alternatively, you can pass in the name of the output feature layer  that should be created by this method to be used as the output for the tool.
        A RuntimeError is raised if a service by that name already exists

    output_neighbor_network_name : Optional. This is the name of the output neighbour network feature layer that will be created.

	context: Context contains additional settings that affect task execution.

    gis: Optional, the GIS on which this tool runs. If not specified, the active GIS is used.

    Returns
    -------
    output_raster : Image layer item 
    """

    task = "DetermineOptimumTravelCostNetwork"

    gis = _arcgis.env.active_gis if gis is None else gis
    url = gis.properties.helperServices.rasterAnalytics.url
    gptool = _arcgis.gis._GISResource(url, gis)


    return_value_names=["output_optimum_network_service"]
    params = {}

    if output_optimum_network_name is None:
        output_optimum_network_service_name = 'Optimum Network Raster_' + _id_generator()
        output_optimum_network_name = output_optimum_network_service_name.replace(' ', '_')
    else:
        output_optimum_network_service_name = output_optimum_network_name.replace(' ', '_')

    folder = None
    folderId = None
    if kwargs is not None:
        if "folder" in kwargs:
                folder = kwargs["folder"]
        if folder is not None:
            if isinstance(folder, dict):
                if "id" in folder:
                    folderId = folder["id"]
                    folder=folder["title"]
            else:
                owner = gis.properties.user.username
                folderId = gis._portal.get_folder_id(owner, folder)
            if folderId is None:
                folder_dict = gis.content.create_folder(folder, owner)
                folder = folder_dict["title"]
                folderId = folder_dict["id"]

    output_optimum_network_service = _create_output_feature_service(gis, output_optimum_network_name, output_optimum_network_service_name, 'DetermineOptimumTravelCostNetwork', folder)

    if folderId is not None:
        params["outputOptimumNetworkName"] = _json.dumps({"serviceProperties": {"name": output_optimum_network_service_name, "serviceUrl": output_optimum_network_service.url},
                                       "itemProperties": {"itemId": output_optimum_network_service.itemid}, "folderId":folderId})
    else:
        params["outputOptimumNetworkName"] = _json.dumps({"serviceProperties": {"name": output_optimum_network_service_name, "serviceUrl": output_optimum_network_service.url},
                                       "itemProperties": {"itemId": output_optimum_network_service.itemid}})


    params["inputRegionsRasterOrFeatures"] = _layer_input(input_regions_raster)
    #primary output end

    if input_cost_raster is not None:
        params["inputCostRaster"] = _layer_input(input_cost_raster)

    #secondary output start
    if output_neighbor_network_name is None:
        output_neighbor_network_service_name = 'Neighbor Network Raster_' + _id_generator()
        output_neighbor_network_name = output_neighbor_network_service_name.replace(' ', '_')
    else:
        output_neighbor_network_service_name = output_neighbor_network_name.replace(' ', '_')

    

    output_neighbor_network_service = _create_output_feature_service(gis, output_neighbor_network_name, 
                                                                     output_neighbor_network_service_name, 
                                                                     'DetermineOptimumTravelCostNetwork', folder) 

    if folderId is not None:
        params["outputNeighborNetworkName"] = _json.dumps({"serviceProperties": {"name": output_neighbor_network_service_name, "serviceUrl": output_neighbor_network_service.url},
                                       "itemProperties": {"itemId": output_neighbor_network_service.itemid}, "folderId":folderId})
    else:
        params["outputNeighborNetworkName"] = _json.dumps({"serviceProperties": {"name": output_neighbor_network_service_name, 
                                                                             "serviceUrl": output_neighbor_network_service.url},
                                                                             "itemProperties": {"itemId": output_neighbor_network_service.itemid}})
    return_value_names.extend(["output_neighbor_network_service"])
    _set_context(params)

    task_url, job_info, job_id = _analysis_job(gptool, task, params)

    job_info = _analysis_job_status(gptool, task_url, job_info)
    job_values = _analysis_job_results(gptool, task_url, job_info)
    item_properties = {
        "properties": {
            "jobUrl": task_url + '/jobs/' + job_info['jobId'],
            "jobType": "GPServer",
            "jobId": job_info['jobId'],
            "jobStatus": "completed"
        }
    }
    output_optimum_network_service.update(item_properties)
    outputs={"output_optimum_network_service" : output_optimum_network_service}
    if output_neighbor_network_name is not None:
        output_neighbor_network_service.update(item_properties)
        outputs.update({"output_neighbor_network_service":output_neighbor_network_service})

    num_returns = len(outputs)

    return _return_output(num_returns, outputs, return_value_names)


def list_datastore_content(datastore, filter=None, *, gis=None, **kwargs):
    """
    List the contents of the datastore registered with the server (fileShares, cloudStores, rasterStores).

    ==================     ====================================================================
    **Argument**           **Description**
    ------------------     --------------------------------------------------------------------
    datastore              Required. fileshare, rasterstore or cloudstore datastore from which the contents are to be listed. 
                           It can be a string specifying the datastore path eg "/fileShares/SensorData", "/cloudStores/testcloud",
                           "/rasterStores/rasterstore"
                           or it can be a Datastore object containing a fileshare, rasterstore  or a cloudstore path.
                           eg:
                           ds=analytics.get_datastores()
                           ds_items =ds.search()
                           ds_items[1]
                           ds_items[1] may be specified as input for datastore 
    ------------------     --------------------------------------------------------------------
    filter                 Optional. To filter out the raster contents to be displayed
    ------------------     --------------------------------------------------------------------
    gis                    Optional GIS. The GIS on which this tool runs. If not specified, the active GIS is used.
    ==================     ====================================================================

    :return:
        List of contents in the datastore
    """

    task = "ListDatastoreContent"

    gis = _arcgis.env.active_gis if gis is None else gis
    url = gis.properties.helperServices.rasterAnalytics.url
    gptool = _arcgis.gis._GISResource(url, gis)

    params = {}

    if isinstance(datastore,_arcgis.gis.Datastore):
        params["dataStoreName"] = datastore.datapath
    else:
        params["dataStoreName"] = datastore

    if filter is not None:
        params["filter"] = filter

    task_url, job_info, job_id = _analysis_job(gptool, task, params)

    job_info = _analysis_job_status(gptool, task_url, job_info)
    job_values = _analysis_job_results(gptool, task_url, job_info, job_id)
    if job_values["contentList"] is "":
        return None
    return _json.loads(job_values["contentList"]["contentList"])

def build_footprints(image_collection,
                     computation_method="RADIOMETRY",
                     value_range=None,
                     context=None,
                     *,
                     gis=None,
                     **kwargs):
    """

    Computes the extent of every raster in a mosaic dataset. 

    Parameters
    ----------
    image_collection : Required. The input image collection.The image_collection can be a 
                       portal Item or an image service URL or a URI.
                       The image_collection must exist.

    computation_method : Optional. Refine the footprints using one of the following methods: 
                         RADIOMETRY, GEOMETRY
                         Default: RADIOMETRY

    value_range: Optional. Parameter to specify the value range.

    context : Optional dictionary. Can be used to specify values for keys like:
              whereClause, minValue, maxValue, numVertices, shrinkDistance, maintainEdge,
              skipDerivedImages, updateBoundary, requestSize, minRegionSize, simplification,
              edgeTorelance, maxSliverSize, minThinnessRatio

    gis: Optional, the GIS on which this tool runs. If not specified, the active GIS is used.

    Returns
    -------
    output_raster : Image layer item 
    """

    task = "BuildFootprints"

    gis = _arcgis.env.active_gis if gis is None else gis
    url = gis.properties.helperServices.rasterAnalytics.url
    gptool = _arcgis.gis._GISResource(url, gis)

    params = {}

    _set_image_collection_param(gis, params, image_collection)

    computation_method_values = ["RADIOMETRY","GEOMETRY"]
    if not computation_method.upper() in computation_method_values:
        raise RuntimeError("computation_method can only be one of the following: RADIOMETRY, GEOMETRY")

    params["computationMethod"] = computation_method

    if value_range is not None:
        params["valueRange"] = value_range
    
    _set_context(params, context)

    task_url, job_info, job_id = _analysis_job(gptool, task, params)

    job_info = _analysis_job_status(gptool, task_url, job_info)
    job_values = _analysis_job_results(gptool, task_url, job_info, job_id)

    return job_values["outCollection"]["url"]


def build_overview(image_collection,
                   cell_size=None,
                   context=None,
                    *,
                    gis=None,
                    **kwargs):
    """

    Parameters
    ----------
    image_collection : Required. The input image collection.The image_collection can be a 
                       portal Item or an image service URL or a URI.
                       The image_collection must exist.

    cell_size : optional float or int, to set the cell size for overview.

    context : optional dictionary

    gis: Optional, the GIS on which this tool runs. If not specified, the active GIS is used.

    Returns
    -------
    output_raster : Image layer item 
    """

    task = "BuildOverview"

    gis = _arcgis.env.active_gis if gis is None else gis
    url = gis.properties.helperServices.rasterAnalytics.url
    gptool = _arcgis.gis._GISResource(url, gis)

    params = {}

    _set_image_collection_param(gis, params, image_collection)

    if cell_size is not None:
        params["cellSize"] = cell_size
    
    _set_context(params, context)

    task_url, job_info, job_id = _analysis_job(gptool, task, params)

    job_info = _analysis_job_status(gptool, task_url, job_info)
    job_values = _analysis_job_results(gptool, task_url, job_info, job_id)

    return job_values["outCollection"]["url"]


def calculate_statistics(image_collection,
                         skip_factors=None,
                         context=None,
                          *,
                          gis=None,
                          **kwargs):
    """
    Calculates statistics for an image collection

    Parameters
    ----------
    image_collection : Required. The input image collection.The image_collection can be a 
                       portal Item or an image service URL or a URI.
                       The image_collection must exist.

    skip_factors : optional dictionary, Controls the portion of the raster that is used when calculating the statistics.
                    eg: {"x":5,"y":5} x value represents - the number of horizontal pixels between samples
                                      y value represents - the number of vertical pixels between samples.

    context : optional dictionary. Can be used to specify parameters for calculating statistics. Keys can be 
             ignoreValues, skipExisting, areaOfInterest

    gis: Optional, the GIS on which this tool runs. If not specified, the active GIS is used.

    Returns
    -------
    output_raster : Image layer item 
    """

    task = "CalculateStatistics"

    gis = _arcgis.env.active_gis if gis is None else gis
    url = gis.properties.helperServices.rasterAnalytics.url
    gptool = _arcgis.gis._GISResource(url, gis)

    params = {}

    _set_image_collection_param(gis, params, image_collection)

    if skip_factors is not None:
        params["skipfactors"] = skip_factors
    
    _set_context(params, context)

    task_url, job_info, job_id = _analysis_job(gptool, task, params)

    job_info = _analysis_job_status(gptool, task_url, job_info)
    job_values = _analysis_job_results(gptool, task_url, job_info, job_id)

    return job_values["outCollection"]["url"]


def determine_travel_costpath_as_polyline(input_source_data,
                                          input_cost_raster,
                                          input_destination_data,
                                          path_type='BEST_SINGLE',
                                          output_polyline_name=None,
                                          *,
                                          gis=None,
                                          **kwargs):

    '''
    Calculates the least cost polyline path between sources and known destinations.

    ====================================     ====================================================================
    **Argument**                             **Description**
    ------------------------------------     --------------------------------------------------------------------
    input_source_data                        The layer that identifies the cells to determine the least 
                                             costly path from. This parameter can have either a raster input or 
                                             a feature input.
    ------------------------------------     --------------------------------------------------------------------
    input_cost_raster                        A raster defining the impedance or cost to move planimetrically through
                                             each cell.
    
                                             The value at each cell location represents the cost-per-unit distance for 
                                             moving through the cell. Each cell location value is multiplied by the 
                                             cell resolution while also compensating for diagonal movement to 
                                             obtain the total cost of passing through the cell. 
    
                                             The values of the cost raster can be an integer or a floating point, but they 
                                             cannot be negative or zero as you cannot have a negative or zero cost.
    ------------------------------------     --------------------------------------------------------------------
    input_destination_data                   The layer that defines the destinations used to calculate the distance. 
                                             This parameter can have either a raster input or a feature input.
    ------------------------------------     --------------------------------------------------------------------
    path_type                                A keyword defining the manner in which the values and zones on the 
                                             input destination data will be interpreted in the cost path calculations.

                                             A string describing the path type, which can either be BEST_SINGLE, 
                                             EACH_CELL, or EACH_ZONE.

                                             BEST_SINGLE: For all cells on the input destination data, the 
                                             least-cost path is derived from the cell with the minimum of 
                                             the least-cost paths to source cells. This is the default.

                                             EACH_CELL: For each cell with valid values on the input 
                                             destination data, at least-cost path is determined and saved 
                                             on the output raster. With this option, each cell of the input 
                                             destination data is treated separately, and a least-cost path 
                                             is determined for each from cell.

                                             EACH_ZONE: For each zone on the input destination data, 
                                             a least-cost path is determined and saved on the output raster. 
                                             With this option, the least-cost path for each zone begins at 
                                             the cell with the lowest cost distance weighting in the zone.
    ------------------------------------     --------------------------------------------------------------------
    output_polyline_name                     Optional. If not provided, a feature layer is created by the method 
                                             and used as the output.

                                             You can pass in an existing feature layer Item from your GIS to use 
                                             that instead.

                                             Alternatively, you can pass in the name of the output feature layer  that should be created by this method to be used as the output for the tool.
                                             A RuntimeError is raised if a service by that name already exists
    ------------------------------------     --------------------------------------------------------------------
    gis                                      Optional GIS. the GIS on which this tool runs. If not specified, the active GIS is used.
    ====================================     ====================================================================

    :return:
        The imagery layer url

    '''

    task = "DetermineTravelCostPathAsPolyline"

    gis = _arcgis.env.active_gis if gis is None else gis
    url = gis.properties.helperServices.rasterAnalytics.url
    gptool = _arcgis.gis._GISResource(url, gis)

    params = {}

    if output_polyline_name is None:
        output_polyline_service_name = 'Output Polyline_' + _id_generator()
        output_polyline_name = output_polyline_service_name.replace(' ', '_')
    else:
        output_polyline_service_name = output_polyline_name.replace(' ', '_')

    folder = None
    folderId = None
    if kwargs is not None:
        if "folder" in kwargs:
                folder = kwargs["folder"]
        if folder is not None:
            if isinstance(folder, dict):
                if "id" in folder:
                    folderId = folder["id"]
                    folder=folder["title"]
            else:
                owner = gis.properties.user.username
                folderId = gis._portal.get_folder_id(owner, folder)
            if folderId is None:
                folder_dict = gis.content.create_folder(folder, owner)
                folder = folder_dict["title"]
                folderId = folder_dict["id"]

    output_polyline_service = _create_output_feature_service(gis, output_polyline_name, output_polyline_service_name, 'DetermineTravelCostPathAsPolyline', folder)

    if folderId is not None:
        params["outputPolylineName"] = _json.dumps({"serviceProperties": {"name": output_polyline_service_name, "serviceUrl": output_polyline_service.url},
                                       "itemProperties": {"itemId": output_polyline_service.itemid}, "folderId":folderId})
    else:
        params["outputPolylineName"] = _json.dumps({"serviceProperties": {"name": output_polyline_service_name, "serviceUrl": output_polyline_service.url},
                                       "itemProperties": {"itemId": output_polyline_service.itemid}})

    #primary output end
    if input_source_data is not None:
        params["inputSourceRasterOrFeatures"] = _layer_input(input_source_data)
    else:
        raise RuntimeError('input_source_data cannot be None')

    if input_cost_raster is not None:
        params["inputCostRaster"] = _layer_input(input_cost_raster)
    else:
        raise RuntimeError('input_cost_raster cannot be None')

    if input_destination_data is not None:
        params["inputDestinationRasterOrFeatures"] = _layer_input(input_destination_data)
    else:
        raise RuntimeError('input_destination_data cannot be None')

    path_type_allowed_values = ["BEST_SINGLE","EACH_CELL","EACH_ZONE"]
    if path_type is not None:
        if [element.lower() for element in path_type_allowed_values].count(path_type.lower()) <= 0 :
            raise RuntimeError("path_type can only be one of the following: "+ str(path_type_allowed_values))
        for element in path_type_allowed_values:
            if path_type.lower() == element.lower():
                params['pathType'] = element

    _set_context(params)

    task_url, job_info, job_id = _analysis_job(gptool, task, params)

    job_info = _analysis_job_status(gptool, task_url, job_info)
    job_values = _analysis_job_results(gptool, task_url, job_info)
    item_properties = {
        "properties": {
            "jobUrl": task_url + '/jobs/' + job_info['jobId'],
            "jobType": "GPServer",
            "jobId": job_info['jobId'],
            "jobStatus": "completed"
        }
    }

    output_polyline_service.update(item_properties)

    return output_polyline_service


def _calculate_distance(input_source_data,
                        maximum_distance=None,
                        output_cell_size=None,
                        allocation_field=None,
                        output_distance_name=None,
                        output_direction_name=None,
                        output_allocation_name=None,
                        context=None,
                        *,
                        gis=None,
                        **kwargs):

    '''
    Calculates the Euclidean distance, direction, and allocation from a single source or set of sources.

    ====================================     ====================================================================
    **Argument**                             **Description**
    ------------------------------------     --------------------------------------------------------------------
    input_source_data                        The layer that defines the sources to calculate the distance to. 
                                             The layer can be raster or feature. To use a raster input, it must 
                                             be of integer type.
    ------------------------------------     --------------------------------------------------------------------
    maximum_distance                         Defines the threshold that the accumulative distance values 
                                             cannot exceed. If an accumulative Euclidean distance value exceeds 
                                             this value, the output value for the cell location will be NoData. 
                                             The default distance is to the edge of the output raster.

                                             Supported units: Meters | Kilometers | Feet | Miles

                                             Example:

                                             {"distance":"60","units":"Meters"}
    ------------------------------------     --------------------------------------------------------------------
    output_cell_size                         Specify the cell size to use for the output raster.

                                             Supported units: Meters | Kilometers | Feet | Miles

                                             Example:
                                             {"distance":"60","units":"Meters"}
    ------------------------------------     --------------------------------------------------------------------
    allocation_field                         A field on the input_source_data layer that holds the values that 
                                             defines each source.

                                             It can be an integer or a string field of the source dataset.

                                             The default for this parameter is 'Value'.
    ------------------------------------     --------------------------------------------------------------------
    output_distance_name                     Optional. This is the output distance imagery layer that will be 
                                             created.

                                             If not provided, an imagery layer is created by the method 
                                             and used as the output.
    ------------------------------------     --------------------------------------------------------------------
    output_direction_name                    Optional. This is the output direction imagery layer that will be 
                                             created.

                                             If not provided, an imagery layer is created by the method 
                                             and used as the output.

                                             The output direction raster is in degrees, and indicates the 
                                             direction to return to the closest source from each cell center. 
                                             The values on the direction raster are based on compass directions, 
                                             with 0 degrees reserved for the source cells. Thus, a value of 90 
                                             means 90 degrees to the East, 180 is to the South, 270 is to the west,
                                             and 360 is to the North.
    ------------------------------------     --------------------------------------------------------------------
    output_allocation_name                   Optional. This is the output allocation  imagery layer that will be 
                                             created.

                                             If not provided, an imagery layer is created by the method 
                                             and used as the output.

                                             This parameter calculates, for each cell, the nearest source based 
                                             on Euclidean distance.
    ------------------------------------     --------------------------------------------------------------------
    context                                  Context contains additional settings that affect task execution.
    ------------------------------------     --------------------------------------------------------------------
    gis                                      Optional GIS. the GIS on which this tool runs. If not specified, the active GIS is used.
    ====================================     ====================================================================

    :return:
        The imagery layer url

    '''

    task = "CalculateDistance"

    gis = _arcgis.env.active_gis if gis is None else gis
    url = gis.properties.helperServices.rasterAnalytics.url
    gptool = _arcgis.gis._GISResource(url, gis)

    return_value_names = ["output_distance_service"]
    params = {}

    output_distance_raster, output_distance_service = _set_output_raster(output_distance_name, task, gis, kwargs)  
    params["outputDistanceName"] = output_distance_raster 

    #primary output end

    if input_source_data is not None:
        params["inputSourceRasterOrFeatures"] = _layer_input(input_source_data)
    else:
        raise RuntimeError('input_source_data cannot be None')

    if maximum_distance is not None:
        params["maximumDistance"] = maximum_distance

    if output_cell_size is not None:
        params["outputCellSize"] = output_cell_size

    if allocation_field is not None:
        params["allocationField"] = allocation_field

    if output_direction_name is not None:
        output_direction_raster, output_direction_service = _set_output_raster(output_direction_name, task, gis, kwargs)
        params["outputDirectionName"] = output_direction_raster
        return_value_names.extend(["output_direction_service"])

    if output_allocation_name is not None:
        output_allocation_raster, out_allocation_service = _set_output_raster(output_allocation_name, task, gis, kwargs) 
        params["outputAllocationName"] = output_allocation_raster
        return_value_names.extend(["output_allocation_service"])

    _set_context(params)

    task_url, job_info, job_id = _analysis_job(gptool, task, params)

    job_info = _analysis_job_status(gptool, task_url, job_info)
    job_values = _analysis_job_results(gptool, task_url, job_info)
    item_properties = {
        "properties": {
            "jobUrl": task_url + '/jobs/' + job_info['jobId'],
            "jobType": "GPServer",
            "jobId": job_info['jobId'],
            "jobStatus": "completed"
        }
    }
    output_distance_service.update(item_properties)
    outputs={"output_distance_service" : output_distance_service}
    if output_direction_name is not None:
       output_direction_service.update(item_properties)
       outputs.update({"output_direction_service":output_direction_service})
    if output_allocation_name is not None:
       out_allocation_service.update(item_properties)
       outputs.update({"output_allocation_service" : out_allocation_service})
    num_returns = len(outputs)

    return _return_output(num_returns, outputs, return_value_names)
