#!/usr/bin/env python
import os
import sys
import re
from ricecooker.chefs import YouTubeSushiChef
from ricecooker.classes import licenses
from ricecooker.config import LOGGER
from googleapiclient.discovery import build


# Run constants
################################################################################
CHANNEL_ID = "04deda9bf5b5489689191d4f2bcbaf74"             # UUID of channel
CHANNEL_NAME = "Chicken N Chips"                           # Name of Kolibri channel
CHANNEL_SOURCE_ID = "chicken-n-chips"                              # Unique ID for content source
CHANNEL_DOMAIN = "youtube.com"                         # Who is providing the content
CHANNEL_LANGUAGE = "en"                                     # Language of channel
CHANNEL_DESCRIPTION = 'Chicken & Chips is a weekly pop culture magazine, that focuses on relationships and combines music, journalism, puppetry and animation to create the freshest blend of edutainment in Uganda. Airs every Sunday at 1:30pm on NTV Uganda'                                  # Description of the channel (optional)
CHANNEL_THUMBNAIL = os.path.join('files', 'logo.png')       # Local path or url to image file (optional)
CONTENT_ARCHIVE_VERSION = 1                                 # Increment this whenever you update downloaded content


# Additional constants
################################################################################
# TODO Add GOOGLE API key here. Will need access to Youtube API v3
GOOGLE_API_KEY = os.getenv(GOOGLE_API_KEY)
CHICKEN_N_CHIPS_CHANNEL_ID = 'UCIGQCJIF4fdTrqxnvcwTYxg'


# The chef subclass
################################################################################
class ChickenNChipsChef(YouTubeSushiChef):
    """
    This class converts content from the content source into the format required by Kolibri,
    then uploads the {channel_name} channel to Kolibri Studio.
    Your command line script should call the `main` method as the entry point,
    which performs the following steps:
      - Parse command line arguments and options (run `./sushichef.py -h` for details)
      - Call the `SushiChef.run` method which in turn calls `pre_run` (optional)
        and then the ricecooker function `uploadchannel` which in turn calls this
        class' `get_channel` method to get channel info, then `construct_channel`
        to build the contentnode tree.
    For more info, see https://ricecooker.readthedocs.io
    """
    channel_info = {
        'CHANNEL_ID': CHANNEL_ID,
        'CHANNEL_SOURCE_DOMAIN': CHANNEL_DOMAIN,
        'CHANNEL_SOURCE_ID': CHANNEL_SOURCE_ID,
        'CHANNEL_TITLE': CHANNEL_NAME,
        'CHANNEL_LANGUAGE': CHANNEL_LANGUAGE,
        'CHANNEL_THUMBNAIL': CHANNEL_THUMBNAIL,
        'CHANNEL_DESCRIPTION': CHANNEL_DESCRIPTION,
    }
    DATA_DIR = os.path.abspath('chefdata')
    DOWNLOADS_DIR = os.path.join(DATA_DIR, 'downloads')
    ARCHIVE_DIR = os.path.join(DOWNLOADS_DIR, 'archive_{}'.format(CONTENT_ARCHIVE_VERSION))


    def get_video_ids(self):
        return get_video_ids(CHICKEN_N_CHIPS_CHANNEL_ID)

    def get_channel_metadata(self):
        return {
            'defaults': {
                'license': licenses.CC_BY_NCLicense("Chicken&Chips"),
                'high_resolution': True
            }
        }
    
    def sort_topic_nodes(self, channel, key = None, reverse = False):
        """
        Sort Topic Nodes in channel
        :param channel: channel to sort
        :param key: A Function to execute to decide the order. Default None
        :param reverse: A Boolean. False will sort ascending, True will sort descending. False by default
        :return: Sorted channel
        """
        # default natural sorting
        if not key:
            convert = lambda text: int(text) if text.isdigit() else text.lower() 
            key = lambda key: [ convert(re.sub(r'[^A-Za-z0-9]+', '', c.replace('&', 'and'))) for c in re.split('([0-9]+)', key.title) ]
        try:
            channel.children = sorted(channel.children, key = key, reverse = reverse)
        except Exception as e:
            LOGGER.error("Failed to sort: [%s]. Calling default sorting method", e)
            convert = lambda text: int(text) if text.isdigit() else text.lower() 
            key = lambda key: [ convert(re.sub(r'[^A-Za-z0-9]+', '', c.replace('&', 'and'))) for c in re.split('([0-9]+)', key.title) ]
            channel.children = sorted(channel.children, key = key, reverse = reverse)
        return channel

    
    def construct_channel(self, *args, **kwargs):
        channel = self.get_channel(*args, **kwargs)

        if len(self.get_playlist_ids()) == 0 and len(self.get_video_ids()) == 0:
            raise NotImplementedError("Either get_playlist_ids() or get_video_ids() must be implemented.")

        # TODO: Replace next line with chef code
        nodes = self.create_nodes_for_playlists()
        for node in nodes:
            channel.add_child(node)

        nodes = self.create_nodes_for_videos()
        for node in nodes:
            channel.add_child(node)

        channel = self.sort_topic_nodes(channel)
        
        return channel



def get_video_ids(channel_id):
    if not GOOGLE_API_KEY:
        raise Exception('Missing Google API Key. Please add a key to proceed.')
        exit(1)
        
    youtube = build('youtube', 'v3', developerKey = GOOGLE_API_KEY)
    response = youtube.channels().list(id=channel_id, part = 'contentDetails').execute()

    uploads_id = response['items'][0]['contentDetails']['relatedPlaylists']['uploads']

    video_ids = []
    next_page_token = None
    while 1:

        uploads_playlist = youtube.playlistItems().list(playlistId=uploads_id, part='snippet', maxResults = 50, pageToken = next_page_token).execute()
        for element in uploads_playlist['items']:
            video_ids.append(element['snippet']['resourceId']['videoId'])
        
        next_page_token = uploads_playlist.get('nextPageToken')

        if next_page_token is None:
            break

    return video_ids


settings = {
    'generate-missing-thumbnails': True,
    'compress-videos': True
}
# CLI
################################################################################
if __name__ == '__main__':
    # This code runs when sushichef.py is called from the command line
    chef = ChickenNChipsChef()
    for setting in settings:
        value = settings[setting]
        chef.SETTINGS[setting] = value
    chef.main()
