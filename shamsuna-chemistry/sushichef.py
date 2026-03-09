#!/usr/bin/env python
# coding: utf-8
import os
import sys
from ricecooker.utils import downloader, html_writer
from ricecooker.chefs import SushiChef
from ricecooker.classes import nodes, files, questions, licenses
from ricecooker.config import LOGGER              # Use LOGGER to print messages
from ricecooker.exceptions import raise_for_invalid_channel
from le_utils.constants import exercises, content_kinds, file_formats, format_presets, languages
import re

# Run constants
################################################################################
CHANNEL_NAME = "MIT-مبادىء علم الكيمياء"                                # Name of channel
CHANNEL_SOURCE_ID = "shamsuna_chemistry_ar"
CHANNEL_DOMAIN = "https://www.youtube.com/channel/UCQtFMzEj81ZvIDjDzY6r4XA"          # Who is providing the content
CHANNEL_LANGUAGE = "ar"                                           # Language of channel
CHANNEL_DESCRIPTION = ""
CHANNEL_THUMBNAIL = None

# Additional constants
################################################################################
import youtube_dl

# PLAYLISTS_URL = "https://www.youtube.com/user/HealingClassrooms/playlists"
PLAYLISTS_URL = "https://www.youtube.com/watch?v=XeKL2sUSowE&list=PLgtqMzuQ7viozAz2dhPY-khXGQKExdKt8"
AUTHOR = "Shamsuna Al Arabia"

# The chef subclass
################################################################################
class MyChef(SushiChef):
    """
    This class uploads the Healing Classrooms channel to Kolibri Studio.
    Your command line script should call the `main` method as the entry point,
    which performs the following steps:
      - Parse command line arguments and options (run `./sushichef.py -h` for details)
      - Call the `SushiChef.run` method which in turn calls `pre_run` (optional)
        and then the ricecooker function `uploadchannel` which in turn calls this
        class' `get_channel` method to get channel info, then `construct_channel`
        to build the contentnode tree.
    For more info, see https://github.com/learningequality/ricecooker/tree/master/docs
    """
    channel_info = {                                   # Channel Metadata
        'CHANNEL_SOURCE_DOMAIN': CHANNEL_DOMAIN,       # Who is providing the content
        'CHANNEL_SOURCE_ID': CHANNEL_SOURCE_ID,        # Channel's unique id
        'CHANNEL_TITLE': CHANNEL_NAME,                 # Name of channel
        'CHANNEL_LANGUAGE': CHANNEL_LANGUAGE,          # Language of channel
        'CHANNEL_THUMBNAIL': CHANNEL_THUMBNAIL,        # Local path or url to image file (optional)
        'CHANNEL_DESCRIPTION': CHANNEL_DESCRIPTION,    # Description of the channel (optional)
    }
    # Your chef subclass can ovverdie/extend the following method:
    # get_channel: to create ChannelNode manually instead of using channel_info
    # pre_run: to perform preliminary tasks, e.g., crawling and scraping website
    # __init__: if need to customize functionality or add command line arguments

    def construct_channel(self, *args, **kwargs):
        """
        Creates ChannelNode and build topic tree
        Args:
          - args: arguments passed in during upload_channel (currently None)
          - kwargs: extra argumens and options not handled by `uploadchannel`.
            For example, add the command line option   lang="fr"  and the string
            "fr" will be passed along to `construct_channel` as kwargs['lang'].
        Returns: ChannelNode

        Healing Classrooms is organized with the following hierarchy:
            Playlist (TopicNode)
            |   Youtube Video (VideoNode)
            |   Youtube Video (VideoNode)

        """
        channel = self.get_channel(*args, **kwargs)  # Create ChannelNode from data in self.channel_info

        # Download the playlist/video information
        try:
            with youtube_dl.YoutubeDL({'skip_download': True}) as ydl:
              info_dict = ydl.extract_info(PLAYLISTS_URL, download=False)
              print (info_dict.keys())

              # Generate topics based off playlist entries in dict
              #for playlist in info_dict['entries']:
  
                  # Get language of playlist (hack)
              #    language = "fr"
              #    if "English" in playlist['title']:
              #        language = "en"
              #    elif "Arabic" in playlist['title']:
              language = "ar"
  
              #    playlist_topic = nodes.TopicNode(title=playlist['title'], source_id=playlist['id'], language=language)
              #    channel.add_child(playlist_topic)
  

                  # Generate videos based off video entries in dict
              videos = sorted(info_dict['entries'], key=lambda x: int(re.search("\d+", x['title']).group()))
              print( [v['title'] for v in videos])
              import time
              time.sleep(15)
              for video in videos:
                  #try:
                  #    num, = re.findall("\d+",video['title'])
                  #    title = re.sub(video['title'], num, "")
                  #    title = ("0"+num)[-2:] + " " + title 
                  #except Exception as e:
                  #    print (e)
                  #    print (video['title'])
                  #    print (repr(video['title']))
                  #    raise
                  thumbnail_url = len(video['thumbnails']) and video['thumbnails'][0]['url']

                  channel.add_child(nodes.VideoNode(
                      title = video['title'],
                      source_id = video['id'],
                      license = licenses.PublicDomainLicense(),
                      description = video['description'],
                      derive_thumbnail = not thumbnail_url,
                      files = [files.WebVideoFile(video['webpage_url'])],
                      thumbnail = thumbnail_url,
                      author = AUTHOR,
                      # tags = video['categories'] + video['tags'], # TODO: uncomment this when added
                      ))
        except Exception as e:
            import traceback, sys
            traceback.print_exc(file=sys.stdout)
            raise
    
        raise_for_invalid_channel(channel)  # Check for errors in channel construction

        return channel



# CLI
################################################################################
if __name__ == '__main__':
    # This code runs when sushichef.py is called from the command line
    chef = MyChef()
    chef.main()
