#!/usr/bin/python
# -*- coding: utf-8 -*-
import common
import connection
import m3u8
import base64
import datetime
import os
import ustvpaths
import re
import simplejson
import sys
import threading
import time
import urllib
import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin
from bs4 import BeautifulSoup, SoupStrainer
try:
	from pycaption import detect_format, SRTWriter
except:
	detect_format = None
from Queue import PriorityQueue

addon = xbmcaddon.Addon()
player = common.XBMCPlayer()
pluginHandle = int(sys.argv[1])

VIDEOURL = 'http://media.mtvnservices.com/'
VIDEOURLAPI = 'http://media-utils.mtvnservices.com/services/MediaGenerator/%s'
VIDEOURLAPIHLS = 'http://media-utils.mtvnservices.com/services/MediaGenerator/%s?device=Android&deviceOsVersion=4.4.4'
TYPES = [('fullEpisodes' , 'Full Episodes'), ('bonusClips,afterShowsClips,recapsClips,sneakPeeksClips,dailies,showClips' , 'Extras')]
DEVICE = 'Xbox'
BITRATERANGE = 10
TIMEOUT = 50

class Thread(threading.Thread): 
	def __init__(self, target, *args):
		self._target = target
		self._args = args
		threading.Thread.__init__(self)
		
	def run(self):
		self._target(*self._args)

def masterlist(SITE, SHOWS):
	master_db = []
	master_data = connection.getURL(SHOWS)
	master_tree = simplejson.loads(master_data)
	for master_item in master_tree['promoList']['promos']:
		try:
			master_item = master_item['promo']['associatedContent']['series']
			master_name = master_item['title']
			master_id = master_item['seriesId']
			if master_id is not None:
				master_db.append((master_name, SITE, 'seasons', master_id))
			else:
				pass
		except:
			pass
	return master_db

def seasons(SITE, API, season_id = common.args.url):
	seasons = []
	count = 0
	for type in TYPES:
		season_url = API + 'series/' + season_id + '/playlists.json?page=0&pageSize=500&type=' + type[0]
		season_data = connection.getURL(season_url)
		try:
			season_tree = simplejson.loads(season_data)['series']['playlists']
			for season_item in season_tree:
				try:
					if (season_item['playlist']['distributionPolicies'][0]['distributionPolicy']['policyType'] == 'playable'):
						count = count + 1
				except:
					if (season_item['playlist']['distributionPolicies'][0]['policyType'] == 'playable'):
						count = count + 1
				else:
					count = count
			if count > 0:
				seasons.append((type[1], SITE, 'episodes', season_url, -1, -1))
		except:
			pass
	return seasons

def episodes(SITE, episode_url = common.args.url):
	episodes = []
	episode_data = connection.getURL(episode_url)
	episode_tree = simplejson.loads(episode_data)
	for episode_item in episode_tree['series']['playlists']:
		show_name = episode_tree['series']['title']
		episode_item = episode_item['playlist']
		if '|' in episode_item['headline']:
			episode_name = episode_item['headline'].split('|')[-1].strip()
		elif '- ' in episode_item['headline']:
			episode_name = episode_item['headline'].split('- ')[-1].strip()
		else:
			try:
				episode_name = episode_item['headline'].split(':')[1].strip()
			except:
				episode_name = episode_item['headline']
		try:
			episode_info = re.compile('[s|S]([0-9]).[e|E]?([0-9]{0,2}).*').findall(episode_item['title'])
			try:
				episode_season, episode_number = episode_info[0]
			except:
				episode_season = episode_info
				episode_number = -1
		except:
			episode_season = -1
			episode_number = -1
		url = episode_item['id']
		try:
			episode_plot = episode_item['subhead']
		except:
			episode_plot = ''
		episode_thumb = episode_item['image']
		try:
			episode_duration = common.format_seconds(episode_item['duration']['timecode'])
		except:
			continue
		episode_type = episode_item['contentType'][:-1]
		episode_airdate = common.format_date(epoch = episode_item['postedDate']['timestamp'])
		u = sys.argv[0]
		u += '?url="' + urllib.quote_plus(url) + '"'
		u += '&mode="' + SITE + '"'
		u += '&sitemode="play"'
		infoLabels = {	'title' : episode_name,
						'plot' : episode_plot,
						'durationinseconds' : episode_duration,
						'TVShowTitle' : show_name,
						'season' : episode_season,
						'episode' : episode_number,
						'premiered' : episode_airdate}
		try:
			if (episode_item['distributionPolicies'][0]['distributionPolicy']['policyType'] == 'playable'):
				episodes.append((u, episode_name, episode_thumb, infoLabels, 'list_qualities', False, episode_type))
		except:
			if (episode_item['distributionPolicies'][0]['policyType'] == 'playable'):
				episodes.append((u, episode_name, episode_thumb, infoLabels, 'list_qualities', False, episode_type))
		else:
			pass
	return episodes

def play_video(BASE, video_uri = common.args.url, media_base = VIDEOURL):
	video_url = media_base + video_uri
	try:
		qbitrate = common.args.quality
	except:
		qbitrate = None
	video_url2 = 'stack://'
	closedcaption = []
	exception = False
	queue = PriorityQueue()
	segments = []
	if 'feed' in video_uri:
		feed_url = video_uri
	else:
		swf_url = connection.getRedirect(video_url, header = {'Referer' : BASE})
		params = dict(item.split("=") for item in swf_url.split('?')[1].split("&"))
		uri = urllib.unquote_plus(params['uri'])
		config_url = urllib.unquote_plus(params['CONFIG_URL'].replace('Other', DEVICE))
		config_data = connection.getURL(config_url, header = {'Referer' : video_url, 'X-Forwarded-For' : '12.13.14.15'})
		config_tree = BeautifulSoup(config_data, 'html.parser')
		if not config_tree.error:
			feed_url = config_tree.feed.string
			uri = urllib.quote_plus(uri)
			feed_url = feed_url.replace('{uri}', uri).replace('&amp;', '&').replace('{device}', DEVICE).replace('{ref}', 'None').replace('{type}', 'network').strip()
		else:
				exception = True
				error_text = config_tree.error.string.split('/')[-1].split('_') 
				if error_text[1] == 'loc':
					params = dict(item.split("=") for item in config_url.split('?')[-1].split('&'))
					common.show_exception('Geo', params['geo'])
	if not exception:
		feed_data = connection.getURL(feed_url,  header = {'X-Forwarded-For' : '12.13.14.15'})
		video_tree = BeautifulSoup(feed_data, 'html.parser', parse_only = SoupStrainer('media:group'))
		video_segments = video_tree.find_all('media:content')
		if not video_segments:
			video_tree = BeautifulSoup(feed_data, 'html.parser')
			common.show_exception(video_tree.find('meta', property = "og:site_name")['content'], video_tree.find('meta', property = "og:url")['content'])
			exception = True
		threads = []
		for i, video_item in enumerate(video_segments):
			try:
				threads.append(Thread(get_videos, queue, i, video_item, qbitrate, False))
			except Exception, e:
				print "Exception: ", e
		[i.start() for i in threads]
		[i.join() for i in threads]
		while not queue.empty():
			video_data2 = queue.get()
			video_url2 += video_data2[1] + ' , '
			segments.append(video_data2[2])
			closedcaption.append((video_data2[3], int(video_data2[0])))
		player._segments_array = segments
		finalurl = video_url2[:-3]
		time.sleep(20)
		if (addon.getSetting('enablesubtitles') == 'true') and closedcaption and detect_format is not None:
			convert_subtitles(closedcaption)
			player._subtitles_Enabled = True
		item = xbmcgui.ListItem(path = finalurl)
		if player._localHTTPServer:
			filestring = 'XBMC.RunScript(' + os.path.join(ustvpaths.LIBPATH,'proxy.py') + ', 12345)'
			xbmc.executebuiltin(filestring)
			finalurl = video_url2[:-3]
			#localhttpserver = True
			time.sleep(20)
		queue.task_done()
		try:
			item.setThumbnailImage(common.args.thumb)
		except:
			pass
		try:
			item.setInfo('Video', {	'title' : common.args.name,
									'season' : common.args.season_number,
									'episode' : common.args.episode_number,
									'TVShowTitle' : common.args.show_title })
		except:
			pass

		xbmcplugin.setResolvedUrl(pluginHandle, True, item)
		while player.is_active:
			player.sleep(250)

def play_video2(API, video_url = common.args.url, rtmp = True):
	try:
		qbitrate = common.args.quality
	except:
		qbitrate = None
	video_url2 = 'stack://'
	threads = []
	segments = []
	closedcaption = []
	queue = PriorityQueue()
	video_data = connection.getURL(API + 'playlists/%s/videos.json' % video_url)
	video_tree = simplejson.loads(video_data)
	video_item = video_tree['playlist']['videos']
	for i in range(0, len(video_item)):
		try:
			threads.append(Thread(get_videos, queue, i, video_item[i], qbitrate, rtmp))
		except Exception, e:
			print "Exception: ", e
	[i.start() for i in threads]
	[i.join() for i in threads]
	while not queue.empty():
		video_data2 = queue.get()
		video_url2 += video_data2[1] + ' , '
		segments.append(video_data2[2])
		closedcaption.append((video_data2[3], int(video_data2[0])))
	player._segments_array = segments
	finalurl = video_url2[:-3]
	if (addon.getSetting('enablesubtitles') == 'true') and closedcaption and detect_format is not None:
		convert_subtitles(closedcaption)
		player._subtitles_Enabled = True
	item = xbmcgui.ListItem(path = finalurl)
	queue.task_done()
	try:
		item.setThumbnailImage(common.args.thumb)
	except:
		pass
	try:
		item.setInfo('Video', {	'title' : common.args.name,
								'season' : common.args.season_number,
								'episode' : common.args.episode_number,
								'TVShowTitle' : common.args.show_title })
	except:
		pass
	xbmcplugin.setResolvedUrl(pluginHandle, True, item)
	while player.is_active:
		player.sleep(250)

def get_videos(queue, i, video_item, qbitrate, rtmp = False):
	try:
		video_mgid = video_item['video']['mgid']
	except:
		try:
			video_mgid = video_item['url'].split('uri=')[1].split('&')[0]
		except:
			try:
				video_mgid = video_item['url'].split('mgid=')[1].split('&')[0]
			except:
				video_mgid = video_item['url'].split('/')[-1].split('?')[0]
	video_data = connection.getURL(VIDEOURLAPI % video_mgid)
	video_tree = BeautifulSoup(video_data, 'html.parser')
	try:
		duration = video_tree.findAll('rendition')[0]['duration']
	except:
		duration = 0
	try:
		closedcaption = video_tree.find('typographic', format = 'ttml')['src']
	except:
		closedcaption = None
	hbitrate = -1
	lbitrate = -1
	sbitrate = int(addon.getSetting('quality'))
	if  rtmp:
		try:
			video_url2 = video_tree.findAll('rendition')
			if qbitrate is None:
				for video_index in video_url2:
					bitrate = int(video_index['bitrate'])
					if bitrate < lbitrate or lbitrate == -1:
						lbitrate = bitrate
						lplaypath_url = video_index.src.string	
					if bitrate > hbitrate and bitrate <= sbitrate:
						hbitrate = bitrate
						playpath_url = video_index.src.string
			else:
				playpath_url = video_tree.find('rendition', bitrate = qbitrate).src.string
			if playpath_url is None:
				playpath_url = lplaypath_url
			if "gsp.alias" in playpath_url:
				file_name = 'rtmpe://cp10740.edgefcs.net/ondemand/mtvnorigin/gsp.alias' + playpath_url.split('/gsp.alias')[1]
			else:
				file_name = playpath_url
			queue.put([i, file_name, duration, closedcaption])
		except:
			pass
	else:
		try:
			video_data = connection.getURL(VIDEOURLAPIHLS % video_mgid)
			video_tree = BeautifulSoup(video_data, 'html.parser')
			video_menu = video_tree.src.string
			hbitrate = -1
			lbitrate = -1
			m3u8_url = None
			#can we just pass video_menu
			
			if addon.getSetting('sel_quality') == 'true' or qbitrate is not None or  int(xbmc.getInfoLabel( "System.BuildVersion" )[:2]) < 14 or common.use_proxy() :
				m3u8_master_data = connection.getURL(video_menu, savecookie = True, cookiefile = i)
				m3u8_master = m3u8.parse(m3u8_master_data)
				sbitrate = int(addon.getSetting('quality')) * 1024
				for video_index in m3u8_master.get('playlists'):
					bitrate = int(video_index.get('stream_info')['bandwidth'])
					if qbitrate is None:
						if bitrate < lbitrate or lbitrate == -1:
							lbitrate = bitrate
							lm3u8_url = video_index.get('uri')
						if bitrate > hbitrate and bitrate <= sbitrate:
							hbitrate = bitrate
							m3u8_url = video_index.get('uri')
					elif (qbitrate * (100 - BITRATERANGE)) / 100 < bitrate and (qbitrate * (100 + BITRATERANGE)) / 100 > bitrate:
						m3u8_url = video_index.get('uri')
				if 	((m3u8_url is None) and (qbitrate is None)):
					m3u8_url = lm3u8_url
				m3u8_data = connection.getURL(m3u8_url, loadcookie = True, cookiefile = i)
				key_url = re.compile('URI="(.*?)"').findall(m3u8_data)[0]
				key_data = connection.getURL(key_url, loadcookie = True, cookiefile = i)
				key_file = open(ustvpaths.KEYFILE % str(i), 'wb')
				key_file.write(key_data)
				key_file.close()
				video_url = re.compile('(http:.*?)\n').findall(m3u8_data)
				for video_item in video_url:
					newurl = base64.b64encode(video_item)
					newurl = urllib.quote_plus(newurl)
					m3u8_data = m3u8_data.replace(video_item, 'http://127.0.0.1:12345/' + str(i) + '/foxstation/' + newurl)
				m3u8_data = m3u8_data.replace(key_url, 'http://127.0.0.1:12345/play%s.key' % str(i))
				file_name = ustvpaths.PLAYFILE.replace('.m3u8', str(i) + '.m3u8')
				playfile = open(file_name, 'w')
				playfile.write(m3u8_data)
				playfile.close()
			else:
				print "********************* No sel*****************"
				file_name = video_menu
				player._localHTTPServer = False
			queue.put([i, file_name, duration, closedcaption])
		except:
			pass	

def list_qualities(BASE, video_url = common.args.url, media_base = VIDEOURL):
	bitrates = []
	if media_base not in video_url:
		video_url = media_base + video_url
	exception = False
	if 'feed' not in video_url:
		swf_url = connection.getRedirect(video_url, header = {'Referer' : BASE})
		params = dict(item.split("=") for item in swf_url.split('?')[1].split("&"))
		uri = urllib.unquote_plus(params['uri'])
		config_url = urllib.unquote_plus(params['CONFIG_URL'].replace('Other', DEVICE))
		config_data = connection.getURL(config_url, header = {'Referer' : video_url, 'X-Forwarded-For' : '12.13.14.15'})
		config_tree = BeautifulSoup(config_data, 'html.parser')
		if not config_tree.error:
			feed_url = config_tree.feed.string
			feed_url = feed_url.replace('{uri}', uri).replace('&amp;', '&').replace('{device}', DEVICE).replace('{ref}', 'None').replace('{type}', 'normal').strip()
		else:
			exception = True
			error_text = config_tree.error.string.split('/')[-1].split('_') 
			common.show_exception(error_text[1], error_text[2])
	else:
		feed_url = video_url
	if not exception:
		feed_data = connection.getURL(feed_url)
		video_tree = BeautifulSoup(feed_data, 'html.parser', parse_only = SoupStrainer('media:group'))
		video_segments = video_tree.find_all('media:content')
		video_segment = video_segments[0]
		video_url3 = video_segment['url'].replace('{device}', DEVICE)
		video_data3 = connection.getURL(video_url3, header = {'X-Forwarded-For' : '12.13.14.15'})
		video_tree3 = BeautifulSoup(video_data3, 'html.parser')
		video_menu = video_tree3.find('src').string
		m3u8_url = None
		m3u_master_data = connection.getURL(video_menu, savecookie = True)
		m3u_master = m3u8.parse(m3u_master_data)
		for video_index in m3u_master.get('playlists'):
			bitrate = int(video_index.get('stream_info')['bandwidth'])
			display = int(bitrate) / 1024
			bitrates.append((display, bitrate))
		return bitrates

def list_qualities2(API, video_url = common.args.url):
	video_bitrates = []
	video_data = connection.getURL(API + 'playlists/%s/videos.json' % video_url)
	video_tree = simplejson.loads(video_data)
	video_mgid = video_tree['playlist']['videos'][0]['video']['mgid']
	video_data2 = connection.getURL(VIDEOURLAPI % video_mgid)
	video_tree2 = BeautifulSoup(video_data2, 'html.parser')
	video_url2 = video_tree2.findAll('rendition')
	for video_index in video_url2:
		video_bitrate = int(video_index['bitrate'])
		video_bitrates.append((video_bitrate, video_bitrate))
	return video_bitrates

def convert_subtitles(closedcaption):
	str_output = ''
	count = 0
	for closedcaption_url, i in closedcaption:
		count = int(i) + 1
		if closedcaption_url is not None:
			try:
				cc_content = common.smart_unicode(connection.getURL(closedcaption_url, connectiontype = 0).replace(' 9137', ''))
				reader = detect_format(cc_content)
				if reader:
				
					str_output = common.smart_utf8(SRTWriter().write(reader().read(cc_content)))
					file = open(os.path.join(ustvpaths.DATAPATH, 'subtitle-%s.srt' % str(count)), 'w')
					file.write(str_output)
					str_output=''
					file.close()
				else:
					print "Unknown sub type"
			except  Exception, e:
				print "Exception with Subs: ", e
