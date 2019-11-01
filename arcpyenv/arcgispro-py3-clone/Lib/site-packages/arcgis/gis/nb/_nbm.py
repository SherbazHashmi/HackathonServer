import os
from arcgis.gis import GIS
from arcgis._impl.common._mixins import PropertyMap

########################################################################
class NotebookManager(object):
    """
    Provides access to managing a site's notebooks
    """
    _url = None
    _gis = None
    _properties = None
    #----------------------------------------------------------------------
    def __init__(self, url, gis):
        """Constructor"""
        self._url = url
        if isinstance(gis, GIS):
            self._gis = gis
            self._con = self._gis._con
        else:
            raise ValueError("Invalid GIS object")
    #----------------------------------------------------------------------
    def _init(self):
        """loads the properties"""
        try:
            params = {'f': 'json'}
            res = self._gis._con.get(self._url, params)
            self._properties = PropertyMap(res)
        except:
            self._properties = PropertyMap({})
    #----------------------------------------------------------------------
    def __str__(self):
        return "<NotebookManager @ {url}>".format(url=self._url)
    #----------------------------------------------------------------------
    def __repr__(self):
        return "<NotebookManager @ {url}>".format(url=self._url)
    #----------------------------------------------------------------------
    @property
    def properties(self):
        """returns the properties of the resource"""
        if self._properties is None:
            self._init()
        return self._properties
    #----------------------------------------------------------------------
    @property
    def runtimes(self):
        """
        Returns a list of all runtimes

        :return: List
        """
        url = self._url + "/runtimes"
        params = {'f' : 'json'}
        res = self._con.get(url, params)
        if "runtimes" in res:
            return [Runtime(url=url + "/{rid}".format(rid=r["id"]),
                            gis=self._gis) \
                    for r in res["runtimes"]]
        return []
    #----------------------------------------------------------------------
    def restore_runtime(self):
        """
        This operation restores the two default notebook runtimes in ArcGIS
        Notebook Server - ArcGIS Notebook Python 3 Standard and ArcGIS
        Notebook Python 3 Advanced - to their original settings.
        """
        url = self._url + "/runtimes/restore"
        params = {'f' : 'json'}
        res = self._con.post(url, params)
        if 'status' in res:
            return res['status'] == 'success'
        return res
    #----------------------------------------------------------------------
    def _open_notebook(self,
                      itemid,
                      templateid=None,
                      nb_runtimeid=None,
                      template_nb=None):
        """
        **Internal call used to open notebooks this call can and will be changed**

        Opens a notebook on the notebook server

        ==================     ====================================================================
        **Argument**           **Description**
        ------------------     --------------------------------------------------------------------
        itemid                 Required String. Opens an existing portal item.
        ------------------     --------------------------------------------------------------------
        templateid             Optional String. The id of the portal notebook template. To get the
                               system templates, look at the sample notebooks group:

                               ```
                               from arcgis.gis import GIS
                               gis = GIS()
                               grp = gis.groups.search("title:(esri sample notebooks) AND owner:\"esri_notebook\")[0]
                               grp.content

                               ```
        ------------------     --------------------------------------------------------------------
        nb_runtimeid           Optional String. The runtime to use to generate a new notebook.
        ------------------     --------------------------------------------------------------------
        template_nb            Optional String. The start up template for the notebook.
        ==================     ====================================================================

        :return: dict

        """
        params = {
            "itemId" : itemid,
            "templateId" : templateid,
            'notebookRuntimeId' : nb_runtimeid,
            'templateNotebook' : template_nb ,
            'async' : True,
            'f' : 'json'
        }
        url = self._url + "/openNotebook"
        return self._con.post(url, params)
    #----------------------------------------------------------------------
    def _add_runtime(self,
                     name,
                     image_id,
                     version="10.7",
                     container_type='docker',
                     image_pull_string="",
                     max_cpu=1.0,
                     max_memory=4.0,
                     max_memory_unit='g',
                     max_swap_memory="",
                     max_swap_unit='g',
                     shared_memory=None,
                     shared_memory_unit='m',
                     docker_runtime="",
                     manifest=None,
                     **kwargs):
        """
        **WARNING: private method, this will change in future releases**

        Added a new docker image to the notebook server.
        """
        url = self._url + "/runtimes/register"
        params = {
            'f' : 'json',
            "name" : name,
            "version" : version,
            "imageId" :  image_id,
            "containerType": container_type,
            "imagePullString" : image_pull_string,
            "maxCpu": float(max_cpu),
            "maxMemory": float(max_memory),
            "maxMemoryUnit": max_memory_unit,
            "maxSwapMemory": max_swap_memory,
            "maxSwapMemoryUnit": max_swap_unit,
            "sharedMemory": shared_memory,
            "sharedMemoryUnit": shared_memory_unit,
            "dockerRuntime": docker_runtime,
            "f": "json"
        }

        for k,v in kwargs.items():
            params[k] = v
        res = self._con.post(url,
                             params,
                             files={'manifestFile' : manifest},
                             add_headers=[('X-Esri-Authorization',
                                          "bearer {token}".format(token=self._con.token))]
                             )
        return res

########################################################################
class Runtime(object):
    """
    """
    _url = None
    _gis = None
    _properties = None
    #----------------------------------------------------------------------
    def __init__(self, url, gis):
        """Constructor"""
        self._url = url
        if isinstance(gis, GIS):
            self._gis = gis
            self._con = self._gis._con
        else:
            raise ValueError("Invalid GIS object")
    #----------------------------------------------------------------------
    def _init(self):
        """loads the properties"""
        try:
            params = {'f': 'json'}
            res = self._gis._con.get(self._url, params)
            self._properties = PropertyMap(res)
        except:
            self._properties = PropertyMap({})
    #----------------------------------------------------------------------
    def __str__(self):
        return "<Runtime @ {url}>".format(url=self._url)
    #----------------------------------------------------------------------
    def __repr__(self):
        return "<Runtime @ {url}>".format(url=self._url)
    #----------------------------------------------------------------------
    @property
    def properties(self):
        """returns the properties of the resource"""
        if self._properties is None:
            self._init()
        return self._properties
    #----------------------------------------------------------------------
    def delete(self):
        """
        Deletes the current runtime from the ArcGIS Notebook Server

        :returns: boolean

        """
        url = self._url + "/unregister"
        params = {'f' : 'json'}
        res = self._con.post(url, params)
        if 'status' in res:
            return res['status'] == 'success'
        return res
    #----------------------------------------------------------------------
    def update(self,
               name=None,
               image_id=None,
               max_cpu=None,
               max_memory=None,
               memory_unit=None,
               max_swap_memory=None,
               swap_memory_unit=None,
               shared_memory=None,
               docker_runtime=None,
               shared_unit=None,
               version=None,
               container_type=None,
               pull_string=None,
               require_advanced_priv=None,
               manifest=None):
        """
        This operation allows you to update the properties of a notebook
        runtime in ArcGIS Notebook Server. These settings will be applied
        to every container to which the runtime is applied.

        You can use this operation to update the resource limits of the
        runtime, such as maximum CPU and maximum memory. You can also use
        it to extend either of the default notebook runtimes, in order to
        make additional Python modules available to your notebook authors,
        or as a step in making ArcGIS Notebook Server able to use graphical
        processing units (GPUs).



        """
        url = self._url + "/update"
        if manifest is None:
            manifest = ""
        if manifest:
            file = {'manifestFile' : manifest}

        params = {
            "name": name,
            "version" : version,
            "imageId" : image_id,
            "containerType": container_type,
            "imagePullString" : pull_string,
            "requiresAdvancedPrivileges": require_advanced_priv,
            "maxCpu" : max_cpu or float(self.properties.maxCpu),
            "maxMemory" : max_memory or float(self.properties.maxMemory),
            "maxMemoryUnit" : memory_unit or "g",
            "maxSwapMemory" : max_swap_memory or "",
            "maxSwapMemoryUnit" : swap_memory_unit or "g",
            "sharedMemory" : shared_memory or "",
            "sharedMemoryUnit" : shared_unit or "m",
            "dockerRuntime": docker_runtime,
            'f' : 'json'
        }
        import json
        for k in list(params.keys()):

            if params[k] is None and \
               k in self.properties:
                params[k] = self.properties[k]
            elif params[k] is None:
                params[k] = ""
            if isinstance(params[k], bool):
                params[k] = json.dumps(params[k])
            elif isinstance(params[k], (int, float)):
                params[k] = float(params[k])

        if len(params) == 1:
            return False
        res = self._con.post(url,
                             params,
                             files={'manifestFile' : manifest},
                             add_headers=[('X-Esri-Authorization',
                                          "bearer {token}".format(token=self._con.token))]
                             )
        if 'status' in res:
            return res['status'] == 'success'
        return res
    #----------------------------------------------------------------------
    @property
    def manifest(self):
        """
        This resource returns a JSON representation of all the Python
        libraries supported in the specified notebook runtime. Notebook
        authors who open notebooks using this runtime are able to import
        any of the libraries in the manifest into their notebooks.

        :returns: List of Dictionaries

        """
        url = self._url + "/manifest"
        params = {'f' : 'json'}
        res = self._con.get(url, params)
        if "libraries" in res:
            return res["libraries"]
        return res



