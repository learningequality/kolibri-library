#!/usr/bin/env python
import os
from ricecooker.chefs import YouTubeSushiChef
from ricecooker.classes import licenses
from googleapiclient.discovery import build


# Run constants
################################################################################
CHANNEL_ID = "32e5033ebc7a456b91fccbd2747d4035"             # UUID of channel
CHANNEL_NAME = "Newz Beat"                           # Name of Kolibri channel
CHANNEL_SOURCE_ID = "Newz_Beat"                              # Unique ID for content source
CHANNEL_DOMAIN = "youtube.com"                         # Who is providing the content
CHANNEL_LANGUAGE = "en"                                     # Language of channel
CHANNEL_DESCRIPTION = 'Follow the beat, follow the beat. From the studio to the street....Tuula, kalira, wuliriza, nyumirwa amawulire! NewzBeat is a Ugandan rap-news programme delivering the latest information in verse and rhyme. Beeramu tosubwa amawulire gaffe mu bitontome! This bilingual English-Luganda news magazine show airs on NTV Uganda every weekend!'                                  # Description of the channel (optional)
CHANNEL_THUMBNAIL = os.path.join('files', 'logo.jpg')                                    # Local path or url to image file (optional)
CONTENT_ARCHIVE_VERSION = 1                                 # Increment this whenever you update downloaded content


# Additional constants
################################################################################
# TODO Add Google API key here. Will need access to the Youtube API v3 in order for script to run.
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
NEWZ_BEAT_CHANNEL_ID = 'UCgoXKBqkLrBau7dVpXFhWDA'


# The chef subclass
################################################################################
class NewzBeatChef(YouTubeSushiChef):
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
        return get_video_ids(NEWZ_BEAT_CHANNEL_ID)

    def get_channel_metadata(self):
        return {
            'defaults': {
                'license': licenses.CC_BY_NCLicense("NewzBeat"),
                'high_resolution': True
            }
        }


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

# CLI
################################################################################
if __name__ == '__main__':
    # This code runs when sushichef.py is called from the command line
    chef = NewzBeatChef()
    chef.main()
