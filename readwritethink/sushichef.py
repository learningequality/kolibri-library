#!/usr/bin/env python

from bs4 import BeautifulSoup
from bs4 import Tag
from collections import OrderedDict, defaultdict
import copy
from http import client
import gettext
import json
from le_utils.constants import licenses, content_kinds, file_formats
import logging
import os
#import pafy
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
from utils import get_level_map
import urllib.parse as urlparse
import youtube_dl


# Additional Constants
################################################################################
LOGGER = logging.getLogger()
__logging_handler = logging.StreamHandler()
LOGGER.addHandler(__logging_handler)
LOGGER.setLevel(logging.INFO)

# BASE_URL is used to identify when a resource is owned by Edsitement
BASE_URL = "http://www.readwritethink.org"

# If False then no download is made
# for debugging proporses
DOWNLOAD_VIDEOS = True

# time.sleep for debugging proporses, it helps to check log messages
TIME_SLEEP = .6

DATA_DIR = "chefdata"

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
    obj_id = "30100"
    collection_type = "Strategy Guide"
    url = "http://www.readwritethink.org/resources/resource-print.html?id={}".format(obj_id)
    channel_tree = dict(
        source_domain="www.readwritethink.org",
        source_id='readwritethink',
        title='ReadWriteThink',
        description=""""Here at ReadWriteThink, our mission is to provide educators, parents, and afterschool professionals with access to the highest quality practices in reading and language arts instruction by offering the very best in free materials."""[:400], #400 UPPER LIMIT characters allowed 
        thumbnail=None,#"http://www.readwritethink.org/images/rwt-243.gif",
        language="en",
        children=[],
        license=get_license(licenses.CC_BY, copyright_holder="ReadWriteThink").as_dict(),
    )

    try:
        print_page = PrintPage()
        print_page.search_printpage_url(url)
        print_page.get_type()
        print_page.get_grades()

        collection = Collection(source_id=url,
            type=collection_type,
            obj_id=obj_id)
        collection.to_file()
        collection.to_node(channel_tree)
    except requests.exceptions.HTTPError as e:
        LOGGER.info("Error: {}".format(e))

    return channel_tree


class ResourceBrowser(object):
    def __init__(self, resource_url, get_only_id=False):
        self.resource_url = resource_url
        self.get_only_id = get_only_id

    def get_resource_data(self, limit_page=1):
        pass

    def build_pagination_url(self, page):
        params = {'page': page}
        url_parts = list(urlparse.urlparse(self.resource_url))
        query = dict(urlparse.parse_qsl(url_parts[4]))
        query.update(params)
        url_parts[4] = urlencode(query)
        return urlparse.urlunparse(url_parts)

    def get_total_items(self, text):
        string = re.search(r"\d+\-\d+ of \d+", text).group()
        return int(string.split("of")[-1].strip())

    def run(self, limit_page=1):
        page_number = 1
        total_items = None
        counter = 0
        urls = set([])
        while total_items is None or counter < total_items:
            url = self.build_pagination_url(page_number)
            try:
                page_contents = downloader.read(url, loadjs=False)
            except requests.exceptions.HTTPError as e:
                LOGGER.info("Error: {}".format(e))
            else:
                LOGGER.info("CRAWLING : URL {}".format(url))
                page = BeautifulSoup(page_contents, 'html5lib')
                browser = page.find("ol", class_="results")
                if total_items is None:
                    results = page.find("h2", class_="results-hdr-l")
                    total_items = self.get_total_items(results.text)
                for a in browser.find_all(lambda tag: tag.name == "a"):
                    url = urljoin(BASE_URL, a["href"])
                    print_page = PrintPage()
                    print_page.search_printpage_url(url)
                    if self.get_only_id is False:
                        print_page.get_type()
                        print_page.get_grades()
                    counter += 1
                    yield dict(url=print_page.url, 
                        collection=print_page.type,
                        id=print_page.resource_id,
                        sub_type=print_page.sub_type,
                        grades=print_page.grades)
                LOGGER.info("  - {} of {}".format(counter, total_items))
                time.sleep(TIME_SLEEP)
                page_number += 1
                if limit_page is not None and page_number > limit_page:
                    break


class PrintPage(object):
    def __init__(self):
        self.url = None
        self.type = None
        self.sub_type = None
        self.grades = None
        self.resource_id = None
        self.page = None

    def search_printpage_url(self, url):
        try:
            page_contents = downloader.read(url, loadjs=False)
        except requests.exceptions.HTTPError as e:
            LOGGER.info("Error: {}".format(e))
        else:
            page = BeautifulSoup(page_contents, 'html.parser')
            print_page = page.find(lambda tag: tag.name == "a" and tag.findParent("img", id="icon-materials"))
            if print_page is not None:
                self.url = self.parse_js(print_page.attrs["onclick"])
                self.resource_id = self.url.split("id=")[-1]

    def get_type(self):
        if self.page is None and self.url is not None:
            try:
                page_contents = downloader.read(self.url, loadjs=False)
            except requests.exceptions.HTTPError as e:
                LOGGER.info("Error: {}".format(e))
            else:
                self.page = BeautifulSoup(page_contents, 'html.parser')

        if self.page is not None:
            h3 = self.page.find("h3", class_="pad3b")
            self.type = h3.text
            try:
                self.sub_type = self.page.find(text="Lesson Plan Type").findNext("td").text
            except:
                pass

    def get_grades(self):
        if self.page is None and self.url is not None:
            try:
                page_contents = downloader.read(self.url, loadjs=False)
            except requests.exceptions.HTTPError as e:
                LOGGER.info("Error: {}".format(e))
            else:
                self.page = BeautifulSoup(page_contents, 'html.parser')

        if self.page is not None:
            h3 = self.page.find("h3", class_="pad3b")
            try:
                self.grades = self.page.find(text=re.compile(r"^Grade")).findNext("td").text        
            except:
                pass

    def parse_js(self, value):
        init = value.find("/")
        end = value.find("',")
        return urljoin(BASE_URL, value[init:end]).strip()


class Collection(object):
    def __init__(self, source_id, type, obj_id=None, subtype=None, grades=None, 
        theme=None):
        self.page = self.download_page(source_id)
        if self.page is not False:
            self.title = self.clean_title(self.page.find("h1"))
            self.source_id = source_id
            self.type = type
            self.license = None
            self.lang = "en"
            self.obj_id = obj_id
            self.subtype = subtype
            self.grades = grades
            self.theme = "General" if theme is None or theme == "" else theme
            
            if self.type == "Lesson Plan":
                self.curriculum_type = LessonPlan()
            elif self.type == "Activity":
                self.curriculum_type = Activity()
            elif self.type == "Strategy Guide":
                self.curriculum_type = StrategyGuide()
            elif self.type == "Printout":
                self.curriculum_type = Printout()
            elif self.type == "Tip":
                self.curriculum_type = Tip()

    def download_page(self, url):
        tries = 0
        while tries < 4:
            try:
                document = downloader.read(url, loadjs=False, session=sess)
            except requests.exceptions.HTTPError as e:
                LOGGER.info("Error: {}".format(e))
            except requests.exceptions.ConnectionError:
                ### this is a weird error, may be it's raised when the webpage
                ### is slow to respond requested resources
                LOGGER.info("Connection error, the resource will be scraped in 5s...")
                time.sleep(3)
            else:
                page = BeautifulSoup(document, 'html5lib')#'html.parser') #html5lib
                return page.find("div", id="print-container")
            tries += 1
        return False

    def clean_title(self, title):
        if title is not None:
            text = title.text.replace("\t", " ").replace("/", "-")
            return text.strip()

    def drop_null_sections(self, menu):
        sections = OrderedDict()
        for section in self.curriculum_type.render(self, menu_filename=menu.filepath):
            #sections[section.__class__.__name__] = section
            sections[section.id] = section
        return sections

    ##activities, lessons, etc
    def topic_info(self):
        theme_node = dict(
            kind=content_kinds.TOPIC,
            source_id=self.theme,
            title=self.theme,
            description="",
            license=None,
            children=[]
        )

        topic_node = dict(
            kind=content_kinds.TOPIC,
            source_id=self.type,
            title=self.type,
            description="",
            license=None,
            children=[]
        )
        topic_node["children"].append(theme_node)
        if self.subtype is not None:
            subtopic_node = dict(
                kind=content_kinds.TOPIC,
                source_id=self.subtype,
                title=self.subtype,
                description="",
                license=None,
                children=[]
            )
            theme_node["children"].append(subtopic_node)
        else:
            subtopic_node = None
        return topic_node, theme_node, subtopic_node

    def to_file(self):
        from collections import namedtuple
        LOGGER.info(" + [{}|{}|{}]: {}".format(self.theme, self.type, self.subtype, self.title))
        LOGGER.info("   - URL: {}".format(self.source_id))
        copy_page = copy.copy(self.page)
        base_path = build_path([DATA_DIR, self.type, self.obj_id])
        filepath = "{path}/{title}.zip".format(path=base_path, 
            title=self.title)
        Menu = namedtuple('Menu', ['filepath'])
        menu = Menu(filepath=filepath)
        sections = self.drop_null_sections(menu)
        self.info = sections["quick"].info()
        author = sections["quick"].plan_info.get("lesson author", "")
        self.info["description"] = sections["overview"].overview
        license = get_license(licenses.CC_BY, copyright_holder=sections["info"].copyright).as_dict()
        self.info["license"] = license
        pdfs_info = sections["print-container"].build_pdfs_info(base_path, license)
        videos_info = sections["print-container"].build_videos_info(base_path, license)
        if self.type != "Printout": #To avoid nested printouts
            printouts_info = sections["print-container"].build_printouts_info()
        else:
            printouts_info = None
        sections["print-container"].clean_page()
        sections["print-container"].to_file()
        html_info = sections["print-container"].html_info(license, 
            self.info["description"], self.info["thumbnail"],
            author)

        if html_info is not None:
            self.info["children"].append(html_info)
        if pdfs_info is not None:
            self.info["children"] += pdfs_info
        if videos_info is not None:
            self.info["children"] += videos_info
        if printouts_info is not None:
            self.info["children"] += printouts_info

    def add_nodes(self, topic_node, theme_node):
        for children in topic_node["children"]:
            if children["source_id"] == theme_node["source_id"]:
                break
        else:
            topic_node["children"].append(theme_node)

    def to_node(self, tree):
        if tree is not None and\
            tree.get("source_id", None) != self.theme and\
            tree.get("source_id", None) != self.type and\
            self.subtype is not None:
            subtopic_node = get_level_map(tree, [self.type, self.theme, self.subtype])
            theme_node = get_level_map(tree, [self.type, self.theme])
            topic_node = get_level_map(tree, [self.type])
        elif tree is not None and\
            tree.get("source_id", None) != self.theme and\
            tree.get("source_id", None) != self.type:
            theme_node = get_level_map(tree, [self.type, self.theme])
            topic_node = get_level_map(tree, [self.type])
            subtopic_node = None
        elif tree is not None and tree.get("source_id", None) != self.type:
            topic_node = get_level_map(tree, [self.type])
            theme_node = None
            subtopic_node = None
        elif tree is None:
            theme_node = None
            topic_node = None
            subtopic_node = None
        else:
            topic_node = tree
            theme_node = None
            subtopic_node = None

        if self.type == "Printout":
            if tree is None:
                return self.info
            else:
                if topic_node is None:
                    topic_node, _, _ = self.topic_info()
                topic_node["children"].append(self.info)
                return topic_node
        elif topic_node is None:
            topic_node, theme_node, subtopic_node = self.topic_info()
            if subtopic_node is not None:
                subtopic_node["children"].append(self.info)
            else:
                self.add_nodes(theme_node, self.info)
            self.add_nodes(topic_node, theme_node)
            tree["children"].append(topic_node)
        elif topic_node is not None and theme_node is None:
            _, theme_node, subtopic_node = self.topic_info()
            if subtopic_node is not None:
                subtopic_node["children"].append(self.info)
                self.add_nodes(theme_node, subtopic_node)
            else:
                self.add_nodes(theme_node, self.info)
            self.add_nodes(topic_node, theme_node)
        elif topic_node is not None and theme_node is not None and subtopic_node is None:
            _, _, subtopic_node = self.topic_info()
            if subtopic_node is not None:
                subtopic_node["children"].append(self.info)
                theme_node["children"].append(subtopic_node)
            else:
                theme_node["children"].append(self.info)
            self.add_nodes(topic_node, theme_node)
        else:
            subtopic_node["children"].append(self.info)
        return theme_node


class CurriculumType(object):
    def render(self, collection, menu_filename):
        for meta_section in self.sections:
            Section = meta_section["class"]
            if isinstance(Section, list):
                section = sum([subsection(collection, filename=menu_filename, 
                                menu_name=meta_section["menu_name"])
                                for subsection in Section])
                section.id = meta_section["id"] 
            else:
                section = Section(collection, filename=menu_filename, id_=meta_section["id"], 
                                menu_name=meta_section["menu_name"])
            yield section


class LessonPlan(CurriculumType):
    def __init__(self, *args, **kwargs):
        self.sections = [
            {"id": "quick", "class": QuickLook, "menu_name": "quick_look"},
            {"id": "overview", "class": OverView, "menu_name": "overview"},
            {"id": "print-container", "class": PrintContainer, "menu_name": "body"},
            {"id": "info", "class": Copyright, "menu_name": "info"},
        ]


class StrategyGuide(CurriculumType):
    def __init__(self, *args, **kwargs):
        self.sections = [
            {"id": "quick", "class": QuickLook, "menu_name": "quick_look"},
            {"id": "overview", "class": AboutThis, "menu_name": "overview"},
            {"id": "print-container", "class": PrintContainer, "menu_name": "body"},
            {"id": "info", "class": Copyright, "menu_name": "info"},
        ]


class Printout(CurriculumType):
    def __init__(self, *args, **kwargs):
        self.sections = [
            {"id": "quick", "class": QuickLook, "menu_name": "quick_look"},
            {"id": "overview", "class": AboutThisPrintout, "menu_name": "overview"},
            {"id": "print-container", "class": PrintContainer, "menu_name": "body"},
            {"id": "info", "class": Copyright, "menu_name": "info"},
        ]


class Activity(CurriculumType):
    def __init__(self, *args, **kwargs):
        self.sections = [
            {"id": "quick", "class": QuickLook, "menu_name": "quick_look"},
            {"id": "overview", "class": OverView, "menu_name": "overview"},
            {"id": "print-container", "class": PrintContainer, "menu_name": "body"},
            {"id": "info", "class": Copyright, "menu_name": "info"},
        ]


class Tip(CurriculumType):
    def __init__(self, *args, **kwargs):
        self.sections = [
            {"id": "quick", "class": QuickLook, "menu_name": "quick_look"},
            {"id": "overview", "class": WhyUseTip, "menu_name": "overview"},
            {"id": "print-container", "class": PrintContainer, "menu_name": "body"},
            {"id": "info", "class": Copyright, "menu_name": "info"},
        ]


class CollectionSection(object):
    def __init__(self,  collection, filename=None, id_=None, menu_name=None):
        LOGGER.debug(id_)
        self.id = id_
        self.collection = collection
        self.filename = filename
        self.menu_name = menu_name
        self.img_url = None
        self.lang = "en"

    def __add__(self, o):
        if isinstance(self.body, Tag) and isinstance(o.body, Tag):
            parent = Tag(name="div")
            parent.insert(0, self.body)
            parent.insert(1, o.body)
            self.body = parent
        elif self.body is None and isinstance(o.body, Tag):
            self.body = o.body
        else:
            LOGGER.info("Null sections: {} and {}".format(
                self.__class__.__name__, o.__class__.__name__))

        return self

    def __radd__(self, o):
        return self

    def clean_title(self, title):
        if title is not None:
            title = str(title)
        return title

    def get_content(self):
        remove_iframes(self.body)
        remove_links(self.body)
        return "".join([str(p) for p in self.body])

    def get_pdfs(self):
        urls = {}
        if self.body is not None:
            resource_links = self.body.find_all("a", href=re.compile("\.pdf$"))
            for link in resource_links:
                if link["href"] not in urls:
                    filename = get_name_from_url(link["href"])
                    abs_url = urljoin(BASE_URL, link["href"].strip())
                    if filename.endswith(".pdf"):
                        urls[abs_url] = (filename, link.text, abs_url)
            return urls.values()

    def get_printouts(self):
        urls = {}
        if self.body is not None:
            resource_links = self.body.find_all("a", href=re.compile("\/printouts\/"))
            for link in resource_links:
                related_rs = link.findPrevious(lambda tag: tag.name == "h3" and\
                                            tag.text.lower() == "related resources")
                if related_rs is None and link["href"] not in urls and not link["href"].endswith(".pdf"):
                    abs_url = urljoin(BASE_URL, link["href"].strip())
                    url_parts = list(urlparse.urlparse(abs_url))[:3]
                    abs_url = urlparse.urlunparse(url_parts+['', '', ''])
                    if abs_url.endswith(".html") and abs_url.find("printouts") != -1:
                        urls[abs_url] = (link.text, abs_url)
            return urls.values()

    def build_pdfs_info(self, path, license=None):
        pdfs_urls = self.get_pdfs()
        if len(pdfs_urls) == 0:
            return

        PDFS_DATA_DIR = build_path([path, 'pdfs'])
        files_list = []
        for filename, name, pdf_url in pdfs_urls:
            try:
                response = downloader.read(pdf_url, session=sess, timeout=10)
                pdf_filepath = os.path.join(PDFS_DATA_DIR, filename)
                with open(pdf_filepath, 'wb') as f:
                    f.write(response)
                LOGGER.info("   - File: {}".format(filename))
                files = dict(
                    kind=content_kinds.DOCUMENT,
                    source_id=pdf_url,
                    title=name,
                    description='',
                    files=[dict(
                        file_type=content_kinds.DOCUMENT,
                        path=pdf_filepath
                    )],
                    language=self.lang,
                    license=license)
                files_list.append(files)
            except requests.exceptions.HTTPError as e:
                LOGGER.info("Error: {}".format(e))
            except requests.exceptions.ConnectionError as e:
                LOGGER.info("Error: {}".format(e))
            except requests.exceptions.TooManyRedirects as e:
                LOGGER.info("Error: {}".format(e))

        return files_list

    def build_printouts_info(self):
        printouts_urls = self.get_printouts()
        if len(printouts_urls) == 0:
            return
        
        node = None
        for name, url in printouts_urls:
            print_page = PrintPage()
            print_page.search_printpage_url(url)
            print_page.get_type()
            collection = Collection(
                source_id=print_page.url,
                type=print_page.type,
                obj_id=print_page.resource_id)
            collection.to_file()
            node = collection.to_node(node)
        if node is not None:
            return [node]
        else:
            return []

    def get_domain_links(self):
        return set([link.get("href", "") for link in self.body.find_all("a") if link.get("href", "").startswith("/")])

    def images_ref_to_local(self, images_ref, prefix=""):
        images = []
        for img in images_ref:
            if img["src"].startswith("/"):
                img_src = urljoin(BASE_URL, img["src"])
            else:
                img_src = img["src"]
            filename = get_name_from_url(img_src)
            img["src"] = prefix + filename
            images.append((img_src, filename))
        return images

    def get_imgs(self, prefix=""):
        images = self.images_ref_to_local(self.body.find_all("img"), prefix=prefix)
        if len(images) > 0:
            self.img_url = images[-1][0]
        return images

    def get_imgs_into_links(self, prefix=""):
        def check_link(tag):
            allowed_ext = ['jpg', 'jpeg', 'png', 'gif']
            img_ext = tag.attrs.get("href", "").split(".")[-1]
            return tag.name  == "a" and img_ext in allowed_ext
        return [a.get("href", None) for a in self.body.find_all(check_link)]

    def get_videos_urls(self):
        urls = set([])

        for iframe in self.body.find_all("iframe"):
            url = iframe["src"]
            if YouTubeResource.is_youtube(url):
                urls.add(YouTubeResource.transform_embed(url))
            iframe.extract()

        queue = self.body.find_all("a", href=re.compile("^http"))
        max_tries = 3
        num_tries = 0
        while queue:
            try:
                a = queue.pop(0)
                ### some links who are youtube resources have shorted thier ulrs
                ### with session.head we can expand it
                if check_shorter_url(a["href"]):
                    resp = sess.head(a["href"], allow_redirects=True, timeout=2)
                    url = resp.url
                else:
                    url = a["href"]
                if YouTubeResource.is_youtube(url, get_channel=False):
                    urls.add(url.strip())
            except (requests.exceptions.MissingSchema, requests.exceptions.ReadTimeout):
                LOGGER.info("Connection error with: {}".format(a["href"]))
            except requests.exceptions.TooManyRedirects:
                LOGGER.info("Too many redirections, skip resource: {}".format(a["href"]))
            except requests.exceptions.ConnectionError:
                ### this is a weird error, perhaps it's raised when the webpage
                ### is slow to respond requested resources
                LOGGER.info(a["href"])
                num_tries += 1
                LOGGER.info("Connection error, the resource will be scraped in 3s... num try {}".format(num_tries))
                if num_tries < max_tries:
                    queue.insert(0, a)
                else:
                    LOGGER.info("Connection error, give up.")
                time.sleep(3)
            except KeyError:
                pass
            else:
                num_tries = 0
        return urls

    def get_local_video_urls(self):
        urls = set([])
        local_videos_page = self.body.find_all(lambda tag: tag.name == "a" and\
            tag.attrs.get("href", "").find("video") != -1 and\
            (tag.attrs.get("href", "").startswith("/") or tag.attrs.get("href", "").find(BASE_URL) != -1))
        for link in local_videos_page:
                urls.add(urljoin(BASE_URL, link.get("href", "")).strip())
        return urls

    def build_videos_info(self, path, license=None):
        videos_urls = self.get_videos_urls()
        local_videos_urls = self.get_local_video_urls()
        if len(videos_urls) == 0 and len(local_videos_urls) == 0:
            return

        VIDEOS_DATA_DIR = build_path([path, 'videos'])
        videos_list = []
        for i, url in enumerate(videos_urls):
            resource = YouTubeResource(url, lang=self.lang)
            resource.to_file(filepath=VIDEOS_DATA_DIR)
            if resource.resource_file is not None:
                videos_list.append(resource.resource_file)

        video_resources = set([])
        for i, page_url in enumerate(local_videos_urls):
            urls = self.find_video_url(page_url)
            for url in urls:
                if url not in video_resources:
                    resource = LocalVideoResource(url, lang=self.lang)
                    resource.to_file(filepath=VIDEOS_DATA_DIR)
                    video_resources.add(url)
                    if resource.resource_file is not None:
                        videos_list.append(resource.resource_file)
        return videos_list

    def find_video_url(self, page_url):
        urls = set([])
        try:
            document = downloader.read(page_url, loadjs=False, session=sess)
        except requests.exceptions.HTTPError as e:
            LOGGER.info("Error: {}".format(e))
        except requests.exceptions.ConnectionError:
            ### this is a weird error, may be it's raised when the webpage
            ### is slow to respond requested resources
            LOGGER.info("Connection error, the resource will be scraped in 5s...")
            time.sleep(3)
        else:
            for rs in re.findall(r':\s"/.+\.mp4"', str(document)):
                rs = rs[3:-1]
                if rs.startswith("/"):
                    urls.add(urljoin(BASE_URL, rs))
                else:
                    start = rs.find("/")
                    urls.add(urljoin(BASE_URL, rs[start:]))
        return urls

    def write(self, filename, content):
        with html_writer.HTMLWriter(self.filename, "a") as zipper:
            zipper.write_contents(filename, content, directory="files")

    def write_img(self, url, filename):
        with html_writer.HTMLWriter(self.filename, "a") as zipper:
            zipper.write_url(url, filename, directory="files")

    def to_file(self, filename, menu_index=None):
        if self.body is not None and filename is not None:
            images = self.get_imgs()
            content = self.get_content()

            if menu_index is not None:
                html = '<html><head><meta charset="utf-8"><link rel="stylesheet" href="../css/styles.css"></head><body><div class="sidebar"><a class="sidebar-link toggle-sidebar-button" href="javascript:void(0)" onclick="javascript:toggleNavMenu();">&#9776;</a>{}</div><div class="main-content-with-sidebar">{}</div><script src="../js/scripts.js"></script></body></html>'.format(
                    menu_index, content)
            else:
                html = '<html><head><meta charset="utf-8"><link rel="stylesheet" href="../css/styles.css"></head><body><div class="main-content-with-sidebar">{}</div><script src="../js/scripts.js"></script></body></html>'.format(
                    content)

            self.write(filename, html)
            for img_src, img_filename in images:
                self.write_img(img_src, img_filename)


class QuickLook(CollectionSection):
    def __init__(self, collection, filename=None, id_="quick", menu_name="quick_look"):
        super(QuickLook, self).__init__(collection, filename=filename,
                id_=id_, menu_name=menu_name)
        img_src = self.get_thumbnail()
        if img_src is not None:
            filename = get_name_from_url(img_src).lower()
            filename_ext = filename.split(".")[-1]
            if filename_ext in ["jpg", "jpeg", "png"]:
                self.thumbnail = save_thumbnail(img_src, filename)
            else:
                self.thumbnail = None
        else:
            self.thumbnail = None
        self.plan_info = self.get_plan_info()
    
    def get_thumbnail(self):
        div = self.collection.page.find("div", class_="box-fade")
        if div is None:
            div = self.collection.page.find("div", class_="box-gray-d7-699")
            if div is None:
                div = self.collection.page.find("div", class_="box-aqua-695")
                if div is None:
                    div = self.collection.page.find("div", class_="box-salmon-695")
                    if div is None:
                        div = self.collection.page.find("div", class_="box-purple-695")

        img = div.find(lambda tag: tag.name == "img" and tag.findParent("p"))
        if img is not None:
            if img["src"].startswith("/"):
                return urljoin(BASE_URL, img["src"])
            else:
                return img["src"]

    def get_plan_info(self):
        table = self.collection.page.find("table", class_="plan-info")
        rows = table.find_all("td")
        data = {}
        for row_name, row_value in zip(rows[::2], rows[1::2]):
            key = row_name.text.strip().lower()
            if key == "publisher":
                a = row_value.find("a")
                data[key] = {"url": a["href"], "title": a["title"]}
            else:
                data[key] = row_value.text
        return data

    def info(self):
        return dict(
            kind=content_kinds.TOPIC,
            source_id=self.collection.source_id,
            title=self.collection.title,
            thumbnail=self.thumbnail,
            description="",
            license="",
            children=[]
        )


class OverView(CollectionSection):
    def __init__(self, collection, filename=None, id_="overview", menu_name="overview"):
        super(OverView, self).__init__(collection, filename=filename,
                id_=id_, menu_name=menu_name)
        self.get_overview()

    def get_overview(self):
        self.overview = self.collection.page.find(lambda tag: tag.name == "h3" and\
            tag.findChildren(lambda tag: tag.name == "a" and tag.attrs.get("name", "") == "overview"))
        node = self.overview.findNext("p")
        for i in range(5):
            if node.text is None or len(node.text) < 2:
                node = node.findNext("p")
            else:
                break
        self.overview = node.text


class AboutThis(CollectionSection):
    def __init__(self, collection, filename=None, id_="overview", menu_name="overview"):
        super(AboutThis, self).__init__(collection, filename=filename,
                id_=id_, menu_name=menu_name)
        self.get_overview()

    def get_overview(self):
        self.overview = self.collection.page.find(lambda tag: tag.name == "h3" and\
            tag.text == "About This Strategy Guide")
        if self.overview is not None:
            node = self.overview.findNext("div")
            for i in range(5):
                if node.text is None or len(node.text) < 2:
                    node = node.findNext("p")
                else:
                    break
            self.overview = node.text


class AboutThisPrintout(CollectionSection):
    def __init__(self, collection, filename=None, id_="overview", menu_name="overview"):
        super(AboutThisPrintout, self).__init__(collection, filename=filename,
                id_=id_, menu_name=menu_name)
        self.get_overview()

    def get_overview(self):
        self.overview = self.collection.page.find(lambda tag: tag.name == "td" and\
            tag.text.lower() == "about this printout")
        if self.overview is not None:
            node = self.overview.findNext("div")
        elif self.overview is None: 
            self.overview = self.collection.page.find(lambda tag: tag.name == "h3" and\
                tag.text.lower() == "about this printout")
            node = self.overview.findNext("p")
        for i in range(5):
            if node.text is None or len(node.text) < 2:
                node = node.findNext("p")
            else:
                break
        self.overview = node.text


class WhyUseTip(CollectionSection):
    def __init__(self, collection, filename=None, id_="overview", menu_name="overview"):
        super(WhyUseTip, self).__init__(collection, filename=filename,
                id_=id_, menu_name=menu_name)
        self.get_overview()

    def get_overview(self):
        self.overview = self.collection.page.find(lambda tag: tag.name == "h3" and\
            tag.text.lower() == "why use this tip")
        node = self.overview.findNext("p")
        for i in range(5):
            if node.text is None or len(node.text) < 2:
                node = node.findNext("p")
            else:
                break
        self.overview = node.text


class Copyright(CollectionSection):
    def __init__(self, collection, filename=None, id_="copyright", menu_name="copyright"):
        super(Copyright, self).__init__(collection, filename=filename,
                id_=id_, menu_name=menu_name)
        self.get_copyright_info()

    def get_copyright_info(self):
        p = self.collection.page.find("p", id="footer-l")
        if p is not None:
            p_text = p.text
            index = p_text.find("©")
            if index != -1:
                self.copyright = p_text[index:].strip().replace("\n", "").replace("\t", "")
                LOGGER.info("   - COPYRIGHT INFO:" + self.copyright)
            else:
                self.copyright = "ReadWriteThink"
        else:
            self.copyright = "ReadWriteThink"


class PrintContainer(CollectionSection):
    def __init__(self, collection, filename=None, id_="print-container", menu_name="body"):
        super(PrintContainer, self).__init__(collection, filename=filename,
                id_=id_, menu_name=menu_name)
        self.body = self.collection.page
        self.filepath = filename

    def html_info(self, license, description, thumbnail, author):
        return dict(
            kind=content_kinds.HTML5,
            source_id=self.collection.source_id,
            title=self.collection.title,
            description=description,
            thumbnail=thumbnail,
            author=author,
            files=[dict(
                file_type=content_kinds.HTML5,
                path=self.filepath
            )],
            language=self.lang,
            license=license)

    def clean_page(self):
        for script_tag in self.body.find_all("script"):
            script_tag.extract()
        self.body.find("p", id="page-url").decompose()
        tabs = self.body.find("div", class_="table-tabs-back")
        if tabs is not None:
            tabs.decompose()
        self.body.find("span", class_="print-page-button").decompose()
        self.body.find("div", id="email-share-print").decompose()
        for p in self.body.find_all(lambda tag: tag.name == "p" and\
            "txt-right" in tag.attrs.get("class", []) and tag.findChildren("img")):
            p.decompose()

        comments = self.body.find(lambda tag: tag.name == "h3" and tag.text == "Comments")
        if comments is not None:
            for section in comments.find_all_next():
                if section.name == "div" and section.attrs.get("id", "") == "footer":
                    break
                section.decompose()
            comments.decompose()
        remove_links(self.body)

    def write(self, content):
        with html_writer.HTMLWriter(self.filepath, "w") as zipper:
            zipper.write_index_contents(content)

    def write_css_js(self, filepath):
        with html_writer.HTMLWriter(filepath, "a") as zipper, open("chefdata/styles.css") as f:
            content = f.read()
            zipper.write_contents("styles.css", content, directory="css/")

        with html_writer.HTMLWriter(filepath, "a") as zipper, open("chefdata/scripts.js") as f:
            content = f.read()
            zipper.write_contents("scripts.js", content, directory="js/")

    def to_file(self):
        if self.body is not None:
            images = self.get_imgs(prefix="files/")
            html = '<html><head><meta charset="utf-8"><link rel="stylesheet" href="css/styles.css"></head><body><div class="main-content-with-sidebar">{}</div><script src="js/scripts.js"></script></body></html>'.format(self.body)
            self.write(html)
            self.write_css_js(self.filepath)
            LOGGER.info("  * " + self.filepath)
            for img_src, img_filename in images:
                self.write_img(img_src, img_filename)


class ResourceType(object):
    """
        Base class for File, WebPage, Video, Audio resources
    """
    def __init__(self, type_name=None):
        LOGGER.info("Resource Type: "+type_name)
        self.type_name = type_name
        self.resource_file = None

    def to_file(self, filepath=None):
        pass

    def add_resource_file(self, info):
        self.resource_file = info


class YouTubeResource(ResourceType):
    def __init__(self, resource_url, type_name="Youtube", lang="en"):
        super(YouTubeResource, self).__init__(type_name=type_name)
        self.resource_url = self.clean_url(resource_url)
        self.file_format = file_formats.MP4
        self.lang = lang
        self.filepath = None
        self.filename = None

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
        video_info = self.get_video_info()
        video_id = video_info["id"]
        subs = []
        if 'subtitles' in video_info:
            subtitles_info = video_info["subtitles"]
            for language in subtitles_info.keys():
                subs.append(dict(file_type=SUBTITLES_FILE, youtube_id=video_id, language=language))
        return subs

    def process_file(self, download=False, filepath=None):
        self.download(download=download, base_path=filepath)
        if self.filepath is not None:
            files = [dict(file_type=content_kinds.VIDEO, path=self.filepath)]
            files += self.subtitles_dict()

            self.add_resource_file(dict(
                kind=content_kinds.VIDEO,
                source_id=self.resource_url,
                title=self.filename,
                description='',
                files=files,
                language=self.lang,
                license=get_license(licenses.CC_BY, copyright_holder="ReadWriteThink").as_dict()))

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
        self.process_file(download=DOWNLOAD_VIDEOS, filepath=filepath)


class LocalVideoResource(ResourceType):
    def __init__(self, resource_url, type_name="Local Video", lang="en"):
        super(LocalVideoResource, self).__init__(type_name=type_name)
        self.resource_url = resource_url
        self.file_format = file_formats.MP4
        self.lang = lang

    def process_file(self, download=False, filepath=None):
        if download is True:
            video_filepath = self.video_download(download_to=filepath)
        else:
            video_filepath = None

        if video_filepath is not None:
            files = [dict(file_type=content_kinds.VIDEO, path=video_filepath)]

            self.add_resource_file(dict(
                kind=content_kinds.VIDEO,
                source_id=self.resource_url,
                title=get_name_from_url_no_ext(video_filepath),
                description='',
                files=files,
                language=self.lang,
                license=get_license(licenses.CC_BY, copyright_holder="ReadWriteThink").as_dict()))

    def video_download(self, download_to):
        r = requests.get(self.resource_url, stream=True)
        videp_filepath = os.path.join(download_to, get_name_from_url(self.resource_url))
        with open(videp_filepath, 'wb') as f:
            LOGGER.info("   - Downloading {}".format(self.resource_url))
            for chunk in r.iter_content(chunk_size=1024*4): 
                if chunk:
                    f.write(chunk)
                    f.flush()
        return videp_filepath

    def to_file(self, filepath=None):
        self.process_file(download=DOWNLOAD_VIDEOS, filepath=filepath)


class ReadWriteThinkChef(JsonTreeChef):
    ROOT_URL = "http://{HOSTNAME}"
    HOSTNAME = "www.readwritethink.org"
    TREES_DATA_DIR = os.path.join(DATA_DIR, 'trees')
    CRAWLING_STAGE_OUTPUT_TPL = 'web_resource_tree.json'
    SCRAPING_STAGE_OUTPUT_TPL = 'ricecooker_json_tree.json'
    LICENSE = get_license(licenses.CC_BY, copyright_holder="ReadWriteThink").as_dict()
    THUMBNAIL = "http://www.readwritethink.org/images/rwt-243.gif"

    def __init__(self):
        build_path([ReadWriteThinkChef.TREES_DATA_DIR])
        self.scrape_stage = os.path.join(ReadWriteThinkChef.TREES_DATA_DIR, 
                                ReadWriteThinkChef.SCRAPING_STAGE_OUTPUT_TPL)
        self.crawling_stage = os.path.join(ReadWriteThinkChef.TREES_DATA_DIR, 
                                ReadWriteThinkChef.CRAWLING_STAGE_OUTPUT_TPL)
        super(ReadWriteThinkChef, self).__init__()

    def download_css_js(self):
        r = requests.get("https://raw.githubusercontent.com/learningequality/html-app-starter/master/css/styles.css")
        with open("chefdata/styles.css", "wb") as f:
            f.write(r.content)

        r = requests.get("https://raw.githubusercontent.com/learningequality/html-app-starter/master/js/scripts.js")
        with open("chefdata/scripts.js", "wb") as f:
            f.write(r.content)

    def pre_run(self, args, options):
        css = os.path.join(os.path.dirname(os.path.realpath(__file__)), "chefdata/styles.css")
        js = os.path.join(os.path.dirname(os.path.realpath(__file__)), "chefdata/scripts.js")
        if not if_file_exists(css) or not if_file_exists(js):
            LOGGER.info("Downloading styles")
            self.download_css_js()
        self.crawl(args, options)
        self.scrape(args, options)

    def crawl(self, args, options):
        web_resource_tree = dict(
            kind='ReadWriteThinkResourceTree',
            title='ReadWriteThink',
            children=OrderedDict()
        )
        crawling_stage = os.path.join(ReadWriteThinkChef.TREES_DATA_DIR,                     
                                    ReadWriteThinkChef.CRAWLING_STAGE_OUTPUT_TPL)
        resources_theme = {
            "10": "Arts",
            "16": "Careers",
            "11": "Community",
            "13": "Drama",
            "18": "English-Language Learners",
            "17": "Family",
            "6": "Fiction",
            "19": "Mathematics",
            "25": "Mobile Learning",
            "9": "Non Fiction",
            "7": "Poetry",
            "5": "Science",
            "23": "Season / Holiday",
            "15": "Social Action",
            "22": "Social Studies / History",
            "21": "Sports",
            "24": "STEM"
        }

        themes_map = {}
        for theme_id, theme_name in resources_theme.items():
            curriculum_url = urljoin(ReadWriteThinkChef.ROOT_URL.format(HOSTNAME=ReadWriteThinkChef.HOSTNAME), "search/?theme={}".format(theme_id))
            resource_browser = ResourceBrowser(curriculum_url, get_only_id=True)
            for data in resource_browser.run(limit_page=None):
                themes_map[data["id"]] = theme_name

        resources_types = [(6, "Lesson Plans"), (70, "Activities & Projects"), 
            (74, "Tips & Howtos"), (56, "Strategy Guide"), (18, "Printouts")]
        for resource_id, resource_name in resources_types:
            curriculum_url = urljoin(ReadWriteThinkChef.ROOT_URL.format(HOSTNAME=ReadWriteThinkChef.HOSTNAME), "search/?resource_type={}".format(resource_id))
            resource_browser = ResourceBrowser(curriculum_url)
            for data in resource_browser.run(limit_page=None):
                theme_name = themes_map.get(data["id"], "")
                data["theme"] = theme_name
                web_resource_tree["children"][data["url"]] = data
        web_resource_tree["children"] = list(web_resource_tree["children"].values())
        with open(crawling_stage, 'w') as f:
            json.dump(web_resource_tree, f, indent=2)
        return web_resource_tree

    def scrape(self, args, options):
        cache_tree = options.get('cache_tree', '1')
        download_video = options.get('--download-video', "1")
        if int(download_video) == 0:
            global DOWNLOAD_VIDEOS
            DOWNLOAD_VIDEOS = False

        with open(self.crawling_stage, 'r') as f:
            web_resource_tree = json.load(f)
            assert web_resource_tree['kind'] == 'ReadWriteThinkResourceTree'
         
        #channel_tree = test()
        channel_tree = self._build_scraping_json_tree(cache_tree, web_resource_tree)
        self.write_tree_to_json(channel_tree, "en")

    def write_tree_to_json(self, channel_tree, lang):
        write_tree_to_json_tree(self.scrape_stage, channel_tree)

    def _build_scraping_json_tree(self, cache_tree, web_resource_tree):
        LANG = 'en'
        channel_tree = dict(
                source_domain=ReadWriteThinkChef.HOSTNAME,
                source_id='readwritethink',
                title='ReadWriteThink',
                description="""Here at ReadWriteThink, our mission is to provide educators, parents, and afterschool professionals with access to the highest quality practices in reading and language arts instruction by offering the very best in free materials."""[:400], #400 UPPER LIMIT characters allowed 
                thumbnail=None,#ReadWriteThinkChef.THUMBNAIL,
                language=LANG,
                children=[],
                license=ReadWriteThinkChef.LICENSE,
            )
        counter = 0
        total_size = len(web_resource_tree["children"])
        for resource in web_resource_tree["children"]:
            if 0 <= counter < total_size:
                LOGGER.info("{} of {}".format(counter, total_size))
                collection = Collection(source_id=resource["url"],
                                type=resource["collection"],
                                obj_id=resource["id"],
                                subtype=resource["sub_type"],
                                grades=resource["grades"],
                                theme=resource["theme"])
                collection.to_file()
                collection.to_node(channel_tree)
            counter += 1
        return channel_tree


# CLI: This code will run when `souschef.py` is called on the command line
################################################################################
if __name__ == '__main__':
    chef = ReadWriteThinkChef()
    chef.main()
