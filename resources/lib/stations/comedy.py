#!/usr/bin/python
# -*- coding: utf-8 -*-
import common
import connection
import main_viacom
import re
import simplejson
import sys
import urllib
import xbmcaddon
from bs4 import BeautifulSoup, SoupStrainer

addon = xbmcaddon.Addon()

SITE = "comedy"
NAME = "Comedy Central"
DESCRIPTION = "COMEDY CENTRAL, the #1 brand in comedy, is available to over 99 million viewers nationwide and is a top-rated network among men ages 18-24 and 18-34 and adults ages 18-49.  With on-air, online and on-the-go mobile technology, COMEDY CENTRAL gives its audience access to the cutting-edge, laugh-out-loud world of comedy wherever they go.  Hit series include Tosh.0, Workaholics, Futurama, Key & Peele, Ugly Americans and the Emmy' and Peabody' Award-winning series The Daily Show with Jon Stewart, The Colbert Report and South Park.  COMEDY CENTRAL is also involved in producing nationwide stand-up tours, boasts its own record label and operates one of the most successful home entertainment divisions in the industry.  COMEDY CENTRAL is owned by, and is a registered trademark of Comedy Partners, a wholly-owned unit of Viacom Inc. (NASDAQ: VIA and VIAB).  For more information visit COMEDY CENTRAL's press Web site at www.cc.com/press or the network's consumer site at www.comedycentral.com and follow us on Twitter @ComedyCentralPR for the latest in breaking news updates, behind-the-scenes information and photos."
BASE = "http://www.cc.com"
SHOWS = "http://www.cc.com/shows"
VIDEOURL = "http://media.mtvnservices.com/"
RATINGS = {'Mature' : 'TV-MA', 'general audience' : 'TV-G'}

def masterlist():
	"""Build a list of all shows. First get all the shows listed in the Full Episodes menu
	   Then read all shows from the page's microdata. Filter to make sure there are no duplicates"""
	master_db = []
	root_doubles = []
	root_url = SHOWS
	root_data = connection.getURL(root_url)
	try:
		root_tree = BeautifulSoup(root_data, 'html.parser', parse_only = SoupStrainer('div'))
	except Exception, e:
		print e
	root_menu = root_tree.find(class_ = 'full_episodes').find_all('a', href = re.compile('^http+'), class_ = False)
	for root_item in root_menu:
		root_name = root_item.string
		if root_name is not None and root_name.lower() not in root_doubles and root_name.split(' with ')[0].lower() not in root_doubles:
			root_doubles.append(root_name.lower().split(' with ')[0])
			season_url = root_item['href']
			master_db.append((root_name, SITE, 'seasons', season_url))
	root_menu = root_tree.find_all('li', itemtype = 'http://schema.org/TVSeries')
 	for root_item in root_menu:
		try:
			root_name = root_item.find('meta', itemprop = 'name')['content']
		except:
			root_name = root_item.find_all(itemprop= 'name')[0].string
		if '|' in root_name:
			root_name = root_name.split('|')[0].strip()
		try:
			season_url = root_item.find('meta', itemprop = 'url')['content']
		except:
			season_url = root_item.find('a', itemprop = 'url')['href']
		if root_name.lower() not in root_doubles and root_name.split(' with ')[0].lower() not in root_doubles:
			root_doubles.append(root_name.lower().split(' with ')[0])
			master_db.append((root_name, SITE, 'seasons', season_url))
	return master_db

def _get_manifest(page_url):
	""" Try to get the manifest Javascript object for the current page. Input URL can be any kind of page
	    Returns the manifest feed as a JSON object if found, else return False """
	triforceManifestFeed = None
	page_data = connection.getURL(page_url.replace('=', '').strip())
	page_tree = BeautifulSoup(page_data, 'html.parser')
	scripts = page_tree.find_all('script', text= re.compile('triforceManifestFeed'))
	print scripts
	try:
		for script in scripts:
			print "S",script
			triforceManifestFeed = script.string.split('var triforceManifestFeed = ')[1]
			print triforceManifestFeed
			triforceManifestFeed = triforceManifestFeed.strip()[:-1]
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
	seasons = []
	print "su",show_url
	triforceManifestFeed = _get_manifest(show_url)
	if triforceManifestFeed:
		seasons = add_items_from_manifestfile(triforceManifestFeed, show_url)
	else:
		full_episodes_url = get_full_episodes_url(show_url)
		clips_url = get_clips_url(show_url)
		if full_episodes_url:
			triforceManifestFeed = _get_manifest(full_episodes_url)
			if triforceManifestFeed:
				seasons = add_items_from_manifestfile(triforceManifestFeed, full_episodes_url)
			else:
				seasons.append(('Full Episodes',  SITE, 'episodes', full_episodes_url, -1, -1))
		if clips_url:
			triforceManifestFeed = _get_manifest(clips_url)
			if triforceManifestFeed:
				seasons.extend(add_items_from_manifestfile(triforceManifestFeed, clips_url))
			else:
				seasons.append(('Full Episodes',  SITE, 'episodes', clips_url, -1, -1))
	return seasons

def episodes(episode_url = common.args.url):
	""" Add individual episodes. If the URL is a manifest feed, load from JSON, else analyse
	    the HTML of the page """
	if episode_url.endswith('#ManifestFeed'):
		triforceManifestFeed = _get_manifest_feed(episode_url)
		if triforceManifestFeed:
			episodes = add_video_from_manifestfile(triforceManifestFeed)
	else:
		episodes = episodes_from_html(episode_url)
	return episodes

def get_full_episodes_url(show_url):
	""" Get the URL to the full episodes page """
	show_data = connection.getURL(show_url)
	show_tree = BeautifulSoup(show_data, 'html5lib')
	show_menu = None
	try:
		show_menu = show_tree.find('a', class_ = 'episodes')
	except:
		pass
	if show_menu is None:
		show_menu = show_tree.find('a', text = re.compile('full episodes', re.IGNORECASE))
	if show_menu is not None:
		full_episodes_url = show_menu['href']
		if 'http' not in full_episodes_url:
			full_episodes_url = show_url + full_episodes_url
		return full_episodes_url
	else:
		return False
		
def get_clips_url(show_url):
	""" Get the URL to the clips page """
	show_data = connection.getURL(show_url)
	show_tree = BeautifulSoup(show_data, 'html5lib')
	show_menu = None
	show_menu = show_tree.find('a', href = re.compile('(?<!stand-up)/(video|clips)'))
	if show_menu is not None:
		clips_url = show_menu['href']
		if 'http' not in clips_url:
			clips_url = show_url + clips_url
		return clips_url
	else:
		return False

def episodes_from_html(episode_url = common.args.url, page = 1):
	""" Add episodes by analysing the HTML of the page """
	episodes = []
	if page == 1:
		episode_data = connection.getURL(episode_url)
		episode_tree = None
		try:
			episode_url = re.compile("var .*Showcase.* = '(.*)'").findall(episode_data)[0]
			if 'http' not in episode_url:
				episode_url = BASE + episode_url
			episode_data = connection.getURL(episode_url)
		except:
			try:
				episode_tree = BeautifulSoup(episode_data, 'html5lib')
				episode_url = episode_tree.find('div', class_ = 'content')['data-feed']
				episode_data = connection.getURL(episode_url)
				episode_tree = BeautifulSoup(episode_data, 'html5lib')
			except:
				pass
	if episode_tree is  None:
		episode_tree = BeautifulSoup(episode_data, 'html5lib')
	if 'Clips' in common.args.name  :
		next = episode_tree.find('a', class_ = re.compile('next'))		    
		episodes = add_video(episode_tree)
		if next is not None:
			try:
				if 'href' in next.attrs:
					nexturl = next['href'].replace(' ', '+')
				else:
					nexturl = next['onclick'].split(';')[0].replace("loadContent('", "").replace("')", "")
				if 'http' not in nexturl:
					nexturl = BASE + nexturl
				if page < int(addon.getSetting('maxpages')):
					episodes_from_html(nexturl, page + 1)
			except:
				pass
	else:
		next = episode_tree.find('a', class_ = re.compile('next'))		    
		episodes = add_video(episode_tree, False)
		if next is not None:
			try:
				nexturl = next['href']
				if nexturl[0] == '?': 
					nexturl = episode_url.split('?')[0] + nexturl				
				elif 'http' not in nexturl: 
					nexturl = BASE + nexturl
				if page < int(addon.getSetting('maxpages')):
					episodes.extend(episodes_from_html(nexturl, page + 1))
			except:
				pass
	return episodes

def _keyinfeed(keys1, keys2):
	""" Helper function to find if a key from an list is present in another list """
	for key in keys1:
		if key in keys2:
			return True
	return False

def add_items_from_manifestfile(triforceManifestFeed, season_url):
	""" Add container items based on the manifest feed. If there are no items in the feed
	    skip it. Special rule not to add Daily Show items to Colbert Report and vice versa """
	seasons = []
	if True:
		feeds = []
		for zone in triforceManifestFeed['manifest']['zones']:
			thiszone = triforceManifestFeed['manifest']['zones'][zone]
			feed_data = connection.getURL(thiszone['feed'])
			feed = simplejson.loads(feed_data)
			try:
				promoType = feed['result']['promo']['promoType']
			except:
				promoType = None
			if _keyinfeed(['videos','episodes','playlist','playlists','episodeVideos'], feed['result'].keys()) and promoType != 'all_full_episodes':

				if 'episodes' in feed['result']:
					if len(feed['result']['episodes']) == 0:
						continue
				if 'episodeVideos' in feed['result']:
					if len(feed['result']['episodeVideos']) == 0:
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
				try:
					title = feed['result']['promo']['headline']
				except:
					pass
				if title == '':
					if ' - ' in thiszone['moduleName']:
						title = thiszone['moduleName'].split(' - ')[1]
					else:
						title = thiszone['moduleName']
					if title.endswith(' Promo'):
						title = title[:-6]
				feeds.append({'title': title, 'url': thiszone['feed']})
		feeds.sort(key = lambda x: x['title'])
		for feed in feeds:
			if 'Daily Show' in feed['title'] and 'colbertreport' in season_url:
				continue
			if 'Colbert' in feed['title'] and 'dailyshow' in season_url:
				continue
			
			title = feed['title']
			feed_url =  feed['url'] 
			if 'ENT_' not in title:
				display_name = title
			else:
				feed_data2 = connection.getURL(feed_url)
				feed_menu2 = simplejson.loads(feed_data2)
				try:
					display_name = feed_menu2['result']['promo']['headerText'].replace('More', 'Full')
				except:
					try:
						display_name = feed_menu2['result']['playlist']['title']
					except:
						try:
							display_name = feed_menu2['result']['promo']['promoType'].replace('_', ' ').title().replace('Episode', 'Videos')
						except:
							display_name = feed_menu2['result']['episodeVideos'][0]['distPolicy']['canonicalURL'].split('/')[3].title().replace('-', ' ')
			seasons.append((display_name,  SITE, 'episodes', feed['url'] + "#ManifestFeed", -1, -1))
	return seasons
	
def add_video_from_manifestfile(manifest_feed):
	""" Add videos based on a manifest feed """
	try:
		episodes = []
		shows = []
		items = manifest_feed['result']
		if 'episodes' in items:
			items = items['episodes']
		elif 'videos' in items:
			items = items['videos']
		elif 'playlist' in items:
			items = items['playlist']['videos']
		elif 'episodeVideos' in items:
			items = items['episodeVideos']
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
		try:
			episode_type = manifest_feed['result']['promo']['promoType'].replace('_', ' ').title()
		except:
			episode_type = 'Clip'
		for item in items:
			try:
				episode_name = item['title']
			except:
				episode_name = item['shortTitle']
			epoch = float(item['airDate'])
			epoch = common.convert_to_timezone(epoch, '', -5, epoch)  
			episode_airdate = common.format_date(epoch , '', '%d.%m.%Y', epoch)
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
			show_name = item['show']['title']
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
			show = {'u': u, 'episode_name': episode_name, 'episode_thumb': episode_thumb, 'infoLabels': infoLabels, 'epoch': epoch}
			shows.append(show)
		if len(shows):
			shows = sorted(shows, key=lambda show: show['epoch'], reverse=True)
			for show in shows:
				episodes.append((show['u'], show['episode_name'], show['episode_thumb'], show['infoLabels'], 'list_qualities', False, episode_type))
		return episodes
	except:
		pass

def add_fullepisodes_southpark(episode_tree):
	try:
		season = urllib.unquote(sys.argv[2].split('&')[2].split('=')[1].replace('%22','')).split(' ')[1]
		episode_menu = episode_tree.find_all('article', class_ = 'thumb')
		for episode_item in episode_menu:
			episode_name = episode_item.find(class_ = 'title')
			if episode_name is None:
				continue
			url = episode_item.a['href']
			try:
				season_number, episode_number = re.compile('s([0-9]{2})e([0-9]{2})').findall(url)[0]
			except:
				episode_number = -1
				season_number = -1
			
			if int(season) != int(season_number):
				continue
			episode_name = episode_name.string.strip()
			episode_plot = episode_item.find('p', class_ = 'episode').string.strip()
			episode_airdate = episode_item.find(class_ = 'air-date').string.strip()
			episode_airdate = common.format_date(episode_airdate , '%m.%d.%Y', '%d.%m.%Y')
			episode_thumb = re.match('(.*?)url\(\'(.*?)\'\)', episode_item.find('a', class_ = 'fill')['style']).group(2)
			u = sys.argv[0]
			u += '?url="' + urllib.quote_plus(url) + '"'
			u += '&mode="' + SITE + '"'
			u += '&sitemode="play_video"'
			infoLabels={	'title' : episode_name,
							'season' : season_number,
							'episode' : episode_number,
							'plot' : episode_plot,
							'premiered' : episode_airdate }
			common.add_video(u, episode_name, episode_thumb, infoLabels = infoLabels, quality_mode  = 'list_qualities')
	except:
		pass

def add_video(episode_tree, episode = False):
	try:
		episodes = []
		episode_menu = episode_tree.find_all(itemtype = 'http://schema.org/TVEpisode')
		if not episode_menu:
			episode_menu = episode_tree.find_all(itemtype = 'http://schema.org/VideoObject')
		for episode_item in episode_menu:
			if episode == False or episode_item.find(class_ = 'episode'):
				episode_name = episode_item.find('meta', itemprop = 'name')['content']
				episode_plot = episode_item.find('meta', itemprop = 'description')['content']
				url = episode_item.find('meta', itemprop = 'url')['content']
				try:
					episode_thumb = episode_item.find('meta', itemprop = 'image')['content'].split('?')[0]
				except:
					try:
						episode_thumb = episode_item.find('meta', itemprop = 'thumbnailUrl')['content'].split('?')[0]
					except:
						episode_thumb = episode_item.find('img')['src'].split('?')[0]
				try:
					episode_airdate = episode_item.find('meta', itemprop = 'uploadDate')['content']
				except:
					try:
						episode_airdate = episode_item.find('meta', itemprop = 'datePublished')['content']
						try:
							episode_airdate = common.format_date(episode_airdate, '%B %d, %Y')
						except:
							episode_airdate = common.format_date(episode_airdate, '%b %d, %Y')
					except:
						episode_airdate = -1
				try:
					episode_duration = episode_item.find('meta', itemprop = 'duration')['content']
					try:
						duration_mins, duration_seconds = re.compile('([0-9]*)M([0-9]*)S').findall(episode_duration)[0]
						episode_duration_seconds = int(duration_mins) * 60 + int(duration_seconds)
					except:
						episode_duration_seconds = int(episode_duration.replace('S', '').replace('T',''))
				except:
					episode_duration_seconds = -1
				try:
					episode_meta = episode_item.find('div', class_ = 'video_meta').text.split('|')[0]
					season_number = int(episode_meta.split('-')[0].replace('Season', '').strip())
					episode_number = int(episode_meta.split('-')[1].replace('Episode', '').strip()[1:])
				except:
					season_number = -1
					episode_number = -1
				u = sys.argv[0]
				u += '?url="' + urllib.quote_plus(url) + '"'
				u += '&mode="' + SITE + '"'
				u += '&sitemode="play_video"'
				infoLabels={	'title' : episode_name,
								'durationinseconds' : episode_duration_seconds,
								'season' : season_number,
								'episode' : episode_number,
								'plot' : episode_plot,
								'premiered' : episode_airdate }
				episodes.append((u, episode_name, episode_thumb, infoLabels,  'list_qualities', False, 'Full Episode'))
		return episodes	
	except:
		pass

def add_clips_southpark(episode_tree):
	try:
		episode_menu = episode_tree.find_all('li', class_ = 'clips_thumb')
		clip_titles = []
		for episode_item in episode_menu:
			episode_name = episode_item.find('a', class_ = 'clips_thumb_link', text = True).string
			if episode_name not in clip_titles:
				clip_titles.append(episode_name)
				episode_plot = episode_item.find('h6').string.replace('"', '')
				url = episode_item.find('a')['href']
				episode_thumb = episode_item.find('img')['src'].split('?')[0]
				try:
					episode_duration_seconds = common.format_seconds(episode_item.find('span', class_ = 'clips_duration').string)
				except:
					episode_duration_seconds = -1
				try:
					episode_season = int(episode_item.find('h5', class_ = 'clips_thumb_season').string.replace('Season ', ''))
				except:
					episode_season = -1
				u = sys.argv[0]
				u += '?url="' + urllib.quote_plus(url) + '"'
				u += '&mode="' + SITE + '"'
				u += '&sitemode="play_video"'
				infoLabels={	'title' : episode_name,
								'duration' : episode_duration_seconds,
								'season' : episode_season,
								'plot' : episode_plot,
								'tvshowtitle' : 'South Park'}
				common.add_video(u, episode_name, episode_thumb, infoLabels = infoLabels, quality_mode  = 'list_qualities')
	except:
		pass

def play_video(video_url = common.args.url):
	video_data = connection.getURL(video_url)
	try:
		mgid = BeautifulSoup(video_data, 'html.parser').find('div', attrs = {'data-mgid' : True})['data-mgid']
		video_url2 = mgid
	except:
		try:
			video_url2 = re.compile('swfobject\.embedSWF\("(.*?)"').findall(video_data)[0]
		except:
			embedded_data = BeautifulSoup(video_data, 'html.parser').find('meta',  property = "sm4:video:embed" )['content']
			video_url2 = BeautifulSoup(embedded_data, 'html.parser').iframe['src'].split('embed/')[1]
	show = video_url2.split(':')[-2].replace('.com', '')
	if show != 'comedycentral':
		show = 'www'
	feed_url = 'http://' + show + '.cc.com/feeds/mrss?uri=' + video_url2 
	main_viacom.play_video(BASE, feed_url)

def list_qualities(video_url = common.args.url):
	video_data = connection.getURL(video_url)
	try:
		mgid = BeautifulSoup(video_data, 'html5lib').find('div', attrs = {'data-mgid' : True})['data-mgid']
		video_url2 = VIDEOURL + mgid
	except:
		video_url2 = re.compile('swfobject\.embedSWF\("(.*?)"').findall(video_data)[0]
	return main_viacom.list_qualities(BASE, video_url2)
