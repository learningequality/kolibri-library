#!/usr/bin/env python
import os
import sys
sys.path.append(os.getcwd()) # Handle relative imports
import requests
from le_utils.constants import licenses
from ricecooker.classes.nodes import DocumentNode, VideoNode, TopicNode
from ricecooker.classes.files import HTMLZipFile, VideoFile, SubtitleFile, DownloadFile
from ricecooker.chefs import SushiChef
import logging
import json 
from collections import OrderedDict
from index_lessons import crawl_lesson_index
from urllib.parse import urljoin
from single_lesson import get_lesson
import add_file
from bs4 import BeautifulSoup
import localise
add_file.metadata = {"license": licenses.CC_BY_NC_ND,
                     "copyright_holder": "ArtsEdge"}

raw_lessons = crawl_lesson_index()
lessons = OrderedDict([('Elementary', [x for x in raw_lessons if x.grade == "K-4"]),
                       ('Middle',     [x for x in raw_lessons if x.grade == "5-8"]),
                       ('High',       [x for x in raw_lessons if x.grade == "9-12"])])

LOGGER = logging.getLogger()


class ArtsEdgeChef(SushiChef):
    channel_info = {
        'CHANNEL_SOURCE_DOMAIN': 'artsedge.kennedy-center.org/', # who is providing the content (e.g. learningequality.org)
        'CHANNEL_SOURCE_ID': 'artsedge',         # channel's unique id
        'CHANNEL_TITLE': 'ArtsEdge',
        'CHANNEL_LANGUAGE': 'en',                          # Use language codes from le_utils
        # 'CHANNEL_THUMBNAIL': 'https://im.openupresources.org/assets/im-logo.svg', # (optional) local path or url to image file
        'CHANNEL_DESCRIPTION': 'Connect. Create.',  # (optional) description of the channel (optional)
    }

    def construct_channel(self, **kwargs):
        
        def video_node(video, subtitle, data):
            if subtitle:
                files = [video, subtitle]
            else:
                files = [video]
            return VideoNode(source_id=data['link'],
                             title=data['link'],
                             license=licenses.CC_BY_NC_SA, 
                             copyright_holder="JFK Center for the Performing Arts",
                             files=files,
                             )            
            
        # create channel
        _id = 0
        _subid = 0
        channel = self.get_channel(**kwargs)
        # create a topic and add it to channel
        data = {}
        
        urls = set()
        for item in lessons:
            topic = TopicNode("__"+item, item, "Resources for {} school students".format(item.lower()))
            channel.add_child(topic)
            for lesson in lessons[item]: 
                print (lesson)
                
                if ':' in lesson.title:
                    title = lesson.title.partition(":")[2]
                else:
                    title = lesson.title
                lesson_node = TopicNode("__{}".format(_id), title, "")
                _id = _id + 1
                topic.add_child(lesson_node)
                urls.add(lesson.link)
                sources = set()
                old_text = None
                subnode = None
                
                html_response = requests.get(urljoin("https://artsedge.kennedy-center.org/", lesson.link))
                html_response.raise_for_status()
                soup = BeautifulSoup(html_response.content, "html5lib")
                zipfile_name = localise.make_local(soup, urljoin("https://artsedge.kennedy-center.org/", lesson.link))
                print ("HTML Filesize: ", os.path.getsize(zipfile_name), os.path.abspath(zipfile_name))
                html_node = add_file.create_node(HTMLZipFile, filename=zipfile_name, title=title)
                lesson_node.add_child(html_node)
                
                for text, node in get_lesson(urljoin("https://artsedge.kennedy-center.org/", lesson.link)):
                    print (repr(text), repr(old_text))
                    if not text:
                        text = "Discussion"
                    if text != old_text:
                        subnode = TopicNode("__SUB_{}".format(_subid), text[0]+text[1:].lower(), "")
                        _subid=_subid+1
                        old_text = text
                        lesson_node.add_child(subnode)
                    
                    if node.source_id in sources:  # skip duplicates
                        continue
                    subnode.add_child(node)
                    sources.add(node.source_id)
        return channel
    
def download_videos(jsonfile):
    with open(jsonfile) as f:
        database = [json.loads(line) for line in f.readlines()]
        
    i = 0
    for item in database:
        if item['category'] in ["Video"]: # ("Document", "Audio", "Image", "Video"):
            yield detail.get_individual_page(item)
            i=i+1
            if i == 4:
                print ("Artificial quit")
                break


if __name__ == '__main__':
    """
    Set the environment var `CONTENT_CURATION_TOKEN` (or `KOLIBRI_STUDIO_TOKEN`)
    to your Kolibri Studio token, then call this script using:
        python souschef.py  -v --reset
    """
    mychef = ArtsEdgeChef()
    if 'KOLIBRI_STUDIO_TOKEN' in os.environ:
        os.environ['CONTENT_CURATION_TOKEN'] = os.environ['KOLIBRI_STUDIO_TOKEN']
    mychef.main()
