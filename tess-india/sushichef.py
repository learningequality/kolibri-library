#!/usr/bin/env python

from bs4 import BeautifulSoup
from bs4 import Tag
from collections import OrderedDict, defaultdict
import copy
from http import client
import gettext
import hashlib
import json
from le_utils.constants import licenses, content_kinds, file_formats
import logging
import os
from pathlib import Path
import re
import requests
from ricecooker.classes.licenses import get_license
from ricecooker.chefs import JsonTreeChef
from ricecooker.utils.caching import CacheForeverHeuristic, FileCache, CacheControlAdapter
from ricecooker.utils import downloader, html_writer
from ricecooker.utils.jsontrees import write_tree_to_json_tree, SUBTITLES_FILE
import sys
import time
from urllib.error import URLError
from urllib.parse import urljoin, urlencode
from utils import save_thumbnail, if_file_exists, load_tree
from utils import if_dir_exists, get_name_from_url, get_name_from_url_no_ext
from utils import build_path, remove_links, remove_iframes, check_shorter_url
from utils import get_level_map, get_node_from_channel
import urllib.parse as urlparse
import youtube_dl


# Additional Constants
################################################################################
LOGGER = logging.getLogger()
__logging_handler = logging.StreamHandler()
LOGGER.addHandler(__logging_handler)
LOGGER.setLevel(logging.INFO)

# BASE_URL is used to identify when a resource is owned by Edsitement
BASE_URL = "http://www.tess-india.edu.in/learning-materials"

# If False then no download is made
# for debugging proporses
DOWNLOAD_VIDEOS = True

# time.sleep for debugging proporses, it helps to check log messages
TIME_SLEEP = .8

DATA_DIR = "chefdata"
COPYRIGHT_HOLDER = "The Open University"

#Curricular units with its lessons
CURRICULAR_UNITS_MAP = defaultdict(OrderedDict)
#Lessons related with curricular units
LESSONS_CURRICULAR_MAP = defaultdict(set)
# webcache
###############################################################
sess = requests.Session()
cache = FileCache('.webcache')
basic_adapter = CacheControlAdapter(cache=cache)
forever_adapter = CacheControlAdapter(heuristic=CacheForeverHeuristic(), cache=cache)
sess.mount('http://', basic_adapter)
sess.mount(BASE_URL, forever_adapter)

# Main Scraping Method
################################################################################

def test():
    """
    Test individual resources
    """
    url = "http://www.tess-india.edu.in/learning-materials?course_tid=136&subject_tid=181&educational_level_tid=226"
    global channel_tree    
    channel_tree = dict(
        source_domain=TESSIndiaChef.HOSTNAME,
        source_id='tessindia',
        title='TESSIndia',
        description="""TESS-India is led by The Open University and Save The Children India, funded by UK Aid it is a multilingual teacher professional development programme whose aim is to support India’s national educational policy by enhancing the classroom practice of primary and secondary school teachers through the provision of freely available, adaptable Open Educational Resources (OER)."""[:400], #400 UPPER LIMIT characters allowed 
        thumbnail=None,
        language="en",
        children=[],
        license=TESSIndiaChef.LICENSE,
    )
    try:
        resource = Resource(source_id=url,
            lang="en",
            state="All India - English",
            subject="English",
            level="Elementary")
        resource.scrape()
        resource.to_tree(channel_tree)
    except requests.exceptions.HTTPError as e:
        LOGGER.info("Error: {}".format(e))
    return channel_tree


def test_lesson():
    lesson_url = "http://www.tess-india.edu.in/learning-resource-1001"
    lesson = Lesson(name="test", key_resource_id=lesson_url, lang="en",
                    extra_resources=None, path=["A", "B"])
    lesson.download()
    lesson_node = lesson.to_node()
    print(lesson_node)


class ResourceBrowser(object):
    def __init__(self, resource_url):
        self.resource_url = resource_url

    def build_url(self, course_tid=None, subject_tid=None, educational_level_tid=None):
        if educational_level_tid is not None:
            params = dict(course_tid=course_tid, subject_tid=subject_tid, 
                        educational_level_tid=educational_level_tid)
        else:
            params = dict(course_tid=course_tid, subject_tid=subject_tid)
        url_parts = list(urlparse.urlparse(self.resource_url))
        query = dict(urlparse.parse_qsl(url_parts[4]))
        query.update(params)
        url_parts[4] = urlencode(query)
        return urlparse.urlunparse(url_parts)

    def get_total_items(self, text):
        string = re.search(r"\d+\-\d+ of \d+", text).group()
        return int(string.split("of")[-1].strip())

    def run(self, limit_page=1, page_number=1):
        total_items = None
        counter = 0
        try:
            page_contents = downloader.read(self.resource_url, loadjs=False)
        except requests.exceptions.HTTPError as e:
            LOGGER.info("Error: {}".format(e))
        else:
            page = BeautifulSoup(page_contents, 'html.parser')
            states = page.find("div", class_=["lm-filter-course"])
            states_tree = self.get_state_lang(states)
            subjects = page.find("div", class_=["lm-filter-subject"])
            subjects_tree = self.get_subjects(subjects)
            levels = page.find("div", class_=["lm-filter-level"])
            levels_tree = self.get_levels(levels)
            pages_params = self.build_page_params(states_tree, subjects_tree, levels_tree)
            for page_params in pages_params:
                url = self.build_url(page_params["course_tid"], 
                    page_params["subject_tid"], 
                    page_params.get("educational_level_tid", None))
                yield dict(url=url,
                    subject_name=page_params["subject_name"],
                    state_lang=page_params["state_lang"],
                    level_name=page_params.get("level_name", None))
                LOGGER.info("CRAWLING : URL {}".format(url))
                time.sleep(TIME_SLEEP)

    def get_state_lang(self, items):
        tree = {}
        for state_data in items.findAll("button"):
            tree[state_data["data-tid"]] = state_data.text.strip()
        return tree

    def get_subjects(self, items):
        tree = {}
        for subject_data in items.findAll("button"):
            if subject_data["data-course"] == "all":
                continue
            tree.setdefault(subject_data["data-course"], {})
            tree[subject_data["data-course"]][subject_data["data-tid"]] = (subject_data.text.strip(), bool(int(subject_data.get("data-hide-level", "0"))))
        return tree

    def get_levels(self, items):
        tree = {}
        for subject_data in items.findAll("button"):
            tree.setdefault(subject_data["data-course"], {})
            tree[subject_data["data-course"]][subject_data["data-tid"]] = subject_data.text.strip()
        return tree

    def build_page_params(self, states, subjects, levels):
        pages = []#course_tid, subject_tid, educational_level_tid
        for course_tid in subjects:
            for subjects_tid in subjects[course_tid]:
                subject_name = subjects[course_tid][subjects_tid][0]
                not_has_levels = subjects[course_tid][subjects_tid][1]
                info = {"course_tid": course_tid, "subject_tid": subjects_tid,
                    "state_lang": states[course_tid], "subject_name": subject_name}
                if not_has_levels is False:
                    for level_tid in levels[course_tid]:
                        info_tmp = info.copy()
                        info_tmp["educational_level_tid"] = level_tid
                        info_tmp["level_name"] = levels[course_tid][level_tid]
                        pages.append(info_tmp)
                else:        
                    pages.append(info)
        return pages


class Resource(object):
    def __init__(self, source_id,  lang="en", state=None, subject=None, level=None):
        self.source_id = source_id
        self.lang = lang
        self.state = state
        self.subject = subject
        self.level = level
        self.nodes = []
        self.ids = set([])

    def scrape(self):
        page = download(self.source_id)
        for material in page.findAll("div", class_=["node-learning-material"]):
            resource = material.find(lambda tag: tag.name == "a" and tag.findParent("h2"))
            if resource is not None:
                lesson_name = resource.text
                lesson_url = resource["href"]
            else:
                lesson_name = material.find("h2").text
                lesson_url = material.attrs.get("about", "")
            extra_resources = material.findAll(lambda tag: tag.name == "a" and \
                tag.findParent("div", class_=["lmat-download"]))
            extra_resources_urls = set([])
            for extra_resource in extra_resources:
                extra_resources_urls.add(extra_resource["href"])
            if not lesson_url in self.ids:
                lesson = Lesson(name=lesson_name, key_resource_id=lesson_url, lang=self.lang,
                    extra_resources=extra_resources_urls, path=[self.state, self.subject, self.level])
                lesson.download()
                lesson_node = lesson.to_node()
                if len(lesson_node["children"]) > 0:
                    self.nodes.append(lesson_node)
                self.ids.add(lesson_url)

    def empty_state_node(self):
        return dict(
            kind=content_kinds.TOPIC,
            source_id=self.state,
            title=self.state,
            description="",
            license=None,
            language=self.lang,
            children=[]
        )

    def empty_subject_node(self):
        return dict(
            kind=content_kinds.TOPIC,
            source_id=self.subject,
            title=self.subject,
            description="",
            license=None,
            language=self.lang,
            children=[]
        )

    def empty_level_node(self):
        return dict(
            kind=content_kinds.TOPIC,
            source_id=self.level,
            title=self.level,
            description="",
            license=None,
            language=self.lang,
            children=[]
        )

    def build_tree(self, nodes, subtree=None, tree_level=0):
        if tree_level == 0:
            if subtree is None:
                root = self.empty_state_node()
            else:
                root = subtree
            subject = self.empty_subject_node()
            if self.level is not None:
                level = self.empty_level_node()
                level["children"].extend(nodes)
                subject["children"].append(level)
            else:
                subject["children"].extend(nodes)
            root["children"].append(subject)
            return root
        elif tree_level == 1:
            subject = subtree
            if self.level is not None:
                level = self.empty_level_node()
                level["children"].extend(nodes)
                subject["children"].append(level)
            else:
                subject["children"].extend(nodes)
        elif tree_level == 2:
            level = subtree
            level["children"].extend(nodes)

    def get_tree_level(self, channel_tree):
        subtree = get_level_map(channel_tree, [self.state, self.subject, self.level])
        level = 2
        if subtree is None:
            subtree = get_level_map(channel_tree, [self.state, self.subject])
            level -= 1
            if subtree is None:
                subtree = get_level_map(channel_tree, [self.state])
                level -= 1
        return subtree, level

    def to_tree(self, channel_tree):
        subtree, tree_level = self.get_tree_level(channel_tree)
        root = self.build_tree(self.nodes, subtree, tree_level=tree_level)
        if subtree is None and root is not None:
            channel_tree["children"].append(root)
                

class Lesson(object):
    def __init__(self, name=None, key_resource_id=None, extra_resources=None, 
                path=None, lang="en"):
        self.key_resource_id = urljoin(BASE_URL, key_resource_id.strip())
        self.filename = hashlib.sha1(name.encode("utf-8")).hexdigest()
        self.title = name if len(name) < 80 else name[:80]
        self.path_levels = path
        self.lang = lang
        self.file = None
        self.video = None
        self.ids = set([])
        LOGGER.info("Collecting: {}".format(self.key_resource_id))
        LOGGER.info("   - Name: {}".format(self.title))
        LOGGER.info("   - Lang: {}".format(self.lang))
        self.html = HTMLLesson(source_id=self.key_resource_id, name=self.title, 
            lang=self.lang)
        if self.path_levels[-1] is None:
            self.base_path = build_path([DATA_DIR] + self.path_levels[:-1] + [self.filename])
        else:
            self.base_path = build_path([DATA_DIR] + self.path_levels + [self.filename])
        if extra_resources is not None:
            LOGGER.info("   - Extra resources: {}".format(len(extra_resources)))
            self.set_extra_resources(extra_resources)

    def set_extra_resources(self, extra_resources):
        for resource in extra_resources:
            LOGGER.info("   - Resource: {}".format(resource))
            if resource.endswith(".pdf"):
                self.file = File(resource, lang=self.lang, name=self.title)
            elif resource.endswith(".doc") or resource.endswith(".docx"):
                pass
            else:
                resource = urljoin(BASE_URL, resource.strip())
                if resource != self.key_resource_id:
                    self.video = HTMLLesson(source_id=resource, 
                        name=self.title + " - Videos", lang=self.lang)

    def download(self):
        self.html.scrape(self.base_path, name="index")
        if self.file:
            self.file.download(self.base_path)
        if self.video:
            self.video.scrape(self.base_path, name="video")

    def to_node(self):
        topic_node = dict(
            kind=content_kinds.TOPIC,
            source_id=self.key_resource_id,
            title=self.title,
            description="",
            language=self.lang,
            license=None,
            children=[]
        )

        for html_node in self.html.to_nodes():
            if html_node is not None and html_node["source_id"] not in self.ids:
                topic_node["children"].append(html_node)
                self.ids.add(html_node["source_id"])

        if self.file is not None:
            file_node = self.file.to_node()
            if file_node is not None and file_node["source_id"] not in self.ids:
                topic_node["children"].append(file_node)
                self.ids.add(file_node["source_id"])

        if self.video is not None:
            videos_nodes = self.video.to_nodes()
            for video_node in videos_nodes:
                if video_node is not None and video_node["source_id"] not in self.ids:
                    topic_node["children"].append(video_node)
                    self.ids.add(video_node["source_id"])
        
        return topic_node
        

class File(object):
    def __init__(self, source_id, lang="en", lincese="", name=None):
        self.filename = get_name_from_url(source_id)
        self.source_id = urljoin(BASE_URL, source_id) if source_id.startswith("/") else source_id
        self.filepath = None
        self.lang = lang
        self.name = "{}_{}".format(name, self.filename)
        self.license = get_license(licenses.CC_BY_NC_SA, copyright_holder=COPYRIGHT_HOLDER).as_dict()

    def download(self, base_path):
        PDFS_DATA_DIR = build_path([base_path, 'pdfs'])
        try:
            response = sess.get(self.source_id)
            content_type = response.headers.get('content-type')
            if 'application/pdf' in content_type:
                self.filepath = os.path.join(PDFS_DATA_DIR, self.filename)
                with open(self.filepath, 'wb') as f:
                    for chunk in response.iter_content(10000):
                        f.write(chunk)
                LOGGER.info("   - Get file: {}, node name: {}".format(self.filename, self.name))
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
                title=self.name,
                description='',
                files=[dict(
                    file_type=content_kinds.DOCUMENT,
                    path=self.filepath
                )],
                language=self.lang,
                license=self.license)
            return node


class HTMLLesson(object):
    def __init__(self, source_id=None, lang="en", name=None):
        self.source_id = source_id
        self.filepath = None
        self.name = name
        self.lang = lang
        self.menu = Menu(lang=self.lang, name=name)
        self.license = get_license(licenses.CC_BY_NC_SA, copyright_holder=COPYRIGHT_HOLDER).as_dict()

    def sections_to_menu(self):
        page = download(self.source_id)
        if page:
            content = page.find("main", class_="content-main")
            ul = content.find(lambda tag: tag.name == "ul" and tag.findParent("div", class_="content"))
            self.menu.index_content = ul
            href = None
            for link in content.findAll("a"):
                href = link.get("href", "")
                links_class = link.get("class", [])
                if href:# and "active" not in links_class:
                    self.menu.add_item(title=link.text, url=urljoin(self.source_id, href))

    def scrape(self, base_path, name="htmlapp"):
        self.filepath = "{path}/{name}.zip".format(path=base_path, name=name)
        self.sections_to_menu()
        self.menu.to_file(self.filepath, base_path)

    def to_nodes(self):
        if self.menu.is_valid:
            menu_node = self.menu.to_nodes()
            node = dict(
                kind=content_kinds.HTML5,
                source_id=self.source_id,
                title=self.name,
                description="",
                thumbnail=None,
                author="",
                files=[dict(
                    file_type=content_kinds.HTML5,
                    path=self.filepath
                )],
                language=self.lang,
                license=self.license)
            return [node] + menu_node
        else:
            return []


class Menu(object):
    def __init__(self, lang="en", name=None):
        self.items = OrderedDict()
        self.index_content = None
        self.images = {}
        self.pdfs_url = set([])
        self.nodes = []
        self.ids = set([])
        self.is_valid = False
        self.lang = lang
        self.name = name

    def build_index(self, directory="files/"):
        items = iter(self.items.values())
        if self.index_content is not None:
            self.index_content["class"] = "sidebar-items"
            for ul in self.index_content:
                if hasattr(ul, 'findAll'):
                    for a in ul.findAll("a"):
                        item = next(items)
                        a["href"] = "{}{}".format(directory, item["filename"])
                        a["class"] = "sidebar-link"
                else:
                    return
            self.is_valid = True
            return str(self.index_content)

    def add_item(self, title=None, url=None):
        filename = self.item_to_filename(title)
        if url not in self.items:
            content = self.get_sections_content(url)
            self.items[url] = {"title": title, "filename": filename, "content": content}

    def clean_content(self, content):
        content.find("div", class_="addthis").decompose()
        obj_tags = content.find_all("div", class_="oucontent-media")#oucontent-embedtemplate")
        if obj_tags is not None:
            for obj_tag in obj_tags:
                obj_tag.decompose()
        if content is not None:
            for link in content.find_all("a"):
                if "active" not in link.attrs.get("class", []):
                    link.replaceWithChildren()

    def pager(self, content, index):
        ul = content.find("ul", class_="pager")
        first_page = ul.find(lambda tag: tag.name == "a" and tag.findParent("li", class_="pager-first"))
        last_page = ul.find(lambda tag: tag.name == "a" and tag.findParent("li", class_="pager-last"))
        previous = ul.find(lambda tag: tag.name == "a" and tag.findParent("li", class_="pager-previous"))
        next = ul.find(lambda tag: tag.name == "a" and tag.findParent("li", class_="pager-next"))
        if first_page is not None:
            first_page["href"] = "../index.html"
        items = list(self.items.values())
        if last_page is not None:
            last_page["href"] = items[-1]["filename"]
        if previous is not None:
            if index > 0:
                previous["href"] = items[index - 1]["filename"]
            else:
                previous["href"] = first_page["href"]
        if next is not None:
            if index < len(items) - 1:
                next["href"] = items[index + 1]["filename"]
            else:
                next["href"] = last_page["href"]

    def get_sections_content(self, url):
        page = download(url)
        content = page.find("section", class_="main-content")
        return content

    def get_images(self, content):
        for img in content.findAll("img"):
            if img["src"].startswith("/"):
                img_src = urljoin(BASE_URL, img["src"])
            else:
                img_src = img["src"]
            filename = get_name_from_url(img_src)
            if img_src not in self.images and img_src:
                img["src"] = filename
                self.images[img_src] = filename

    def write_pdfs(self, base_path, content):
        for tag_a in content.findAll(lambda tag: tag.name == "a" and tag.attrs.get("href", "").endswith(".pdf")):
            pdf_url = tag_a.get("href", "")
            if pdf_url not in self.pdfs_url and pdf_url:
                self.pdfs_url.add(pdf_url)
                pdf_file = File(pdf_url, lang=self.lang, name=self.name)
                pdf_file.download(base_path)
                node = pdf_file.to_node()
                if node is not None and node["source_id"] not in self.ids:
                    self.nodes.append(node)
                    self.ids.add(node["source_id"])

    def write_video(self, base_path, content):
        videos = content.find_all(lambda tag: tag.name == "a" and tag.attrs.get("href", "").find("youtube") != -1 or tag.attrs.get("href", "").find("youtu.be") != -1 or tag.text.lower() == "youtube")
        VIDEOS_DATA_DIR = build_path([base_path, 'videos'])
        for video in videos:
            youtube = YouTubeResource(video.get("href", ""), lang=self.lang)
            node = get_node_from_channel(youtube.resource_url, channel_tree)
            if node is None:
                youtube.to_file(filepath=VIDEOS_DATA_DIR)
                node = youtube.node

            if node is not None:
                if video.parent.name == 'li':
                    video.parent.replace_with("Video name: " + node["title"])
                if node["source_id"] not in self.ids:
                    self.nodes.append(node)
                    self.ids.add(node["source_id"])

    def write_index(self, filepath, content):
        with html_writer.HTMLWriter(filepath, "w") as zipper:
            zipper.write_index_contents(content)

    def write_contents(self, filepath_index, filename, content, directory="files"):
        with html_writer.HTMLWriter(filepath_index, "a") as zipper:
            content = '<html><head><meta charset="utf-8"><link rel="stylesheet" href="../css/styles.css"></head><body>{}<script src="../js/scripts.js"></script></body></html>'.format(content)
            zipper.write_contents(filename, content, directory=directory)
    
    def write_images(self, filepath, content):
        self.get_images(content)
        with html_writer.HTMLWriter(filepath, "a") as zipper:
            for img_src, img_filename in self.images.items():
                try:
                    zipper.write_url(img_src, img_filename, directory="files")
                except requests.exceptions.HTTPError:
                    pass

    def write_css_js(self, filepath):
        with html_writer.HTMLWriter(filepath, "a") as zipper, open("chefdata/styles.css") as f:
            content = f.read()
            zipper.write_contents("styles.css", content, directory="css/")

        with html_writer.HTMLWriter(filepath, "a") as zipper, open("chefdata/scripts.js") as f:
            content = f.read()
            zipper.write_contents("scripts.js", content, directory="js/")

    def item_to_filename(self, name):
        name = "_".join(name.lower().split(" "))
        hash_name = hashlib.sha1(name.encode("utf-8")).hexdigest()
        return "{}.html".format(hash_name)

    def to_file(self, filepath, base_path):
        index_content_str = self.build_index()
        if index_content_str is not None:
            self.write_index(filepath, '<html><head><meta charset="utf-8"><link rel="stylesheet" href="css/styles.css"></head><body><div class="main-content-with-sidebar">{}</div><script src="js/scripts.js"></script></body></html>'.format(index_content_str))
            self.write_css_js(filepath)
            for i, item in enumerate(self.items.values()):
                self.write_images(filepath, item["content"])
                file_nodes = self.write_pdfs(base_path, item["content"])
                video_nodes = self.write_video(base_path, item["content"])
                self.pager(item["content"], i)
                self.clean_content(item["content"])
                content = '<div class="sidebar"><a class="sidebar-link toggle-sidebar-button" href="javascript:void(0)" onclick="javascript:toggleNavMenu();">&#9776;</a>'+\
                self.build_index(directory="./") +"</div>"+\
                '<div class="main-content-with-sidebar">'+str(item["content"])+'</div>'
                self.write_contents(filepath, item["filename"], content)

    def to_nodes(self):
        return self.nodes


class ResourceType(object):
    """
        Base class for File, WebPage, Video, Audio resources
    """
    def __init__(self, type_name=None, source_id=None):
        LOGGER.info("Resource Type: {} [{}]".format(type_name, source_id))
        self.type_name = type_name
        self.node = None
        self.resource_url = source_id

    def to_file(self, filepath=None):
        pass


class YouTubeResource(ResourceType):
    def __init__(self, resource_url, type_name="Youtube", lang="en"):
        super(YouTubeResource, self).__init__(type_name=type_name, 
            source_id=self.clean_url(resource_url))        
        self.file_format = file_formats.MP4
        self.lang = lang
        self.filename = None
        self.filepath = None

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
                info = ydl.extract_info(self.resource_url, download=(download_to is not None))
                return info
            except(youtube_dl.utils.DownloadError, youtube_dl.utils.ContentTooShortError,
                    youtube_dl.utils.ExtractorError) as e:
                LOGGER.info('An error occured ' + str(e))
                LOGGER.info(self.resource_url)
            except KeyError as e:
                LOGGER.info(str(e))

    def subtitles_dict(self):
        subs = []
        video_info = self.get_video_info()
        if video_info is not None:
            video_id = video_info["id"]
            if 'subtitles' in video_info:
                subtitles_info = video_info["subtitles"]
                LOGGER.info("Subtitles: {}".format(",".join(subtitles_info.keys())))
                for language in subtitles_info.keys():
                    subs.append(dict(file_type=SUBTITLES_FILE, youtube_id=video_id, language=language))
        return subs

    def process_file(self, download=False, filepath=None):
        self.download(download=download, base_path=filepath)
        if self.filepath:
            files = [dict(file_type=content_kinds.VIDEO, path=self.filepath)]
            files += self.subtitles_dict()

            self.node = dict(
                kind=content_kinds.VIDEO,
                source_id=self.resource_url,
                title=self.filename,
                description='',
                files=files,
                language=self.lang,
                license=get_license(licenses.CC_BY, copyright_holder=COPYRIGHT_HOLDER).as_dict())

    def download(self, download=True, base_path=None):
        if not "watch?" in self.resource_url or "/user/" in self.resource_url or\
            download is False:
            return

        download_to = base_path
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

    def to_file(self, filepath=None):
        if "watch?" in self.resource_url or not "/user/" in self.resource_url: 
            self.process_file(download=DOWNLOAD_VIDEOS, filepath=filepath)


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
            return BeautifulSoup(document, 'html.parser') #html5lib
        tries += 1
    return False


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


def language_map(subject):
    lang_map = {
        "All India - English": "en",
        "अखिल भारतीय हिंदी": "hi",
        "उत्तर प्रदेश": "hi",
        "बिहार": "hi",
        "मध्य प्रदेश": "hi",
        "অসম": "as",
        "পশ্চিমবঙ্গ": "bn",
        "ଓଡ଼ିଶା": "or",
        "ಕರ್ನಾಟಕ":  "kn"
    }
    return lang_map.get(subject, "en")


class TESSIndiaChef(JsonTreeChef):
    HOSTNAME = BASE_URL
    TREES_DATA_DIR = os.path.join(DATA_DIR, 'trees')
    CRAWLING_STAGE_OUTPUT_TPL = 'web_resource_tree.json'
    SCRAPING_STAGE_OUTPUT_TPL = 'ricecooker_json_tree.json'
    LICENSE = get_license(licenses.CC_BY_NC_SA, copyright_holder=COPYRIGHT_HOLDER).as_dict()
    THUMBNAIL = ""

    def __init__(self):
        build_path([TESSIndiaChef.TREES_DATA_DIR])
        self.scrape_stage = os.path.join(TESSIndiaChef.TREES_DATA_DIR, 
                                TESSIndiaChef.SCRAPING_STAGE_OUTPUT_TPL)
        self.crawling_stage = os.path.join(TESSIndiaChef.TREES_DATA_DIR, 
                                TESSIndiaChef.CRAWLING_STAGE_OUTPUT_TPL)
        super(TESSIndiaChef, self).__init__()

    def pre_run(self, args, options):
        css = os.path.join(os.path.dirname(os.path.realpath(__file__)), "chefdata/styles.css")
        js = os.path.join(os.path.dirname(os.path.realpath(__file__)), "chefdata/scripts.js")
        if not if_file_exists(css) or not if_file_exists(js):
            LOGGER.info("Downloading styles")
            self.download_css_js()
        self.crawl(args, options)
        channel_tree = self.scrape(args, options)
        clean_leafs_nodes_plus(channel_tree)
        self.write_tree_to_json(channel_tree, "en")

    def download_css_js(self):
        r = requests.get("https://raw.githubusercontent.com/learningequality/html-app-starter/master/css/styles.css")
        with open("chefdata/styles.css", "wb") as f:
            f.write(r.content)

        r = requests.get("https://raw.githubusercontent.com/learningequality/html-app-starter/master/js/scripts.js")
        with open("chefdata/scripts.js", "wb") as f:
            f.write(r.content)

    def crawl(self, args, options):
        web_resource_tree = dict(
            kind='TESSIndiaResourceTree',
            title='TESSIndia',
            children=[]
        )
        crawling_stage = os.path.join(TESSIndiaChef.TREES_DATA_DIR,                     
                                    TESSIndiaChef.CRAWLING_STAGE_OUTPUT_TPL)
        resource_browser = ResourceBrowser(BASE_URL)
        for data in resource_browser.run(limit_page=None, page_number=1):
            web_resource_tree["children"].append(data)
        with open(crawling_stage, 'w') as f:
            json.dump(web_resource_tree, f, indent=2)
        return web_resource_tree

    def scrape(self, args, options):
        cache_tree = options.get('cache_tree', '1')
        download_video = options.get('--download-video', "1")

        with open(self.crawling_stage, 'r') as f:
            web_resource_tree = json.load(f)
            assert web_resource_tree['kind'] == 'TESSIndiaResourceTree'
         
        if int(download_video) == 0:
            global DOWNLOAD_VIDEOS
            DOWNLOAD_VIDEOS = False

        return self._build_scraping_json_tree(cache_tree, web_resource_tree)

    def write_tree_to_json(self, channel_tree, lang):
        write_tree_to_json_tree(self.scrape_stage, channel_tree)

    def _build_scraping_json_tree(self, cache_tree, web_resource_tree):
        LANG = 'mul'
        global channel_tree
        channel_tree = dict(
                source_domain=TESSIndiaChef.HOSTNAME,
                source_id='tessindia',
                title='TESSIndia',
                description="""TESS-India is led by The Open University and Save The Children India, funded by UK Aid it is a multilingual teacher professional development programme whose aim is to support India’s national educational policy by enhancing the classroom practice of primary and secondary school teachers through the provision of freely available, adaptable Open Educational Resources (OER)."""[:400], #400 UPPER LIMIT characters allowed 
                thumbnail=None,
                language=LANG,
                children=[],
                license=TESSIndiaChef.LICENSE,
            )
        counter = 0
        types = set([])
        total_size = len(web_resource_tree["children"])
        copyrights = []
        for resource in web_resource_tree["children"]:
            if 0 <= counter <= total_size:
                LOGGER.info("{} of {}".format(counter, total_size))
                LOGGER.info("Resource: {}".format(resource["url"]))
                resource = Resource(source_id=resource["url"],
                    lang=language_map(resource["state_lang"].strip()),
                    state=resource["state_lang"],
                    subject=resource["subject_name"],
                    level=resource["level_name"])
                resource.scrape()
                resource.to_tree(channel_tree)
            counter += 1
        return channel_tree


# CLI: This code will run when `souschef.py` is called on the command line
################################################################################
if __name__ == '__main__':
    chef = TESSIndiaChef()
    chef.main()
