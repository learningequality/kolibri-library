#!/usr/bin/env python
import argparse
from itertools import groupby
import json
import os
import re
import shutil
import sys
import tempfile

from bs4 import BeautifulSoup
import requests

# from le_utils.constants import content_kinds
from le_utils.constants import licenses
from le_utils import constants
from ricecooker.chefs import SushiChef
from ricecooker.classes import nodes, files
from ricecooker.classes.licenses import get_license
from ricecooker.exceptions import UnknownFileTypeError, raise_for_invalid_channel
from ricecooker.utils.caching import CacheForeverHeuristic, FileCache, CacheControlAdapter
from ricecooker.utils.zip import create_predictable_zip


# LOGGING SETTINGS
################################################################################
import logging
# logging.basicConfig(filename='logs/mitblossoms.log')
compact_fmt = '%(name)s\t%(message)s'
logging.basicConfig(level=logging.INFO, format=compact_fmt)
logging.getLogger("cachecontrol.controller").setLevel(logging.WARNING)
logging.getLogger("requests.packages").setLevel(logging.WARNING)
logging.getLogger("urllib3.connectionpool").setLevel(logging.WARNING)
# detaild_fmt = '%(asctime)s %(hostname)s %(name)s[%(process)d] %(levelname)s %(message)s'
logger = logging.getLogger('mitblossoms')



# MIT BLOSSOMS CHANNEL SETTINGS
################################################################################
CHANNEL_SOURCE_DOMAIN = 'blossoms.mit.edu'
CHANNEL_SOURCE_ID = 'mit_blossoms_v1.0b'
CHANNEL_TITLE = 'MIT Blossoms'
CHANNEL_THUMBNAIL = 'https://pk12.mit.edu/files/2016/02/MIT-Blossoms.png'
CHANNEL_LANGUAGE='en'
MIT_BLOSSOMS_LICENSE = get_license(licenses.CC_BY_NC_SA, copyright_holder='MIT Blossoms')
DATA_DIR = 'chefdata'
ZIP_FILES_TMP_DIR = os.path.join(DATA_DIR, 'zipfiles')
CONTENT_DIR = 'content'
BASE_URL = 'https://blossoms.mit.edu'
VIDEOS_BY_LANGUAGE_PATH = '/videos/by_language'
ALL_LANGUAGES = ['Arabic', 'English', 'Farsi', 'Hindi', 'Japanese', 'Kannada',
                 'Korean', 'Malay', 'Mandarin', 'Portuguese', 'Spanish', 'Urdu']
SELECTED_LANGUAGES = ALL_LANGUAGES   # download all languages
LANGUAGE_LOOKUP = {
    'Arabic': 'ar',
    'English': 'en',
    'Farsi': 'fa',
    'Hindi': 'hi',
    'Japanese': 'ja',
    'Kannada': 'kn',
    'Korean': 'ko',
    'Malay': 'ms',
    'Mandarin': 'zh',
    'Portuguese': 'pt',
    'Spanish': 'es',
    'Urdu': 'ur',
 }


# SOURCE_ID and TITLE CONVENTIONS
################################################################################
# 1. In order to identify `transcript`s and `teachers_doc`s belong to a given
#    video lesson, we prefix their titles with a slug of the lesson's title, e.g.,
#    "The Construction of ..: Written Transcript of this video lesson in Arabic"
TITLE_SLUG_LENGTH = 20
#
# 2. All the choices for the `source_id` and `title` attibutes of content nodes
#    are summarized in a global dictionary `BLOSSOMS_FMT` (see Legend below).
BLOSSOMS_FMT = {
    'topic': {
        'source_id': 'mit_blossoms_topic_{title}',
        'title': '{title}',
    },
    'cluster': {
        'source_id': 'mit_blossoms_cluster_{title}',
        'title': '{title}',
    },
    'lesson': {
        'source_id': '{node_id}',                              # e.g. "node-123"
        'title': '{title}',
    },
    'video': {
        'source_id': '{node_id}:{lang_variant}',
        'title': '{lang_variant}: {title}',
    },
    'transcript': {
        'source_id': '{node_id}:{file_name}',
        'title': '{slug}: {transcript_title}',
    },
    'additional_resources': {
        'source_id': '{node_id}:additional_resources',
        'title': 'Additional Resources for {title}',
    },
    'teachers_doc': {
        'source_id': '{node_id}:{file_name}',
        'title': '{slug}:{doc_title}',
    },
}
# Legend:
#  node_id = lesson.get_source_id()          e.g. "node-123"
#  title   = lesson.title                    e.g. "The Construction of Proteins"
#  slug    = title[:TITLE_SLUG_LENGTH]+'..'  e.g. "The Construction of .."
#  lang_variant                              e.g. "Arabic-English Subtitles"



# CACHE LOGIC
################################################################################
SESSION = requests.Session()
cache = FileCache('.webcache')
forever_adapter= CacheControlAdapter(heuristic=CacheForeverHeuristic(), cache=cache)
SESSION.mount('https://blossoms.mit.edu', forever_adapter)          # TODO: change this in final version
SESSION.mount('http://d1baxxa0joomi3.cloudfront.net', forever_adapter)
SESSION.mount('http://techtv.mit.edu', forever_adapter)



# PART 1: CRAWLING
################################################################################

def get_lang_paths():
    """
    Retrieve all video listings for each language.
    Retruns a list of tuples of the form:
        (lang, path)
    """
    resp = SESSION.get(BASE_URL+VIDEOS_BY_LANGUAGE_PATH)
    doc = BeautifulSoup(resp.content, 'html.parser')
    main_div = doc.find("div", {"id": "main"})
    videos_ul = main_div.find('div', {'class': 'item-list'}).find_next('ul')
    vudeos_lis = videos_ul.find_all('li')
    lang_paths = []
    for li in vudeos_lis:
        lang_paths.append((li.find('a').text.strip(), li.find('a')['href']))
    return lang_paths

def get_all_lessons_info(listing_url):
    """
    Retrieve all video lessons from a listing url.
    Returns a list of dicts:
        {   topic:
            title:
            url:           }
    """
    resp = SESSION.get(listing_url)
    doc = BeautifulSoup(resp.content, 'html.parser')
    main_div = doc.find('div', {'id': 'main'})
    view_content = main_div.find('div', {'class': 'view-content'})
    view_table = view_content.find('table')
    video_tds_raw = view_table.find_all('td')

    # skip empty <td>s (e.g. last td when there is an odd number of items)
    video_tds = []
    for video_td in video_tds_raw:
        title = video_td.find('div', {'class':"views-field-title"})
        if title is not None:
            video_tds.append(video_td)

    # extract useful info from each td
    video_lessons = []
    for video_td in video_tds:
        topic = video_td.find('div', {'class':"views-field-field-topic-value"}).find('h4').text
        title_div = video_td.find('div', {'class':"views-field-title"})
        lesson_path = title_div.find('a')['href']
        lesson_title = title_div.find('a').text

        lesson = {}
        lesson['topic'] = topic
        lesson['title'] = lesson_title
        lesson['url'] = BASE_URL + lesson_path

        video_lessons.append(lesson)

    return video_lessons

def group_lesson_by_topic(video_lessons):
    """
    Given a list of video lesson json objects,
    return a list of dicts, where each dict corresponds to videos for a given topic.
    """
    # 1. sort topics alphabetically
    video_lessons = sorted(video_lessons, key=lambda vl: vl['topic'])

    # 2. group videos by category
    topics_list = []
    for topic, group in groupby(video_lessons, lambda vl: vl['topic']):
        # 3. sort videos within group alphabetically (by title)
        topic_lessons = sorted(group, key=lambda vl: vl['title'])
        topics_list.append({'topic': topic,
                            'lessons': topic_lessons})
    return topics_list

def build_preliminary_tree(languages=None):
    """
    Crawl the MIT Blossoms website and produce a web_resource_tree.
    """
    lang_paths = get_lang_paths()

    if languages:
        selected_lang_paths = [p for p in lang_paths if p[0] in languages]
    else:
        selected_lang_paths = lang_paths

    # STAGE 1.1 OUTPUT: Topics and Lessons before adding the TopicClusters
    web_resource_tree = dict(
        __class__='MitBlossomsResourceTree',
        children=[],
    )

    for lang, path in selected_lang_paths:
        lang_node = {}
        lang_node['__class__'] = 'MitBlossomsLang'
        lang_node['lang'] = lang
        lang_node['children'] = []  # list of MitBlossomsTopic objects
        lang_url = BASE_URL + path
        lang_node['url'] = lang_url

        # Crawl lessons by language
        video_lessons = get_all_lessons_info(lang_url)
        topics_list = group_lesson_by_topic(video_lessons)

        for topic in topics_list:
            topic_node = {}
            topic_node['__class__'] = 'MitBlossomsTopic'
            topic_node['title'] = topic['topic']
            topic_node['children'] = []  # list of MitBlossomsVideoLessonResource objects

            for lesson in topic['lessons']:
                lesson_node = {}
                lesson_node['__class__'] = 'MitBlossomsVideoLessonResource'
                lesson_node['title'] = lesson['title']
                lesson_node['url'] = lesson['url']

                # save the lesson
                topic_node['children'].append(lesson_node)

            # save this topic
            lang_node['children'].append(topic_node)

        # save the lang
        web_resource_tree['children'].append(lang_node)
    return web_resource_tree

################################################################################

def retrieve_topic_clusters(lesson_url):
    """
    Retrieves topic clusters for a given video lesson.

    Returns a list of strings or None.
    """
    resp = SESSION.get(lesson_url)
    doc = BeautifulSoup(resp.content, 'html.parser')
    cluster_p = doc.find('p', {'class': 'cluster-lesson-page-display'})
    if cluster_p is None:
        return None
    else:
        cluster_names = [a.text for a in cluster_p.find_all('a')]
        return cluster_names

def get_or_create_cluster(parent, cluster_name):
    cluster_node = None
    for child in parent['children']:
        if child['__class__'] == 'MitBlossomsTopicCluster' and \
           child['title'] == cluster_name:
            cluster_node = child
            break
    if cluster_node is None:
        cluster_node = {}
        cluster_node['__class__'] = 'MitBlossomsTopicCluster'
        cluster_node['title'] = cluster_name
        cluster_node['children'] = []
        parent['children'].append(cluster_node)
    return cluster_node

def add_topic_cluster_membership(web_resource_tree):
    """
    Retrieve topic-cluster membership for each video and rewrite web_resource_tree
    """
    for lang_node in web_resource_tree['children']:
        for topic_node in lang_node['children']:
            logger.info('Processing topic ' + topic_node['title'])

            old_children = topic_node['children']
            topic_node['children'] = []

            for lesson_node in old_children:

                if 'title' not in lesson_node:
                    continue
                logger.info("Processing lesson " + lesson_node['title'])
                topic_clusters = retrieve_topic_clusters(lesson_node['url'])
                if topic_clusters is None:
                    topic_node['children'].append(lesson_node)
                else:
                    for cluster_name in topic_clusters:
                        cluster_node = get_or_create_cluster(topic_node, cluster_name)
                        cluster_node['children'].append(lesson_node)

            # order children so clusters come before lessons
            def clusters_first(node):
                if node['__class__'] == 'MitBlossomsTopicCluster':
                    return -1
                elif node['__class__'] == 'MitBlossomsVideoLessonResource':
                    return 10
                else:
                    return 11 # everything else later
            topic_node['children'] = sorted(topic_node['children'], key=clusters_first)

    return web_resource_tree


def crawling_part(args, options):
    """
    Main function for PART 1: CRAWLING.
    """
    web_resource_tree = build_preliminary_tree(languages=args['languages'])
    web_resource_tree = add_topic_cluster_membership(web_resource_tree)
    json_file_name = os.path.join(DATA_DIR, 'web_resource_tree.json')
    with open(json_file_name, 'w') as json_file:
        json.dump(web_resource_tree, json_file, indent=2)
    logger.info('Intermediate result stored in' + json_file_name)
    logger.info('Crawling part finished.\n')




# PART 2: SCRAPING HELPERS
################################################################################

def get_cloudfront_video_url(lang_video_url):
    """
    Returns the url of the actual mp4 file for a language variant.
    Returns None if no mp4 file is found.
    """
    # PART 1: Open the language specific video player page on MIT Blossoms
    resp1 = SESSION.get(lang_video_url)
    lang_video_doc = BeautifulSoup(resp1.content, 'html.parser')
    player_div = lang_video_doc.find('div', {'class':"video-embeddedplayer"})
    embed_url = player_div.find('iframe')['src']

    # PART 2: Open the iframe that contains the actual link to the mp4 file
    resp2 = SESSION.get(embed_url)
    embed_doc = BeautifulSoup(resp2.content, 'html.parser')
    player = embed_doc.find('div', {'class': 'video-player'})
    if player:
        video_url = player.find('source', {'type':'video/mp4'})['src']
        if video_url.startswith('//'):   # since CDN URLs don't include protocol
            video_url = 'http:' + video_url
        return video_url
    else:
        return None


class MitBlossomsVideoLessonResource(object):
    """
    Helper class with scrapting logic for MIT Blossoms video resources.
    """
    BASE_URL = 'https://blossoms.mit.edu'
    ALLOWED_EXTS_FOR_TEACHERS_DOCS = ['pdf']
    ALLOWED_EXTS_FOR_TRANSCRIPTS = ['pdf']

    def __init__(self, data):
        assert data['__class__'] == 'MitBlossomsVideoLessonResource'
        self.url = data['url']
        self.title = data['title']
        resp = SESSION.get(self.url)
        self.doc = BeautifulSoup(resp.content, 'html.parser')


    # METADATA #################################################################

    def get_source_id(self):
        node_div = self.doc.find('div', {'class': "node-lesson"})
        return node_div['id']

    def get_slug(self):
        return self.title[0:TITLE_SLUG_LENGTH] + '..'

    def get_thumbnail_url(self):
        thumb_div = self.doc.find('div', {'class': "lesson-thumbnail-block"})
        img_path = thumb_div.find('img')['src']
        return self.BASE_URL + img_path

    def get_video_summary(self):
        summary_div = self.doc.find('div', {'class':"lesson-summary-block"})
        if summary_div:
            return summary_div.get_text().strip()
        else:
            return None

    def get_teachers(self):
        teachers_div = self.doc.find('div', {'class':"lesson-teacher-info"})
        # in 98% of all videos, the author names appear in <strong> or <b>
        # in  2% this fails, so we'll fix this issue in the post-processing step
        name_strongs = teachers_div.find_all(['strong','b'])
        teachers_names = []
        for strong in name_strongs:
            if strong:
                # handle edge case where multiple teachers included in on <stong>
                teachers_names.extend([x.strip() for x in strong.text.split('\n')])
        if len(teachers_names) == 0:
            logger.warn("Couldn't find teacher names for " + self.get_source_id() + ' ' + self.url)
        return teachers_names

    def get_teachers_biography(self):
        pass

    def get_for_teachers(self):
        """
        Extra PDF with info for teachers.   # TODO: handle DOCX
        Returns a list of (file_name, file_url), where
          - file_name is the achor text (Document title)
          - file_url is the URL where the document is located
        """
        teachers_guide_div = self.doc.find('div', {'id':"lesson-detail-tab-teacher_guide"})
        block_divs = teachers_guide_div.find_all('div', {'class':"lesson-teacher-guide-block"})
        all_links = [div.find('a') for div in block_divs]
        resources = []
        for link in all_links:
            file_name = os.path.basename(link['href'])
            (base_name, ext) = os.path.splitext(file_name)
            if ext.lstrip('.').lower() in self.ALLOWED_EXTS_FOR_TEACHERS_DOCS:
                resource = {}
                resource['file_name'] = file_name
                resource['file_url'] = link['href']
                resource['title'] = re.sub(' \(PDF format\)', '', link.text)
                resources.append(resource)
        return resources

    def get_additional_resources_zip(self):
        """
        Extract the HTML + links of the Additional Resources lesson tab.
        Returns path to zip file with contents.
        """
        resources_div = self.doc.find('div', {'id':"lesson-detail-tab-resources"})
        inner_block_div = resources_div.find('div', {'class':"lesson-resources-block"})

        if inner_block_div is None:
            logger.warn('No Additional Resources for ' + self.url)
            return None

        # replace blue links with regular text
        all_links = inner_block_div.find_all('a')
        for link in all_links:
            anchor_text = link.get_text().strip()
            link.replaceWith(anchor_text)

        # create a temp directory to house the index.html and other files
        destpath = tempfile.mkdtemp(dir=ZIP_FILES_TMP_DIR)

        # create an index.html with the content from the "Additional Resources" tab
        basic_page_str = """
        <!DOCTYPE html>
        <html>
          <head>
            <meta charset="utf-8">
            <title></title>
          </head>
          <body>
          </body>
        </html>"""
        basic_page = BeautifulSoup(basic_page_str, "html.parser")
        body = basic_page.find('body')
        body.append(inner_block_div)
        with open(os.path.join(destpath, 'index.html'), 'w', encoding="utf8") as index_html:
            index_html.write(str(basic_page))
        # Note: none of the "Additional Resources" tabs include any images,
        #       i.e., inner_block_div.find_all("img") == []
        # turn the temp folder into a zip file
        zippath = create_predictable_zip(destpath)

        return zippath


    def get_transcripts(self):
        """
        Returns the link to PDF of transcript file for the vidoe (if available).
        """
        transcripts_div = self.doc.find('div', {'id':"lesson-detail-tab-transcript"})
        block_divs = transcripts_div.find_all('div', {'class':"lesson-transcript-block"})
        all_links = [div.find('a') for div in block_divs]
        transcripts = []
        for link in all_links:
            file_name = os.path.basename(link['href'])
            (base_name, ext) = os.path.splitext(file_name)
            if ext.lstrip('.').lower() in self.ALLOWED_EXTS_FOR_TRANSCRIPTS:
                transcript = {}
                transcript['file_name'] = file_name
                transcript['file_url'] = link['href']
                transcript['title'] = re.sub(' \(PDF format\)', '', link.text)
                transcripts.append(transcript)
        return transcripts



    # VIDEO RETRIEVAL LOGIC ####################################################

    def get_video_urls(self):
        """
        Retrieve video urls for then video embed links below the screenshot.

        Returns a list of tuples: (lang_variant, url).
        """
        videos_ul = self.doc.find('ul', {'class':"lesson-playvideo-block"})
        video_lis = videos_ul.find_all('li', {'class':"lesson-playvideo-item"})
        video_links = []
        for video_li in video_lis:
            video_link_div = video_li.find('div', {'class':"lesson-playvideo-contents"})
            if video_link_div is not None:
                video_link = video_link_div.find('a')
                video_links.append(video_link)
        lang_path_tuples = [(link.text.strip(), link['href']) for link in video_links]

        lang_url_tuples = []
        for lang_path_tuple in lang_path_tuples:
            lang_video_url = self.BASE_URL + lang_path_tuple[1]
            video_url = get_cloudfront_video_url(lang_video_url)
            if video_url:
                lang_url_tuples.append((lang_path_tuple[0], video_url))
            else:
                pass

        return lang_url_tuples

    def get_video_urls_alt(self):
        """
        Retrieve video urls for this lesson from the "Download Video" tab.
        NOTE: The approach of `get_video_urls` is more reliable because it seems
              some of the language variants do not appear in "Download Video" tab,
              e.g. https://blossoms.mit.edu/videos/lessons/tragedy_commons

        Returns a list of tuples: (lang_variant, url).
        """
        downloads_div = self.doc.find('div', {'id':"lesson-detail-tab-download"})
        videos_table = downloads_div.find('table', {'class':"lesson-downloadvideo-contents"})
        video_tds = videos_table.find_all('tr')
        lang_url_tuples = []
        for video_tr in video_tds:
            video_name_td = video_tr.find('td', {'class':"videolist-name"})
            if video_name_td:
                video_path = video_name_td.find('a')['href']
                video_url = self.BASE_URL + video_path
                video_lang = video_tr.find('td', {'class':"videolist-language"}).text.strip()
                if 'Subtitles' in video_lang and len(video_lang)%2 == 0:
                    # handle edge case where videos with subtitles appears twice
                    half_length = int(len(video_lang)/2)
                    first_half = video_lang[0:half_length]
                    second_half = video_lang[half_length:]
                    if first_half == second_half:
                        video_lang = first_half
                video_format = video_tr.find('td', {'class':"videolist-format"}).text.strip()
                if video_format == 'MPEG 4':
                    lang_url_tuples.append((video_lang, video_url))
        return lang_url_tuples

    def get_video_url_for_lang(self, lang):
        """
        Looks through video links for current lesson and finds the best-matching
        video for the the language `lang`.  Returns a tuple (lang_variant, url).
        """
        lang_url_tuples = self.get_video_urls()
        matchin_tuples = [tuple for tuple in lang_url_tuples if lang in tuple[0]]
        if not matchin_tuples:
            lang_url_tuples = self.get_video_urls_alt()
            matchin_tuples = [tuple for tuple in lang_url_tuples if lang in tuple[0]]

        def _is_more_specific(new, current, lang):
            """
            Returns true if `new` language variant is more specific that `current`
               lang  >  lang+' Voice-over'  >  lang+' Subtitles'
            """
            if current is None or new == lang:
                return True
            elif lang+' Voice-over' in new and lang+' Subtitles' in current:
                return True
            else:
                return False

        video_url_tuple = (None, None)  # e.g. ('English-Arabic subtitles', 'http:....')
        for lang_variant, url in matchin_tuples:
            if _is_more_specific(lang_variant, video_url_tuple[0], lang):
                video_url_tuple = (lang_variant, url)
        if video_url_tuple[1] is None:
            logger.debug('Lesson ' + self.url + ' no video for ' + lang + ' in ' + str(lang_url_tuples))

        return video_url_tuple



def _get_child_node_by_title(parent_node, title):
    """
    Looks through `parent_node`s children to see if a topic|cluster|lesson with
    the given title exists and returns the child_node, else returns None.
    """
    child_node = None
    for existing_child in parent_node['children']:
        if existing_child['title'] == title:
            child_node = existing_child
    return child_node


# Main beast
def _build_json_tree(parent_node, sourcetree, languages=None):
    # type: (dict, List[dict], str) -> None
    """
    Parse the web resource nodes given in `sourcetree` and add as children of `parent_node`.
    """
    EXPECTED_NODE_TYPES = ['MitBlossomsLang', 'MitBlossomsTopic', 'MitBlossomsTopicCluster',
                           'MitBlossomsVideoLessonResource']
    for source_node in sourcetree:
        kind = source_node['__class__']
        if kind not in EXPECTED_NODE_TYPES:
            raise NotImplementedError('Unexpected web resource node type encountered.')

        if kind == 'MitBlossomsLang':
            # For OPTION E we do not use the top-level split-by language. Instead,
            # we process the children of all languages together in a single topic tree
            source_tree_children = source_node.get("children", [])
            _build_json_tree(parent_node, source_tree_children, languages=languages)

        elif kind == 'MitBlossomsTopic':
            child_node = _get_child_node_by_title(parent_node, source_node['title'])
            if child_node is None:
                child_node = dict(
                    kind='TopicNode',
                    source_id=BLOSSOMS_FMT['topic']['source_id'].format(title=source_node['title']),
                    title=BLOSSOMS_FMT['topic']['title'].format(title=source_node['title']),
                    author='MIT Blossoms',
                    description='Video lessons about ' + source_node['title'],
                    thumbnail=source_node.get("thumbnail"),
                    children=[],
                )
                parent_node['children'].append(child_node)
                logger.info('Created new topic node titled ' + child_node['title'])
            source_tree_children = source_node.get("children", [])
            _build_json_tree(child_node, source_tree_children, languages=languages)

        elif kind == 'MitBlossomsTopicCluster':
            child_node = _get_child_node_by_title(parent_node, source_node['title'])
            if child_node is None:
                child_node = dict(
                    kind='TopicNode',
                    source_id=BLOSSOMS_FMT['cluster']['source_id'].format(title=source_node['title']),
                    title=BLOSSOMS_FMT['cluster']['title'].format(title=source_node['title']),
                    author='MIT Blossoms',
                    description='Video lessons from the cluster ' + source_node['title'],
                    thumbnail=source_node.get("thumbnail"),
                    children=[],
                )
                parent_node['children'].append(child_node)
                logger.info('Created new cluster node titled ' + child_node['title'])
            source_tree_children = source_node.get("children", [])
            _build_json_tree(child_node, source_tree_children, languages=languages)

        elif kind == 'MitBlossomsVideoLessonResource':
            child_node = _get_child_node_by_title(parent_node, source_node['title'])
            if child_node is not None: # This video lesson was already processed
                continue
            lesson = MitBlossomsVideoLessonResource(source_node)
            lesson_authors_joined = ','.join(lesson.get_teachers())
            lesson_folder = dict(
                kind='TopicNode',
                source_id=BLOSSOMS_FMT['lesson']['source_id'].format(
                    node_id=lesson.get_source_id()
                ),
                title=BLOSSOMS_FMT['lesson']['title'].format(title=lesson.title),
                author=lesson_authors_joined,
                description=lesson.get_video_summary(),
                thumbnail=lesson.get_thumbnail_url(),
                children=[],
            )
            parent_node['children'].append(lesson_folder)

            # 1. Add the `VideoNode`s
            for lang in languages:
                lang_variant, video_url = lesson.get_video_url_for_lang(lang)
                if video_url is None:
                    logger.debug('No video_url found for ' + lang + ' in ' + lesson.url)
                    continue
                source_id = BLOSSOMS_FMT['video']['source_id'].format(
                    node_id=lesson.get_source_id(),
                    lang_variant=lang_variant
                )
                video_grandchild = dict(
                    kind='VideoNode',
                    source_id=source_id,
                    title=BLOSSOMS_FMT['video']['title'].format(
                        lang_variant=lang_variant,
                        title=lesson.title
                    ),
                    author=lesson_authors_joined,
                    description=lesson.get_video_summary(),
                    language=constants.languages.getlang(LANGUAGE_LOOKUP[lang]).code, # test path with Language object's code
                    derive_thumbnail=True,
                    thumbnail=lesson.get_thumbnail_url(),
                )

                # Fix for https://github.com/learningequality/sushi-chef-mit-blossoms/issues/3
                # don't add video with same source_id if it already exists
                # TODO(ivan): figure out a more general way to pick which language version to keep
                # e.g. for https://blossoms.mit.edu/videos/lessons/plastics_and_covalent_chemical_bonds
                #      we should pick `ar` instead of `en`
                existing_videos = [n for n in lesson_folder['children'] if n['kind']=='VideoNode']
                exists = any([v['source_id']==source_id for v in existing_videos])
                if not exists:
                    lesson_folder['children'].append(video_grandchild)
                    video_file = dict(
                        file_type='VideoFile',
                        path=video_url,
                        ffmpeg_settings={"crf": 24},
                        language=LANGUAGE_LOOKUP[lang],  # test path with str code
                    )
                    video_grandchild['files'] = [video_file]

            # 2. Add the lesson transcript(s)
            video_transcripts = lesson.get_transcripts()
            if video_transcripts:
                video_transcripts_folder = dict(
                    kind='TopicNode',
                    source_id=lesson.url+'#lesson-detail-tab-transcript',
                    title='Transcripts',
                    author='MIT Blossoms',
                    description=None,
                    children=[],
                )
                lesson_folder['children'].append(video_transcripts_folder)
                for transcript in video_transcripts:
                    document_node = dict(
                        kind='DocumentNode',
                        source_id=BLOSSOMS_FMT['transcript']['source_id'].format(
                            node_id=lesson.get_source_id(),
                            file_name=transcript['file_name']
                        ),
                        title=BLOSSOMS_FMT['transcript']['title'].format(
                            slug=lesson.get_slug(),
                            transcript_title=transcript.get('title')
                        ),
                        author=lesson_authors_joined,
                        description=transcript.get('title'),
                        thumbnail=None,
                    )
                    video_transcripts_folder['children'].append(document_node)
                    document_file = dict(
                        file_type='DocumentFile',
                        path=transcript['file_url'],
                        # language=lang, # TODO   Ask how to use le_util.languages ???
                    )
                    document_node['files']=[document_file]

            # 3. Add "Additional Resources" content as HTML5app + ZIP file
            resources_zip_path = lesson.get_additional_resources_zip()
            if resources_zip_path:
                additional_resources_grandchild = dict(
                    kind='HTML5AppNode',
                    source_id=BLOSSOMS_FMT['additional_resources']['source_id'].format(
                        node_id = lesson.get_source_id()
                    ),
                    title=BLOSSOMS_FMT['additional_resources']['title'].format(
                        title=lesson.title
                    ),
                    author=None,
                    description="Additional resources and links.",
                )
                lesson_folder['children'].append(additional_resources_grandchild)
                html_zip_file = dict(
                    file_type='HTMLZipFile',
                    path=resources_zip_path,
                )
                additional_resources_grandchild['files'] = [html_zip_file]

            # 4. Add "For Teachers" resources
            teachers_docs = lesson.get_for_teachers()
            if teachers_docs:
                teachers_docs_folder = dict(
                    kind='TopicNode',
                    source_id=lesson.url+'#lesson-detail-tab-teacher_guide',
                    title='For Teachers',
                    author='MIT Blossoms',
                    description='Additional resources for teachers.',
                    children=[],
                )
                lesson_folder['children'].append(teachers_docs_folder)
                for resource in teachers_docs:
                    document_node = dict(
                        kind='DocumentNode',
                        source_id=BLOSSOMS_FMT['teachers_doc']['source_id'].format(
                            node_id=lesson.get_source_id(),
                            file_name=resource['file_name']
                        ),
                        title=BLOSSOMS_FMT['teachers_doc']['title'].format(
                            slug=lesson.get_slug(),
                            doc_title=resource.get('title')
                        ),
                        author=resource.get("author"),
                        description=resource.get('title'),
                        thumbnail=resource.get("thumbnail"),
                    )
                    teachers_docs_folder['children'].append(document_node)
                    document_file = dict(
                        file_type='DocumentFile',
                        path=resource['file_url'],
                        # language=lang, # TODO   Ask how to use le_util.languages ???
                    )
                    document_node['files']=[document_file]
            logger.info('Created new lesson node ' + lesson.title)
        else:
            logger.critical("Encountered an unknown content node format.")
            continue

    return parent_node


def scraping_part(args, options):
    """
    Main function for PART 2:
      - Reads result of crawl from DATA_DIR/web_resource_tree.json
      - Scrapes content from each video lesson
      - Writes ricecooker-ready json to DATA_DIR/ricecooker_json_tree.json
    If args['pruned'] is True, the tree is pruned to leave a few nodes for testing.
    """
    # Read in web_resource_tree.json
    web_resource_tree = None
    with open(os.path.join(DATA_DIR, 'web_resource_tree.json')) as json_file:
        web_resource_tree = json.load(json_file)
    assert web_resource_tree['__class__'] == 'MitBlossomsResourceTree'

    # For testing only: give the pruned test channel a different `source_id`
    if args['pruned']:
        source_id_suffix = '-pruned'
    else:
        source_id_suffix = ''

    # Ricecooker tree
    ricecooker_json_tree = dict(
        kind='ChannelNode',
        children=[],
    )
    _build_json_tree(ricecooker_json_tree, web_resource_tree['children'], languages=args['languages'])

    # Write out ricecooker_json_tree.json
    json_file_name = os.path.join(DATA_DIR, 'ricecooker_json_tree.json')
    with open(json_file_name, 'w') as json_file:
        json.dump(ricecooker_json_tree, json_file, indent=2)

    # Prune the content tree to leave only a few lessons (used for testing)
    if args['pruned']:
        original_tree_path = os.path.join(DATA_DIR, 'ricecooker_json_tree.json')
        full_tree_path = os.path.join(DATA_DIR, 'ricecooker_json_tree_full.json')
        pruned_tree_path = os.path.join(DATA_DIR, 'ricecooker_pruned_json_tree.json')
        shutil.copyfile(original_tree_path, full_tree_path)   # save a backup of the full tree
        prune_tree_for_testing()                              # produce pruned version
        shutil.move(pruned_tree_path, original_tree_path)     # replace full with pruned

    logger.info('Intermediate result stored in ' + json_file_name)
    logger.info('Scraping part finished.\n')



def _find_and_replace_in_node(node, match, update):
    """
    Update attributes of dict `node` from dict `update` if it matches the
    criteria in `match`.
    """
    # check if node matches criteria in `match`
    found = True
    for attr, pattern in match.items():
        if attr in node:
            m = re.search(pattern, node[attr])
            if m is None:
                found = False
                break
        else:
            found = False
            break

    # apply fixes
    if found:
        for key, val in update.items():
            logger.info('Replacing `{}` with `{}`'.format(node[key], val))
            node[key] = val

    # recurse on children if exist
    if 'children' in node:
        for child in node['children']:
            _find_and_replace_in_node(child, match, update)

def apply_json_tree_overrides():
    """
    Apply manual content fixes from `chefdata/json_tree_overrides.json`.
    """
    json_tree_filename = os.path.join(DATA_DIR, 'ricecooker_json_tree.json')
    json_tree = None
    with open(json_tree_filename) as json_file:
        json_tree = json.load(json_file)

    tree_overrides_filename = os.path.join(DATA_DIR, 'json_tree_overrides.json')
    with open(tree_overrides_filename) as overrides_file:
        tree_overrides = json.load(overrides_file)
        for fix in tree_overrides:
            match_criteria = fix['match']
            update_data = fix['update']
            _find_and_replace_in_node(json_tree, match_criteria, update_data)

    # Write out ricecooker_json_tree.json
    with open(json_tree_filename, 'w') as json_file:
        json.dump(json_tree, json_file, indent=2)



# HELPER FUNCTION FOR TESTING
################################################################################

def prune_tree_for_testing():
    ricecooker_json_tree = None
    with open(os.path.join(DATA_DIR,'ricecooker_json_tree.json')) as infile:
        ricecooker_json_tree = json.load(infile)

    pruned_tree = ricecooker_json_tree.copy()
    pruned_tree['children']=[]

    full_first_topic = ricecooker_json_tree['children'][0]
    pruned_first_topic = full_first_topic.copy()
    pruned_first_topic['children']=[]

    full_first_topic_cluster = full_first_topic['children'][0]
    full_third_topic_cluster = full_first_topic['children'][2]
    first_non_cluster_lesson = full_first_topic['children'][6]
    second_non_cluster_lesson = full_first_topic['children'][7]
    third_non_cluster_lesson = full_first_topic['children'][8]

    pruned_first_topic_cluster = full_first_topic_cluster.copy()
    pruned_first_topic_cluster['children']=[]
    pruned_second_topic_cluster = full_third_topic_cluster.copy()
    pruned_second_topic_cluster['children']=[]

    first_lesson_in_first_cluster = full_first_topic_cluster['children'][0]
    first_lesson_in_second_cluster = full_third_topic_cluster['children'][0]

    pruned_first_topic_cluster['children']=[first_lesson_in_first_cluster]
    pruned_second_topic_cluster['children']=[first_lesson_in_second_cluster]
    pruned_first_topic['children']=[
        pruned_first_topic_cluster,
        pruned_second_topic_cluster,
        first_non_cluster_lesson,
        second_non_cluster_lesson,
        third_non_cluster_lesson
    ]
    pruned_tree['children']=[pruned_first_topic]

    with open(os.path.join(DATA_DIR, 'ricecooker_pruned_json_tree.json'), 'w') as outfile:
        json.dump(pruned_tree, outfile, indent=2)



# PART 3
################################################################################

def _build_tree(parent_node, sourcetree):
    """
    Parse nodes given in `sourcetree` and add as children of `parent_node`.
    """
    EXPECTED_NODE_TYPES = ['TopicNode', 'VideoNode', 'DocumentNode', 'HTML5AppNode']

    for source_node in sourcetree:
        kind = source_node['kind']
        if kind not in EXPECTED_NODE_TYPES:
            logger.critical('Unexpected Node type found: ' + kind)
            raise NotImplementedError('Unexpected Node type found in channel json.')

        if kind == 'TopicNode':
            child_node = nodes.TopicNode(
                source_id=source_node["source_id"],
                title=source_node["title"],
                author=source_node.get("author"),
                description=source_node.get("description"),
                language=source_node.get("language"),
                thumbnail=source_node.get("thumbnail"),
            )
            parent_node.add_child(child_node)
            source_tree_children = source_node.get("children", [])
            _build_tree(child_node, source_tree_children)

        elif kind == 'VideoNode':
            child_node = nodes.VideoNode(
                source_id=source_node["source_id"],
                title=source_node["title"],
                license=MIT_BLOSSOMS_LICENSE,
                author=source_node.get("author"),
                description=source_node.get("description"),
                language=source_node.get("language"),
                derive_thumbnail=True,                     # video-specific data
                thumbnail=source_node.get('thumbnail'),
            )
            add_files(child_node, source_node.get("files") or [])
            parent_node.add_child(child_node)

        elif kind == 'DocumentNode':
            child_node = nodes.DocumentNode(
                source_id=source_node["source_id"],
                title=source_node["title"],
                license=MIT_BLOSSOMS_LICENSE,
                author=source_node.get("author"),
                description=source_node.get("description"),
                language=source_node.get("language"),
                thumbnail=source_node.get("thumbnail"),
            )
            add_files(child_node, source_node.get("files") or [])
            parent_node.add_child(child_node)

        elif kind == 'HTML5AppNode':
            child_node = nodes.HTML5AppNode(
                source_id=source_node["source_id"],
                title=source_node["title"],
                license=MIT_BLOSSOMS_LICENSE,
                author=source_node.get("author"),
                description=source_node.get("description"),
                language=source_node.get("language"),
                thumbnail=source_node.get("thumbnail"),
            )
            add_files(child_node, source_node.get("files") or [])
            parent_node.add_child(child_node)

        else:
            logger.critical("Encountered an unknown content node format.")
            continue

    return parent_node


def add_files(node, file_list):
    EXPECTED_FILE_TYPES = ['VideoFile', 'ThumbnailFile', 'HTMLZipFile', 'DocumentFile']

    for f in file_list:

        file_type = f.get('file_type')
        if file_type not in EXPECTED_FILE_TYPES:
            logger.critical(file_type)
            raise NotImplementedError('Unexpected File type found in channel json.')

        path = f.get('path')  # usually a URL, not a local path

        # handle different types of files
        if file_type == 'VideoFile':
            node.add_file(files.VideoFile(path=f['path'], ffmpeg_settings=f.get('ffmpeg_settings')))
        elif file_type == 'ThumbnailFile':
            node.add_file(files.ThumbnailFile(path=path))
        elif file_type == 'HTMLZipFile':
            node.add_file(files.HTMLZipFile(path=path, language=f.get('language')))
        elif file_type == 'DocumentFile':
            node.add_file(files.DocumentFile(path=path, language=f.get('language')))
        else:
            raise UnknownFileTypeError("Unrecognized file type '{0}'".format(f['path']))






# CHEF
################################################################################

class MitBlossomsSushiChef(SushiChef):
    """
    This class contains all the methods for the MIT Blossoms sushi chef.
    """
    channel_info = {
        'CHANNEL_TITLE': CHANNEL_TITLE,
        'CHANNEL_SOURCE_DOMAIN': CHANNEL_SOURCE_DOMAIN,
        'CHANNEL_SOURCE_ID': CHANNEL_SOURCE_ID,
        'CHANNEL_LANGUAGE': CHANNEL_LANGUAGE,
        'CHANNEL_THUMBNAIL': CHANNEL_THUMBNAIL,
        'CHANNEL_DESCRIPTION': None, # TODO(ivan)  add chennel description
    }

    def __init__(self, *args, **kwargs):
        """
        The MIT Blossoms Sushi Chef acceps the `--parts` command line arguement
        which controls which parts of the import pipeline should run.
          - `--parts crawlonly` build `chefdata/web_resource_tree.json` then exit
          - `--parts scrapeonly` build `chefdata/ricecooker_json_tree.json` then exit
          - `--parts main` run the entire pipeline (default)
        """
        super(MitBlossomsSushiChef, self).__init__(*args, **kwargs)

        self.arg_parser = argparse.ArgumentParser(
            description="Sushi chef for MIT Blossoms video lessons.",
            parents=[self.arg_parser]
        )
        self.arg_parser.add_argument('--languages', nargs='*', default=SELECTED_LANGUAGES,
                                     choices=ALL_LANGUAGES,
                                     help='List of languages to import')
        self.arg_parser.add_argument('--parts', nargs='*', default=['main'],
                                     choices=['crawlonly', 'scrapeonly', 'main',],
                                     help='Which parts of import pipeline to run')
        self.arg_parser.add_argument('--pruned', action='store_true',
                                     help='Prune tree for testing purposes.')



    def crawl(self, args, options):
        """
        Call function for PART 1: CRAWLING.
        """
        crawling_part(args, options)

    def scrape(self, args, options):
        """
        Call function for PART 2: SCRAPING.
        """
        scraping_part(args, options)
        apply_json_tree_overrides()

    def pre_run(self, args, options):
        """
        Run the preliminary parts:
          - creawl the blossoms.mit.org site and build a web resource tree
            (see result in `chefdata/web_resource_tree.json`)
          - scrape content and links from video lessons to build the json tree
            of the channel (see result in `chefdata/ricecooker_json_tree.json`)
          - perform manual content fixes for video lessons with non-standard markup
        """
        self.crawl(args, options)
        self.scrape(args, options)



    def construct_channel(self, **kwargs):
        channel = self.get_channel(**kwargs)
        # Load json tree data
        json_tree = None
        with open(os.path.join(DATA_DIR, 'ricecooker_json_tree.json')) as infile:
            json_tree = json.load(infile)
        _build_tree(channel, json_tree['children'])
        raise_for_invalid_channel(channel)
        return channel



# CLI
################################################################################

if __name__ == '__main__':
    """
    The command line argument parsing is handled by the chef class hierarchy:
    MitBlossomsSushiChef  --extends-->  SushiChef  --extends-->  BaseChef
    """
    mitchef = MitBlossomsSushiChef()

    # early parsing of args to extract --part information for partial runs
    args, options = mitchef.parse_args_and_options()
    logger.debug('In MitBlossomsSushiChef.__main__')
    logger.debug('args= ' + str(args))
    logger.debug('options= ' + str(options))

    # Dispatch based on --part specified
    for part in args['parts']:
        if part == 'crawlonly':
            mitchef.crawl(args, options)
        elif part == 'scrapeonly':
            mitchef.scrape(args, options)
        elif part == 'main':
            mitchef.main()

