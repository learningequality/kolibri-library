#!/usr/bin/env python
import os
import sys
from ricecooker.utils import downloader, html_writer
from ricecooker.chefs import SushiChef
from ricecooker.classes import nodes, files, questions, licenses
from ricecooker.config import LOGGER              # Use LOGGER to print messages
from ricecooker.exceptions import raise_for_invalid_channel
from le_utils.constants import exercises, content_kinds, file_formats, format_presets, languages

from config import DOWNLOAD_DIRECTORY, FOLDER
from pdf_splitter import PDFParser

# Run constants
################################################################################
CHANNEL_NAME = "CREE"              # Name of channel
CHANNEL_SOURCE_ID = "sushi-chef-cree-es"    # Channel's unique id
CHANNEL_DOMAIN = "Local Drive - Honduras"          # Who is providing the content
CHANNEL_LANGUAGE = "es"      # Language of channel
CHANNEL_DESCRIPTION = None                                  # Description of the channel (optional)
CHANNEL_THUMBNAIL = None                                    # Local path or url to image file (optional)

# Additional constants
################################################################################
COPYRIGHT_HOLDER = 'Este contenido ha sido publicado por el Licenciado Edelberto Andino para ser utilizado con fines educativos únicamente, no debe ser utilizado con fines lucrativos de ninguna índole.'
LICENSE = "CC BY-NC-SA"

# The chef subclass
################################################################################
class MyChef(SushiChef):
    """
    This class uploads the CREE channel to Kolibri Studio.
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
    # Your chef subclass can override/extend the following method:
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

        scrape_directory(channel, FOLDER)

        raise_for_invalid_channel(channel)  # Check for errors in channel construction

        return channel

def scrape_directory(topic, directory, indent=1):
    for subdirectory, folders, myfiles in os.walk(directory):

        # Go through all of the folders under directory
        for folder in folders:
            print('{}{}'.format('    ' * indent, folder))
            subtopic = nodes.TopicNode(source_id=folder, title=folder)
            topic.add_child(subtopic)

            # Go through folders under directory
            scrape_directory(subtopic, os.sep.join([subdirectory,folder]),indent=indent+1)
        for file in myfiles:
            name,ext=os.path.splitext(file)
            if ext=='.mp4':
                video=nodes.VideoNode(source_id=subdirectory+file,title=name, license=LICENSE, copyright_holder=COPYRIGHT_HOLDER)
                videofile=files.VideoFile(os.sep.join([subdirectory,file]))
                video.add_file(videofile)
                topic.add_child(video)
            elif ext == '.pdf':
                with PDFParser(os.path.sep.join([subdirectory, file])) as parser:
                    chapters = parser.get_data_file()
                    generate_pdf_nodes(chapters, topic, source=os.path.basename(file))
        break;


def generate_pdf_nodes(data, topic, source=""):
    """
        Generates nodes related to pdfs
        Args:
            - data (dict) data on pdf details (split pdfs, file paths, exercises, etc.)
            - topic (TopicNode) node to add sub nodes to
            - source (str) unique string associated with this pdf
        Returns None
    """

    # Iterate through chapter data
    for chapter in data:
        # Create topics if we're dealing with a section
        if chapter.get('header'):
            source_id = "{}-{}".format(source, chapter['header'])
            subtopic = nodes.TopicNode(title=chapter['header'], source_id=source_id)
            topic.add_child(subtopic)
            generate_pdf_nodes(chapter['chapters'], subtopic, source=source_id)

        # Create a document node and its related exercise nodes if it's a document
        elif chapter.get("chapter"):
            # Create doucment node
            source_id = "{}-{}".format(source, chapter['chapter'])
            topic.add_child(nodes.DocumentNode(
                title=chapter['chapter'],
                source_id=source_id,
                copyright_holder=COPYRIGHT_HOLDER,
                license=LICENSE,
                files=[files.DocumentFile(chapter['path'])]
            ))

            # Create exercise nodes
            for index, exercise in enumerate(chapter.get("exercises") or []):
                exercise_id = "{} Exercise {}".format(source_id, index)
                exercise_node = nodes.ExerciseNode(
                    title=chapter['chapter'],
                    source_id=exercise_id,
                    description=exercise.get('description'),
                    copyright_holder=COPYRIGHT_HOLDER,
                    license=LICENSE,
                )
                topic.add_child(exercise_node)
                create_exercise_questions(exercise_node, exercise.get('questions') or [])

def create_exercise_questions(exercise_node, exercise_data):
    """
        Generates exercise questions based on data
        Args:
            - exercise_node (ExerciseNode) node to add questions to
            - exercise_data (dict) data regarding exercises to create
        Returns None
    """
    # Iterate through exercise question data
    for question_index, question in enumerate(exercise_data):
        # Generate a unique assessment_id for each question
        assessment_id = "{}- {}".format(exercise_node.source_id, question_index)

        # Filter list of answers to be added to the questions
        correct_answers = [answer for answer, correct in question['answers'].items() if correct]
        all_answers = [answer for answer, _ in question['answers'].items()]

        # Create a multiple selection question if specified
        if question["type"] == exercises.MULTIPLE_SELECTION:
            exercise_node.add_question(questions.MultipleSelectQuestion(
                id=assessment_id,
                question=question['question'],
                correct_answers=correct_answers,
                all_answers=all_answers,
            ))

        # Create a single selection question if specified
        elif question["type"] == exercises.SINGLE_SELECTION:
            exercise_node.add_question(questions.SingleSelectQuestion(
                id=assessment_id,
                question=question['question'],
                correct_answer=correct_answers[0],
                all_answers=all_answers
            ))

# CLI
################################################################################
if __name__ == '__main__':
    # This code runs when sushichef.py is called from the command line
    chef = MyChef()
    chef.main()

