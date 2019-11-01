import six.moves.urllib
from six.moves.urllib.request import BaseHandler
from six.moves.urllib.response import addinfourl
from six.moves.http_client import HTTPConnection, HTTPSConnection
import base64
import sys

import winkerberos as kerberos

import logging
_log = logging.getLogger(__name__)


class SspiNtlmAuth:
    def __init__(self, user=None):
        status, self.ctx = kerberos.authGSSClientInit("NTLM", gssflags=0, mech_oid=kerberos.GSS_MECH_OID_SPNEGO)

    def create_auth_req(self):
        return self.create_challenge_response('')

    def create_challenge_response(self, challenge):
        status = kerberos.authGSSClientStep(self.ctx, challenge)
        auth_req = kerberos.authGSSClientResponse(self.ctx)
        return auth_req


class NtlmSspiAuthHandler(BaseHandler):
    handler_order = 480

    def __init__(self):
        self.sspiauth = SspiNtlmAuth()

    def http_error_401(self, req, fp, code, msg, headers):
        _log.info('Using NTLM handler')
        url = req.full_url
        response = self.http_error_ntlm_auth_reqed(url, req, headers, 'WWW-Authenticate', 'Authorization', fp)
        return response

    def http_error_407(self, req, fp, code, msg, headers):
        url = req.full_url
        response = self.http_error_ntlm_auth_reqed(url, req, headers, 'Proxy-Authenticate', 'Proxy-authorization', fp)
        return response

    def get_auth_req(self):
        return self.sspiauth.create_auth_req()

    def create_challenge_response(self, input_buffer):
        try:
            return self.sspiauth.create_challenge_response(input_buffer)
        except:
            return None

    def http_error_ntlm_auth_reqed(self, host, req, headers, authenticatehdr, authhdr, fp):
        ntlmsig = authenticatehdr + ': NTLM\n'
        if ntlmsig in str(headers):
            fp.close()
            return self.retry_http_ntlm_sspi_auth(host, req, authenticatehdr, authhdr)

    def retry_http_ntlm_sspi_auth(self, host, req, authenticatehdr, auth_header):
        url = req.full_url
        scheme, _, host, path = url.split('/', 3)

        h = HTTPConnection(host) if scheme == 'http:' else HTTPSConnection(host)
        headers = dict(req.unredirected_hdrs)
        headers.update(dict((k, v) for k, v in req.headers.items() if k not in headers))

        headers["Connection"] = "Keep-Alive"
        headers[auth_header] = "NTLM " + self.get_auth_req()

        h.request(req.get_method(), req.selector, req.data, headers)

        response = h.getresponse()
        response.fp = None  # keep-alive

        ntlmauth = response.headers.get(authenticatehdr)
        if ntlmauth is not None and ntlmauth.startswith('NTLM '):
            challenge = ntlmauth[5:]

            challenge_response = self.create_challenge_response(challenge)

            if challenge_response is None:
                _log.warning('Failed to authenticate using NTLM')
                return None
            headers["Connection"] = "Close"
            headers[auth_header] = "NTLM " + challenge_response

            h.request(req.get_method(), req.selector, req.data, headers)

            response = h.getresponse()

            return addinfourl(response, response.msg, req.get_full_url(), response.status)
        
class KerberosSspiAuthHandler(BaseHandler):
    
    handler_order = 360
    
    def http_error_401(self, req, fp, code, msg, headers):
        _log.info('Using Kerberos handler')
        url = req.full_url
        response = self.http_error_krb_auth_reqed(url, req, headers, fp)
        return response

    def http_error_krb_auth_reqed(self, host, req, headers, fp):
        krbsig = 'WWW-Authenticate: Negotiate\n'
        if krbsig in str(headers):
            fp.close()
            return self.retry_http_krb_sspi_auth(host, req)

    def retry_http_krb_sspi_auth(self, host, req):
        url = req.full_url
        scheme, _, host, path = url.split('/', 3)
        
        h = HTTPConnection(host) if scheme == 'http:' else HTTPSConnection(host)
        headers = dict(req.unredirected_hdrs)
        headers.update(dict((k, v) for k, v in req.headers.items() if k not in headers))
        
        try:
            __, krb_context = kerberos.authGSSClientInit("HTTP@" + host)
            kerberos.authGSSClientStep(krb_context, "")

            negotiate_details = kerberos.authGSSClientResponse(krb_context)
            
            headers["Connection"] = "Keep-Alive"
            headers["Authorization"] = "Negotiate " + negotiate_details
            h.request(req.get_method(), req.selector, req.data, headers)
            response = h.getresponse()
            return addinfourl(response, response.msg, req.get_full_url(), response.status)
        except:
            # e = sys.exc_info()[0]
            # _log.warning(str(e))
            # _log.warning('Failed Kerberos authentication')
            return None
