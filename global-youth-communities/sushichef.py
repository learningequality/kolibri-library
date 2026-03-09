#!/usr/bin/env python
import os
from ricecooker.chefs import SushiChef
from ricecooker.classes import nodes, files
from ricecooker.config import LOGGER              # Use LOGGER to print messages
from ricecooker.exceptions import raise_for_invalid_channel
from le_utils.constants import licenses

""" Additional imports """
###########################################################

# from bs4 import BeautifulSoup
import json
from PyPDF2 import PdfFileWriter, PdfFileReader
from utils import downloader
import io

# Run constants
################################################################################
CHANNEL_NAME = "Global Youth Communities"
CHANNEL_SOURCE_ID = "sushi-chef-global-youth-communities-en"
CHANNEL_DOMAIN = "globalcommunities.org/yslc"
CHANNEL_LANGUAGE = "en"
CHANNEL_DESCRIPTION = "This toolkit contains four guiding manuals that were\
                       developed based on the rich and diverse experiences of \
                       the first 13 Youth Local Councils established."
CHANNEL_THUMBNAIL = "thumbnail.jpeg"

# Additional constants
################################################################################

BASE_URL = "https://www.globalcommunities.org/yslc"
JSON_FILE = "page_structure.json"
CHANNEL_LICENSE = licenses.PUBLIC_DOMAIN
DOWNLOAD_DIRECTORY = os.path.sep.join([os.path.dirname(os.path.realpath(__file__)), "downloads"])


# Create download directory if it doesn't already exist
if not os.path.exists(DOWNLOAD_DIRECTORY):
    os.makedirs(DOWNLOAD_DIRECTORY)


# The chef subclass
################################################################################
class MyChef(SushiChef):

    channel_info = {                                   # Channel Metadata
        'CHANNEL_SOURCE_DOMAIN': CHANNEL_DOMAIN,       # Who is providing the content
        'CHANNEL_SOURCE_ID': CHANNEL_SOURCE_ID,        # Channel's unique id
        'CHANNEL_TITLE': CHANNEL_NAME,                 # Name of channel
        'CHANNEL_LANGUAGE': CHANNEL_LANGUAGE,          # Language of channel
        'CHANNEL_THUMBNAIL': CHANNEL_THUMBNAIL,        # Local path or url to image file (optional)
        'CHANNEL_DESCRIPTION': CHANNEL_DESCRIPTION,    # Description of the channel (optional)
    }

    def construct_channel(self, *args, **kwargs):
        """
        Creates ChannelNode and build topic tree

        Global Youth Communities is organized with the following hierarchy:
        A Practical Guide To Formation & Activation of Youth Shadow Local Councils (Topic)
        |--- Introduction (PDF - DocumentNode)
        |--- Youth Shadow Local Councils: An Overview (PDF - DocumentNode)
        Unified Bylaws for the Youth Shadow Local Councils in Palestine
        |--- Introduction (PDF - DocumentNode)
        |--- General Provisions (PDF - DocumentNode)
        ...
        """
        LOGGER.info("Constructing channel from {}...".format(BASE_URL))

        channel = self.get_channel(*args, **kwargs)  # Create ChannelNode from data in self.channel_info
        topics = read_source(JSON_FILE)
        for topic in topics:
            book_title = topic['book_title']
            source_id = book_title.replace(" ", "_")
            url = topic['path_or_url']
            topic_node = nodes.TopicNode(source_id=source_id, title=book_title)
            channel.add_child(topic_node)
            topic_pdf = download_pdf(url)

            for chapter in topic['chapters']:
                title = chapter['title']
                LOGGER.info("   Writing {}-{}.pdf...".format(book_title, title))
                pdf = split_pdf(chapter=chapter, pdf=topic_pdf)
                pdf_path = "{}/{}-{}.pdf".format(DOWNLOAD_DIRECTORY, book_title, title)
                pdf_file = files.DocumentFile(pdf_path)
                write_pdf(pdf_path, pdf)
                pdf_node = nodes.DocumentNode(
                    source_id="{} {}".format(book_title, title),
                    title=title,
                    files=[pdf_file],
                    license=CHANNEL_LICENSE
                )
                topic_node.add_child(pdf_node)

        raise_for_invalid_channel(channel)  # Check for errors in channel construction
        return channel

def download_pdf(url):
    try:
        page_contents = downloader.read("{url}".format(url=url))
    except Exception as e:
        LOGGER.error("   Error on downloading pdf from {url} : {e}".format(url=url, e=e))
    pdf_content = io.BytesIO(page_contents)
    reader = PdfFileReader(pdf_content)
    return reader

def read_source(json_file):
    with open(json_file) as json_data:
        return json.load(json_data)

def split_pdf(chapter, pdf):
    writer = PdfFileWriter()
    pdf_size = pdf.getNumPages()
    title = chapter['title']
    page_start = chapter['page_start']
    page_end = chapter['page_end']

    if pdf_size < page_start-1 or pdf_size < page_end:
        LOGGER.error("   Error with invalid page information on {} with page {} and page {}.".format(title, page_start, page_end))
    else:
        for page in range(page_start-1, page_end):
            writer.addPage(pdf.getPage(page))
        return writer

def write_pdf(pdf_path, pdf):
    with open(pdf_path, 'wb') as outfile:
        pdf.write(outfile)

# CLI
################################################################################
if __name__ == '__main__':
    # This code runs when sushichef.py is called from the command line
    chef = MyChef()
    chef.main()
