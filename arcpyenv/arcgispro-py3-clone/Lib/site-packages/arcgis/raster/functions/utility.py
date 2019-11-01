from .._layer import ImageryLayer
from arcgis.gis import Item
import numbers
from arcgis.features.layer import FeatureLayer

def _raster_input(raster, raster2=None):
    layer=None
    if raster2 is not None:
        if isinstance(raster2, ImageryLayer) and isinstance(raster, ImageryLayer):
            layer = raster2
            raster_ra = _get_raster_ra(raster2)
            if raster._datastore_raster and raster2._datastore_raster:
                if raster2._fn is not None:
                    if raster._uri == raster2._uri:
                        raster2 = raster2._fn
                    else:
                        raster2 = _replace_raster_url(raster2._fn, raster2._uri)
                else:
                    if raster2._uri == raster._uri:
                        oids = raster2.filtered_rasters()
                        if oids is None:
                            raster2 = '$$'
                        elif len(oids) == 1:
                            raster2 = '$' + str(oids[0])
                        else:
                            raster2 = ['$' + str(x) for x in oids]
                    else:
                        raster2 = raster2._uri
            else:
                 if raster2._fn is not None:
                    if raster._url == raster2._url:
                        raster2 = raster2._fn
                    else:
                        if(raster2._datastore_raster is False):
                            raster2 = _replace_raster_url(raster2._fn, raster2._url)
                        else:
                            raster2 = _replace_raster_url(raster2._fn, raster2._uri)
                 else:
                    if raster2._url == raster._url:
                        oids = raster2.filtered_rasters()
                        if oids is None:
                            raster2 = '$$'
                        elif len(oids) == 1:
                            raster2 = '$' + str(oids[0])
                        else:
                            raster2 = ['$' + str(x) for x in oids]
                    else:
                        if(raster2._datastore_raster is False):
                            raster2 = raster2._url
                        else:
                            raster2 = raster2._uri
        elif isinstance(raster2, ImageryLayer) and not isinstance(raster, ImageryLayer):
            layer = raster2
            raster_ra = _get_raster_ra(raster2)
            raster2 = _get_raster(raster2)

        elif isinstance(raster2, list):
            mix_and_match = False # mixing rasters from two image services
            # try:
            #     r0 = raster2[0]
            #     r1 = raster2[1]
            #     if r0._fn is None and r1._fn is None and r0._url != r1._url:
            #         mix_and_match = True
            # except:
            #     pass

            for r in raster2: # layer is first non numeric raster in list
                if not isinstance(r, numbers.Number):
                    layer = r
                    break

            for r in raster2:
                if r._datastore_raster:
                    if not isinstance(r, numbers.Number):
                        if r._uri != layer._uri:
                            mix_and_match = True
                else:
                    if not isinstance(r, numbers.Number):
                        if r._url != layer._url:
                            mix_and_match = True

            raster_ra = [_get_raster_ra(r) for r in raster2]
            if mix_and_match:
                raster2 = [_get_raster_url(r, layer) for r in raster2]
            else:
                raster2 = [_get_raster(r) for r in raster2]
        else: # secondinput maybe scalar for arithmetic functions, or a chained raster fn
            layer = None
            # raster = raster
            raster_ra = raster2
        return layer, raster2, raster_ra

    if isinstance(raster, ImageryLayer):
        layer = raster
        raster_ra = _get_raster_ra(raster)
        raster = _get_raster(raster)

    elif isinstance(raster, list):
        mix_and_match = False # mixing rasters from two image services
        # try:
        #     r0 = raster[0]
        #     r1 = raster[1]
        #     if r0._fn is None and r1._fn is None and r0._url != r1._url:
        #         mix_and_match = True
        # except:
        #     pass

        for r in raster:
            if isinstance(r, ImageryLayer):
                if r._datastore_raster:
                    layer = r
        if layer is None:
            for r in raster: # layer is first non numeric raster in list
                if not isinstance(r, numbers.Number):
                    layer = r
                    break

        for r in raster:
            if not isinstance(r, numbers.Number):
                if r._datastore_raster:
                    if r._uri != layer._uri:
                        mix_and_match = True
                else:
                    if r._url != layer._url:
                        mix_and_match = True

        raster_ra = [_get_raster_ra(r) for r in raster]
        if mix_and_match:
            raster = [_get_raster_url(r, layer) for r in raster]
        else:
            raster = [_get_raster(r) for r in raster]
    else: # maybe scalar for arithmetic functions, or a chained raster fn
        layer = None
        # raster = raster
        raster_ra = raster

    return layer, raster, raster_ra

def _get_raster(raster):
    if isinstance(raster, ImageryLayer):
        if raster._fn is not None:
            raster = raster._fn
        else:
            oids = raster.filtered_rasters()
            if oids is None:
                raster = '$$'
            elif len(oids) == 1:
                raster = '$' + str(oids[0])
            else:
                raster = ['$' + str(x) for x in oids]
    return raster


def _replace_raster_url(obj, url=None):
    # replace all "Raster" : '$$' with url
    if isinstance(obj, dict):
        value = {k: _replace_raster_url(v, url)
                 for k, v in obj.items()}
    elif isinstance(obj, list):
        value = [_replace_raster_url(elem, url)
                 for elem in obj]
    else:
        value = obj

    if value == '$$':
        return url
    elif isinstance(value, str) and len(value) > 0 and value[0] == '$':
        return url + '/' + value.replace('$', '')
    else:
        return value


def _get_raster_url(raster, layer):
    if isinstance(raster, ImageryLayer):
        if raster._fn is not None:
            if raster._datastore_raster and layer._datastore_raster:
                if raster._uri == layer._uri:
                    raster = raster._fn
                else:
                    raster = _replace_raster_url(raster._fn, raster._uri)

            else:
                if raster._url == layer._url:
                    raster = raster._fn
                else:
                    raster = _replace_raster_url(raster._fn, raster._url)

        else:
            if raster._datastore_raster and layer._datastore_raster:
                if raster._uri == layer._uri:
                    raster = '$$'
                else:
                    raster = raster._uri
            else:
                if raster._url == layer._url:
                    raster = '$$'
                else:
                    raster = raster._url

            # oids = raster.filtered_rasters()
            # if oids is None:
            #     raster = '$$'
            # elif len(oids) == 1:
            #     raster = '$' + str(oids[0])
            # else:
            #     raster = ['$' + str(x) for x in oids]
    return raster


def _get_raster_ra(raster):

    if isinstance(raster, ImageryLayer):
        if "url" in raster._lyr_dict:
            url = raster._lyr_dict["url"]
        if "serviceToken" in raster._lyr_dict:
            url = url+"?token="+ raster._lyr_dict["serviceToken"]
        if raster._fnra is not None:
            raster_ra = raster._fnra
        else:
            raster_ra = {}
            if raster._mosaic_rule is not None:
                if raster._datastore_raster:
                    raster_ra["uri"] = raster._uri
                else:
                    raster_ra["url"] = url
                raster_ra["mosaicRule"] = raster._mosaic_rule
            else:
                if raster._datastore_raster:
                    raster_ra = raster._uri
            
                else:
                    raster_ra = url

            #if raster._mosaic_rule is not None:
            #    raster_ra['mosaicRule'] = raster._mosaic_rule
    elif isinstance(raster, Item):
        raise RuntimeError('Item not supported as input. Use ImageryLayer - e.g. item.layers[0]')
        #raster_ra = {
        #    'itemId': raster.itemid
        #}
    else:
        raster_ra = raster

    return raster_ra


def _raster_input_rft(raster, raster2=None):
    if isinstance(raster, ImageryLayer) or isinstance(raster,FeatureLayer):
        raster_ra = _get_raster_ra_rft(raster)

    elif isinstance(raster, list):
        raster_ra = [_get_raster_ra_rft(r) for r in raster]

    else: # maybe scalar for arithmetic functions, or a chained raster fn
        raster_ra = raster

    return raster_ra


def _get_raster_ra_rft(raster):
    if isinstance(raster, ImageryLayer):
        if "url" in raster._lyr_dict:
            url = raster._lyr_dict["url"]
        if "serviceToken" in raster._lyr_dict:
            url = url+"?token="+ raster._lyr_dict["serviceToken"]
        if raster._fnra is not None:
            raster_ra = raster._fnra
        else:
            raster_ra = {}
            if raster._mosaic_rule is not None:
                if raster._datastore_raster:
                    raster_ra["uri"] = raster._uri
                else:
                    raster_ra["url"] = url
                raster_ra["mosaicRule"] = raster._mosaic_rule
            else:
                if raster._datastore_raster:
                    raster_ra = raster._uri
                else:
                    raster_ra = url


    elif isinstance(raster,FeatureLayer):
        raster_ra = raster._url
            #if raster._mosaic_rule is not None:
            #    raster_ra['mosaicRule'] = raster._mosaic_rule
    elif isinstance(raster, Item):
        raise RuntimeError('Item not supported as input. Use ImageryLayer - e.g. item.layers[0]')
    else:
        raster_ra = raster

    return raster_ra

def _input_rft(input_layer):
    if isinstance(input_layer, dict):
        input_param = input_layer

    elif isinstance(input_layer, str):
        if '/fileShares/' in input_layer or '/rasterStores/' in input_layer or '/cloudStores/' in input_layer:
            input_param = {"uri": input_layer}
        else:
            input_param = {"url": input_layer}

    elif isinstance(input_layer, list):
        input_param = []
        for il in input_layer:
            if isinstance(il,str):
                if '/fileShares/' in il or '/rasterStores/' in il or '/cloudStores/' in il:
                    input_param.append({"uri":il})
                else:
                    input_param.append({"url":il})
            elif isinstance(il,dict):
                input_param.append(il)
    else:
        input_param = input_layer
    return input_param




def _find_object_ref(rft_dict, record, instance):
    for k, v in rft_dict.items():
        if isinstance(v, dict):
            if "_object_id" in v:
                record[v["_object_id"]] = v
            if "isPublic" in v:
                if v["isPublic"] is True:
                    instance._is_public_flag=True
            _find_object_ref(v, record, instance)

        elif isinstance(v, list):
            for ele in v:
                if isinstance (ele,dict):
                    if "_object_id" in ele:
                        record[ele["_object_id"]] = ele
                    if "isPublic" in ele:
                        if ele["isPublic"] is True:
                            instance._is_public_flag=True
                    _find_object_ref(ele, record, instance)
    return _replace_object_id(rft_dict, record)

def _replace_object_id(rft_dict, record):

    if isinstance (rft_dict, dict):
        if "_object_ref_id" in rft_dict.keys():
                ref_value=record[rft_dict["_object_ref_id"]]
                rft_dict=ref_value
                return _replace_object_id(rft_dict, record)
        else:
            for k, v in rft_dict.items():
                if isinstance(v, dict):
                    rft_dict[k]=_replace_object_id(v, record)

                elif isinstance(v, list):
                    for n,ele in enumerate(v):
                        if isinstance (ele,dict):
                            v[n]=_replace_object_id(ele, record)
    return rft_dict


def _python_variable_name(var):
        var = ''.join(e for e in var if e.isalnum() or e=="_")
        return var

