""" The portalpy module for working with the ArcGIS Online and Portal APIs."""
from __future__ import absolute_import
import io
import os
import re
import ssl
import sys
import json
import uuid
import zlib
import shutil
import logging
import datetime
import tempfile
import mimetypes
import unicodedata
try:
    #PY2
    from cStringIO import StringIO
except ImportError:
    #PY3
    from io import StringIO
from io import BytesIO
from collections import OrderedDict

import six
from six.moves.urllib_parse import urlparse, urlunparse, parse_qsl
from six.moves.urllib_parse import quote, unquote, urlunsplit
from six.moves.urllib_parse import urlencode, urlsplit
from six.moves.urllib.error import HTTPError
from six.moves.urllib import request
from six.moves import http_cookiejar as cookiejar
from six.moves import http_client
from arcgis._impl.connection import _ArcGISConnection
from arcgis.gis import GIS
class Error(Exception): pass

__version__ = '2.0'
_log = logging.getLogger(__name__)
########################################################################
class MultiPartForm(object):
    """Accumulate the data to be used when posting a form."""
    PY2 = sys.version_info[0] == 2
    PY3 = sys.version_info[0] == 3
    files = []
    form_fields = []
    boundary = None
    form_data = ""
    #----------------------------------------------------------------------
    def __init__(self, param_dict=None, files=None):
        if param_dict is None:
            param_dict = {}
        if files is None:
            files = {}
        self.boundary = None
        self.files = []
        self.form_data = ""
        if len(self.form_fields) > 0:
            self.form_fields = []

        if len(param_dict) == 0:
            self.form_fields = []
        else:
            for k,v in param_dict.items():
                self.form_fields.append((k,v))
                del k,v
        if isinstance(files, list):
            if len(files) == 0:
                self.files = []
            else:
                for key, filePath, fileName in files:
                    self.add_file(fieldname=key,
                                  filename=fileName,
                                  filePath=filePath,
                                  mimetype=None)
        elif isinstance(files, dict):
            for key, filepath in files.items():
                self.add_file(fieldname=key,
                              filename=os.path.basename(filepath),
                              filePath=filepath,
                              mimetype=None)
                del key, filepath
        self.boundary = "-%s" % self._make_boundary()
    #----------------------------------------------------------------------
    def get_content_type(self):
        return 'multipart/form-data; boundary=%s' % self.boundary
    #----------------------------------------------------------------------
    def add_field(self, name, value):
        """Add a simple field to the form data."""
        self.form_fields.append((name, value))
    #----------------------------------------------------------------------
    def _make_boundary(self):
        """ creates a boundary for multipart post (form post)"""
        if six.PY2:
            return '-===============%s==' % uuid.uuid4().get_hex()
        elif six.PY3:
            return '-===============%s==' % uuid.uuid4().hex
        else:
            from random import choice
            digits = "0123456789"
            letters = "abcdefghijklmnopqrstuvwxyz"
            return '-===============%s==' % ''.join(choice(letters + digits) \
                                                    for i in range(15))
    #----------------------------------------------------------------------
    def add_file(self, fieldname, filename, filePath, mimetype=None):
        """Add a file to be uploaded.
        Inputs:
           fieldname - name of the POST value
           fieldname - name of the file to pass to the server
           filePath - path to the local file on disk
           mimetype - MIME stands for Multipurpose Internet Mail Extensions.
             It's a way of identifying files on the Internet according to
             their nature and format. Default is None.
        """
        body = filePath
        if mimetype is None:
            mimetype = mimetypes.guess_type(filename)[0] or 'application/octet-stream'
        self.files.append((fieldname, filename, mimetype, body))
    #----------------------------------------------------------------------
    @property
    def make_result(self):
        if self.PY2:
            self._2()
        elif self.PY3:
            self._3()
        return self.form_data
    #----------------------------------------------------------------------
    def _2(self):
        """python 2.x version of formatting body data"""
        boundary = self.boundary
        buf = StringIO()
        for (key, value) in self.form_fields:
            buf.write('--%s\r\n' % boundary)
            buf.write('Content-Disposition: form-data; name="%s"' % key)
            buf.write('\r\n\r\n%s\r\n' % value)
        for (key, filename, mimetype, filepath) in self.files:
            if os.path.isfile(filepath):
                buf.write('--{boundary}\r\n'
                          'Content-Disposition: form-data; name="{key}"; '
                          'filename="{filename}"\r\n'
                          'Content-Type: {content_type}\r\n\r\n'.format(
                              boundary=boundary,
                              key=key,
                              filename=filename,
                              content_type=mimetype))
                with open(filepath, "rb") as f:
                    shutil.copyfileobj(f, buf)
                buf.write('\r\n')
        buf.write('--' + boundary + '--\r\n\r\n')
        buf = buf.getvalue()
        self.form_data = buf
    #----------------------------------------------------------------------
    def _3(self):
        """ python 3 method"""
        boundary = self.boundary
        buf = BytesIO()
        textwriter = io.TextIOWrapper(
            buf, 'utf8', newline='', write_through=True)

        for (key, value) in self.form_fields:
            textwriter.write(
                '--{boundary}\r\n'
                'Content-Disposition: form-data; name="{key}"\r\n\r\n'
                '{value}\r\n'.format(
                    boundary=boundary, key=key, value=value))
        for(key, filename, mimetype, filepath) in self.files:
            if os.path.isfile(filepath):
                textwriter.write(
                    '--{boundary}\r\n'
                    'Content-Disposition: form-data; name="{key}"; '
                    'filename="{filename}"\r\n'
                    'Content-Type: {content_type}\r\n\r\n'.format(
                        boundary=boundary, key=key, filename=filename,
                        content_type=mimetype))
                with open(filepath, "rb") as f:
                    shutil.copyfileobj(f, buf)
                textwriter.write('\r\n')
        textwriter.write('--{}--\r\n\r\n'.format(boundary))
        self.form_data = buf.getvalue()
########################################################################
class HTTPSClientAuthHandler(request.HTTPSHandler):
    def __init__(self, key, cert):
        request.HTTPSHandler.__init__(self)
        self.key = key
        self.cert = cert
    def https_open(self, req):
        #Rather than pass in a reference to a connection class, we pass in
        # a reference to a function which, for all intents and purposes,
        # will behave as a constructor
        return self.do_open(self.getConnection, req)
    def getConnection(self, host, timeout=300):
        return  http_client.HTTPSConnection(host,
                                            key_file=self.key,
                                            cert_file=self.cert,
                                            timeout=timeout)

def jsonize_dict(val):
    if isinstance(val, (dict, list)):
        return json.dumps(val)
    else:
        return val

class ServerConnection(object):
    """

    =====================     ====================================================================
    **Argument**              **Description**
    ---------------------     --------------------------------------------------------------------
    baseurl                   optional string, the root URL to a site.
                              Example: https://mysite.com/arcgis
    ---------------------     --------------------------------------------------------------------
    tokenurl                  optional string. Used when a site if federated or when the token
                              URL differs from the site's baseurl.  If a site is federated, the
                              token URL will return as the Portal token and ArcGIS Server users
                              will not validate correctly.
    ---------------------     --------------------------------------------------------------------
    username                  optional string, login username for BUILT-IN security
    ---------------------     --------------------------------------------------------------------
    password                  optional string, a secret word or phrase that must be used to gain
                              access to the account above.
    ---------------------     --------------------------------------------------------------------
    key_file                  optional string, path to PKI ket file
    ---------------------     --------------------------------------------------------------------
    cert_file                 optional string, path to PKI cert file
    ---------------------     --------------------------------------------------------------------
    proxy_host                optional string, web address to the proxy host

                              Example: proxy.mysite.com
    ---------------------     --------------------------------------------------------------------
    proxy_port                optional integer, default is 80. The port where the proxy resided on
    ---------------------     --------------------------------------------------------------------
    expiration                optional integer. The Default is 60. This is the length of time a
                              token is valid for.
                              Example 1440 is one week.
    ---------------------     --------------------------------------------------------------------
    all_ssl                   optional boolean. The default is False. If True, all calls will be
                              made over HTTPS instead of HTTP.
    ---------------------     --------------------------------------------------------------------
    portal_connection         optional GIS. This is used when a site is federated. It is the
                              ArcGIS Online or Portal GIS object used.
    =====================     ====================================================================


    """
    baseurl = None
    key_file = None
    cert_file = None
    all_ssl = None
    proxy_host = None
    proxy_port = None
    _token = None
    _product = None
    _referer = None
    _useragent = None
    _parsed_org_url = None
    _username = None
    _password = None
    _auth = None
    _tokenurl = None
    _token = None
    _server_token = None
    _connection = None
    _portal_connection = None
    _TOKEN_TIME = None
    _REFRESH_WHEN = None
    _handlers = None
    def __init__(self, baseurl=None, tokenurl=None, username=None,
                 password=None, key_file=None, cert_file=None,
                 expiration=60, all_ssl=False, referer=None,
                 proxy_host=None, proxy_port=None,
                 portal_connection=None, **kwargs):
        """ The ServerConnection constructor. Requires URL and optionally username/password. """
        self._verify_cert = kwargs.pop('verify_cert', True)
        self.baseurl = baseurl
        if self._tokenurl is None and \
           portal_connection is None:
            parsed = urlparse(baseurl)
            tokenurl = "{scheme}://{netloc}/{wa}/admin/generateToken".format(
                scheme=parsed.scheme,
                netloc=parsed.netloc,
                wa=parsed.path[1:].split('/')[0]
            )
        self._tokenurl = tokenurl
        self._username = username
        self._password = password
        self._expiration = expiration
        self.all_ssl = all_ssl
        if referer:
            self._referer = referer
        else:
            self._referer = urlparse(baseurl).netloc
        self.key_file = key_file
        self.cert_file = cert_file
        self.proxy_host = proxy_host
        self.proxy_port = proxy_port
        if portal_connection:
            if isinstance(portal_connection, _ArcGISConnection):
                self._portal_connection = portal_connection # second connection
            elif hasattr(self._portal_connection, '_con') and \
                 getattr(self._portal_connection, "_con") is not None:
                self._portal_connection = self._portal_connection._con
            elif isinstance(portal_connection, GIS):
                self._portal_connection = portal_connection._con
            else:
                raise ValueError("A portal_connection object be of type _ArcGISConnection or GIS")
        if self._portal_connection:
            self._product = "FEDERATED_SERVER"
        else:
            self._product = "SERVER"

        # Setup the referer and user agent
        if not referer:
            referer = urlparse(baseurl).netloc
        self._useragent = 'geosaurus/' + __version__
        parsed_url = urlparse(self.baseurl)
        self._parsed_org_url = urlunparse((parsed_url[0], parsed_url[1], "", "", "", ""))

        if cert_file is not None and key_file is not None:
            self._auth = "PKI"
        elif username is not None and password is not None:
            self._auth = "BUILTIN" # or "BASICAUTH" (LDAP) or NTLM or Kerberos (login sets this up)
        elif portal_connection:
            self._auth = "PORTAL_TOKEN"
            self.token
        else:
            self._auth = "ANON"

        # Login if credentials were provided
        if username and password:
            self.login(username, password, expiration)
        elif username or password:
            _log.warning('Both username and password required for login')
    #----------------------------------------------------------------------
    @property
    def product(self):
        if self._product is None:
            self._product = self._check_product()
        return self._product
    #----------------------------------------------------------------------
    @property
    def portal_connection(self):
        """gets/sets an additional connection object to get a token from"""
        return self._portal_connection
    #----------------------------------------------------------------------
    @portal_connection.setter
    def portal_connection(self, value):
        """gets/sets an additional connection object to get a token from"""
        if self._portal_connection != value:
            self._portal_connection = value
            self._token = None
            self._server_token = None
    #----------------------------------------------------------------------
    @property
    def token(self):
        """gets/sets the token"""
        if self._token:
            if self._REFRESH_WHEN and \
               datetime.datetime.now() > self._REFRESH_WHEN:
                self._token = None
                self.token
            return self._token
        if self._portal_connection and \
           self._server_token is None:
            if self._portal_connection.product == "AGO":
                return self._portal_connection.token
            parsed = urlparse(self.baseurl)
            adminURL = "https://%s/%s/admin" % (parsed.netloc, urlparse(self.baseurl).path[1:].split('/')[0])
            self._token = self.portal_connection.generate_portal_server_token(serverUrl=adminURL)
            self._REFRESH_WHEN = datetime.datetime.now() + datetime.timedelta(seconds=self._expiration)
            return self._token
        elif self._portal_connection and self._server_token:
            return self._server_token
        elif self._username and self._password:
            self.login(username=self._username,
                       password=self._password,
                       expiration=60)
            self._REFRESH_WHEN = datetime.datetime.now() + datetime.timedelta(seconds=self._expiration)
            return self._token
        return None
    #----------------------------------------------------------------------
    @token.setter
    def token(self, value):
        """gets/sets the token"""
        if self._token != value:
            self._token = value
    #----------------------------------------------------------------------
    def generate_token(self, username, password, expiration=60):
        """ Generates and returns a new token, but doesn't re-login. """
        if self.product == "SERVER":
            postdata = { 'username': username,
                         'password': password,
                         'client': 'requestip',
                         'expiration': expiration,
                         'f': 'json' }
        elif self.product == "FEDERATED_SERVER" and \
             self._portal_connection:
            parsed = urlparse(self.baseurl)
            adminURL = "%s://%s/%s/admin" % (parsed.scheme, parsed.netloc, urlparse(self.baseurl).path[1:].split('/')[0])
            token =  self.portal_connection.generate_portal_server_token(serverUrl=adminURL)
            return token
        else: # Assume username/password BUITIN
            postdata = { 'username': username, 'password': password,
                         'client': 'referer', 'referer': self._referer,
                         'expiration': expiration, 'f': 'json' }
        if self._tokenurl is None:
            if self.baseurl.endswith('/'):
                resp = self.post('generateToken', postdata,
                                 ssl=urlparse(self._tokenurl).scheme == 'https', add_token=False)
            else:
                resp = self.post('/generateToken', postdata,
                                 ssl=urlparse(self._tokenurl).scheme == 'https', add_token=False)
        else:

            resp = self.post(path=self._tokenurl, postdata=postdata,
                             ssl=urlparse(self._tokenurl).scheme == "https", add_token=False)
        if resp:
            return resp.get('token')
    #----------------------------------------------------------------------
    def login(self, username, password, expiration=60):
        """ Logs into the portal using username/password. """
        try:
            newtoken = self.generate_token(username,
                                           password, expiration)
            self._REFRESH_WHEN = datetime.datetime.now() + datetime.timedelta(seconds=expiration)
            if newtoken:
                self._token = newtoken
                self._username = username
                self._password = password
                self._expiration = expiration
                self._auth = "BUILTIN"
            return newtoken
        except HTTPError as err:
            if err.code == 401: # using basic authentication
                self._auth = "BASICAUTH"
            else:
                raise
    #----------------------------------------------------------------------
    def relogin(self, expiration=None):
        """ Re-authenticates with the portal using the same username/password. """
        if not expiration:
            expiration = self._expiration
        return self.login(self._username, self._password, expiration)
    #----------------------------------------------------------------------
    def logout(self):
        """ Logs out of the portal. """
        self._token = None
        self._server_token = None
    #----------------------------------------------------------------------
    @property
    def is_logged_in(self):
        """ Returns true if logged into the portal. """
        return self._token is not None or self._server_token is not None
    #----------------------------------------------------------------------
    def _mainType(self, resp):
        """ gets the main type from the response object"""
        if six.PY2:
            return resp.headers.maintype
        elif six.PY3:
            return resp.headers.get_content_maintype()
        else:
            return None
    #----------------------------------------------------------------------
    def _check_product(self):
        """
        determines if the product is portal, arcgis online or arcgis server
        """
        baseurl = self.baseurl
        if self.portal_connection:
            return "FEDERATED_SERVER"
        return "SERVER"
    #----------------------------------------------------------------------
    def _get_file_name(self, contentDisposition,
                       url, ext=".unknown"):
        """ gets the file name from the header or url if possible """
        if six.PY2:
            if contentDisposition is not None:
                return re.findall(r'filename[^;=\n]*=(([\'"]).*?\2|[^;\n]*)',
                                  contentDisposition.strip().replace('"', ''))[0][0]
            elif os.path.basename(url).find('.') > -1:
                return os.path.basename(url)
        elif six.PY3:
            if contentDisposition is not None:
                p = re.compile(r'filename[^;=\n]*=(([\'"]).*?\2|[^;\n]*)')
                return p.findall(contentDisposition.strip().replace('"', ''))[0][0]
            elif os.path.basename(url).find('.') > -1:
                return os.path.basename(url)
        return "%s.%s" % (uuid.uuid4().get_hex(), ext)
    #----------------------------------------------------------------------
    def _process_response(self, resp, out_folder=None,  file_name=None):
        """ processes the response object"""
        CHUNK = 4056
        maintype = self._mainType(resp)
        contentDisposition = resp.headers.get('content-disposition')
        contentType = resp.headers.get('content-type')
        contentLength = resp.headers.get('content-length')
        if contentType.find('application/json;') == -1 and \
           (maintype.lower() in ('image',
                                'application',
                                'application/x-zip-compressed') or \
           contentType == 'application/x-zip-compressed' or \
           (contentDisposition is not None and \
            contentDisposition.lower().find('attachment;') > -1)):
            fname = self._get_file_name(
                contentDisposition=contentDisposition,
                url=resp.geturl()).split('?')[0]
            if out_folder is None:
                out_folder = tempfile.gettempdir()
            if contentLength is not None:
                max_length = int(contentLength)
                if max_length < CHUNK:
                    CHUNK = max_length
            if file_name is None:
                file_name = os.path.join(out_folder, fname)
            else:
                file_name = os.path.join(out_folder, file_name)
            with open(file_name, 'wb') as writer:
                for data in self._chunk(response=resp):
                    writer.write(data)
                    del data
                del writer
            return file_name
        else:
            read = ""
            if file_name and out_folder:
                f_n_path = os.path.join(out_folder, file_name)
                with open(f_n_path, 'wb') as writer:
                    for data in self._chunk(response=resp, size=4096):
                        if six.PY3 == True:
                            writer.write(data)
                        else:
                            writer.write(data)
                        del data
                    writer.flush()
                return f_n_path
            else:
                for data in self._chunk(response=resp, size=4096):
                    if six.PY3 == True:
                        if read == "":
                            read = data
                        else:
                            read += data
                    else:
                        read += data
                    del data
            if six.PY3 and \
               len(read) > 0:
                try:
                    read = read.decode("utf-8").strip()
                except:
                    pass
            try:
                return read.strip()
            except:
                return read
        return ""
    #----------------------------------------------------------------------
    def _chunk(self, response, size=4096):
        """
        downloads a web response in pieces to ensure there are no
        memory issues.
        """
        method = response.headers.get("content-encoding")
        if method == "gzip":
            d = zlib.decompressobj(16+zlib.MAX_WBITS)
            b = response.read(size)
            while b:
                data = d.decompress(b)
                yield data
                b = response.read(size)
                del data
        else:
            while True:
                chunk = response.read(size)
                if not chunk: break
                yield chunk
    # ----------------------------------------------------------------------
    def get(self, path, params=None, ssl=False,
            compress=True, try_json=True, is_retry=False,
            use_ordered_dict=False, out_folder=None,
            file_name=None, force_bytes=False, **kwargs):
        """ Returns result of an HTTP GET. Handles token timeout and all SSL mode."""
        path = quote(path, ':/%')
        url = path
        if url.lower().find("https://") > -1 or\
           url.lower().find("http://") > -1:
            url = path
        elif len(url) == 0:
            url = self.baseurl
        elif (len(url) > 0 and url[0] == '/' ) == False and \
             self.baseurl.endswith('/') == False:
            url = "/{path}".format(path=url)

        if not url.startswith('http://') and \
           not url.startswith('https://'):
            url = self.baseurl + url
        if ssl or self.all_ssl:
            url = url.replace('http://', 'https://')

        # Add the token if logged in
        if params is None:
            params = {}
        if try_json:
            params['f'] = 'json'
        if self.is_logged_in:
            params['token'] = self.token
        if len(params.keys()) > 0:
            params = {k: jsonize_dict(v) for k, v in params.items()}
            url = "{url}?{params}".format(url=url,
                                          params=urlencode(params))
            #url = self._url_add_token(url, self.token)

        _log.debug('REQUEST (get): ' + url)

        try:
            # Send the request and read the response
            headers = [('User-Agent', self._useragent)]
            if self._referer:# and \
                #self._auth.lower() != 'pki':
                headers.append(('Referer', self._referer))

            if compress:
                headers.append(('Accept-encoding', 'gzip'))
            if self._handlers is None:
                self._handlers = self.get_handlers()
            opener = request.build_opener(*self._handlers)
            opener.addheaders = headers

            req = request.Request(url,
                                  headers={i[0] : i[1] for i in headers})
            resp = opener.open(req)
            resp_data = self._process_response(resp,
                                               out_folder=out_folder,
                                               file_name=file_name)
            #  if the response is a file saved to disk, return it.

            if (len(resp_data) < 32767) and os.path.isfile(resp_data):
                if force_bytes:
                    return open(resp_data, 'rb').read()
                return resp_data
            # If we're not trying to parse to JSON, return response as is
            if not try_json:
                return resp_data

            try:
                if use_ordered_dict:
                    resp_json = json.loads(resp_data,
                                           object_pairs_hook=OrderedDict)
                else:
                    resp_json = json.loads(resp_data)

                # Check for errors, and handle the case where the token timed
                # out during use (and simply needs to be re-generated)
                try:
                    if resp_json.get('error', None):
                        errorcode = resp_json['error']['code']
                        if errorcode == 498 and not is_retry:
                            _log.info('Token expired during get request, ' \
                                      + 'fetching a new token and retrying')
                            newtoken = self.relogin()
                            newpath = self._url_add_token(path, newtoken)
                            return self.get(path=newpath, params=params, ssl=ssl, compress=compress,
                                            try_json=try_json, is_retry=True)
                        elif errorcode == 498:
                            raise RuntimeError('Invalid token')
                        elif errorcode == 403:
                            message = resp_json['error']['message'] if 'message' in resp_json['error'] else ''
                            if message == "SSL Required":
                                return self.get(path=path, params=params, ssl=True, compress=compress,
                                                try_json=try_json, is_retry=True)

                        self._handle_json_error(resp_json['error'])
                        return None
                except AttributeError:
                    # Top-level JSON object isnt a dict, so can't have an error
                    pass

                # If the JSON parsed correctly and there are no errors,
                # return the JSON
                #if 'status' in resp_json: # FOR DEMO TODO REMOVE ME
                #    return resp_json['status'] == 'success'
                return resp_json

            # If we couldnt parse the response to JSON, return it as is
            except ValueError:
                return resp

        # If we got an HTTPError when making the request check to see if it's
        # related to token timeout, in which case, regenerate a token
        except HTTPError as e:
            if e.code == 498 and not is_retry:
                _log.info('Token expired during get request, fetching a new ' \
                          + 'token and retrying')
                self.logout()
                newtoken = self.relogin()
                newpath = self._url_add_token(path, newtoken)
                return self.get(newpath, ssl, try_json, is_retry=True)
            elif e.code == 498:
                raise RuntimeError('Invalid token')
            else:
                raise e
    #----------------------------------------------------------------------
    def _ensure_dir(self, f):
        if not os.path.exists(f):
            os.makedirs(f)
    #----------------------------------------------------------------------
    def _url_add_token(self, url, token):

        # Parse the URL and query string
        urlparts = urlparse(url)
        qs_list = parse_qsl(urlparts.query)

        # Update the token query string parameter
        replaced_token = False
        new_qs_list = []
        for qs_param in qs_list:
            if qs_param[0] == 'token':
                qs_param = ('token', token)
                replaced_token = True
            new_qs_list.append(qs_param)
        if not replaced_token:
            new_qs_list.append(('token', token))

        # Rebuild the URL from parts and return it
        return urlunparse((urlparts.scheme, urlparts.netloc,
                           urlparts.path, urlparts.params,
                           urlencode(new_qs_list),
                           urlparts.fragment))
    #----------------------------------------------------------------------
    def get_handlers(self):
        handlers = []
        if self._verify_cert == False:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            handler = request.HTTPSHandler(context=ctx)
            handlers.append(handler)

        from urllib.request import HTTPRedirectHandler
        redirect_handler = HTTPRedirectHandler()
        redirect_handler.max_redirections = 30
        redirect_handler.max_repeats = 30
        handlers.append(redirect_handler)
        if self._username and self._password:

            passman = request.HTTPPasswordMgrWithDefaultRealm()
            passman.add_password(None,
                                 self._parsed_org_url,
                                 self._username,
                                 self._password)
            handlers.append(request.HTTPBasicAuthHandler(passman))
            passman = request.HTTPPasswordMgrWithDefaultRealm()
            passman.add_password(None,
                                 self._parsed_org_url,
                                 self._username,
                                 self._password)
            handlers.append(request.HTTPDigestAuthHandler(passman))
            if os.name == 'nt':
                try:
                    from arcgis._impl.common._iwa import NtlmSspiAuthHandler, KerberosSspiAuthHandler

                    auth_krb = KerberosSspiAuthHandler()
                    handlers.append(auth_krb)

                    try:
                        auth_NTLM = NtlmSspiAuthHandler()
                        handlers.append(auth_NTLM)
                    except:
                        pass



                except Error as err:
                    _log.error("winkerberos packages is required for IWA authentication (NTLM and Kerberos).")
                    _log.error("Please install it:\n\tconda install winkerberos")
                    _log.error(str(err))
            else:
                _log.error('The GIS uses Integrated Windows Authentication which is currently only supported on the Windows platform')


        if self._auth == "PKI" or \
           (self.cert_file is not None and self.key_file is not None):
            handlers.append(HTTPSClientAuthHandler(self.key_file, self.cert_file))
        elif self._portal_connection and \
             self._portal_connection.cert_file is not None and \
             self._portal_connection.key_file is not None:
            handlers.append(HTTPSClientAuthHandler(self._portal_connection.key_file,
                                                   self._portal_connection.cert_file))

        cj = cookiejar.CookieJar()

        if self.proxy_host: # Simple Proxy Support
            from urllib.request import ProxyHandler
            if self.proxy_port is None:
                self.proxy_port = 80
            proxies = {"http":"http://%s:%s" % (self.proxy_host, self.proxy_port),
                       "https":"https://%s:%s" % (self.proxy_host, self.proxy_port)}
            proxy_support = ProxyHandler(proxies)
            handlers.append(proxy_support)

        handlers.append(request.HTTPCookieProcessor(cj))
        return handlers
    #----------------------------------------------------------------------
    def post(self, path, postdata=None, files=None, ssl=False, compress=True,
             is_retry=False, use_ordered_dict=False, add_token=True, verify_cert=True,
             token=None, **kwargs):
        """ Returns result of an HTTP POST. Supports Multipart requests."""
        #if path.find(" ") > -1:
        path = quote(path, ':/%')
        out_folder = kwargs.pop('out_folder', tempfile.gettempdir())

        url = path
        if url.lower().find("https://") > -1 or\
           url.lower().find("http://") > -1:
            url = path
        elif len(url) == 0:
            url = self.baseurl
        elif (len(url) > 0 and url[0] == '/' ) == False and \
           self.baseurl.endswith('/') == False:
            url = "/{path}".format(path=url)

        if not url.startswith('http://') and \
           not url.startswith('https://'):
            url = self.baseurl + url

        if ssl or self.all_ssl:
            url = url.replace('http://', 'https://')
        if verify_cert == False:
            import ssl
            ssl._create_default_https_context = ssl._create_unverified_context
        # Add the token if logged in
        if add_token:
            if self.is_logged_in:
                postdata['token'] = self.token
        if token:
            postdata['token'] = token
        if _log.isEnabledFor(logging.DEBUG):
            msg = 'REQUEST: ' + url + ', ' + str(postdata)
            if files:
                msg += ', files=' + str(files)
            _log.debug(msg)

        # If there are files present, send a multipart request
        if files:
            #parsed_url = urlparse(url)
            mpf = MultiPartForm(param_dict=postdata, files=files)
            req = request.Request(url)
            body = mpf.make_result
            req.add_header('User-agent', self._useragent)
            req.add_header('Content-type', mpf.get_content_type())
            req.add_header('Content-length', len(body))
            req.data = body
            headers = [('User-Agent', self._useragent),
                       ('Content-type', mpf.get_content_type()),
                       ('Content-length', len(body))]
            if self._referer and \
               self._auth.lower() != 'pki':
                headers.append(('Referer', self._referer))
            if compress:
                headers.append(('Accept-encoding', 'gzip'))
            if self._handlers is None:
                self._handlers = self.get_handlers()
            #handlers = self.get_handlers()
            opener = request.build_opener(*self._handlers)

            opener.addheaders = headers

            resp = opener.open(req)
            resp_data = self._process_response(resp)
        # Otherwise send a normal HTTP POST request
        else:
            encoded_postdata = None
            if postdata:
                postdata = {k: jsonize_dict(v) for k, v in postdata.items()}
                encoded_postdata = urlencode(postdata)
            headers = [('User-Agent', self._useragent)]
            if self._referer and \
                self._auth.lower() != 'pki':
                headers.append(('Referer', self._referer))
            if compress:
                headers.append(('Accept-encoding', 'gzip'))
            if self._handlers is None:
                self._handlers = self.get_handlers()

            opener = request.build_opener(*self._handlers)
            opener.addheaders = headers
            #request.install_opener(opener)
            req = request.Request(url,
                                  data=encoded_postdata.encode('utf-8'),
                                  headers={i[0] : i[1] for i in headers})
            resp = opener.open(req)#request.urlopen(req)
            resp_data = self._process_response(resp,
                                               out_folder=out_folder,
                                               file_name=None)
        # Parse the response into JSON
        if _log.isEnabledFor(logging.DEBUG):
            _log.debug('RESPONSE: ' + url + ', ' + resp_data)
        #print(resp_data);
        if use_ordered_dict:
            resp_json = json.loads(resp_data, object_pairs_hook=OrderedDict)
        else:
            resp_json = json.loads(resp_data)


        # Check for errors, and handle the case where the token timed out
        # during use (and simply needs to be re-generated)
        try:
            if 'error' in resp_json or \
               ('status' in resp_json and \
                resp_json.get('status', None) != "success"):

                errorcode = resp_json['code'] if 'code' in resp_json else 0
                if errorcode == 498 and not is_retry:
                    _log.info('Token expired during post request, fetching a new '
                              + 'token and retrying')
                    self.logout()
                    newtoken = self.relogin()
                    postdata['token'] = newtoken
                    return self.post(path, postdata, files, ssl, compress,
                                     is_retry=True)
                elif errorcode == 498:
                    raise RuntimeError('Invalid token')
                elif errorcode == 403:
                    message = resp_json['error']['message'] if 'message' in resp_json['error'] else ''
                    if message == "SSL Required":
                        return self.post(path, postdata, files, ssl=True, compress=compress, token=token,
                                         verify_cert=verify_cert, is_retry=True)

                if 'status' in resp_json:
                    self._handle_json_error(resp_json, errorcode)
                else:
                    self._handle_json_error(resp_json['error'], errorcode)
                return None
        except AttributeError:
            # Top-level JSON object isnt a dict, so can't have an error
            pass
        return resp_json
    #----------------------------------------------------------------------
    def _get_content_type(self, filename):
        return mimetypes.guess_type(filename)[0] or 'application/octet-stream'
    #----------------------------------------------------------------------
    def _handle_json_error(self, error, errorcode):
        if 'messages' in error:
            errormessage = ""
        else:
            errormessage = error.get('message', 'Unknown Error')
        _log.error(errormessage)
        if 'details' in error and error['details'] is not None:
            for errordetail in error['details']:
                errormessage = errormessage + "\n" + errordetail
                _log.error(errordetail)
        elif 'messages' in error and error['messages'] is not None:
            for errordetail in error['messages']:
                errormessage = errormessage + "\n" + errordetail
        errormessage = errormessage + "\n(Error Code: " + str(errorcode) +")"
        raise RuntimeError(errormessage)
########################################################################
class _StrictURLopener(request.FancyURLopener):
    def http_error_default(self, url, fp, errcode, errmsg, headers):
        if errcode != 200:
            raise HTTPError(url, errcode, errmsg, headers, fp)

def _normalize_url(url, charset='utf-8'):
    """ Normalizes a URL. Based on http://code.google.com/p/url-normalize."""
    def _clean(string):
        string = str(unquote(string), 'utf-8', 'replace')
        return unicodedata.normalize('NFC', string).encode('utf-8')

    default_port = {
        'ftp': 21,
        'telnet': 23,
        'http': 80,
        'gopher': 70,
        'news': 119,
        'nntp': 119,
        'prospero': 191,
        'https': 443,
        'snews': 563,
        'snntp': 563,
    }

    # if there is no scheme use http as default scheme
    if url[0] not in ['/', '-'] and ':' not in url[:7]:
        url = 'http://' + url


    # shebang urls support
    url = url.replace('#!', '?_escaped_fragment_=')

    # splitting url to useful parts
    scheme, auth, path, query, fragment = urlsplit(url.strip())
    (userinfo, host, port) = re.search('([^@]*@)?([^:]*):?(.*)', auth).groups()

    # Always provide the URI scheme in lowercase characters.
    scheme = scheme.lower()

    # Always provide the host, if any, in lowercase characters.
    host = host.lower()
    if host and host[-1] == '.':
        host = host[:-1]
    # take care about IDN domains
    host = host.decode(charset).encode('idna')  # IDN -> ACE

    # Only perform percent-encoding where it is essential.
    # Always use uppercase A-through-F characters when percent-encoding.
    # All portions of the URI must be utf-8 encoded NFC from Unicode strings
    path = quote(_clean(path), "~:/?#[]@!$&'()*+,;=")
    fragment = quote(_clean(fragment), "~")

    # note care must be taken to only encode & and = characters as values
    query = "&".join(["=".join([quote(_clean(t), "~:/?#[]@!$'()*+,;=") \
                                for t in q.split("=", 1)]) for q in query.split("&")])

    # Prevent dot-segments appearing in non-relative URI paths.
    if scheme in ["", "http", "https", "ftp", "file"]:
        output = []
        for part in path.split('/'):
            if part == "":
                if not output:
                    output.append(part)
            elif part == ".":
                pass
            elif part == "..":
                if len(output) > 1:
                    output.pop()
            else:
                output.append(part)
        if part in ["", ".", ".."]:
            output.append("")
        path = '/'.join(output)

    # For schemes that define a default authority, use an empty authority if
    # the default is desired.
    if userinfo in ["@", ":@"]:
        userinfo = ""

    # For schemes that define an empty path to be equivalent to a path of "/",
    # use "/".
    if path == "" and scheme in ["http", "https", "ftp", "file"]:
        path = "/"

    # For schemes that define a port, use an empty port if the default is
    # desired
    if port and scheme in list(default_port.keys()):
        if port.isdigit():
            port = str(int(port))
            if int(port) == default_port[scheme]:
                port = ''

    # Put it all back together again
    auth = (userinfo or "") + host
    if port:
        auth += ":" + port
    if url.endswith("#") and query == "" and fragment == "":
        path += "#"
    return urlunsplit((scheme, auth, path, query, fragment))

def _parse_hostname(url, include_port=False):
    """ Parses the hostname out of a URL."""
    if url:
        parsed_url = urlparse((url))
        return parsed_url.netloc if include_port else parsed_url.hostname

def _is_http_url(url):
    if url:
        return urlparse(url).scheme in ['http', 'https']

def _unpack(obj_or_seq, key=None, flatten=False):
    """ Turns a list of single item dicts in a list of the dict's values."""

    # The trivial case (passed in None, return None)
    if not obj_or_seq:
        return None

    # We assume it's a sequence
    new_list = []
    for obj in obj_or_seq:
        value = _unpack_obj(obj, key, flatten)
        new_list.extend(value)

    return new_list

def _unpack_obj(obj, key=None, flatten=False):
    try:
        if key:
            value = [obj.get(key)]
        else:
            value = list(obj.values())
    except AttributeError:
        value = [obj]

    # Flatten any lists if directed to do so
    if value and flatten:
        value = [item for sublist in value for item in sublist]

    return value

def _remove_non_ascii(s):
    return ''.join(i for i in s if ord(i) < 128)

def _tostr(obj):
    if not obj:
        return ''
    if isinstance(obj, list):
        return ', '.join(map(_tostr, obj))
    return str(obj)




# This function is a workaround to deal with what's typically described as a
# problem with the web server closing a connection. This is problem
# experienced with www.arcgis.com (first encountered 12/13/2012). The problem
# and workaround is described here:
# http://bobrochel.blogspot.com/2010/11/bad-servers-chunked-encoding-and.html
def _patch_http_response_read(func):
    def inner(*args):
        try:
            return func(*args)
        except http_client.IncompleteRead as e:
            return e.partial

    return inner
http_client.HTTPResponse.read = _patch_http_response_read(http_client.HTTPResponse.read)
