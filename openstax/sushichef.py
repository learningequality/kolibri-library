#!/usr/bin/env python
import copy
import os
import sys;
sys.path.append(os.getcwd()) # Handle relative imports
from ricecooker.utils import downloader, html_writer
from ricecooker.chefs import SushiChef
from ricecooker.classes import nodes, files
from ricecooker.config import LOGGER                        # Use logger to print messages
from ricecooker.exceptions import raise_for_invalid_channel

""" Additional imports """
###########################################################
import logging
import json
from le_utils.constants import licenses, file_formats, roles
from bs4 import BeautifulSoup

import cssutils
from utils.pdf import PDFParser
from svglib.svglib import svg2rlg
from reportlab.graphics import renderPM



""" Run Constants"""
###########################################################

CHANNEL_NAME = "Open Stax"                              # Name of channel
CHANNEL_SOURCE_ID = "open-stax"                         # Channel's unique id
CHANNEL_DOMAIN = "openstax.org"                         # Who is providing the content
CHANNEL_LANGUAGE = "en"                                 # Language of channel
CHANNEL_DESCRIPTION = None                              # Description of the channel (optional)
CHANNEL_THUMBNAIL = "https://pbs.twimg.com/profile_images/461533721493897216/Q-kxGJ-b_400x400.png" # Local path or url to image file (optional)

""" Additional Constants """
###########################################################

BASE_URL = "https://openstax.org/api"
DOWNLOAD_DIRECTORY = os.path.sep.join([os.path.dirname(os.path.realpath(__file__)), "downloads"])
THUMBNAILS_DIRECTORY = os.path.sep.join([os.path.dirname(os.path.realpath(__file__)), "downloads", "thumbnails"])

# Create download directory if it doesn't already exist
if not os.path.exists(DOWNLOAD_DIRECTORY):
    os.makedirs(DOWNLOAD_DIRECTORY)

# Create thumbnails directory if it doesn't already exist
if not os.path.exists(THUMBNAILS_DIRECTORY):
    os.makedirs(THUMBNAILS_DIRECTORY)

# Map for Open Stax licenses to le_utils license constants
LICENSE_MAPPING = {
    "Creative Commons Attribution License": licenses.CC_BY,
    "Creative Commons Attribution-NonCommercial-ShareAlike License": licenses.CC_BY_NC_SA,
}
COPYRIGHT_HOLDER = "Rice University"


""" The chef class that takes care of uploading channel to the content curation server. """
class MyChef(SushiChef):

    channel_info = {                                  # Channel Metadata
        'CHANNEL_SOURCE_DOMAIN': CHANNEL_DOMAIN,      # Who is providing the content
        'CHANNEL_SOURCE_ID': CHANNEL_SOURCE_ID,       # Channel's unique id
        'CHANNEL_TITLE': CHANNEL_NAME,                # Name of channel
        'CHANNEL_LANGUAGE': CHANNEL_LANGUAGE,         # Language of channel
        'CHANNEL_THUMBNAIL': CHANNEL_THUMBNAIL,       # Local path or url to image file (optional)
        'CHANNEL_DESCRIPTION': CHANNEL_DESCRIPTION,   # Description of the channel (optional)
    }

    """ Main scraping method """
    ###########################################################

    def construct_channel(self, *args, **kwargs):
        """ construct_channel: Creates ChannelNode and build topic tree

            OpenStax is organized with the following hierarchy:
                Subject (Topic)
                |   Book (Topic)
                |   |   Main High Resolution PDF (DocumentNode)
                |   |   Main Low Resolution PDF (DocumentNode)
                |   |   Instructor Resources (Topic)
                |   |   |   Resource PDF (DocumentNode)
                |   |   Student Resources (Topic)
                |   |   |   Resource PDF (DocumentNode)

            Returns: ChannelNode
        """
        LOGGER.info("Constructing channel from {}...".format(BASE_URL))

        channel = self.get_channel(*args, **kwargs)             # Creates ChannelNode from data in self.channel_info
        contents = read_source()                                # Get json data from page

        for book in contents.get('books'):
            subject = book.get('subject')

            # Get subject, add if not available
            subject_node = next((child for child in channel.children if child.source_id == subject), None)
            if not subject_node:
                subject_node = nodes.TopicNode(source_id=subject, title=subject)
                channel.add_child(subject_node)

            content = read_source(endpoint=book.get('slug'))     # Read detailed page for content

            if not content:                                      # Skip to next item if nothing is found
                continue

            # Format licensing metadata for content
            auth_info = {
                "license": LICENSE_MAPPING[content.get('license_name')],
                "license_description": content.get('license_text'),
                "copyright_holder": COPYRIGHT_HOLDER,
            }

            # Format content metadata for content
            authors = ", ".join([a['value']['name'] for a in content['authors'][:5]])
            authors = authors + " et. al." if len(content['authors']) > 5 else authors
            details = {
                "description": parse_description(content.get('description')),
                "thumbnail": get_thumbnail(content.get('cover_url')),
                "author": authors,
            }

            # Add book topic
            book_node = nodes.TopicNode(
                source_id=str(content.get('cnx_id')),
                title=content.get('title'),
                description=details.get('description'),
                thumbnail=details.get('thumbnail'),
            )
            subject_node.add_child(book_node)

            # Create high resolution document
            LOGGER.info("   Writing {} documents...".format(book.get('title')))
            add_file_node(book_node, content.get("low_resolution_pdf_url") or content.get("high_resolution_pdf_url"), \
                        content['title'], split=True, contents=content['table_of_contents']['contents'], **auth_info, **details)

            # Create student handbook document
            if content.get("student_handbook_url"):
                add_file_node(book_node, content["student_handbook_url"], "Student Handbook", source_id="student-handbook", **auth_info, **details)

            # Parse resource materials
            LOGGER.info("   Writing {} resources...".format(book.get('title')))
            parse_resources("Instructor Resources", content.get('book_faculty_resources'), book_node, role=roles.COACH, **auth_info)
            parse_resources("Student Resources", content.get('book_student_resources'), book_node, **auth_info)

        raise_for_invalid_channel(channel)                           # Check for errors in channel construction
        return channel


""" Helper Methods """
###########################################################

def read_source(endpoint="books"):
    """ Reads page source using downloader class to get json data """
    page_contents = downloader.read("{baseurl}/{endpoint}".format(baseurl=BASE_URL, endpoint=endpoint))
    return json.loads(page_contents) # Open Stax url returns json object



def get_thumbnail(url):
    filename, _ext = os.path.splitext(os.path.basename(url))
    img_path = os.path.sep.join([THUMBNAILS_DIRECTORY, "{}.png".format(filename)])
    svg_path = os.path.sep.join([THUMBNAILS_DIRECTORY, "{}.svg".format(filename)])

    # This thumbnail gets converted with an error, so download it separately for now
    if "US_history" in filename:
        return files.ThumbnailFile(path="US_history.png")

    # Copy pngs to local storage
    if url.endswith("png"):
        with open(img_path, 'wb') as pngobj:
            pngobj.write(downloader.read(url))

    elif url.endswith("svg"):
        with open(svg_path, 'wb') as svgobj:
            # renderPM doesn't read <style> tags, so add style to individual elements
            svg_contents = BeautifulSoup(downloader.read(url), 'html.parser')
            svg_contents = BeautifulSoup(svg_contents.find('svg').prettify(), 'html.parser')
            if svg_contents.find('style'):
                sheet = cssutils.parseString(svg_contents.find('style').string)
                for rule in sheet:
                    rectangles = svg_contents.find_all('rect', {'class': rule.selectorText.lstrip('.')})
                    paths = svg_contents.find_all('path', {'class': rule.selectorText.lstrip('.')})
                    polygons = svg_contents.find_all('polygon', {'class': rule.selectorText.lstrip('.')})
                    for el in rectangles + paths + polygons:
                        el['style'] = ""
                        for prop in rule.style:
                            el['style'] += "{}:{};".format(prop.name, prop.value)

            # Beautifulsoup autocorrects some words to be all lowercase, so undo correction
            autocorrected_fields = ["baseProfile", "viewBox"]
            svg = svg_contents.find('svg')
            for field in autocorrected_fields:
                if svg.get(field.lower()):
                    svg[field] = svg[field.lower()]
                    del svg[field.lower()]


            svgobj.write(svg_contents.renderContents())
        drawing = svg2rlg(svg_path)
        renderPM.drawToFile(drawing, img_path)

    else:
        import pdb; pdb.set_trace()

    return files.ThumbnailFile(path=img_path)


def parse_description(description):
    """ Removes html tags from description """
    return BeautifulSoup(description or "", "html5lib").text


def parse_resources(resource_name, resource_data, book_node, **auth_info):

    """ Creates resource topics """
    resource_data = resource_data or []
    resource_str = "{}-{}".format(book_node.source_id, resource_name.replace(' ', '-').lower())

    # Create resource topic
    resource_node = nodes.TopicNode(source_id=resource_str, title=resource_name)
    book_node.add_child(resource_node)

    # Add resource documents
    for resource in resource_data:
        if resource.get('link_document_url') and resource['link_document_url'].endswith(".pdf"):
            description = parse_description(resource.get('resource_description'))
            add_file_node(resource_node, resource.get("link_document_url"), resource.get('resource_heading'), description=description, **auth_info)

JSONDATA = {}
with open("pages.json", "rb") as jsonfile:
    JSONDATA = json.load(jsonfile)

def add_file_node(target_node, url, title, split=False, contents=None, source_id=None, **details):
    """ Creates file nodes at target topic node """
    if split:
        book_node = nodes.TopicNode(
            source_id=source_id or target_node.source_id + "-main",
            title=title,
            description=details.get('description'),
            thumbnail=details.get('thumbnail'),
        )
        target_node.add_child(book_node)
        chapters = []
        chapter_details = copy.deepcopy(details)
        del chapter_details['description']
        with PDFParser(url, directory=DOWNLOAD_DIRECTORY) as parser:
            chapters = parser.split_chapters(jsondata=JSONDATA.get(book_node.source_id))
            for index, chapter in enumerate(chapters):
                source_id = contents[index]['id'] if index < len(contents) else "{}-{}".format(book_node.source_id, index)
                create_document_node(chapter['path'], chapter['title'], book_node, source_id, **chapter_details)
    else:
        create_document_node(url, title, target_node, source_id or target_node.source_id, **details)

def create_document_node(path, title, target_node, source_id, **details):
    document_file = files.DocumentFile(path)
    document_id = title.replace(" ", "-").lower()
    target_node.add_child(nodes.DocumentNode(
        source_id="{}-{}".format(source_id, document_id),
        title=title,
        files=[document_file],
        **details
    ))

""" This code will run when the sushi chef is called from the command line. """
if __name__ == '__main__':

    chef = MyChef()
    chef.main()