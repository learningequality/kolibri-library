#!/usr/bin/env python

"""
Sushi Chef for https://k12.thoughtfullearning.com
"""

from collections import defaultdict
import html
import os
import re
import requests
import tempfile
import time
from urllib.parse import urlparse, parse_qs
import uuid

from bs4 import BeautifulSoup
import youtube_dl

import le_utils.constants
from ricecooker.chefs import SushiChef
from ricecooker.classes import nodes, files, licenses
from ricecooker.utils.caching import CacheForeverHeuristic, FileCache, CacheControlAdapter, InvalidatingCacheControlAdapter
from ricecooker.utils.browser import preview_in_browser
from ricecooker.utils.html import download_file, WebDriver
from ricecooker.utils.zip import create_predictable_zip
from ricecooker.utils.downloader import download_static_assets
import selenium.webdriver.support.ui as selenium_ui
from distutils.dir_util import copy_tree


sess = requests.Session()
cache = FileCache('.webcache')
forever_adapter = CacheControlAdapter(heuristic=CacheForeverHeuristic(), cache=cache)

ydl = youtube_dl.YoutubeDL({
    'quiet': True,
    'no_warnings': True,
    'writesubtitles': True,
    'allsubtitles': True,
})

sess.mount('https://k12.thoughtfullearning.com', forever_adapter)
sess.mount('http://fonts.googleapis.com', forever_adapter)
sess.mount('https://apis.google.com', forever_adapter)
sess.mount('http://ajax.googleapis.com', forever_adapter)


headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 6.1; WOW64; rv:20.0) Gecko/20100101 Firefox/20.0",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive"
}


class ThoughtfulLearningChef(SushiChef):
    """
    The chef class that takes care of uploading channel to the content curation server.

    We'll call its `main()` method from the command line script.
    """
    channel_info = {
        'CHANNEL_SOURCE_DOMAIN': "k12.thoughtfullearning.com",
        'CHANNEL_SOURCE_ID': "thoughtful-learning",
        'CHANNEL_TITLE': "Thoughtful Learning",
        'CHANNEL_THUMBNAIL': "thumbnail.png",
        'CHANNEL_DESCRIPTION': "Learning resources on Language Arts, 21st Century Learning, and Social-Emotional Learning.",
    }

    def construct_channel(self, **kwargs):
        """
        Create ChannelNode and build topic tree.
        """
        # create channel
        channel_info = self.channel_info
        channel = nodes.ChannelNode(
            source_domain = channel_info['CHANNEL_SOURCE_DOMAIN'],
            source_id = channel_info['CHANNEL_SOURCE_ID'],
            title = channel_info['CHANNEL_TITLE'],
            thumbnail = channel_info.get('CHANNEL_THUMBNAIL'),
            description = channel_info.get('CHANNEL_DESCRIPTION'),
            language = "en",
        )

        print()
        print("-" * 80)
        print("Downloading all minilesson")
        channel.add_child(download_all_minilessons())

        print()
        print("-" * 80)
        print("Downloading all student models")
        channel.add_child(download_all_student_models())

        print()
        print("-" * 80)
        print("Downloading all writing topics")
        channel.add_child(download_all_writing_topics())

        print()
        print("-" * 80)
        print("Downloading all writing assessments")
        channel.add_child(download_all_writing_assessments())

        return channel


################################################################################
# Minilessons


minilesson_thumbnail = "https://k12.thoughtfullearning.com/sites/k12/files/images/minilessonResources.png"


def download_all_minilessons():
    topic_node = nodes.TopicNode(
        source_id="minilesson",
        title="Minilessons",
        language="en",
        thumbnail=minilesson_thumbnail,
        description="Do you want quick lessons that teach concepts or skills? Each 10-15 minute minilesson presents a concept and engages students in an activity.",
    )

    doc = get_parsed_html_from_url(
            'https://k12.thoughtfullearning.com/resources/minilessons')
    for pane in doc.select('.pane-views-panes'):
        title = pane.select_one('.view-header').text.strip()
        category_node = nodes.TopicNode(source_id=title, title=title, language="en")
        print("Downloading minilesson category %s" % title)
        download_minilesson_category(category_node, pane)
        topic_node.add_child(category_node)

    return topic_node


def download_minilesson_category(category_node, category_doc):
    scraped_urls = set()

    for row in category_doc.select('.views-row'):
        screenshot = row.select_one('.views-field-field-minilesson-screenshot img')
        if screenshot:
            thumbnail = screenshot['src']
        else:
            thumbnail = row.select_one('.views-field-field-minilesson-video img')['src']

        title = row.select_one('.views-field-title').text.strip()

        url = make_fully_qualified_url(row.select_one('.views-field-title a')['href'])
        if url in scraped_urls:
            print('url %s is repeated', url)
            continue
        scraped_urls.add(url)

        description = row.select_one('.views-field-field-minilesson-summary').text.strip()
        print("    Downloading minilesson %s from %s" % (title, url))
        download_content_node(category_node, url, title, thumbnail, description)


################################################################################
# Student models


student_model_thumbnail = "https://k12.thoughtfullearning.com/sites/k12/files/images/studentModelResources.png"


def download_all_student_models():
    topic_node = nodes.TopicNode(
        source_id="student-models",
        title="Student Models",
        language="en",
        thumbnail=student_model_thumbnail,
        description="When you need an example written by a student, check out our vast collection of free student models.",
    )

    doc = get_parsed_html_from_url(
            'https://k12.thoughtfullearning.com/resources/studentmodels')
    for level in doc.select('.view-content .view-grouping'):
        title = level.select_one('.view-grouping-header').contents[0].strip()
        level_node = nodes.TopicNode(source_id=title, title=title, language="en")
        print("Downloading student model level: %s" % title)
        download_student_model_level(level_node, level.select_one('.view-grouping-content'))
        topic_node.add_child(level_node)

    return topic_node


def download_student_model_level(level_node, level_doc):
    for category in level_doc.select('.item-list'):
        title = category.select_one('h3').text.strip()
        category_node = nodes.TopicNode(
            source_id="%s|%s" % (level_node.source_id, title),
            title=title,
            language="en",
            thumbnail=student_model_thumbnail,
        )
        print("    Downloading student model category: %s" % title)
        download_student_model_category(category_node, category)
        level_node.add_child(category_node)


def download_student_model_category(category_node, category_doc):
    for article in category_doc.select('ul li'):
        title = article.select_one('.views-field-title').text.strip()
        form = article.select_one('.views-field-field-form').text.strip()
        combined_title = "%s (%s)" % (title, form)
        url = make_fully_qualified_url(article.select_one('.views-field-title a')['href'])
        print("        Downloading student model article: %s" % combined_title)
        download_content_node(category_node, url, combined_title, student_model_thumbnail)


################################################################################
# Writing topics


writing_topic_thumbnail = "https://k12.thoughtfullearning.com/sites/k12/files/images/writingTopicResources.png"


def download_all_writing_topics():
    topic_node = nodes.TopicNode(
        source_id="writing-topic",
        title="Writing Topics",
        language="en",
        thumbnail=writing_topic_thumbnail,
        description=("Do you want to inspire your students to write great"
            " narratives, essays, and reports? Check out these grade-specific"
            " writing topics organized by mode (explanatory, creative, and so on)."),
    )

    doc = get_parsed_html_from_url(
            'https://k12.thoughtfullearning.com/resources/writingtopics')
    for level in doc.select('.view-content .view-grouping'):
        title = level.select_one('.view-grouping-header').contents[0].strip()
        level_node = nodes.TopicNode(source_id=title, title=title, language="en")
        print("Downloading writing topic level: %s" % title)
        download_writing_topic_level(level_node, level.select_one('.view-grouping-content'))
        topic_node.add_child(level_node)

    return topic_node


def download_writing_topic_level(level_node, level_doc):
    for category in level_doc.select('.item-list'):
        title = category.select_one('h3').text.strip()
        print("    Downloading writing topic category: %s" % title)
        node = download_writing_topic_category(category, title, level_node.source_id)
        level_node.add_child(node)


def download_writing_topic_category(category_doc, title, level_id):
    destination = tempfile.mkdtemp()

    # Download a font
    font_url = make_fully_qualified_url(
            '//fonts.googleapis.com/css?family=Roboto:400,300,300italic,400italic,700,700italic')
    download_file(font_url, destination, request_fn=make_request, filename='roboto.css')

    # Write out the HTML source, based on CSS formatting from
    # https://k12.thoughtfullearning.com/resources/writingtopics

    topics = (("<li>%s</li>" % topic.text) for topic in category_doc.select('.views-row'))
    html_source = """
        <!DOCTYPE html>
        <head>
            <link href='roboto.css' rel='stylesheet' type='text/css'>
            <style>
                ul {
                    margin: 0 0 0 40px;
                    padding: 0;
                }
                li {
                    font-family: "Roboto", sans-serif;
                    font-weight: 300;
                    font-size: 19.2px;
                    line-height: 24.96px;
                    color: #202020;
                    margin-top: 10px;
                }
            </style>
        </head>
        <body>
            <ul>%s</ul>
        </body>
    """ % ''.join(topics)

    with open(os.path.join(destination, "index.html"), "w") as f:
        f.write(html_source)

    print("    ... downloaded to %s" % destination)
    #preview_in_browser(destination)

    zip_path = create_predictable_zip(destination)
    return nodes.HTML5AppNode(
        source_id="%s|%s" % (level_id, title),
        title=truncate_metadata(title),
        license=licenses.CC_BY_NC_SALicense(
            copyright_holder=truncate_metadata('Thoughtful Learning')),
        files=[files.HTMLZipFile(zip_path)],
        language="en",
        thumbnail=writing_topic_thumbnail,
    )


################################################################################
# Writing assessments


writing_assessment_thumbnail = "https://k12.thoughtfullearning.com/sites/k12/files/images/assessmentModelResources.png"


def download_all_writing_assessments():
    topic_node = nodes.TopicNode(
        source_id="writing-assessment",
        title="Writing Assessments",
        language="en",
        thumbnail=writing_assessment_thumbnail,
        description="When you want students to understand how writing is graded, turn to our vast selection of assessment examples. You'll find elementary and middle school models in all of the major modes of writing, along with rubrics that assess each example as \"Strong,\" \"Good,\" \"Okay,\" or \"Poor.\"",
    )

    doc = get_parsed_html_from_url(
            'https://k12.thoughtfullearning.com/resources/writingassessment')
    for grade in doc.select('.view-writing-assessment-silo'):
        title = grade.select_one('.view-grouping-header').contents[0].strip()
        grade_node = nodes.TopicNode(source_id=title, title=title, language="en")
        print("Downloading writing assessment grade: %s" % title)
        download_writing_assessment_grade(grade_node, grade.select_one('.view-content'))
        topic_node.add_child(grade_node)

    return topic_node


def download_writing_assessment_grade(grade_node, grade_doc):
    for category in grade_doc.select('.item-list'):
        title = category.select_one('h3').text.strip()
        category_node = nodes.TopicNode(
            source_id="%s|%s" % (grade_node.source_id, title),
            title=title,
            language="en",
            thumbnail=writing_assessment_thumbnail,
        )
        print("    Downloading writing assessment category: %s" % title)
        download_writing_assessment_category(category_node, category)
        grade_node.add_child(category_node)


def download_writing_assessment_category(category_node, category_doc):
    for article in category_doc.select('ul li .views-field'):
        title = article.select_one('a').contents[0].strip()
        form = article.select_one('.assessmentModelListForm').text.strip()
        rating = article.select_one('.assessmentModelListRating').text.strip()
        combined_title = "%s: %s (%s)" % (form, title, rating)
        url = make_fully_qualified_url(article.select_one('a')['href'])
        print("        Downloading writing assessment: %s" % combined_title)
        download_content_node(category_node, url, combined_title, writing_assessment_thumbnail)


################################################################################
# General helpers


def download_content_node(category_node, url, title, thumbnail=None, description=None):
    doc = get_parsed_html_from_url(url)

    destination = tempfile.mkdtemp()
    doc = download_static_assets(doc, destination,
            'https://k12.thoughtfullearning.com', request_fn=make_request,
            url_blacklist=url_blacklist)

    remove_node(doc, '#header')
    remove_node(doc, '.subMenuBarContainer')
    remove_node(doc, '.breadbookmarkcontainer')
    remove_node(doc, '.resourcePageTypeTitle')
    remove_node(doc, '.sharethis-wrapper')
    remove_node(doc, '.ccBlock')
    remove_node(doc, '#block-views-resource-info-block-block-1')
    remove_node(doc, '#block-views-resource-info-block-block-1')
    remove_node(doc, '#block-views-resource-info-block-block')
    remove_node(doc, '.productSuggestionContainer')
    remove_node(doc, 'footer')

    # For minilessons
    remove_node(doc, '.field-name-field-minilesson-downloadables')

    # For writing assessments
    remove_node(doc, '.assessmentTGLink')
    remove_node(doc, '.assessmentModelRubrics')
    remove_node(doc, '.view-display-id-attachment_1')

    # Write out the HTML source.
    with open(os.path.join(destination, "index.html"), "w") as f:
        f.write(str(doc))

    print("    ... downloaded to %s" % destination)
    #preview_in_browser(destination)

    thumbnail_path = None
    if thumbnail:
        # Manually download the thumbnail and use it so we can lowercase the
        # extension to be accepted by Ricecooker.
        thumbnail_filename = derive_filename(thumbnail)
        thumbnail_path = os.path.join(destination, thumbnail_filename)
        download_file(thumbnail, destination, request_fn=make_request,
                filename=thumbnail_filename)

    # If there is an embedded video in the page source grab it as a video node.
    video_node = None
    iframe = doc.select_one('.embedded-video iframe')
    if iframe:
        youtube_url = iframe['src']
        youtube_id = get_youtube_id_from_url(youtube_url)
        info = ydl.extract_info(youtube_url, download=False)
        video_title = info['title']
        print("    ... and with video titled %s from www.youtube.com/watch?v=%s" % (
                video_title, youtube_id))
        video_node = nodes.VideoNode(
            source_id=youtube_id,
            title=truncate_metadata(info['title']),
            license=licenses.CC_BY_NC_SALicense(
                copyright_holder=truncate_metadata('Thoughtful Learning')),
            description=info['description'],
            language="en",
            derive_thumbnail=True,
            files=[files.YouTubeVideoFile(youtube_id)],
        )
        category_node.add_child(video_node)

    zip_path = create_predictable_zip(destination)
    app_node = nodes.HTML5AppNode(
        source_id=url,
        title=truncate_metadata(title),
        license=licenses.CC_BY_NC_SALicense(
            copyright_holder=truncate_metadata('Thoughtful Learning')),
        description=description,
        thumbnail=thumbnail_path,
        files=[files.HTMLZipFile(zip_path)],
        language="en",
    )

    category_node.add_child(app_node)


# From https://stackoverflow.com/a/7936523
def get_youtube_id_from_url(value):
    """
    Examples:
    - http://youtu.be/SA2iWivDJiE
    - http://www.youtube.com/watch?v=_oPAwA_Udwc&feature=feedu
    - http://www.youtube.com/embed/SA2iWivDJiE
    - http://www.youtube.com/v/SA2iWivDJiE?version=3&amp;hl=en_US
    """
    query = urlparse(value)
    if query.hostname == 'youtu.be':
        return query.path[1:]
    if query.hostname in ('www.youtube.com', 'youtube.com'):
        if query.path == '/watch':
            p = parse_qs(query.query)
            return p['v'][0]
        if query.path[:7] == '/embed/':
            return query.path.split('/')[2]
        if query.path[:3] == '/v/':
            return query.path.split('/')[2]
    # fail?
    return None


def remove_node(doc, selector):
    node = doc.select_one(selector)
    if node:
        node.decompose()


def truncate_metadata(data_string):
    MAX_CHARS = 190
    if len(data_string) > MAX_CHARS:
        data_string = data_string[:190] + " ..."
    return data_string


url_blacklist = [
    'analytics.js',
    'infocusbackground.png',
    'menuicon.svg',
    'elaspan.png',
    'selspan.png',
    '21cspan.png',
    'js_gwq7iqjiqf3enczoxfuyelw46y9cqcl0duc3fh2kku8.js',
    'writersexpressbackground.png',
    'newsletterdino.png',
    'inquirecoverspan.png',
    'jquery.min.js',
    'tlstudents.jpg',
    'buttons.js',
    'inquireplane.png',
    'platform.js',
    'processedit.png',
    'js_blxotns2yt7yglf9qri9l9amfdnkqfnn-_adbtw3sie.js',
    'processprewrite.png',
    'writersexpressfish.png',
    'elastudent.jpg',
    'opener_chpt3.jpg',
    'inquiresky.png',
    'processpublish.png',
    'processwrite.png',
    'processrevise.png',
    'opener_chpt1.jpg',
    'inquireto.png',
]

def is_blacklisted(url):
    return any((item in url.lower()) for item in url_blacklist)


def derive_filename(url):
    name = os.path.basename(urlparse(url).path).replace('%', '_')
    return ("%s.%s" % (uuid.uuid4().hex, name)).lower()


def make_request(url, clear_cookies=True, timeout=60, *args, **kwargs):
    if clear_cookies:
        sess.cookies.clear()

    retry_count = 0
    max_retries = 5
    while True:
        try:
            response = sess.get(url, headers=headers, timeout=timeout, *args, **kwargs)
            break
        except (requests.exceptions.ConnectionError, requests.exceptions.ReadTimeout) as e:
            retry_count += 1
            print("Error with connection ('{msg}'); about to perform retry {count} of {trymax}."
                  .format(msg=str(e), count=retry_count, trymax=max_retries))
            time.sleep(retry_count * 1)
            if retry_count >= max_retries:
                return Dummy404ResponseObject(url=url)

    if response.status_code != 200:
        print("NOT FOUND:", url)

    return response


def get_parsed_html_from_url(url, *args, **kwargs):
    html = make_request(url, *args, **kwargs).content
    return BeautifulSoup(html, "html.parser")


def make_fully_qualified_url(url):
    base = 'https://k12.thoughtfullearning.com'
    if url.startswith("../images"):
        return base + url[2:]
    if url.startswith("../scripts"):
        return base + url[2:]
    if url.startswith("//"):
        return "http:" + url
    if url.startswith("/"):
        return base + url
    if not url.startswith("http"):
        return "%s/%s" % (base, url)
    return url


if __name__ == '__main__':
    """
    This code will run when the sushi chef is called from the command line.
    """
    chef = ThoughtfulLearningChef()
    chef.main()
