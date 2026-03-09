#!/usr/bin/env python
import os
from ricecooker.chefs import YouTubeSushiChef
from ricecooker.classes import licenses


# Run constants
################################################################################
CHANNEL_ID = "85b42a40745f4e2392ed62e72d4dad6e"             # UUID of channel
CHANNEL_NAME = "OceanX"                           # Name of Kolibri channel
CHANNEL_SOURCE_ID = "oceanx-video-lessons"                              # Unique ID for content source
CHANNEL_DOMAIN = "oceanx.org"                         # Who is providing the content
CHANNEL_LANGUAGE = "en"                                     # Language of channel
CHANNEL_DESCRIPTION = "OceanX is a mission to explore the ocean and bring it back to the world. Join us as we build a global community deeply engaged with understanding, enjoying, and protecting our oceans. Through videos about ocean science, exploration, and discovery, experience real experiments with real scientists for learners of all ages."
CHANNEL_THUMBNAIL = "assets/oceanx.jpg"                                    # Local path or url to image file (optional)
CONTENT_ARCHIVE_VERSION = 1                                 # Increment this whenever you update downloaded content


# The chef subclass
################################################################################
class OceanXChef(YouTubeSushiChef):
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
        return [
            'z8el3syekK0',
            'GzR1CudYiuw',
            'C6cX0wQP5NA',
            'xV45VkZrZNI',
            'lwp3pCoyYMU',
            'pBSZ7OVNKfU'
        ]

    def get_channel_metadata(self):
        return {
            'defaults': {
                'license': licenses.SpecialPermissionsLicense(copyright_holder="OceanX", description="Footage supplied Courtesy of OceanX for use in the Kolibri Learning Platform."),
                'high_resolution': True
            }
        }


# CLI
################################################################################
if __name__ == '__main__':
    # This code runs when sushichef.py is called from the command line
    chef = OceanXChef()
    chef.main()
