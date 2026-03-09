#!/usr/bin/env python
from os.path import splitext
from ricecooker.utils import downloader
from ricecooker.chefs import SushiChef
from ricecooker.classes import nodes, files
from ricecooker.config import LOGGER              # Use LOGGER to print messages
from ricecooker.exceptions import raise_for_invalid_channel
from le_utils.constants import licenses

""" Additional imports """
###########################################################
from bs4 import BeautifulSoup

# Run constants
################################################################################
CHANNEL_NAME = "Solar Spell"              # Name of channel
CHANNEL_SOURCE_ID = "sushi-chef-solar-spell-en"    # Channel's unique id
CHANNEL_DOMAIN = "solarspell.org"          # Who is providing the content
CHANNEL_LANGUAGE = "en"      # Language of channel
CHANNEL_DESCRIPTION = "A solar-powered digital library of scholastic educational content and general reference resources."
CHANNEL_THUMBNAIL = "thumbnail.jpg" # Local path or url to image file (optional)

# Additional constants
################################################################################
BASE_URL = 'http://pacificschoolserver.org/'

# License to be used for content under channel
CHANNEL_LICENSE = licenses.PUBLIC_DOMAIN


# The chef subclass
################################################################################
class MyChef(SushiChef):
    """
    This class uploads the Solar Spell channel to Kolibri Studio.
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

    def construct_channel(self, *args, **kwargs):
        """ construct_channel: Creates ChannelNode and build topic tree

            Solar Spell is organized with the following hierarchy(Sample):
                Creative Arts (source_id = dir-creative-arts)
                |--- Culinary Arts (source_id = dir-culinary-arts)
                |--- |--- Real Pasifik 2 introducing Chef Alexis Tahiapuhe of Tahiti (source_id = file-real pasifik 2 introducing chef lela bolobolo of fiji.mp4)
                |--- Pacific Islands Arts and Culture(source_id = dir_pacific_islands_arts_and_culture)
                |--- |--- Cook Islands National Cultural Policy 10 July 2017_final english (File)
                |--- Teaching Resources and Classroom Activities
                Environment (source_id = dir-environment)
                |--- Adapting to Climate Change
                |--- |--- Action Against Climate Change Tuvalu Water and climate change
                |--- Climate Change Info                
                |--- |--- Animated Pacific Island Climate Change Videos
                ...
            Returns: ChannelNode
        """
        LOGGER.info("Constructing channel from {}...".format(BASE_URL))
        channel = self.get_channel(*args, **kwargs)                         # Creates ChannelNode from data in self.channel_info
        LOGGER.info('   Writing {} Folder...'.format(CHANNEL_NAME))    
        endpoint = BASE_URL + "content/"
        scrape_content(endpoint, channel)
        raise_for_invalid_channel(channel)                                  # Check for errors in channel construction
        return channel

""" Helper Methods """
###########################################################

def read_source(url):
    html = downloader.read(url)    
    return BeautifulSoup(html, "html.parser")    

def replace_all(text, replacements):
    for condition, replacement in replacements.items():
        text = text.replace(condition, replacement)
    return text

def scrape_content(endpoint, channel, existingNode=None):
    replacements = {" ": "%20", "#": "%23"} 
    content = read_source(endpoint)
    attributes = content.find("tbody").find_all("td", "text-xs-left")

    for attribute in attributes:
        source_id = attribute.attrs["data-sort-value"]

        # Check if it is mp4 file
        if source_id.endswith(".mp4"):
            video_info = attribute.find("a")
            video_title, _ext = splitext(str(video_info.string))
            filter_video_link = video_info.attrs["href"][1:].replace(" ", "%20")
            video_link = BASE_URL + filter_video_link
            video_file = files.VideoFile(path=video_link)
            video_node = nodes.VideoNode(
                source_id=source_id,
                title=video_title,
                files=[video_file],
                license=CHANNEL_LICENSE
            )
            existingNode.add_child(video_node)

        # Check if it is a directory
        elif source_id.startswith("dir"):
            title = str(attribute.find("strong").string)
            topic_node = nodes.TopicNode(source_id=source_id, title=title)
            if existingNode:
                existingNode.add_child(topic_node)
            else:
                channel.add_child(topic_node)                            

            new_end_point = replace_all(title, replacements)
            new_end = endpoint + "{}/".format(new_end_point)
            scrape_content(new_end, channel, topic_node)
        else:
            LOGGER.info("Format of the file is not supported by the sushi chef : {}".format(source_id))


# CLI
################################################################################
if __name__ == '__main__':
    chef = MyChef()
    chef.main()
