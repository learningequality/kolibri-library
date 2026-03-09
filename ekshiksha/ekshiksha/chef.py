#!/usr/bin/env python

import chardet
import copy
import glob
import os
import shutil
import sys
import tempfile

sys.path.append(os.getcwd())  # Handle relative imports
from pressurecooker import web
from ricecooker.utils import zip
from ricecooker.chefs import SushiChef
from ricecooker.classes import nodes, files
from ricecooker.config import LOGGER  # Use logger to print messages
from ricecooker.exceptions import raise_for_invalid_channel

""" Additional imports """
###########################################################
from le_utils.constants import file_formats, format_presets, licenses

from .utils import int_to_roman, js_file_to_json

""" Run Constants"""
###########################################################

CHANNEL_NAME = "ekShiksha"  # Name of channel
CHANNEL_SOURCE_ID = "sushi-chef-ekShiksha"  # Channel's unique id
CHANNEL_DOMAIN = "ekshiksha"  # Who is providing the content
CHANNEL_LANGUAGE = "en"  # Language of channel
CHANNEL_DESCRIPTION = None  # Description of the channel (optional)
CHANNEL_THUMBNAIL = None  # Local path or url to image file (optional)

""" Additional Constants """
###########################################################
ROOT_DIR = os.path.join(os.path.dirname(__file__), '..')
FILES_DIR = os.path.abspath(os.path.join(ROOT_DIR, 'files'))
assert os.path.exists(FILES_DIR)

CONTENT_ROOT_EN = os.path.join(FILES_DIR, 'ekShiksha', 'ekShikshaEnglish')

# IMPORTANT: REMOVE THIS NOTE ONCE LICENSING HAS BEEN FINALIZED!!!! CURRENT LICENSE INFO IS FOR TESTING!!!
# License to be used for content under channel
CHANNEL_LICENSE = licenses.CC_BY_NC


""" The chef class that takes care of uploading channel to the content curation server. """


class EkShikshaChef(SushiChef):
    channel_info = {  # Channel Metadata
        'CHANNEL_SOURCE_DOMAIN': CHANNEL_DOMAIN,  # Who is providing the content
        'CHANNEL_SOURCE_ID': CHANNEL_SOURCE_ID,  # Channel's unique id
        'CHANNEL_TITLE': CHANNEL_NAME,  # Name of channel
        'CHANNEL_LANGUAGE': CHANNEL_LANGUAGE,  # Language of channel
        'CHANNEL_THUMBNAIL': CHANNEL_THUMBNAIL,  # Local path or url to image file (optional)
        'CHANNEL_DESCRIPTION': CHANNEL_DESCRIPTION,  # Description of the channel (optional)
    }
    content_root = CONTENT_ROOT_EN
    assets_path_rel = 'assets'
    assets_dir = os.path.join(content_root, assets_path_rel)
    js_dir = os.path.join(assets_dir, 'js')
    apps_path_rel = 'apps'
    apps_path = os.path.join(content_root, apps_path_rel)
    chapters_path_rel = 'chapters'
    temp_dir = tempfile.mkdtemp()
    cache_dir = os.path.join(ROOT_DIR, 'chefdata', channel_info['CHANNEL_SOURCE_ID'])
    dep_zip_file = None
    """ Main scraping method """

    ###########################################################

    def construct_channel(self, *args, **kwargs):
        """ construct_channel: Creates ChannelNode and build topic tree
        """

        channel = self.get_channel(*args, **kwargs)  # Creates ChannelNode from data in self.channel_info

        if not os.path.exists(self.content_root):
            print("Cannot find content files at {}".format(self.content_root))
            print("Please extract content files to this location and run the chef again.")
            print("This chef does not yet support scraping from the ekShiksha web site.")
            sys.exit(1)

        self.create_dependency_zip()

        contents = self.get_content_metadata()
        info_with_zips = self.get_zips_for_content(contents)

        standards = self.get_contents_by_standard(info_with_zips)
        standard_keys = list(standards.keys())
        standard_keys.sort()

        for standard_num in standard_keys:
            tree = self.get_content_tree(standards[standard_num])

            standard_topic = nodes.TopicNode(source_id='standard' + str(standard_num), title=int_to_roman(standard_num))

            for root_topic in tree:
                topic = self.create_topic_nodes_recursive(root_topic)
            # some root nodes don't have content in the package we were sent, so we skip those
                if topic:
                    standard_topic.add_child(topic)
            channel.add_child(standard_topic)
        return channel

    def __del__(self):
        self.cleanup()
        assert not os.path.exists(self.temp_dir), "Error cleaning temp directory {}.\nIt may safely be deleted.".format(self.temp_dir)

    def cleanup(self):
        """
        Cleans up the temp directory created by the chef on run.
        """
        # Handle the case where cleanup may be called multiple times
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def get_topics(self):
        """
        Read the topics.js file and return it as a dictionary object.
        :return: A dictionary of topics in this content source.
        """

        topics_js_filename = os.path.join(self.js_dir, 'topics.js')
        return js_file_to_json(topics_js_filename)['topics']

    def get_contents(self):
        """
        Read the contents.js file and return it as a dictionary object.
        :return: A dictionary of content items in this content source.
        """
        contents_js_filename = os.path.join(self.js_dir, 'contents.js')
        return js_file_to_json(contents_js_filename)['content']

    def get_contents_by_standard(self, contents):
        """
        Sort the content items by the CBSE standard that they are aligned to.

        :param contents: A list of content items
        :return: A dictionary with each CBSE standard with content having a key, and a content item list being the value.
        """
        standards = {}

        for content in contents:
            # print("content = {}".format(content))
            standard = int(content['content_info']['standard'])
            if not standard in standards:
                standards[standard] = []
            standards[standard].append(content)
        return standards

    def get_file_info_for_content(self, content):
        """
        The information in the contents.js file is not complete and we need to use some heuristics to determine
        the filename and directory of the HTML file to package for that content item.
        :param content: A content item dictionary.
        :return: A dictionary of information about the file and directory, or None if unable to determine.
        """

        html_file = content['htmlFileName']

        info = None
        # Even though the key is htmlFileName, it may return .jsp or .swf content, which we don't support.
        if os.path.splitext(html_file)[1] == '.html':
            if 'resourceDir' in content:
                resource_dir = content['resourceDir']
                app_path_rel = os.path.join(self.apps_path_rel, resource_dir)
                app_path_full = os.path.join(self.content_root, app_path_rel)
                if os.path.exists(app_path_full):
                    info = {}
                    info['content_info'] = content
                    info['standard'] = content['standard']
                    info['dir'] = app_path_rel
                    info['dir_absolute'] = app_path_full
                    info['html_file'] = os.path.basename(html_file)
            elif 'contentId' in content:
                content_id = content['contentId']
                chapter_path_rel = os.path.join(self.chapters_path_rel, str(content_id))
                chapter_path_full = os.path.join(self.content_root, chapter_path_rel)
                if os.path.exists(chapter_path_full):
                    if 'resourceUrl' in content:
                        info = {}
                        info['content_info'] = content
                        info['dir'] = chapter_path_rel
                        info['dir_absolute'] = chapter_path_full
                        info['html_file'] = '{}.html'.format(content['resourceUrl'])
                        if 'imageDir' in content:
                            info['image_dir'] = os.path.join(chapter_path_rel, content['imageDir'])

        if info:
            if 'developerName' in content:
                info['author'] = content['developerName']
            if 'title' in content:
                if 'unicodeText' in content['title']:
                    info['title'] = content['title']['unicodeText']
            if 'organization' in content:
                info['organization'] = content['organization']

        return info

    def create_dependency_zip(self):
        """
        Create a zip of the shared assets that are referenced by the other zip files.
        """
        pie_subdir = "PIE"
        dep_zip_temp_dir = os.path.join(self.temp_dir, 'dep_zip')
        os.makedirs(dep_zip_temp_dir)

        # Copy over the assets directory'
        assets_temp_dir = os.path.join(dep_zip_temp_dir, self.assets_path_rel)
        shutil.copytree(self.assets_dir, assets_temp_dir)

        # Copy over the PIE shared libraries in the apps folder
        pie_dir = os.path.join(self.apps_path, pie_subdir)
        pie_temp_dir = os.path.join(dep_zip_temp_dir, pie_subdir)
        shutil.copytree(pie_dir, pie_temp_dir)
        for afile in os.listdir(pie_temp_dir):
            if 'three.js' in afile.lower() or 'three.min.js' in afile.lower():
                self.patch_three_js(os.path.join(pie_temp_dir, afile))
        # ricecooker requires all zips to have an index.html, even dependency zips right now.
        # FIXME: Have ricecooker check is_primary before alerting about missing index.html.
        index_file = os.path.join(dep_zip_temp_dir, 'index.html')
        f = open(index_file, 'w')
        f.write('')
        f.close()

        self.dep_zip = self.create_zip_from_dir(dep_zip_temp_dir)
        self.dep_zip_file = files.HTMLZipFile(self.dep_zip, preset=format_presets.HTML5_DEPENDENCY_ZIP)

    def update_html(self, content_info, html_file_path):
        """
        Update HTML content for Kolibri, including changing links to reference files within Kolibri.

        :param content_info: File info dictionary from the get_file_info_from_content function
        :param html_file_path: Absolute path to the HTML file to update.

        :return Modified HTML source as a string.
        """

        parser = web.HTMLParser(html_file_path)

        # update links to files in dependency zip
        local_links = parser.get_local_files()
        links_to_replace = {}

        assets_ref = '/assets/'
        pie_ref = '../../PIE/'
        for link in local_links:
            if pie_ref in link:
                content_info['needs_dep_zip'] = True
                dep_zip_pie_ref = '{}/PIE/'.format(os.path.basename(self.dep_zip))
                links_to_replace[pie_ref] = dep_zip_pie_ref

            elif assets_ref in link:
                content_info['needs_dep_zip'] = True
                dep_zip_assets_ref = '/zipcontent/{}/assets/'.format(os.path.basename(self.dep_zip))
                links_to_replace[assets_ref] = dep_zip_assets_ref

            # find and patch any Three.js references in the sources that are not part of the PIE package.
            elif 'three.js' in link.lower() or 'three.min.js' in link.lower():
                # print("Three.js link found: {}".format(link))
                full_path = os.path.join(os.path.dirname(html_file_path), link)
                if os.path.exists(full_path):
                    self.patch_three_js(full_path)

        return parser.replace_links(links_to_replace)

    def patch_three_js(self, three_js_path):
        """
        Patches the Three.js library to fix issues with cross-origin image loading. Please make sure NOT to patch
        the original source files using this function.

        :param three_js_path: Path to the Three.js library to patch.
        """
        add_to_end = """if (window.origin !== window.location.origin) { THREE.TextureLoader.prototype.crossOrigin = 'anonymous'; }"""
        f = open(three_js_path)
        data = f.read()
        f.close()

        data = data + add_to_end
        f = open(three_js_path, 'w')
        f.write(data)
        f.close()

    def get_html5_zip_node_for_content(self, content_info):
        """
        Convert an HTML file and its associated assets into a Kolibri-compatible HTML5 zip file.

        Upon the completion of this function, an 'html5_zip' property will be added to content_info containing
        the path to the HTML5 zip file to include in the Kolibri bundle.

        :param content_info: Metadata dictionary with information about the node to create a zip file for.
        :return:
        """
        if 'dir' in content_info:
            # copytree expects to create the dir it's copying itself, so just create the parent directory.
            temp_path = os.path.join(self.temp_dir, content_info['dir'])

            shutil.copytree(content_info['dir_absolute'], temp_path)
            if content_info['html_file'] != "index.html":
                os.rename(os.path.join(temp_path, content_info['html_file']), os.path.join(temp_path, 'index.html'))

            for html_file in glob.glob(os.path.join(temp_path, '*.html')):
                html_file_path = os.path.join(temp_path, html_file)
                new_html = self.update_html(content_info, html_file_path)
                f = open(html_file_path, 'w')
                f.write(new_html)
                f.close()

            content_info['html5_zip'] = self.create_zip_from_dir(temp_path)

    def create_zip_from_dir(self, dir_to_zip):
        """
        Adds all the files and subfolders from dir_to_zip into a Kolibri-compatible zip file.

        :param dir_to_zip: Directory containing files to zip.
        :return: Path to zip file. Note that this file is stored in the temp dir and will not persist across runs.
        """
        temp_zip = zip.create_predictable_zip(dir_to_zip)
        zip_hash = files.get_hash(temp_zip)
        zip_dir = os.path.join(self.cache_dir, 'zips')
        if not os.path.exists(zip_dir):
            os.makedirs(zip_dir)
        output_zip = os.path.join(zip_dir, '{}.zip'.format(zip_hash))
        os.rename(temp_zip, output_zip)
        return output_zip

    def get_content_metadata(self):
        """
        Iterates through the chef's content items and determines metadata properties needed to properly package
        the content in Kolibri.

        :return: List of item metadata dictionaries.
        """
        content_metadata = []
        for content in self.get_contents():
            file_info = self.get_file_info_for_content(content)
            if file_info:
                content_metadata.append(file_info)

        return content_metadata

    def get_zips_for_content(self, contents):
        """
        Convenience function to generate all the HTML5 zip files of all the content.

        :param contents: A list of dictionaries with information about content items.
        :return:
        """
        for content in contents:
            self.get_html5_zip_node_for_content(content)

        return contents

    def get_content_tree(self, contents_info):
        """
        Create a hierarchical topic tree from the topics and contents data in the JS files.
        :return: A list of nodes in hierarchical order.
        """
        tree = []
        topics = self.get_topics()
        topics_by_id = {}
        for topic in topics:
            topics_by_id[topic['id']] = copy.copy(topic)

        # step 1: Add the content nodes to the topics they are associated with
        for content_info in contents_info:
            anode = content_info['content_info']
            topic_id = int(anode['topic']['id'])
            if topic_id in topics_by_id:
                topic = topics_by_id[topic_id]
                if not 'nodes' in topic:
                    topic['nodes'] = []
                topic['nodes'].append(content_info)
            else:
                print("Topic {} not found".format(topic_id))

        # step 2: go through topics, checking for parents and creating parent-child relationships
        root_topic_ids = []
        for topic_id in topics_by_id:
            topic = topics_by_id[topic_id]
            if 'parent' in topic:
                parent_id = topic['parent']
                if parent_id == '#':
                    root_topic_ids.append(int(topic['id']))
                else:
                    parent = topics_by_id[int(parent_id)]
                    if not 'child_ids' in parent:
                        parent['child_ids'] = []
                    parent['child_ids'].append(topic_id)

        # step 3: convert flat data structures to tree
        def _get_children_recursive(topic):
            if 'child_ids' in topic:
                topic['subtopics'] = []
                for child_id in topic['child_ids']:
                    child = topics_by_id[child_id]
                    _get_children_recursive(child)
                    topic['subtopics'].append(child)

        tree = []
        for root_id in root_topic_ids:
            root = topics_by_id[root_id]
            _get_children_recursive(root)
            if ('nodes' in root and len(root['nodes']) > 0) or ('subtopics' in root and len(root['subtopics']) > 0):
                tree.append(root)
        return tree

    def create_topic_nodes_recursive(self, topic_info):
        """
        Create nodes for all the content items in the tree. Currently supports HTML5 app node and topic node creation.

        :param topic_info: Dictionary with information about the current topic to use for generating nodes.
        :return: A TopicNode of the node topic_info along with all child topics and nodes.
        """
        topic_node = nodes.TopicNode(source_id=str(topic_info['id']), title=topic_info['text'])

        has_content = False
        if 'nodes' in topic_info:
            has_content = True
            topic_nodes = topic_info['nodes']
            for anode in topic_nodes:
                node_files = [files.HTMLZipFile(anode['html5_zip'])]
                if 'needs_dep_zip' in anode and anode['needs_dep_zip']:
                    print("Needs dep zip: {}".format(anode))
                    node_files.append(self.dep_zip_file)
                html_node = nodes.HTML5AppNode(
                    files = node_files,
                    title = anode['title'],
                    source_id=anode['dir'],
                    license=licenses.CC_BY_NC,
                    copyright_holder="ekShiksha"
                )
                if 'description' in anode:
                    html_node.description = anode['description']

                # One possible way to store metadata about each content node on Studio.
                # extra_fields = {'metadata' : {}}
                # metadata = extra_fields['metadata']
                # metadata['grades'] = [{'curriculum': 'CBSE', 'grades': [int(anode['standard'])] }]
                # metadata['subject'] = topic_info['text']
                # TODO: Add the topic tree as 'categories'

                topic_node.add_child(html_node)

        if 'subtopics' in topic_info:
            for subtopic in topic_info['subtopics']:
                child = self.create_topic_nodes_recursive(subtopic)
                if child:
                    has_content = True
                    topic_node.add_child(child)

        # This shouldn't happen, so output a warning if it does.
        if not has_content:
            print("Node {} has no content".format(topic_info))
            return None

        return topic_node

