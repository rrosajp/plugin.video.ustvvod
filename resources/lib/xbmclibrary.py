#!/usr/bin/env python
# -*- coding: utf-8 -*-
import common
import os.path
import string
import sys
import urllib
import shutil
import time
import traceback
import ustvpaths
import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs
import glob

from bs4 import BeautifulSoup

addon = xbmcaddon.Addon()
pluginHandle = int(sys.argv[1]) 

if (addon.getSetting('enablelibraryfolder') == 'true'):
	MOVIE_PATH = os.path.join(xbmc.translatePath('special://profile/addon_data/plugin.video.ustvvod'),'Movies')
	TV_SHOWS_PATH = os.path.join(xbmc.translatePath('special://profile/addon_data/plugin.video.ustvvod/'),'TV')
elif (addon.getSetting('customlibraryfolder') <> ''):
	if addon.getSetting('customlibraryfoldermovie') == '':
		MOVIE_PATH = os.path.join(xbmc.translatePath(addon.getSetting('customlibraryfolder')),'Movies')
		TV_SHOWS_PATH = os.path.join(xbmc.translatePath(addon.getSetting('customlibraryfolder')),'TV') 
	else:
		MOVIE_PATH = xbmc.translatePath(addon.getSetting('customlibraryfoldermovie'))
		TV_SHOWS_PATH = xbmc.translatePath(addon.getSetting('customlibraryfolder')) 
	
class Validate:
	def __init__( self ):
		sources = xbmc.translatePath('special://profile/sources.xml')
		file = open(sources, 'r')
		source_data = file.read()
		file.close()
		source_tree = BeautifulSoup(source_data, 'html.parser')
		tv_path = source_tree.find('path', text = TV_SHOWS_PATH)
		movie_path = source_tree.find('path', text = MOVIE_PATH)
		msg = ""
		if tv_path is None:
			msg = "No source for " + TV_SHOWS_PATH + "\n"
		if movie_path is None:
			msg = "No source for " + MOVIE_PATH + "\n"
		if msg != "":
			dialog = xbmcgui.Dialog()
			dialog.ok(addon.getLocalizedString(39042), msg)
		else:
			dialog = xbmcgui.Dialog()
			dialog.ok(addon.getLocalizedString(39042), "Sources OK")
	
class Main:
	active = False
	def __init__( self ):
		if (addon.getSetting('enablelibraryfolder') == 'true'):
			self.SetupUSTVVODLibrary()
		elif (addon.getSetting('customlibraryfolder') <> ''):
			self.CreateDirectory(MOVIE_PATH)
			self.CreateDirectory(TV_SHOWS_PATH) 
		else:
			return

		if common.args.mode.startswith('Clear'):
			dialog = xbmcgui.Dialog()
			if dialog.yesno('Clear Exported Items', 'Are you sure you want to delete all exported items?'):
				shutil.rmtree(MOVIE_PATH)
				shutil.rmtree(TV_SHOWS_PATH)
			return
		
		if common.args.mode.startswith('Force'):
			self.EnableNotifications = True
		else:
			self.EnableNotifications = False

		if common.args.mode.endswith('FavoriteEpisodesLibrary'):
			try:
				self.GetFavoriteEpisodes()
			except Exception as e:
				print "Error exporting " , e
		elif common.args.mode.endswith('NetworkLibrary'):
			try:
				self.GetNetworkShows(common.args.submode)
			except Exception as e:
				print "Error exporting site ", e
		elif common.args.mode.endswith('AllShowsLibrary'):
			self.GetAllShows()
		elif common.args.mode.endswith('ExportShowLibrary'):
			series_title, mode, submode, url = common.args.url.split('<join>')
			series_title = urllib.unquote_plus(series_title)
			self.GetShow(series_title, mode, submode, url)
		if (addon.getSetting('updatelibrary') == 'true'):
			self.UpdateLibrary()
			self.CleanLibrary()
	
	def UpdateLibrary(self):
		xbmc.executebuiltin("UpdateLibrary(video)")
		
	def CleanLibrary(self):
		xbmc.executebuiltin("CleanLibrary(video)")
	
	def Notification(self, heading, message, duration = 10000, image = None):
		if self.EnableNotifications == True:
			if image is None:
				xbmc.executebuiltin('XBMC.Notification("%s", "%s", %s)' % ( heading, message, duration) )
			else:
				xbmc.executebuiltin('XBMC.Notification("%s", "%s", %s, "%s")' % ( heading, message, duration, image) )

	def SaveFile(self, filename, data, dir):
		path = os.path.join(dir, filename)
		file = xbmcvfs.File(path, 'w')
		data = common.smart_utf8(data)
		file.write(data)
		file.close()

	def CreateDirectory(self, dir_path):
		os.path.join(dir_path, '') # ensure the path terminates in a '/'
		if not xbmcvfs.exists(dir_path):
			xbmcvfs.mkdirs(dir_path)
	
	def cleanfilename(self, name):    
		valid_chars = "-_.() %s%s" % (string.ascii_letters, string.digits)
		return ''.join(c for c in name if c in valid_chars).strip()

	def GetFavoriteEpisodes(self):
		shows = common.fetch_showlist(1)
		self.ExportShowList(shows, 750)
		self.Notification(addon.getLocalizedString(39036), addon.getLocalizedString(39037) % addon.getLocalizedString(39000), image = ustvpaths.FAVICON)
		
	def GetAllShows(self):
		shows = common.fetch_showlist(0)
		self.ExportShowList(shows, 750)
		self.Notification(addon.getLocalizedString(39036), addon.getLocalizedString(39037) % addon.getLocalizedString(39002), image = ustvpaths.ALLICON)
			
	def GetShow(self, series_title, mode, sitemode, url):
		showdata = common.get_show_data(series_title, mode, sitemode, url)
		self.ExportShowList([showdata], 10)
		image =  showdata[7]
		self.Notification(addon.getLocalizedString(39036), addon.getLocalizedString(39037) % series_title, image = image)
	
	def GetNetworkShows(self, site):
		network = common.get_network(site)
		if network:
			networkshows = getattr(network, 'masterlist')()
			shows = []
			for show in networkshows:
				try:
					series_title, mode, sitemode, url = show
					siteplot = None
				except:
					series_title, mode, sitemode, url, siteplot = show
				showdata = common.get_show_data(series_title, mode, sitemode, url, siteplot)
				shows.append(showdata)
			self.ExportShowList(shows, 100)
			image =  os.path.join(ustvpaths.IMAGEPATH, network.SITE + '.png')
			self.Notification(addon.getLocalizedString(39036), addon.getLocalizedString(39037) % network.NAME, image = image)

	def ExportShowList(self, shows, delay = 0): 
		for show in shows:
			self.ExportShowMovie(show)
			xbmc.sleep(delay)
			
	def ExportShowMovie(self, item):
		try:
			self.ExportShow(item)
		except Exception as e:
			print "Error exporting show", e, item
			print traceback.format_exc()

	def ExportShow(self, show):
		series_title, mode, sitemode, url, tvdb_id, imdb_id, tvdbbanner, tvdbposter, tvdbfanart, first_aired, date, year, actors, genres, studio, plot, runtime, rating, airs_dayofweek, airs_time, status, has_full_episodes, favor, hide, show_name = show
		allepisodes = []
		has_episodes = False
		has_movies = False
		if '--' not in series_title:
			directory = os.path.join(TV_SHOWS_PATH, self.cleanfilename(show_name))
			filelist = glob.glob(os.path.join(directory,"*.strm"))
		
			seasons = common.get_seasons(mode, sitemode, url)
			for season in seasons:
				section_title,  site, subsitemode, suburl, locked, unlocked = season
				if 'Clips' not in section_title and ('Episode' in section_title or 'Season' in section_title):
					episodes = common.get_episodes(mode, subsitemode, suburl, tvdb_id) 
					allepisodes.extend(episodes)
					if allepisodes != []:
						for episode in allepisodes:
							try:
								type = episode[-1]
							except:
								print "Type not found.............."
							try:
								
								info = episode[3]
							except:
								print "Info not found......................."
							try:
								number = info['episode']
							except:
								number = -1
							if type == 'Full Episode' and number > -1:
								has_episodes = True
		else:
			episodes = common.get_episodes(mode, sitemode, url, tvdb_id)
			allepisodes = episodes
			has_movies = True
		if has_movies:
			directory = MOVIE_PATH
			for episode in allepisodes:
				self.ExportVideo(episode, directory, studio = studio)
				icon = episode[2]
				self.Notification(addon.getLocalizedString(39036), addon.getLocalizedString(39037) % episode[1], image = icon)
		elif has_episodes:
			self.CreateDirectory(directory)
			if addon.getSetting('shownfo') == 'true':
				
				tvshowDetails  = '<tvshow>'
				tvshowDetails += '<title>'+ show_name + '</title>'
				tvshowDetails += '<showtitle>' + show_name + '</showtitle>'
				tvshowDetails +=  '<rating>' + str(rating) + '</rating>'
				tvshowDetails +=  '<year>' + str(year) + '</year>'
				try:
					plot = common.replace_signs(plot)
					tvshowDetails +=  '<plot>' + plot + '</plot>'
				except:
					pass
				try:
					tvshowDetails += '<runtime>' + runtime +'</runtime>'
				except:
					pass
				try:
					tvshowDetails += '<thumb>' + tvdbposter +'</thumb>'
				except:
					try:
						tvshowDetails += '<thumb>' + tvdbbanner +'</thumb>'
					except:
						pass
				try:
					tvshowDetails += '<fanart>'
					tvshowDetails += '<thumb dim="1920x1080" colors="" preview="' + tvdbfanart + '">' + tvdbposter + '</thumb></fanart>'
				except:
					pass
				try:
					epguide = common.TVDBURL + ('/api/%s/series/%s/all/en.zip' % (common.TVDBAPIKEY, TVDB_ID))
					tvshowDetails += '<episodeguide>'
					tvshowDetails += '<url cache="' + TVDB_ID + '.xml">'+ epguide +'</url>'
					tvshowDetails += '</episodeguide>'
					tvshowDetails += '<id>' + TVDB_ID +'</id>'
				except:
					pass
				try:
					for genre in genres.split('|'):
						if genre:
							tvshowDetails += '<genre>' + genre + '</genre>'
				except:
					pass
				try:
					tvshowDetails += '<premiered>' + first_aired + '</premiered>'
				except:
					pass
				try:
					tvshowDetails += '<status>' + status + '</status>'
				except:
					pass
				try:
					tvshowDetails += '<studio>' + studio + '</studio>'
				except:
					pass
				try:
					for actor in actors.split('|'):
						if actor:
							tvshowDetails += '<actor><name>' + common.smart_unicode(actor) + '</name></actor>'
				except:
					pass
				tvshowDetails +='<dateadded>' + time.strftime("%Y-%m-%d %H:%M:%S") + '</dateadded>'
				tvshowDetails +='</tvshow>'					
				self.SaveFile( 'tvshow.nfo', tvshowDetails, directory)
			exported = []
			for episode in allepisodes:
				try:
					fname = self.ExportVideo(episode, directory, studio = studio)
					filelist.remove(fname)
				except Exception, e:
					print "Can't clean up video", e, filelist, fname
			#Delete eps not updated
			try:
				for f in filelist:
					print "Expired ",f
					os.remove(f)
			except:
				print "Exception deleting expired content"
			
			self.Notification(addon.getLocalizedString(39036), addon.getLocalizedString(39037) % show_name, image = tvdbposter)

		else:
			print "No episodes found "

	def ExportVideo(self, episode, directory, studio = None):
		strm, title, episode_thumb, data, qmode, ishd, media_type = episode
		title = data['title']
		if media_type == 'Full Episode':
			season = data['season']
			episode = data['episode']
			show_name = data['TVShowTitle']
			if season  > 0 and episode > -1:
				filename = self.cleanfilename('S%sE%s - %s' % (season, episode, title))
				try:
					strm = strm + '&name="'+ title +'"'
				except:
					pass
				try:
					strm = strm + '&thumb="' +  urllib.quote_plus(episode_thumb) +'"'
				except:
					pass
				try:
					strm = strm + '&episode_number="' + str(episode) + '"&season_number="'  + str(season) + '"&show_title="' + show_name +'"'
				except:
					pass
				
				self.SaveFile( filename + '.strm', strm, directory)
				if addon.getSetting('episodenfo') == 'true':
					episodeDetails  = '<episodedetails>'
					episodeDetails += '<title>'+title+' '+ addon.getSetting('librarysuffix') +'</title>'
					try:
						rating = str(float(data['Rating']))
					except:
						rating = ''
					episodeDetails += '<rating>' + rating + '</rating>'
					episodeDetails += '<season>' + str(season) + '</season>'
					episodeDetails += '<episode>' + str(episode) + '</episode>'
					try:
						plot = data['plot']
						episodeDetails += '<plot>' + common.smart_unicode(plot) + '</plot>'
					except:
						pass
					try:
						episodeDetails += '<thumb>' + episode_thumb +'</thumb>'
					except:
						pass
					try:
						original_premiere = data['premiered'].replace(' 00:00:00','')
						year = original_premiere.split('-')[0]
						episodeDetails += '<year>' + year + '</year>'
						episodeDetails += '<aired>' + original_premiere + '</aired>'
						episodeDetails += '<premiered>' + original_premiere + '</premiered>'
					except:
						pass
					try:
						episodeDetails += '<studio>' + studio + '</studio>'
					except:
						pass
					try:
						episodeDetails += '<mpaa>' + data['mpaa'] + '</mpaa>'
					except:
						pass
					try:
						for actor in data['cast']:
							episodeDetails += '<actor><name>' + actor.strip()+'</name></actor>'
					except:
						pass
					try:
						episodeDetails += '<rating>' + data['Rating'] + '</rating>'
					except:
						pass
					episodeDetails += '</episodedetails>'
					self.SaveFile( filename+'.nfo', episodeDetails, directory)
		elif media_type == 'Movie':
			filename = self.cleanfilename(title) 
			try:
				filename = filename + ' (%s)' % data['year']
			except:
				pass
			directory = MOVIE_PATH
			try:
					strm = strm + '&name="' + title +'"'
			except:
				pass
			self.SaveFile(filename+'.strm', strm, directory)
			if addon.getSetting('movienfo') == 'true':
				movie = '<movie>'
				movie += '<title>' + title+' '+ addon.getSetting('librarysuffix') + '</title>'
				try:
					movie += '<rating>' + data['rating'] + '</rating>'
				except:
					pass
				try:
					movie += '<plot>' + common.smart_unicode(data['plot']) + '</plot>'
				except:
					pass
				try:
					movie += '<thumb>' + episode_thumb + '</thumb>'
				except:
					pass
				try:	
					movie += '<year>' + str(data['year']) + '</year>'
				except:
					pass
				try:
					movie += '<genre>' + data['genre'] + '</genre>'
				except:
					pass
				try:
					movie += '<director>' + data['director'] + '</director>'
				except:
					pass
				try:
					movie += '<mpaa>' + data['mpaa'] + '</mpaa>'
				except:
					pass
				try:
					for actor in data['cast']:
						movie += '<actor><name>' + actor.strip() + '</name></actor>'
				except:
					pass
				try:
					durationseconds = data['durationinseconds']
					duration = int(durationseconds / 60)
					movie += '<runtime>' + duration + '</runtime>'
				except:
					pass
				movie += '</movie>'
				self.SaveFile(filename + '.nfo', movie, directory)
		return os.path.join(directory, filename + '.strm')

	def SetupUSTVVODLibrary(self):
		print "Trying to add USTVVOD source paths..."
		source_path = os.path.join(xbmc.translatePath('special://profile/'), 'sources.xml')
		dialog = xbmcgui.Dialog()
		
		self.CreateDirectory(MOVIE_PATH)
		self.CreateDirectory(TV_SHOWS_PATH)
