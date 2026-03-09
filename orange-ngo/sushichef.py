#!/usr/bin/env python

from bs4 import BeautifulSoup
import codecs
from collections import defaultdict, OrderedDict
import copy
import glob
from le_utils.constants import licenses, content_kinds, file_formats
import hashlib
import json
import logging
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
from utils import dir_exists, get_name_from_url, clone_repo, build_path
from utils import file_exists, get_video_resolution_format, remove_links
from utils import get_name_from_url_no_ext, get_node_from_channel, get_level_map
from utils import remove_iframes, get_confirm_token, save_response_content
import youtube_dl

DATA_DIR = "chefdata"
COPYRIGHT_HOLDER = "Orange NGO"
LICENSE = get_license(licenses.CC_BY, 
        copyright_holder=COPYRIGHT_HOLDER).as_dict()
AUTHOR = "Orange NGO"

LOGGER = logging.getLogger()
__logging_handler = logging.StreamHandler()
LOGGER.addHandler(__logging_handler)
LOGGER.setLevel(logging.INFO)

DOWNLOAD_VIDEOS = True
DOWNLOAD_FILES = True
LOAD_VIDEO_LIST = False

sess = requests.Session()

# Run constants
################################################################################
CHANNEL_DOMAIN = "https://www.youtube.com/channel/UC0s6otAswvWTyFD3-Uxoohw/" # Who is providing the content
CHANNEL_LANGUAGE = "ar"                                                      # Language of channel
CHANNEL_DESCRIPTION = None                                                   # Description of the channel (optional)
CHANNEL_THUMBNAIL = "https://yt3.ggpht.com/a-/AN66SAyzq6kC7KlGFoNHbVmdOMlY6ENfQk0YkFZs5A=s288-mo-c-c0xffffffff-rj-k-no"                                                                          # Local path or url to image file (optional)

# Additional constants
################################################################################


class Node(object):
    def __init__(self, title=None, source_id=None, lang="ar"):
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
    

class Grades(object):
    def __init__(self, *args, **kwargs):
        self.grades = []

    def load(self, filename, auto_parse=False):
        with open(filename, "r") as f:
            grades = json.load(f)
            for grade in grades:
                grade_obj = Grade() 
                subject_obj = Subject(title=grade["title"], source_id=grade["source_id"], 
                                      lang=grade["lang"])
                subject_obj.auto_generate_lessons(grade["lessons"], playlist=False)
                self.grades.append(subject_obj)

    def __iter__(self):
        return iter(self.grades)


class Grade(Node):
    def __init__(self, *args, **kwargs):
        super(Grade, self).__init__(*args, **kwargs)
        self.subjects = []

    def add_subject(self, subject):
        self.subjects.append(subject)


class Subject(Node):
    def __init__(self, *args, **kwargs):
        super(Subject, self).__init__(*args, **kwargs)
        self.lessons = []

    def auto_generate_lessons(self, urls, playlist=True):
        for url in urls:
            youtube = YouTubeResourceNode(url)
            if playlist is True:
                for title, url in youtube.playlist_name_links():
                    lesson = Lesson(title=title, source_id=url, lang=self.lang)
                    self.lessons.append(lesson)
            else:
                lesson = Lesson(title=None, source_id=url, lang=self.lang)
                self.lessons.append(lesson)


class Lesson(Node):

    def download(self, download=True, base_path=None):
        youtube = YouTubeResourceNode(self.source_id, lang=self.lang)
        pdf_urls = youtube.download(download, base_path)
        if self.title is None:
            self.title = youtube.title
        self.add_node(youtube)
        if len(pdf_urls) > 0:
            pdf_nodes = self.build_pdfs_nodes(pdf_urls, base_path)
            for pdf_node in pdf_nodes:
                self.add_node(pdf_node)

    def build_pdfs_nodes(self, urls, base_path):
        base_path = build_path([base_path, 'pdfs'])
        pdf_nodes = []
        for pdf_url in urls:
            pdf_file = File(source_id=pdf_url, lang=self.lang, title=self.title)
            pdf_file.download(download=DOWNLOAD_FILES, base_path=base_path)
            pdf_nodes.append(pdf_file)
        return pdf_nodes

    def to_node(self):
        children = list(self.tree_nodes.values())
        if len(children) == 1:
            return children[0]
        else:
            return dict(
                kind=content_kinds.TOPIC,
                source_id=self.source_id,
                title=self.title,
                description=self.description,
                language=self.lang,
                author=AUTHOR,
                license=LICENSE,
                children=children
            )


class File(Node):
    def __init__(self, title=None, source_id=None, lang="ar"):
        super(File, self).__init__(title=title, source_id=source_id, lang=lang)
        self.filename = get_name_from_url(source_id)
        self.filepath = None
        self.lang = lang

    def download(self, download=True, base_path=None):
        try:
            if download is False:
                return
            response = sess.get(self.source_id)
            content_type = response.headers.get('content-type')
            if 'application/pdf' in content_type:
                self.filepath = os.path.join(base_path, self.filename)
                with open(self.filepath, 'wb') as f:
                    for chunk in response.iter_content(10000):
                        f.write(chunk)
                LOGGER.info("    - Get file: {}, node name: {}".format(self.filename, self.title))
        except requests.exceptions.HTTPError as e:
            LOGGER.info("Error: {}".format(e))
        except requests.exceptions.ConnectionError:
            ### this is a weird error, may be it's raised when the webpage
            ### is slow to respond requested resources
            LOGGER.info("Connection error, the resource will be scraped in 5s...")
            time.sleep(3)
        except requests.exceptions.ReadTimeout as e:
            LOGGER.info("Error: {}".format(e))
        except requests.exceptions.TooManyRedirects as e:
            LOGGER.info("Error: {}".format(e))

    def to_node(self):
        if self.filepath is not None:
            node = dict(
                kind=content_kinds.DOCUMENT,
                source_id=self.source_id,
                title=self.title,
                description='',
                files=[dict(
                    file_type=content_kinds.DOCUMENT,
                    path=self.filepath
                )],
                language=self.lang,
                license=LICENSE)
            return node


class YouTubeResourceNode(YouTubeResource):
    def __init__(self, source_id, name=None, type_name="Youtube", lang="ar", 
            embeded=False, section_title=None):
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
        self.section_title = section_title
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
        return self.get_file_url(info)

    def get_file_url(self, info):
        description = info["description"]
        pattern = 'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
        url_re = re.compile(pattern)
        return url_re.findall(description)

    def to_node(self):
        if self.filepath is not None:
            files = [dict(file_type=content_kinds.VIDEO, path=self.filepath)]
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


# The chef subclass
################################################################################
class OrangeNGOChef(JsonTreeChef):
    TREES_DATA_DIR = os.path.join(DATA_DIR, 'trees')

    def __init__(self):
        build_path([OrangeNGOChef.TREES_DATA_DIR])
        super(OrangeNGOChef, self).__init__()

    def pre_run(self, args, options):
        channel_tree = self.scrape(args, options)
        self.write_tree_to_json(channel_tree)

    def lessons(self):
        global CHANNEL_SOURCE_ID
        self.RICECOOKER_JSON_TREE = 'ricecooker_json_tree.json'
        CHANNEL_NAME = "Orange NGO (العربيّة)"
        CHANNEL_SOURCE_ID = "orange-ngo-ar"
        channel_tree = dict(
                source_domain=CHANNEL_DOMAIN,
                source_id=CHANNEL_SOURCE_ID,
                title=CHANNEL_NAME,
                description="""أورانج إن جي أو تقدم للمتعلمين في المرحلة الجامعية وما بعد ذلك مجموعة من المحاضرات والدروس المصورة القصيرة في عدة مواضيع تساعدهم في حياتهم ومهاراتهم المهنية كإدارة الأعمال والدعم النفسي والتدريس وغيرها."""
[:400], #400 UPPER LIMIT characters allowed 
                thumbnail=CHANNEL_THUMBNAIL,
                author=AUTHOR,
                language=CHANNEL_LANGUAGE,
                children=[],
                license=LICENSE,
            )

        grades = Grades()
        grades.load("resources_ar.json", auto_parse=True)
        return channel_tree, grades

    def scrape(self, args, options):
        download_video = options.get('--download-video', "1")
        load_video_list = options.get('--load-video-list', "0")

        if int(download_video) == 0:
            global DOWNLOAD_VIDEOS
            DOWNLOAD_VIDEOS = False

        if int(load_video_list) == 1:
            global LOAD_VIDEO_LIST
            LOAD_VIDEO_LIST = True

        global channel_tree
        channel_tree, grades = self.lessons()
        base_path = [DATA_DIR]
        base_path = build_path(base_path)

        for subject in grades:
            for lesson in subject.lessons:
                lesson.download(download=DOWNLOAD_VIDEOS, base_path=base_path)
                subject.add_node(lesson)
            channel_tree["children"].append(subject.to_node())
        
        return channel_tree

    def write_tree_to_json(self, channel_tree):
        scrape_stage = os.path.join(OrangeNGOChef.TREES_DATA_DIR, 
                                self.RICECOOKER_JSON_TREE)
        write_tree_to_json_tree(scrape_stage, channel_tree)


# CLI
################################################################################
if __name__ == '__main__':
    chef = OrangeNGOChef()
    chef.main()
