#!/usr/bin/env python
import csv
import os
import re

from le_utils.constants.labels import levels
from le_utils.constants.labels import subjects
from PIL import Image
from PIL import UnidentifiedImageError
from ricecooker.chefs import SushiChef
from ricecooker.classes import files
from ricecooker.classes import licenses
from ricecooker.classes import nodes
from ricecooker.config import get_storage_path
from ricecooker.config import LOGGER
from ricecooker.utils.youtube import YouTubePlaylistUtils
from ricecooker.utils.youtube import YouTubeVideoUtils


YOUTUBE_CACHE_DIR = os.path.join("chefdata", "youtubecache")


def extract_id_from_link(link):
    match = re.search(r"list=([^&]+)", link)
    return match.group(1) if match else None


def convert_row(row):
    return {
        "level1Folder": row["Level 1 folders"],
        "level2Folder": row["Level 2 folders"],
        "grade_level": row["grade_level"],
        "subject": row["subject"],
        "id": extract_id_from_link(row["Link"]),
    }


def convert_csv(csv_path):
    with open(csv_path, "r") as csvfile:
        reader = csv.DictReader(csvfile)
        grade_topics = []
        grade_topic = None
        for row in reader:
            if row["Level 1 folders"]:
                grade_topic = {
                    "title": row["Level 1 folders"],
                    "grade_level": row["grade_level"],
                    "children": [],
                }
                grade_topics.append(grade_topic)
            grade_topic["children"].append(convert_row(row))

        return grade_topics


# Run constants
################################################################################
CHANNEL_NAME = "Guyana Learning Channel"  # Name of Kolibri channel
CHANNEL_SOURCE_ID = "GuyanaLearningChannel"  # Unique ID for content source
CHANNEL_DOMAIN = "https://www.youtube.com/@GuyanaLearningChannel/playlists"  # Who is providing the content
CHANNEL_LANGUAGE = "en"  # Language of channel
CHANNEL_DESCRIPTION = "The Guyana Learning Channel provides hundreds of educational videos covering most subjects in primary and secondary education, using a lesson format: in each video a teacher presents a lesson using interactive graphics. Approved by the Ministry of Education, Guyana."  # Description of the channel (optional)
CHANNEL_THUMBNAIL = "https://yt3.googleusercontent.com/zRAVzOjRY_2DNJlZmH5nLzSmyE1VsGEL_doOVOY0cj9Z-G4pKgET4Q59acLtkRDsIb9L3x5WGxw=s176-c-k-c0x00ffffff-no-rj"  # Local path or url to image file (optional)
CHANNEL_TAGLINE = "Hundreds of videos covering most of the subjects in primary and secondary education. Approved by the Ministry of Education, Guyana."

COPYRIGHT_HOLDER = (
    "Ministry of Education, Guyana"  # Name of content creator or rights holder
)


# The chef subclass
################################################################################
class GuyanaSEIPChef(SushiChef):
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

    channel_info = {
        "CHANNEL_SOURCE_DOMAIN": CHANNEL_DOMAIN,
        "CHANNEL_SOURCE_ID": CHANNEL_SOURCE_ID,
        "CHANNEL_TITLE": CHANNEL_NAME,
        "CHANNEL_LANGUAGE": CHANNEL_LANGUAGE,
        "CHANNEL_THUMBNAIL": CHANNEL_THUMBNAIL,
        "CHANNEL_DESCRIPTION": CHANNEL_DESCRIPTION,
        "CHANNEL_TAGLINE": CHANNEL_TAGLINE,
    }

    SETTINGS = {
        "compress": True,
        "video-height": 720,
    }

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
        channel = self.get_channel(
            *args, **kwargs
        )  # Create ChannelNode from data in self.channel_info

        grade_topics = convert_csv("playlists.csv")

        for grade_topic in grade_topics:
            grade_topic_source_id = "guyana-moe-grade-topic-{0}".format(
                grade_topic["title"]
            )
            grade_levels = [
                level
                for level, label in levels.choices
                if label.lower() == grade_topic["grade_level"].lower()
            ]
            grade_topic_node = nodes.TopicNode(
                title=grade_topic["title"],
                source_id=grade_topic_source_id,
                author=COPYRIGHT_HOLDER,
                provider=COPYRIGHT_HOLDER,
                language=CHANNEL_LANGUAGE,
                grade_levels=grade_levels,
            )
            playlists = grade_topic["children"]
            for playlist in playlists:
                youtube_playlist = YouTubePlaylistUtils(
                    id=playlist["id"], cache_dir=YOUTUBE_CACHE_DIR
                )
                playlist_info = youtube_playlist.get_playlist_info(use_proxy=False)
                if playlist_info is None:
                    LOGGER.warning(
                        "Skipping playlist {0} as not available from YouTube".format(
                            playlist["id"]
                        )
                    )
                    continue

                # Get channel description if there is any
                playlist_description = playlist_info["description"]

                categories = [
                    subject
                    for subject, label in subjects.choices
                    if label.lower() == playlist["subject"].lower()
                ]

                topic_source_id = "aimhi-child-topic-{0}".format(playlist_info["title"])

                title = playlist_info["title"]

                if ":" in title:
                    title = title.split(":")[0].strip()
                elif "NGSA Booster" in title:
                    title = title.split("-")[1].strip()
                else:
                    title = title.split("-")[0].strip()

                topic_node = nodes.TopicNode(
                    title=title,
                    source_id=topic_source_id,
                    author=COPYRIGHT_HOLDER,
                    provider=COPYRIGHT_HOLDER,
                    description=playlist_description,
                    language=CHANNEL_LANGUAGE,
                    categories=categories,
                )

                for child in playlist_info["children"]:
                    video = YouTubeVideoUtils(
                        id=child["id"], cache_dir=YOUTUBE_CACHE_DIR
                    )
                    video_details = video.get_video_info(use_proxy=False)
                    if video_details is None:
                        LOGGER.warning(
                            "Skipping video {0} as not available from YouTube".format(
                                child["id"]
                            )
                        )
                        continue
                    video_source_id = "GuyanaSEIP-{0}-{1}".format(
                        playlist["id"], video_details["id"]
                    )

                    thumbnail_link = video_details["thumbnail"] or None

                    thumbnail_file = None

                    if thumbnail_link:
                        thumbnail_file = files.ThumbnailFile(thumbnail_link)
                        thumbnail_file.process_file()
                        if thumbnail_file.filename is None:
                            thumbnail_file = None
                        else:
                            try:
                                with Image.open(
                                    get_storage_path(thumbnail_file.filename)
                                ) as im:
                                    im.verify()
                            except UnidentifiedImageError:
                                LOGGER.warning(
                                    "Invalid thumbnail image for video {0}".format(
                                        video_source_id
                                    )
                                )
                                thumbnail_file = None

                    video_node = nodes.VideoNode(
                        source_id=video_source_id,
                        title=video_details["title"],
                        description=video_details["description"],
                        author=COPYRIGHT_HOLDER,
                        language=CHANNEL_LANGUAGE,
                        provider=COPYRIGHT_HOLDER,
                        thumbnail=thumbnail_file,
                        license=licenses.get_license(
                            "CC BY-NC-ND", copyright_holder=COPYRIGHT_HOLDER
                        ),
                        files=[
                            files.YouTubeVideoFile(
                                youtube_id=video_details["id"],
                                language=CHANNEL_LANGUAGE,
                                high_resolution=True,
                            )
                        ],
                    )
                    topic_node.add_child(video_node)
                    if topic_node.thumbnail is None and thumbnail_file is not None:
                        # If the topic node does not have a thumbnail set the first
                        # video's thumbnail as the topic thumbnail, parallel to youtube playlists
                        topic_node.set_thumbnail(thumbnail_file)

                grade_topic_node.add_child(topic_node)
                if (
                    grade_topic_node.thumbnail is None
                    and topic_node.thumbnail is not None
                ):
                    # If the grade topic node does not have a thumbnail set the first
                    # topic's thumbnail as the grade topic thumbnail
                    grade_topic_node.set_thumbnail(topic_node.thumbnail)

            # add topic to channel
            channel.add_child(grade_topic_node)

        return channel


# CLI
################################################################################
if __name__ == "__main__":
    # This code runs when script.py is called from the command line
    chef = GuyanaSEIPChef()
    chef.main()
