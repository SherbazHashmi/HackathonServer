import time as _time
from arcgis.gis import GIS
from arcgis._impl import _ArcGISConnection
from arcgis._impl.common._mixins import PropertyMap
from arcgis.gis import Item
###########################################################################
class PortalDataStore(object):
    """

    The datastores resource page provides access to operations that allow you to do the
    following:

    - Validate a data store against your server.
    - Register a data store to your server.
    - Retrieve a list of servers your data store is registered to.
    - Refresh your data store registration information in the server.
    - Unregister a data store from your server.

    Additionally, users also have the ability to bulk publish layers from a data store,
    retrieve a list of previously published layers, and delete bulk-published layers.

    """
    _con = None
    _gis = None
    _url = None
    _properties = None
    #----------------------------------------------------------------------
    def __init__(self, url, gis):
        """Constructor"""
        self._url = url
        self._gis = gis
        self._con = gis._con
    #----------------------------------------------------------------------
    def __str__(self):
        return "< PortalDataStore @ {url} >".format(url=self._url)
    #----------------------------------------------------------------------
    def __repr__(self):
        return "< PortalDataStore @ {url} >".format(url=self._url)
    #----------------------------------------------------------------------
    @property
    def properties(self):
        """returns the properties of the datastore"""
        if self._properties is None:
            params = {'f' : 'json'}
            res = self._con.get(self._url, params)
            self._properties = PropertyMap(res)
        return self._properties
    #----------------------------------------------------------------------
    def register(self, item, server_id):
        """

        The `register` method allows for Data Store type Items to be added to an ArcGIS Server instance.
        Before registering a data store, it is recommended that you validate your data store with the
        given server.

        ==================     ====================================================================
        **Argument**           **Description**
        ------------------     --------------------------------------------------------------------
        item                   Required Item/Item Id (as string). The item Id or Item of the data
                               store to register with the server. Note that a data store can be
                               registered on multiple servers.
        ------------------     --------------------------------------------------------------------
        server_id              Required String. The unique id of the server you want to register
                               the datastore with.
        ==================     ====================================================================

        :returns: Boolean

        """
        if isinstance(item, Item):
            item_id = item.id
        elif isinstance(item, str):
            item_id = item
        url = "{base}/addToServer".format(base=self._url)
        params = {
            'f' : 'json',
            'datastoreId' : item_id,
            'serverId' : server_id
        }
        res = self._con.post(url, params)
        if 'success' in res:
            return res['success']
        return res
    #----------------------------------------------------------------------
    @property
    def _all_datasets(self):
        """
        The _all_datasets resource page provides access to bulk publishing
        operations. These operations allow users to publish and synchronize
        datasets from a given data store, return a list of published layers,
        and remove all previously published layers in preparation for the
        deregistration of a data store.

        :returns: Boolean

        """
        url = "{base}/allDatasets".format(base=self._url)
        params = {
            'f' : 'json'}
        res = self._con.post(url, params)
        if 'success' in res:
            return res['success']
        return res
    #----------------------------------------------------------------------
    def delete_layers(self, item):
        """
        Before a data store can be unregistered from a server, all of its
        bulk-published layers must be deleted. The delete_layers removes all
        layers published from the data store.

        ==================     ====================================================================
        **Argument**           **Description**
        ------------------     --------------------------------------------------------------------
        item                   Required Item. The Data Store `Item` to delete all published layers.
        ==================     ====================================================================

        :returns: Boolean

        """
        if isinstance(item, Item):
            item_id = item.id
        else:
            item_id = item
            item = self._gis.content.get(item_id)
        params = {
            'f' : 'json',
            'datastoreId' : item_id
        }
        url = "{base}/allDatasets/deleteLayers"
        res = self._con.post(url, params)
        if res['success'] == True:
            status = item.status(self, job_id=res['jobId'])
            while status["status"].lower() != 'completed':
                status = item.status(self, job_id=res['jobId'])
                if status['status'].lower() == "failed":
                    return False
                else:
                    _time.sleep(2)
            return True
        return False
    #----------------------------------------------------------------------
    def layers(self, item):
        """
        The `layers operation returns a list of layers bulk published from a
        data store with the `publish_layers` method. The `layers` method
        returns an array of tuples, with each tuple containing two
        objects: a layer and the dataset it was published from.

        ==================     ====================================================================
        **Argument**           **Description**
        ------------------     --------------------------------------------------------------------
        item                   Required Item. The Data Store `Item` to list all published layers
                               and registered datasets.
        ==================     ====================================================================

        :returns: List

        """

        if isinstance(item, Item):
            item_id = item.id
        else:
            item_id = item
            item = self._gis.content.get(item_id)

        url = "{base}/allDatasets/getLayers".format(base=self._url)
        params = {
            'f' : 'json',
            'datastoreId' : item_id
        }
        res = self._con.post(url, params)
        if "layerAndDatasets" in res:
            return res["layerAndDatasets"]
        return []
    #----------------------------------------------------------------------
    def servers(self, item):
        """
        The `servers` property returns a list of your servers that a given
        data store has been registered to. This operation returns the
        serverId, the server name, both the server and admin URLs, and
        whether or not the server is hosted.


        ==================     ====================================================================
        **Argument**           **Description**
        ------------------     --------------------------------------------------------------------
        item                   Required Item. The Data Store `Item` to list all registered servers.
        ==================     ====================================================================

        :returns: List

        """

        if isinstance(item, Item):
            item_id = item.id
        else:
            item_id = item
            item = self._gis.content.get(item_id)

        url = self._url + "/getServers"
        params = {
            'f' : 'json',
            'datastoreId' : item_id
        }
        res = self._con.post(url, params)
        if 'servers' in res:
            return res['servers']
        return res
    #----------------------------------------------------------------------
    def publish_layers(self, item, srv_config, server_id, folder=None, server_folder=None):
        """
        The `publish_layers` operation publishes, or syncs, the datasets from a
        data store onto your ArcGIS Server, resulting in at least one layer per
        dataset.

        When this operation is called for the first time, every parameter in
        the operation must be passed through. On subsequent calls,
        publish_layers will synchronize the datasets and created layers, which
        includes both publishing layers from new datasets and removing layers
        for datasets no longer found in the data store.

        ==================     ====================================================================
        **Argument**           **Description**
        ------------------     --------------------------------------------------------------------
        item                   Required Item. The Data Store `Item` to publish from.
        ------------------     --------------------------------------------------------------------
        srv_config             Required Dict. The JSON that will be used as a template for all the
                               services that will be published or synced. This JSON can be used to
                               change the properties of the data store's map and feature services.
                               Only map service configurations with feature services enabled are
                               supported by this parameter.
        ------------------     --------------------------------------------------------------------
        server_id              Required String. The serverId that the datasets will be published to.
        ------------------     --------------------------------------------------------------------
        folder                 Optional String. The folder to which the datasets will be published.
        ------------------     --------------------------------------------------------------------
        server_folder          Optional String. The name of the server folder.
        ==================     ====================================================================

        :returns: Boolean

        """
        if isinstance(item, Item):
            item_id = item.id
        else:
            item_id = item
            item = self._gis.content.get(item_id)
        url = self._url + "/allDatasets/publishLayers"
        params = {
            'f' : 'json',
            'datastoreId' : item_id,
            'templateScvConfig' : srv_config,
            'portalFolderId' : folder,
            'serverId' : server_id,
            'serverFolder' : server_folder,
        }
        res = self._con.post(url, params)
        if res['success'] == True:
            status = item.status(self, job_id=res['jobId'])
            while status["status"].lower() != 'completed':
                status = item.status(self, job_id=res['jobId'])
                if status['status'].lower() == "failed":
                    return False
                else:
                    _time.sleep(2)
            return True
        return False
    #----------------------------------------------------------------------
    def unregister(self, item, server_id):
        """
        Removes the datastore association from a server.

        :returns: Boolean

        """
        if isinstance(item, Item):
            item_id = item.id
        elif isinstance(item, str):
            item_id = item
        url = self._url + "/removeFromServer"
        params = {
            'f' : 'json',
            'datastoreId' : item_id,
            'serverId' : server_id
        }
        res = self._con.post(url, params)
        if 'success' in res:
            return res['success']
        return res
    #----------------------------------------------------------------------
    def refresh_server(self, item, server_id):
        """
        After a data store has been registered, there may be times in which
        the data store's registration information may be changed. When
        changes like these occur, the server will need to be updated with
        the newly configured information so that your users will still be
        able to access the data store items without interruption. The
        `refresh_server` can be called to propagate these changes to your
        ArcGIS Server. This operation can only be performed after the data
        store information has been updated.

        ==================     ====================================================================
        **Argument**           **Description**
        ------------------     --------------------------------------------------------------------
        item                   Required Item/Item Id (as string). The item Id or Item of the data
                               store to register with the server. Note that a data store can be
                               registered on multiple servers.
        ------------------     --------------------------------------------------------------------
        server_id              Required String. The unique id of the server you want to register
                               the datastore with.
        ==================     ====================================================================

        :returns: Boolean

        """
        if isinstance(item, Item):
            item_id = item.id
        elif isinstance(item, str):
            item_id = item

        url = self._url + "/refreshServer"
        params = {
            'f' : 'json',
            'datastoreId' : item_id,
            'serverId' : server_id
        }
        res = self._con.post(url, params)
        if 'success' in res:
            return res['success']
        return res
    #----------------------------------------------------------------------
    def validate(self, server_id, item=None, config=None):
        """
        The `validate` ensures that your ArcGIS Server can connect and use
        the datasets stored within a given data store. While this operation
        can be called before or after the data store has been registered
        with your server, it is recommended that the validate operation is
        performed beforehand. A data store can be validated by using either
        its datastoreId or the JSON for an unregistered data store.

        ==================     ====================================================================
        **Argument**           **Description**
        ------------------     --------------------------------------------------------------------
        server_id              Required String. The unique id of the server you want to register
                               the datastore with.
        ------------------     --------------------------------------------------------------------
        item                   Optional Item/Item Id (as string). The item Id or Item of the data
                               store to register with the server. Note that a data store can be
                               registered on multiple servers.
        ------------------     --------------------------------------------------------------------
        config                 Optional dict. The connection information for a new datastore.
        ==================     ====================================================================

        :returns: Boolean

        """

        if item and isinstance(item, Item):
            item_id = item.id
        elif item and isinstance(item, str):
            item_id = item
        else:
            item_id = None

        url = self._url + "/validate"
        params = {
                'f' : 'json',
                'serverId' : server_id
            }
        if item:
            params['datastoreId'] = item_id
        elif config:
            import json
            params['datastore'] = json.dumps(config)
        else:
            raise ValueError("Invalid parameters, an item or config is required.")
        res = self._con.post(url, params)
        if 'status' in res:
            if res['status'] == 'success':
                return True
            return res['status']
        return res
