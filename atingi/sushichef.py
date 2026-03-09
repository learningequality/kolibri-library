#!/usr/bin/env python
import json
import os
from typing import Any
from typing import Dict
from typing import List

import requests
from le_utils.constants.labels import levels
from le_utils.constants.labels import subjects
from ricecooker.chefs import SushiChef
from ricecooker.classes.files import DocumentFile
from ricecooker.classes.files import HTMLZipFile
from ricecooker.classes.licenses import get_license
from ricecooker.classes.nodes import ChannelNode
from ricecooker.classes.nodes import DocumentNode
from ricecooker.classes.nodes import HTML5AppNode
from ricecooker.classes.nodes import TopicNode
from ricecooker.config import LOGGER
from ricecooker.utils.zip import create_predictable_zip

from transform import copy_digital_enquirer_kit_files
from transform import download_gdrive_files
from transform import prepare_lesson_html5_directory
from transform import unzip_scorm_files

CHANNEL_NAME = "Learn with atingi"
CHANNEL_SOURCE_ID = "atingi"
SOURCE_DOMAIN = "https://www.atingi.org/"
CHANNEL_LANGUAGE = "en"
CHANNEL_DESCRIPTION = "Learn digital and professional skills, connect with peers, and take action for your future."  # noqa: E501
CHANNEL_THUMBNAIL = "chefdata/logoatingi.png"
CONTENT_ARCHIVE_VERSION = 1

CHANNEL_LICENSE = get_license("CC BY-SA", copyright_holder="Atingi")
SESSION = requests.Session()

categories: List[str] = [
    subjects.TECHNICAL_AND_VOCATIONAL_TRAINING,
    subjects.DIGITAL_LITERACY,
    subjects.TOOLS_AND_SOFTWARE_TRAINING,
]

grade_levels: List[str] = [
    levels.PROFESSIONAL,
    levels.WORK_SKILLS,
]


class AtingiChef(SushiChef):
    channel_info: Dict[str, str] = {
        "CHANNEL_SOURCE_DOMAIN": SOURCE_DOMAIN,
        "CHANNEL_SOURCE_ID": CHANNEL_SOURCE_ID,
        "CHANNEL_TITLE": CHANNEL_NAME,
        "CHANNEL_LANGUAGE": CHANNEL_LANGUAGE,
        "CHANNEL_THUMBNAIL": CHANNEL_THUMBNAIL,
        "CHANNEL_DESCRIPTION": CHANNEL_DESCRIPTION,
    }

    def download_content(self) -> None:
        LOGGER.info("Downloading needed files from Google Drive folders")
        download_gdrive_files()
        LOGGER.info("Uncompressing courses in scorm format")
        unzip_scorm_files()
        # create html5app nodes for each lesson
        for course in self.course_data.keys():
            course_dir = course.replace(" ", "_").replace("&", "").lower()

            for lesson in self.course_data[course]:
                lesson_dir = os.path.join(f"chefdata/{course_dir}/{lesson}")
                if not os.path.exists(lesson_dir):  # create lesson app dir
                    lesson_data = self.course_data[course][lesson]
                    if course_dir == "digital_enquirer_kit":
                        copy_digital_enquirer_kit_files(
                            lesson_data, lesson_dir
                        )  # noqa: E501
                    else:
                        prepare_lesson_html5_directory(lesson_data, lesson_dir)
                LOGGER.info(
                    f"Creating zip for lesson: {lesson} in course {course}"  # noqa: E501
                )
                self.course_data[course][lesson][
                    "zipfile"
                ] = create_predictable_zip(  # noqa: E501
                    lesson_dir
                )

    def pre_run(self, args: Any, options: dict) -> None:
        self.course_data = json.load(open("chefdata/course_data.json"))
        LOGGER.info("Downloading files from Google Drive folders")

    def build_doc_node(
        self, doc: str, lesson_title: str, lesson_file: str
    ) -> DocumentNode:
        unit = lesson_title.split(" - ")[0]
        doc_name = doc.replace(".pdf", "")
        doc_node = DocumentNode(
            source_id=f"{doc_name.replace(' ', '_')}_id",
            title=f"{unit} forms: {doc_name}",
            files=[
                DocumentFile(
                    f"chefdata/{lesson_file}/scormcontent/assets/{doc}"
                )  # noqa: E501
            ],  # noqa: E501
            license=CHANNEL_LICENSE,
            language="en",
            categories=categories,
            grade_levels=grade_levels,
        )
        return doc_node

    def construct_channel(self, *args, **kwargs) -> ChannelNode:
        channel = self.get_channel(*args, **kwargs)
        sub_topic_node = None
        for course in self.course_data.keys():
            course_dir = course.replace(" ", "_").replace("&", "").lower()
            thumbnail = f"chefdata/{course_dir}.png"
            topic_node = TopicNode(
                source_id=f"{course_dir}_id",
                title=course,
                categories=categories,
                grade_levels=grade_levels,
                thumbnail=thumbnail,
                language=CHANNEL_LANGUAGE,
                author="Atingi",
            )
            for lesson in self.course_data[course]:
                lesson_data = self.course_data[course][lesson]
                title = lesson_data["title"]
                if "Module" in title:
                    module_name = title.split(":")[0]
                    if (
                        sub_topic_node is None
                        or getattr(sub_topic_node, "title", None)
                        != module_name  # noqa: E501
                    ):
                        if (
                            sub_topic_node is not None
                            and getattr(sub_topic_node, "title", None)
                            != module_name  # noqa: E501
                        ):
                            topic_node.add_child(sub_topic_node)
                        sub_topic_node = TopicNode(
                            source_id=f"{module_name}_{course_dir}_id".replace(
                                " ", "_"
                            ),
                            title=module_name,
                            categories=categories,
                            grade_levels=grade_levels,
                            thumbnail=thumbnail,
                            language=CHANNEL_LANGUAGE,
                            author="Atingi",
                        )

                else:
                    sub_topic_node = None

                zip_file = lesson_data["zipfile"]
                zip_node = HTML5AppNode(
                    source_id="{}_{}_id".format(
                        course_dir, lesson.replace(" ", "_")
                    ),  # noqa: E501
                    title=title,
                    files=[HTMLZipFile(zip_file)],
                    license=CHANNEL_LICENSE,
                    language="en",
                    categories=categories,
                    grade_levels=grade_levels,
                )
                if sub_topic_node is not None:
                    sub_topic_node.add_child(zip_node)
                else:
                    topic_node.add_child(zip_node)
            if sub_topic_node is not None:
                topic_node.add_child(sub_topic_node)
            channel.add_child(topic_node)
        return channel


if __name__ == "__main__":
    chef = AtingiChef()
    chef.main()
