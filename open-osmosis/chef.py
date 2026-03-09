#!/usr/bin/env python

"""
Sushi Chef for Open Osmosis:
Videos from https://www.youtube.com/channel/UCNI0qOojpkhsUtaQ4_2NUhQ/playlists
Assessment items from https://open.osmosis.org/topics
"""

from collections import defaultdict
import html
import os
import pycountry
import re
import requests
import tempfile
import time
from urllib.parse import urlparse, parse_qs

from bs4 import BeautifulSoup
import youtube_dl

from le_utils.constants import content_kinds, file_formats, languages, exercises
from ricecooker.chefs import SushiChef
from ricecooker.classes import nodes, files, licenses, questions
from ricecooker.utils.caching import CacheForeverHeuristic, FileCache, CacheControlAdapter, InvalidatingCacheControlAdapter
from ricecooker.utils.browser import preview_in_browser
from ricecooker.utils.html import download_file, WebDriver
from ricecooker.utils.zip import create_predictable_zip


sess = requests.Session()
cache = FileCache('.webcache')
forever_adapter = CacheControlAdapter(heuristic=CacheForeverHeuristic(), cache=cache)

sess.mount('http://', forever_adapter)
sess.mount('https://', forever_adapter)

ydl = youtube_dl.YoutubeDL({
    'no_warnings': True,
    'writesubtitles': True,
    'allsubtitles': True,
    'ignoreerrors': True,  # Skip over deleted videos in a playlist
})

LICENSE = licenses.CC_BY_SALicense(
    copyright_holder='Open Osmosis (open.osmosis.org)')

# Map between assessment topic name and YouTube playlist name
QUESTION_VIDEO_MAP = {
    "Genetics": "Genetics pathology",
    "Dermatology": "Dermatology pathology",
    "Heme/Onc": "Hematology pathology",
    "Neurology": "Neurological pathology",
    "Renal": "Renal pathology",
    "Cardiology": "Cardiovascular pathology",
    "GI": "Gastrointestinal pathology",
    "Endocrine": "Endocrine pathology",
    "Reproduction": "Reproductive pathology",
    "MSK": "Musculoskeletal pathology",
    "Pediatrics": "Pediatrics videos",
    "Pulmonology": "Respiratory pathology",
    "Psychiatry": "Mental health and disorders",
    "Microbiology": "Infectious disease pathology",
    "Anesthesiology": None,
    "Emergency Medicine": None,
    "Osteopathic Principles": None,
    "Ophthalmology": None,
    "Radiology": None,
    "Surgery": None,
    None: "Pathophysiology",
    None: "The science of teaching and learning",
    None: "Physiology",
    None: "Ear, nose, and throat",
    None: "Immune disorders",
    None: "Fluid and Electrolyte Imbalances",
    None: "Maternal pathology",
}


class OpenOsmosisChef(SushiChef):
    """
    The chef class that takes care of uploading channel to the content curation server.

    We'll call its `main()` method from the command line script.
    """
    channel_info = {
        'CHANNEL_SOURCE_DOMAIN': "open.osmosis.org",
        'CHANNEL_SOURCE_ID': "open-osmosis",
        'CHANNEL_TITLE': "Osmosis.org",
        'CHANNEL_THUMBNAIL': "https://d3cdo0emj8d2qc.cloudfront.net/assets/f78c3f1d2be258bd84c85cb1f342e9f7343c798b.png",
        'CHANNEL_DESCRIPTION': "A study tool built for tomorrow's doctors and health workers.",
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

        topics_map = fetch_youtube_playlists(channel)
        fetch_assessment_topics(channel, topics_map)

        return channel


def fetch_youtube_playlists(parent_node):
    """Fetch all of the YouTube playlists from the YouTube channel.

    Return a map of YouTube playlist title to the topic node.
    """
    youtube_channel_url = 'https://www.youtube.com/channel/UCNI0qOojpkhsUtaQ4_2NUhQ/playlists'
    print("--- Fetching videos from YouTube channel (%s) ---" % youtube_channel_url)
    print()

    topics_map = {}
    info = ydl.extract_info(youtube_channel_url, download=False)
    for i, playlist in enumerate(info['entries']):
        title = playlist['title']
        youtube_url = playlist['webpage_url']
        print("  Downloading playlist %s (%s)" % (title, youtube_url))
        playlist_topic = nodes.TopicNode(
                source_id=playlist['id'], title=playlist['title'],
                language="en")
        topics_map[title] = playlist_topic
        parent_node.add_child(playlist_topic)
        for j, video in enumerate(playlist['entries']):
            if video:
                playlist_topic.add_child(fetch_video(video))

    return topics_map


def fetch_assessment_topics(parent_node, topics_map):
    """Fetch all of the assessment topics listed in Open Osmosis."""
    assessment_topics_url = "https://open.osmosis.org/topics"
    print("--- Fetching assessments from %s ---" % assessment_topics_url)
    print()

    with WebDriver("https://open.osmosis.org/topics", delay=1000) as driver:
        page_html = get_generated_html_from_driver(driver)
        doc = BeautifulSoup(page_html, "html.parser")

        for i, topic in enumerate(doc.select('.container .topic')):
            link = topic.select_one('a')
            href = link['href']
            topic_id = href.split('/')[-1]
            url = make_fully_qualified_url(href)
            text = link.text.strip()
            img = link.select_one('img')['src']

            print('Fetching topic %s (%s)' % (text, url))

            # Get the topic node, either by trying to finding the corresponding
            # topic node that was created in the earlier videos scraping step,
            # or creating a new one.
            topic_node = None
            video_topic_name = QUESTION_VIDEO_MAP.get(text)

            if video_topic_name:
                topic_node = topics_map.get(video_topic_name)
                if topic_node:
                    topic_node.title = "%s (%s)" % (text, video_topic_name)
                    topic_node.set_thumbnail(img)

            if not topic_node:
                topic_node = nodes.TopicNode(source_id=topic_id,
                        title=text, thumbnail=img)
                parent_node.add_child(topic_node)

            fetch_assessment_topic_items(driver, topic_node, url,
                    topic_short_title=text, thumbnail=img)


def _title_exercise(topic_title, first_item, last_item):
    return "%s Questions %s-%s" % (topic_title, first_item, last_item)


QUESTIONS_PER_EXERCISE = 5

def fetch_assessment_topic_items(driver, topic_node, topic_url,
        topic_short_title, thumbnail=None):
    """Fetch the individual assessment items for a given topic.

    Groups every 5 assessments into an exercise node.
    """
    next_item_url = topic_url
    item_count = 0

    while next_item_url:
        driver.get(next_item_url)
        current_url = driver.current_url
        item_id = current_url.split('/')[-1]

        print('  Fetching question %s (%s)' % (item_count + 1, current_url))

        # Create exercise node, grouping together every 5 questions.
        if item_count % QUESTIONS_PER_EXERCISE == 0:
            first_item_index_in_exercise = item_count
            exercise_title = _title_exercise(topic_short_title, item_count + 1,
                    item_count + QUESTIONS_PER_EXERCISE)
            exercise_node = nodes.ExerciseNode(source_id=item_id,
                    title=exercise_title, license=LICENSE, thumbnail=thumbnail,
                    exercise_data={'randomize': False})
            topic_node.add_child(exercise_node)

        # Now try to convert the page HTML into an assessment item, retrying
        # on error, and then skipping any missing images after a few failed
        # retries.
        for i in range(0, 4):
            try:
                page_html = get_generated_html_from_driver(driver)
                question, next_item_url = fetch_assessment_item(page_html, item_id)
                break
            except Exception as e:
                wait_time = (2 ** i)
                print("Got an error, retrying after a wait of %s seconds. "
                        "Error was: %s" % (wait_time, str(e)))
                driver.get(current_url)
                time.sleep(wait_time)
                exception = e
        else:
            print("Going to try skipping any missing images")
            page_html = get_generated_html_from_driver(driver)
            question, next_item_url = fetch_assessment_item(page_html, item_id,
                    skip_missing_images=True)

        exercise_node.add_question(question)
        item_count += 1

    # Re-title the exercise, given that this is the last exercise in the topic,
    # which may not contain up to 5 items. (e.g. re-title it "Genetics 10-12")
    exercise_node.title = _title_exercise(topic_short_title,
            first_item_index_in_exercise + 1, item_count)


def _process_text_into_markdown(container_node, skip_missing_images):
    markdown_text = ''

    for node in container_node.children:
        image = node.select_one('.models-media-Image')
        if image:
            assert len(node.select('.models-media-Image')) == 1, 'multiple images found'
            image_tag = image.select_one('img')
            if not image_tag:
                if skip_missing_images:
                    continue
                else:
                    raise Exception("Cannot find img tag where we expect one")
            src = image_tag['src']
            credit = image.text.strip()
            markdown_text += '![%s](%s)\n\n%s\n\n' % (credit, src, credit)
        else:
            text = node.get_text(separator="\n").strip()
            if 'fwb' in node.get('class', []):
                text = '**' + text + '**'
            markdown_text += text + "\n\n"

    return markdown_text


def fetch_assessment_item(page_html, item_id, skip_missing_images=False):
    """Fetch an individual assessment item given its page HTML.

    Return a tuple (question object, next item url).
    """
    doc = BeautifulSoup(page_html, "html.parser")

    question_markdown = _process_text_into_markdown(doc.select_one('#Content .stem'),
            skip_missing_images)
    answers = [ans.text.strip() for ans in doc.select('.answers .ans div')]
    correct = doc.select_one('.answers-explained .fwb').text.strip()

    # TODO(davidhu): Get videos from hints, e.g. in https://open.osmosis.org/item/142641
    # TODO(davidhu): Fine-tune line spacing for hints
    hint_1 = _process_text_into_markdown(doc.select_one('.answers-explained .explain-ans'),
            skip_missing_images)
    hint_2 = _process_text_into_markdown(doc.select_one('.answers-explained .explain'),
            skip_missing_images)
    combined_hint = "%s\n\nMain Explanation\n---\n\n%s" % (hint_1, hint_2)

    question = questions.SingleSelectQuestion(id=item_id, hints=combined_hint,
            question=question_markdown, all_answers=answers,
            correct_answer=correct)

    next_item_url = None
    next_link = doc.select_one('.ques-nav-right a')
    if next_link:
        next_href = doc.select_one('.ques-nav-right a')['href']
        if not next_href.endswith('null'):
            next_item_url = make_fully_qualified_url(next_href)

    return question, next_item_url


def fetch_video(video):
    youtube_id = video['id']
    title = video['title']
    description = video['description']
    youtube_url = video['webpage_url']
    subtitle_languages = video['subtitles'].keys()

    print("    Fetching video data: %s (%s)" % (title, youtube_url))

    video_node = nodes.VideoNode(
        source_id=youtube_id,
        title=truncate_metadata(title),
        license=LICENSE,
        description=truncate_description(description),
        derive_thumbnail=True,
        language="en",
        files=[files.YouTubeVideoFile(youtube_id=youtube_id)],
    )

    # Add subtitles in whichever languages are available.
    for language in subtitle_languages:
        # TODO(david): Should catch exception thrown by
        # files.YouTubeSubtitleFile rather than breaking abstraction.
        if languages.getlang(language) or languages.getlang_by_alpha2(language):
            video_node.add_file(files.YouTubeSubtitleFile(
                youtube_id=youtube_id, language=language))
        else:
            print("WARNING: Subtitle language %s not found in languages file" % language)

    return video_node


DESCRIPTION_RE = re.compile('Subscribe - .*$')

def truncate_description(description):
    first_line = description.splitlines()[0]
    return DESCRIPTION_RE.sub('', first_line)


def truncate_metadata(data_string):
    MAX_CHARS = 190
    if len(data_string) > MAX_CHARS:
        data_string = data_string[:190] + " ..."
    return data_string


def make_fully_qualified_url(url):
    if url.startswith("//"):
        return "http:" + url
    if url.startswith("/"):
        return "https://open.osmosis.org" + url
    if not url.startswith("http"):
        return "https://open.osmosis.org/" + url
    return url


def get_generated_html_from_driver(driver, tagname="html"):
    return driver.execute_script("return document.getElementsByTagName('{tagname}')[0].innerHTML".format(tagname=tagname))


if __name__ == '__main__':
    """
    This code will run when the sushi chef is called from the command line.
    """
    chef = OpenOsmosisChef()
    chef.main()
