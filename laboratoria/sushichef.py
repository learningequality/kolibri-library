#!/usr/bin/env python

from bs4 import BeautifulSoup
import codecs
from collections import defaultdict
import copy
from git import Repo
import glob
from le_utils.constants import licenses, content_kinds, file_formats
import hashlib
import json
import logging
import markdown2
import ntpath
import os
import pafy
from pathlib import Path
import re
import requests
from ricecooker.classes.licenses import get_license
from ricecooker.chefs import JsonTreeChef
from ricecooker.utils import downloader, html_writer
from ricecooker.utils.caching import CacheForeverHeuristic, FileCache, CacheControlAdapter
from ricecooker.utils.jsontrees import write_tree_to_json_tree, SUBTITLES_FILE
import time
from urllib.error import URLError
from urllib.parse import urljoin
from utils import if_dir_exists, get_name_from_url, clone_repo, build_path
from utils import if_file_exists, get_video_resolution_format, remove_links
from utils import get_name_from_url_no_ext, get_node_from_channel, get_level_map
from utils import remove_iframes, get_confirm_token, save_response_content
import youtube_dl   


BASE_URL = "https://github.com/Laboratoria/"
REPOSITORY_URL = {
    "curricula-js": urljoin(BASE_URL, "curricula-js.git"),
    "curricula-ux": urljoin(BASE_URL, "curricula-ux.git"),
    "curricula-mobile": urljoin(BASE_URL, "curricula-mobile.git"),
    "executive-training": urljoin(BASE_URL, "executive-training.git")
}
DATA_DIR = "chefdata"
COPYRIGHT_HOLDER = "Laboratoria"
COUNTER_TITLE_KEYS = defaultdict(int)

LOGGER = logging.getLogger()
__logging_handler = logging.StreamHandler()
LOGGER.addHandler(__logging_handler)
LOGGER.setLevel(logging.INFO)

DOWNLOAD_VIDEOS = True

sess = requests.Session()
cache = FileCache('.webcache')
basic_adapter = CacheControlAdapter(cache=cache)
forever_adapter = CacheControlAdapter(heuristic=CacheForeverHeuristic(), cache=cache)
sess.mount('http://', basic_adapter)
sess.mount(BASE_URL, forever_adapter)



class HTMLApp(object):
    def __init__(self, index):
        self.page = index
        self.subdirs = self.get_subdirs()
        self.subject = self.page.subject()
        self.lang = "es"
        self.filepath = None

    def get_subdirs(self):
        dirs = []
        pattern = re.compile('\d{1,2}\-')
        if self.page.content is None:
            return dirs
        links = self.page.content.find_all(lambda tag: tag.name == "a" and\
            tag.findParent("h3"), href=pattern)
        for a in links:
            dirs.append(a["href"])
        return dirs

    def write_index(self):
        path = [DATA_DIR] + self.page.pwd[2:]
        filename = self.page.filepath.split("/")[-1]
        self.filepath = os.path.join(build_path(path), "{}.zip".format(filename))
        with html_writer.HTMLWriter(self.filepath, "w") as zipper:
            images = self.page.get_images()
            content = copy.copy(self.page.content)
            remove_links(content)
            remove_iframes(content)
            zipper.write_index_contents(str(content))
        return images

    def write_css_js(self):
        with html_writer.HTMLWriter(self.filepath, "a") as zipper, open("chefdata/styles.css") as f:
            content = f.read()
            zipper.write_contents("styles.css", content, directory="css/")

        with html_writer.HTMLWriter(self.filepath, "a") as zipper, open("chefdata/highlight_default.css") as f:
            content = f.read()
            zipper.write_contents("highlight_default.css", content, directory="css/")

        with html_writer.HTMLWriter(self.filepath, "a") as zipper, open("chefdata/scripts.js") as f:
            content = f.read()
            zipper.write_contents("scrips.js", content, directory="js/")

    def write_images(self, images):
        with html_writer.HTMLWriter(self.filepath, "a") as zipper:
            for img_src, img_filename in images.items():
                try:
                    zipper.write_url(img_src, img_filename, directory=self.page.extra_files_path)
                except (requests.exceptions.HTTPError, requests.exceptions.SSLError):
                    pass

    def write_pdfs(self):
        path = [DATA_DIR] + self.page.pwd[2:]
        path = build_path(path)
        urllist = UrlPDFList("pdf_white_list.json")
        for pdf in self.page.get_pdfs():
            if urllist.valid_url(pdf.source_id):
                pdf.download(path)
                yield pdf.to_node()

    def write_videos(self):
        path = [DATA_DIR] + self.page.pwd[2:]
        path = build_path(path)
        urllist = UrlVideoList("youtube_white_list.json")
        for video in self.page.get_videos():
            if urllist.valid_url(video.source_id) or video.is_valid:
                video.download(download=DOWNLOAD_VIDEOS, base_path=path)
                yield video.to_node()

    def topic_node(self):
        return dict(
            kind=content_kinds.TOPIC,
            source_id=self.page.url,
            title=self.page.title,
            description="",
            license=None,
            lang=self.lang,
            children=[]
        )

    def to_node(self):
        if self.filepath is not None:
            filename = self.page.filepath.split("/")[-1]
            return dict(
                kind=content_kinds.HTML5,
                source_id=urljoin(self.page.url, filename),
                title=self.page.title,
                description="",
                thumbnail=None,
                author="",
                files=[dict(
                    file_type=content_kinds.HTML5,
                    path=self.filepath
                )],
                language=self.lang,
                license=get_license(licenses.CC_BY, copyright_holder=COPYRIGHT_HOLDER).as_dict())


class MarkdownReader(object):
    def __init__(self, filepath, extra_files_path="", title=None):
        self.filepath = filepath
        self.copyright = None
        self.extra_files_path = extra_files_path
        self.pwd = self.filepath.split("/")[:-1]
        self.copyright = None
        self.title = self.filepath.split("/")[-1] if title is None else title 
        self.url = self.pwd2url()
        self.content = None
        self.lang = "es"

    @property
    def title(self):
        return self._title

    @title.setter
    def title(self, v):
        pattern = r"^\d{2}-"
        match = re.match(pattern, v)

        if match:
            clean_title = re.sub(pattern, "", v).title().replace("-", " ")
            counter = self.level_counter(clean_title)
            if counter > 1:
                title_subfix = str(counter)
            else:
                title_subfix = ""
            self._title = "{} {}".format(clean_title, title_subfix).strip()
        else:
            self._title = v

    def level_counter(self, clean_title):
        levels = self.filepath.replace("README.md", "")
        path_str = "/".join(levels.split("/")[:-1]) + clean_title
        key = hashlib.sha1(path_str.encode("utf-8")).hexdigest()
        COUNTER_TITLE_KEYS[key] += 1
        return COUNTER_TITLE_KEYS[key]

    def pwd2url(self):
        return urljoin(BASE_URL, "/".join(self.pwd[2:]+[""]))

    def exists(self):
        return if_file_exists(self.filepath)

    def subject(self):
        return self.pwd[-1]

    def load_content(self):
        self.content = self.parser(self.to_html())
        if self.content is not None:
            self.get_copyright()
            self.get_h1_title()

    def to_html(self):
        try:
            with codecs.open(self.filepath, mode="r", encoding="utf-8") as input_file:
                text = input_file.read()
                html = markdown2.markdown(text, extras=["tables", "fenced-code-blocks"])
        except FileNotFoundError as e:
            LOGGER.info("Error: {}".format(e))
        else:
            return '<html><head><meta charset="utf-8"><link rel="stylesheet" href="css/styles.css"><link rel="stylesheet" href="css/highlight_default.css"></head><body><div class="main-content-with-sidebar">{}</div><script src="js/scripts.js"></script></body></html>'.format(html)

    def parser(self, document):
        if document is not None:
            return BeautifulSoup(document, 'html.parser')

    def get_images(self):
        images = {}
        for img in self.content.findAll("img"):
            if "src" in img.attrs:
                if img["src"].startswith("/"):
                    img_src = urljoin(BASE_URL, img["src"])
                elif not img["src"].startswith("http"):
                    img_src = urljoin(BASE_URL, "/".join(self.pwd[2:]), img["src"])
                else:
                    img_src = img["src"]
            
                if img_src not in images and img_src:
                    filename = get_name_from_url(img_src)
                    img["src"] = self.extra_files_path+filename
                    images[img_src] = filename
        return images

    def get_pdfs(self):
        unique_urls = set([])
        files = self.get_data_fn([lambda tag: tag.name == "a" and tag.attrs.get("href", "").endswith(".pdf")], 
            {}, "href", File, unique_urls)
        files.extend(self.get_data_fn([lambda tag: tag.name == "iframe" and tag.attrs.get("src", "").endswith(".pdf")], {}, "src", File, unique_urls))
        pattern = re.compile('drive\.google\.com')
        files.extend(self.get_data_fn(["a"], {"href": pattern}, "href", FileDrive, unique_urls))
        return files

    def get_videos(self):
        unique_urls = set([])
        pattern = re.compile('youtube.com|youtu\.be')
        videos = self.get_data_fn(["a"], {"href": pattern}, "href", YouTubeResource, 
            unique_urls)
        videos.extend(self.get_data_fn(["iframe"], {"src": pattern}, "src", 
            YouTubeResource, unique_urls, embeded=True))
        pattern = re.compile('laboratoria.wistia.com')
        videos.extend(self.get_data_fn(["a"], {"href": pattern}, "href", 
            WistiaVideoResource, unique_urls))
        return videos

    def get_data_fn(self, fn_args, fn_kwargs, attr, class_, unique_urls, **extra_params):        
        data = []
        for tag in self.content.find_all(*fn_args, **fn_kwargs):
            url = tag.get(attr, None)
            LOGGER.info("Tag: {} source url {}".format(tag.name, url))
            if url is not None:
                data_obj = class_(url, lang="es", **extra_params)
                if data_obj.source_id not in unique_urls:
                    data.append(data_obj)
                    unique_urls.add(data_obj.source_id)
        return data

    def read_dir(self):
        try:
            path = "/".join(self.pwd)
            if if_dir_exists(path):
                return sorted([elem for elem in os.listdir(path) 
                    if if_dir_exists(os.path.join(path, elem)) and\
                    not elem.startswith(".")])
            else:
                return []
        except FileNotFoundError as e:
            LOGGER.info("Error: {}".format(e))
            return []

    def get_copyright(self):
        h2 = self.content.find(lambda tag: tag.name == "h2" and\
            tag.text.find("Copyright") != -1)
        if h2 is not None:
            self.copyright = h2.findNext('p')

    def get_h1_title(self):
        h1 = self.content.find("h1")
        if h1 is not None:
            self.title = h1.text

    def get_levels(self):
        prefix = BASE_URL
        levels = []
        for level in self.pwd[2:-1]:
            url = urljoin(prefix, level+"/")
            levels.append(url)
            prefix = url
        return levels

    def write(self, channel_tree):
        htmlapp = HTMLApp(self)
        images = htmlapp.write_index()
        htmlapp.write_images(images)
        htmlapp.write_css_js()
        htmlapp_node = self._set_node(htmlapp, channel_tree)
        for node in htmlapp.write_pdfs():
            if node is not None:
                htmlapp_node["children"].append(node)
        for node in htmlapp.write_videos():
            if node is not None:
                htmlapp_node["children"].append(node)
        return htmlapp_node

    def _set_node(self, htmlapp, channel_tree):
        topic_node = get_node_from_channel(self.url, channel_tree)
        if topic_node is None:
            topic_node = htmlapp.topic_node()
            levels = self.get_levels()
            if len(levels) > 0:
                parent = get_level_map(channel_tree, levels)
            else:
                parent = channel_tree
            if parent is not None:
                parent["children"].append(topic_node)
            else:
                LOGGER.info("Element {} does not found in channel tree".format(self.url))

        htmlapp_node = htmlapp.to_node()
        if htmlapp_node is not None:
            topic_node["children"].append(htmlapp_node)
        return topic_node

    def add_empty_node(self, channel_tree):
        htmlapp = HTMLApp(self)
        return self._set_node(htmlapp, channel_tree)
        

class YouTubeResource(object):
    def __init__(self, source_id, type_name="Youtube", lang="en", embeded=False):
        LOGGER.info("Resource Type: "+type_name)
        self.filename = None
        self.type_name = type_name
        self.filepath = None
        if embeded is True:
            self.source_id = YouTubeResource.transform_embed(source_id)
        else:
            self.source_id = self.clean_url(source_id)
        self.file_format = file_formats.MP4
        self.lang = lang
        self.is_valid = False

    def clean_url(self, url):
        if url[-1] == "/":
            url = url[:-1]
        return url.strip()

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

    def get_video_info(self, download_to=None, subtitles=True):
        ydl_options = {
                'writesubtitles': subtitles,
                'allsubtitles': subtitles,
                'no_warnings': True,
                'restrictfilenames':True,
                'continuedl': True,
                'quiet': False,
                'format': "bestvideo[height<={maxheight}][ext=mp4]+bestaudio[ext=m4a]/best[height<={maxheight}][ext=mp4]".format(maxheight='480'),
                'outtmpl': '{}/%(id)s'.format(download_to),
                'noplaylist': False
            }

        with youtube_dl.YoutubeDL(ydl_options) as ydl:
            try:
                ydl.add_default_info_extractors()
                info = ydl.extract_info(self.source_id, download=(download_to is not None))
                return info
            except(youtube_dl.utils.DownloadError, youtube_dl.utils.ContentTooShortError,
                    youtube_dl.utils.ExtractorError) as e:
                LOGGER.info('An error occured ' + str(e))
                LOGGER.info(self.source_id)
            except KeyError as e:
                LOGGER.info(str(e))

    def subtitles_dict(self):
        subs = []
        video_info = self.get_video_info()
        if video_info is not None:
            video_id = video_info["id"]
            if 'subtitles' in video_info:
                subtitles_info = video_info["subtitles"]
                for language in subtitles_info.keys():
                    subs.append(dict(file_type=SUBTITLES_FILE, youtube_id=video_id, language=language))
        return subs

    #youtubedl has some troubles downloading videos in youtube,
    #sometimes raises connection error
    #for that I choose pafy for downloading
    def download(self, download=True, base_path=None):
        if not "watch?" in self.source_id or "/user/" in self.source_id or\
            download is False:
            return

        download_to = build_path([base_path, 'videos'])
        for i in range(4):
            try:
                info = self.get_video_info(download_to=download_to, subtitles=False)
                if info is not None:
                    LOGGER.info("Video resolution: {}x{}".format(info.get("width", ""), info.get("height", "")))
                    self.filepath = os.path.join(download_to, "{}.mp4".format(info["id"]))
                    self.filename = info["title"]
                    if self.filepath is not None and os.stat(self.filepath).st_size == 0:
                        LOGGER.info("Empty file")
                        self.filepath = None
            except (ValueError, IOError, OSError, URLError, ConnectionResetError) as e:
                LOGGER.info(e)
                LOGGER.info("Download retry")
                time.sleep(.8)
            except (youtube_dl.utils.DownloadError, youtube_dl.utils.ContentTooShortError,
                    youtube_dl.utils.ExtractorError, OSError) as e:
                LOGGER.info("An error ocurred, may be the video is not available.")
                return
            except OSError:
                return
            else:
                return

    def to_node(self):
        if self.filepath is not None:
            files = [dict(file_type=content_kinds.VIDEO, path=self.filepath)]
            files += self.subtitles_dict()
            node = dict(
                kind=content_kinds.VIDEO,
                source_id=self.source_id,
                title=self.filename,
                description='',
                files=files,
                language=self.lang,
                license=get_license(licenses.CC_BY_SA, copyright_holder=COPYRIGHT_HOLDER).as_dict())
            return node


class LocalVideoResource(object):
    def __init__(self, source_id, type_name="Local Video", lang="es"):
        LOGGER.info("Resource Type: "+type_name)
        self.source_id = source_id
        self.file_format = file_formats.MP4
        self.lang = lang        
        self.filename = None
        self.type_name = type_name
        self.filepath = None
        self.is_valid = True

    def download(self, download=True, base_path=None):
        if download is False:
            return
        download_to = build_path([base_path, 'videos'])
        response = requests.get(self.source_id, stream=True)
        if response.headers.get("content-type") != 'video/mp4':
            return
        self.filename = get_name_from_url(self.source_id)
        self.filepath = os.path.join(download_to, "{}.mp4".format(self.filename))
        if if_file_exists(self.filepath):
            LOGGER.info("Video already downloaded {}".format(self.filepath))
        else:
            with open(self.filepath, 'wb') as f:
                LOGGER.info("   - Downloading {}".format(self.source_id))
                save_response_content(response, self.filepath)
        if self.filepath is not None and os.stat(self.filepath).st_size == 0:
            LOGGER.info("Empty file")
            self.filepath = None

    def to_node(self):
        if self.filepath is not None:
            node = dict(
                kind=content_kinds.VIDEO,
                source_id=self.source_id,
                title=self.filename,
                description='',
                files = [dict(file_type=content_kinds.VIDEO, path=self.filepath)],
                language=self.lang,
                license=get_license(licenses.CC_BY_SA, copyright_holder=COPYRIGHT_HOLDER).as_dict())
            return node


class WistiaVideoResource(LocalVideoResource):
    def __init__(self, *args, **kwargs):
        super(WistiaVideoResource, self).__init__(*args, **kwargs)
        self.get_url_from_embeded()
        
    def get_url_from_embeded(self):
        r = requests.get(self.source_id)
        parser = BeautifulSoup(r.content, 'html.parser')
        pattern = re.compile("videoUrl=")
        meta = parser.find("meta", content=pattern)
        if meta is not None:
            meta_content = meta.get("content", "")
            init_index = meta_content.find("videoUrl=")
            end_index = meta_content[init_index:].find("&")
            self.source_id = meta_content[init_index+len("videoUrl="):end_index+init_index]


class File(object):
    def __init__(self, source_id, lang="en", lincese="", drive=True):
        self.filename = get_name_from_url(source_id)
        self.source_id = urljoin(BASE_URL, source_id) if source_id.startswith("/") else source_id
        self.filepath = None
        self.lang = lang
        self.license = get_license(licenses.CC_BY_SA, copyright_holder=COPYRIGHT_HOLDER).as_dict()

    def is_pdf(self):
        response = sess.get(self.source_id)
        content_type = response.headers.get('content-type')
        if content_type is not None and 'application/pdf' in content_type:
            return response

    def download(self, base_path):
        PDFS_DATA_DIR = build_path([base_path, 'pdfs'])
        try:
            response = self.is_pdf()
            if response is not None:
                self.filepath = os.path.join(PDFS_DATA_DIR, self.filename)
                save_response_content(response, self.filepath)
                LOGGER.info("   - Get file: {}".format(self.filename))
        except requests.exceptions.HTTPError as e:
            LOGGER.info("Error: {}".format(e))
        except requests.exceptions.ConnectionError:
            ### this is a weird error, may be it's raised when the webpage
            ### is slow to respond requested resources
            LOGGER.info("Connection error, the resource will be scraped in 5s...")
        except requests.exceptions.ReadTimeout as e:
            LOGGER.info("Error: {}".format(e))
        except requests.exceptions.TooManyRedirects as e:
            LOGGER.info("Error: {}".format(e))

    def to_node(self):
        if self.filepath is not None:
            node = dict(
                kind=content_kinds.DOCUMENT,
                source_id=self.source_id,
                title=self.filename,
                description='',
                files=[dict(
                    file_type=content_kinds.DOCUMENT,
                    path=self.filepath
                )],
                language=self.lang,
                license=self.license)
            return node


class FileDrive(File):
    def __init__(self, source_id, lang="en", lincese="", drive=True):
        self.source_id = source_id.strip()
        self.id = self.get_id_from_url()
        self.filename = "googledrive_{}.pdf".format(self.id)
        self.filepath = None
        self.lang = lang
        self.license = get_license(licenses.CC_BY_SA, copyright_holder=COPYRIGHT_HOLDER).as_dict()

    def get_id_from_url(self):
        url = self.source_id
        if url.find("file/d/") != -1:
            index = url.find("file/d/")
            end_index = index + len("file/d/") + url[index+len("file/d/"):].find("/")
            return url[index+len("file/d/"):end_index].strip()
        elif url.find("?id=") != -1:
            index = url.find("?id=")
            return url[index+len("?id="):].strip()

    def is_pdf(self):
        URL = "https://docs.google.com/uc?export=download"
        response = sess.get(URL, params={'id': self.id}, stream=True)
        token = get_confirm_token(response)
        if token:
            params = {'id':id, 'confirm':token}
            response = sess.get(URL, params=params, stream=True)
        content_type = response.headers.get('content-type')
        if content_type is not None and 'application/pdf' in content_type:
            return response

    def download(self, base_path):
        PDFS_DATA_DIR = build_path([base_path, 'pdfs'])
        try:
            response = self.is_pdf()
            if response is not None:
                self.filepath = os.path.join(PDFS_DATA_DIR, self.filename)
                save_response_content(response, self.filepath)
                LOGGER.info("   - Get file: {}".format(self.filename))
        except requests.exceptions.HTTPError as e:
            LOGGER.info("Error: {}".format(e))
        except requests.exceptions.ConnectionError:
            ### this is a weird error, may be it's raised when the webpage
            ### is slow to respond requested resources
            LOGGER.info("Connection error, the resource will be scraped in 5s...")
        except requests.exceptions.ReadTimeout as e:
            LOGGER.info("Error: {}".format(e))
        except requests.exceptions.TooManyRedirects as e:
            LOGGER.info("Error: {}".format(e))


class LocalJSFile(object):
    def __init__(self, source_id, lang="en", lincese=""):
        self.filename = get_name_from_url(source_id)
        self.pwd = source_id.split("/")[:-1]
        self.source_id = self.pwd2url()
        self.filepath = os.path.join(*self.pwd, self.filename)
        self.lang = lang
        self.license = get_license(licenses.CC_BY_SA, copyright_holder=COPYRIGHT_HOLDER).as_dict()
        self.zip_filepath = None

    def pwd2url(self):
        return urljoin(BASE_URL, "/".join(self.pwd[2:]+[self.filename]))

    def write_index(self):
        path = [DATA_DIR] + self.pwd[2:]
        self.zip_filepath = os.path.join(build_path(path), "{}.zip".format(self.filename))
        with html_writer.HTMLWriter(self.zip_filepath, "w") as zipper, open(self.filepath, 'r') as f:
            zipper.write_index_contents('<html><head><meta charset="utf-8"></head><body>'+f.read().replace("\n", "<br>")+"</body></html>")

    def to_node(self):
        if self.zip_filepath is not None:
            return dict(
                kind=content_kinds.HTML5,
                source_id=self.source_id,
                title=self.filename,
                description="",
                thumbnail=None,
                author="",
                files=[dict(
                    file_type=content_kinds.HTML5,
                    path=self.zip_filepath
                )],
                language=self.lang,
                license=get_license(licenses.CC_BY, copyright_holder=COPYRIGHT_HOLDER).as_dict())


def folder_walker(repo_dir, dirs, channel_tree):
    for directory in dirs:
        LOGGER.info("--- {} {}".format(repo_dir, directory))
        md_files = get_md_files(os.path.join(repo_dir, directory))
        if len(md_files) > 0:
            for filepath in md_files:
                md = MarkdownReader(filepath, extra_files_path="files/")
                md.load_content()
                htmlapp_node = md.write(channel_tree)
        else:
            md = MarkdownReader(os.path.join(repo_dir, directory, "README.md"), 
                extra_files_path="files/", title=directory)
            htmlapp_node = md.add_empty_node(channel_tree)

        js_files = get_js_files(os.path.join(repo_dir, directory))
        for js_fileobj in js_files:
            js_fileobj.write_index()
            htmlapp_node["children"].append(js_fileobj.to_node())
        subdirs = md.read_dir()
        folder_walker(os.path.join(repo_dir, directory), subdirs, channel_tree)


def folder_walker_items(repo_dir, dirs, urllist, attr='get_pdfs'):
    for directory in dirs:
        LOGGER.info("--- {} {}".format(repo_dir, directory))
        files = get_md_files(os.path.join(repo_dir, directory))
        if len(files) > 0:
            for filepath in files:
                md = MarkdownReader(filepath, extra_files_path="files/")
                md.load_content()
                urllist.add_batch(getattr(md, attr)())#md.get_pdfs())
        else:
            md = MarkdownReader(os.path.join(repo_dir, directory, "README.md"), 
                extra_files_path="files/", title=directory)
        subdirs = md.read_dir()
        folder_walker_items(os.path.join(repo_dir, directory), subdirs, urllist, attr=attr)



class UrlList(object):
    def __init__(self, filename):
        self.filename = os.path.join(DATA_DIR, filename)
        self.load()
        self.new_elem = False

    def load(self):
        if if_file_exists(self.filename):
            #try:
            with open(self.filename, "r") as f:
                self.urls = json.load(f)
            #except json.decoder.JSONDecodeError:
            #    self.urls = {}
        else:
            self.urls = {}

    def save(self):
        if self.new_elem == True:
            with open(self.filename, "w") as f:
                json.dump(self.urls, f, indent=2, sort_keys=True)

    def valid_url(self, url):
        try:
            return self.urls[url] == 1
        except KeyError:
            return False


class UrlPDFList(UrlList):
    def add_batch(self, file_objs):
        for file_obj in file_objs:
            if not file_obj.source_id in self.urls and file_obj.is_pdf() is not None:
                self.urls[file_obj.source_id] = 0
                self.new_elem = True


class UrlVideoList(UrlList):
    def add_batch(self, video_objs):
        for video_obj in video_objs:
            if not video_obj.source_id in self.urls:
                self.urls[video_obj.source_id] = 0
                self.new_elem = True


def get_md_files(path):
    all_md_files = sorted(glob.glob(os.path.join(path, "*.md")))
    md_files = []
    readme = None
    #this put the readme file in the first place of the list to read the title
    #and save it in the topic node. If README does not exist the title is read 
    #from the next file or is set form the current directory name
    for i, filepath in enumerate(all_md_files):
        if filepath.endswith("README.md"):
            readme = filepath
            all_md_files.pop(i)
            break

    for filepath in all_md_files:
        if not filepath.endswith("CONTRIBUTING.md"):
            md_files.append(filepath)

    if readme is not None:
        return [readme] + md_files
    return md_files


def get_js_files(path):
    js_files = []
    for js_file in glob.glob(os.path.join(path, "*.js")):
        js_files.append(LocalJSFile(js_file))
    return js_files


#When a node has only one child and this child it's a object (file, video, etc),
#this is moved to an upper level
def clean_leafs_nodes_plus(channel_tree):
    children = channel_tree.get("children", None)
    if children is None:
        return
    elif len(children) == 1 and not "children" in children[0]:
        return channel_tree["children"][0]
    elif len(children) == 0:
        return -1
    else:
        del_nodes = []
        for i, node in enumerate(children):
            leaf_node = clean_leafs_nodes_plus(node)
            if leaf_node is not None and leaf_node != -1:
                if leaf_node["source_id"].endswith(".js"):
                    levels = leaf_node["source_id"].split("/")
                    parent_dir = levels[-2] #dirname
                    leaf_node["title"] = "{}_{}".format(parent_dir, leaf_node["title"])
                children[i] = leaf_node
            elif leaf_node == -1:
                del children[i]
            elif leaf_node is None:
                try:
                    if len(node["children"]) == 0:
                        del children[i]
                    elif len(node["children"]) == 1:
                        children[i] = node["children"][0]
                except KeyError:
                    pass


class LaboratoriaChef(JsonTreeChef):
    HOSTNAME = BASE_URL
    TREES_DATA_DIR = os.path.join(DATA_DIR, 'trees')
    SCRAPING_STAGE_OUTPUT_TPL = 'ricecooker_json_tree.json'
    LICENSE = get_license(licenses.CC_BY_SA, copyright_holder=COPYRIGHT_HOLDER).as_dict()
    THUMBNAIL = ""

    def __init__(self):
        build_path([LaboratoriaChef.TREES_DATA_DIR])
        self.scrape_stage = os.path.join(LaboratoriaChef.TREES_DATA_DIR, 
                                LaboratoriaChef.SCRAPING_STAGE_OUTPUT_TPL)
        super(LaboratoriaChef, self).__init__()

    def pre_run(self, args, options):
        css = os.path.join(os.path.dirname(os.path.realpath(__file__)), "chefdata/styles.css")
        js = os.path.join(os.path.dirname(os.path.realpath(__file__)), "chefdata/scripts.js")
        if not if_file_exists(css) or not if_file_exists(js):
            LOGGER.info("Downloading styles")
            self.download_css_js()
        self.scrape(args, options)

    def scrape(self, args, options):
        LANG = 'es'
        global channel_tree
        channel_tree = dict(
                source_domain=LaboratoriaChef.HOSTNAME,
                source_id=BASE_URL,
                title='Laboratoria',
                description="""Trabajamos para ser la principal fuente de talento tech femenino de América Latina para el mundo, transformando el futuro de miles de mujeres y las empresas que las reciben."""[:400], #400 UPPER LIMIT characters allowed 
                thumbnail=None,
                language=LANG,
                children=[],
                license=LaboratoriaChef.LICENSE,
            )

        path = build_path([DATA_DIR, "git"])
        repos = options.get('--repo', None)
        download_video = options.get('--download-video', "1")
        if repos is None:
            repos = REPOSITORY_URL.keys()
        else:
            repos = [repos]

        if int(download_video) == 0:
            global DOWNLOAD_VIDEOS
            DOWNLOAD_VIDEOS = False

        url_pdf_list = UrlPDFList("pdf_white_list.json")
        url_v_list = UrlVideoList("youtube_white_list.json")
        for repo in repos:
            repo_dir = os.path.join(path, repo)
            clone_repo(REPOSITORY_URL[repo], repo_dir)
            readme = MarkdownReader(os.path.join(repo_dir, "README.md"), extra_files_path="files/")
            folder_walker_items(repo_dir, readme.read_dir(), url_pdf_list, attr='get_pdfs')
            folder_walker_items(repo_dir, readme.read_dir(), url_v_list, attr='get_videos')
            url_pdf_list.save()
            url_v_list.save()

        #the counter is reset from previous ingest
        global COUNTER_TITLE_KEYS
        COUNTER_TITLE_KEYS = defaultdict(int)
        for repo in repos:
            repo_dir = os.path.join(path, repo)
            self._build_scraping_json_tree(channel_tree, repo_dir)
        self.write_tree_to_json(channel_tree, "en")

    def write_tree_to_json(self, channel_tree, lang):
        write_tree_to_json_tree(self.scrape_stage, channel_tree)

    def _build_scraping_json_tree(self, channel_tree, repo_dir):
        readme = MarkdownReader(os.path.join(repo_dir, "README.md"), extra_files_path="files/")
        readme.load_content()
        readme.write(channel_tree)
        COPYRIGHT_HOLDER = readme.copyright
        dirs = readme.read_dir()
        if "00-template" in dirs:
            dirs = dirs[1:] #skiped 00-template dir
        folder_walker(repo_dir, dirs, channel_tree)
        clean_leafs_nodes_plus(channel_tree)

    def download_css_js(self):
        r = requests.get("https://raw.githubusercontent.com/learningequality/html-app-starter/master/css/styles.css")
        with open("chefdata/styles.css", "wb") as f:
            f.write(r.content)

        r = requests.get("https://raw.githubusercontent.com/richleland/pygments-css/master/default.css")
        with open("chefdata/highlight_default.css", "w") as f:
            f.write(r.content.decode("utf-8").replace(".highlight", ".codehilite"))

        r = requests.get("https://raw.githubusercontent.com/learningequality/html-app-starter/master/js/scripts.js")
        with open("chefdata/scripts.js", "wb") as f:
            f.write(r.content)
        
def test():
    channel_tree = dict(
        source_domain="",
        source_id=BASE_URL,
        title='Laboratoria',
        description="""Trabajamos para ser la principal fuente de talento tech femenino de América Latina para el mundo, transformando el futuro de miles de mujeres y las empresas que las reciben."""[:400], #400 UPPER LIMIT characters allowed 
        thumbnail=None,
        language="es",
        children=[],
        license="",
    )

    #filepath = "chefdata/git/curricula-js/09-paradigms/01-paradigms/01-overview/README.md"
    filepath = "chefdata/git/curricula-js/14-chatbot/02-getting-started/02-ms-bot-framework/README.md"
    md = MarkdownReader(filepath, extra_files_path="files/")
    md.load_content()
    htmlapp_node = md.write(channel_tree)
    print(htmlapp_node)


# CLI: This code will run when `souschef.py` is called on the command line
################################################################################
if __name__ == '__main__':
    chef = LaboratoriaChef()
    chef.main()
    #test()
