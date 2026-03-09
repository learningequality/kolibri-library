#!/usr/bin/env python
import os
import sys
sys.path.append(os.getcwd()) # Handle relative imports
from ricecooker.utils import downloader, html_writer
from ricecooker.chefs import SushiChef
from ricecooker.classes import nodes, files, questions, licenses
from ricecooker.config import LOGGER                        # Use logger to print messages
from ricecooker.exceptions import raise_for_invalid_channel
from le_utils.constants import licenses, exercises, content_kinds, file_formats, format_presets, languages


""" Additional imports """
###########################################################
from bs4 import BeautifulSoup
from client import Client

""" Run Constants"""
###########################################################

CHANNEL_NAME = "Overcoming Obstacles"              # Name of channel
CHANNEL_SOURCE_ID = "sushi-chef-overcoming-obstacles-en" # Channel's unique id
CHANNEL_DOMAIN = "jayoshih"         # Who is providing the content
CHANNEL_LANGUAGE = "en"      # Language of channel
CHANNEL_DESCRIPTION = None                                  # Description of the channel (optional)
CHANNEL_THUMBNAIL = None                                    # Local path or url to image file (optional)


""" Additional Constants """
###########################################################
BASE_URL = "https://www.overcomingobstacles.org"
CLIENT = Client("jordan@learningequality.org", "kolibri")
COPYRIGHT_HOLDER = "Community for Education Foundation"
LICENSE = licenses.ALL_RIGHTS_RESERVED
DOWNLOAD_DIRECTORY = "downloads"

if not os.path.exists(DOWNLOAD_DIRECTORY):
    os.makedirs(DOWNLOAD_DIRECTORY)

""" The chef class that takes care of uploading channel to the content curation server. """
class MyChef(SushiChef):

    channel_info = {                                   # Channel Metadata
        'CHANNEL_SOURCE_DOMAIN': CHANNEL_DOMAIN,       # Who is providing the content
        'CHANNEL_SOURCE_ID': CHANNEL_SOURCE_ID,        # Channel's unique id
        'CHANNEL_TITLE': CHANNEL_NAME,                 # Name of channel
        'CHANNEL_LANGUAGE': CHANNEL_LANGUAGE,          # Language of channel
        'CHANNEL_THUMBNAIL': CHANNEL_THUMBNAIL,      # Local path or url to image file (optional)
        'CHANNEL_DESCRIPTION': CHANNEL_DESCRIPTION,      # Description of the channel (optional)
    }


    """ Main scraping method """
    ###########################################################

    def construct_channel(self, *args, **kwargs):
        """ construct_channel: Creates ChannelNode and build topic tree
            Returns: ChannelNode
        """
        channel = self.get_channel(*args, **kwargs)   # Creates ChannelNode from data in self.channel_info

        CLIENT.login("{}/portal/auth/login".format(BASE_URL))

        scrape_source(channel)

        raise_for_invalid_channel(channel)            # Check for errors in channel construction

        return channel


""" Helper Methods """
###########################################################
def get_id(text):
    return ''.join([c for c in text.replace(' ', '-') if c.isalnum() or c == '-'])

def get_soup(url=""):
    url = url if url.startswith('http:') else "{}/{}".format(BASE_URL, url.lstrip('/'))
    response = CLIENT.get(url)
    return BeautifulSoup(response.content, 'html5lib')

def scrape_source(channel):
    LOGGER.info("Scraping Overcoming Obstacles at {}".format(BASE_URL))
    page = get_soup('portal')

    # Add curriculum topics
    for tab in page.find_all('li', {'class': 'tab-title'}):
        topic = nodes.TopicNode(get_id(tab.text), tab.text)
        LOGGER.info("    Processing {} (curriculum)".format(tab.text))
        channel.add_child(topic)

        curriculum_page = get_soup(tab.find('a')['href'])
        for column in curriculum_page.find_all('div', {'class': 'columns'}):
            column_topic = topic
            if column.find('h2'):
                source_id = "{}-{}".format(topic.source_id, get_id(column.find('h2').text))
                column_topic = nodes.TopicNode(source_id, column.find('h2').text)
                topic.add_child(column_topic)
            process_section(column, column_topic)

def process_section(column, topic):
    # Add subtopics
    for section in column.find_all('dl'):
        header = section.find('dt')
        LOGGER.info("        Processing {} (section)".format(header.text))
        source_id = "{}-{}".format(topic.source_id, get_id(header.text))
        subtopic = nodes.TopicNode(source_id, header.text)
        topic.add_child(subtopic)

        # Add resources
        for resource in section.find_all('dd'):
            subtopic.add_child(process_resource(resource))

def process_resource(resource):
    page = get_soup(resource.find('a')['data-reveal-ajax'])

    identifier = next(l for l in page.find_all('a') if l.get('data-id') and l.get('data-token'))
    source_id = "{}-{}".format(identifier['data-id'], identifier['data-token'])
    title = page.find('span', {'id': 'module-large-title'}).text.strip()

    LOGGER.info("            Processing {} (resource)".format(title))

    # Need to download while still using proper authentication
    filename = '{}/{}.pdf'.format(DOWNLOAD_DIRECTORY, title)
    if not os.path.isfile(filename):
        with open(filename, 'wb') as fout:
            fout.write(CLIENT.get(page.find('a', {'id': 'module-dl'})['href']).content)

    return nodes.DocumentNode(source_id, title, license=LICENSE, copyright_holder=COPYRIGHT_HOLDER,
        description=page.find('span', {'id': 'module-large-description'}).text.strip(),
        files=[files.DocumentFile(path=filename)]
    )

""" This code will run when the sushi chef is called from the command line. """
if __name__ == '__main__':

    chef = MyChef()
    chef.main()
