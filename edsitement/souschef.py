#!/usr/bin/env python
"""
Edsitement is organized as follow:
- There is two top levels set of topics, Lesson Plans and Student Resources
- Each topic has lessons and resources
- Finally, each lesson or resource has contents like images, videos, pdfs and html5 files.
"""

from collections import OrderedDict
import itertools
import logging
import os
from pathlib import Path
import re
import sys
import time
from urllib.error import URLError
from urllib.parse import urlparse, urljoin

from bs4 import BeautifulSoup, Tag
from le_utils.constants import licenses, file_formats
import pafy
import requests
from ricecooker.classes.files import download_from_web, config
from ricecooker.utils import data_writer, path_builder, downloader, html_writer
from ricecooker.utils.caching import CacheForeverHeuristic, FileCache, CacheControlAdapter
import youtube_dl


# Run Constants
################################################################################

CHANNEL_NAME = "EDSITEment"              # Name of channel
CHANNEL_SOURCE_ID = "edsitement-testing" # Channel's unique id    # change to just 'edsitement' for prod
CHANNEL_DOMAIN = "edsitement.neh.gov"         # Who is providing the content
CHANNEL_LANGUAGE = "en"      # Language of channel
CHANNEL_DESCRIPTION = """EDSITEment is a partnership between the National Endowment for the Humanities and the National Trust for the Humanities.

EDSITEment offers a treasure trove for teachers, students, and parents searching for high-quality material on the Internet in the subject areas of literature and language arts, foreign languages, art and culture, and history and social studies."""                                  # Description of the channel (optional)
CHANNEL_THUMBNAIL = "https://www.neh.gov/files/imagecache/explore_large/explore/images/edsitement.jpg"                                    # Local path or url to image file (optional)
PATH = path_builder.PathBuilder(channel_name=CHANNEL_NAME)  # Keeps track of path to write to csv
WRITE_TO_PATH = "{}{}{}.zip".format(os.path.dirname(os.path.realpath(__file__)), os.path.sep, CHANNEL_NAME) # Where to generate zip file



# Additional Constants
################################################################################

LOGGER = logging.getLogger()
__logging_handler = logging.StreamHandler()
LOGGER.addHandler(__logging_handler)
LOGGER.setLevel(logging.INFO)

# BASE_URL is used to identify when a resource is owned by Edsitement
BASE_URL = "http://edsitement.neh.gov"

# These constans restrict the number of subjects and student resources when it's
# doing the scrape
# for debugging proporses
STUDENT_RESOURCE_SUBJECT_INIT = 0
STUDENT_RESOURCE_SUBJECT_END = 4 #MAX 4 TOPICS OR NONE
STUDENT_RESOURCE_INIT = 0
STUDENT_RESOURCE_END = None

# Same with these, restrict the number of subjects and lessons plans when it's
# doing the scrape
# for debugging proporses
LESSON_PLANS_SUBJECT_INIT = 0
LESSON_PLANS_SUBJECT_END = 4
LESSON_PLANS_INIT = 0
LESSON_PLANS_END = None

# If False then no download is made
# for debugging proporses
DOWNLOAD_VIDEOS = True

# time.sleep for debugging proporses, it helps to check log messages
TIME_SLEEP = .2

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
def scrape_source(writer):
    """ scrape_source: Scrapes channel page and writes to a DataWriter
        Args: writer (DataWriter): class that writes data to folder/spreadsheet structure
        Returns: None
    """
    scrape_lesson_plans()
    scrape_student_resources()


# Helper Methods
################################################################################

def scrape_lesson_plans():
    """
        Scrape lesson plans from its urls
    """
    LESSONS_PLANS_URL = urljoin(BASE_URL, "lesson-plans")
    for lesson_plan_url, levels in lesson_plans(lesson_plans_subject(LESSONS_PLANS_URL)):
        subtopic_name = lesson_plan_url.split("/")[-1]
        try:
            page_contents = downloader.read(lesson_plan_url, session=sess)
        except requests.exceptions.HTTPError as e:
            LOGGER.info("Error: {}".format(e))
        else:
            page = BeautifulSoup(page_contents, 'html5lib')
            lesson_plan = LessonPlan(page,
                lesson_filename="/tmp/lesson-"+subtopic_name+".zip",
                resources_filename="/tmp/resources-"+subtopic_name+".zip")
            lesson_plan.source = lesson_plan_url
            lesson_plan.to_file(PATH, levels)


def lesson_plans_subject(page_url):
    """
        Scrape lesson plans subjects
        25 -> Art & Culture
        21 -> Foreign Language
        22 -> History & Social Studies
        23 -> Literature & Language Arts
    """
    page_contents = downloader.read(page_url, session=sess)
    LOGGER.info("Scrapping: " + page_url)
    page = BeautifulSoup(page_contents, 'html.parser')
    subject_ids = [25, 21, 22, 23]#, 18319, 18373, 25041, 31471]
    for node in subject_ids:
        page_h3 = page.find("h3", id="node-"+str(node))
        resource_a = page_h3.find("a", href=True)
        subtopic_url = urljoin(BASE_URL, resource_a["href"].strip())
        yield subtopic_url, ["Lesson Plans or For Teachers"]


def lesson_plans(lesson_plans_subject):
    """
    Scrape lesson plans from the lessons list of each subject
    http://edsitement.neh.gov/subject/<subject>
    """
    for lesson_url, levels in itertools.islice(lesson_plans_subject, LESSON_PLANS_SUBJECT_INIT, LESSON_PLANS_SUBJECT_END): #MAX NUMBER OF SUBJECTS
        page_contents = downloader.read(lesson_url, session=sess)
        page = BeautifulSoup(page_contents, 'html.parser')
        sub_lessons = page.find_all("div", class_="lesson-plan-link")
        title = page.find("h2", class_="subject-area").text
        LOGGER.info("- Subject:"+title)
        LOGGER.info("- [url]:"+lesson_url)
        for seq, sub_lesson in enumerate(itertools.islice(sub_lessons, LESSON_PLANS_INIT, LESSON_PLANS_END)): #MAX NUMBER OF LESSONS
            resource_a = sub_lesson.find("a", href=True)
            resource_url = resource_a["href"].strip()
            LOGGER.info("SEQ ID: {}".format(LESSON_PLANS_INIT+seq))
            time.sleep(TIME_SLEEP)
            yield urljoin(BASE_URL, resource_url), levels + [title]


def scrape_student_resources():
    """
    Scrape student resources from the main page http://edsitement.neh.gov/student-resources
    """
    STUDENT_RESOURCES_URL = urljoin(BASE_URL, "student-resources/")
    subject_ids = [25, 21, 22, 23]
    levels = ["Student Resources"]
    for subject in subject_ids[STUDENT_RESOURCE_SUBJECT_INIT:STUDENT_RESOURCE_SUBJECT_END]:
        params_url = "all?grade=All&subject={}&type=All".format(subject)
        page_url = urljoin(STUDENT_RESOURCES_URL, params_url)
        LOGGER.info("Scrapping: " + page_url)
        page_contents = downloader.read(page_url, session=sess)
        page = BeautifulSoup(page_contents, 'html.parser')
        resource_links = page.find_all(lambda tag: tag.name == "a" and tag.findParent("h3"))
        for link in resource_links[STUDENT_RESOURCE_INIT:STUDENT_RESOURCE_END]:
            time.sleep(TIME_SLEEP)
            if link["href"].rfind("/student-resource/") != -1:
                student_resource_url = urljoin(BASE_URL, link["href"])
                try:
                    page_contents = downloader.read(student_resource_url, session=sess)
                except requests.exceptions.HTTPError as e:
                    LOGGER.info("Error: {}".format(e))
                page = BeautifulSoup(page_contents, 'html.parser')
                topic_name = student_resource_url.split("/")[-1]
                student_resource = StudentResourceIndex(page,
                    filename="/tmp/student-resource-"+topic_name+".zip",
                    levels=levels)
                student_resource.to_file()


def get_name_from_url(url):
    return os.path.basename(urlparse(url).path)


def get_name_from_url_no_ext(url):
    path = get_name_from_url(url)
    return ".".join(path.split(".")[:-1])


def remove_links(content):
    if content is not None:
        for link in content.find_all("a"):
            link.replaceWithChildren()


#add a span tag as parent to an "a" element and his href 
def link_to_text(content):
    if content is not None:
        for tag in content.find_all("a"):
            span = Tag(name="span")
            if tag.get("href", ""):
                url = tag["href"]
                if url.endswith(".pdf"):
                    pass
                elif url.startswith("http") or url.startswith("/"):
                    tag.wrap(span)
                    span.insert(1, " ("+url+")")


def has_copyright(content):
    for license in content.findAll(text=re.compile('license', flags=re.IGNORECASE)):
        license = license.lower()
        if license.find("©") != -1 or license.find("all rights reserved") != -1:
            return True
    return False


def if_file_exists(filepath):
    file_ = Path(filepath)
    return file_.is_file()


class Menu(object):
    """
        This class checks elements on the lesson menu and build the menu list
    """
    def __init__(self, page, filename=None, id_=None):
        self.body = page.find("div", id=id_)
        self.menu = OrderedDict()
        self.filename = filename
        self.menu_titles(self.body.find_all("h4"))

    def write(self, content):
        with html_writer.HTMLWriter(self.filename, "w") as zipper:
            zipper.write_index_contents(content)

    def to_file(self):
        html = '<html><head><meta charset="utf-8"><link rel="stylesheet" href="css/styles.css"></head><body><div class="main-content-with-sidebar">{}</div><script src="js/scripts.js"></script></body></html>'.format(self.to_html())
        self.write(html)

    def menu_titles(self, titles):
        for title in titles:
            self.add(title.text)

    def get(self, name):
        try:
            return self.menu[name]["filename"]
        except KeyError:
            return None

    def add(self, title):
        name = title.lower().replace(" ", "_")
        self.menu[name] = {
            "filename": "{}.html".format(name),
            "text": title
        }

    def to_html(self, directory="files/", active_li=None):
        li = ['<ul class="sidebar-items">']
        for e in self.menu.values():
            li.append("<li>")
            li.append('<a href="{directory}{filename}" class="sidebar-link">{text}</a>'.format(directory=directory, **e))
            li.append("</li>")
        li.append("</ul>")
        return "".join(li)


class LessonSection(object):
    """
        Base class for the menu setions
    """
    def __init__(self, page, filename=None, id_=None, menu_name=None):
        LOGGER.debug(id_)
        self.body = page.find("div", id=id_)
        if self.body is not None:
            self.title = self.clean_title(self.body.find("h4"))
        self.filename = filename
        self.menu_name = menu_name

    def clean_title(self, title):
        if title is not None:
            title = str(title)
        return title

    def get_content(self):
        content = self.body.find("div", class_="text")
        link_to_text(content)
        remove_links(content)
        return "".join([str(p) for p in content])

    def write(self, filename, content):
        with html_writer.HTMLWriter(self.filename, "a") as zipper:
            zipper.write_contents(filename, content, directory="files")

    def write_css_js(self, filepath):
        with html_writer.HTMLWriter(filepath, "a") as zipper, open("chefdata/styles.css") as f:
            content = f.read()
            zipper.write_contents("styles.css", content, directory="css/")

        with html_writer.HTMLWriter(filepath, "a") as zipper, open("chefdata/scripts.js") as f:
            content = f.read()
            zipper.write_contents("scripts.js", content, directory="js/")

    def to_file(self, filename, menu_index=None):
        if self.body is not None and filename is not None:
            content = self.get_content()
            if self.title:
                content = self.title+""+content

            if menu_index is not None:
                html = '<html><head><meta charset="utf-8"><link rel="stylesheet" href="../css/styles.css"></head><body><div class="sidebar"><a class="sidebar-link toggle-sidebar-button" href="javascript:void(0)" onclick="javascript:toggleNavMenu();">&#9776;</a>{}</div><div class="main-content-with-sidebar">{}</div><script src="../js/scripts.js"></script></body></html>'.format(menu_index, content)
            else:
                html = '<html><head><meta charset="utf-8"><link rel="stylesheet" href="../css/styles.css"></head><body><div class="main-content-with-sidebar">{}</div><script src="../js/scripts.js"></script></body></html>'.format(content)

            self.write(filename, html)
            self.write_css_js(self.filename)


class Introduction(LessonSection):
    def __init__(self, page, filename=None):
        super(Introduction, self).__init__(page, filename=filename,
            id_="sect-introduction", menu_name="introduction")


class GuidingQuestions(LessonSection):
    def __init__(self, page, filename=None):
        super(GuidingQuestions, self).__init__(page, filename=filename,
            id_="sect-questions", menu_name="guiding_questions")


class LearningObjetives(LessonSection):
    def __init__(self, page, filename=None):
        super(LearningObjetives, self).__init__(page, filename=filename,
            id_="sect-objectives", menu_name="learning_objectives")


class Background(LessonSection):
    def __init__(self, page, filename=None):
        super(Background, self).__init__(page, filename=filename,
            id_="sect-background", menu_name="background")


class PreparationInstructions(LessonSection):
    def __init__(self, page, filename=None):
        super(PreparationInstructions, self).__init__(page, filename=filename,
            id_="sect-preparation", menu_name="preparation_instructions")


class LessonActivities(LessonSection):
    def __init__(self, page, filename=None):
        super(LessonActivities, self).__init__(page, filename=filename,
            id_="sect-activities", menu_name="lesson_activities")


class Assessment(LessonSection):
    def __init__(self, page, filename=None):
        super(Assessment, self).__init__(page, filename=filename,
            id_="sect-assessment", menu_name="assessment")


class ExtendingTheLesson(LessonSection):
    def __init__(self, page, filename=None):
        super(ExtendingTheLesson, self).__init__(page, filename=filename,
            id_="sect-extending", menu_name="extending_the_lesson")


class TheBasics(LessonSection):
    def __init__(self, page, filename=None):
        super(TheBasics, self).__init__(page, filename=filename,
            id_="sect-thebasics", menu_name="the_basics")

    def get_content(self):
        link_to_text(self.body)
        remove_links(self.body)
        return str(self.body)


class Resources(object):
    """
        class for extracting elements from the resources panel on the lesson
    """
    def __init__(self, page, filename=None):
        self.body = page.find("div", id="sect-resources")
        self.filename = filename

    def get_img_url(self):
        resource_img = self.body.find("li", class_="lesson-image")
        if resource_img is not None:
            if not has_copyright(resource_img):
                img_tag = resource_img.find("img")
                return img_tag["src"]
            else:
                LOGGER.info("  ------- IMAGE WITH COPYRIGHT")
                LOGGER.info(resource_img.text)
                LOGGER.info("  -------")

    def get_credits(self):
        resource_img = self.body.find("li", class_="lesson-image")
        if resource_img is not None:
            link_to_text(resource_img)
            remove_links(resource_img)
            credits = "".join(map(str, resource_img.findChildren("p")))
            return credits

    def get_pdfs(self):
        resource_links = self.body.find_all("a")
        pdfs = []
        for link in resource_links:
            if link.get("href", "").endswith(".pdf"):
                name = get_name_from_url(link["href"])
                LOGGER.info("   + Filename: {}".format(name))
                pdfs.append((name, urljoin(BASE_URL, link["href"])))
        return pdfs

    def student_resources(self):
        resources = self.body.find("dd", id="student-resources")
        if resources is not None:
            for link in resources.find_all("a"):
                yield link["href"]

    def write_img(self, img_url, filename):
        with html_writer.HTMLWriter(self.filename, "a") as zipper:
            zipper.write_url(img_url, filename, directory="files")

    def write_index(self, content):
        with html_writer.HTMLWriter(self.filename, "w") as zipper:
            zipper.write_index_contents(content)

    def write(self, content, img_url, filename):
        self.write_index(content)
        self.write_img(img_url, filename)

    def to_file(self):
        img_url = self.get_img_url()
        if img_url is not None:
            response = requests.get(img_url)
            if response.status_code == 200:
                filename = get_name_from_url(img_url)
                img_tag = "<img alt='{img}' src='files/{img}'>".format(img=filename)
                html = '<html><head><meta charset="UTF-8"></head><body>{}{}</body></html>'.format(
                    img_tag, self.get_credits())
                self.write(html, img_url, filename)


class LessonPlan(object):
    """
        This class analyze each menu section and save it to a folder
    """
    def __init__(self, page, lesson_filename=None, resources_filename=None):
        self.page = page
        self.title = self.clean_title(self.page.find("div", id="description"))
        self.menu = Menu(self.page, filename=lesson_filename, id_="sect-thelesson")
        self.menu.add("The Basics")
        self.sections = [
            Introduction,
            GuidingQuestions,
            LearningObjetives,
            Background,
            PreparationInstructions,
            LessonActivities,
            Assessment,
            ExtendingTheLesson,
            TheBasics
        ]
        self.resources = Resources(self.page, filename=resources_filename)
        self.source = None

    def clean_title(self, title):
        if title is not None:
            title = title.text.strip()
            title = re.sub("\n|\t", " ", title)
            title = re.sub(" +", " ", title)
        return title

    def rename_pdfs(self, pdfs):
        renamed_pdf_files = []
        for _, pdf_url in pdfs:
            name = "{}.pdf".format(self.title)
            LOGGER.info("   + Filename renamed: {}".format(name))
            renamed_pdf_files.append((name, pdf_url))
        return renamed_pdf_files

    def to_file(self, PATH, levels):
        LOGGER.info(" + Lesson:"+ self.title)
        self.menu.to_file()
        for Section in self.sections:
            section = Section(self.page, filename=self.menu.filename)
            menu_filename = self.menu.get(section.menu_name)
            menu_index = self.menu.to_html(directory="", active_li=menu_filename)
            section.to_file(menu_filename, menu_index=menu_index)
        #self.resources.to_file() download and save images
        metadata_dict = {"description": "",
            "language": "en",
            "license": licenses.CC_BY,
            "copyright_holder": "National Endowment for the Humanities",
            "author": "",
            "source_id": self.source}

        levels.append(self.title)
        PATH.set(*levels)
        writer.add_file(str(PATH), "THE LESSON", self.menu.filename, **metadata_dict)
        writer.add_folder(str(PATH), "RESOURCES", **metadata_dict)
        PATH.set(*(levels+["RESOURCES"]))
        ##rename pdf files when the lesson have only one file
        pdfs = self.resources.get_pdfs()
        if len(pdfs) == 1:
            pdfs = self.rename_pdfs(pdfs)

        for name, pdf_url in pdfs:
            meta = metadata_dict.copy()
            meta["source_id"] = pdf_url
            try:
                writer.add_file(str(PATH), name.replace(".pdf", ""), pdf_url, **meta)
            except requests.exceptions.HTTPError as e:
                LOGGER.info("Error: {}".format(e))
        if if_file_exists(self.resources.filename):
            writer.add_file(str(PATH), "MEDIA", self.resources.filename, **metadata_dict)
            self.rm(self.resources.filename)
        #resource.student_resources() external web page
        PATH.go_to_parent_folder()
        PATH.go_to_parent_folder()

    def rm(self, filepath):
        os.remove(filepath)


class StudentResourceIndex(object):
    def __init__(self, page, filename=None, levels=None):
        self.body = page
        self.filename = filename
        self.title = None
        self.levels = levels

    def get_img_url(self):
        resource_img = self.body.find("div", class_="image")
        if resource_img is not None:
            img_tag = resource_img.find("img")
            if img_tag is not None:
                return img_tag["src"]

    def get_credits(self):
        credits = self.body.find("div", class_="caption")
        credits_elems = credits.find_all("div")
        type_ = credits_elems[0]
        LOGGER.info(type_.text)
        source = credits_elems[1]
        return "<div>{}</div><div>{}</div>".format(type_, source.text)

    def get_viewmore(self):
        view_more = self.body.find(lambda tag: tag.name == "a" and\
                                    tag.findParent("div", class_="more"))
        return view_more["href"]

    def get_content(self):
        content = self.body.find("div", id="description")
        self.title = content.find("h2")
        created = content.find("div", class_="created")
        self.description = content.find("p")
        if self.description is not None:
            link_to_text(self.description)
            remove_links(self.description)
        return "".join(map(str, [self.title, created, self.description]))

    def write_img(self, img_url, filename):
        with html_writer.HTMLWriter(self.filename, "a") as zipper:
            path = zipper.write_url(img_url, filename, directory="files")

    def write_index(self, content):
        with html_writer.HTMLWriter(self.filename, "w") as zipper:
            zipper.write_index_contents(content)

    def write(self, content, img_url, filename):
        self.write_index(content)
        if img_url is not None:
            self.write_img(img_url, filename)

    def to_file(self):
        img_url = None#self.get_img_url()
        if img_url is not None:
            filename_img = get_name_from_url(img_url)
            img_tag = "<img alt='{img}' src='files/{img}'>".format(img=filename_img)
        else:
            img_tag = ""
            filename_img = ""

        content = self.get_content()
        html = '<html><head><meta charset="UTF-8"></head><body>{}{}{}</body></html>'.format(
            content, img_tag, self.get_credits())
        self.write(html, img_url, filename_img)
        resource_checker = ResourceChecker(self.get_viewmore())
        resource = resource_checker.check()
        description = "" if self.description is None else self.description.text
        levels = self.levels + [self.title.text]
        metadata_dict = resource.to_file(description, self.filename)
        if metadata_dict is not None:
            PATH.set(*levels)
            writer.add_file(str(PATH), "THE LESSON", self.filename, **metadata_dict)
            if resource.resources_files is not None:
                writer.add_folder(str(PATH), "RESOURCES", **metadata_dict)
                PATH.set(*(levels+["RESOURCES"]))
                for file_src, file_metadata in resource.resources_files:
                    try:
                        meta = file_metadata if len(file_metadata) > 0 else metadata_dict
                        filename = get_name_from_url_no_ext(file_src)
                        if file_src.endswith(".pdf"):
                            filename = "{}_{}".format(self.title.text, filename)
                            LOGGER.info("   * " + filename)
                        writer.add_file(str(PATH), filename, file_src, **meta)
                    except requests.exceptions.HTTPError as e:
                        LOGGER.info("Error: {}".format(e))
                PATH.go_to_parent_folder()
            PATH.go_to_parent_folder()


class ResourceChecker(object):
    def __init__(self, resource_url):
        LOGGER.info("Resource url:"+resource_url)
        self.resource_url = resource_url

    def has_file(self):
        files = [(self.resource_url.endswith(filetype), filetype)
                for filetype in ["pdf", "mp4", "mp3", "swf", "jpg"]]
        file_ = list(filter(lambda x: x[0], files))
        if len(file_) > 0:
            return file_[0][1]
        else:
            return None

    def check(self):
        file_ = self.has_file()
        #edsitement has resources on 208.254.21.241 but is not reachable
        if self.resource_url.find(BASE_URL) != -1 and file_ is None:
            return WebPageSource(self.resource_url)
        elif self.resource_url.find(BASE_URL) != -1 and file_ is not None and\
            file_ != "swf" and file_ != "jpg":
            return FileSource(self.resource_url)
        elif self.resource_url.find(BASE_URL) != -1 and file_ == "jpg":
            return ImageSource(self.resource_url)
        elif self.resource_url.find("interactives.mped.org") != -1:
            return ResourceType("interactives") #response error
        elif file_ == "swf":
            return ResourceType("flash")
        elif self.resource_url.find("youtu.be") != -1 or\
            self.resource_url.find("youtube.com") != -1:
            return YouTubeResource(self.resource_url)
        elif self.resource_url.find("vimeo.com") != -1:
            return VimeoResource(self.resource_url)
        elif self.resource_url.find("soundcloud.com") != -1:
            return SoundCloudResource(self.resource_url)
        else:
            return ResourceType("unknown")


class ResourceType(object):
    """
        Base class for File, WebPage, Video, Audio resources
    """
    def __init__(self, type_name=None):
        LOGGER.info("Resource Type: "+type_name)
        self.type_name = type_name
        self.resources_files = None

    def to_file(self, description, filename):
        pass

    def add_resources_files(self, src, metadata, local=False):
        if self.resources_files is None:
            self.resources_files  = []
        if local is True:
            self.resources_files.append((src, metadata))
        else:
            self.resources_files.append((urljoin(BASE_URL, src), metadata))


class FileSource(ResourceType):
    def __init__(self, resource_url, type_name="File"):
        super(FileSource, self).__init__(type_name=type_name)
        self.resource_url = resource_url

    def to_file(self, description, filename):
        metadata_dict = {"description": description,
            "language": "en",
            "license": licenses.CC_BY,
            "copyright_holder": "National Endowment for the Humanities",
            "author": "",
            "source_id": self.resource_url}
        self.add_resources_files(self.resource_url, metadata_dict)
        return metadata_dict


class ImageSource(ResourceType):
    def __init__(self, resource_url, type_name="Image"):
        super(ImageSource, self).__init__(type_name=type_name)
        self.resource_url = resource_url

    def write(self, content, filepath, img_filename):
        self.write_index(content, filepath)
        self.write_img(self.resource_url, filepath, img_filename)

    def write_index(self, content, filepath):
        with html_writer.HTMLWriter(filepath, "w") as zipper:
            zipper.write_index_contents(content)

    def write_img(self, img_url, filepath, img_filename):
        with html_writer.HTMLWriter(filepath, "a") as zipper:
            path = zipper.write_url(img_url, img_filename, directory="files")

    def to_file(self, description, filepath):
        metadata_dict = {"description": description,
            "language": "en",
            "license": licenses.CC_BY,
            "copyright_holder": "National Endowment for the Humanities",
            "author": "",
            "source_id": self.resource_url}
        img_filename = get_name_from_url(self.resource_url)
        img_tag = "<img alt='{img}' src='files/{img}'>".format(img=img_filename)
        html = "<html><body>{}</body></html>".format(img_tag)
        self.write(html, filepath, img_filename)
        return metadata_dict


class WebPageSource(ResourceType):
    def __init__(self, resource_url, type_name="Web Page"):
        super(WebPageSource, self).__init__(type_name=type_name)
        self.resource_url = resource_url

    def write(self, content, filepath):
        self.write_index(content, filepath)

    def write_index(self, content, filepath):
        with html_writer.HTMLWriter(filepath, "w") as zipper:
            zipper.write_index_contents(content)

    def write_css_js(self, filepath):
        with html_writer.HTMLWriter(filepath, "a") as zipper, open("chefdata/styles.css") as f:
            content = f.read()
            zipper.write_contents("styles.css", content, directory="css/")

        with html_writer.HTMLWriter(filepath, "a") as zipper, open("chefdata/scripts.js") as f:
            content = f.read()
            zipper.write_contents("scripts.js", content, directory="js/")

    def swf_content(self, content):
        obj = content.find("object")
        if obj is not None and obj["type"] == "application/x-shockwave-flash":
            return True
        return False

    def to_file(self, description, filepath):
        try:
            page_contents = downloader.read(self.resource_url, session=sess)
        except requests.exceptions.HTTPError as e:
            LOGGER.info("Error: {}".format(e))
            return None
        else:
            metadata_dict = {"description": description,
                "language": "en",
                "license": licenses.CC_BY,
                "copyright_holder": "National Endowment for the Humanities",
                "author": "",
                "source_id": self.resource_url}
            page = BeautifulSoup(page_contents, 'html.parser')
            LOGGER.info("COPYRIGHT {}".format(has_copyright(page)))
            content = page.find("div", id="content")
            if self.swf_content(content):
                return
            files = self.remove_external_links(content)
            images = self.find_local_images(content)
            for file_ in files:
                metadata_files = metadata_dict.copy()
                metadata_files["source_id"] = file_
                self.add_resources_files(file_, metadata_files)
            #for img in images:
            #    self.add_resources_files(img)
            self.write('<html><head><meta charset="utf-8"><link rel="stylesheet" href="css/styles.css"></head><body><div class="main-content-with-sidebar">'+str(content)+'</div><script src="js/scripts.js"></script></body></html>', filepath)
            self.write_css_js(filepath)
            return metadata_dict

    def remove_external_links(self, content):
        files = []
        for link in content.find_all("a"):
            href = link.get("href", "")
            if href.find(BASE_URL) != -1 or href.startswith("#") or\
                href.startswith("/") or href == "":
                if href.endswith("pdf"):
                    files.append(href)
            link.replaceWithChildren()
        return files

    def find_local_images(self, content):
        images = []
        for img_tag in content.find_all("img"):
            src = img_tag.get("src", "")
            if src.startswith("/") or src.find(BASE_URL) != -1:
                images.append(src)
            img_tag.replaceWithChildren()
        return images


class YouTubeResource(ResourceType):
    def __init__(self, resource_url, type_name="Youtube"):
        super(YouTubeResource, self).__init__(type_name=type_name)
        self.resource_url = resource_url
        self.file_format = file_formats.MP4

    def process_file(self, download=False):
        ydl_options = {
            #'outtmpl': '%(title)s-%(id)s.%(ext)s',
            #'format': 'bestaudio/best',
            'writethumbnail': False,
            'no_warnings': True,
            'continuedl': False,
            'restrictfilenames':True,
            'quiet': False,
            'format': "bestvideo[height<={maxheight}][ext=mp4]+bestaudio[ext=m4a]/best[height<={maxheight}][ext=mp4]".format(maxheight='720'),
        }

        with youtube_dl.YoutubeDL(ydl_options) as ydl:
            try:
                ydl.add_default_info_extractors()
                info = ydl.extract_info(self.resource_url, download=False)
                if info["license"] == "Standard YouTube License" or info["license"] is None:
                    if download is True:
                        filepath = self.video_download()
                    else:
                        filepath = None

                    if filepath is not None:
                        self.add_resources_files(filepath, {}, local=True)
                        return True
            except(youtube_dl.utils.DownloadError, youtube_dl.utils.ContentTooShortError,
                    youtube_dl.utils.ExtractorError) as e:
                LOGGER.info('error_occured ' + str(e))

    #youtubedl has some troubles downloading videos in youtube,
    #sometimes raises connection error
    #for that I choose pafy for downloading
    def video_download(self):
        for try_number in range(10):
            try:
                video = pafy.new(self.resource_url)
                best = video.getbest(preftype="mp4")
                filepath = best.download(filepath="/tmp/")
            except (URLError, ConnectionResetError) as e:
                LOGGER.info(e)
                LOGGER.info("Download retry:"+str(try_number))
                time.sleep(.5)
            else:
                return filepath

    def to_file(self, description, filepath):
        metadata_dict = {"description": description,
            "language": "en",
            "license": licenses.CC_BY,
            "copyright_holder": "National Endowment for the Humanities",
            "author": "",
            "source_id": self.resource_url}
        if self.process_file(download=DOWNLOAD_VIDEOS):
            return metadata_dict


class VimeoResource(ResourceType):
    def __init__(self, resource_url, type_name="Vimeo"):
        super(VimeoResource, self).__init__(type_name=type_name)
        self.resource_url = resource_url
        self.file_format = file_formats.MP4

    def process_file(self, download=False):
        ydl_options = {
            #'outtmpl': '%(title)s-%(id)s.%(ext)s',
            #'format': 'bestaudio/best',
            'writethumbnail': False,
            'no_warnings': True,
            'continuedl': False,
            'restrictfilenames':True,
            'quiet': False,
        }

        with youtube_dl.YoutubeDL(ydl_options) as ydl:
            try:
                ydl.add_default_info_extractors()
                info = ydl.extract_info(self.resource_url, download=False)
                if download is True:
                    filepath = self.video_download(ydl_options)
                else:
                    filepath = None

                if filepath is not None:
                    self.add_resources_files(filepath, {}, local=True)
                    return True
            except(youtube_dl.utils.DownloadError, youtube_dl.utils.ContentTooShortError,
                    youtube_dl.utils.ExtractorError) as e:
                LOGGER.info('error_occured ' + str(e))

    def video_download(self, ydl_options):
        for try_number in range(10):
            try:
                filename = download_from_web(self.resource_url, ydl_options,
                    ext=".{}".format(self.file_format))
            except (URLError, ConnectionResetError) as e:
                LOGGER.info(e)
                LOGGER.info("Download retry:"+str(try_number))
                time.sleep(.5)
            except FileNotFoundError as e:
                LOGGER.info(str(e))
                return None
            else:
                filepath = config.get_storage_path(filename)
                return filepath

    def to_file(self, description, filepath):
        metadata_dict = {"description": description,
            "language": "en",
            "license": licenses.CC_BY,
            "copyright_holder": "National Endowment for the Humanities",
            "author": "",
            "source_id": self.resource_url}
        if self.process_file(download=DOWNLOAD_VIDEOS):
            return metadata_dict


class SoundCloudResource(VimeoResource):
    def __init__(self, resource_url, type_name="SoundCloud"):
        super(SoundCloudResource, self).__init__(resource_url, type_name=type_name)
        self.file_format = file_formats.MP3


def download_css_js():
    css = os.path.join(os.path.dirname(os.path.realpath(__file__)), "chefdata/styles.css")
    js = os.path.join(os.path.dirname(os.path.realpath(__file__)), "chefdata/scripts.js")
    if not if_file_exists(css) or not if_file_exists(js):
        LOGGER.info("Downloading styles")
        r = requests.get("https://raw.githubusercontent.com/learningequality/html-app-starter/master/css/styles.css")
        with open("chefdata/styles.css", "wb") as f:
            f.write(r.content)

        r = requests.get("https://raw.githubusercontent.com/learningequality/html-app-starter/master/js/scripts.js")
        with open("chefdata/scripts.js", "wb") as f:
            f.write(r.content)


# CLI: This code will run when the sous chef is called from the command line
################################################################################
if __name__ == '__main__':
    download_css_js()
    # Open a writer to generate files
    with data_writer.DataWriter(write_to_path=WRITE_TO_PATH) as writer:

        # Write channel details to spreadsheet
        thumbnail = writer.add_file(str(PATH), "Channel Thumbnail", CHANNEL_THUMBNAIL, write_data=False)
        writer.add_channel(CHANNEL_NAME, CHANNEL_SOURCE_ID, CHANNEL_DOMAIN, CHANNEL_LANGUAGE, description=CHANNEL_DESCRIPTION, thumbnail=thumbnail)

        # Scrape source content
        scrape_source(writer)

        sys.stdout.write("\n\nDONE: Zip created at {}\n".format(writer.write_to_path))
