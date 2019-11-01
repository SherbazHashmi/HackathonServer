"""
Global Raster functions.
These functions are applied to the raster data to create a
processed product on disk, using ImageryLayer.save() method or arcgis.raster.analytics.generate_raster().

Global functions cannot be used for visualization using dynamic image processing. They cannot be applied to layers that
are added to a map for on-the-fly image processing or visualized inline within the Jupyter notebook.

Functions can be applied to various rasters (or images), including the following:

* Imagery layers
* Rasters within imagery layers

"""
from arcgis.raster._layer import ImageryLayer
from arcgis.features import FeatureLayer
from arcgis.gis import Item
import copy
import numbers
from arcgis.raster.functions.utility import _raster_input, _get_raster, _replace_raster_url, _get_raster_url, _get_raster_ra
from arcgis.geoprocessing._support import _layer_input,_feature_input
import string as _string
import random as _random
import arcgis as _arcgis

def _create_output_image_service(gis, output_name, task):
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
                                                      service_type="imageService")
    description = "Image Service generated from running the " + task + " tool."
    item_properties = {
        "description": description,
        "tags": "Analysis Result, " + task,
        "snippet": "Analysis Image Service generated from " + task
    }
    output_service.update(item_properties)
    return output_service


def _id_generator(size=6, chars=_string.ascii_uppercase + _string.digits):
    return ''.join(_random.choice(chars) for _ in range(size))


def _gbl_clone_layer(layer, function_chain, function_chain_ra,**kwargs):
    if isinstance(layer, Item):
        layer = layer.layers[0]    

    newlyr = ImageryLayer(layer._url, layer._gis)

    newlyr._lazy_properties = layer.properties
    newlyr._hydrated = True
    newlyr._lazy_token = layer._token

    # if layer._fn is not None: # chain the functions
    #     old_chain = layer._fn
    #     newlyr._fn = function_chain
    #     newlyr._fn['rasterFunctionArguments']['Raster'] = old_chain
    # else:
    newlyr._fn = function_chain
    newlyr._fnra = function_chain_ra

    newlyr._where_clause = layer._where_clause
    newlyr._spatial_filter = layer._spatial_filter
    newlyr._temporal_filter = layer._temporal_filter
    newlyr._mosaic_rule = layer._mosaic_rule
    newlyr._filtered = layer._filtered
    newlyr._extent = layer._extent
    
    newlyr._uses_gbl_function = True
    for key in kwargs:
        newlyr._other_outputs.update({key:kwargs[key]})

    return newlyr

def _feature_gbl_clone_layer(layer, function_chain, function_chain_ra,**kwargs):
    if isinstance(layer, Item):
        layer = layer.layers[0]    

    newlyr = ImageryLayer(layer._url, layer._gis)
    
    newlyr._fn = function_chain
    newlyr._fnra = function_chain_ra

    newlyr._storage = layer._storage
    newlyr._dynamic_layer = layer._dynamic_layer

    newlyr._uses_gbl_function = True
    for key in kwargs:
        newlyr._other_outputs.update({key:kwargs[key]})
    return newlyr

def euclidean_distance(in_source_data,
                       cell_size=None,
                       max_distance=None,
                       distance_method="PLANAR"):
    """
    Calculates, for each cell, the Euclidean distance to the closest source. 
    For more information, see 
    http://pro.arcgis.com/en/pro-app/help/data/imagery/euclidean-distance-global-function.htm

    Parameters
    ----------
    :param in_source_data: raster; The input raster that identifies the pixels or locations to
                            which the Euclidean distance for every output pixel location is calculated.
                            The input type can be an integer or a floating-point value.
    :param cell_size:  The pixel size at which the output raster will be created. If the cell
                            size was explicitly set in Environments, that will be the default cell size. 
                            If Environments was not set, the output cell size will be the same as the 
                            Source Raster
    :param max_distance: The threshold that the accumulative distance values cannot exceed. If an
                            accumulative Euclidean distance exceeds this value, the output value for
                            the pixel location will be NoData. The default distance is to the edge 
                            of the output raster
    :return: output raster with function applied
    """
    layer, in_source_data, raster_ra = _raster_input(in_source_data)
                  
    template_dict = {
        "rasterFunction" : "GPAdapter",
        "rasterFunctionArguments" : {
            "toolName" : "EucDistance_sa",           
            "PrimaryInputParameterName":"in_source_data",
            "OutputRasterParameterName":"out_distance_raster",
            "in_source_data": in_source_data,
                
        }
    }
    
    if cell_size is not None:
        template_dict["rasterFunctionArguments"]["cell_size"] = cell_size
    
    if max_distance is not None:
        template_dict["rasterFunctionArguments"]["maximum_distance"] = max_distance

    distance_method_list = ["PLANAR","GEODESIC"]
    if distance_method is not None:
        if distance_method.upper() not in distance_method_list:
            raise RuntimeError('distance_method should be one of the following '+ str(distance_method_list))
        template_dict["rasterFunctionArguments"]["distance_method"] = distance_method

    function_chain_ra = copy.deepcopy(template_dict)
    function_chain_ra["rasterFunctionArguments"]["in_source_data"] = raster_ra

    return _gbl_clone_layer(layer, template_dict, function_chain_ra)
    


def euclidean_allocation(in_source_data,
                         in_value_raster=None,
                         max_distance=None,
                         cell_size=None,
                         source_field=None,
                         distance_method=None):
    
    """
    Calculates, for each cell, the nearest source based on Euclidean distance.
    For more information, see 
    http://pro.arcgis.com/en/pro-app/help/data/imagery/euclidean-allocation-global-function.htm

    Parameters
    ----------
    :param in_source_data: raster; The input raster that identifies the pixels or locations to which
                            the Euclidean distance for every output pixel location is calculated. 
                            The input type can be an integer or a floating-point value.
                            If the input Source Raster is floating point, the Value Raster must be set,
                            and it must be an integer. The Value Raster will take precedence over any
                            setting of the Source Field.
    :param in_value_raster: The input integer raster that identifies the zone values that should be 
                            used for each input source location. For each source location pixel, the
                            value defined by the Value Raster will be assigned to all pixels allocated
                            to the source location for the computation. The Value Raster will take 
                            precedence over any setting for the Source Field .
    :param max_distance: The threshold that the accumulative distance values cannot exceed. If an
                            accumulative Euclidean distance exceeds this value, the output value for
                            the pixel location will be NoData. The default distance is to the edge                     
                            of the output raster
    :param cell_size: The pixel size at which the output raster will be created. If the cell size
                            was explicitly set in Environments, that will be the default cell size. 
                            If Environments was not set, the output cell size will be the same as the 
                            Source Raster
    :param source_field: The field used to assign values to the source locations. It must be an
                            integer type. If the Value Raster has been set, the values in that input
                            will take precedence over any setting for the Source Field.
    :return: output raster with function applied
    """
    
    layer1, in_source_data, raster_ra1 = _raster_input(in_source_data)      
            
    template_dict = {
        "rasterFunction" : "GPAdapter",
        "rasterFunctionArguments" : {
            "toolName" : "EucAllocation_sa",           
            "PrimaryInputParameterName":"in_source_data",
            "OutputRasterParameterName":"out_allocation_raster",
            "in_source_data": in_source_data            
                
        }
    }
    
    if in_value_raster is not None:
        layer2, in_value_raster, raster_ra2 = _raster_input(in_value_raster)
        template_dict["rasterFunctionArguments"]["in_value_raster"] = in_value_raster
    
    if cell_size is not None:
        template_dict["rasterFunctionArguments"]["cell_size"] = cell_size
    
    if max_distance is not None:
        template_dict["rasterFunctionArguments"]["maximum_distance"] = max_distance
    
    if source_field is not None:
        template_dict["rasterFunctionArguments"]["source_field"] = source_field

    distance_method_list = ["PLANAR","GEODESIC"]
    if distance_method is not None:
        if distance_method.upper() not in distance_method_list:
            raise RuntimeError('distance_method should be one of the following '+ str(distance_method_list))
        template_dict["rasterFunctionArguments"]["distance_method"] = distance_method
    
    function_chain_ra = copy.deepcopy(template_dict)
    function_chain_ra['rasterFunctionArguments']["in_source_data"] = raster_ra1
    if in_value_raster is not None:
        function_chain_ra["rasterFunctionArguments"]["in_value_raster"] = raster_ra2

    return _gbl_clone_layer(layer1, template_dict, function_chain_ra)
    
    
    
def cost_distance(in_source_data,
                  in_cost_raster,
                  max_distance=None,
                  source_cost_multiplier=None,
                  source_start_cost=None,
                  source_resistance_rate=None,
                  source_capacity=None,
                  source_direction=None):
    """
    Calculates the least accumulative cost distance for each cell from or to the least-cost
    source over a cost surface.
    For more information, see
    http://pro.arcgis.com/en/pro-app/help/data/imagery/cost-distance-global-function.htm

    Parameters
    ----------
    :param in_source_data: The input raster that identifies the pixels or locations to which the
                            least accumulated cost distance for every output pixel location is 
                            calculated. The Source Raster can be an integer or a floating-point value.
    :param in_cost_raster: A raster defining the cost or impedance to move planimetrically through each pixel.
                            The value at each pixel location represents the cost-per-unit distance for moving 
                            through it. Each pixel location value is multiplied by the pixel resolution, while 
                            also compensating for diagonal movement to obtain the total cost of passing through 
                            the pixel. 
    :param max_distance: The threshold that the accumulative cost values cannot exceed. If an accumulative cost
                            distance exceeds this value, the output value for the pixel location will be NoData. 
                            The maximum distance defines the extent for which the accumulative cost distances are
                            calculated. The default distance is to the edge of the output raster.
    :param source_cost_multiplier: The threshold that the accumulative cost values cannot exceed. If an accumulative                                       
                            cost distance exceeds this value, the output value for the pixel location will be 
                            NoData. The maximum distance defines the extent for which the accumulative cost 
                            distances are calculated. The default distance is to the edge of the output raster.
    :param source_start_cost: The starting cost from which to begin the cost calculations. This parameter allows
                            for the specification of the fixed cost associated with a source. Instead of starting
                            at a cost of 0, the cost algorithm will begin with the value set here.
                            The default is 0. The value must be 0 or greater. A numeric (double) value or a field
                            from the Source Raster can be used for this parameter.
    :param source_resistance_rate: This parameter simulates the increase in the effort to overcome costs as the
                            accumulative cost increases. It is used to model fatigue of the traveler. The growing
                            accumulative cost to reach a pixel is multiplied by the resistance rate and added to 
                            the cost to move into the subsequent pixel.
                            It is a modified version of a compound interest rate formula that is used to calculate
                            the apparent cost of moving through a pixel. As the value of the resistance rate increases,
                            it increases the cost of the pixels that are visited later. The greater the resistance rate, 
                            the higher the cost to reach the next pixel, which is compounded for each subsequent movement. 
                            Since the resistance rate is similar to a compound rate and generally the accumulative cost 
                            values are very large, small resistance rates are suggested, such as 0.005 or even smaller, 
                            depending on the accumulative cost values.
                            The default is 0. The values must be 0 or greater. A numeric (double) value or a field from
                            the Source Raster can be used for this parameter.
    :param source_capacity: Defines the cost capacity for the traveler for a source. The cost calculations continue for
                            each source until the specified capacity is reached.
                            The default capacity is to the edge of the output raster. The values must be greater than 0. 
                            A double numeric value or a field from the Source Raster can be used for this parameter.
    :param source_direction: Defines the direction of the traveler when applying the source resistance rate and the source
                            starting cost.
                            FROM_SOURCE - The source resistance rate and source starting cost will be applied beginning
                            at the input source and moving out to the nonsource cells. This is the default.
                            TO_SOURCE - The source resistance rate and source starting cost will be applied beginning at
                            each nonsource cell and moving back to the input source.
                            Either specify the From Source or To Source keyword, which will be applied to all sources,
                            or specify a field in the Source Raster that contains the keywords to identify the direction
                            of travel for each source. That field must contain the string From Source or To Source.
    
    :return: output raster with function applied
    """        
    layer1, in_source_data, raster_ra1 = _raster_input(in_source_data)  
    layer2, in_cost_raster, raster_ra2 = _raster_input(in_cost_raster)
    
    template_dict = {
        "rasterFunction" : "GPAdapter",
        "rasterFunctionArguments" : {
            "toolName" : "CostDistance_sa",           
            "PrimaryInputParameterName":"in_source_data",
            "OutputRasterParameterName":"out_distance_raster",
            "in_source_data": in_source_data, 
            "in_cost_raster": in_cost_raster
             
        }
    }    
    
    if max_distance is not None:
        template_dict["rasterFunctionArguments"]["maximum_distance"] = max_distance
    
    if source_cost_multiplier is not None:
        template_dict["rasterFunctionArguments"]["source_cost_multiplier"] = source_cost_multiplier
    
    if source_start_cost is not None:
        template_dict["rasterFunctionArguments"]["source_start_cost"] = source_start_cost
    
    if source_resistance_rate is not None:
        template_dict["rasterFunctionArguments"]["source_resistance_rate"] = source_resistance_rate
    
    if source_capacity is not None:
        template_dict["rasterFunctionArguments"]["source_capacity"] = source_capacity
    
    source_direction_list = ["FROM_SOURCE","TO_SOURCE"]

    if source_direction is not None:
        if source_direction.upper() not in source_direction_list:
            raise RuntimeError('source_direction should be one of the following '+ str(source_direction_list))
        template_dict["rasterFunctionArguments"]["source_direction"] = source_direction

    function_chain_ra = copy.deepcopy(template_dict)
    function_chain_ra["rasterFunctionArguments"]["in_source_data"] = raster_ra1
    function_chain_ra["rasterFunctionArguments"]["in_cost_raster"] = raster_ra2

    return _gbl_clone_layer(layer1, template_dict, function_chain_ra)


def cost_allocation(in_source_data,
                    in_cost_raster,
                    in_value_raster=None,
                    max_distance=None,                    
                    source_field=None,
                    source_cost_multiplier=None,
                    source_start_cost=None,
                    source_resistance_rate=None,
                    source_capacity=None,
                    source_direction=None):
    """
    Calculates, for each cell, its least-cost source based on the least accumulative cost over a cost surface.
    For more information, see
    http://pro.arcgis.com/en/pro-app/help/data/imagery/cost-allocation-global-function.htm

    Parameters
    ----------
    :param in_source_data: The input raster that identifies the pixels or locations to which the
                            least accumulated cost distance for every output pixel location is 
                            calculated. The Source Raster can be an integer or a floating-point value.
                            If the input Source Raster is floating point, the Value Raster must be set, 
                            and it must be an integer. The Value Raster will take precedence over any 
                            setting of the Source Field.
    :param in_cost_raster: A raster defining the cost or impedance to move planimetrically through each pixel.
                            The value at each pixel location represents the cost-per-unit distance for moving 
                            through it. Each pixel location value is multiplied by the pixel resolution, while 
                            also compensating for diagonal movement to obtain the total cost of passing through 
                            the pixel. 
                            The values of the Cost Raster can be integer or floating point, but they cannot be 
                            negative or zero.
    :param in_value_raster: The input integer raster that identifies the zone values that should be used for 
                            each input source location. For each source location pixel, the value defined by
                            the Value Raster will be assigned to all pixels allocated to the source location 
                            for the computation. The Value Raster will take precedence over any setting for 
                            the Source Field. 
    :param max_distance: The threshold that the accumulative cost values cannot exceed. If an accumulative cost
                            distance exceeds this value, the output value for the pixel location will be NoData. 
                            The maximum distance defines the extent for which the accumulative cost distances are
                            calculated. The default distance is to the edge of the output raster.
    :param source_field: The field used to assign values to the source locations. It must be an integer type.
                            If the Value Raster has been set, the values in that input will take precedence over
                            any setting for the Source Field.
    :param source_cost_multiplier: This parameter allows for control of the mode of travel or the magnitude at
                            a source. The greater the multiplier, the greater the cost to move through each cell.
                            The default value is 1. The values must be greater than 0. A numeric (double) value or
                            a field from the Source Raster can be used for this parameter.
    :param source_start_cost: The starting cost from which to begin the cost calculations. This parameter allows
                            for the specification of the fixed cost associated with a source. Instead of starting
                            at a cost of 0, the cost algorithm will begin with the value set here.
                            The default is 0. The value must be 0 or greater. A numeric  (double) value or a field
                            from the Source Raster can be used for this parameter.
    :param source_resistance_rate: This parameter simulates the increase in the effort to overcome costs as the
                            accumulative cost increases. It is used to model fatigue of the traveler. The growing
                            accumulative cost to reach a pixel is multiplied by the resistance rate and added to 
                            the cost to move into the subsequent pixel.
                            It is a modified version of a compound interest rate formula that is used to calculate
                            the apparent cost of moving through a pixel. As the value of the resistance rate increases,
                            it increases the cost of the pixels that are visited later. The greater the resistance rate, 
                            the higher the cost to reach the next pixel, which is compounded for each subsequent movement. 
                            Since the resistance rate is similar to a compound rate and generally the accumulative cost 
                            values are very large, small resistance rates are suggested, such as 0.005 or even smaller, 
                            depending on the accumulative cost values.
                            The default is 0. The values must be 0 or greater. A numeric (double) value or a field from
                            the Source Raster can be used for this parameter.
    :param source_capacity: Defines the cost capacity for the traveler for a source. The cost calculations continue for
                            each source until the specified capacity is reached.
                            The default capacity is to the edge of the output raster. The values must be greater than 0. 
                            A double numeric value or a field from the Source Raster can be used for this parameter.
    :source_direction: Defines the direction of the traveler when applying the source resistance rate and the source
                            starting cost.
                            FROM_SOURCE - The source resistance rate and source starting cost will be applied beginning
                            at the input source and moving out to the nonsource cells. This is the default.
                            TO_SOURCE - The source resistance rate and source starting cost will be applied beginning at
                            each nonsource cell and moving back to the input source.
                            Either specify the From Source or To Source keyword, which will be applied to all sources,
                            or specify a field in the Source Raster that contains the keywords to identify the direction
                            of travel for each source. That field must contain the string From Source or To Source.
    
    :return: output raster with function applied
    """   
            
    layer1, in_source_data, raster_ra1 = _raster_input(in_source_data)
    layer2, in_cost_raster, raster_ra2 = _raster_input(in_cost_raster)
            
    template_dict = {
        "rasterFunction" : "GPAdapter",
        "rasterFunctionArguments" : {
            "toolName" : "CostAllocation_sa",           
            "PrimaryInputParameterName":"in_source_data",
            "OutputRasterParameterName":"out_allocation_raster",
            "in_source_data": in_source_data, 
            "in_cost_raster": in_cost_raster
             
        }
    }    
    if in_value_raster is not None:
        layer3, in_value_raster, raster_ra3 = _raster_input(in_value_raster)
        template_dict["rasterFunctionArguments"]["in_value_raster"] = in_value_raster

    if max_distance is not None:
        template_dict["rasterFunctionArguments"]["maximum_distance"] = max_distance

    if source_field is not None:
        template_dict["rasterFunctionArguments"]["source_field"] = source_field
    
    if source_cost_multiplier is not None:
        template_dict["rasterFunctionArguments"]["source_cost_multiplier"] = source_cost_multiplier
    
    if source_start_cost is not None:
        template_dict["rasterFunctionArguments"]["source_start_cost"] = source_start_cost
    
    if source_resistance_rate is not None:
        template_dict["rasterFunctionArguments"]["source_resistance_rate"] = source_resistance_rate
    
    if source_capacity is not None:
        template_dict["rasterFunctionArguments"]["source_capacity"] = source_capacity

    source_direction_list = ["FROM_SOURCE","TO_SOURCE"]

    if source_direction is not None:
        if source_direction.upper() not in source_direction_list:
            raise RuntimeError('source_direction should be one of the following '+ str(source_direction_list))
        template_dict["rasterFunctionArguments"]["source_direction"] = source_direction


    function_chain_ra = copy.deepcopy(template_dict)
    function_chain_ra["rasterFunctionArguments"]["in_source_data"] = raster_ra1
    function_chain_ra["rasterFunctionArguments"]["in_cost_raster"] = raster_ra2
    if in_value_raster is not None:
        function_chain_ra["rasterFunctionArguments"]["in_value_raster"] = raster_ra3

    return _gbl_clone_layer(layer1, template_dict, function_chain_ra)


def zonal_statistics(in_zone_data,
                     zone_field,
                     in_value_raster,
                     ignore_nodata=True,
                     statistics_type=None):
                     
    """"
    Calculates statistics on values of a raster within the zones of another dataset.
    For more information, 
    http://pro.arcgis.com/en/pro-app/help/data/imagery/zonal-statistics-global-function.htm

    Parameters
    ----------
    :param in_zone_data: Dataset that defines the zones. The zones can be defined by an integer raster
    :param zone_field: Field that holds the values that define each zone. It can be an integer or a
                            string field of the zone raster.
    :param in_value_raster: Raster that contains the values on which to calculate a statistic.
    :param ignore_no_data: Denotes whether NoData values in the Value Raster will influence the results
                            of the zone that they fall within.
                            True - Within any particular zone, only pixels that have a value in the Value
                            Raster will be used in determining the output value for that zone. NoData 
                            pixels in the Value Raster will be ignored in the statistic calculation. 
                            This is the default.
                            False - Within any particular zone, if any NoData pixels exist in the Value 
                            Raster, it is deemed that there is insufficient information to perform 
                            statistical calculations for all the pixels in that zone; therefore, the 
                            entire zone will receive the NoData value on the output raster.
    :param statistics_type: Statistic type to be calculated.
                            MEAN-Calculates the average of all pixels in the Value Raster that belong to
                            the same zone as the output pixel.
                            MAJORITY-Determines the value that occurs most often of all pixels in the 
                            Value Raster that belong to the same zone as the output pixel.
                            MAXIMUM-Determines the largest value of all pixels in the Value Raster 
                            that belong to the same zone as the output pixel.
                            MEDIAN-Determines the median value of all pixels in the Value Raster
                            that belong to the same zone as the output pixel.
                            MINIMUM-Determines the smallest value of all pixels in the Value Raster 
                            that belong to the same zone as the output pixel.
                            MINORITY-Determines the value that occurs least often of all pixels in
                            the Value Raster that belong to the same zone as the output pixel.
                            RANGE-Calculates the difference between the largest and smallest value 
                            of all pixels in the Value Raster that belong to the same zone as the
                            output pixel.
                            STD-Calculates the standard deviation of all pixels in
                            the Value Rasterthat belong to the same zone as the output pixel.
                            SUM-Calculates the total value of all pixels in the Value Raster that
                            belong to the same zone as the output pixel.
                            VARIETY-Calculates the number of unique values for all pixels in the 
                            Value Raster that belong to the same zone as the output pixel.
    :return: output raster with function applied

    """
    layer1, in_zone_data, raster_ra1 = _raster_input(in_zone_data)  
    layer2, in_value_raster, raster_ra2 = _raster_input(in_value_raster)
        
    template_dict = {
        "rasterFunction" : "GPAdapter",
        "rasterFunctionArguments" : {
            "toolName" : "ZonalStatistics_sa",           
            "PrimaryInputParameterName" : "in_value_raster",
            "OutputRasterParameterName" : "out_raster",
            "in_zone_data" : in_zone_data, 
            "zone_field" : zone_field,
            "in_value_raster" : in_value_raster
             
        }
    }

    if ignore_nodata is not None:
        if not isinstance(ignore_nodata,bool):
            raise RuntimeError('ignore_nodata should be a boolean value')
        if ignore_nodata is True:
            ignore_nodata = "DATA"
        elif ignore_nodata is False:
            ignore_nodata = "NODATA"
        template_dict["rasterFunctionArguments"]["ignore_nodata"] = ignore_nodata
        
             
    statistics_type_list = ["MEAN","MAJORITY","MAXIMUM","MEDIAN","MINIMUM","MINORITY","RANGE","STD","SUM","VARIETY"]
    if statistics_type is not None:
        if statistics_type.upper() not in statistics_type_list:
            raise RuntimeError('statistics_type should be one of the following '+ str(statistics_type_list))    
        template_dict["rasterFunctionArguments"]["statistics_type"] = statistics_type


    function_chain_ra = copy.deepcopy(template_dict)
    function_chain_ra['rasterFunctionArguments']["in_zone_data"] = raster_ra1
    function_chain_ra["rasterFunctionArguments"]["in_value_raster"] = raster_ra2

    return _gbl_clone_layer(layer1, template_dict, function_chain_ra)        
        
        
def least_cost_path(in_source_data,
                    in_cost_raster,
                    in_destination_data,
                    destination_field=None,                    
                    path_type="EACH_CELL",
                    max_distance=None,
                    source_cost_multiplier=None,
                    source_start_cost=None,
                    source_resistance_rate=None,
                    source_capacity=None,
                    source_direction=None):
    """
    Calculates the least-cost path from a source to a destination. The least accumulative cost distance 
    is calculated for each pixel over a cost surface, to the nearest source. This produces an output 
    raster that records the least-cost path, or paths, from selected locations to the closest source
    pixels defined within the accumulative cost surface, in terms of cost distance.
    For more information, see
    http://pro.arcgis.com/en/pro-app/help/data/imagery/least-cost-path-global-function.htm

    Parameters
    ----------
    :param in_source_data: The input raster that identifies the pixels or locations to which the
                            least accumulated cost distance for every output pixel location is 
                            calculated. The Source Raster can be an integer or a floating-point value.
                            If the input Source Raster is floating point, the Value Raster must be set, 
                            and it must be an integer. The Value Raster will take precedence over any 
                            setting of the Source Field.
    :param in_cost_raster: A raster defining the cost or impedance to move planimetrically through each pixel.
                            The value at each pixel location represents the cost-per-unit distance for moving 
                            through it. Each pixel location value is multiplied by the pixel resolution, while 
                            also compensating for diagonal movement to obtain the total cost of passing through 
                            the pixel. 
                            The values of the Cost Raster can be integer or floating point, but they cannot be 
                            negative or zero.
    :param in_destination_data: A raster dataset that identifies the pixels from which the least-cost path is 
                            determined to the least costly source. This input consists of pixels that have valid
                            values, and the remaining pixels must be assigned NoData. Values of 0 are valid.
    :param destination_field: The field used to obtain values for the destination locations.
    :param path_type: A keyword defining the manner in which the values and zones on the input destination
                            data will be interpreted in the cost path calculations:
                            EACH_CELL-A least-cost path is determined for each pixel with valid values on the 
                            input destination data, and saved on the output raster. Each cell of the input 
                            destination data is treated separately, and a least-cost path is determined for each from cell.
                            EACH_ZONE-A least-cost path is determined for each zone on the input destination data and
                            saved on the output raster. The least-cost path for each zone begins at the pixel with the
                            lowest cost distance weighting in the zone.
                            BEST_SINGLE-For all pixels on the input destination data, the least-cost path is derived
                            from the pixel with the minimum of the least-cost paths to source cells.
    :param max_distance: The threshold that the accumulative cost values cannot exceed. If an accumulative cost
                            distance exceeds this value, the output value for the pixel location will be NoData. 
                            The maximum distance defines the extent for which the accumulative cost distances are
                            calculated. The default distance is to the edge of the output raster.
    :param source_field: The field used to assign values to the source locations. It must be an integer type.
                            If the Value Raster has been set, the values in that input will take precedence over
                            any setting for the Source Field.
    :param source_cost_multiplier: The threshold that the accumulative cost values cannot exceed. If an accumulative
                            cost distance exceeds this value, the output value for the pixel location will be 
                            NoData. The maximum distance defines the extent for which the accumulative cost 
                            distances are calculated. The default distance is to the edge of the output raster.
    :param source_start_cost: The starting cost from which to begin the cost calculations. This parameter allows
                            for the specification of the fixed cost associated with a source. Instead of starting
                            at a cost of 0, the cost algorithm will begin with the value set here.
                            The default is 0. The value must be 0 or greater. A numeric (double) value or a field
                            from the Source Raster can be used for this parameter.
    :param source_resistance_rate: This parameter simulates the increase in the effort to overcome costs as the
                            accumulative cost increases. It is used to model fatigue of the traveler. The growing
                            accumulative cost to reach a pixel is multiplied by the resistance rate and added to 
                            the cost to move into the subsequent pixel.
                            It is a modified version of a compound interest rate formula that is used to calculate
                            the apparent cost of moving through a pixel. As the value of the resistance rate increases,
                            it increases the cost of the pixels that are visited later. The greater the resistance rate, 
                            the higher the cost to reach the next pixel, which is compounded for each subsequent movement. 
                            Since the resistance rate is similar to a compound rate and generally the accumulative cost 
                            values are very large, small resistance rates are suggested, such as 0.005 or even smaller, 
                            depending on the accumulative cost values.
                            The default is 0. The values must be 0 or greater. A numeric (double) value or a field from
                            the Source Raster can be used for this parameter.
    :param source_capacity: Defines the cost capacity for the traveler for a source. The cost calculations continue for
                            each source until the specified capacity is reached.
                            The default capacity is to the edge of the output raster. The values must be greater than 0. 
                            A double numeric value or a field from the Source Raster can be used for this parameter.
    :param source_direction: Defines the direction of the traveler when applying the source resistance rate and the source
                            starting cost.
                            FROM_SOURCE - The source resistance rate and source starting cost will be applied beginning
                            at the input source and moving out to the nonsource cells. This is the default.
                            TO_SOURCE-The source resistance rate and source starting cost will be applied beginning at
                            each nonsource cell and moving back to the input source.
                            Either specify the From Source or To Source keyword, which will be applied to all sources,
                            or specify a field in the Source Raster that contains the keywords to identify the direction
                            of travel for each source. That field must contain the string From Source or To Source.
    
    :return: output raster with function applied
    """  
    layer1, in_source_data, raster_ra1 = _raster_input(in_source_data)
    layer2, in_cost_raster, raster_ra2 = _raster_input(in_cost_raster)
    layer3, in_destination_data, raster_ra3 = _raster_input(in_destination_data)
            
    template_dict = {
        "rasterFunction" : "GPAdapter",
        "rasterFunctionArguments" : {
            "toolName" : "ShortestPath",           
            "PrimaryInputParameterName" : "in_source_data",
            "OutputRasterParameterName":"out_path_raster",
            "in_source_data" : in_source_data, 
            "in_cost_raster" : in_cost_raster,
            "in_destination_data" : in_destination_data
                
        }
    }    
            
    if destination_field is not None:
        template_dict["rasterFunctionArguments"]["destination_field"] = destination_field
    
    if path_type is not None:
        path_type_list = ["EACH_CELL", "EACH_ZONE", "BEST_SINGLE"]
        if path_type.upper() not in path_type_list:
            raise RuntimeError('path_type should be one of the following '+ str(path_type_list))
        template_dict["rasterFunctionArguments"]["path_type"] = path_type

    if max_distance is not None:
        template_dict["rasterFunctionArguments"]["maximum_distance"] = max_distance
    
    if source_cost_multiplier is not None:
        template_dict["rasterFunctionArguments"]["source_cost_multiplier"] = source_cost_multiplier
    
    if source_start_cost is not None:
        template_dict["rasterFunctionArguments"]["source_start_cost"] = source_start_cost
    
    if source_resistance_rate is not None:
        template_dict["rasterFunctionArguments"]["source_resistance_rate"] = source_resistance_rate
    
    if source_capacity is not None:
        template_dict["rasterFunctionArguments"]["source_capacity"] = source_capacity

    source_direction_list = ["FROM_SOURCE","TO_SOURCE"]

    if source_direction is not None:
        if source_direction.upper() not in source_direction_list:
            raise RuntimeError('source_direction should be one of the following '+ str(source_direction_list) )
        template_dict["rasterFunctionArguments"]["source_direction"] = source_direction

    function_chain_ra = copy.deepcopy(template_dict)
    function_chain_ra['rasterFunctionArguments']["in_source_data"] = raster_ra1
    function_chain_ra["rasterFunctionArguments"]["in_cost_raster"] = raster_ra2
    function_chain_ra["rasterFunctionArguments"]["in_destination_data"] = raster_ra3

    return _gbl_clone_layer(layer1, template_dict, function_chain_ra)


def flow_distance(input_stream_raster,
                  input_surface_raster,
                  input_flow_direction_raster=None,
                  distance_type="VERTICAL",
                  flow_direction_type= "D8"):
                     
    """
    This function computes, for each cell, the minimum downslope 
    horizontal or vertical distance to cell(s) on a stream or
    river into which they flow. If an optional flow direction 
    raster is provided, the down slope direction(s) will be 
    limited to those defined by the input flow direction raster.

    Parameters
    ----------
    :param input_stream_raster: An input raster that represents a linear stream network
    :param input_surface_raster: The input raster representing a continuous surface.
    :param input_flow_direction_raster: The input raster that shows the direction of flow out of each cell.
    :param distance_type: VERTICAL or HORIZONTAL distance to compute; if not
                                 specified, VERTICAL distance is computed.
    :return: output raster with function applied
    """
    layer1, input_stream_raster, raster_ra1 = _raster_input(input_stream_raster)  
    layer2, input_surface_raster, raster_ra2 = _raster_input(input_surface_raster)

        
    template_dict = {
        "rasterFunction" : "GPAdapter",
        "rasterFunctionArguments" : {
            "toolName" : "FlowDistance_sa",           
            "PrimaryInputParameterName" : "in_stream_raster",
            "OutputRasterParameterName" : "out_raster",
            "in_stream_raster" : input_stream_raster, 
            "in_surface_raster" : input_surface_raster,
             
        }
    }    
    if input_flow_direction_raster is not None:
        layer3, input_flow_direction_raster, raster_ra3 = _raster_input(input_flow_direction_raster)
        template_dict["rasterFunctionArguments"]["in_flow_direction_raster"] = input_flow_direction_raster
    
    distance_type_list = ["VERTICAL","HORIZONTAL"]

    if distance_type is not None:
        if distance_type.upper() not in distance_type_list:
            raise RuntimeError('distance_type should be one of the following '+ str(distance_type_list))
        template_dict["rasterFunctionArguments"]["distance_type"] = distance_type

    flow_direction_type_list = ["D8","MFD","DINF"]
    if flow_direction_type is not None:
        if flow_direction_type.upper() not in flow_direction_type_list:
            raise RuntimeError('flow_direction_type should be one of the following '+ str(flow_direction_type_list))
        template_dict["rasterFunctionArguments"]["flow_direction_type"] = flow_direction_type

    function_chain_ra = copy.deepcopy(template_dict)
    function_chain_ra['rasterFunctionArguments']["in_stream_raster"] = raster_ra1
    function_chain_ra['rasterFunctionArguments']["in_surface_raster"] = raster_ra2
    if input_flow_direction_raster is not None:
        function_chain_ra["rasterFunctionArguments"]["in_flow_direction_raster"] = raster_ra3

    return _gbl_clone_layer(layer1, template_dict, function_chain_ra)


def flow_accumulation(input_flow_direction_raster,
                      input_weight_raster=None,
                      data_type="FLOAT",                      
                      flow_direction_type= "D8"):
                     
    """"    
    Replaces cells of a raster corresponding to a mask 
    with the values of the nearest neighbors.

    :param input_flow_direction_raster: The input raster that shows the direction of flow out of each cell.
    :param input_weight_raster: An optional input raster for applying a weight to each cell.
    :param data_type: INTEGER, FLOAT, DOUBLE
    :return: output raster with function applied

    """
    layer1, input_flow_direction_raster, raster_ra1 = _raster_input(input_flow_direction_raster)  
            
    template_dict = {
        "rasterFunction" : "GPAdapter",
        "rasterFunctionArguments" : {
            "toolName" : "FlowAccumulation_sa",           
            "PrimaryInputParameterName" : "in_flow_direction_raster",
            "OutputRasterParameterName" : "out_accumulation_raster",
            "in_flow_direction_raster" : input_flow_direction_raster
             
        }
    }    
    if input_weight_raster is not None:
        layer2, input_weight_raster, raster_ra2 = _raster_input(input_weight_raster) 
        template_dict["rasterFunctionArguments"]["in_weight_raster"] = input_weight_raster

    data_type_list=["FLOAT","INTEGER","DOUBLE"]

    if data_type is not None:
        if data_type.upper() not in data_type_list:
            raise RuntimeError('data_type should be one of the following '+ str(data_type_list))
        template_dict["rasterFunctionArguments"]["data_type"] = data_type   
        
    flow_direction_type_list = ["D8","MFD","DINF"]
    if flow_direction_type is not None:
        if flow_direction_type.upper() not in flow_direction_type_list:
            raise RuntimeError('flow_direction_type should be one of the following '+ str(flow_direction_type_list))
        template_dict["rasterFunctionArguments"]["flow_direction_type"] = flow_direction_type
    
    function_chain_ra = copy.deepcopy(template_dict)
    function_chain_ra["rasterFunctionArguments"]["in_flow_direction_raster"] = raster_ra1    
    if input_weight_raster is not None:
        function_chain_ra['rasterFunctionArguments']["in_weight_raster"] = raster_ra2    

    return _gbl_clone_layer(layer1, template_dict, function_chain_ra)


def flow_direction(input_surface_raster,
                   force_flow= "NORMAL",
                   flow_direction_type= "D8",
                   generate_out_drop_raster=False):
    """
    Replaces cells of a raster corresponding to a mask 
    with the values of the nearest neighbors.

    Parameters
    ----------
    :param input_surface_raster: The input raster representing a continuous surface.
    :param force_flow: NORMAL or FORCE, Specifies if edge cells will always flow outward or follow normal flow rules.
    :param flow_direction_type: Specifies which flow direction type to use.
                          D8 - Use the D8 method. This is the default.
                          MFD - Use the Multi Flow Direction (MFD) method.
                          DINF - Use the D-Infinity method.
    :param generate_out_drop_raster: Boolean, determines whether out_drop_raster should be generated or not.
                                      Set this parameter to True, in order to generate the out_drop_raster.
                                      If set to true, the output will be a named tuple with name values being
                                      output_flow_direction_service and output_drop_service.
                                      eg,

                                      flow_direction_output =  flow_direction(input_surface_raster,
                                                                            force_flow= "NORMAL",
                                                                            flow_direction_type= "D8",
                                                                            generate_out_drop_raster=True)

                                      out_var = flow_direction_output.save()

                                      then,

                                      out_var.output_flow_direction_service -> gives you the output flow direction imagery layer item

                                      out_var.output_drop_service -> gives you the output drop raster imagery layer item


    :return: output raster with function applied

    """
    layer, input_surface_raster, raster_ra = _raster_input(input_surface_raster)  
            
    template_dict = {
        "rasterFunction" : "GPAdapter",
        "rasterFunctionArguments" : {
            "toolName" : "FlowDirection_sa",           
            "PrimaryInputParameterName" : "in_surface_raster",
            "OutputRasterParameterName" : "out_flow_direction_raster",
            "in_surface_raster" : input_surface_raster
        }
    }    
      
    force_flow_list = ["NORMAL","FORCE"]
    if force_flow is not None:
        if force_flow.upper() not in force_flow_list:
            raise RuntimeError('force_flow should be one of the following '+ str(force_flow_list))
        template_dict["rasterFunctionArguments"]["force_flow"] = force_flow
       

    flow_direction_type_list = ["D8","MFD","DINF"]
    if flow_direction_type is not None:
        if flow_direction_type.upper() not in flow_direction_type_list:
            raise RuntimeError('flow_direction_type should be one of the following '+ str(flow_direction_type_list))
        template_dict["rasterFunctionArguments"]["flow_direction_type"] = flow_direction_type
             

    function_chain_ra = copy.deepcopy(template_dict)
    function_chain_ra["rasterFunctionArguments"]["in_surface_raster"] = raster_ra    

    if generate_out_drop_raster is True:
        return _gbl_clone_layer(layer, template_dict, function_chain_ra, out_drop_raster = generate_out_drop_raster, use_ra=True)
    
    return _gbl_clone_layer(layer, template_dict, function_chain_ra, out_drop_raster = generate_out_drop_raster)

def fill(input_surface_raster,        
         zlimit=None):
    """
    Fills sinks in a surface raster to remove small imperfections in the data

    Parameters
    ----------
    :param input_surface_raster: The input raster representing a continuous surface.
    :param zlimit: Data type - Double. Maximum elevation difference between a sink and
            its pour point to be filled.
            If the difference in z-values between a sink and its pour point is greater than the z_limit, that sink will not be filled.
            The value for z-limit must be greater than zero.
            Unless a value is specified for this parameter, all sinks will be filled, regardless of depth.
    
    :return: output raster with function applied

    """
    layer, input_surface_raster, raster_ra = _raster_input(input_surface_raster)  
            
    template_dict = {
        "rasterFunction" : "GPAdapter",
        "rasterFunctionArguments" : {
            "toolName" : "Fill_sa",           
            "PrimaryInputParameterName" : "in_surface_raster",
            "OutputRasterParameterName" : "out_surface_raster",
            "in_surface_raster" : input_surface_raster            
             
        }
    }    
    
    if zlimit is not None:
        template_dict["rasterFunctionArguments"]["z_limit"] = zlimit
    
    function_chain_ra = copy.deepcopy(template_dict)
    function_chain_ra["rasterFunctionArguments"]["in_surface_raster"] = raster_ra    
    
    return _gbl_clone_layer(layer, template_dict, function_chain_ra)


def nibble(input_raster,
           input_mask_raster,
           nibble_values= "ALL_VALUES",
           nibble_no_data= "PRESERVE_NODATA",
           input_zone_raster=None):
    """
    Replaces cells of a raster corresponding to a mask 
    with the values of the nearest neighbors.

    Parameters
    ----------
    :param input_raster: The input rater to nibble.
                   The input raster can be either integer or floating point type.
    :param input_mask_raster: The input raster to use as the mask.
    :param nibble_values: possbile options are "ALL_VALUES" and "DATA_ONLY".
        Default is "ALL_VALUES"
    :param nibble_no_data: PRESERVE_NODATA or PROCESS_NODATA possible values;
        Default is PRESERVE_NODATA.
    :param input_zone_raster: The input raster that defines the zones to use as the mask.
    
    :return: output raster with function applied

    """
    layer1, input_raster, raster_ra1 = _raster_input(input_raster)
    layer2, input_mask_raster, raster_ra2 = _raster_input(input_mask_raster)  
            
    template_dict = {
        "rasterFunction" : "GPAdapter",
        "rasterFunctionArguments" : {
            "toolName" : "Nibble_sa",           
            "PrimaryInputParameterName" : "in_raster",
            "OutputRasterParameterName" : "out_raster",
            "in_raster" : input_raster,
            "in_mask_raster" : input_mask_raster,
            "nibble_values" : nibble_values,
            "nibble_nodata" : nibble_no_data
             
        }
    }    
    
    nibble_values_list = ["ALL_VALUES","DATA_ONLY"]
    if nibble_values is not None:
        if nibble_values.upper() not in nibble_values_list:
            raise RuntimeError('nibble_values should be one of the following '+ str(nibble_values_list))
        template_dict["rasterFunctionArguments"]["nibble_values"] = nibble_values


    nibble_no_data_list = ["PRESERVE_NODATA","PROCESS_NODATA"]
    if nibble_no_data is not None:
         if nibble_no_data.upper() not in nibble_no_data_list:
             raise RuntimeError('nibble_nodata should be one of the following '+ str(nibble_no_data_list))
         template_dict["rasterFunctionArguments"]["nibble_nodata"] = nibble_no_data

    if input_zone_raster is not None:
        layer3, input_zone_raster, raster_ra3 = _raster_input(input_zone_raster)
        template_dict["rasterFunctionArguments"]["in_zone_raster"] = input_zone_raster
    
    function_chain_ra = copy.deepcopy(template_dict)
    function_chain_ra["rasterFunctionArguments"]["in_raster"] = raster_ra1
    function_chain_ra["rasterFunctionArguments"]["in_mask_raster"] = raster_ra2
    if input_zone_raster is not None:
        function_chain_ra["rasterFunctionArguments"]["in_zone_raster"] = raster_ra3
    
    return _gbl_clone_layer(layer1, template_dict, function_chain_ra)


def stream_link(input_raster,
                input_flow_direction_raster):
    """
    Assigns unique values to sections of a raster linear network between intersections

    Parameters
    ----------
    :param input_raster:     An input raster that represents a linear stream network.
    :param input_flow_direction_raster: The input raster that shows the direction of flow out of each cell
    :return: output raster with function applied

    """
    layer1, input_raster, raster_ra1 = _raster_input(input_raster)
    layer2, input_flow_direction_raster, raster_ra2 = _raster_input(input_flow_direction_raster)  
            
    template_dict = {
        "rasterFunction" : "GPAdapter",
        "rasterFunctionArguments" : {
            "toolName" : "StreamLink_sa",           
            "PrimaryInputParameterName" : "in_stream_raster",
            "OutputRasterParameterName" : "out_raster",
            "in_stream_raster" : input_raster,
            "in_flow_direction_raster" : input_flow_direction_raster                 
        }
    }    
    
    
    function_chain_ra = copy.deepcopy(template_dict)
    function_chain_ra["rasterFunctionArguments"]["in_stream_raster"] = raster_ra1
    function_chain_ra["rasterFunctionArguments"]["in_flow_direction_raster"] = raster_ra2
        
    return _gbl_clone_layer(layer1, template_dict, function_chain_ra)


def watershed(input_flow_direction_raster,
              input_pour_point_data,
              pour_point_field=None):
    """
    Replaces cells of a raster corresponding to a mask 
    with the values of the nearest neighbors.

    Parameters
    ----------
    :param input_flow_direction_raster: The input raster that shows the direction of flow out of each cell.
    :param input_pour_point_data: The input pour point locations. For a raster, this represents cells above
                            which the contributing area, or catchment, will be determined. All cells that 
                            are not NoData will be used as source cells.
                            For a point feature dataset, this represents locations above which the contributing
                            area, or catchment, will be determined.
    :param pour_point_field: Field used to assign values to the pour point locations. If the pour point dataset is a
                       raster, use Value.
                       If the pour point dataset is a feature, use a numeric field. If the field contains 
                       floating-point values, they will be truncated into integers.    
    :return: output raster with function applied

    """
    layer1, input_flow_direction_raster, raster_ra1 = _raster_input(input_flow_direction_raster)  
    layer2, input_pour_point_data, raster_ra2 = _raster_input(input_pour_point_data)
            
    template_dict = {
        "rasterFunction" : "GPAdapter",
        "rasterFunctionArguments" : {
            "toolName" : "Watershed_sa",           
            "PrimaryInputParameterName" : "in_flow_direction_raster",
            "OutputRasterParameterName" : "out_raster",
            "in_flow_direction_raster" : input_flow_direction_raster,
            "in_pour_point_data" : input_pour_point_data
        }
    }    
    
    if pour_point_field is not None:
        template_dict["rasterFunctionArguments"]["pour_point_field"] = pour_point_field

    
    function_chain_ra = copy.deepcopy(template_dict)
    function_chain_ra["rasterFunctionArguments"]["in_flow_direction_raster"] = raster_ra1
    function_chain_ra["rasterFunctionArguments"]["in_pour_point_data"] = raster_ra2
        
    return _gbl_clone_layer(layer1, template_dict, function_chain_ra)


def calculate_travel_cost(in_source_data,
                          in_cost_raster=None,
                          in_surface_raster=None,
                          in_horizontal_raster=None,
                          in_vertical_raster=None,
                          horizontal_factor="BINARY",
                          vertical_factor="BINARY",
                          maximum_distance=None,
                          source_cost_multiplier=None,
                          source_start_cost=None,
                          source_resistance_rate=None,
                          source_capacity=None,
                          source_direction=None,
                          allocation_field=None,
                          generate_out_allocation_raster=False,
                          generate_out_backlink_raster=False):
    """

    Parameters
    ----------
    :param in_source_data:  The layer that defines the sources to calculate the distance too. The layer 
                            can be raster or feature.

    :param in_cost_raster:   A raster defining the impedance or cost to move planimetrically through each cell.

    :param in_surface_raster:  A raster defining the elevation values at each cell location.
    
    :param in_horizontal_raster:  A raster defining the horizontal direction at each cell.

    :param in_vertical_raster:  A raster defining the vertical (z) value for each cell.

    :param horizontal_factor:  The Horizontal Factor defines the relationship between the horizontal cost 
                               factor and the horizontal relative moving angle.
                               Possible values are: "BINARY", "LINEAR", "FORWARD", "INVERSE_LINEAR"

    :param vertical_factor:  The Vertical Factor defines the relationship between the vertical cost factor and 
                            the vertical relative moving angle (VRMA)
                            Possible values are: "BINARY", "LINEAR", "SYMMETRIC_LINEAR", "INVERSE_LINEAR",
                            "SYMMETRIC_INVERSE_LINEAR", "COS", "SEC", "COS_SEC", "SEC_COS"

    :param maximum_distance:  The maximum distance to calculate out to. If no distance is provided, a default will 
                             be calculated that is based on the locations of the input sources.

    :param source_cost_multiplier:  Multiplier to apply to the cost values.

    :param source_start_cost:  The starting cost from which to begin the cost calculations.

    :param source_resistance_rate:  This parameter simulates the increase in the effort to overcome costs 
                                    as the accumulative cost increases.

    :param source_capacity:  Defines the cost capacity for the traveler for a source.

    :param source_direction:  Defines the direction of the traveler when applying horizontal and vertical factors, 
                              the source resistance rate, and the source starting cost.
                              Possible values: FROM_SOURCE, TO_SOURCE

    :param allocation_field:  A field on theinputSourceRasterOrFeatures layer that holds the values that define each source.

    :param generate_out_backlink_raster:   Boolean, determines whether out_backlink_raster should be generated or not.
                                           Set this parameter to True, in order to generate the out_backlink_raster.
                                           If set to true, the output will be a named tuple with name values being
                                           output_distance_service and output_backlink_service.
                                           eg,
                                           out_layer = calculate_travel_cost(in_source_data
                                                                                generate_out_backlink_raster=True)
                                           out_var = out_layer.save()
                                           then,
                                           out_var.output_distance_service -> gives you the output distance imagery layer item
                                           out_var.output_backlink_service -> gives you the output backlink raster imagery layer item

    :param generate_out_allocation_raster:  Boolean, determines whether out_allocation_raster should be generated or not.
                                            Set this parameter to True, in order to generate the out_backlink_raster.
                                            If set to true, the output will be a named tuple with name values being
                                            output_distance_service and output_allocation_service.
                                            eg,
                                            out_layer = calculate_travel_cost(in_source_data
                                                                                generate_out_allocation_raster=False)
                                            out_var = out_layer.save()
                                            then,
                                            out_var.output_distance_service -> gives you the output distance imagery layer item
                                            out_var.output_allocation_service -> gives you the output allocation raster imagery layer item

    :param gis: Optional, the GIS on which this tool runs. If not specified, the active GIS is used.

    :return: output raster with function applied
    """
    if isinstance (in_source_data, ImageryLayer):
        layer1, input_source_data, raster_ra1 = _raster_input(in_source_data)
    else:
        raster_ra1 = _layer_input(in_source_data)
        input_source_data = raster_ra1
        layer1=raster_ra1


    if in_cost_raster is not None:
        layer2, in_cost_raster, raster_ra2 = _raster_input(in_cost_raster)
       
    if in_surface_raster is not None:
        layer3, in_surface_raster, raster_ra3 = _raster_input(in_surface_raster)
    if in_horizontal_raster is not None:
        layer4, in_horizontal_raster, raster_ra4 = _raster_input(in_horizontal_raster)
    if in_vertical_raster is not None:
        layer5, in_vertical_raster, raster_ra5 = _raster_input(in_vertical_raster)
            
    template_dict = {
        "rasterFunction" : "GPAdapter",
        "rasterFunctionArguments" : {
            "toolName" : "CalculateTravelCost_sa",
            "PrimaryInputParameterName" : "in_source_data",
            "OutputRasterParameterName":"out_distance_raster",
            "in_source_data" : input_source_data
        }
    }
    
    if in_cost_raster is not None:
        template_dict["rasterFunctionArguments"]["in_cost_raster"] = in_cost_raster

    if in_surface_raster is not None:
        template_dict["rasterFunctionArguments"]["in_surface_raster"] = in_surface_raster

    if in_horizontal_raster is not None:
        template_dict["rasterFunctionArguments"]["in_horizontal_raster"] = in_horizontal_raster

    if in_vertical_raster is not None:
        template_dict["rasterFunctionArguments"]["in_vertical_raster"] = in_vertical_raster

    horizontal_factor_list = ["BINARY", "LINEAR", "FORWARD", "INVERSE_LINEAR"]
    if horizontal_factor.upper() not in horizontal_factor_list:
        raise RuntimeError('horizontal_factor should be one of the following '+ str(horizontal_factor_list))
    template_dict["rasterFunctionArguments"]["horizontal_factor"] = horizontal_factor

    vertical_factor_list = ["BINARY", "LINEAR", "SYMMETRIC_LINEAR", "INVERSE_LINEAR",
                            "SYMMETRIC_INVERSE_LINEAR", "COS", "SEC", "COS_SEC", "SEC_COS"]
    if vertical_factor.upper() not in vertical_factor_list:
        raise RuntimeError('vertical_factor should be one of the following '+ str(vertical_factor_list))
    template_dict["rasterFunctionArguments"]["vertical_factor"] = vertical_factor

    if maximum_distance is not None:
        template_dict["rasterFunctionArguments"]["maximum_distance"] = maximum_distance

    if source_cost_multiplier is not None:
        template_dict["rasterFunctionArguments"]["source_cost_multiplier"] = source_cost_multiplier

    if source_start_cost is not None:
        template_dict["rasterFunctionArguments"]["source_start_cost"] = source_start_cost

    if source_resistance_rate is not None:
        template_dict["rasterFunctionArguments"]["source_resistance_rate"] = source_resistance_rate

    if source_capacity is not None:
        template_dict["rasterFunctionArguments"]["source_capacity"] = source_capacity

    if source_direction is not None:
        source_direction_list = ["FROM_SOURCE","TO_SOURCE"]
        if source_direction.upper() not in source_direction_list:
            raise RuntimeError('source_direction should be one of the following '+ str(source_direction_list) )
        template_dict["rasterFunctionArguments"]["source_direction"] = source_direction

    if allocation_field is not None:
        template_dict["rasterFunctionArguments"]["allocation_field"] = allocation_field

    function_chain_ra = copy.deepcopy(template_dict)
    function_chain_ra['rasterFunctionArguments']["in_source_data"] = raster_ra1
    if in_cost_raster is not None:
        function_chain_ra['rasterFunctionArguments']["in_cost_raster"] = raster_ra2

    if in_surface_raster is not None:
        function_chain_ra['rasterFunctionArguments']["in_surface_raster"] = raster_ra3

    if in_horizontal_raster is not None:
        function_chain_ra['rasterFunctionArguments']["in_horizontal_raster"] = raster_ra4

    if in_vertical_raster is not None:
        function_chain_ra['rasterFunctionArguments']["in_vertical_raster"] = raster_ra5

    if isinstance(in_source_data, ImageryLayer):
        return _gbl_clone_layer(in_source_data, template_dict, function_chain_ra, out_allocation_raster = generate_out_allocation_raster, out_backlink_raster = generate_out_backlink_raster, use_ra=True)
    else:
        return _feature_gbl_clone_layer(in_source_data, template_dict, function_chain_ra, out_allocation_raster = generate_out_allocation_raster, out_backlink_raster = generate_out_backlink_raster, use_ra=True)
        
def kernel_density(in_features,
                   population_field,
                   cell_size=None,
                   search_radius=None,
                   area_unit_scale_factor="SQUARE_MAP_UNITS",
                   out_cell_values="DENSITIES",
                   method="PLANAR"):
    """
    Calculates a magnitude-per-unit area from point or polyline features using a kernel function to 
    fit a smoothly tapered surface to each point or polyline. 
    For more information, see 
    http://pro.arcgis.com/en/pro-app/help/data/imagery/kernel-density-global-function.htm

    Parameters
    ----------
    :param in_features:               The input point or line features for which to calculate the density
    :param population_field:          Field denoting population values for each feature. The Population 
                                      Field is the count or quantity to be spread across the landscape to 
                                      create a continuous surface. Values in the population field may be 
                                      integer or floating point.
    :param cell_size:                 The pixel size for the output raster dataset. If the Cellsize has 
                                      been set in the geoprocessing Environments it will be the default.
    :param search_radius:             The search radius within which to calculate density. Units are 
                                      based on the linear unit of the projection.
    :param area_unit_scale_factor:    The desired area units of the output density values.
                                        -SQUARE_MAP_UNITS-For the square of the linear units of the output spatial reference.
                                        
                                        -SQUARE_MILES-For (U.S.) miles.
                                        
                                        -SQUARE_KILOMETERS-For kilometers.
                                        
                                        -ACRES For (U.S.) acres.
                                        
                                        -HECTARES-For hectares.
                                        
                                        -SQUARE_METERS-For meters.
                                        
                                        -SQUARE_YARDS-For (U.S.) yards.
                                        
                                        -SQUARE_FEET-For (U.S.) feet.
                                        
                                        -SQUARE_INCHES-For (U.S.) inches.
                                        
                                        -SQUARE_CENTIMETERS-For centimeters.
                                        
                                        -SQUARE_MILLIMETERS-For millimeters.
    :param out_cell_values:           Determines what the values in the output raster represent.

                                       -DENSITIES-The output values represent the predicted density value. This is the default.

                                       -EXPECTED_COUNTS-The output values represent the predicted amount of the phenomenon within each 
                                        pixel. Since the pixel value is linked to the specified Cellsize, the resulting raster cannot be 
                                        resampled to a different pixel size and still represent the amount of the phenomenon.

    :param method:                    Determines whether to use a shortest path on a spheroid (geodesic) or a flat earth (planar) method.

                                        -PLANAR-Uses planar distances between the features. This is the default.

                                        -GEODESIC-Uses geodesic distances between features. This method takes into account the curvature 
                                        of the spheroid and correctly deals with data near the poles and the International dateline.

    :return:                          output raster
    """

    input_features = _layer_input(in_features)
        
    template_dict = {
        "rasterFunction" : "GPAdapter",
        "rasterFunctionArguments" : {
            "toolName" : "KernelDensity_sa",           
            "PrimaryInputParameterName":"in_features",
            "OutputRasterParameterName":"out_raster",
            "in_features": input_features,
            "population_field":population_field,
            "RasterInfo":{"blockWidth" : 2048,
                          "blockHeight":256,
                          "bandCount":1,
                          "pixelType":9,
                          "firstPyramidLevel":1,
                          "maximumPyramidLevel":30,
                          "pixelSizeX":0,
                          "pixelSizeY" :0,
                          "type":"RasterInfo"}
        }
    }

    if search_radius is not None:
        template_dict["rasterFunctionArguments"]["search_radius"] = search_radius

    if cell_size is not None:
        template_dict["rasterFunctionArguments"]["cell_size"] = cell_size
    
    if area_unit_scale_factor is not None: 
        area_unit_scale_factor_list = ["SQUARE_MAP_UNITS","SQUARE_MILES", "SQUARE_KILOMETERS", "ACRES","HECTARES","SQUARE_METERS","SQUARE_YARDS"
                                       "SQUARE_FEET","SQUARE_INCHES", "SQUARE_CENTIMETERS","SQUARE_MILLIMETERS"]
        if area_unit_scale_factor.upper() not in area_unit_scale_factor_list:
            raise RuntimeError('area_unit_scale_factor should be one of the following '+ str(area_unit_scale_factor_list))
        template_dict["rasterFunctionArguments"]["area_unit_scale_factor"] = area_unit_scale_factor

    out_cell_values_list = ["DENSITIES", "EXPECTED_COUNTS"]
    if out_cell_values.upper() not in out_cell_values_list:
        raise RuntimeError('out_cell_values should be one of the following '+ str(out_cell_values_list))
    template_dict["rasterFunctionArguments"]["out_cell_values"] = out_cell_values

    method_list = ["PLANAR", "GEODESIC"]
    if method.upper() not in method_list:
        raise RuntimeError('method should be one of the following '+ str(method_list))
    template_dict["rasterFunctionArguments"]["method"] = method

    if isinstance(in_features, Item):
        in_features = in_features.layers[0]
    newlyr = ImageryLayer(in_features._url, in_features._gis)
    newlyr._fn = template_dict
    newlyr._fnra = template_dict
    newlyr._uses_gbl_function = True
    return newlyr


def cost_path(in_destination_data,
              in_cost_distance_raster,
              in_cost_backlink_raster,
              path_type="EACH_CELL",
              destination_field=None,
             ):
    """
    Calculates the least-cost path from a source to a destination.

    Parameters
    ----------
    :param in_destination_data:     A raster or feature dataset that identifies those cells from which the least-cost 
                                    path is determined to the least costly source. If the input is a raster, the input 
                                    consists of cells that have valid values (zero is a valid value), and the remaining 
                                    cells must be assigned NoData.
    :param in_cost_distance_raster: The name of a cost distance raster to be used to determine the least-cost path from 
                                    the destination locations to a source. The cost distance raster is usually created 
                                    with the Cost Distance, Cost Allocation or Cost Back Link tools. The cost distance 
                                    raster stores, for each cell, the minimum accumulative cost distance over a cost 
                                    surface from each cell to a set of source cells.
    :param in_cost_backlink_raster: The name of a cost back link raster used to determine the path to return to a source 
                                    via the least-cost path. For each cell in the back link raster, a value identifies 
                                    the neighbor that is the next cell on the least accumulative cost path from the cell
                                    to a single source cell or set of source cells.
    :param path_type:               A keyword defining the manner in which the values and zones on the input destination 
                                    data will be interpreted in the cost path calculations.
                                    EACH_CELL — For each cell with valid values on the input destination data, a least-cost
                                    path is determined and saved on the output raster. With this option, each cell of the 
                                    input destination data is treated separately, and a least-cost path is determined for 
                                    each from cell.
                                    EACH_ZONE — For each zone on the input destination data, a least-cost path is determined
                                    and saved on the output raster. With this option, the least-cost path for each zone 
                                    begins at the cell with the lowest cost distance weighting in the zone.
                                    BEST_SINGLE — For all cells on the input destination data, the least-cost path is derived 
                                    from the cell with the minimum of the least-cost paths to source cells.
    :param destination_field:       The field used to obtain values for the destination locations. Input feature data must 
                                    contain at least one valid field.
    
    :return: output raster with function applied
    """        
    layer1, in_destination_data, raster_ra1 = _raster_input(in_destination_data)  
    layer2, in_cost_distance_raster, raster_ra2 = _raster_input(in_cost_distance_raster)
    layer3,  in_cost_backlink_raster, raster_ra3 = _raster_input(in_cost_backlink_raster)
    
    template_dict = {
        "rasterFunction" : "GPAdapter",
        "rasterFunctionArguments" : {
            "toolName" : "CostPath_sa",           
            "PrimaryInputParameterName":"in_destination_data",
            "OutputRasterParameterName":"out_raster",
            "in_destination_data": in_destination_data, 
            "in_cost_distance_raster": in_cost_distance_raster,
            "in_cost_backlink_raster": in_cost_backlink_raster   
        }
    }    

    if path_type is not None:
        path_type_list = ["EACH_CELL", "EACH_ZONE", "BEST_SINGLE"]
        if path_type.upper() not in path_type_list:
            raise RuntimeError('path_type should be one of the following '+ str(path_type_list))
        template_dict["rasterFunctionArguments"]["path_type"] = path_type
    
    if destination_field is not None:
        template_dict["rasterFunctionArguments"]["destination_field"] = destination_field

    function_chain_ra = copy.deepcopy(template_dict)
    function_chain_ra["rasterFunctionArguments"]["in_destination_data"] = raster_ra1
    function_chain_ra["rasterFunctionArguments"]["in_cost_distance_raster"] = raster_ra2
    function_chain_ra["rasterFunctionArguments"]["in_cost_backlink_raster"] = raster_ra3

    return _gbl_clone_layer(layer1, template_dict, function_chain_ra)

def euclidean_direction (in_source_data,
                         cell_size=None,
                         max_distance=None,
                         distance_method="PLANAR"):
    """
    Calculates, for each cell, the Euclidean distance to the closest source. 

    Parameters
    ----------
    :param in_source_data:  The input source locations. This is a raster or feature dataset that 
                            identifies the cells or locations to which the Euclidean distance for 
                            every output cell location is calculated. For rasters, the input type 
                            can  be integer or floating point.
    :param cell_size:       Defines the threshold that the accumulative distance values cannot 
                            exceed. If an accumulative Euclidean distance value exceeds this 
                            value, the output value for the cell location will be NoData. The default
                            distance is to the edge of the output raster.
    :param max_distance:    The cell size at which the output raster will be created. This will be the
                            value in the environment if it is explicitly set. If it is not set in the 
                            environment, the default cell size will depend on if the input source data 
                            is a raster or a feature, as follows: If the source is raster, the output 
                            will have that same cell size. If the source is feature, the output will 
                            have a cell size determined by the shorter of the width or height of the 
                            extent of input feature, in the input spatial reference, divided by 250.
    :return: output raster with function applied
    """
    layer, in_source_data, raster_ra = _raster_input(in_source_data)
                  
    template_dict = {
        "rasterFunction" : "GPAdapter",
        "rasterFunctionArguments" : {
            "toolName" : "EucDirection_sa",           
            "PrimaryInputParameterName":"in_source_data",
            "OutputRasterParameterName":"out_direction_raster",
            "in_source_data": in_source_data,
                
        }
    }
    
    if cell_size is not None:
        template_dict["rasterFunctionArguments"]["cell_size"] = cell_size
    
    if max_distance is not None:
        template_dict["rasterFunctionArguments"]["maximum_distance"] = max_distance

    distance_method_list = ["PLANAR","GEODESIC"]
    if distance_method is not None:
        if distance_method.upper() not in distance_method_list:
            raise RuntimeError('distance_method should be one of the following '+ str(distance_method_list))
        template_dict["rasterFunctionArguments"]["distance_method"] = distance_method

    function_chain_ra = copy.deepcopy(template_dict)
    function_chain_ra["rasterFunctionArguments"]["in_source_data"] = raster_ra

    return _gbl_clone_layer(layer, template_dict, function_chain_ra)

def cost_backlink(in_source_data,
                  in_cost_raster,
                  max_distance=None,
                  source_cost_multiplier=None,
                  source_start_cost=None,
                  source_resistance_rate=None,
                  source_capacity=None,
                  source_direction=None):
    """
    Calculates the least accumulative cost distance for each cell from or to the least-cost
    source over a cost surface.

    Parameters
    ----------
    :param in_source_data: The input raster that identifies the pixels or locations to which the
                            least accumulated cost distance for every output pixel location is 
                            calculated. The Source Raster can be an integer or a floating-point value.
    :param in_cost_raster: A raster defining the cost or impedance to move planimetrically through each pixel.
                            The value at each pixel location represents the cost-per-unit distance for moving 
                            through it. Each pixel location value is multiplied by the pixel resolution, while 
                            also compensating for diagonal movement to obtain the total cost of passing through 
                            the pixel. 
    :param max_distance: The threshold that the accumulative cost values cannot exceed. If an accumulative cost
                            distance exceeds this value, the output value for the pixel location will be NoData. 
                            The maximum distance defines the extent for which the accumulative cost distances are
                            calculated. The default distance is to the edge of the output raster.
    :param source_cost_multiplier: The threshold that the accumulative cost values cannot exceed. If an accumulative
                            cost distance exceeds this value, the output value for the pixel location will be 
                            NoData. The maximum distance defines the extent for which the accumulative cost 
                            distances are calculated. The default distance is to the edge of the output raster.
    :param source_start_cost: The starting cost from which to begin the cost calculations. This parameter allows
                            for the specification of the fixed cost associated with a source. Instead of starting
                            at a cost of 0, the cost algorithm will begin with the value set here.
                            The default is 0. The value must be 0 or greater. A numeric (double) value or a field
                            from the Source Raster can be used for this parameter.
    :param source_resistance_rate: This parameter simulates the increase in the effort to overcome costs as the
                            accumulative cost increases. It is used to model fatigue of the traveler. The growing
                            accumulative cost to reach a pixel is multiplied by the resistance rate and added to 
                            the cost to move into the subsequent pixel.
                            It is a modified version of a compound interest rate formula that is used to calculate
                            the apparent cost of moving through a pixel. As the value of the resistance rate increases,
                            it increases the cost of the pixels that are visited later. The greater the resistance rate, 
                            the higher the cost to reach the next pixel, which is compounded for each subsequent movement. 
                            Since the resistance rate is similar to a compound rate and generally the accumulative cost 
                            values are very large, small resistance rates are suggested, such as 0.005 or even smaller, 
                            depending on the accumulative cost values.
                            The default is 0. The values must be 0 or greater. A numeric (double) value or a field from
                            the Source Raster can be used for this parameter.
    :param source_capacity: Defines the cost capacity for the traveler for a source. The cost calculations continue for
                            each source until the specified capacity is reached.
                            The default capacity is to the edge of the output raster. The values must be greater than 0. 
                            A double numeric value or a field from the Source Raster can be used for this parameter.
    :param source_direction: Defines the direction of the traveler when applying the source resistance rate and the source
                            starting cost.
                            FROM_SOURCE - The source resistance rate and source starting cost will be applied beginning
                            at the input source and moving out to the nonsource cells. This is the default.
                            TO_SOURCE - The source resistance rate and source starting cost will be applied beginning at
                            each nonsource cell and moving back to the input source.
                            Either specify the From Source or To Source keyword, which will be applied to all sources,
                            or specify a field in the Source Raster that contains the keywords to identify the direction
                            of travel for each source. That field must contain the string From Source or To Source.
    
    :return: output raster with function applied
    """        
    layer1, in_source_data, raster_ra1 = _raster_input(in_source_data)  
    layer2, in_cost_raster, raster_ra2 = _raster_input(in_cost_raster)
                            
    template_dict = {
        "rasterFunction" : "GPAdapter",
        "rasterFunctionArguments" : {
            "toolName" : "CostBackLink_sa",           
            "PrimaryInputParameterName":"in_source_data",
            "OutputRasterParameterName":"out_backlink_raster",
            "in_source_data": in_source_data, 
            "in_cost_raster": in_cost_raster
             
        }
    }    
    
    if max_distance is not None:
        template_dict["rasterFunctionArguments"]["maximum_distance"] = max_distance
    
    if source_cost_multiplier is not None:
        template_dict["rasterFunctionArguments"]["source_cost_multiplier"] = source_cost_multiplier
    
    if source_start_cost is not None:
        template_dict["rasterFunctionArguments"]["source_start_cost"] = source_start_cost
    
    if source_resistance_rate is not None:
        template_dict["rasterFunctionArguments"]["source_resistance_rate"] = source_resistance_rate
    
    if source_capacity is not None:
        template_dict["rasterFunctionArguments"]["source_capacity"] = source_capacity
    
    if source_direction is not None:
        source_direction_list = ["FROM_SOURCE","TO_SOURCE"]
        if source_direction.upper() not in source_direction_list:
            raise RuntimeError('source_direction should be one of the following '+ str(source_direction_list) )
        template_dict["rasterFunctionArguments"]["source_direction"] = source_direction
    
    function_chain_ra = copy.deepcopy(template_dict)
    function_chain_ra["rasterFunctionArguments"]["in_source_data"] = raster_ra1
    function_chain_ra["rasterFunctionArguments"]["in_cost_raster"] = raster_ra2

    return _gbl_clone_layer(layer1, template_dict, function_chain_ra)


def region_group(in_raster,
                 number_of_neighbor_cells="FOUR",
                 zone_connectivity="WITHIN",
                 add_link = "ADD_LINK",
                 excluded_value = 0):
    """
    For each cell in the output, the identity of the connected region to which that cell 
    belongs is recorded. A unique number is assigned to each region.

    Parameters
    ----------
    :param in_raster:  Required, the input raster whose unique connected regions will be identified.
                       It must be of integer type.

    :param number_of_neighbor_cells: Optional. The number of neighboring cells to use in evaluating connectivity between cells.
                                     Possible values - FOUR, EIGHT. Default is FOUR
    
    :param zone_connectivity:  Optional. Defines which cell values should be considered when testing for connectivity.
                               Possible values - WITHIN, CROSS. Default is WITHIN

    :param add_link: Optional, Specifies whether a link field is added to the table of the output.
                     Possible values - ADD_LINK, NO_LINK. Default is ADD_LINK

    :param excluded_value: Identifies a value such that if a cell location contains the value, no spatial
                           connectivity will be evaluated regardless how the number of neighbors is specified (FOUR or EIGHT).
                           
                           Cells with the excluded value will be treated as NoData and are eliminated from calculations.
                           Cell locations that contain the excluded value will receive 0 on the output raster.

                           The excluded value is similar to the concept of a background value,
                           or setting a mask in the environment for a single run of the tool.
                           A value must be specified for this parameter if the CROSS keyword is specified
    
    :return: output raster with function applied
    """
    layer, in_raster, raster_ra = _raster_input(in_raster)
                  
    template_dict = {
        "rasterFunction" : "GPAdapter",
        "rasterFunctionArguments" : {
            "toolName" : "RegionGroup_sa",           
            "PrimaryInputParameterName":"in_raster",
            "OutputRasterParameterName":"out_raster",
            "in_raster": in_raster,
                
        }
    }
    
    if number_of_neighbor_cells is not None:
        if number_of_neighbor_cells.upper() == "EIGHT" or number_of_neighbor_cells.upper() == "FOUR":
            template_dict["rasterFunctionArguments"]["number_neighbors"] = number_of_neighbor_cells.upper()
        else:
            raise RuntimeError("number_of_neighbor_cells should either be 'EIGHT' or 'FOUR' ")
    
    if zone_connectivity is not None:
        if zone_connectivity.upper() == "WITHIN" or zone_connectivity.upper() == "CROSS":
            template_dict["rasterFunctionArguments"]["zone_connectivity"] = zone_connectivity.upper()
        else:
            raise RuntimeError("zone_connectivity should either be 'WITHIN' or 'CROSS' ")

    if add_link is not None:
        if add_link.upper() == "ADD_LINK" or add_link.upper() == "NO_LINK":
            template_dict["rasterFunctionArguments"]["add_link"] = add_link.upper()
        else:
            raise RuntimeError("add_link should either be 'ADD_LINK' or 'NO_LINK' ")

    if excluded_value is not None:
        template_dict["rasterFunctionArguments"]["excluded_value"] = excluded_value

    function_chain_ra = copy.deepcopy(template_dict)
    function_chain_ra["rasterFunctionArguments"]["in_raster"] = raster_ra

    return _gbl_clone_layer(layer, template_dict, function_chain_ra)


def corridor(in_distance_raster1,
             in_distance_raster2):
    """
    Calculates the sum of accumulative costs for two input accumulative cost rasters. 

    Parameters
    ----------
    :param in_distance_raster1: The first input distance raster. 
                                It should be an accumulated cost distance output from a distance function
                                such as cost_distance or path_distance.


    :param in_distance_raster2: The second input distance raster.
                                It should be an accumulated cost distance output from a distance function 
                                such as cost_distance or path_distance.

    :return: output raster with function applied
    """
    layer1, in_distance_raster1, raster_ra1 = _raster_input(in_distance_raster1)  
    layer2, in_distance_raster2, raster_ra2 = _raster_input(in_distance_raster2)
    
    template_dict = {
        "rasterFunction" : "GPAdapter",
        "rasterFunctionArguments" : {
            "toolName" : "Corridor_sa",           
            "PrimaryInputParameterName":"in_distance_raster1",
            "OutputRasterParameterName":"out_raster",
            "in_distance_raster1": in_distance_raster1, 
            "in_distance_raster2": in_distance_raster2
             
        }
    }    
    
    function_chain_ra = copy.deepcopy(template_dict)
    function_chain_ra["rasterFunctionArguments"]["in_distance_raster1"] = raster_ra1
    function_chain_ra["rasterFunctionArguments"]["in_distance_raster2"] = raster_ra2

    return _gbl_clone_layer(layer1, template_dict, function_chain_ra)


def path_distance(in_source_data,
                  in_cost_raster=None,
                  in_surface_raster=None,
                  in_horizontal_raster=None,
                  in_vertical_raster=None,
                  horizontal_factor="BINARY",
                  vertical_factor="BINARY",
                  maximum_distance=None,
                  source_cost_multiplier=None,
                  source_start_cost=None,
                  source_resistance_rate=None,
                  source_capacity=None,
                  source_direction=None):
    """
    Calculates, for each cell, the least accumulative cost distance from or to the least-cost source, 
    while accounting for surface distance along with horizontal and vertical cost factors

    Parameters
    ----------
    :param in_source_data:  The input source locations. 
                            This is a raster that identifies the cells or locations from or to which the 
                            least accumulated cost distance for every output cell location is calculated.

                            The raster input type can be integer or floating point.

    :param in_cost_raster:   A raster defining the impedance or cost to move planimetrically through each cell.
                             The value at each cell location represents the cost-per-unit distance for moving through the cell. 
                             Each cell location value is multiplied by the cell resolution while also 
                             compensating for diagonal movement to obtain the total cost of passing through the cell. 
                             The values of the cost raster can be integer or floating point, 
                             but they cannot be negative or zero (you cannot have a negative or zero cost).

    :param in_surface_raster:  A raster defining the elevation values at each cell location.
                               The values are used to calculate the actual surface distance covered when 
                               passing between cells.
    
    :param in_horizontal_raster: A raster defining the horizontal direction at each cell.
                                 The values on the raster must be integers ranging from 0 to 360, with 0 degrees being north, 
                                 or toward the top of the screen, and increasing clockwise. Flat areas should be given a value of -1. 
                                 The values at each location will be used in conjunction with the {horizontal_factor} to determine 
                                 the horizontal cost incurred when moving from a cell to its neighbors.

    :param in_vertical_raster:  A raster defining the vertical (z) value for each cell. The values are used for calculating the slope 
                                used to identify the vertical factor incurred when moving from one cell to another.

    :param horizontal_factor:  The Horizontal Factor defines the relationship between the horizontal cost 
                               factor and the horizontal relative moving angle.
                               Possible values are: "BINARY", "LINEAR", "FORWARD", "INVERSE_LINEAR"

    :param vertical_factor: The Vertical Factor defines the relationship between the vertical cost factor and 
                            the vertical relative moving angle (VRMA)
                            Possible values are: "BINARY", "LINEAR", "SYMMETRIC_LINEAR", "INVERSE_LINEAR",
                            "SYMMETRIC_INVERSE_LINEAR", "COS", "SEC", "COS_SEC", "SEC_COS"

    :param maximum_distance:  Defines the threshold that the accumulative cost values cannot exceed. 
                              If an accumulative cost distance value exceeds this value, the output value for the cell 
                              location will be NoData. The maximum distance defines the extent for which the accumulative cost distances are calculated.

                              The default distance is to the edge of the output raster.

    :param source_cost_multiplier:  Multiplier to apply to the cost values.

    :param source_start_cost: The starting cost from which to begin the cost calculations.

    :param source_resistance_rate:  This parameter simulates the increase in the effort to overcome costs 
                                    as the accumulative cost increases.  It is used to model fatigue of the traveler. 
                                    The growing accumulative cost to reach a cell is multiplied by the resistance rate 
                                    and added to the cost to move into the subsequent cell.

    :param source_capacity:  Defines the cost capacity for the traveler for a source. 
                             The cost calculations continue for each source until the specified capacity is reached.
                             The values must be greater than zero. The default capacity is to the edge of the output raster.

    :param source_direction:  Defines the direction of the traveler when applying horizontal and vertical factors, 
                              the source resistance rate, and the source starting cost.
                              Possible values: FROM_SOURCE, TO_SOURCE

    :return: output raster with function applied
    """
    layer1, input_source_data, raster_ra1 = _raster_input(in_source_data)

    if in_cost_raster is not None:
        layer2, in_cost_raster, raster_ra2 = _raster_input(in_cost_raster)
       
    if in_surface_raster is not None:
        layer3, in_surface_raster, raster_ra3 = _raster_input(in_surface_raster)
    if in_horizontal_raster is not None:
        layer4, in_horizontal_raster, raster_ra4 = _raster_input(in_horizontal_raster)
    if in_vertical_raster is not None:
        layer5, in_vertical_raster, raster_ra5 = _raster_input(in_vertical_raster)
            
    template_dict = {
        "rasterFunction" : "GPAdapter",
        "rasterFunctionArguments" : {
            "toolName" : "PathDistance_sa",
            "PrimaryInputParameterName" : "in_source_data",
            "OutputRasterParameterName":"out_distance_raster",
            "in_source_data" : input_source_data
        }
    }
    
    if in_cost_raster is not None:
        template_dict["rasterFunctionArguments"]["in_cost_raster"] = in_cost_raster

    if in_surface_raster is not None:
        template_dict["rasterFunctionArguments"]["in_surface_raster"] = in_surface_raster

    if in_horizontal_raster is not None:
        template_dict["rasterFunctionArguments"]["in_horizontal_raster"] = in_horizontal_raster

    if in_vertical_raster is not None:
        template_dict["rasterFunctionArguments"]["in_vertical_raster"] = in_vertical_raster

    horizontal_factor_list = ["BINARY", "LINEAR", "FORWARD", "INVERSE_LINEAR"]
    if horizontal_factor is not None:
        if horizontal_factor.upper() not in horizontal_factor_list:
            raise RuntimeError('horizontal_factor should be one of the following '+ str(horizontal_factor_list))
        template_dict["rasterFunctionArguments"]["horizontal_factor"] = horizontal_factor

    vertical_factor_list = ["BINARY", "LINEAR", "SYMMETRIC_LINEAR", "INVERSE_LINEAR",
                            "SYMMETRIC_INVERSE_LINEAR", "COS", "SEC", "COS_SEC", "SEC_COS"]
    if vertical_factor is not None:
        if vertical_factor.upper() not in vertical_factor_list:
            raise RuntimeError('vertical_factor should be one of the following '+ str(vertical_factor_list))
        template_dict["rasterFunctionArguments"]["vertical_factor"] = vertical_factor

    if maximum_distance is not None:
        template_dict["rasterFunctionArguments"]["maximum_distance"] = maximum_distance

    if source_cost_multiplier is not None:
        template_dict["rasterFunctionArguments"]["source_cost_multiplier"] = source_cost_multiplier

    if source_start_cost is not None:
        template_dict["rasterFunctionArguments"]["source_start_cost"] = source_start_cost

    if source_resistance_rate is not None:
        template_dict["rasterFunctionArguments"]["source_resistance_rate"] = source_resistance_rate

    if source_capacity is not None:
        template_dict["rasterFunctionArguments"]["source_capacity"] = source_capacity

    if source_direction is not None:
        source_direction_list = ["FROM_SOURCE","TO_SOURCE"]
        if source_direction is not None:
            if source_direction.upper() not in source_direction_list:
                raise RuntimeError('source_direction should be one of the following '+ str(source_direction_list) )
            template_dict["rasterFunctionArguments"]["source_direction"] = source_direction

    function_chain_ra = copy.deepcopy(template_dict)
    function_chain_ra['rasterFunctionArguments']["in_source_data"] = raster_ra1
    if in_cost_raster is not None:
        function_chain_ra['rasterFunctionArguments']["in_cost_raster"] = raster_ra2

    if in_surface_raster is not None:
        function_chain_ra['rasterFunctionArguments']["in_surface_raster"] = raster_ra3

    if in_horizontal_raster is not None:
        function_chain_ra['rasterFunctionArguments']["in_horizontal_raster"] = raster_ra4

    if in_vertical_raster is not None:
        function_chain_ra['rasterFunctionArguments']["in_vertical_raster"] = raster_ra5


    return _gbl_clone_layer(in_source_data, template_dict, function_chain_ra)


def path_distance_allocation(in_source_data,
                  in_cost_raster=None,
                  in_surface_raster=None,
                  in_horizontal_raster=None,
                  in_vertical_raster=None,
                  horizontal_factor="BINARY",
                  vertical_factor="BINARY",
                  maximum_distance=None,
                  in_value_raster=None,
                  source_field = None,  
                  source_cost_multiplier=None,
                  source_start_cost=None,
                  source_resistance_rate=None,
                  source_capacity=None,
                  source_direction=None):

    """
    Calculates the least-cost source for each cell based on the least accumulative cost over a cost surface, 
    while accounting for surface distance along with horizontal and vertical cost factors.

    Parameters
    ----------
    :param in_source_data:  The input source locations.
                            This is a raster or feature dataset that identifies the cells or locations from or to which 
                            the least accumulated cost distance for every output cell location is calculated.

                            For rasters, the input type can be integer or floating point.

                            If the input source raster is floating point, the {in_value_raster} must be set, and it must be of integer type. 
                            The value raster will take precedence over any setting of the {source_field}.

    :param in_cost_raster:   A raster defining the impedance or cost to move planimetrically through each cell.

    :param in_surface_raster:  A raster defining the elevation values at each cell location.
    
    :param in_horizontal_raster:  A raster defining the horizontal direction at each cell.

    :param in_vertical_raster:  A raster defining the vertical (z) value for each cell.

    :param horizontal_factor:  The Horizontal Factor defines the relationship between the horizontal cost 
                               factor and the horizontal relative moving angle.
                               Possible values are: "BINARY", "LINEAR", "FORWARD", "INVERSE_LINEAR"

    :param vertical_factor: The Vertical Factor defines the relationship between the vertical cost factor and 
                            the vertical relative moving angle (VRMA)
                            Possible values are: "BINARY", "LINEAR", "SYMMETRIC_LINEAR", "INVERSE_LINEAR",
                            "SYMMETRIC_INVERSE_LINEAR", "COS", "SEC", "COS_SEC", "SEC_COS"

    :param maximum_distance: Defines the threshold that the accumulative cost values cannot exceed.

    :param in_value_raster:  The input integer raster that identifies the zone values that should be 
                             used for each input source location.
                             For each source location (cell or feature), the value defined by the {in_value_raster} will be 
                             assigned to all cells allocated to the source location for the computation. 
                             The value raster will take precedence over any setting for the {source_field}.

    :param source_field:   The field used to assign values to the source locations. It must be of integer type.
                           If the {in_value_raster} has been set, the values in that input will have precedence over any setting for the {source_field}.

    :param source_cost_multiplier:  Multiplier to apply to the cost values.
                                    Allows for control of the mode of travel or the magnitude at a source. The greater the multiplier, 
                                    the greater the cost to move through each cell.

                                    The values must be greater than zero. The default is 1.

    :param source_start_cost:   The starting cost from which to begin the cost calculations. 
                                Allows for the specification of the fixed cost associated with a source. Instead of starting at a cost of zero, 
                                the cost algorithm will begin with the value set by source_start_cost.

                                The values must be zero or greater. The default is 0.

    :param source_resistance_rate:  This parameter simulates the increase in the effort to overcome costs as the accumulative cost increases. 
                                    It is used to model fatigue of the traveler. The growing accumulative cost to reach a cell is multiplied by 
                                    the resistance rate and added to the cost to move into the subsequent cell.

    :param source_capacity:  Defines the cost capacity for the traveler for a source. 
                             The cost calculations continue for each source until the specified capacity is reached.

                             The values must be greater than zero. The default capacity is to the edge of the output raster.

    :param source_direction:  Defines the direction of the traveler when applying horizontal and vertical factors, 
                              the source resistance rate, and the source starting cost.
                              Possible values: FROM_SOURCE, TO_SOURCE

    :return: output raster with function applied
    """
    
    layer1, input_source_data, raster_ra1 = _raster_input(in_source_data)

    if in_cost_raster is not None:
        layer2, in_cost_raster, raster_ra2 = _raster_input(in_cost_raster)
       
    if in_surface_raster is not None:
        layer3, in_surface_raster, raster_ra3 = _raster_input(in_surface_raster)
    if in_horizontal_raster is not None:
        layer4, in_horizontal_raster, raster_ra4 = _raster_input(in_horizontal_raster)
    if in_vertical_raster is not None:
        layer5, in_vertical_raster, raster_ra5 = _raster_input(in_vertical_raster)
            
    template_dict = {
        "rasterFunction" : "GPAdapter",
        "rasterFunctionArguments" : {
            "toolName" : "PathAllocation_sa",
            "PrimaryInputParameterName" : "in_source_data",
            "OutputRasterParameterName":"out_allocation_raster",
            "in_source_data" : input_source_data
        }
    }
    
    if in_cost_raster is not None:
        template_dict["rasterFunctionArguments"]["in_cost_raster"] = in_cost_raster

    if in_surface_raster is not None:
        template_dict["rasterFunctionArguments"]["in_surface_raster"] = in_surface_raster

    if in_horizontal_raster is not None:
        template_dict["rasterFunctionArguments"]["in_horizontal_raster"] = in_horizontal_raster

    if in_vertical_raster is not None:
        template_dict["rasterFunctionArguments"]["in_vertical_raster"] = in_vertical_raster

    horizontal_factor_list = ["BINARY", "LINEAR", "FORWARD", "INVERSE_LINEAR"]
    if horizontal_factor is not None:
        if horizontal_factor.upper() not in horizontal_factor_list:
            raise RuntimeError('horizontal_factor should be one of the following '+ str(horizontal_factor_list))
        template_dict["rasterFunctionArguments"]["horizontal_factor"] = horizontal_factor

    vertical_factor_list = ["BINARY", "LINEAR", "SYMMETRIC_LINEAR", "INVERSE_LINEAR",
                            "SYMMETRIC_INVERSE_LINEAR", "COS", "SEC", "COS_SEC", "SEC_COS"]
    if vertical_factor is not None:
        if vertical_factor.upper() not in vertical_factor_list:
            raise RuntimeError('vertical_factor should be one of the following '+ str(vertical_factor_list))
        template_dict["rasterFunctionArguments"]["vertical_factor"] = vertical_factor

    if maximum_distance is not None:
        template_dict["rasterFunctionArguments"]["maximum_distance"] = maximum_distance

    if in_value_raster is not None:
        layer6, in_value_raster, raster_ra6 = _raster_input(in_value_raster)
        template_dict["rasterFunctionArguments"]["in_value_raster"] = in_value_raster

    if source_field is not None:
        template_dict["rasterFunctionArguments"]["source_field"] = source_field

    if source_cost_multiplier is not None:
        template_dict["rasterFunctionArguments"]["source_cost_multiplier"] = source_cost_multiplier

    if source_start_cost is not None:
        template_dict["rasterFunctionArguments"]["source_start_cost"] = source_start_cost

    if source_resistance_rate is not None:
        template_dict["rasterFunctionArguments"]["source_resistance_rate"] = source_resistance_rate

    if source_capacity is not None:
        template_dict["rasterFunctionArguments"]["source_capacity"] = source_capacity
    
    if source_direction is not None:
        source_direction_list = ["FROM_SOURCE","TO_SOURCE"]
        if source_direction.upper() not in source_direction_list:
            raise RuntimeError('source_direction should be one of the following '+ str(source_direction_list) )
        template_dict["rasterFunctionArguments"]["source_direction"] = source_direction


    function_chain_ra = copy.deepcopy(template_dict)
    function_chain_ra['rasterFunctionArguments']["in_source_data"] = raster_ra1
    if in_cost_raster is not None:
        function_chain_ra['rasterFunctionArguments']["in_cost_raster"] = raster_ra2

    if in_surface_raster is not None:
        function_chain_ra['rasterFunctionArguments']["in_surface_raster"] = raster_ra3

    if in_horizontal_raster is not None:
        function_chain_ra['rasterFunctionArguments']["in_horizontal_raster"] = raster_ra4

    if in_vertical_raster is not None:
        function_chain_ra['rasterFunctionArguments']["in_vertical_raster"] = raster_ra5

    if in_value_raster is not None:
        function_chain_ra["rasterFunctionArguments"]["in_value_raster"] = raster_ra6

    return _gbl_clone_layer(in_source_data, template_dict, function_chain_ra)


def path_distance_back_link(in_source_data,
                  in_cost_raster=None,
                  in_surface_raster=None,
                  in_horizontal_raster=None,
                  in_vertical_raster=None,
                  horizontal_factor="BINARY",
                  vertical_factor="BINARY",
                  maximum_distance=None,
                  source_cost_multiplier=None,
                  source_start_cost=None,
                  source_resistance_rate=None,
                  source_capacity=None,
                  source_direction=None):
    """
    Defines the neighbor that is the next cell on the least accumulative cost path to the least-cost source, 
    while accounting for surface distance along with horizontal and vertical cost factors.

    Parameters
    ----------
    :param in_source_data:  The input source locations.

                            This is a raster that identifies the cells or locations from 
                            or to which the least accumulated cost distance for every output cell location is calculated.

                            For rasters, the input type can be integer or floating point.

    :param in_cost_raster:   A raster defining the impedance or cost to move planimetrically through each cell.

                             The value at each cell location represents the cost-per-unit distance for moving through the cell. 
                             Each cell location value is multiplied by the cell resolution while also compensating for diagonal 
                             movement to obtain the total cost of passing through the cell.

                             The values of the cost raster can be integer or floating point, but they cannot be negative or 
                             zero (you cannot have a negative or zero cost).

    :param in_surface_raster:  A raster defining the elevation values at each cell location. The values are used to calculate the actual 
                               surface distance covered when passing between cells.
    
    :param in_horizontal_raster: A raster defining the horizontal direction at each cell. 
                                 The values on the raster must be integers ranging from 0 to 360, with 0 degrees being north, or toward 
                                 the top of the screen, and increasing clockwise. Flat areas should be given a value of -1. 
                                 The values at each location will be used in conjunction with the {horizontal_factor} to determine the 
                                 horizontal cost incurred when moving from a cell to its neighbors.

    :param in_vertical_raster:  A raster defining the vertical (z) value for each cell. The values are used for calculating the slope 
                                used to identify the vertical factor incurred when moving from one cell to another.

    :param horizontal_factor:  The Horizontal Factor defines the relationship between the horizontal cost 
                               factor and the horizontal relative moving angle.
                               Possible values are: "BINARY", "LINEAR", "FORWARD", "INVERSE_LINEAR"

    :param vertical_factor: The Vertical Factor defines the relationship between the vertical cost factor and 
                            the vertical relative moving angle (VRMA)
                            Possible values are: "BINARY", "LINEAR", "SYMMETRIC_LINEAR", "INVERSE_LINEAR",
                            "SYMMETRIC_INVERSE_LINEAR", "COS", "SEC", "COS_SEC", "SEC_COS"

    :param maximum_distance:  Defines the threshold that the accumulative cost values cannot exceed. If an accumulative cost distance 
                              value exceeds this value, the output value for the cell location will be NoData. The maximum distance 
                              defines the extent for which the accumulative cost distances are calculated. 
                              
                              The default distance is to the edge of the output raster.

    :param source_cost_multiplier:  Multiplier to apply to the cost values. Allows for control of the mode of travel or the magnitude at a source. 
                                    The greater the multiplier, the greater the cost to move through each cell. The values must be greater than zero. 
                                    The default is 1.

    :param source_start_cost:  The starting cost from which to begin the cost calculations. Allows for the specification of the fixed cost associated with a source. 
                               Instead of starting at a cost of zero, the cost algorithm will begin with the value set by source_start_cost. 
                               
                               The values must be zero or greater. The default is 0.

    :param source_resistance_rate:  This parameter simulates the increase in the effort to overcome costs as the accumulative cost increases. 
                                    It is used to model fatigue of the traveler. The growing accumulative cost to reach a cell is multiplied 
                                    by the resistance rate and added to the cost to move into the subsequent cell.

    :param source_capacity:  Defines the cost capacity for the traveler for a source. 
                             The cost calculations continue for each source until the specified capacity is reached.

                             The values must be greater than zero. The default capacity is to the edge of the output raster.

    :param source_direction:  Defines the direction of the traveler when applying horizontal and vertical factors, 
                              the source resistance rate, and the source starting cost.
                              Possible values: FROM_SOURCE, TO_SOURCE

    :return: output raster with function applied
    """
    
    layer1, input_source_data, raster_ra1 = _raster_input(in_source_data)

    if in_cost_raster is not None:
        layer2, in_cost_raster, raster_ra2 = _raster_input(in_cost_raster)
       
    if in_surface_raster is not None:
        layer3, in_surface_raster, raster_ra3 = _raster_input(in_surface_raster)
    if in_horizontal_raster is not None:
        layer4, in_horizontal_raster, raster_ra4 = _raster_input(in_horizontal_raster)
    if in_vertical_raster is not None:
        layer5, in_vertical_raster, raster_ra5 = _raster_input(in_vertical_raster)
            
    template_dict = {
        "rasterFunction" : "GPAdapter",
        "rasterFunctionArguments" : {
            "toolName" : "PathBackLink_sa",
            "PrimaryInputParameterName" : "in_source_data",
            "OutputRasterParameterName":"out_backlink_raster",
            "in_source_data" : input_source_data
        }
    }
    
    if in_cost_raster is not None:
        template_dict["rasterFunctionArguments"]["in_cost_raster"] = in_cost_raster

    if in_surface_raster is not None:
        template_dict["rasterFunctionArguments"]["in_surface_raster"] = in_surface_raster

    if in_horizontal_raster is not None:
        template_dict["rasterFunctionArguments"]["in_horizontal_raster"] = in_horizontal_raster

    if in_vertical_raster is not None:
        template_dict["rasterFunctionArguments"]["in_vertical_raster"] = in_vertical_raster

    horizontal_factor_list = ["BINARY", "LINEAR", "FORWARD", "INVERSE_LINEAR"]
    if horizontal_factor is not None:
        if horizontal_factor.upper() not in horizontal_factor_list:
            raise RuntimeError('horizontal_factor should be one of the following '+ str(horizontal_factor_list))
        template_dict["rasterFunctionArguments"]["horizontal_factor"] = horizontal_factor

    vertical_factor_list = ["BINARY", "LINEAR", "SYMMETRIC_LINEAR", "INVERSE_LINEAR",
                            "SYMMETRIC_INVERSE_LINEAR", "COS", "SEC", "COS_SEC", "SEC_COS"]
    if vertical_factor is not None:
        if vertical_factor.upper() not in vertical_factor_list:
            raise RuntimeError('vertical_factor should be one of the following '+ str(vertical_factor_list))
        template_dict["rasterFunctionArguments"]["vertical_factor"] = vertical_factor

    if maximum_distance is not None:
        template_dict["rasterFunctionArguments"]["maximum_distance"] = maximum_distance


    if source_cost_multiplier is not None:
        template_dict["rasterFunctionArguments"]["source_cost_multiplier"] = source_cost_multiplier

    if source_start_cost is not None:
        template_dict["rasterFunctionArguments"]["source_start_cost"] = source_start_cost

    if source_resistance_rate is not None:
        template_dict["rasterFunctionArguments"]["source_resistance_rate"] = source_resistance_rate

    if source_capacity is not None:
        template_dict["rasterFunctionArguments"]["source_capacity"] = source_capacity

    if source_direction is not None:
        source_direction_list = ["FROM_SOURCE","TO_SOURCE"]
        if source_direction.upper() not in source_direction_list:
            raise RuntimeError('source_direction should be one of the following '+ str(source_direction_list) )
        template_dict["rasterFunctionArguments"]["source_direction"] = source_direction


    function_chain_ra = copy.deepcopy(template_dict)
    function_chain_ra['rasterFunctionArguments']["in_source_data"] = raster_ra1
    if in_cost_raster is not None:
        function_chain_ra['rasterFunctionArguments']["in_cost_raster"] = raster_ra2

    if in_surface_raster is not None:
        function_chain_ra['rasterFunctionArguments']["in_surface_raster"] = raster_ra3

    if in_horizontal_raster is not None:
        function_chain_ra['rasterFunctionArguments']["in_horizontal_raster"] = raster_ra4

    if in_vertical_raster is not None:
        function_chain_ra['rasterFunctionArguments']["in_vertical_raster"] = raster_ra5

    return _gbl_clone_layer(in_source_data, template_dict, function_chain_ra)

def calculate_distance(in_source_data,
                       maximum_distance=None,
                       output_cell_size=None,
                       allocation_field=None,
                       generate_out_allocation_raster=False,
                       generate_out_direction_raster=False):
    """
    Calculates the Euclidean distance, direction, and allocation from a single source or set of sources.

    Parameters
    ----------
    :param in_source_data:  The layer that defines the sources to calculate the distance to. 
                            The layer can be raster or feature. To use a raster input, it must 
                            be of integer type.

    :param maximum_distance:  Defines the threshold that the accumulative distance values 
                              cannot exceed. If an accumulative Euclidean distance value exceeds 
                              this value, the output value for the cell location will be NoData. 
                              The default distance is to the edge of the output raster.

                              Supported units: Meters | Kilometers | Feet | Miles

                              Example:

                              {"distance":"60","units":"Meters"}

    :param output_cell_size:   Specify the cell size to use for the output raster.

                               Supported units: Meters | Kilometers | Feet | Miles

                               Example:
                               {"distance":"60","units":"Meters"}

    :param allocation_field:  A field on the input_source_data layer that holds the values that 
                              defines each source.

                              It can be an integer or a string field of the source dataset.

                              The default for this parameter is 'Value'.

    :param generate_out_direction_raster:   Boolean, determines whether out_direction_raster should be generated or not.
                                           Set this parameter to True, in order to generate the out_direction_raster.
                                           If set to true, the output will be a named tuple with name values being
                                           output_distance_service and output_direction_service.
                                           eg,
                                           out_layer = calculate_distance(in_source_data
                                                                         generate_out_direction_raster=True)
                                           out_var = out_layer.save()
                                           then,
                                           out_var.output_distance_service -> gives you the output distance imagery layer item
                                           out_var.output_direction_service -> gives you the output backlink raster imagery layer item

                                           The output direction raster is in degrees, and indicates the 
                                           direction to return to the closest source from each cell center. 
                                           The values on the direction raster are based on compass directions, 
                                           with 0 degrees reserved for the source cells. Thus, a value of 90 
                                           means 90 degrees to the East, 180 is to the South, 270 is to the west,
                                           and 360 is to the North.

    :param generate_out_allocation_raster:  Boolean, determines whether out_allocation_raster should be generated or not.
                                            Set this parameter to True, in order to generate the out_backlink_raster.
                                            If set to true, the output will be a named tuple with name values being
                                            output_distance_service and output_allocation_service.
                                            eg,
                                            out_layer = calculate_distance(in_source_data
                                                                           generate_out_allocation_raster=False)
                                            out_var = out_layer.save()
                                            then,
                                            out_var.output_distance_service -> gives you the output distance imagery layer item
                                            out_var.output_allocation_service -> gives you the output allocation raster imagery layer item

                                            This parameter calculates, for each cell, the nearest source based 
                                            on Euclidean distance.

    :return: output raster with function applied
    """
    if isinstance (in_source_data, ImageryLayer):
        layer1, input_source_data, raster_ra1 = _raster_input(in_source_data)
    else:
        raster_ra1 = _layer_input(in_source_data)
        input_source_data = raster_ra1
        layer1=raster_ra1

    template_dict = {
        "rasterFunction" : "GPAdapter",
        "rasterFunctionArguments" : {
            "toolName" : "CalculateDistance_sa",
            "PrimaryInputParameterName" : "in_source_data",
            "OutputRasterParameterName":"out_distance_raster",
            "in_source_data" : input_source_data
        }
    }
    
    if maximum_distance is not None:
        template_dict["rasterFunctionArguments"]["maximum_distance"] = maximum_distance

    if output_cell_size is not None:
        template_dict["rasterFunctionArguments"]["output_cell_size"] = output_cell_size

    if allocation_field is not None:
        template_dict["rasterFunctionArguments"]["allocation_field"] = allocation_field

    function_chain_ra = copy.deepcopy(template_dict)
    function_chain_ra['rasterFunctionArguments']["in_source_data"] = raster_ra1

    if isinstance(in_source_data, ImageryLayer):
        return _gbl_clone_layer(in_source_data, template_dict, function_chain_ra, out_allocation_raster = generate_out_allocation_raster, out_direction_raster = generate_out_direction_raster, use_ra=True)
    else:
        return _feature_gbl_clone_layer(in_source_data, template_dict, function_chain_ra, out_allocation_raster = generate_out_allocation_raster, out_direction_raster = generate_out_direction_raster, use_ra=True)
