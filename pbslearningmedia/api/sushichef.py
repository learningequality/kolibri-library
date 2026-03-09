#!/usr/bin/env python
import os
import sys
sys.path.append(os.getcwd()) # Handle relative imports
import requests
from le_utils.constants import licenses
from ricecooker.classes.nodes import DocumentNode, VideoNode, AudioNode, TopicNode, Node
from ricecooker.classes.files import HTMLZipFile, VideoFile, SubtitleFile, DownloadFile
from ricecooker.chefs import SushiChef
from ricecooker.classes.licenses import SpecialPermissionsLicense
import logging
import jsonlines
import tags
import add_file
import download
from copy import deepcopy
import ricecooker
from bs4 import BeautifulSoup
from le_utils.constants.format_presets import PRESETLIST
import standards
import support
import copyright

for preset in PRESETLIST:
    if preset.id in ("high_res_video", "low_res_video"):
        preset.convertible_formats.append("m4v")
        preset.convertible_formats.append("mov")
    if preset.id in ("audio",):
        preset.convertible_formats.append("m4a")


sys.setrecursionlimit(10000)
LOGGER = logging.getLogger()
MAX_NODE_LENGTH = 500

SHARE_LICENCE = SpecialPermissionsLicense(copyright_holder="PBS", description='Verbatim Use ("Stream, Download, and Share") — You are permitted to download the Content, make verbatim copies of the Content, incorporate the Content unmodified into a presentation, and distribute verbatim copies of the Content, but you may not edit or alter the Content or create any derivative works of the Content. You must attribute the Content as indicated in the Download Package.')

MODIFY_LICENCE = SpecialPermissionsLicense(copyright_holder='PBS', description='Download to Re-edit and Distribute ("Stream, Download, Share, and Modify") — You are permitted to download, edit, distribute, and make derivative works of the Content. You must attribute the Content as indicated in the Download Package. Read the full license.')

licence_lookup = {"Stream, Download and Share": SHARE_LICENCE,
                  "Stream, Download, Share, and Modify": MODIFY_LICENCE}

def add_child_replacement(self, node, before=False):
    """ add_child: Adds child node to node
        Args: node to add as child
        Returns: None
    """
    
    assert isinstance(node, Node), "Child node must be a subclass of Node"
    node.parent = self
    for child in self.children:
        if node.source_id == child.source_id:
            print( "source_id {} repeated in {}".format(node.source_id, repr(self)))
            return
    if not before:
        self.children += [node]
    else:
        self.children.insert(0,node)

ricecooker.classes.nodes.add_child = add_child_replacement

def as_text(html):
    soup = BeautifulSoup(html, features="lxml")
    return soup.get_text()

def use_rights(x):
    if 'detail' not in x.keys(): return False
    if 'use_rights' not in x['detail'].keys(): return False
    return "Share" in str(x['detail']['use_rights'])
    
### Import index and filter for only shareable entries
with jsonlines.open("full.uniq.jsonlines") as reader:
    raw_index_data = list(reader)
index_data = list (x for x in raw_index_data if use_rights(x))
    
print ("Imported ", len(raw_index_data), " index entries")
print ("Using", len(index_data), " shareable index entries")

# Create list of leaf-tags.
# leaf_tags = {"audio": ['a', 'b'...], ...}
s_tags = list(tags.tags.keys())
s_tags.append("NOPE:NOPE")
leaf_tags = {}
old_tag = ""
for tag in s_tags:
    if old_tag in tag:
        pass
    else:
        pre, _, post = old_tag.partition(":")
        if pre not in leaf_tags:
            leaf_tags[pre] = []
        leaf_tags[pre].append(post)
    old_tag = tag
assert ("NOPE") not in leaf_tags

nodes = {}
def hier(medium, curriculum_tags):
    
    out_tags = []
    all_ancestors = []
    for tag in curriculum_tags:
        all_ancestors.extend(tag['ancestor_ids'])
    retry = {}
    for tag in sorted(curriculum_tags, key =lambda x: x['id']):
        slug = tag['slug']
        _id = tag['id']
        name = tag['name']
        if not tag['ancestor_ids']:
            ancestor = "ROOT"
        else:
            ancestor = tag['ancestor_ids'][-1]
        # attach to tree
        if _id not in nodes[medium]:
            nodes[medium][_id] = TopicNode(source_id=slug, title =name)
            try:
                add_child_replacement(nodes[medium][ancestor], nodes[medium][_id], before=True)
                # nodes[medium][ancestor].add_child(nodes[medium][_id])
            except Exception:
                retry[(medium,ancestor)] = nodes[medium][_id]      
        if _id not in all_ancestors:
            out_tags.append(nodes[medium][_id])
    for k,v in retry.items():
        add_child_replacement(nodes[k[0]][k[1]], v, before=True)
        # nodes[k[0]][k[1]].add_child(v)
    assert out_tags
    return out_tags
  

class PBS_API_Chef(SushiChef):
    # hierarchy = # open reverse.json and parse
    
    channel_info = {
        'CHANNEL_SOURCE_DOMAIN': 'pbslearningmedia.org', # who is providing the content (e.g. learningequality.org)
        'CHANNEL_SOURCE_ID': 'pbslearningmedia_api',         # channel's unique id
        'CHANNEL_TITLE': 'PBS Learning Media',
        'CHANNEL_LANGUAGE': 'en',                          # Use language codes from le_utils
        # TODO add thumbnail
        'CHANNEL_THUMBNAIL': "pbs.png",
        'CHANNEL_DESCRIPTION': 'Bring Your Classroom to Life With PBS',  # (optional) description of the channel (optional)
    }

    def construct_channel(self, **kwargs):
        # code exists for:
        # "More" link
        # Collections
        # Alphabetical
    
        # create channel
        channel = self.get_channel(**kwargs)

        i=0
        for _ in leaf_tags: # original media descriptons like 'Audio' which are wrong.
            #if medium != "Video": continue
            for i, index in enumerate(index_data):

                # completes OK
                #if i<320: continue

                resource_url = index['detail']['objects'][0]['canonical_url']
                print ("#", i, ":", resource_url)
                #for x in index['detail']['objects']:
                #    print (x['canonical_url'], x['role'])
                  
                canonical = index['index']['canonical_url']
                assert canonical is not None

                
                copyright_string = index['detail']['copyright']
                if not copyright.has_copyright(copyright_string):
                    copyright_list = []
                    for a in index['detail']['required_attributions']:
                        if a['role'].lower() == "producer":
                            copyright_list.append(a['name'])
                        if copyright_list:
                            copyright_string = ", ".join(set(copyright_list))
                        else:
                            copyright_string = "PBS Learning Media"

                # TODO - fix
                author_array = []
                for a in index['detail']['required_attributions']:
                    if a['role'] in ['brand', 'contributor']:
                        author_array.append(a['name'])
                author_string = ", ".join(set(author_array))

                provider_array = []
                for a in index['detail']['required_attributions']:
                    if a['role'] in ['funder', 'sponsor', 'partner']:
                        provider_array.append(a['name'])
                provider_string = ", ".join(set(provider_array))
                
                standards_tags = standards.get_standards(index['detail']['canonical_url'])

                try:
                    nodes[canonical], actual_medium = download.download_something(canonical_url=resource_url,
                                                           title=index['index']['title'],
                                                           license=licence_lookup[index['detail']['use_rights']],
                                                           copyright_holder=copyright_string,
                                                           author = author_string,
                                                           # Done later because of ricecooker bug
                                                           # see https://github.com/learningequality/ricecooker/issues/226
                                                           # provider = provider_string,
                                                           # tags=standards_tags,
                                                           description=as_text(index['detail']['description']),
                                                           )

                except download.NotExpected:
                    with open("fail.log", "a") as f:
                        f.write(str(i)+":"+canonical + " isn't anything\n")
                    continue
                except add_file.CantMakeNode:
                    with open("fail.log", "a") as f:
                        f.write(str(i)+":"+canonical + " is a bad thing\n")
                    continue
                except download.Skip:
                    continue
                nodes[canonical].provider = provider_string
                nodes[canonical].tags=standards_tags

                support_nodes = support.get_support_nodes(detail = index['detail'],
                                                          license = licence_lookup[index['detail']['use_rights']],
                                                          copyright_holder = copyright_string,
                                                          author = author_string)
                video_topic_node = TopicNode(source_id="vtn_"+resource_url, title=index['index']['title'])
                add_child_replacement(video_topic_node, nodes[canonical])
                for node in support_nodes:
                    add_child_replacement(video_topic_node, node)

                # TODO - do something with support nodes!
                
                if actual_medium not in nodes:
                    nodes[actual_medium]={}
                    nodes[actual_medium]["ROOT"] = TopicNode(source_id = actual_medium, title = actual_medium)
                    channel.add_child(nodes[actual_medium]["ROOT"])
                
                leafs = hier(actual_medium, index['detail']['curriculum_tags'])

                for leaf in leafs:
                    # print (leaf)
                    # WAS: add_child_replacement(leaf, deepcopy(nodes[canonical]), before=False)
                    add_child_replacement(leaf, deepcopy(video_topic_node), before=False) # TODO: deepercopy
                    # leaf.add_child(deepcopy(nodes[canonical]))

        return channel
 
def make_channel():
    mychef = PBS_API_Chef()
    args = {'token': os.environ['KOLIBRI_STUDIO_TOKEN'], 'reset': True, 'verbose': True}
    options = {}
    mychef.run(args, options)
    #mychef.main()

make_channel()
