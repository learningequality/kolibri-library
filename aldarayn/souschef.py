#!/usr/bin/env python
import os
import sys
sys.path.append(os.getcwd()) # Handle relative imports
import requests
import json
import hashlib
from le_utils.constants import licenses
from ricecooker.classes.nodes import TopicNode #DocumentNode, VideoNode, AudioNode
# from ricecooker.classes.files import HTMLZipFile, VideoFile, SubtitleFile, DownloadFile
from ricecooker.chefs import SushiChef
import detail
import arabic
import csvstructure
import video
from collections import namedtuple
from csvstructure import L1_KEY, L2_KEY, L3_KEY, L4_KEY, WEBSITE_URL_KEY, TITLE_KEY
Row = namedtuple("Row", csvstructure.PYTHON_FIELDNAMES)

def sha1(x):
    return hashlib.sha1(x.encode('utf-8')).hexdigest()

def dragon_construct_channel(self, **kwargs):
    channel = self.get_channel(**kwargs)
    cats = {None: channel}

    for i, raw_row in enumerate(list(self.channel_index)):
        print ("**** ROW {} OF {}".format(i, len(list(self.channel_index))))
        row = raw_row # on vader, row is unordered...
        # create channel structure for this row
        #row = Row(*raw_row.values())
        #print (row)
        #exit()
        if row[L1_KEY] == csvstructure.L1_KEY: continue
        topic_tree = [row[L1_KEY], row[L2_KEY], row[L3_KEY], row[L4_KEY], row[TITLE_KEY]]
        topic_tree = tuple(x for x in topic_tree if x)  # remove Nones
        for i in range(1,6):
            partial_tree = topic_tree[:i]
            parent = partial_tree[:-1] or None
            leaf = partial_tree[-1]
            if partial_tree not in cats:
                cats[partial_tree] = TopicNode(source_id=sha1(repr(partial_tree)),
                                               title=leaf,
                                               description="")
                cats[parent].add_child(cats[partial_tree])
        topic_node = cats[topic_tree]

        # download videos
        video_list = detail.handle_page(row[WEBSITE_URL_KEY])
        for video_url in video_list:
            video_node = video.acquire_video_node(video_url,
                                                  license="CC BY-NC",
                                                  copyright_holder="Aldarayn Foundation",
                                                  description = None
                                                  )
            source_ids = [x.source_id for x in topic_node.children]
            if video_node.source_id in source_ids:
                continue # skip
            topic_node.add_child(video_node)
            topic_node.validate()
        print (video_list)

    assert channel.validate()
    return channel

class AdultChef(SushiChef):
    channel_info = {
        'CHANNEL_SOURCE_DOMAIN': 'aldarayn.com', # who is providing the content (e.g. learningequality.org)
        'CHANNEL_SOURCE_ID': 'aldarayn_adult',         # channel's unique id
        'CHANNEL_TITLE': arabic.TITLE_ADULT,
        'CHANNEL_LANGUAGE': 'ar',                          # Use language codes from le_utils
        # 'CHANNEL_THUMBNAIL': 'https://im.openupresources.org/assets/im-logo.svg', # (optional) local path or url to image file
        'CHANNEL_DESCRIPTION': arabic.CHANNEL_DESC[:400],  # (optional) description of the channel (optional)
    }

    channel_index = csvstructure.adult_structure()
    construct_channel = dragon_construct_channel


class K12Chef(SushiChef):
    channel_info = {
        'CHANNEL_SOURCE_DOMAIN': 'aldarayn.com', # who is providing the content (e.g. learningequality.org)
        'CHANNEL_SOURCE_ID': 'aldarayn_k12',         # channel's unique id
        'CHANNEL_TITLE': arabic.TITLE_K12,
        'CHANNEL_LANGUAGE': 'ar',                          # Use language codes from le_utils
        # 'CHANNEL_THUMBNAIL': 'https://im.openupresources.org/assets/im-logo.svg', # (optional) local path or url to image file
        'CHANNEL_DESCRIPTION': arabic.CHANNEL_DESC[:400],  # (optional) description of the channel (optional)
    }

    channel_index = csvstructure.k12_structure()
    construct_channel = dragon_construct_channel

def make_channel():
    args = {'token': os.environ['KOLIBRI_STUDIO_TOKEN'], 'reset': True, 'verbose': True}
    if "adult" in sys.argv:
        adult=True
    if "child" in sys.argv:
        child=True
    options = {}
    if "adult":
        adult_chef = AdultChef()
        adult_chef.run(args, options)
    if "child":
        k12_chef = K12Chef()
        k12_chef.run(args, options)

make_channel()
