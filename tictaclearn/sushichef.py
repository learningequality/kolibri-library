#!/usr/bin/env python
import os
from ricecooker.chefs import SushiChef
from ricecooker.classes import nodes, files, licenses
from ricecooker.config import LOGGER, THUMBNAILS  # Use LOGGER to print messages
from le_utils.constants import exercises
from le_utils.constants.languages import getlang_by_name, getlang
from le_utils.constants import licenses as le_licenses
from ricecooker.classes.questions import SingleSelectQuestion
from utils import *

import dropbox
import json
import re

# Run constants
################################################################################
# CHANNEL_ID = "64d440bdac615b549fa160ea341ab743"         # Main channel ID
# CHANNEL_ID = "bc1a1352ba4f4324a2efbe4e0ec808f3"  # Test channel ID
CHANNEL_NAME = "TicTacLearn"  # Name of Kolibri channel
CHANNEL_SOURCE_ID = "tictaclearn2_hi"  # Unique ID for content source
CHANNEL_DOMAIN = "https://tictaclearn.org/"  # Who is providing the content
CHANNEL_LANGUAGE = "hi"  # Language of channel
CHANNEL_DESCRIPTION = """TicTacLearn channel description:
TicTacLearn, a digital public good by Central Square Foundation, is one of India’s largest educational content repositories with 12000+ animated videos for Math and Science. TicTacLearn is available in Hindi, Telugu, Marathi, Odia, Gujarati and English with complete coverage for grades 1-10. All videos are byte-sized (~4-5 mins), mapped to India’s national curriculum (NCERT).
"""  # Description of the channel (optional)
CHANNEL_THUMBNAIL = None  # Local path or url to image file (optional)
CONTENT_ARCHIVE_VERSION = 1

# Additional constants
################################################################################
# VIDEOS_XLS = os.path.abspath("ticataclearn_dropbox.xlsx")
# ASSESSMENT_XLS = os.path.abspath("assessments.xlsx")
CREDENTIALS = os.path.join("credentials", "credentials.json")
VIDEO_FOLDER = os.path.abspath(os.path.join("chefdata", "videos"))
SHEETS_FOLDER = os.path.abspath(os.path.join("chefdata", "sheets"))
FAILED_LINKS_DIR = os.path.join("chefdata", "failed_links")
FAILED_LINKS_JSON = os.path.join(FAILED_LINKS_DIR, "failed_links.json")
FAILED_IMAGES_JSON = os.path.join(FAILED_LINKS_DIR, "failed_image_links.json")
TTL_MAIN_LOGO = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.path.join("TTLFinalLogo.jpg"))
EXCEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          'TicTacLearn - Dropbox Catalogue 2022 (1).xlsx'
                          )

DICT_ASSESSMENT_XLS = {
    'en': {
        'Mathematics': os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            'TTL_math_practice_content',
            'English',
            'Math_G1to10_English_FINAL (External Sharing).xlsx'),
        'Science': os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            'TTL_science_practice_content',
            'English',
            'Science_G6to10_English_FINAL_external.xlsx')
    },
    'hi': {
        'Mathematics': os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            'TTL_math_practice_content',
            'Hindi',
            'Math_G1to10_Hindi_FINAL (External Sharing).xlsx'),
        'Science': os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            'TTL_science_practice_content',
            'Hindi',
            'Science_G6to10_Hindi_FINAL_external.xlsx')
    }
}


# The chef subclass
################################################################################
class TicTacLearnChef(SushiChef):
    """
    This class converts content from the content source into the format required by Kolibri,
    then uploads the {channel_name} channel to Kolibri Studio.
    Your command line script should call the `main` method as the entry point,
    which performs the following steps:
      - Parse command line arguments and options (run `./sushichef.py -h` for details)
      - Call the `SushiChef.run` method which in turn calls `pre_run` (optional)
        and then the ricecooker function `uploadchannel` which in turn calls this
        class' `get_channel` method to get channel info, then `construct_channel`
        to build the contentnode tree.
    For more info, see https://ricecooker.readthedocs.io
    """
    language = getlang(CHANNEL_LANGUAGE)
    channel_info = {
        'CHANNEL_SOURCE_DOMAIN': CHANNEL_DOMAIN,
        'CHANNEL_SOURCE_ID': "{}_{}".format(CHANNEL_SOURCE_ID, language.name),
        'CHANNEL_TITLE': "{} ({})".format(CHANNEL_NAME, language.name),
        'CHANNEL_LANGUAGE': CHANNEL_LANGUAGE,
        'CHANNEL_THUMBNAIL': TTL_MAIN_LOGO,
        'CHANNEL_DESCRIPTION': CHANNEL_DESCRIPTION,
    }
    ASSETS_DIR = os.path.abspath('assets')
    DATA_DIR = os.path.abspath('chefdata')
    DOWNLOADS_DIR = os.path.join(DATA_DIR, 'downloads')
    ARCHIVE_DIR = os.path.join(DOWNLOADS_DIR, 'archive_{}'.format(CONTENT_ARCHIVE_VERSION))

    # Your chef subclass can override/extend the following method:
    # get_channel: to create ChannelNode manually instead of using channel_info
    # pre_run: to perform preliminary tasks, e.g., crawling and scraping website
    # __init__: if need to customize functionality or add command line arguments

    def video_node_from_dropbox(self, video_details, link, token):
        dbx = dropbox.Dropbox(token)

        metadata, res = dbx.sharing_get_shared_link_file(url=link)
        # get relative path to video file
        video_path = os.path.relpath(os.path.join(VIDEO_FOLDER, metadata.name))

        if not os.path.isfile(video_path):
            with open(video_path, 'wb') as f:
                f.write(res.content)
        else:
            LOGGER.info("{} already downloaded. Skipping".format(metadata.name))

        video_file = files.VideoFile(path=video_path)

        video_node = nodes.VideoNode(
            title=video_details["title"],
            source_id=link,
            license=licenses.CC_BYLicense("TicTacLearn"),
            files=[video_file]
        )

        return video_node

    def video_node_from_local_storage(self, title, file_path, topic_name):
        if os.path.exists(file_path):
            video_file = files.VideoFile(path=file_path, ffmpeg_settings={"max_width": 720})
            video_node = nodes.VideoNode(
                title=title,
                source_id='video_local_topic_name_{}'.format(title),
                license=licenses.CC_BYLicense("TicTacLearn"),
                files=[video_file]
            )

            return video_node

    # returns an array of questions
    def create_question(self, question_data):
        question_arr = []
        for key_id, question_metadata in question_data:
            if question_metadata["question"] is None:
                question_text = question_metadata["question_image"]
            else:
                question_text = question_metadata["question"] if question_metadata["question_image"] == None else \
                    question_metadata["question"] + " " + question_metadata["question_image"]

            question = SingleSelectQuestion(
                id=key_id,
                question=question_text,
                correct_answer=question_metadata["correct_answer"],
                all_answers=question_metadata["all_answers"],
                hints=[]
            )
            question_arr.append(question)

        return question_arr

    def upload_content(self, data, channel):
        for language, language_value in data.items():
            # convert to title to apply title case for node titles
            language = language.title()
            language_node = nodes.TopicNode(
                title=language,
                source_id=language,
                author="TicTacLearn",
                description='',
                thumbnail=TTL_MAIN_LOGO,
                language=getlang_by_name(language)
            )
            for grade, grade_value in language_value.items():
                grade_node = nodes.TopicNode(
                    title='{}'.format(grade).replace('_', ' '),
                    source_id="{}-{}".format(language, grade),
                    author="TicTacLearn",
                    description='',
                    # thumbnail=TTL_MAIN_LOGO,
                    language=getlang_by_name(language)
                )

                for subject, subject_value in grade_value.items():
                    subject = subject.title()
                    subject_node = nodes.TopicNode(
                        title=subject,
                        source_id="{}-{}-{}".format(language, grade, subject),
                        author="TicTacLearn",
                        description='',
                        # thumbnail=TTL_MAIN_LOGO,
                        language=getlang_by_name(language)
                    )
                    for chapter, chapter_value in subject_value.items():
                        if chapter:
                            chapter = chapter.title()
                            chapter_node = nodes.TopicNode(
                                title=chapter.replace('_', ' '),
                                source_id="{}-{}-{}-{}".format(language, grade, subject, chapter),
                                author="TicTacLearn",
                                description='',
                                # thumbnail=TTL_MAIN_LOGO,
                                language=getlang_by_name(language)
                            )
                            for topic, topic_value in chapter_value.items():
                                topic = topic.title()
                                if topic == "Chapter Assessment":
                                    questions = self.create_question(topic_value.items())
                                    if questions:
                                        exercise_node = nodes.ExerciseNode(
                                            source_id="{}-{}-{}-{}-{}".format(language, grade, subject, chapter, topic),
                                            title=topic,
                                            author="TicTacLearn",
                                            description="Chapter Assessment",
                                            language=getlang_by_name(language),
                                            license=licenses.CC_BYLicense("TicTacLearn"),
                                            # thumbnail=TTL_MAIN_LOGO,
                                            exercise_data={
                                                "mastery_model": exercises.M_OF_N,
                                                "m": len(questions),
                                                "n": len(questions),
                                                "randomize": True
                                            },
                                            questions=questions
                                        )
                                        chapter_node.add_child(exercise_node)
                                else:
                                    topic_node = nodes.TopicNode(
                                        title=topic,
                                        source_id="{}-{}-{}-{}-{}".format(language, grade, subject, chapter, topic),
                                        author="TicTacLearn",
                                        description='',
                                        # thumbnail=TTL_MAIN_LOGO,
                                        language=getlang_by_name(language)
                                    )
                                    for content_type, content in topic_value.items():
                                        if content_type.lower() == "video":
                                            for file_name in content:
                                                try:
                                                    video_node = self.video_node_from_local_storage(
                                                        file_name, content.get(file_name), topic)
                                                    topic_node.add_child(video_node)
                                                except Exception as e:
                                                    LOGGER.info(e)
                                                    LOGGER.info(
                                                        "{}-{}-{}-{}-{}".format(language, grade, subject, chapter,
                                                                                topic))
                                                    LOGGER.info("Error getting video from local with path: {}".format(
                                                        content))
                                        else:
                                            # content type is assessment
                                            questions = self.create_question(content.items())
                                            exercise_node = nodes.ExerciseNode(
                                                source_id="{}-{}-{}-{}-{}-Assessment".format(language, grade, subject,
                                                                                             chapter, topic),
                                                title="{} Assessment".format(topic),
                                                author="TicTacLearn",
                                                description="{} Assessment".format(topic),
                                                license=licenses.CC_BYLicense("TicTacLearn"),
                                                # thumbnail=TTL_MAIN_LOGO,
                                                exercise_data={
                                                    "mastery_model": exercises.M_OF_N,
                                                    "m": len(questions),
                                                    "n": len(questions),
                                                    "randomize": True
                                                },
                                                questions=questions
                                            )
                                            topic_node.add_child(exercise_node)

                                    chapter_node.add_child(topic_node)
                                chapter_node.sort_children()
                            subject_node.add_child(chapter_node)
                        subject_node.sort_children()
                    grade_node.add_child(subject_node)
                channel.add_child(grade_node)

        return channel

    def get_file_id(self, url):
        regex = '(?<=\/d\/)(.+)(?=\/)'
        result = re.search(regex, url)
        return result.group(1)

    def add_to_failed(self, link, details, content_type):
        with open(FAILED_LINKS_JSON, encoding='utf-8') as f:
            try:
                data = json.loads(f.read())
            except:
                # no data in json file
                print('no data in json file')
                with open(FAILED_LINKS_JSON, 'w', encoding='utf-8') as json_file:
                    dict_failed = {}
                    dict_failed[link] = {}
                    dict_failed[link]["title"] = details["title"]
                    dict_failed[link]["type"] = content_type
                    json.dump(dict_failed, json_file, indent=4, ensure_ascii=False)
                    return

            with open(FAILED_LINKS_JSON, 'w', encoding='utf-8') as json_file:
                data[link] = {}
                data[link]["title"] = details["title"]
                data[link]["type"] = content_type
                json.dump(data, json_file, indent=4, ensure_ascii=False)
                return

    def construct_channel(self, *args, **kwargs):
        """
        Creates ChannelNode and build topic tree
        Args:
          - args: arguments passed in on the command line
          - kwargs: extra options passed in as key="value" pairs on the command line
            For example, add the command line option   lang="fr"  and the value
            "fr" will be passed along to `construct_channel` as kwargs['lang'].
        Returns: ChannelNode
        """
        """
        Channel structure:
            Language > Grade > Subject > Chapter > Topic Name > Content
        """
        channel = self.get_channel(*args, **kwargs)  # Create ChannelNode from data in self.channel_info

        if os.path.exists(FAILED_LINKS_DIR):
            os.remove(FAILED_LINKS_JSON)
        else:
            os.makedirs(FAILED_LINKS_DIR, exist_ok=True)

        if not os.path.exists(VIDEO_FOLDER):
            os.makedirs(VIDEO_FOLDER, exist_ok=True)

        if not os.path.exists(SHEETS_FOLDER):
            os.makedirs(SHEETS_FOLDER, exist_ok=True)
        with open(FAILED_LINKS_JSON, 'w+'):
            pass
        with open(FAILED_IMAGES_JSON, 'w+'):
            pass

        language = getlang(CHANNEL_LANGUAGE)
        root_folder = os.path.abspath('downloads/{}'.format(str(language.name).capitalize()))
        dict_all_files_paths = get_all_local_folder_paths(root_folder)
        dict_all_files = get_all_local_files(EXCEL_PATH, language.name, dict_all_files_paths)
        dict_assessment_lang = DICT_ASSESSMENT_XLS.get(CHANNEL_LANGUAGE)
        data = read_assessment_xls(dict_assessment_lang, dict_all_files)

        channel = self.upload_content(data, channel)

        return channel


# CLI
################################################################################
if __name__ == '__main__':
    # This code runs when sushichef.py is called from the command line
    chef = TicTacLearnChef()
    chef.main()
