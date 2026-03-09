#!/usr/bin/env python

import json
import os
import sys
import tempfile
from urllib.parse import urlparse

from bs4 import BeautifulSoup
import requests

from ricecooker.utils import downloader, html_writer
from ricecooker.chefs import SushiChef
from ricecooker.classes import nodes, files, questions, licenses
from ricecooker.config import LOGGER              # Use LOGGER to print messages
from ricecooker.exceptions import raise_for_invalid_channel
from ricecooker.utils.downloader import download_static_assets
from ricecooker.utils.zip import create_predictable_zip
from le_utils.constants import exercises, content_kinds, file_formats, format_presets, languages


# Run constants
################################################################################
CHANNEL_NAME = "Concord Consortium Science Simulations"              # Name of channel
CHANNEL_SOURCE_ID = "sushi-chef-concord-consortium"    # Channel's unique id
CHANNEL_DOMAIN = "learn.concord.org"          # Who is providing the content
CHANNEL_LANGUAGE = "en"      # Language of channel
CHANNEL_DESCRIPTION = None                                  # Description of the channel (optional)
CHANNEL_THUMBNAIL = None                                    # Local path or url to image file (optional)

# Additional constants
################################################################################



# The chef subclass
################################################################################
class MyChef(SushiChef):
    """
    This class uploads the Concord Consortium Science Simulations channel to Kolibri Studio.
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
        """
        channel = self.get_channel(*args, **kwargs)  # Create ChannelNode from data in self.channel_info

        api_search_url = 'https://learn.concord.org/api/v1/search/search?search_term=&sort_order=Alphabetical&material_types%5B%5D=Investigation&material_types%5B%5D=Activity&material_types%5B%5D=Interactive&include_official=1&investigation_page=1&activity_page=1&interactive_page=1&per_page=1000'
        models = get_all_resources(api_search_url)['models'] # TODO activities and sequences

        preview_urls = list(map(lambda x: x['preview_url'], models))
        resolved_urls = list(map(lambda x: requests.get(x).url, preview_urls))
        parsed_urls = list(map(lambda x: urlparse(x), resolved_urls))

        # Narrow down to just embeddable models for now # TODO all models, not just embeddable-based
        # Filter models and parsed_urls together so indices stay aligned
        embeddable_pairs = [(m, u) for m, u in zip(models, parsed_urls) if u.path == '/embeddable.html']
        embeddable_models = [pair[0] for pair in embeddable_pairs]
        embeddable_parsed_urls = [pair[1] for pair in embeddable_pairs]
        embeddable_base_urls = list(map(lambda x: x.scheme + '://' + x.netloc, embeddable_parsed_urls))
        embeddable_fragments = list(map(lambda x: x.fragment, embeddable_parsed_urls))

        # Get randomly-named temp dir to hold all the soup dirs for this run of the script
        temp_dir = get_temp_dir(parent_dir='temp')
        print('temp dir:', temp_dir)

        soups = [get_soup(e.geturl()) for e in embeddable_parsed_urls]
        # Download assets for each embeddable-based model into own soup dir # TODO all models, not just embeddable-based
        for i, soup in enumerate(soups):
            soup_dir = temp_dir + os.sep + 'soup_' + str(i).rjust(3, '0')
            os.makedirs(soup_dir)

            print('\nDOWNLOADING STATIC ASSETS FOR SOUP', i)
            print('embeddable:', embeddable_parsed_urls[i].geturl())

            doc = quietly(download_static_assets, soup, soup_dir, embeddable_base_urls[i],
                    url_blacklist=['analytics.js']) # TODO add ga.js to blacklist

            # This file must be named index.html for Kolibri studio upload to work
            with open(soup_dir + os.sep + 'index.html', 'w') as f:
                fragment = embeddable_parsed_urls[i].fragment
                edited_doc_str = str(doc).replace('document.location.hash', "'#" + fragment + "'")
                f.write(edited_doc_str)

            # Save fragment-url json responses
            embeddable_fragment = embeddable_fragments[i]
            download_dir = soup_dir + os.sep + os.path.dirname(embeddable_fragment)
            filename = os.path.basename(embeddable_fragment)

            fragment_url = embeddable_base_urls[i] + os.sep + embeddable_fragment
            fragment_json = requests.get(fragment_url).json()

            os.makedirs(download_dir)
            with open(download_dir + os.sep + filename, 'w') as f:
                f.write(json.dumps(fragment_json))

            if fragment_json.get('redirect'):
                print('REDIRECT found')
                # TODO: Deal with redirects

            relative_asset_paths = get_asset_paths_from_json(fragment_json)
            for ap in relative_asset_paths:
                print('JSON asset path:', ap)
                asset_url = embeddable_base_urls[i] + os.sep + ap
                asset_download_dir = soup_dir + os.sep + os.path.dirname(ap)
                asset_filename = os.path.basename(ap)
                download(asset_url, asset_download_dir + os.sep + asset_filename)

            zip_path = create_predictable_zip(soup_dir)

            # topic_node_title = fragment_json.get('title', 'topic_title')
            topic_node_title = fragment_json.get('title', 'follow redirect to get topic title') # TODO follow fragment_json redirects to get title
            topic_node_source_id = 'model/' + str(embeddable_models[i]['id']) # str() in case it's an array with multiple 'about's
            topic_node = nodes.TopicNode(title=topic_node_title, source_id=topic_node_source_id)
            channel.add_child(topic_node)

            app_node_source_id = 'embeddable/' + os.path.splitext(os.path.basename(embeddable_fragment))[0]
            app_node_title = fragment_json.get('title', 'follow redirect to get app title') # TODO follow fragment_json redirects to get title
            app_node_description = str(fragment_json.get('about', 'follow redirect to get app description')) # str() in case it's an array with multiple 'about's # TODO deal with arrays # TODO follow fragment_json redirects to get title
            license = get_model_license(embeddable_models[i])
            topic_node.add_child(nodes.HTML5AppNode(
                source_id=app_node_source_id,
                title=app_node_title,
                description=app_node_description,
                license=licenses.PublicDomainLicense(copyright_holder=license),
                # thumbnail=thumbnail,
                files=[files.HTMLZipFile(zip_path)],
                language='en',
            ))

        raise_for_invalid_channel(channel)  # Check for errors in channel construction

        return channel


def get_asset_paths_from_json(json):
    asset_paths = []

    for model in json.get('models', []):
        if model.get('url'):
            asset_paths.append(model['url'])

    if json.get('i18nMetadata'):
        asset_paths.append(json['i18nMetadata'])

    # TODO: metadata and locale data, svgs?

    return asset_paths


def download(url, download_path):
    """ Expecting just JSON files (for now) """
    response = requests.get(url)
    if not response.ok:
        print('FAILED TO DOWNLOAD, status_code:', response.status_code)
        print('url:', url)
        return
    content_type = response.headers['content-type']
    if not content_type.startswith('application/json'):
        print('FAILED TO DOWNLOAD, wrong content-type:', content_type)
        print('url:', url)
        return

    os.makedirs(os.path.dirname(download_path), exist_ok=True)
    with open(download_path, 'w') as f:
        f.write(json.dumps(response.json()))
    # TODO: deal with other file types if needed
    return


def quietly(func, *args, **kwargs):
    stdout = sys.stdout
    sys.stdout = open(os.devnull, 'w')
    returnValue = func(*args, **kwargs)
    sys.stdout.close()
    sys.stdout = stdout
    return returnValue


def get_model_license(model):
    try:
        return model.get('license_info', {}).get('code', 'unknown_license')
    except Exception:
        return 'unknown_license'


def get_temp_dir(parent_dir):
    os.makedirs(parent_dir, exist_ok=True)
    temp_dir_prefix = os.getcwd() + os.sep + parent_dir + os.sep
    temp_dir = tempfile.mkdtemp(prefix=temp_dir_prefix)
    return temp_dir


def get_all_resources(api_search_url):
    api_response = requests.get(api_search_url)
    all_resources = json.loads(api_response.text)

    all_resources_new_format = {
        'activities': [],
        'models': [],
        'sequences': []
    }

    for result in all_resources['results']:
        if result['type'] == 'interactives':
            all_resources_new_format['models'] = result['materials']
        if result['type'] == 'investigations':
            all_resources_new_format['sequences'] = result['materials']
        if result['type'] == 'activities':
            all_resources_new_format['activities'] = result['materials']

    return all_resources_new_format


def get_soup(url):
    response = requests.get(url)
    response.encoding = 'utf-8'
    soup = BeautifulSoup(response.text, 'html5lib')
    return soup


# CLI
################################################################################
if __name__ == '__main__':
    # This code runs when sushichef.py is called from the command line
    chef = MyChef()
    chef.main()
