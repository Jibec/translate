#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2008 Zuza Software Foundation
#
# This file is part of Translate.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, see <http://www.gnu.org/licenses/>.

import StringIO
import urllib
import simplejson as json
import pycurl
import gobject

class RESTClient(object):
    """Nonblocking client that can handle multiple HTTP REST requests"""

    class Request(gobject.GObject):
        """Single HTTP REST request, blocking if used standalone"""
        def __init__(self, url, id, method='GET', data=None, headers=None):
            gobject.GObject.__init__(self)
            self.result = StringIO.StringIO()
            self.result_headers = StringIO.StringIO()
            
            # do we really need to keep these around?
            self.url = url
            self.id = id
            self.method = method
            self.data = data
            self.headers = headers

            # the actual curl request object
            self.curl = pycurl.Curl()
            self.curl.setopt(pycurl.WRITEFUNCTION, self.result.write)
            self.curl.setopt(pycurl.HEADERFUNCTION, self.result_headers.write)
            self.curl.setopt(pycurl.URL, self.url + "/" + urllib.quote_plus(id))
            # let's set the HTTP request method
            if method == 'GET':
                self.curl.setopt(pycurl.HTTPGET, 1)
            elif method == 'POST':
                self.curl.setopt(pycurl.POST, 1)
            elif method == 'PUT':
                self.curl.setopt(pycurl.UPLOAD, 1)
            else:
                self.curl.setopt(pycurl.CUSTOMREQUEST, method)
            if data:
                self.curl.setopt(pycurl.READDATA, json.dumps(data))
            if headers:
                self.curl.setopt(pycurl.HTTPHEADER, headers)
            #self reference required cause CurlMulti will only return
            #Curl handles
            self.curl.request = self

        # define __hash__ and __eq__ so we can have meaningful sets
        def __hash__(self):
            return hash((self.url, self.id, self.method, self.data, self.headers))
        def __eq__(self, other):
            return (self.url, self.id, self.method, self.data, self.headers) == (other.url, other.id, other.method, other.data, other.headers)

        def perform(self):
            """run the request (blocks)"""
            self.curl.perform()

        def handle_result(self):
            """called after http request is done"""
            (id, data) = json.loads(self.result.getvalue())
            self.emit("REST-success", id, data)
            
            
    def __init__(self):
        self.running = False
        self.requests = set()
        self.curl = pycurl.CurlMulti()


    def add(self,request):
        """add a request to the queue"""
        self.curl.add_handle(request.curl)
        self.requests.add(request)
        self.run()
    
    def run(self):
        """client should not be running when request queue is empty"""
        if self.running: return
        gobject.timeout_add(100, self.perform)
        self.running = True
    
    def close_request(self, handle):
        """finalize a successful request"""
        self.curl.remove_handle(handle)
        handle.request.handle_result()
        self.requests.remove(handle.request)

    def perform(self):
        """main event loop function, non blocking execution of all queued requests"""
        ret, num_handles = self.curl.perform()
        num, completed, failed = self.curl.info_read()
        [self.close_request(com) for com in completed]
        #TODO: handle failed requests

        if ret != pycurl.E_CALL_MULTI_PERFORM and num_handles == 0:
            #we are done with this batch what do we do?
            self.running = False
            return False

        return True
        

gobject.signal_new("REST-success", RESTClient.Request,
                   gobject.SIGNAL_RUN_LAST,
                   gobject.TYPE_NONE,
                   (gobject.TYPE_PYOBJECT, gobject.TYPE_PYOBJECT))
