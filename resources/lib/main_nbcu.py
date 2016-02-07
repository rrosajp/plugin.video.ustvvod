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
import time
import urllib
import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin
from bs4 import BeautifulSoup, SoupStrainer

addon = xbmcaddon.Addon()
player = common.XBMCPlayer()
pluginHandle = int(sys.argv[1])

CATERGORIES = ['Series', 'Shows']

 
def masterlist(SITE, SHOWS):
	master_db = []
	master_data = connection.getURL(SHOWS)
	master_menu = simplejson.loads(master_data)['entries']
	dupes = {}
	for master_item in master_menu:
		master_name = master_item['title']
		master_url = master_item['plcategory$fullTitle']
		master_order = master_item['plcategory$order']
		if len(master_url.split('/')) == 2 and master_url.split('/')[0] in CATERGORIES:
			key = master_name.replace(' ', '').replace('?', '')
			if key in dupes:
				dupe_order, dupe_url, dupe_name = dupes[key]
				if dupe_order > master_order:
					dupes[key] = (master_order, master_url, master_name)
			else:
				dupes[key] = (master_order, master_url, master_name)
	for master_order, master_url, master_name in dupes.itervalues():
		master_db.append((master_name, SITE, 'seasons', master_url))
	return master_db

def seasons(SITE, FULLEPISODES, CLIPS, FULLEPISODESWEB = None, season_urls = common.args.url):

	seasons = []
	for season_url in season_urls.split(','):
		season_data = connection.getURL(FULLEPISODES % urllib.quote_plus(season_url) + '&range=0-1')
		try:
			season_menu = int(simplejson.loads(season_data)['totalResults'])
		except:
			season_menu = 0
		if season_menu > 0:
			season_url2 = FULLEPISODES % urllib.quote_plus(season_url) + '&range=0-' + str(season_menu)
			seasons.append(('Full Episodes',  SITE, 'episodes', season_url2, -1, -1))
		if FULLEPISODESWEB:
			try:
				show = season_url.split('/')[-1].replace(' ', '')
				web_data = connection.getURL(FULLEPISODESWEB % show)
				try:
					web_tree = BeautifulSoup(web_data, 'html.parser')
				except:
					web_tree = BeautifulSoup(web_data, 'html5lib')
				all = len(web_tree.find_all('div', class_ = 'view-mode-vid_teaser_show_episode'))
				auth = len(web_tree.find_all('div', class_ = 'tve-video-auth'))
				if all > auth:
					seasons.append(('Full Episodes',  SITE, 'episodes_web', FULLEPISODESWEB % show, -1, -1))
				else:
					try:
						print "eps block"
						eps = web_tree.find( class_ = 'view-syfy-show-episodes').find_all(text= re.compile('Full Episode'))
						headers = []
						for ep in eps:
							heading = ep.parent.parent.parent.parent.parent.findPrevious('h3').div.string.strip()
							if heading not in headers:
								headers.append(heading)
						for web_item in headers:
							seasons.append(('Season ' +web_item,  SITE, 'episodes_web', FULLEPISODESWEB % show + '/' + web_item, -1, -1))
					except:
						title = web_tree.find( class_ = 'pane-full-episodes-pane-episodes-by-show').h2.string
						seasons.append((title,  SITE, 'episodes_web', FULLEPISODESWEB % show, -1, -1))
			except Exception as e:
				print "Exception with web processing", e
		season_data2 = connection.getURL(CLIPS % urllib.quote_plus(season_url) + '&range=0-1')
		try:
			season_menu2 = int(simplejson.loads(season_data2)['totalResults'])
		except:
			season_menu2 = 0
		if season_menu2 > 0:
			season_url3 = CLIPS % urllib.quote_plus(season_url) + '&range=0-' + str(season_menu2)
			if ',' in season_urls:
				seasons.append(('Clips %s'%season_url,  SITE, 'episodes', season_url3, -1, -1))
			else:
				seasons.append(('Clips',  SITE, 'episodes', season_url3, -1, -1))
	return seasons

def episodes(SITE, episode_url = common.args.url, quailty = True):
	episodes = []
	episode_data = connection.getURL(episode_url)
	episode_menu = simplejson.loads(episode_data)['entries']
	for i, episode_item in enumerate(episode_menu):
		default_mediacontent = None
		for mediacontent in episode_item['media$content']:
			if (mediacontent['plfile$isDefault'] == True) and (mediacontent['plfile$format'] == 'MPEG4'):
				default_mediacontent = mediacontent
			elif (mediacontent['plfile$format'] == 'MPEG4'):
				mpeg4_mediacontent = mediacontent
		if default_mediacontent is None:
			default_mediacontent = mpeg4_mediacontent
		url = default_mediacontent['plfile$url']
		episode_duration = int(episode_item['media$content'][0]['plfile$duration'])
		episode_plot = episode_item['description']
		episode_airdate = common.format_date(epoch = episode_item['pubDate']/1000)
		episode_name = episode_item['title']
		try:
			season_number = int(episode_item['pl' + str(i + 1) + '$season'][0])
		except:
			try:
				season_number = int(episode_item['nbcu$seasonNumber'])
			except:
				season_number = -1
		try:
			episode_number = int(episode_item['pl' + str(i + 1) + '$episode'][0])
		except:
			try:
				episode_number = int(episode_item['nbcu$episodeNumber'])
			except:
				episode_number = -1
		try:
			episode_thumb = episode_item['plmedia$defaultThumbnailUrl']
		except:
			episode_thumb = None
		try:
			if episode_item['pl1$fullEpisode'] == True:
				episode_type = 'Full Episode'
			else:
				episode_type = 'Clip'
		except:
			episode_type = 'Clip'
		try:
			episode_cast = episode_item['pl1$people']
		except:
			episode_cast = []
		try:
			show_name = episode_item['pl1$shows']
		except:
			try:
				show_name = episode_item['media$categories'][1]['media$name'].split('/')[1]
			except:
				show_name = simplejson.loads(episode_data)['title']
		u = sys.argv[0]
		u += '?url="' + urllib.quote_plus(url) + '"'
		u += '&mode="' + SITE + '"'
		u += '&sitemode="play_video"'
		infoLabels={	'title' : episode_name,
						'durationinseconds' : episode_duration,
						'season' : season_number,
						'episode' : episode_number,
						'plot' : episode_plot,
						'premiered' : episode_airdate,
						'cast' : episode_cast,
						'TVShowTitle' : show_name}
		if quailty == True:
			quality_mode  = 'list_qualities'
		else:
			quality_mode = None
		episodes.append((u, episode_name, episode_thumb, infoLabels, quality_mode, False, episode_type))
	return episodes
#	display = int(bitrate) / 1024
	
def list_qualities(M3UURL = None):
	exception = False
	video_url = common.args.url
	video_data = connection.getURL(video_url)
	if 'link.theplatform.com' not in video_url:
		video_tree =  BeautifulSoup(video_data, 'html.parser')
		try:
			player_url = 'http:' + video_tree.find('div', class_ = 'video-player-wrapper').iframe['src']
		except:
			player_url = 'http:' + video_tree.find('div', id = 'pdk-player')['data-src']
		player_data = connection.getURL(player_url)
		player_tree = BeautifulSoup(player_data, 'html.parser')
		video_url = player_tree.find('link', type = "application/smil+xml")['href']
		video_url = video_url + '&format=SCRIPT'
		
		script_data = connection.getURL(video_url)
		script_menu = simplejson.loads(script_data)
		if script_menu['pl1$entitlement'] != 'auth':
			bitrates,exception = smil_bitrates(video_url)
		else:
			captions = script_menu['captions'][0]['src']
			id = re.compile('([0-9]+.[0-9]+.*).tt').findall(captions)[0]
			td = (datetime.datetime.utcnow()- datetime.datetime(1970,1,1))
			unow = int((td.microseconds + (td.seconds + td.days * 24 * 3600) * 10**6) / 10**6)
			master_url = M3UURL % (id, str(unow), str(unow+60))
			bitrates = m3u_bitrates(master_url)
			return bitrates
			#need to set captions on player
	else:
		bitrates,exception = smil_bitrates(video_url)
	if  not exception:
		return bitrates
	else:
		common.show_exception(video_tree.ref['title'], video_tree.ref['abstract'])

		

def play_video(SWFURL, M3UURL = None, BASE = None):
	key_url = None
	try:
		qbitrate = common.args.quality
	except:
		qbitrate = None
	exception = False
	video_url = common.args.url
	hbitrate = -1
	lbitrate = -1
	sbitrate = int(addon.getSetting('quality')) * 1024
	closedcaption = None
	video_data = connection.getURL(video_url)
	if 'link.theplatform.com' not in video_url:
		video_tree =  BeautifulSoup(video_data, 'html.parser')
		print "Getting plauer url"
		try:
			player_url = 'http:' + video_tree.find('div', class_ = 'video-player-wrapper').iframe['src']
		except:

			player_url = 'http:' + video_tree.find('div', class_='pdk-player')['data-src']
		print player_url
		player_data = connection.getURL(player_url)
		player_tree =  BeautifulSoup(player_data, 'html.parser')
		video_url = player_tree.find('link', type = "application/smil+xml")['href']
		video_url = video_url + '&format=SCRIPT'
		
		script_data = connection.getURL(video_url)
		script_menu = simplejson.loads(script_data)
		if script_menu['pl1$entitlement'] != 'auth':
			finalurl,exception = process_smil(video_url)
		else:
			captions = script_menu['captions'][0]['src']

			id = re.compile('([0-9]+.[0-9]+.*).tt').findall(captions)[0]

			td = (datetime.datetime.utcnow()- datetime.datetime(1970,1,1))
			unow = int((td.microseconds + (td.seconds + td.days * 24 * 3600) * 10**6) / 10**6)
			master_url = M3UURL % (id, str(unow), str(unow+60))
			finalurl = process_m3u(master_url, qbitrate)
	else:
		finalurl, exception = process_smil(video_url)
	if  not exception:
		item = xbmcgui.ListItem(path = finalurl)

		try:
			item.setThumbnailImage(common.args.thumb)
		except:
			pass
		try:
			item.setInfo('Video', {	'title' : common.args.name,
							'season' : common.args.season_number,
							'episode' : common.args.episode_number,
							'TVShowTitle' : common.args.show_title})
		except:
			pass
		xbmcplugin.setResolvedUrl(pluginHandle, True, item)
		while player.is_active:
			player.sleep(250)
	else:
		common.show_exception(video_tree.ref['title'], video_tree.ref['abstract'])


def process_smil(video_url, qbitrate = None):
	closedcaption = None
	video_data = connection.getURL(video_url)
	video_tree = BeautifulSoup(video_data, 'html.parser')
	video_rtmp = video_tree.meta
	playpath_url = None
	lplaypath_url = None
	try:
		base_url = video_rtmp['base']
	except:
		base_url = None
	if base_url is not None:
		if qbitrate is None:
			video_url2 = video_tree.switch.find_all('video')
			for video_index in video_url2:
				bitrate = int(video_index['system-bitrate'])
				if bitrate < lbitrate or lbitrate == -1:
					lbitrate = bitrate
					lplaypath_url = video_index['src']	
				if bitrate > hbitrate and bitrate <= sbitrate:
					hbitrate = bitrate
					playpath_url = video_index['src']	
			if playpath_url is None:
				playpath_url = lplaypath_url
		else:
			playpath_url = video_tree.switch.find('video', attrs = {'system-bitrate' : qbitrate})['src']
		if '.mp4' in playpath_url:
			playpath_url = 'mp4:'+ playpath_url
		else:
			playpath_url = playpath_url.replace('.flv','')
		finalurl = base_url +' playpath=' + playpath_url + ' swfurl=' + SWFURL + ' swfvfy=true'
		player._localHTTPServer = False
	else:
		video_data = connection.getURL(video_url + '&manifest=m3u&Tracking=true&Embedded=true&formats=F4M,MPEG4')
		video_tree = BeautifulSoup(video_data, 'html.parser')
		try:
			closedcaption = video_tree.textstream['src']
			player._subtitles_Enabled = True
		except:
			pass
		if (addon.getSetting('enablesubtitles') == 'true') and (closedcaption is not None):
				convert_subtitles(closedcaption)
		if  video_tree.find('param', attrs = {'name' : 'isException', 'value' : 'true'}) is None:
			video_url2 = video_tree.body.seq.video
			video_url3 = video_url2['src']
			finalurl = process_m3u(video_url3, qbitrate)
			return finalurl, False

		else:
			exception = True
	return finalurl, exception
	

def smil_bitrates(video_url):
	bitrates = []
	video_data = connection.getURL(video_url)
	video_tree = BeautifulSoup(video_data, 'html.parser')
	video_rtmp = video_tree.meta
	playpath_url = None
	lplaypath_url = None
	try:
		base_url = video_rtmp['base']
	except:
		base_url = None
	if base_url is not None:
			video_url2 = video_tree.switch.find_all('video')
			for video_index in video_url2:
				bitrate = int(video_index['system-bitrate'])
				bitrates.append((int(bitrate) / 1024, bitrate))
	else:
		video_data = connection.getURL(video_url + '&manifest=m3u&Tracking=true&Embedded=true&formats=F4M,MPEG4')
		video_tree = BeautifulSoup(video_data, 'html.parser')
		if  video_tree.find('param', attrs = {'name' : 'isException', 'value' : 'true'}) is None:
			video_url2 = video_tree.body.seq.video
			video_url3 = video_url2['src']
			bitrates = m3u_bitrates(video3_url)
		else:
			exception = True
	return bitrates, exception

def m3u_bitrates(m3u_url):
	bitrates = []
	video_data2 = connection.getURL(m3u_url, savecookie = True)
	video_url5 = m3u8.parse(video_data2)
	for video_index in video_url5.get('playlists'):
		bitrate = int(video_index.get('stream_info')['bandwidth'])
		bitrates.append((int(bitrate) / 1024, bitrate))
	return bitrates

def process_m3u(m3u_url, qbitrate = None):
	key_url = None
	sbitrate = int(addon.getSetting('quality')) * 1024
	lbitrate = -1
	hbitrate = -1
	video_data2 = connection.getURL(m3u_url, savecookie = True)
	video_url5 = m3u8.parse(video_data2)
	for video_index in video_url5.get('playlists'):
		bitrate = int(video_index.get('stream_info')['bandwidth'])
		try:
			codecs =  video_index.get('stream_info')['codecs']
		except:
			codecs = ''
		if qbitrate is None:
			if (bitrate < lbitrate or lbitrate == -1):
				lbitrate = bitrate
				lplaypath_url =  video_index.get('uri')
			if (bitrate > hbitrate and bitrate <= sbitrate):
				hbitrate = bitrate
				playpath_url = video_index.get('uri')
		elif  bitrate == qbitrate:
			playpath_url =  video_index.get('uri')
	if playpath_url is None:
		playpath_url = lplaypath_url
	if not common.use_proxy() and int(addon.getSetting('connectiontype')) == 0:
		player._localHTTPServer = False
		return playpath_url
	else:
		m3u_data = connection.getURL(playpath_url, loadcookie = True)
		try:
			key_url = re.compile('URI="(.*?)"').findall(m3u_data)[0]
			
			key_data = connection.getURL(key_url, loadcookie = True)		
			key_file = open(ustvpaths.KEYFILE % '0', 'wb')
			key_file.write(key_data)
			key_file.close()
		except:
			pass
		video_url5 = re.compile('(http:.*?)\n').findall(m3u_data)
		if int(addon.getSetting('connectiontype')) > 0:
			proxy_config = common.proxyConfig()
			for i, video_item in enumerate(video_url5):
				newurl = base64.b64encode(video_item)
				newurl = urllib.quote_plus(newurl)
				m3u_data = m3u_data.replace(video_item, 'http://127.0.0.1:12345/proxy/' + newurl + '/' + proxy_config)
		filestring = 'XBMC.RunScript(' + os.path.join(ustvpaths.LIBPATH,'proxy.py') + ', 12345)'
		xbmc.executebuiltin(filestring)
		time.sleep(20)
		if key_url is not None:
			m3u_data = m3u_data.replace(key_url, 'http://127.0.0.1:12345/play0.key')
		playfile = open(ustvpaths.PLAYFILE, 'w')
		playfile.write(m3u_data)
		playfile.close()
		return ustvpaths.PLAYFILE
				
def clean_subs(data):
	br = re.compile(r'<br.*?>')
	tag = re.compile(r'<.*?>')
	space = re.compile(r'\s\s\s+')
	apos = re.compile(r'&amp;apos;')
	sub = br.sub('\n', data)
	sub = tag.sub(' ', sub)
	sub = space.sub(' ', sub)
	sub = apos.sub('\'', sub)
	return sub

def convert_subtitles(closedcaption):
	str_output = ''
	subtitle_data = connection.getURL(closedcaption, connectiontype = 0)
	subtitle_data = BeautifulSoup(subtitle_data, 'html.parser', parse_only = SoupStrainer('div'))
	lines = subtitle_data.find_all('p')
	for i, line in enumerate(lines):
		if line is not None:
			sub = clean_subs(common.smart_utf8(line))
			start_time_rest, start_time_msec = line['begin'].rsplit(':',1)
			start_time = common.smart_utf8(start_time_rest + ',' + start_time_msec)
			try:
				end_time_rest, end_time_msec = line['end'].rsplit(':',1)
				end_time = common.smart_utf8(end_time_rest + ',' + end_time_msec)
			except:
				continue
			str_output += str(i + 1) + '\n' + start_time + ' --> ' + end_time + '\n' + sub + '\n\n'
	file = open(ustvpaths.SUBTITLE, 'w')
	file.write(str_output)
	file.close()
