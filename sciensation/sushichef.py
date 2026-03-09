#!/usr/bin/env python
import os
import sys
from ricecooker.utils import downloader, html_writer, zip
from ricecooker.chefs import SushiChef
from ricecooker.classes import nodes, files, questions, licenses
from ricecooker.config import LOGGER              # Use LOGGER to print messages
from ricecooker.exceptions import raise_for_invalid_channel
from le_utils.constants import exercises, content_kinds, file_formats, format_presets, languages

import pandas
import re
from bs4 import BeautifulSoup
import shutil
# Run constants
################################################################################
CHANNEL_ID = "f189d7c505644311a4e62d9f3259e31b"             # UUID of channel
CHANNEL_NAME = "Sciensation"                           # Name of Kolibri channel
CHANNEL_SOURCE_ID = "Sciensation"                              # Unique ID for content source
CHANNEL_DOMAIN = "sciensation.org"                         # Who is providing the content
CHANNEL_LANGUAGE = "es"                                     # Language of channel
CHANNEL_DESCRIPTION = 'Ciênsação started in 2015, with the support of UNESCO Brasil, as an initiative to promote hands-on experiments at public schools in Brazil. Since then, volunteers have developed, tested, photographed and repeatedly revised more than 100 experiments. These experiments were then translated to Portuguese, Spanish and English, and published online, so that teachers in all of Latin America can benefit from this work.'                                  # Description of the channel (optional)
CHANNEL_THUMBNAIL = os.path.join('files', 'sciensation_logo.png')                                    # Local path or url to image file (optional)
CONTENT_ARCHIVE_VERSION = 1                                 # Increment this whenever you update downloaded content


# Additional constants
################################################################################
XLS = os.path.join('files', 'sciensation_metadata.xls')
XLS_SHEETS = {
    'en': os.path.join('files', 'sciensation_en.xls'),
    # 'es': os.path.join('files', 'sciensation_es.xls'),
    # 'pt': os.path.join('files', 'sciensation_pt.xls')
}
SUBJECTS = ['Biology', 'Physics', 'Chemistry', 'Geography', 'Maths']
EXPERIMENTS_FOLDER = os.path.join('chefdata', 'experiments')
TEMP_FOLDER = os.path.join('chefdata', 'tempfiles')
# The chef subclass
################################################################################
class SciensationChef(SushiChef):
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

    # Your chef subclass can override/extend the following method:
    # get_channel: to create ChannelNode manually instead of using channel_info
    # pre_run: to perform preliminary tasks, e.g., crawling and scraping website
    # __init__: if need to customize functionality or add command line arguments
    def construct_channel(self, *args, **kwargs):
        """
        Creates ChannelNode and build topic tree
        Args:
          - args: arguments passed in on the command line
          - kwargs: extra options passed in as key="value" pairs on the command line
            For example, add the command line option   lang="fr"  and the value
            "fr" will be passed along to `construct_channel` as kwargs['lang'].
        Returns: ChannelNode
        """
        channel = self.get_channel(*args, **kwargs)  # Create ChannelNode from data in self.channel_info
        # Channel structure: language --> subject --> experiments
        for lang_code, value in XLS_SHEETS.items():
            # lang_code = language code
            # value = link to xls sheet
            
            # read xlxs file using pandas
            xls_file = pandas.read_excel(value)
            print(lang_code)
            print(value)
            if lang_code == 'en':
                language = 'English'
            elif lang_code == 'es':
                language = 'Español'
            else:
                language = 'Português'
            topic_node = nodes.TopicNode(
                title = language,
                source_id = 'sciensation_{}'.format(language),
                author = 'Sciensation',
                provider = 'Sciensation',
                description = '{} experiements'.format(language),
                language = lang_code
            )
            # add subject nodes
            for subject in SUBJECTS:
                subject_node = nodes.TopicNode(
                    title = subject,
                    source_id = 'sciensation_{0}_{1}'.format(language, subject),
                    author = 'Sciensation',
                    provider = 'Sciensation',
                    description = '',
                    language = lang_code
                )
                
                # Add exercises to subject nodes
                experiment_dict = buildDict(xls_file)
                subject_node = add_experiments(subject, lang_code, subject_node, experiment_dict)

                topic_node.add_child(subject_node)

            channel.add_child(topic_node)
        return channel

def format_url(id, language_code):
    if language_code == 'en':
        return 'https://sciensation.org/hands-on_experiments/{}.html'.format(id)
    elif language_code == 'es':
        return 'https://ciensacion.org/experimento_manos_en_la_masa/{}.html'.format(id)
    else:
        return 'https://ciensacao.org/experimento_mao_na_massa/{}.html'.format(id)

def buildDict(xls):
    dict = {}
    for index, row in xls.iterrows():
        # filter out inactive exercises
        if row['Active'] == 0:
            continue
        row_id = 'e{}'.format(row['ID'])
        # split subject string into array
        subjects = row['Subject'].split(', ')
        dict[row_id] = subjects
    return dict

def add_experiments(subject, language, node, dict):
    for experiment_id, subject_arr in dict.items():
        # check if experiment is part of subject
        if subject in subject_arr:
            print('{0} is part of subject: {1}'.format(experiment_id, subject))
            node = scrape_page(experiment_id, language, node)
    return node


def scrape_page(exp_id, language, subject_node):
    # format to appropriate url depending on language
    my_downloader = downloader.ArchiveDownloader(EXPERIMENTS_FOLDER)
    url = format_url(exp_id, language)
    # page = downloader.archive_page(url, EXPERIMENTS_FOLDER)
    page = my_downloader.get_page(url, refresh = True)
    my_zip_dir = my_downloader.create_zip_dir_for_page(url)
    index_file = os.path.join(my_zip_dir, 'index.html')
    # entry = page['index_path']
    zip_path_entry = os.path.relpath(index_file, os.path.join('chefdata', 'experiments'))

    soup = BeautifulSoup(open(index_file, encoding = 'utf-8'), 'html.parser')

    # get title
    visible_SRAtitle = soup.find('h1', {'class': 'SRAtitle'})
    title = visible_SRAtitle.get_text(strip = True)

    # get tags
    visible_SRAtd = soup.findAll('div', {'class': 'SRAtd'})
    visible_tags = visible_SRAtd[-1]
    tags_arr = []
    for a_tags in visible_tags.findAll('a'):
        tag = a_tags.get_text(strip = True)
        # remove special characters
        tag = re.sub(r"[^a-zA-Z0-9]+", ' ', tag)
        # removing ending whitespace
        tag = tag.rstrip()
        tags_arr.append(tag)
    
    # remove navbar
    navbar = soup.find('nav')
    navbar.decompose()

    # remove footer
    footer = soup.find('footer')
    footer.decompose()

    # remove all hrefs
    for a_tag in soup.findAll('a'):
        del a_tag['href']
        # move all children of a tag to parent
        a_tag.replaceWithChildren()

    # write updated soup to html file
    soup_str = str(soup)
    # html_file = open(entry, 'w', encoding = 'utf-8')
    html_file = open(index_file, 'w', encoding = 'utf-8')
    html_file.write(soup_str)
    html_file.close()

    # zippath = zip.create_predictable_zip(EXPERIMENTS_FOLDER, zip_path_entry)
    zippath = zip.create_predictable_zip(my_zip_dir)
    # copy zippath to temp folder here if necessary
    shutil.copy(zippath, TEMP_FOLDER)
    html5_node = nodes.HTML5AppNode(
        source_id = '{0}_{1}'.format(language, url),
        files = [files.HTMLZipFile(zippath)],
        title = title,
        description = '',
        license = licenses.CC_BYLicense('Sciensation'),
        language = language,
        thumbnail = None,
        author = 'Sciensation',
        tags = tags_arr
    )
    subject_node.add_child(html5_node)
    return subject_node
# CLI
################################################################################
if __name__ == '__main__':
    # This code runs when sushichef.py is called from the command line
    chef = SciensationChef()
    chef.main()