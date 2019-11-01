"""
ArcGIS Server site mode that allows you to control changes to your site.
You can set the site mode to READ_ONLY to disallow the publishing of new
services and block most administrative operations. Your existing services
will continue to function as they did previously. Note that certain
administrative operations such as adding and removing machines from a
site are still available in READ_ONLY mode.
"""
from __future__ import absolute_import
from __future__ import print_function
from .._common import BaseServer

###########################################################################
class Mode(BaseServer):
    """
    ArcGIS Server site mode that allows you to control changes to your site.
    You can set the site mode to READ_ONLY to disallow the publishing of new
    services and block most administrative operations. Your existing services
    will continue to function as they did previously. Note that certain
    administrative operations such as adding and removing machines from a
    site are still available in READ_ONLY mode.
    """
    _url = None
    _con = None
    _json_dict = None
    _json = None
    _siteMode = None
    _copyConfigLocal = None
    _lastModified = None
    #----------------------------------------------------------------------
    def __init__(self,
                 url,
                 gis,
                 initialize=False):
        """Constructor"""
        super(Mode, self).__init__(gis=gis,
                                   url=url)
        if url.lower().endswith('/mode'):
            self._url = url
        else:
            self._url = url + "/mode"
        self._con = gis
        if initialize:
            self._init(gis)
    #----------------------------------------------------------------------
    def update(self,
               siteMode,
               runAsync=False):
        """
        The update operation is used to move between the two types of site
        modes. Switching to READ_ONLY mode will restart all your services
        as the default behavior. Moving to EDITABLE mode will not restart
        services.

        ===============     ====================================================================
        **Argument**        **Description**
        ---------------     --------------------------------------------------------------------
        siteMode:           Required string. The mode you will set your site to. Values:
                            READ_ONLY or EDITABLE.
        ---------------     --------------------------------------------------------------------
        runAsync            Optional boolean. Determines if this operation must run asynchronously.
        ===============     ====================================================================


        :return: boolean

        """
        params = {"siteMode" : siteMode,
                  "runAsync" : runAsync,
                  "f" : "json"}
        url = self._url + "/update"
        res = self._con.post(path=url,
                             postdata=params)
        if 'status' in res:
            return res['status'] == 'success'
        return res
