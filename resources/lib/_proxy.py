﻿#!/usr/bin/python
# -*- coding: utf-8 -*-
import _addoncompat
import cookielib
import BaseHTTPServer
import os
import os.path
import sys
import xbmc
import re
import base64
import httplib
import socket
import traceback
import time
import urllib
import urllib2
import simplejson

sys.path.append(
    os.path.abspath(xbmc.translatePath(_addoncompat.get_path())))

from dns.resolver import Resolver

PLUGINPATH = xbmc.translatePath(_addoncompat.get_path())
RESOURCESPATH = os.path.join(PLUGINPATH,'resources')
CACHEPATH = os.path.join(RESOURCESPATH,'cache')
VIDEOPATH = os.path.join(CACHEPATH,'videos')
KEYFILE = os.path.join(CACHEPATH,'play.key')
PLAYFILE = os.path.join(CACHEPATH,'play.m3u8')
COOKIE = os.path.join(CACHEPATH,'cookie.txt')

HOST_NAME = 'localhost'
PORT_NUMBER = int(sys.argv[1])

class MyHTTPConnection(httplib.HTTPConnection):
	_dnsproxy = []
	def connect(self):
		resolver = Resolver()
		resolver.nameservers = self._dnsproxy
		answer = resolver.query(self.host, 'A')
		self.host = answer.rrset.items[0].address
		self.sock = socket.create_connection((self.host, self.port))

class MyHTTPHandler(urllib2.HTTPHandler):
	_dnsproxy = []
	def http_open(self, req):
		MyHTTPConnection._dnsproxy = self._dnsproxy 
		return self.do_open(MyHTTPConnection, req)
		
class StoppableHTTPServer(BaseHTTPServer.HTTPServer):
	def serve_forever(self):
		self.stop = False
		while not self.stop:
			self.handle_request()

class StoppableHttpRequestHandler(BaseHTTPServer.BaseHTTPRequestHandler):
	def _writeheaders(self):
		self.send_response(200)
		self.send_header('Content-type', 'text/html')
		self.end_headers()

	def do_HEAD(self):
		self._writeheaders()

	def do_GET(self):
		self.answer_request(1)

	def answer_request(self, sendData):
		request_path = self.path[1:]
		request_path = re.sub(r'\?.*', '', request_path)
		if 'stop' in self.path:
			self._writeheaders()
			self.server.stop = True
			print 'Server stopped'
		elif 'play.key' in self.path:
			try:
				self._writeheaders()
				file = open(KEYFILE.replace('play.key', request_path), 'r')
				data = file.read()
				self.wfile.write(data)
				file.close()
			except IOError:
				self.send_error(404, 'File Not Found: %s' % self.path)
			return
		elif 'm3u8' in self.path:
			try:
				self._writeheaders()
				file = open(PLAYFILE.replace('play.m3u8', request_path), 'r')
				data = file.read()
				self.wfile.write(data)
				file.close()
			except IOError:
				self.send_error(404, 'File Not Found: %s' % self.path)
			return
		elif 'foxstation' in self.path:
			realpath = urllib.unquote_plus(request_path[11:])
			fURL = base64.b64decode(realpath)
			self.serveFile(fURL, sendData)
		elif 'proxy' in self.path:
			realpath = urllib.unquote_plus(request_path[6:])
			proxyconfig = realpath.split('/')[1]
			proxy_object = simplejson.loads(proxyconfig)
			if int(proxy_object['connectiontype']) == 1:
				proxies = proxy_object['dns_proxy']
				MyHTTPHandler._dnsproxy = proxies
				handler = MyHTTPHandler
			elif int(proxy_object['connectiontype']) == 2:
				proxy = proxy_object['proxy']
				us_proxy = 'http://' + proxy['us_proxy'] + ':' + proxy['us_proxy_port']
				proxy_handler = urllib2.ProxyHandler({'http' : us_proxy})
				handler = proxy_handler
			realpath = realpath.split('/')[0]
			fURL = base64.b64decode(realpath)
			
			self.serveFile(fURL, sendData, handler)

	def serveFile(self, fURL, sendData, httphandler = None):
		
		cj = cookielib.LWPCookieJar(COOKIE) 
		if httphandler is None:
			opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cj))
		else:
			opener = urllib2.build_opener(httphandler, urllib2.HTTPCookieProcessor(cj))
		
		request = urllib2.Request(url = fURL)
		opener.addheaders = []
		d = {}
		sheaders = self.decodeHeaderString(''.join(self.headers.headers))
		for key in sheaders:
			d[key] = sheaders[key]
			if (key != 'Host'):
				opener.addheaders = [(key, sheaders[key])]
			if (key == 'User-Agent'):
				opener.addheaders = [('User-Agent', 'Mozilla/5.0 (Windows NT 6.1; Win64; x64; rv:25.0) Gecko/20100101 Firefox/25.0')]
		if os.path.isfile(COOKIE):
			cj.load(ignore_discard = True)
			cj.add_cookie_header(request)
		response = opener.open(request)
		self.send_response(200)
		headers = response.info()
		for key in headers:
			try:
				val = headers[key]
				self.send_header(key, val)
			except Exception, e:
				print e
				pass
		self.end_headers()
		if (sendData):
			fileout = self.wfile
			try:
				buf = 'INIT'
				try:
					while ((buf != None) and (len(buf) > 0)):
						buf = response.read(8 * 1024)
						fileout.write(buf)
						fileout.flush()
					response.close()
					fileout.close()
				except socket.error, e:
					print time.asctime(), 'Client closed the connection.'
					try:
						response.close()
						fileout.close()
					except Exception, e:
						return
				except Exception, e:
					traceback.print_exc(file = sys.stdout)
					response.close()
					fileout.close()
			except:
				traceback.print_exc()
				fileout.close()
				return
		try:
			fileout.close()
		except:
			pass

	def decodeHeaderString(self, hs):
		di = {}
		hss = hs.replace('\r', '').split('\n')
		for line in hss:
			u = line.split(': ')
			try:
				di[u[0]] = u[1]
			except:
				pass
		return di

def runserver(server_class = StoppableHTTPServer,
		handler_class = StoppableHttpRequestHandler):
	server_address = (HOST_NAME, PORT_NUMBER)
	httpd = server_class(server_address, handler_class)
	httpd.serve_forever()

if __name__ == '__main__':
	runserver()
