#!/usr/bin/python
# -*- coding: utf-8 -*-
import common
import connection
import main_nbcu
import sys
import urllib
import re
from bs4 import BeautifulSoup

SITE = "syfy"
NAME = "Syfy"
ALIAS = ["SciFi"]
DESCRIPTION = "Syfy is a media destination for imagination-based entertainment. With year round acclaimed original series, events, blockbuster movies, classic science fiction and fantasy programming, a dynamic Web site (www.Syfy.com), and a portfolio of adjacent business (Syfy Ventures), Syfy is a passport to limitless possibilities. Originally launched in 1992 as SCI FI Channel, and currently in 95 million homes, Syfy is a network of NBC Universal, one of the world's leading media and entertainment companies. Syfy. Imagine greater."
SHOWS = "http://feed.theplatform.com/f/hQNl-B/2g1gkJT0urp6/categories?form=json&sort=order"
CLIPS = "http://feed.theplatform.com/f/hQNl-B/2g1gkJT0urp6?count=true&form=json&byCustomValue={fullEpisode}{false}&byCategories=%s"
FULLEPISODES = "http://feed.theplatform.com/f/hQNl-B/2g1gkJT0urp6?count=true&form=json&byCustomValue={fullEpisode}{true}&byCategories=%s"
SWFURL = "http://www.syfy.com/_utils/video/codebase/pdk/swf/flvPlayer.swf"
FULLEPISODESWEB = "http://www.syfy.com/%s/episodes"
BASE = "http://syfy.com"
M3UURL = 'https://tvesyfy-vh.akamaihd.net/i/prod/video/%s_,25,40,18,12,7,4,2,00.mp4.csmil/master.m3u8?__b__=1000&hdnea=st=%s~exp=%s'

def masterlist():
	return main_nbcu.masterlist(SITE, SHOWS)

def seasons(season_url = common.args.url):
	return main_nbcu.seasons(SITE, FULLEPISODES, CLIPS, FULLEPISODESWEB, season_url)

def episodes(episode_url = common.args.url):
	return main_nbcu.episodes(SITE, episode_url)

def list_qualities():
	return main_nbcu.list_qualities(M3UURL)

def play_video():
	main_nbcu.play_video(SWFURL, M3UURL, BASE)
	
def episodes_web(episode_url = common.args.url):
	episodes = []
	try:
		episode_data = connection.getURL(episode_url)
	except Exception, e:
		print "Exception", e
	try:
		web_tree = BeautifulSoup(episode_data, 'html.parser')
	except:
		web_tree = BeautifulSoup(episode_data, 'html5lib')
	show_name = re.compile('showSite":"(.*?)"').findall(episode_data)[0]
	try:
		episode_menu = web_tree.find( class_ = 'view-syfy-show-episodes').find_all(class_ = 'views-row')
		for episode_item in episode_menu:
			if episode_item.find(text = re.compile('Full Episode')):
				episode_name = episode_item.h2.a.contents[1]
				try:
					season_number = int(episode_url.split('/')[-1])
				except:
					try:
						season_number = int(episode_url.split('/')[-1].split('?')[0])
					except:
						season_number = -1
				try:
					episode_number = int(episode_item.h2.a.span.string.replace('.',''))
				except:
					episode_number = -1
				try:
					episode_thumb = episode_item.img['src']
				except:
					episode_thumb = None
				episode_plot = episode_item.p.string
				url = episode_item.a['href']
				u = sys.argv[0]
				u += '?url="' + urllib.quote_plus(url) + '"'
				u += '&mode="' + SITE + '"'
				u += '&sitemode="play_video"'
				infoLabels={	'title' : episode_name,
								'season' : season_number,
								'episode' : episode_number,
								'TVShowTitle' : show_name,
								'plot' : episode_plot
							}
				episodes.append((u, episode_name, episode_thumb, infoLabels, 'list_qualities', False, 'Full Episode'))
		next = None
		try:
			next = web_tree.find('li', class_ = 'pager-next')
			if next:
				next_url = episode_url + '?' + next.a['href'].split('?')[1]
				episodes.extend(episodes_web(next_url))
		except:
			pass
	except:
		episode_menu = web_tree.find( class_ = 'pane-full-episodes-pane-episodes-by-show').find_all(class_ = 'grid-item')
		for episode_item in episode_menu:
			season_number, episode_number, episode_name = re.compile('S(\d)\.E(\d+) (.*)').search(episode_item.span.string).groups()
			url = BASE + episode_item.a['href']
			episode_thumb = episode_item.img['src']
			u = sys.argv[0]
			u += '?url="' + urllib.quote_plus(url) + '"'
			u += '&mode="' + SITE + '"'
			u += '&sitemode="play_video"'
			infoLabels={	'title' : episode_name,
							'season' : season_number,
							'episode' : episode_number,
							'TVShowTitle' : show_name
						}
			episodes.append((u, episode_name, episode_thumb, infoLabels, 'list_qualities', False, 'Full Episode'))
	return episodes
