#!/usr/bin/env python
# -*- coding: UTF-8 -*-
import os
import sys
from bs4 import BeautifulSoup
import subprocess
from ricecooker.utils import downloader, html_writer
from ricecooker.chefs import SushiChef
from ricecooker.classes import nodes, files, questions, licenses
from ricecooker.config import LOGGER              # Use LOGGER to print messages
from ricecooker.exceptions import raise_for_invalid_channel
from le_utils.constants import exercises, content_kinds, file_formats, format_presets, languages
import zipfile
from ceibal_scrapers import CeibalPageScraper
# import tempfile
import shutil

# Run constants
################################################################################
CHANNEL_NAME = "Ceibal"              # Name of channel
CHANNEL_SOURCE_ID = "sushi-chef-ceibal-es-test"    # Channel's unique id
CHANNEL_DOMAIN = "rea.ceibal.edu.uy"          # Who is providing the content
CHANNEL_LANGUAGE = "es"      # Language of channel
CHANNEL_DESCRIPTION = "El repositorio de Recursos educativos abiertos (REA) de Ceibal es una plataforma "\
                    "que alberga los REA construidos por los contenidistas de Ceibal "\
                    "y por la comunidad educativa; su misión no solamente es hacer de "\
                    "depósito, sino el ser un espacio para el intercambio de recursos y "\
                    "materiales pedagógicos facilitando la adaptación de estos y la interacción "\
                    "entre distintas comunidades de práctica."
CHANNEL_THUMBNAIL = "https://yt3.ggpht.com/a/AGF-l78Li2_W_X6fyV3lu6etxgfcFmb1xr73FCao6A=s900-mo-c-c0xffffffff-rj-k-no"

# Additional constants
################################################################################
BASE_URL = "https://rea.ceibal.edu.uy/"
DOWNLOAD_DIRECTORY = os.path.sep.join([os.path.dirname(os.path.realpath(__file__)), "downloads"])
if not os.path.exists(DOWNLOAD_DIRECTORY):
    os.makedirs(DOWNLOAD_DIRECTORY)

# VIDEO_DIRECTORY = os.path.sep.join([os.path.dirname(os.path.realpath(__file__)), "videos"])
# if not os.path.exists(VIDEO_DIRECTORY):
#     os.makedirs(VIDEO_DIRECTORY)

# DRIVE_DIRECTORY = os.path.sep.join([os.path.dirname(os.path.realpath(__file__)), "gdrive"])
# if not os.path.exists(DRIVE_DIRECTORY):
#     os.makedirs(DRIVE_DIRECTORY)

LICENSE_MAP = {
    'BY-NC': licenses.CC_BY_NCLicense,
    'BY-NC-SA':licenses.CC_BY_NC_SALicense,
    'BY': licenses.CC_BYLicense,
    'BY-SA': licenses.CC_BY_SALicense
}


# The chef subclass
################################################################################
class CeibalChef(SushiChef):
    """
    This class uploads the Ceibal channel to Kolibri Studio.
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
    # Your chef subclass can override/extend the following method:
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
        """
        channel = self.get_channel(*args, **kwargs)  # Create ChannelNode from data in self.channel_info

        scrape_channel(channel)

        raise_for_invalid_channel(channel)  # Check for errors in channel construction

        return channel

def get_source_id(text):
    return "{}{}".format(BASE_URL, text.lstrip('/').lower().replace(' ', '_'))


def scrape_channel(channel):
    # Read from Categorias dropdown menu
    page = BeautifulSoup(downloader.read(BASE_URL), 'html5lib')
    dropdown = page.find('a', {'id': 'btn-categorias'}).find_next_sibling('ul')

    # Go through dropdown and generate topics and subtopics
    for category_list in dropdown.find_all('li', {'class': 'has-children'}):

        # Parse categories
        for category in category_list.find_all('li', {'class': 'has-children'}):
            # Add this topic to channel when scraping entire channel
            category_name = category.find('a').text
            topic = nodes.TopicNode(title=category_name, source_id=get_source_id(category_name))
            channel.add_child(topic)
            LOGGER.info(topic.title)

            # Parse subcategories
            for subcategory in category.find_all('li'):
                if not subcategory.attrs.get('class') or 'go-back' not in subcategory.attrs['class']:
                    # Get rid of this check to scrape entire site
                    subcategory_name = subcategory.find('a').text
                    subcategory_link = subcategory.find('a')['href']
                    LOGGER.info('  {}'.format(subcategory_name))
                    subtopic = nodes.TopicNode(title=subcategory_name, source_id=get_source_id(subcategory_link))
                    topic.add_child(subtopic)

                    # Parse resources
                    scrape_subcategory(subcategory_link, subtopic)


def scrape_subcategory(link, topic):
    url = "{}{}".format(BASE_URL, link.lstrip("/"))
    resource_page = BeautifulSoup(downloader.read(url), 'html5lib')

    # Skip "All" category
    for resource_filter in resource_page.find('div', {'class': 'menu-filtro'}).find_all('a')[1:]:
        LOGGER.info('    {}'.format(resource_filter.text))
        source_id = get_source_id('{}/{}'.format(topic.title, resource_filter.text))
        filter_topic = nodes.TopicNode(title=resource_filter.text, source_id=source_id)
        scrape_resource_list(url + resource_filter['href'], filter_topic)
        topic.add_child(filter_topic)

def scrape_resource_list(url, topic):
    resource_list_page = BeautifulSoup(downloader.read(url), 'html5lib')

    # Go through pages, omitting Previous and Next buttons
    for page in range(len(resource_list_page.find_all('a', {'class': 'page-link'})[1:-1])):
        # Use numbers instead of url as the links on the site are also broken
        resource_list = BeautifulSoup(downloader.read("{}&page={}".format(url, page + 1)), 'html5lib')
        for resource in resource_list.find_all('a', {'class': 'card-link'}):
            resource_file = scrape_resource(resource['href'], topic)


def scrape_resource(url, topic):
    resource = BeautifulSoup(downloader.read(url), 'html5lib')
    LOGGER.info('      {}'.format(resource.find('h2').text))

    filepath = download_resource(resource.find('div', {'class': 'decargas'}).find('a')['href'])
    license = None
    author = ''
    for data_section in resource.find('div', {'class': 'datos_generales'}).find_all('h4'):
        if 'Licencia' in data_section.text:
            try:
                license = LICENSE_MAP[data_section.find_next_sibling('p').text](copyright_holder="Ceibal")
            except KeyError as e:
                LOGGER.error(str(e))
                license = licenses.CC_BYLicense
        elif 'Autor' in data_section.text:
            author = data_section.find_next_sibling('p').text
    if filepath:
        thumbnail = resource.find('div', {'class': 'img-recurso'}).find('img')['src']
        if thumbnail.endswith('.gif'):
            thumbnail = os.path.sep.join([DOWNLOAD_DIRECTORY, thumbnail.split('/')[-1].replace('.gif', '.png')])
            with open(thumbnail, 'wb') as fobj:
                fobj.write(downloader.read(resource.find('div', {'class': 'img-recurso'}).find('img')['src']))

        topic.add_child(nodes.HTML5AppNode(
            title=resource.find('h2').text,
            source_id=url,
            license=license,
            author=author,
            description=resource.find('form').find_all('p')[1].text,
            thumbnail=thumbnail,
            tags = [tag.text[:30] for tag in resource.find_all('a', {'class': 'tags'})],
            files=[files.HTMLZipFile(path=filepath)],
        ))

def download_resource(endpoint):
    try:
        url = '{}{}'.format(BASE_URL, endpoint.lstrip('/'))
        filename, ext = os.path.splitext(endpoint)
        filename = '{}.zip'.format(filename.lstrip('/').replace('/', '-'))
        write_to_path = CeibalPageScraper(url, locale='es').to_file(filename=filename, directory=DOWNLOAD_DIRECTORY)
        return write_to_path
    except Exception as e:
        LOGGER.error(str(e))


# CLI
################################################################################
import time
if __name__ == '__main__':
    start = time.time()
    # This code runs when sushichef.py is called from the command line
    chef = CeibalChef()
    chef.main()

    print("FINISHED: {}".format(time.time() - start))

