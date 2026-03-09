#!/usr/bin/env python

from bs4 import BeautifulSoup
import codecs
import copy
import csv
from collections import defaultdict, OrderedDict
import copy
import glob
from le_utils.constants import licenses, content_kinds, file_formats
import hashlib
import json
import logging
from moviepy.config import change_settings
from moviepy.editor import VideoFileClip
import ntpath
import os
from pathlib import Path
import re
import requests
from ricecooker.classes.licenses import get_license
from ricecooker.chefs import JsonTreeChef
from ricecooker.utils import downloader, html_writer
from ricecooker.utils.caching import CacheForeverHeuristic, FileCache, CacheControlAdapter
from ricecooker.utils.jsontrees import write_tree_to_json_tree, SUBTITLES_FILE
from pressurecooker.youtube import YouTubeResource
import time
from urllib.error import URLError
from urllib.parse import urljoin
from utils import if_dir_exists, get_name_from_url, clone_repo, build_path
from utils import file_exists, get_video_resolution_format, remove_links
from utils import get_name_from_url_no_ext, get_node_from_channel, get_level_map
from utils import remove_iframes, get_confirm_token, save_response_content
import youtube_dl


change_settings({"FFMPEG_BINARY": "ffmpeg"})

BASE_URL = "https://www.youtube.com/channel/UCdvmxJ8AmQBtcveTIBW3Qvw/videos"

DATA_DIR = "chefdata"
COPYRIGHT_HOLDER = "Free English with Hello Channel"
LICENSE = get_license(licenses.CC_BY, 
        copyright_holder=COPYRIGHT_HOLDER).as_dict()
AUTHOR = "Free English with Hello Channel"

LOGGER = logging.getLogger()
__logging_handler = logging.StreamHandler()
LOGGER.addHandler(__logging_handler)
LOGGER.setLevel(logging.INFO)

DOWNLOAD_VIDEOS = True
LOAD_VIDEO_LIST = False

sess = requests.Session()
cache = FileCache('.webcache')
basic_adapter = CacheControlAdapter(cache=cache)
forever_adapter = CacheControlAdapter(heuristic=CacheForeverHeuristic(), cache=cache)
sess.mount('http://', basic_adapter)
sess.mount(BASE_URL, forever_adapter)

# Run constants
################################################################################
CHANNEL_DOMAIN = ""          # Who is providing the content
CHANNEL_LANGUAGE = "en"      # Language of channel
CHANNEL_DESCRIPTION = "Lessons for teaching English vocabulary, grammar, and speaking."    # Description of the channel (optional)
CHANNEL_TAGLINE = "Lessons for teaching English vocabulary, grammar, and speaking."
CHANNEL_THUMBNAIL = None                                    # Local path or url to image file (optional)
CHANNEL_NAME = "Hello English Lessons"
CHANNEL_SOURCE_ID = "sushi-chef-hello-channel"

# Additional constants
################################################################################



class Node(object):
    def __init__(self, title, source_id, lang="en"):
        self.title = title
        self.source_id = source_id
        self.tree_nodes = OrderedDict()
        self.lang = lang
        self.description = None

    def add_node(self, obj):
        node = obj.to_node()
        if node is not None:
            self.tree_nodes[node["source_id"]] = node

    def to_node(self):
        return dict(
            kind=content_kinds.TOPIC,
            source_id=self.source_id,
            title=self.title,
            description=self.description,
            language=self.lang,
            author=AUTHOR,
            license=LICENSE,
            children=list(self.tree_nodes.values())
        )


class Topic(Node):
    def __init__(self, *args, **kwargs):
        super(Topic, self).__init__(*args, **kwargs)
        self.units = []


class VocabularyConversationalEnglish(Topic):
    def __init__(self, *args, **kwargs):
        title = "Vocabulary and Conversational English"
        super(VocabularyConversationalEnglish, self).__init__(title, title)
        self.base_title = "Learn English Vocabulary"

    def clean_title(self, title):
        title = title.replace(self.base_title, "").strip()
        return title.replace("English Conversation", "")

    def auto_generate_units(self, url, base_path):
        youtube = YouTubeResourceNode(url)
        units = defaultdict(list)
        for name, url in youtube.playlist_name_links():
            if name.startswith(self.base_title):
                units[name].append(url)

        units = sorted(units.items(), key=lambda x: x[0], reverse=False)
        for title, urls in units:
            for url in urls:
                youtube = YouTubeResourceNode(url, lang=self.lang)
                youtube.download(DOWNLOAD_VIDEOS, base_path)
                youtube.title = self.clean_title(youtube.title)
                LOGGER.info("+ {}".format(youtube.title))
                yield youtube


class EnglishGrammar(Topic):
    def __init__(self, *args, **kwargs):
        title = "English Grammar"
        super(EnglishGrammar, self).__init__(title, title)
        self.base_title = "English Conversation"

    def clean_title(self, title):
        title = title.replace(self.base_title, "").strip()
        pattern = "(?P<lesson>Lesson \d+)"
        exp = re.search(pattern, title)
        if exp:
            return exp.group("lesson")
        else:
            return title

    def auto_generate_units(self, base_path):
        values = video_editing_file_to_dict("video_editing_data.csv")
        counter = 1
        for url, clips in values.items():
            for youtube, i in cut_video(url, base_path, clips, counter):
                youtube.title = self.clean_title(youtube.title)
                LOGGER.info("+ {}".format(youtube.title))
                counter += 1
                yield youtube


class YouTubeResourceNode(YouTubeResource):
    def __init__(self, source_id, name=None, type_name="Youtube", lang="en", 
            embeded=False, subtitles=True):
        if embeded is True:
            self.source_id = YouTubeResourceNode.transform_embed(source_id)
        else:
            self.source_id = self.clean_url(source_id)
        super(YouTubeResourceNode, self).__init__(source_id)
        LOGGER.info("    + Resource Type: {}".format(type_name))
        LOGGER.info("    - URL: {}".format(source_id))
        self.filename = None
        self.type_name = type_name
        self.filepath = None
        self.name = name
        self.subtitles = subtitles
        self.file_format = file_formats.MP4
        self.lang = lang
        self.is_valid = False

    def clean_url(self, url):
        if url[-1] == "/":
            url = url[:-1]
        return url.strip()

    @property
    def title(self):
        return self.name

    @title.setter
    def title(self, v):
        self.name = v

    @classmethod
    def is_youtube(self, url, get_channel=False):
        youtube = url.find("youtube") != -1 or url.find("youtu.be") != -1
        if get_channel is False:
            youtube = youtube and url.find("user") == -1 and url.find("/c/") == -1
        return youtube

    @classmethod
    def transform_embed(self, url):
        url = "".join(url.split("?")[:1])
        return url.replace("embed/", "watch?v=").strip()

    def playlist_links(self):
        ydl_options = {
                'no_warnings': True,
                'restrictfilenames':True,
                'continuedl': True,
                'quiet': False,
                'format': "bestvideo[height<={maxheight}][ext=mp4]+bestaudio[ext=m4a]/best[height<={maxheight}][ext=mp4]".format(maxheight='480'),
                'noplaylist': False
            }

        playlist_videos_url = []
        with youtube_dl.YoutubeDL(ydl_options) as ydl:
            try:
                ydl.add_default_info_extractors()
                info = ydl.extract_info(self.source_id, download=False)
                for entry in info["entries"]:
                    playlist_videos_url.append(entry["webpage_url"])
            except(youtube_dl.utils.DownloadError, youtube_dl.utils.ContentTooShortError,
                    youtube_dl.utils.ExtractorError) as e:
                LOGGER.info('An error occured ' + str(e))
                LOGGER.info(self.source_id)
            except KeyError as e:
                LOGGER.info(str(e))
        return playlist_videos_url

    def playlist_name_links(self):
        name_url = []
        source_id_hash = hashlib.sha1(self.source_id.encode("utf-8")).hexdigest()
        base_path = build_path([DATA_DIR, CHANNEL_SOURCE_ID])
        videos_url_path = os.path.join(base_path, "{}.json".format(source_id_hash))

        if file_exists(videos_url_path) and LOAD_VIDEO_LIST is True:
            with open(videos_url_path, "r") as f:
                name_url = json.load(f)
        else:
            for url in self.playlist_links():
                youtube = YouTubeResourceNode(url)
                info = youtube.get_resource_info()
                name_url.append((info["title"], url))
            with open(videos_url_path, "w") as f:
                json.dump(name_url, f)
        return name_url

    def subtitles_dict(self):
        subs = []
        video_info = self.get_resource_subtitles()
        if video_info is not None:
            video_id = video_info["id"]
            if 'subtitles' in video_info:
                subtitles_info = video_info["subtitles"]
                for language in subtitles_info.keys():
                    subs.append(dict(file_type=SUBTITLES_FILE, youtube_id=video_id, language=language))
        return subs

    def download(self, download=True, base_path=None):
        info = super(YouTubeResourceNode, self).download(base_path=base_path)
        self.filepath = info["filename"]
        self.title = info["title"]

    def to_node(self):
        if self.filepath is not None:
            files = [dict(file_type=content_kinds.VIDEO, path=self.filepath)]
            if self.subtitles:
                files += self.subtitles_dict()
            node = dict(
                kind=content_kinds.VIDEO,
                source_id=self.source_id,
                title=self.title,
                description='',
                author=AUTHOR,
                files=files,
                language=self.lang,
                license=LICENSE
            )
            return node


#time_str with format hh:mm:ss
def time_to_secs(time_str):
    values = time_str.split(":")
    values = map(int, values)
    secs = sum([(v*m) for v, m in zip(values, [3600, 60, 1])])
    return secs


def video_editing_file_to_dict(filepath):
    with open(filepath, "r") as f:
        csv_reader = csv.reader(f, delimiter=',')
        header = next(csv_reader)
        data = OrderedDict()
        url_idx = header.index("video_url")
        start_idx = header.index("start")
        stop_idx = header.index("stop")

        for row in csv_reader:
            if row[url_idx] not in data:
                data[row[url_idx]] = []
            data[row[url_idx]].append((time_to_secs(row[start_idx]), time_to_secs(row[stop_idx])))
        return data
    

def cut_video(url, base_path, clips, counter=0):
    youtube = YouTubeResourceNode(url)
    youtube.download(download=DOWNLOAD_VIDEOS, base_path=base_path)
    for clip in clips:
        filepath = youtube.filepath.replace(".mp4", "{}_{}.mp4".format(*clip))
        if not file_exists(filepath):
            video = VideoFileClip(youtube.filepath).subclip(*clip)
            video.write_videofile(filepath, fps=25, audio_codec='libfdk_aac')
        youtube_copy = copy.deepcopy(youtube)
        youtube_copy.source_id = filepath.split()[-1]
        youtube_copy.title = "{} {}".format(youtube.title[:-3], counter)
        youtube_copy.filepath = filepath
        counter += 1
        yield youtube_copy, counter


# The chef subclass
################################################################################
class HelloChannelChef(JsonTreeChef):
    HOSTNAME = BASE_URL
    TREES_DATA_DIR = os.path.join(DATA_DIR, 'trees')
    SCRAPING_STAGE_OUTPUT_TPL = 'ricecooker_json_tree.json'
    THUMBNAIL = ""

    def __init__(self):
        build_path([HelloChannelChef.TREES_DATA_DIR])
        self.scrape_stage = os.path.join(HelloChannelChef.TREES_DATA_DIR, 
                                HelloChannelChef.SCRAPING_STAGE_OUTPUT_TPL)
        super(HelloChannelChef, self).__init__()

    def pre_run(self, args, options):
        channel_tree = self.scrape(args, options)
        self.write_tree_to_json(channel_tree)

    def lessons(self):
        channel_tree = dict(
                source_domain=HelloChannelChef.HOSTNAME,
                source_id=BASE_URL,
                title=CHANNEL_NAME,
                description=CHANNEL_DESCRIPTION,
                thumbnail="http://3.bp.blogspot.com/_XoyoDdCstIU/TRu159QK2wI/AAAAAAAAANs/G6QSVqXmZqY/s400/Dibujo.jpg",
                author=AUTHOR,
                language=CHANNEL_LANGUAGE,
                children=[],
                tagline=CHANNEL_TAGLINE,
                license=LICENSE,
            )
        
        return channel_tree


    def scrape(self, args, options):
        download_video = options.get('--download-video', "1")
        load_video_list = options.get('--load-video-list', "0")

        if int(download_video) == 0:
            global DOWNLOAD_VIDEOS
            DOWNLOAD_VIDEOS = False

        if int(load_video_list) == 1:
            global LOAD_VIDEO_LIST
            LOAD_VIDEO_LIST = True

        channel_tree = self.lessons()

        base_path = [DATA_DIR] + ["data"]
        base_path = build_path(base_path)

        vocabulary = VocabularyConversationalEnglish()
        for unit in vocabulary.auto_generate_units(BASE_URL, base_path):
            vocabulary.add_node(unit)
        english_grammar = EnglishGrammar()
        for unit in english_grammar.auto_generate_units(base_path):
            english_grammar.add_node(unit)
        channel_tree["children"].append(english_grammar.to_node())
        channel_tree["children"].append(vocabulary.to_node())
        
        return channel_tree

    def write_tree_to_json(self, channel_tree):
        write_tree_to_json_tree(self.scrape_stage, channel_tree)


# CLI
################################################################################
if __name__ == '__main__':
    chef = HelloChannelChef()
    chef.main()
