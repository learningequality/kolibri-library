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
from utils import dir_exists, get_name_from_url, clone_repo, build_path, modify_nodes
from utils import file_exists, get_video_resolution_format, remove_links
from utils import get_name_from_url_no_ext, get_node_from_channel, get_level_map
from utils import remove_iframes, get_confirm_token, save_response_content
import youtube_dl
from json2node import GradeJsonTree
from extended_node import SubjectNode

DATA_DIR = "chefdata"
COPYRIGHT_HOLDER = "University College of Science and Technology"
LICENSE = get_license(licenses.CC_BY, 
        copyright_holder=COPYRIGHT_HOLDER).as_dict()
AUTHOR = "University College of Science and Technology"

LOGGER = logging.getLogger()
__logging_handler = logging.StreamHandler()
LOGGER.addHandler(__logging_handler)
LOGGER.setLevel(logging.INFO)

DOWNLOAD_VIDEOS = True
LOAD_VIDEO_LIST = False

sess = requests.Session()

# Run constants
################################################################################
CHANNEL_NAME = "University College of Science and Technology's E-learning Unit (العربيّة)" # Name of channel
CHANNEL_SOURCE_ID = "ucst-elearning"    # Channel's unique id
CHANNEL_DOMAIN = "https://www.youtube.com/user/CoursesTube/" # Who is providing the content
CHANNEL_LANGUAGE = "ar"      # Language of channel
CHANNEL_DESCRIPTION = "تقدم قناة مركز التعليم الإلكتروني في الكلية الجامعية للعلوم والتكنولوجيا مجموعة من الدروس الفعالة والمفيدة لطلاب المرحلة الجامعية في عديد من التخصصات مثل العلوم الطبية والهندسة والبرمجيات وعلوم الحاسوب. كما أنها تحوي مجموعة من الدروس المقدمة لطلبة المرحلة الثانوية في البرمجة."                                  # Description of the channel (optional)
CHANNEL_THUMBNAIL = "https://yt3.ggpht.com/a-/AAuE7mAONlA6e6c5gpmCuxIUvfk3-IegnkU8xXb35w=s288-mo-c-c0xffffffff-rj-k-no"                                    # Local path or url to image file (optional)




def alias_fn(node, alias_dict):
    rename = alias_dict.get(node["title"], None)
    if rename is not None:
        node["title"] = rename


# The chef subclass
################################################################################
class UCSTChef(JsonTreeChef):
    TREES_DATA_DIR = os.path.join(DATA_DIR, 'trees')

    def __init__(self):
        build_path([UCSTChef.TREES_DATA_DIR])
        super(UCSTChef, self).__init__()

    def pre_run(self, args, options):
        rename_nodes = bool(int(options.get('--rename_nodes', "1")))
        channel_tree = self.scrape(args, options)
        self.write_tree_to_json(channel_tree)
        if file_exists("alias.json") and rename_nodes is True:
            with open("alias.json", "r") as f:
                alias_dict = json.load(f)
            with open(os.path.join(UCSTChef.TREES_DATA_DIR, "ricecooker_json_tree.json"), "r") as f:
                channel_tree = json.load(f)
            modify_nodes(channel_tree, alias_fn, alias_dict)
            self.write_tree_to_json(channel_tree)

    def scrape(self, args, options):
        download_video = options.get('--download-video', "1")
        load_video_list = options.get('--load-video-list', "0")

        if int(download_video) == 0:
            global DOWNLOAD_VIDEOS
            DOWNLOAD_VIDEOS = False

        if int(load_video_list) == 1:
            global LOAD_VIDEO_LIST
            LOAD_VIDEO_LIST = True

        global CHANNEL_SOURCE_ID
        self.RICECOOKER_JSON_TREE = 'ricecooker_json_tree.json'
        channel_tree = dict(
                source_domain=CHANNEL_DOMAIN,
                source_id=CHANNEL_SOURCE_ID,
                title=CHANNEL_NAME,
                description=CHANNEL_DESCRIPTION[:400], #400 UPPER LIMIT characters allowed 
                thumbnail=CHANNEL_THUMBNAIL,
                author=AUTHOR,
                language=CHANNEL_LANGUAGE,
                children=[],
                license=LICENSE,
            )

        grades = GradeJsonTree(subject_node=SubjectNode)
        grades.load("resources.json", auto_parse=True, author=AUTHOR, 
            license=LICENSE, save_url_to=build_path([DATA_DIR, CHANNEL_SOURCE_ID]),
            load_video_list=load_video_list)

        base_path = [DATA_DIR]
        base_path = build_path(base_path)

        for grade in grades:
            for subject in grade.subjects:
                for lesson in subject.lessons:
                    video = lesson.download(download=DOWNLOAD_VIDEOS, base_path=base_path)
                    lesson.add_node(video)
                    subject.add_node(lesson)
                grade.add_node(subject)
            channel_tree["children"].append(grade.to_dict())
        return channel_tree

    def write_tree_to_json(self, channel_tree):
        scrape_stage = os.path.join(UCSTChef.TREES_DATA_DIR,
                                self.RICECOOKER_JSON_TREE)
        write_tree_to_json_tree(scrape_stage, channel_tree)


# CLI
################################################################################
if __name__ == '__main__':
    chef = UCSTChef()
    chef.main()
