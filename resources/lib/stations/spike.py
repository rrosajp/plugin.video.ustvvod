#!/usr/bin/python
# -*- coding: utf-8 -*-
import common
import connection
import main_viacom
import re
import simplejson
import sys
import urllib
import xbmcgui
import xbmcplugin
import json
from bs4 import BeautifulSoup

pluginHandle = int(sys.argv[1])


SITE = "spike"
NAME = "Spike TV"
DESCRIPTION = "Spike TV knows what guys like. The brand speaks to the bold, adventuresome side of men with action-packed entertainment, including a mix of comedy, blockbuster movies, sports, innovative originals and live events. Popular shows like The Ultimate Fighter, TNA iMPACT!, Video Game Awards, DEA, MANswers, MXC, and CSI: Crime Scene Investigation, plus the Star Wars and James Bond movie franchises, position Spike TV as the leader in entertainment for men."
BASE = "http://www.spike.com"
SHOWS = "http://www.spike.com/shows/"

PN_API = "http://www.powernationtv.com/api/"
PN_URL = "http%3A%2F%2Fapi.brightcove.com%2Fservices%2Flibrary%3Fmedia_delivery%3Dhttp%26command%3Dfind_video_by_reference_id%26token%3Doad4MXnw--kXX1LAE3O3tFREdftYEX3LProaX0OseIo6j2zfqp9SZA..%26video_fields%3DaccountId%2Cname%2CshortDescription%2CreferenceId%2Cid%2CcustomFields%2CvideoFullLength%2CHLSURL%2CvideoStillURL%2CcuePoints%2Crenditions%2Clength%26api%3Dpowernation%26reference_id%3D"

def masterlist():
	master_dict = {}
	master_db = []
	master_data = connection.getURL(SHOWS)
	master_tree = BeautifulSoup(master_data, 'html5lib')
	master_section = master_tree.find_all('div', class_ = 'primetime_and_originals')
	for section in master_section:
		master_menu = section.find_all('a', text = True)
		for master_item in master_menu:
			master_name = master_item.text
			tvdb_name = common.get_show_data(master_name,SITE, 'seasons')[-1]
			season_url = BASE + master_item['href']
			if tvdb_name not in master_dict.keys():
				master_dict[tvdb_name] = season_url
			else:
				master_dict[tvdb_name] = master_dict[tvdb_name] + ',' + season_url
	for master_name, season_url in master_dict.iteritems():	
		master_db.append((master_name, SITE, 'seasons', season_url))
	return master_db

def _get_manifest(page_url):
	""" Try to get the manifest Javascript object for the current page. Input URL can be any kind of page
	    Returns the manifest feed as a JSON object if found, else return False """
	triforceManifestFeed = None
	page_data = connection.getURL(page_url)
	page_tree = BeautifulSoup(page_data, 'html.parser')
	scripts = page_tree.find_all('script')
	try:
		for script in scripts:
			if ('triforceManifestFeed') in script.string:
				triforceManifestFeed = script.string.split(' = ')[1]
				triforceManifestFeed = triforceManifestFeed.strip()[:-1]
				triforceManifestFeed = triforceManifestFeed.split(';')[0]
				triforceManifestFeed = simplejson.loads(triforceManifestFeed)
				return triforceManifestFeed
	except:
		return False

def _get_manifest_feed(feed_url):
	""" Load a single manifest feed as a JSON object. Input should already be a feed URL 
	    #ManifestFeed can be added to the end of the URL to aid detection of a URL as amanifest
	    feed, as opposed to a full page URL. #ManifestFeed is removed before calling the URL """
	try:
		if feed_url.endswith('#ManifestFeed'):
			feed_url = feed_url[:-13] # strip #ManifestFeed from URL
		page_data = connection.getURL(feed_url)
		return simplejson.loads(page_data)
	except:
		return False

def add_items_from_manifestfile(triforceManifestFeed, season_url, multiSeason = False):
	""" Add container items based on the manifest feed. If there are no items in the feed
	    skip it. Special rule not to add Daily Show items to Colbert Report and vice versa """
	seasons = []
	try:
		feeds = []
		for zone in triforceManifestFeed['manifest']['zones']:
			thiszone = triforceManifestFeed['manifest']['zones'][zone]
			feed_data = connection.getURL(thiszone['feed'])
			feed = simplejson.loads(feed_data)
			try:
				promoType = feed['result']['promo']['promoType']
			except:
				promoType = None
			if _keyinfeed(['videos','playlist','playlists','episode', 'items', 'filters'], feed['result'].keys()) and promoType != 'all_full_episodes':
				if 'episodes' in feed['result']:
					if len(feed['result']['episodes']) == 0:
						continue
				if 'episode' in feed['result']:
					if 'episodeType' not in feed['result']['episode'].keys():
						continue
				elif 'videos' in feed['result']:
					if len(feed['result']['videos']) == 0:
						continue
				elif 'playlist' in feed['result']:
					if len(feed['result']['playlist']) == 0:
						continue
				elif 'playlists' in feed['result']:
					if len(feed['result']['playlists'][0]) == 0:
						continue
				title = ''
				if multiSeason:
					try:
						prefix = feed['result']['episode']['show']['title'] + ' '
					except:
						prefix = feed['result']['items'][0]['show']['title'] + ' '
				else:
					prefix = ''
				try:
					filters = feed['result']['filters']
					has_fulleps = False
					for filter in filters:
						if 'Full Episodes' in filter['name'] and filter['count'] > 0:
							has_fulleps = True
						if 'Episodes' not in filter['name'] and has_fulleps:
							seasonUrl = filter['url'] 
							seasons.append((prefix + filter['name'],  SITE, 'episodes', seasonUrl + "&fullEpisodes=1#ManifestFeed", -1, -1))
					for filter in filters:
						if 'Episodes' not in filter['name']:
							seasonUrl = filter['url'] 
							seasons.append((prefix + 'Clips ' + filter['name'],  SITE, 'episodes', seasonUrl + "&fullEpisodes=0#ManifestFeed", -1, -1))
				except:
					title = feed['result']['episode']['episodeType']
					title = re.sub(r"(\w)([A-Z])", r"\1 \2", title).title()
					seasons.append((title,  SITE, 'episodes', thiszone['feed'] + "?&fullEpisodes=1#ManifestFeed", -1, -1))
	except Exception, e:
		pass
	return seasons

def _keyinfeed(keys1, keys2):
	""" Helper function to find if a key from an list is present in another list """
	for key in keys1:
		if key in keys2:
			return True
	return False
		
def seasons(show_url = common.args.url):
	""" Load the items for a show. This can be "Full Epiodes" and "Clips", or something based
	    on the data.
	    Southpark has a different site structure, so this is redirected to a different function.
	    Some pages have a manifest Javascript object that contains JSON feeds to all episodes.
	    Other pages do not have this. This function tries to find if the show home page has such
	    a feed. If so, only data from the feed is used. If the home page does not have the feed,
	    try to find the URL for the full episodes and the clips pages. For each of these pages
	    the script tries to load the manifest feed. If this cannot be found, add items based on
	    the HTML page. A consequence of this is that some shows can have mixed results: full
	    episides pages does not have a manifest, but clips does. This can lead to duplication of
	    container items. Many shows seem to contain a feed for full episodes, but this feed is empty """

	# Powernation has a separate API, so lets redirect to the appropriate function
	if 'powernation' in show_url:
		return seasons_powernation()

	seasons = []
	if ',' in show_url:
		multiSeason = True
	else:
		multiSeason = False
	for show_url in show_url.split(','):
		season_data = connection.getURL(show_url)
		season_tree = BeautifulSoup(season_data, 'html5lib') #Bad parser
		
		try:
			season_item = season_tree.find('a', href = re.compile('episode.{3,}'))['href']
			if BASE not in season_item:
				season_item = BASE + season_item 
			triforceManifestFeed = _get_manifest(season_item)
		except:
			triforceManifestFeed = None
		if triforceManifestFeed:
			seasons.extend(add_items_from_manifestfile(triforceManifestFeed, season_item, multiSeason))
		else:
			season_item = season_tree.find('div', class_=re.compile('(menu)|(grid)')).find('a', href = re.compile('video-'))
			if season_item is not None:
				season_name2 = season_item.text
				if BASE not in season_item['href']:
					season_url3 = BASE + season_item['href']
				else:
					season_url3 = season_item['href']
				if not multiSeason:
					seasons.append((season_name2.title(), SITE, 'episodes', season_url3, -1, -1))
				else:
					title = season_tree.find('title').string.split('|')[0].strip().title()
					seasons.append((title + ' ' + season_name2, SITE, 'episodes', season_url3, -1, -1))
	return seasons

def seasons_powernation():
	shows = []
	master_data = connection.getURL(PN_API + "shows/all")
	show_json = json.loads(master_data)
	for show in show_json['shows']:
		show_name = show['title']
		show_id = show['episode_prefix']
		shows.append((show_name, SITE, 'episodes', PN_API + "episodes/all/show/" + show_id + "/per_page/75", -1, -1))
	
	return shows

def episodes_from_html(episode_url = common.args.url):
	episode_data = connection.getURL(episode_url)
	episode_tree = BeautifulSoup(episode_data, 'html5lib')
	episodes = add_clips(episode_tree)
	return episodes
	
def add_video_from_manifestfile(manifest_feed, full_episodes = False):
	""" Add videos based on a manifest feed """
	try:
		episodes = []
		shows = []
		items = manifest_feed['result']
		if 'videos' in items:
			items = items['videos']
		elif 'playlist' in items:
			items = items['playlist']['videos']
		elif 'episode' in items:
			items = [items['episode']]
		elif 'playlists' in items:
			t_items = []
			k = 0
			for i in items['playlists']:
				l = 0
				for j in items['playlists'][k]['videos']:
					t_items.append(items['playlists'][k]['videos'][l])
					l = l + 1
				k = k + 1
			items = t_items
		elif 'items' in items:
			items = items['items']
		for item in items:
			try:
				episode_type = item['episodeType']
				if episode_type == 'fullEpisode':
					episode_type = 'Full Episode'
				else:
					episode_type = 'Clip'
			except:
				episode_type = 'Clip'
			if item['distPolicy']['authTve'] == False:
				if (full_episodes == True  and episode_type == 'Full Episode') or (full_episodes == False  and episode_type != 'Full Episode'):
					try:
						episode_name = item['title']
					except:
						episode_name = item['shortTitle']
					try:
						epoch = float(item['airDate'])
						epoch = common.convert_to_timezone(epoch, '', -5, epoch)  
						
						episode_airdate = common.format_date(epoch , '', '%d.%m.%Y', epoch)
					except:
						episode_airdate = -1
					episode_plot = item['shortDescription']
					episode_thumb = item['images'][0]['url']
					try:
						episode_duration = item['duration']
					except:
						episode_duration = -1
					url = item['url']
					if not url:
						url = item['canonicalURL']
					try:
						season_number = item['season']['seasonNumber']
						episode_number = str(int(str(item['season']['episodeNumber'])[len(str(season_number)):]))
					except:
						season_number = -1
						episode_number = -1
					try:
						show_name = item['show']['title']
					except:
						show_name = ''
					episode_expires = item['distPolicy']['endDate']
					try:
						episode_mpaa = RATINGS[item['contentRating']]
					except:
						episode_mpaa = None
					u = sys.argv[0]
					u += '?url="' + urllib.quote_plus(url) + '"'
					u += '&mode="' + SITE + '"'
					u += '&sitemode="play_video"'
					infoLabels={	'title' : episode_name,
									'season' : season_number,
									'episode' : episode_number,
									'plot' : episode_plot,
									'premiered' : episode_airdate,
									'durationinseconds' : episode_duration,
									'TVShowTitle' : show_name,
									'mpaa' : episode_mpaa
									}
					try:
						infoLabels = common.enrich_infolabels(infoLabels, epoch = episode_expires)
					except Exception as e:
						print "Can't enrich", e
					episodes.append((u, episode_name, episode_thumb, infoLabels, 'list_qualities', False, episode_type))
		return episodes
	except Exception,e:
		print "Exception: ", e
		
def episodes(episode_url = common.args.url):
	""" Add individual episodes. If the URL is a manifest feed, load from JSON, else analyse
	    the HTML of the page """

	# Redirect to powernation episode function
	if 'powernation' in episode_url:
		return episodes_powernation(episode_url)

	if 'fullEpisodes=1' in episode_url:
		fullEps = True
		surfix = 'fullEpisodes=1'
	else:
		fullEps = False
		surfix = ''
	if episode_url.endswith('#ManifestFeed'):
		triforceManifestFeed = _get_manifest_feed(episode_url)
		if triforceManifestFeed:
			allepisodes = add_video_from_manifestfile(triforceManifestFeed, fullEps)
			try:
				if triforceManifestFeed['result']['nextPageURL']:
					allepisodes.extend(episodes(triforceManifestFeed['result']['nextPageURL'] + surfix + '#ManifestFeed'))
			except:
				pass
	else:
		allepisodes = episodes_from_html(episode_url)
	return allepisodes

def episodes_powernation(episode_url):
	episodes = []
	episodes_data = connection.getURL(episode_url)
	episodes_json = json.loads(episodes_data)
	for episode_item in episodes_json['episodes']:
		episode_name = episode_item['description']['title']
		episode_plot = episode_item['description']['description_long']
		episode_thumb = episode_item['description']['image_url']
		episode_id = episode_item['description']['episode_id']

		
		season_num, episode_num = episode_id.split('-')

		u = sys.argv[0]
		u += '?url="' + PN_URL + episode_id + '"'
		u += '&mode="' + SITE + '"'
		u += '&sitemode="play_video"'
		infoLabels={	'title' : episode_name,
						'plot' : episode_plot, 
						'TVShowTitle' : episode_item['description']['show_name'],
						'season' : episode_item['description']['season'],
						'episode' : episode_num}

		episodes.append((u, episode_name, episode_thumb, infoLabels, None, False, None))
	return episodes

def add_clips(episode_tree):
	episodes = []
	try:
		try:
			episode_menu = episode_tree.find(class_ ='clips').find_all(class_= 'clip')
		except:
			episode_menu = episode_tree.find_all(class_ = 'block')
		for episode_item in episode_menu:
			try:
				episode_name = common.replace_signs(episode_item.find('a', class_ = 'title').text)
			except:
				episode_name = common.replace_signs(episode_item.find('h3').a.text)
			episode_plot = common.replace_signs(episode_item.find('p', class_ = False).text)
			episode_thumb = episode_item.find('img')['src'].split('?')[0]
			try:
				url = episode_item.find('a', class_ = 'title')['href']
			except:
				url = episode_item.find('div', class_ = 'thumb_area').a['href']
			try:
				try:
					episode_airdate = episode_item.find('div', class_ ='info').contents[-1].split(' ', 1)[1].strip()
				except:
					episode_airdate = episode_item.find('div', class_ = 'details').find('small', text = re.compile('Posted')).text.split(' ', 1)[1].strip()
				episode_airdate = common.format_date(episode_airdate, '%B %d, %Y', '%d.%m.%Y')
			except:
				episode_airdate = -1
			try:
				episode_duration = re.compile('\((.*)\)').findall(episode_name)[0]
				episode_name = re.compile('(.*)\s\(.*\)').findall(episode_name)[0]
				episode_duration = common.format_seconds(episode_duration)
			except:
				try:
					episode_duration = common.format_seconds(episode_item.find('h3').small.text.replace(')', '').replace('(', ''))
				except:
					episode_duration = -1
			u = sys.argv[0]
			u += '?url="' + urllib.quote_plus(url) + '"'
			u += '&mode="' + SITE + '"'
			u += '&sitemode="play_video"'
			infoLabels = {	'title' : episode_name,
							'durationinseconds' : episode_duration,
							'plot' : episode_plot,
							'premiered' : episode_airdate }
			episodes.append((u, episode_name, episode_thumb, infoLabels, None, False, 'Clip'))
	except Exception, e:
		pass
	return episodes

def play_video(video_uri = common.args.url):
	# Handle the poewrnation specific video loading
	if 'powernation' in video_uri:
		video_data = connection.getURL(video_uri)
		video_json = json.loads(video_data)
		video_url = video_json['HLSURL']
		
		item = xbmcgui.ListItem(path = video_url)
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
	else:
		video_data = connection.getURL(video_uri)
		video_url = BeautifulSoup(video_data, 'html5lib').find('div', class_ = 'video_player')['data-mgid']
		main_viacom.play_video(BASE, video_url)	

def list_qualities(video_url = common.args.url):
	video_data = connection.getURL(video_url)
	video_url = BeautifulSoup(video_data, 'html5lib').find('div', class_ = 'video_player')['data-mgid']
	return main_viacom.list_qualities(BASE, video_url)
