from json2node import Node, ABCSubjectNode, ABCLessonNode
import youtube_dl
import json
from le_utils.constants import content_kinds, file_formats
import hashlib
import logging
from pressurecooker.youtube import YouTubeResource
import os
from utils import file_exists


LOGGER = logging.getLogger()
__logging_handler = logging.StreamHandler()
LOGGER.addHandler(__logging_handler)
LOGGER.setLevel(logging.INFO)


class SubjectNode(ABCSubjectNode):
    
    def auto_generate_lessons(self, urls, save_url_to=None, load_video_list=False):
        for url in urls:
            try:
                youtube = YouTubeResourceNode(url)
            except(youtube_dl.utils.DownloadError, youtube_dl.utils.ContentTooShortError,
                    youtube_dl.utils.ExtractorError) as e:
                    LOGGER.error(url)
            else:
                playlist_urls = youtube.playlist_name_links(save_url_to, load_video_list)
                if len(playlist_urls) > 0:
                    for title, url in playlist_urls:
                        lesson = LessonNode(title=title, source_id=url, 
                            lang=self.lang, author=self.author, license=self.license)
                        self.lessons.append(lesson)
                else:
                    # it is a normal url not a play list url
                    info = youtube.get_resource_info()
                    title = info["title"]
                    lesson = LessonNode(title=title, source_id=url, 
                        lang=self.lang, author=self.author, license=self.license)
                    self.lessons.append(lesson)


class LessonNode(ABCLessonNode):

    def download(self, download=True, base_path=None):
        youtube = YouTubeResourceNode(self.source_id, lang=self.lang, 
            author=self.author, license=self.license)
        youtube.download(download, base_path)
        return youtube


class YouTubeResourceNode(YouTubeResource, Node):
    def __init__(self, source_id, name=None, type_name="Youtube", lang="ar",
            embeded=False, section_title=None, author=None, license=None):
        if embeded is True:
            source_id = YouTubeResourceNode.transform_embed(source_id)
        else:
            source_id = self.clean_url(source_id)
        YouTubeResource.__init__(self, source_id)
        Node.__init__(self, title=None, source_id=source_id, lang=lang, 
            author=author, license=license)
        LOGGER.info("    + Resource Type: {}".format(type_name))
        LOGGER.info("    - URL: {}".format(self.source_id))
        self.filename = None
        self.type_name = type_name
        self.filepath = None
        self.name = name
        self.section_title = section_title
        self.file_format = file_formats.MP4
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
                LOGGER.info("Key Error: {} key does not found".format(e))
        return playlist_videos_url

    def playlist_name_links(self, base_path, load_video_list):
        name_url = []
        source_id_hash = hashlib.sha1(self.source_id.encode("utf-8")).hexdigest()
        videos_url_path = os.path.join(base_path, "{}.json".format(source_id_hash))

        if file_exists(videos_url_path) and load_video_list is True:
            with open(videos_url_path, "r") as f:
                name_url = json.load(f)
        else:
            for url in self.playlist_links():
                youtube = YouTubeResourceNode(url)
                info = youtube.get_resource_info()
                name_url.append((info["title"], url))
            if len(name_url) > 0:
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

    def to_dict(self):
        if self.filepath is not None:
            files = [dict(file_type=content_kinds.VIDEO, path=self.filepath)]
            files += self.subtitles_dict()
            node = dict(
                kind=content_kinds.VIDEO,
                source_id=self.source_id,
                title=self.title,
                description='',
                author=self.author,
                files=files,
                language=self.lang,
                license=self.license
            )
            return node
