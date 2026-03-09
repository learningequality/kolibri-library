#!/usr/bin/env python
import os
import re
from ricecooker.chefs import SushiChef
from ricecooker.classes import nodes, files
from ricecooker.config import LOGGER              # Use LOGGER to print messages
from ricecooker.exceptions import raise_for_invalid_channel
from le_utils.constants import licenses, languages
import requests
import youtube_dl
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from client import Client

# Run constants
################################################################################
CHANNEL_NAME = "Migration Matters"
CHANNEL_SOURCE_ID = "sushi-chef-migration-matters-en"
CHANNEL_DOMAIN = "migrationmatters.me/#featured_courses"
CHANNEL_LANGUAGE = "en"
CHANNEL_DESCRIPTION = "Migration Matters is a non-profit "\
                      "that was founded in 2016 to address "\
                      "big topics on migration through short-form "\
                      "video courses that empower the public to have "\
                      "more nuanced and evidence-based conversations "\
                      "about migration and refugees."
CHANNEL_THUMBNAIL = "thumbnail.png"

# Additional constants
################################################################################

BASE_URL = "https://iversity.org"
CLIENT = Client("shivi@learningequality.org", "kolibri")
CHANNEL_LICENSE = licenses.CC_BY_NC_ND
COPYRIGHT_HOLDER = "CC BY-NC-ND 4.0"
EMAIL_COURSE_URL = "http://migrationmatters.me/episode/"
HEADERS = {'User-Agent': str(UserAgent().chrome)}
DOWNLOAD_DIRECTORY = os.path.sep.join([os.path.dirname(os.path.realpath(__file__)), "downloads"])
EPISODE_DICT = {}
PAGE_DICT = {}

# Create download directory if it doesn't already exist
if not os.path.exists(DOWNLOAD_DIRECTORY):
    os.makedirs(DOWNLOAD_DIRECTORY)

# The chef subclass
################################################################################
class MyChef(SushiChef):

    channel_info = {                                   # Channel Metadata
        'CHANNEL_SOURCE_DOMAIN': CHANNEL_DOMAIN,       # Who is providing the content
        'CHANNEL_SOURCE_ID': CHANNEL_SOURCE_ID,        # Channel's unique id
        'CHANNEL_TITLE': CHANNEL_NAME,                 # Name of channel
        'CHANNEL_LANGUAGE': CHANNEL_LANGUAGE,          # Language of channel
        'CHANNEL_THUMBNAIL': CHANNEL_THUMBNAIL,        # Local path or url to image file (optional)
        'CHANNEL_DESCRIPTION': CHANNEL_DESCRIPTION,    # Description of the channel (optional)
    }

    def construct_channel(self, *args, **kwargs):
        """
        Creates ChannelNode and build topic tree

        Migration-Matters is organized with the following hierarchy:
        Iversity Site
        Understanding Diversity (Topic)
        |--- Welcome (Video - VideoNode)
        |--- Who is 'Us' and Who is 'Them'? (Video - VideoNode)
        ...
        Email Course
        A MIGRANT'S VIEW (Topic)
        |--- Nassim's Takeaway: Can Europe Welcome Them All? (Video - VideoNode)
        |--- Do Deportations Cut Migration? (Video - VideoNode)
        ...
        """

        channel = self.get_channel(*args, **kwargs)  # Create ChannelNode from data in self.channel_info
        CLIENT.login("{}/en/users/sign_in".format(BASE_URL))
        scrape_iversity(channel)
        scrape_email_courses(EMAIL_COURSE_URL)

        # create a topic node for each episode
        # and add videos with same episode as children
        for episode in EPISODE_DICT:
            source_id = episode.strip().replace(" ", "_")
            topic = nodes.TopicNode(source_id=source_id, title=episode)
            for video in EPISODE_DICT[episode]:
                topic.add_child(video)
            channel.add_child(topic)

        raise_for_invalid_channel(channel)                                  # Check for errors in channel construction
        return channel

def crawl_each_post(post_url):
    resp = requests.get(post_url, headers=HEADERS)
    soup = BeautifulSoup(resp.content, "html.parser")
    wrapper = soup.find('div', {'class': 'wpb_wrapper'})
    course_name = wrapper.find('div', {'class': 'vc_custom_heading'}).getText().strip()
    delimiters = " OF ", " FROM "
    regex_pattern = '|'.join(map(re.escape, delimiters))
    course = re.split(regex_pattern, course_name)[1]
    wpb_video_wrapper = wrapper.find_all('div', {'class': 'wpb_video_wrapper'})

    if wpb_video_wrapper:

        for each_wrapper in wpb_video_wrapper:
            video_url = each_wrapper.find('iframe').attrs["src"].split("?feature")[0]
            video_id = video_url.split("/")[-1]

            ydl = youtube_dl.YoutubeDL({
                'outtmpl': './downloads/%(id)s.%(ext)s',
                'writeautomaticsub': True,
                'logger': LOGGER
            })

            with ydl:
                result = ydl.extract_info(
                    "http://www.youtube.com/watch?v={}".format(video_id),
                    download=True
                )
            if 'entries' in result:
                video = result['entries'][0]
            else:
                video = result

            video_title = video["title"]
            video_source_id = video_title.strip().replace(" ", "_")
            video_path = "{}/{}.mp4".format(DOWNLOAD_DIRECTORY, video_id)
            video_subtitle_path = "{}/{}.en.vtt".format(DOWNLOAD_DIRECTORY, video_id)
            video_file = files.VideoFile(path=video_path, language=languages.getlang('en').code)
            video_subtitle = files.SubtitleFile(path=video_subtitle_path, language=languages.getlang('en').code)
            video_node = nodes.VideoNode(
                source_id=video_source_id,
                title=video_title,
                files=[video_file, video_subtitle],
                license=CHANNEL_LICENSE,
                copyright_holder=COPYRIGHT_HOLDER,
            )

            if course not in EPISODE_DICT:
                EPISODE_DICT[course] = [video_node]
            else:
                EPISODE_DICT[course].append(video_node)
            LOGGER.info("   Uploading video - {}".format(video_title.strip()))
    else:
        LOGGER.info("Format of the file is not supported by the sushi chef : {}".format(course_name))

def crawl_video(url, first=False):
    resp = requests.get(url, headers=HEADERS)
    soup = BeautifulSoup(resp.content, "html.parser")
    posts = soup.find_all('div', {'class': 'post'})
    for post in posts:
        post_url = post.find('a').attrs["href"]
        crawl_each_post(post_url)
    # This is to return BeautifulSoup part to
    # crawl next pages.
    if first:
        return soup
    return None

def scrape_email_courses(url):
    soup = crawl_video(url, True)
    pagination = soup.find('div', {'class': 'pagination'}).find_all('li')

    for each_page in pagination:
        page, status = each_page.find("a").string, each_page.attrs.get("class")
        if page not in PAGE_DICT:
            PAGE_DICT[page] = status
            if status is None:
                next_page_url = each_page.find("a").attrs["href"]
                crawl_video(next_page_url)

def scrape_iversity(channel):
    url = "{}/en/my/courses/rethinking-us-them-integration-and-diversity-in-europe/lesson_units".format(BASE_URL)
    LOGGER.info("   Scraping Migration Matters at {}".format(url))
    source = read_source(url)
    chapters = source.find_all('div', {'class': 'chapter-units-wrapper'})

    for chapter in chapters:
        title = str(chapter.find('div', {'class': 'chapter-title'}).string)
        source_id = title.strip().replace(" ", "_")
        topic = nodes.TopicNode(source_id=source_id, title=title)
        lessons = chapter.find_all('a', {'class': 'unit-wrapper'})

        for lesson in lessons:
            video_exists = lesson.find('i', {'class': 'unit_video'})
            video_title = str(lesson.find('span', {'class': 'unit-title'}).string).strip()

            if video_exists:
                video_source_id = video_title.replace(" ", "_")
                video_url = "{}{}".format(BASE_URL, lesson.attrs["href"])
                video_source = read_source(video_url)
                video_info = video_source.find('video')
                video_subtitle_path = video_info.find('track', {'kind': 'subtitles'}).attrs["src"]
                video_subtitle = files.SubtitleFile(path=video_subtitle_path, language=languages.getlang('en').code)
                video_link = video_info.find('source', {'res':'480'}).attrs["src"]
                video_file = files.VideoFile(path=video_link, language=languages.getlang('en').code)
                video_node = nodes.VideoNode(
                    source_id=video_source_id,
                    title=video_title,
                    files=[video_file, video_subtitle],
                    license=CHANNEL_LICENSE,
                    copyright_holder=COPYRIGHT_HOLDER
                )
                LOGGER.info("   Uploading video - {}".format(video_title.strip()))
                topic.add_child(video_node)
            else:
                LOGGER.info("Format of the file is not supported by the sushi chef : {}".format(video_title))

        channel.add_child(topic)

def read_source(url):
    response = CLIENT.get(url)
    return BeautifulSoup(response.content, 'html5lib')

# CLI
################################################################################
if __name__ == '__main__':
    # This code runs when sushichef.py is called from the command line
    chef = MyChef()
    chef.main()
