#!/usr/bin/env python
import json
import os
import sys

from le_utils.constants import licenses as license_constants
from ricecooker.chefs import SushiChef
from ricecooker.classes import nodes, files, questions, licenses
from ricecooker.config import LOGGER              # Use LOGGER to print messages
from ricecooker.exceptions import raise_for_invalid_channel
from ricecooker.utils import downloader, html_writer

# FIXME: Update to use the version in pressurecooker once it gets pushed
import pdf

# Run constants
################################################################################
CHANNEL_NAME = "INTO Intercultural Mentoring"              # Name of channel
CHANNEL_SOURCE_ID = "sushi-chef-intercultural-mentoring-en-2"    # Channel's unique id
CHANNEL_DOMAIN = "interculturalmentoring.eu"          # Who is providing the content
CHANNEL_LANGUAGE = "en"      # Language of channel
CHANNEL_DESCRIPTION = """
This toolkit for teachers and other professional staff provides instrucions, guidelines and both
operaonal and methodological proposals for trainers to upskill secondary school teachers to intervene
through an intercultural mentor when students from abroad, especially new arrivals, have personal or
academic difficules, or drop out of school.
"""
CHANNEL_THUMBNAIL = "into-icon.png"                                    # Local path or url to image file (optional)

# Additional constants
################################################################################
BASE_URL = "http://www.interculturalmentoring.eu/images/Toolkits/"
JSON_FILE = "page_structure.json"
CHANNEL_LICENSE = license_constants.SPECIAL_PERMISSIONS  # TODO: Get confirmation on license.
LICENSE_DESCRIPTION = """
This material falls under the European Commission's copyright policy. Full details
on the terms for distribution, editing and re-use can be found here:
http://ec.europa.eu/ipg/basics/legal/notice_copyright/index_en.htm
"""
DOWNLOAD_DIRECTORY = os.path.sep.join([os.path.dirname(os.path.realpath(__file__)), "downloads"])


# Helper methods
def load_json_from_file(json_file):
    with open(json_file) as json_data:
        return json.load(json_data)


# The chef subclass
################################################################################
class MyChef(SushiChef):
    """
    This class uploads the INTO Intercultural Mentoring channel to Kolibri Studio.
    Your command line script should call the `main` method as the entry point,
    which performs the following steps:
      - Parse command line arguments and options (run `./sushichef.py -h` for details)
      - Call the `SushiChef.run` method which in turn calls `pre_run` (optional)
        and then the ricecooker function `uploadchannel` which in turn calls this
        class' `get_channel` method to get channel info, then `construct_channel`
        to build the contentnode tree.
    For more info, see https://github.com/learningequality/ricecooker/tree/master/docs
    """
    channel_info = {                                   # Channel Metadata
        'CHANNEL_SOURCE_DOMAIN': CHANNEL_DOMAIN,       # Who is providing the content
        'CHANNEL_SOURCE_ID': CHANNEL_SOURCE_ID,        # Channel's unique id
        'CHANNEL_TITLE': CHANNEL_NAME,                 # Name of channel
        'CHANNEL_LANGUAGE': CHANNEL_LANGUAGE,          # Language of channel
        'CHANNEL_THUMBNAIL': CHANNEL_THUMBNAIL,        # Local path or url to image file (optional)
        'CHANNEL_DESCRIPTION': CHANNEL_DESCRIPTION,    # Description of the channel (optional)
    }
    # Your chef subclass can ovverdie/extend the following method:
    # get_channel: to create ChannelNode manually instead of using channel_info
    # pre_run: to perform preliminary tasks, e.g., crawling and scraping website
    # __init__: if need to customize functionality or add command line arguments

    def construct_channel(self, *args, **kwargs):
        """
        Creates ChannelNode and build topic tree
        Args:
          - args: arguments passed in during upload_channel (currently None)
          - kwargs: extra argumens and options not handled by `uploadchannel`.
            For example, add the command line option   lang="fr"  and the string
            "fr" will be passed along to `construct_channel` as kwargs['lang'].
        Returns: ChannelNode
        """
        channel = self.get_channel(*args, **kwargs)  # Create ChannelNode from data in self.channel_info

        topics = load_json_from_file(JSON_FILE)
        for topic in topics:
            book_title = topic['book_title']
            source_id = book_title.replace(" ", "_")
            url = topic['path_or_url']
            topic_node = nodes.TopicNode(source_id=source_id, title=book_title,
                    tags = [
                        "Teacher facing",
                        "Professional development",
                        "Life skills",
                        "Intercultural skills",
                        "Mentorship",
                        "Formal contexts"
                    ])
            channel.add_child(topic_node)

            parser = pdf.PDFParser(url, toc=topic['chapters'])
            parser.open()
            chapters = parser.split_chapters()
            for chapter in chapters:
                title = chapter['title']
                pdf_path = chapter['path']
                pdf_file = files.DocumentFile(pdf_path)
                pdf_node = nodes.DocumentNode(
                    source_id="{} {}".format(book_title, title),
                    title=title,
                    author="INTO",
                    tags = [
                        "Teacher facing",
                        "Professional development",
                        "Life skills",
                        "Intercultural skills",
                        "Mentorship",
                        "Formal contexts"
                    ],
                    files=[pdf_file],
                    license=licenses.get_license(CHANNEL_LICENSE, "INTO", LICENSE_DESCRIPTION),
                    copyright_holder="INTO"
                )
                topic_node.add_child(pdf_node)

        raise_for_invalid_channel(channel)  # Check for errors in channel construction

        return channel



# CLI
################################################################################
if __name__ == '__main__':
    # This code runs when sushichef.py is called from the command line
    chef = MyChef()
    chef.main()
