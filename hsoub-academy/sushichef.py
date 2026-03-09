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
import time
from urllib.error import URLError
from urllib.parse import urljoin
from utils import dir_exists, get_name_from_url, clone_repo, build_path
from utils import file_exists, get_video_resolution_format, remove_links
from utils import get_name_from_url_no_ext, get_node_from_channel, get_level_map
from utils import remove_iframes, get_confirm_token, save_response_content
from utils import link_to_text, remove_scripts, save_thumbnail
import youtube_dl
import uuid
import urllib.parse as urlparse


BASE_URL = "https://academy.hsoub.com/"

DATA_DIR = "chefdata"
COPYRIGHT_HOLDER = "Hsoub Academy"
LICENSE = get_license(licenses.CC_BY_NC_SA, 
        copyright_holder=COPYRIGHT_HOLDER).as_dict()
AUTHOR = "Hsoub Academy"

LOGGER = logging.getLogger()
__logging_handler = logging.StreamHandler()
LOGGER.addHandler(__logging_handler)
LOGGER.setLevel(logging.INFO)

DOWNLOAD_VIDEOS = True

sess = requests.Session()


# Run constants
################################################################################
CHANNEL_NAME = "Hsoub Academy"                              # Name of channel
CHANNEL_SOURCE_ID = "sushi-chef-hsoub-academy"              # Channel's unique id
CHANNEL_DOMAIN = BASE_URL                                   # Who is providing the content
CHANNEL_LANGUAGE = "ar"                                     # Language of channel
CHANNEL_DESCRIPTION = None                                  # Description of the channel (optional)
CHANNEL_THUMBNAIL = None                                    # Local path or url to image file (optional)

# Additional constants
################################################################################

data_nav = OrderedDict([
("Lessons and Articles", "دروس ومقالات"),
("Books and Resources",  "كتب وملفات"),
("Questions and Answers", "أسئلة وأجوبة")
])


def browser_resources():
    page = download(BASE_URL)
    ul01 = page.find(lambda tag: tag.name == "ul" and tag.attrs.get("data-role", "") == "primaryNavBar")
    for name, name_ar in data_nav.items():
        LOGGER.info("- Category: {} {}".format(name, name_ar))
        li = ul01.find(lambda tag: tag.name == "a" and tag.text.strip() == name_ar)
        ul02 = li.findNext()
        category = Category(name_ar, name_ar)
        for a in ul02.find_all("a"):
            source_id = a.get("href", "")
            title = a.text.strip()
            category.add_topic(title, source_id, name)
        yield category


class Paginator(object):
    def __init__(self, url, initial=1, last=None):
        self.url = url
        self.initial_page = initial
        self.last_page = last
        self.counter = initial
    
    def build_page_url(self):
        return self.url + "?page={}".format(self.counter)
    
    def find_max(self):
        page = download(self.url)
        li_page = page.find("li", class_="ipsPagination_pageJump")
        if li_page is not None:
            value = li_page.find("input")
            self.last_page = int(value.attrs.get("max", "0"))
        else:
            self.last_page = 1

    def __next__(self):
        page_url = self.build_page_url()
        self.counter += 1
        return page_url
    
    def __iter__(self):
        if self.last_page is not None:
            while self.initial_page <= self.counter <= self.last_page:
                yield next(self)
        else:
            while True:
                yield next(self)

    

class Node(object):
    def __init__(self, title, source_id, lang="ar"):
        self.title = title
        self.source_id = source_id
        self.tree_nodes = OrderedDict()
        self.lang = lang
        self.description = None
        self._thumbnail = None
        self.author = None

    def add_node(self, obj):
        node = obj.to_node()
        if node is not None:
            self.tree_nodes[node["source_id"]] = node

    @property
    def thumbnail(self):
        return self._thumbnail

    @thumbnail.setter
    def thumbnail(self, url):
        key = hashlib.sha1(url.encode("utf-8")).hexdigest()
        self._thumbnail = save_thumbnail(url, key, DATA_DIR)

    def title_hash(self):
        return hashlib.sha1(self.title.encode("utf-8")).hexdigest()

    def to_node(self):
        return dict(
            kind=content_kinds.TOPIC,
            source_id=self.source_id,
            title=self.title,
            description=self.description,
            language=self.lang,
            thumbnail=self.thumbnail,
            author=AUTHOR if self.author is None else self.author,
            license=LICENSE,
            children=list(self.tree_nodes.values())
        )
    

class Category(Node):
    def __init__(self, *args, **kwargs):
        super(Category, self).__init__(*args, **kwargs)
        self.topics = []

    def add_topic(self, title, url, name):
        if url != "#":
            if name == "Lessons and Articles":
                self.topics.append(LessonTopic(title, url))
            elif name == "Books and Resources":
                self.topics.append(BookTopic(title, url))
            else:
                self.topics.append(QuestionTopic(title, url))

    def download(self):
        for topic in self.topics:
            topic.download()
            self.add_node(topic)


class LessonTopic(Node):
    def download(self):
        LOGGER.info("--- Topic: {}".format(self.source_id))
        pages = Paginator(self.source_id, initial=1)
        pages.find_max()
        for page in pages:
            LOGGER.info("------ Page: {} of {}".format(page, pages.last_page))
            page = download(page)
            div = page.find("div", id="elCmsPageWrap")
            articles = div.find_all("article")
            for article_soup in articles:
                img = article_soup.find("img")
                title_a = article_soup.find(lambda tag: tag.name == "a" and tag.findParent("h2") and tag.get("href", "").find("/tags/") == -1)
                title = title_a.text.strip()
                source_id = title_a.get("href", "")
                article = Article(title, source_id)
                article.description = article_soup.find("section").text
                article.thumbnail = img.get("src", None)
                article.author = title_a.findNext("a").text.strip()
                base_path = build_path([DATA_DIR, self.title_hash(), article.title_hash()])
                article.download(base_path=base_path)
                self.add_node(article)


class BookTopic(Node):
    def download(self):
        LOGGER.info("--- Book Topic: {}".format(self.source_id))
        pages = Paginator(self.source_id, initial=1)
        pages.find_max()
        pattern = "(?P<url>https?://[^\s]+)"
        re_pattern = re.compile(pattern)
        for page in pages:
            LOGGER.info("------ Page: {} of {}".format(page, pages.last_page))
            page = download(page)
            ol = page.find("ol", class_="ipsDataList")
            books = ol.find_all("li", class_="ipsDataItem")
            for book_soup in books:
                div = book_soup.find_all("div")
                style = div[0].find("a").get("style", "")
                img_url = re_pattern.search(style).group("url").replace('"', "")
                title_a = div[1].find(lambda tag: tag.name == "a" and tag.findParent("h4") and tag.get("href", "").find("/tags/") == -1)
                title = title_a.text.strip()
                source_id = title_a.get("href", "")
                book = Book(title, source_id)
                book.description = title_a.findNext("div").text.strip()
                book.thumbnail = img_url
                book.author = title_a.findNext("a").text.strip()
                base_path = build_path([DATA_DIR, self.title_hash(), book.title_hash()])
                book.download(base_path=base_path)
                self.add_node(book)
    

class QuestionTopic(Node):
    def download(self):
        LOGGER.info("--- Question and Answers: {}".format(self.source_id))
        pages = Paginator(self.source_id, initial=1)
        pages.find_max()
        for page in pages:
            LOGGER.info("------ Page: {} of {}".format(page, pages.last_page))
            page = download(page)
            div = page.find("div", class_="ipsBox")
            questions = page.find_all("li", class_="cForumQuestion")
            for question_soup in questions:
                div = question_soup.find_all("div")
                title_a = div[1].find(lambda tag: tag.name == "a" and tag.findParent("h4") and tag.get("href", "").find("/tags/") == -1)
                title = title_a.text.strip()
                source_id = title_a.get("href", "")
                question = Question(title, source_id)
                question.author = title_a.findNext("a").text.strip()
                base_path = build_path([DATA_DIR, self.title_hash(), question.title_hash()])
                question.download(base_path=base_path)
                self.add_node(question)


class Article(Node):
    def __init__(self, *args, **kwargs):
        super(Article, self).__init__(*args, **kwargs)
        LOGGER.info("--------- Article: {}".format(self.title))

    def download(self, download=True, base_path=None):
        html_app = HTMLApp(self.title, self.source_id)
        html_app.author = self.author
        html_app.thumbnail = self.thumbnail
        video_urls = self.search_urls(html_app.body)
        html_app.to_file(base_path)
        self.add_node(html_app)
        for url in video_urls:
            youtube = YouTubeResource(url, lang=self.lang)
            youtube.download(download, base_path)
            self.add_node(youtube)

    def search_urls(self, body):
        video_urls = self.video_urls(body)
        return video_urls

    def video_urls(self, content):
        urls = set([])
        video_urls = content.find_all(lambda tag: tag.name == "a" and tag.attrs.get("href", "").find("youtube") != -1 or tag.attrs.get("href", "").find("youtu.be") != -1 or tag.text.lower() == "youtube")

        for video_url in video_urls:
            urls.add(video_url.get("href", ""))

        for iframe in content.find_all("iframe"):
            url = iframe["src"]
            if YouTubeResource.is_youtube(url):
                urls.add(YouTubeResource.transform_embed(url))

        return urls

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
                thumbnail=self.thumbnail,
                author=AUTHOR if self.author is None else self.author,
                license=LICENSE,
                children=children
            )



class Book(Node):
    def __init__(self, *args, **kwargs):
        super(Book, self).__init__(*args, **kwargs)
        LOGGER.info("--------- Book: {}".format(self.title))
        self.filepath = None
        self.filename = None

    def soup(self):
        ##the function "download" was not used here because we need the cookies from this source_id
        headers = {'User-Agent': 'Mozilla/5.0'}
        client = requests.Session()
        r = client.get(self.source_id, timeout=60, headers=headers)
        soup = BeautifulSoup(r.text, 'html5lib')
        client.headers.update(headers)
        return soup.find("aside"), client

    def download(self, download=True, base_path=None):
        body, client = self.soup()
        a = body.find("a")
        url = a.get("href", "")
        try:
            if download is False:
                return
            #parsed = urlparse.urlparse(url)
            #csrfKey = str(urlparse.parse_qs(parsed.query)['csrfKey'])
            response = client.get(url, timeout=60, headers=client.headers)
            content_type = response.headers.get('content-type')
            if 'application/pdf' in content_type:
                self.filename = response.headers.get("Content-Disposition", "").split("=")[1]
                self.filename = self.filename[1:len(self.filename)-1]
                self.filepath = os.path.join(base_path, self.filename)
                if not file_exists(self.filepath):
                    with open(self.filepath, 'wb') as f:
                        for chunk in response.iter_content(10000):
                            f.write(chunk)
                    LOGGER.info("    - Get file: {}".format(self.filename))
                else:
                    LOGGER.info("    - File: {} already saved".format(self.filename))
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
                description=self.description,
                thumbnail=self.thumbnail,
                author=AUTHOR if self.author is None else self.author,
                files=[dict(
                    file_type=content_kinds.DOCUMENT,
                    path=self.filepath
                )],
                language=self.lang,
                license=LICENSE)
            return node


class Question(Node):
    def __init__(self, *args, **kwargs):
        super(Question, self).__init__(*args, **kwargs)
        LOGGER.info("--------- Question: {}".format(self.title))

    def download(self, download=True, base_path=None):
        html_app = HTMLAppQA(self.title, self.source_id)
        html_app.author = self.author
        html_app.to_file(base_path)
        self.add_node(html_app)

    def to_node(self):
        return list(self.tree_nodes.values())[0]


class HTMLApp(object):
    def __init__(self, title, source_id, lang="ar"):
        self.title = title
        self.source_id = source_id
        self.lang = lang
        self.description = None
        self.thumbnail = None
        self.author = None
        self.filepath = None
        self.body = self.soup()

    def soup(self):
        soup = download(self.source_id)
        if soup:
            return soup.find("article")

    def clean(self, content):
        link_to_text(content)
        remove_links(content)
        remove_iframes(content)
        remove_scripts(content)
        return content

    def title_hash(self):
        return hashlib.sha1(self.title.encode("utf-8")).hexdigest()

    def to_local_images(self, content):
        images_urls = {}
        for img in content.find_all("img"):
            try:
                img_src = img["src"]
            except KeyError:
                continue
            else:
                if img_src.startswith("/"):
                    img_src = urljoin(BASE_URL, img_src)
                filename = get_name_from_url(img_src)
                if img_src not in images_urls and img_src:
                    img["src"] = filename
                    images_urls[img_src] = filename
        return images_urls

    def write_images(self, filepath, images):
        with html_writer.HTMLWriter(filepath, "a") as zipper:
            for img_src, img_filename in images.items():
                try:
                    if img_src.startswith("data:image/"):
                        pass
                    else:
                        requests.get(img_src, timeout=20)
                        zipper.write_url(img_src, img_filename, directory="")
                except requests.exceptions.ConnectionError:
                    pass
                except requests.exceptions.HTTPError:
                    pass
                except requests.exceptions.MissingSchema:
                    pass
                except requests.exceptions.InvalidSchema:
                    pass
                except requests.exceptions.ReadTimeout:
                    pass
                except requests.exceptions.ConnectTimeout as e:
                    LOGGER.info(str(e))

    def write_index(self, filepath, content):
        with html_writer.HTMLWriter(filepath, "w") as zipper:
            zipper.write_index_contents(content)

    def write_css_js(self, filepath):
        with html_writer.HTMLWriter(filepath, "a") as zipper, open("chefdata/styles.css") as f:
            content = f.read()
            zipper.write_contents("styles.css", content, directory="css/")

        with html_writer.HTMLWriter(filepath, "a") as zipper, open("chefdata/scripts.js") as f:
            content = f.read()
            zipper.write_contents("scripts.js", content, directory="js/")

    def to_file(self, base_path):
        self.filepath = "{path}/{name}.zip".format(path=base_path, name=self.title_hash())
        if file_exists(self.filepath):
            LOGGER.info("     * File exists {}".format(self.filepath))
            return True
        if self.body is None:
            return False
        body = self.clean(self.body)
        images = self.to_local_images(body)
        self.write_index(self.filepath, '<html><head><meta charset="utf-8"><link rel="stylesheet" href="css/styles.css"></head><body style="text-align:right;"><div class="main-content-with-sidebar">{}</div><script src="js/scripts.js"></script></body></html>'.format(body))
        self.write_images(self.filepath, images)
        self.write_css_js(self.filepath)

    def to_node(self):
        if self.filepath is not None:
            return dict(
                kind=content_kinds.HTML5,
                source_id=self.source_id,
                title=self.title,
                description=self.description,
                thumbnail=self.thumbnail,
                author=AUTHOR if self.author is None else self.author,
                files=[dict(
                    file_type=content_kinds.HTML5,
                    path=self.filepath
                )],
                language=self.lang,
                license=LICENSE
            )

class HTMLAppQA(HTMLApp):
    def soup(self):
        soup = download(self.source_id)
        if soup:
            return soup.find_all("article")

    def clean(self, content):
        remove_links(content)
        remove_iframes(content)
        remove_scripts(content)
        return content

    def to_file(self, base_path):
        self.filepath = "{path}/{name}.zip".format(path=base_path, name=self.title_hash())
        if file_exists(self.filepath):
            LOGGER.info("     * File exists {}".format(self.filepath))
            return True
        if self.body is None:
            return False
        articles = ["<h2>{}</h2>".format(self.title)]
        images = {}
        for article in self.body:
            images.update(self.to_local_images(article))
            articles.append(str(self.clean(article)))
        self.write_index(self.filepath, '<html><head><meta charset="utf-8"><link rel="stylesheet" href="css/styles.css"></head><body style="text-align:right;"><div class="main-content-with-sidebar">{}</div><script src="js/scripts.js"></script></body></html>'.format("".join(articles)))
        self.write_images(self.filepath, images)
        self.write_css_js(self.filepath)



class YouTubeResource(object):
    def __init__(self, source_id, name=None, type_name="Youtube", lang="ar", 
            embeded=False, section_title=None):
        LOGGER.info("    + Resource Type: {}".format(type_name))
        LOGGER.info("    - URL: {}".format(source_id))
        self.filename = None
        self.type_name = type_name
        self.filepath = None
        self.name = name
        self.section_title = section_title
        if embeded is True:
            self.source_id = YouTubeResource.transform_embed(source_id)
        else:
            self.source_id = self.clean_url(source_id)
        self.file_format = file_formats.MP4
        self.lang = lang
        self.is_valid = False

    def clean_url(self, url):
        if len(url) == 0:
            return url
 
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
        for url in self.playlist_links():
            youtube = YouTubeResource(url)
            info = youtube.get_video_info(None, False)
            name_url.append((info["title"], url))
        return name_url

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
                'noplaylist': True
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
                    LOGGER.info("    + Video resolution: {}x{}".format(info.get("width", ""), info.get("height", "")))
                    self.filepath = os.path.join(download_to, "{}.mp4".format(info["id"]))
                    self.filename = info["title"]
                    if self.filepath is not None and os.stat(self.filepath).st_size == 0:
                        LOGGER.info("    + Empty file")
                        self.filepath = None
            except (ValueError, IOError, OSError, URLError, ConnectionResetError) as e:
                LOGGER.info(e)
                LOGGER.info("Download retry")
                time.sleep(.8)
            except (youtube_dl.utils.DownloadError, youtube_dl.utils.ContentTooShortError,
                    youtube_dl.utils.ExtractorError, OSError) as e:
                LOGGER.info("     + An error ocurred, may be the video is not available.")
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
                title=self.name if self.name is not None else self.filename,
                description='',
                author=AUTHOR,
                files=files,
                language=self.lang,
                license=LICENSE
            )
            return node


def download(source_id):
    tries = 0
    while tries < 4:
        try:
            document = downloader.read(source_id, loadjs=False, session=sess)
        except requests.exceptions.HTTPError as e:
            LOGGER.info("Error: {}".format(e))
        except requests.exceptions.ConnectionError:
            ### this is a weird error, may be it's raised when the webpage
            ### is slow to respond requested resources
            LOGGER.info("Connection error, the resource will be scraped in 5s...")
            time.sleep(3)
        except requests.exceptions.TooManyRedirects as e:
            LOGGER.info("Error: {}".format(e))
        else:
            return BeautifulSoup(document, 'html5lib') #html5lib
        tries += 1
    return False



# The chef subclass
################################################################################
class HsoubAcademyChef(JsonTreeChef):
    HOSTNAME = BASE_URL
    TREES_DATA_DIR = os.path.join(DATA_DIR, 'trees')
    SCRAPING_STAGE_OUTPUT_TPL = 'ricecooker_json_tree.json'
    THUMBNAIL = ""

    def __init__(self):
        build_path([HsoubAcademyChef.TREES_DATA_DIR])
        self.scrape_stage = os.path.join(HsoubAcademyChef.TREES_DATA_DIR, 
                                HsoubAcademyChef.SCRAPING_STAGE_OUTPUT_TPL)
        super(HsoubAcademyChef, self).__init__()

    def pre_run(self, args, options):
        self.download_css_js()
        channel_tree = self.scrape(args, options)
        self.write_tree_to_json(channel_tree)

    def download_css_js(self):
        r = requests.get("https://raw.githubusercontent.com/learningequality/html-app-starter/master/css/styles.css")
        with open("chefdata/styles.css", "wb") as f:
            f.write(r.content)

        r = requests.get("https://raw.githubusercontent.com/learningequality/html-app-starter/master/js/scripts.js")
        with open("chefdata/scripts.js", "wb") as f:
            f.write(r.content)

    def scrape(self, args, options):
        download_video = options.get('--download-video', "1")

        if int(download_video) == 0:
            global DOWNLOAD_VIDEOS
            DOWNLOAD_VIDEOS = False

        global channel_tree
        channel_tree = dict(
                source_domain=HsoubAcademyChef.HOSTNAME,
                source_id=BASE_URL,
                title=CHANNEL_NAME,
                description="""Hsoub Academy provides online courses in the area of computer science and digital literacy for adult learners and IT emerging professionals. Those courses include video lessons and articles on what is trending in the coding and entrepreneurship world today.."""
[:400], #400 UPPER LIMIT characters allowed 
                thumbnail="fa36cba155b77177120dc0f1a6fbde8a.png",
                author=AUTHOR,
                language=CHANNEL_LANGUAGE,
                children=[],
                license=LICENSE,
            )

        for category in browser_resources():
            category.download()
            channel_tree["children"].append(category.to_node())

        return channel_tree

    def write_tree_to_json(self, channel_tree):
        write_tree_to_json_tree(self.scrape_stage, channel_tree)


# CLI
################################################################################
if __name__ == '__main__':
    chef = HsoubAcademyChef()
    chef.main()
