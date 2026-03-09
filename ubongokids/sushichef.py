#!/usr/bin/env python

import os
import logging
import re
import json

import youtube_dl

from cache import Db
from youtube import Client, CachingClient

from le_utils.constants import content_kinds, licenses
from ricecooker.chefs import JsonTreeChef
from ricecooker.classes.licenses import get_license
from ricecooker.utils.jsontrees import write_tree_to_json_tree
from ricecooker.config import setup_logging


# Switches on caching and debug log level
DEBUG = True

logger = logging.getLogger(__name__)

setup_logging(
    level=logging.DEBUG if DEBUG else logging.INFO,
    add_loggers=["requests.packages", "cachecontrol.controller", "ubongo_youtubedl"]
)

# Store a list of videos per playlist. Some playlists have duplicate videos, so
# skip them.
VIDEOS_USED_SOURCE_IDS = {}


class UbongoKidsChef(JsonTreeChef):
    HOSTNAME = "ubongokids.com"
    ROOT_URL = "http://www.{}".format(HOSTNAME)
    DATA_DIR = "chefdata"
    TREES_DATA_DIR = os.path.join(DATA_DIR, "trees")
    CRAWLING_STAGE_OUTPUT = "web_resource_tree.json"
    SCRAPING_STAGE_OUTPUT = "ricecooker_json_tree.json"
    LICENSE = get_license(
        licenses.CC_BY_NC_ND, copyright_holder="Ubongo Media"
    ).as_dict()
    
    # List of Youtube channels and their language.
    YOUTUBE_CHANNELS = {
        "UCwYh0qBAF8HyKt0KUMp1rNg": {
            "lang": "swa",
            "name": "Ubongo Kids (Kiswahili)",
        },
        "UCjsrL7gPn-S5SJJcKp-OYUA": {
            "lang": "en",
            "name": "Ubongo Kids (English)",
        },
        "UCcJywQx_THCEr5-1mJbGL9w": {
            "lang": "swa",
            "name": "Akili and Me (Kiswahili)",
        },
        "UC0TLvo891eEEM6HGC5ON7ug": {
            "lang": "en",
            "name": "Akili and Me (English)"
        },
    }

    def pre_run(self, args, options):
        self.youtube = Client(
            youtube_dl.YoutubeDL(
                dict(
                    verbose=True,
                    no_warnings=True,
                    writesubtitles=True,
                    allsubtitles=True,
                    logger=logging.getLogger("ubongo_youtubedl"),
                    extract_flat=True,  # This is necessary for playlists to not request info for each video and hit API limits
                )
            )
        )
        if DEBUG:
            cache = Db(os.path.join(os.getcwd(), ".cache"), "ubongokids.pickle")
            self.youtube = CachingClient(self.youtube, cache)
        self.crawl(args, options)
        self.scrape(args, options)

    def crawl(self, args, options):
        web_resource_tree = dict(
            kind="UbongoKidsWebResourceTree",
            title="Ubongo Kids is a Tanzanian edutainment cartoon made by Ubongo Media.",
            children=[
                self.crawl_youtube_channel(cid)
                for cid in UbongoKidsChef.YOUTUBE_CHANNELS.keys()
            ],
        )
        with open(
            os.path.join(
                UbongoKidsChef.TREES_DATA_DIR, UbongoKidsChef.CRAWLING_STAGE_OUTPUT
            ),
            "w",
        ) as f:
            json.dump(web_resource_tree, f, indent=2)
            logger.info("Crawling results stored")
        return web_resource_tree

    def crawl_youtube_channel(self, channel_id):
        youtube_channel = self.youtube.get_channel_data(channel_id)
        title = UbongoKidsChef.YOUTUBE_CHANNELS[channel_id]["name"]
        # Alternative version is this, but the channels were not named after
        # the same pattern
        # title = youtube_channel["name"]
        return dict(
            kind="UbongoKidsYoutubeChannel",
            id=youtube_channel["id"],
            title=title,
            url=youtube_channel["url"],
            children=[
                self.crawl_youtube_playlist(playlist_id)
                for playlist_id in youtube_channel["playlists"]
            ],
            language=UbongoKidsChef.YOUTUBE_CHANNELS[channel_id]["lang"],
        )

    def crawl_youtube_playlist(self, playlist_id):
        playlist = self.youtube.get_playlist_data(playlist_id)
        title = playlist["name"]
        children = [
            self.crawl_youtube_video(video_id) for video_id in playlist["videos"]
        ]
        # Remove all the None-types
        children = list(filter(bool, children))
        return dict(
            kind="UbongoKidsYoutubePlaylist",
            id=playlist["id"],
            title=title,
            url=playlist["url"],
            children=children,
        )

    def crawl_youtube_video(self, video_id):
        video = self.youtube.get_video_data(video_id)
        if not video:
            return None
        result = dict(
            kind="UbongoKidsYoutubeVideo",
        )
        result.update(video)
        return result

    def scrape(self, args, options):
        with open(
            os.path.join(
                UbongoKidsChef.TREES_DATA_DIR, UbongoKidsChef.CRAWLING_STAGE_OUTPUT
            ),
            "r",
        ) as f:
            web_resource_tree = json.load(f)
            assert web_resource_tree["kind"] == "UbongoKidsWebResourceTree"

        ricecooker_json_tree = dict(
            source_domain=UbongoKidsChef.HOSTNAME,
            source_id="ubongokids",
            title="Ubongo Kids",
            description="""Interactive edu-cartoons that teach math and science through fun animated stories and catchy original songs, launched on TanzaniaTV in January 2014 and produced by Ubongo Media."""[
                :400
            ],
            thumbnail="http://www.ubongokids.com/wp-content/uploads/2016/06/logo_ubongo_kids-150x100.png",
            # Means multilingual
            # https://ricecooker.readthedocs.io/en/latest/examples/languages.html
            language="mul",
            children=[
                self.scrape_youtube_channel(child)
                for child in web_resource_tree["children"]
            ],
            license=UbongoKidsChef.LICENSE,
        )
        write_tree_to_json_tree(
            os.path.join(
                UbongoKidsChef.TREES_DATA_DIR, UbongoKidsChef.SCRAPING_STAGE_OUTPUT
            ),
            ricecooker_json_tree,
        )
        return ricecooker_json_tree

    def scrape_youtube_channel(self, channel):
        language = UbongoKidsChef.YOUTUBE_CHANNELS[channel["id"]]["lang"]
        return dict(
            kind=content_kinds.TOPIC,
            source_id=channel["id"],
            title=channel["title"],
            description="",
            children=[
                self.scrape_youtube_playlist(playlist, language, channel["id"])
                for playlist in channel["children"]
            ],
            language=language,
            license=UbongoKidsChef.LICENSE,
        )

    def scrape_youtube_playlist(self, playlist, language, channel_id):
        parent_source_id = "channel:{}-playlist:{}".format(channel_id, playlist["id"])
        children = [self.scrape_youtube_video(video, parent_source_id, language) for video in playlist["children"]]
        children = list(filter(lambda x: x is not None, children))
        return dict(
            kind=content_kinds.TOPIC,
            source_id="channel:{}-playlist:{}".format(channel_id, playlist["id"]),
            title=playlist["title"],
            children=children,
            language=language,
            license=UbongoKidsChef.LICENSE,
        )

    def scrape_youtube_video(self, video, parent_source_id, language):
        """
        :param parent_source_id: the source id of the parent is retained to
        check that the same video isn't duplicated and to ensure uniqueness
        
        """
        source_id = "video:{}".format(video["id"])
        
        if parent_source_id not in VIDEOS_USED_SOURCE_IDS:
            VIDEOS_USED_SOURCE_IDS[parent_source_id] = []
        if source_id in VIDEOS_USED_SOURCE_IDS[parent_source_id]:
            logger.warning("Video appears twice in the same parent and is ignored: {} - parent: {}".format(video["url"], parent_source_id))
            return None
        VIDEOS_USED_SOURCE_IDS[parent_source_id].append(source_id)
        
        # Many titles are of the form
        # [unique title] | [playlist] | [generic descriptor]
        # [unique title] - [playlist] - [generic descriptor]
        title = video["title"].strip()
        before_title = title
        
        # Simple check, if the result after cleaning up a title matches
        # something in this list, skip it
        skip_title_if_matches = [
            re.compile(r"^Ubongo\sKids\sSing-Along$"),
            re.compile(r"United\sNations\s\+\sUbongo\sKids"),
            re.compile(r"^Geometry$"),
            re.compile(r"^Math\sSong"),
        ]

        titles_dash = title.split(" - ")
        titles_dash = list(filter(lambda s: s != "", titles_dash))
         
        titles_pipe = title.split(" | ")
        titles_pipe = list(filter(lambda s: s != "", titles_pipe))
        
        if len(titles_dash) == 3:
            title = titles_dash[0]
        elif len(titles_pipe) == 3:
            title = titles_pipe[0]
        elif len(titles_pipe) == 4:
            # Join the first two components in this pattern
            title = " - ".join(titles_pipe[0:2])
        
        title = title.strip()
        
        if any(p.match(title) for p in skip_title_if_matches):
            logging.debug("Ignoring title change for: {}".format(title))
            title = before_title
        
        # Consistent use of dash instead of pipe
        title = title.replace(" | ", " - ")
        
        return dict(
            kind=content_kinds.VIDEO,
            source_id=source_id,
            title=title,
            thumbnail=video["thumbnail"],
            description="",  # video["description"] does not provide adequate descriptions
            files=[dict(file_type=content_kinds.VIDEO, youtube_id=video["id"], high_resolution=False)],
            language=language,
            license=UbongoKidsChef.LICENSE,
        )


if __name__ == "__main__":

    UbongoKidsChef().main()
