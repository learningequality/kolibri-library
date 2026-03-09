import os
import shutil
import sys
import time
from typing import Dict, List, Optional, Tuple, Union

import fitz
import requests

from bs4 import BeautifulSoup

from le_utils.constants.labels import subjects

from ricecooker.chefs import SushiChef
from ricecooker.classes.files import DocumentFile
from ricecooker.classes.files import VideoFile
from ricecooker.classes.licenses import get_license
from ricecooker.classes.nodes import ChannelNode
from ricecooker.classes.nodes import DocumentNode
from ricecooker.classes.nodes import TopicNode
from ricecooker.classes.nodes import VideoNode
from ricecooker.config import LOGGER

SESSION = requests.Session()
COURSE_URL = "https://fundawande.org"
SIZE_LIMIT = 15 * 1024 * 1024  # 15 MB


def make_request(
    url: str, timeout: int = 60, method: str = "GET", **kwargs
) -> Optional[requests.Response]:
    """
    Failure-resistant HTTP GET/HEAD request helper method.
    """
    retry_count = 0
    max_retries = 5
    # needs to change the User-Agent to avoid being blocked

    while True:
        try:
            response = SESSION.request(method, url, timeout=timeout, **kwargs)
            break
        except (
            requests.exceptions.ConnectionError,
            requests.exceptions.ReadTimeout,
        ) as e:
            retry_count += 1
            LOGGER.warning(
                "Connection error ('{msg}'); about to perform retry {count} of {trymax}.".format(
                    msg=str(e), count=retry_count, trymax=max_retries
                )
            )
            time.sleep(retry_count * 1)
            if retry_count >= max_retries:
                LOGGER.error("FAILED TO RETRIEVE:" + str(url))
                return None
    if response.status_code != 200:
        LOGGER.error("ERROR " + str(response.status_code) + " when getting url=" + url)
        return None
    return response


def download_page(url: str) -> Tuple[Optional[str], Optional[BeautifulSoup]]:
    """def download_page(url: str) -> Tuple[Optional[str], Optional[BeautifulSoup]]:
    Download `url` (following redirects) and soupify response contents.
    Returns (final_url, page) where final_url is URL afrer following redirects.
    """
    response = make_request(url)
    if not response:
        return (None, None)
    html = response.text
    page = BeautifulSoup(html, "html.parser")
    LOGGER.debug("Downloaded page " + str(url))
    return (response.url, page)


def map_categories(name: str) -> List[str]:
    """
    Map categories to LE subjects
    """
    categories = []
    if name in (
        "Literacy Workbooks",
        "Reading Academy ",
        "Reading Strategy 2022 - 2030",
        "ECDoE Reading Policy",
    ):
        categories = [
            subjects.LITERACY,
            subjects.READING_AND_WRITING,
            subjects.READING_COMPREHENSION,
        ]
    if name in ("Maths Workbooks", "Maths", "Numeracy Academy"):
        categories.append(subjects.MATHEMATICS)
    if name in (
        "Teaching Guides",
        "Instructional Coaching",
        "Lesson Plan Intervention",
        "Reading for Meaning Course",
    ):
        categories.append(subjects.FOR_TEACHERS)
    if name in "DBE Vocabulary Posters":
        categories.append(
            subjects.LANGUAGE_LEARNING,
        )

    return categories


class FundaWandeSushiChef(SushiChef):

    channel_info: Dict[str, str] = {
        "CHANNEL_TITLE": "Funda Wande Organization - English",
        "CHANNEL_SOURCE_DOMAIN": "https://fundawande.org/",
        "CHANNEL_SOURCE_ID": "funda-wande",
        "CHANNEL_LANGUAGE": "en",
        "CHANNEL_THUMBNAIL": "https://fundawande.org/img/funda-wande-logo.png",
        "CHANNEL_DESCRIPTION": "Funda Wande is a not-for-profit organization that aims to equip teachers to teach reading-for-meaning and calculating-with-confidence in Grades R-3 in South Africa.",
    }

    SETTINGS: Dict[str, Union[bool, Dict[str, int]]] = {
        "compress": True,
        "ffmpeg_settings": {"video-height": 480},
    }

    def crawl(self, section: str, element: str) -> Dict[str, Dict[str, str]]:
        LOGGER.info("Crawling... {}".format(section))
        resources: Dict[str, Dict[str, str]] = {}
        _, page = download_page("{}/{}".format(COURSE_URL, section))
        if page is None:
            return resources
        links = page.find_all(element, {"data-cat4": "ENG"})
        urls = []
        for link in links:
            if element == "a":
                url = "{}{}".format(COURSE_URL, link.get("href"))
            else:
                onclick_attr = link["onclick"]
                url = "{}{}".format(COURSE_URL, onclick_attr.split("'")[1])
                if url[-3:] != "mp4":
                    continue  # wrong link in the page

            if url in urls:
                continue  # skip duplicate pdfs/files
            urls.append(url)
            name = link.get("data-label").strip()
            topic = link.get("data-cat1").strip()
            level = link.get("data-cat2").strip()
            term = link.get("data-cat3").strip()

            # let's add the level to the name for the Reading for Meaning Course videos
            if topic == "Reading for Meaning Course":
                if element != "a":
                    name = "{}: {}".format(level, name)
            if (
                "Covid" in topic
                or "Phonics" in topic
                or "Marksheets" in topic
                or "Strategy" in topic
            ):
                continue  # skip section having these words in their titles
            if topic == "Maths Workbooks":
                topic = "Maths"
            idx = "{}-{}-{}-{}_id".format(topic, level, term, name)
            idx = idx.replace(" ", "_")
            if topic not in self.topics:
                self.topics[topic] = [idx]
            else:
                self.topics[topic].append(idx)
            resource = {
                "name": name,
                "topic": topic,
                "level": level,
                "term": term,
                "url": url,
            }
            resources[idx] = resource

        return resources

    def download_and_compress_pdfs(self) -> None:
        LOGGER.info("Downloading pdf files...")
        for pdf in self.pdfs.keys():
            pdf_name = "chefdata/{}.pdf".format(pdf)
            compressed_pdf = "chefdata/compressed/{}.pdf".format(pdf)
            if not os.path.exists(compressed_pdf):
                # download the pdf
                if not os.path.exists(pdf_name):
                    LOGGER.info("Downloading pdf file {}".format(pdf_name))
                    pdf_url = self.pdfs[pdf]["url"]
                    pdf_file = requests.get(pdf_url)
                    with open(pdf_name, "wb") as f:
                        f.write(pdf_file.content)
                # compress the pdf if its more than 15 MB:
                file_size = os.path.getsize(pdf_name)
                if file_size > SIZE_LIMIT:
                    LOGGER.info("Compressing pdf file {}".format(pdf_name))
                    doc = fitz.open(pdf_name)
                    try:
                        doc.save(
                            compressed_pdf,
                            garbage=4,
                            deflate=True,
                            clean=True,
                            deflate_images=True,
                        )
                    except ValueError:
                        print("Error compressing file {}...".format(pdf_name))
                        sys.exit(1)
                else:
                    shutil.copy2(pdf_name, compressed_pdf)

    def pre_run(self, args, options):
        self.topics = {}
        self.pdfs = self.crawl("/learning-resources", "a")
        self.videos = self.crawl("/video-resources", "button")
        self.download_and_compress_pdfs()

    def get_subtopic_node(
        self, topic_node: TopicNode, obj: Dict[str, str], categories: List[str]
    ) -> TopicNode:
        if "Grade" not in obj["level"]:
            return topic_node
        if self.using_subtopics:
            if obj["level"] not in self.subtopics:
                subtopic_node = TopicNode(
                    source_id="{}_id".format(obj["level"]),
                    title=obj["level"],
                    categories=categories,
                )
                self.subtopics[obj["level"]] = subtopic_node
                topic_node.add_child(subtopic_node)
            subtopic_node = self.subtopics[obj["level"]]
        else:
            subtopic_node = topic_node
        return subtopic_node

    def construct_channel(self, *args, **kwargs) -> ChannelNode:
        channel = self.get_channel(*args, **kwargs)
        used_resorces = []
        for topic in self.topics.keys():
            categories = map_categories(topic)
            topic_node = TopicNode(
                source_id="{}_id".format(topic.replace(" ", "_")),
                title=topic,
                categories=categories,
            )
            self.subtopics: Dict[str, TopicNode] = {}
            # If topic has Grades, let's split it into subtopics
            self.using_subtopics = "Grade" in self.topics[topic][0]
            self.last_subtopic = None
            for resource in self.topics[topic]:

                if resource in used_resorces:
                    print("Skipping resource {}".format(resource))
                    continue
                used_resorces.append(resource)
                if resource in sorted(self.pdfs):
                    obj_resource = self.pdfs.get(resource)
                    subtopic_node = self.get_subtopic_node(
                        topic_node, obj_resource, categories
                    )

                    pdf_file = DocumentFile(
                        path="chefdata/compressed/{}.pdf".format(resource),
                        language="en",
                    )
                    term = (
                        "{} - ".format(obj_resource["term"])
                        if obj_resource["term"] != "All"
                        else ""
                    )
                    subtopic_node.add_child(
                        DocumentNode(
                            source_id=resource,
                            title="{}{}".format(term, obj_resource["name"]),
                            files=[pdf_file],
                            author="Funda Wande",
                            license=get_license(
                                "CC BY", copyright_holder="Funda Wande"
                            ),
                            categories=categories,
                        )
                    )
                elif resource in sorted(self.videos):
                    video_file = VideoFile(
                        path=self.videos[resource]["url"],
                        language="en",
                    )
                    obj_resource = self.videos.get(resource)
                    subtopic_node = self.get_subtopic_node(
                        topic_node, obj_resource, categories
                    )
                    subtopic_node.add_child(
                        VideoNode(
                            source_id=resource,
                            license=get_license(
                                "CC BY", copyright_holder="Funda Wande"
                            ),
                            title=obj_resource["name"],
                            author="Funda Wande",
                            files=[video_file],
                            categories=categories,
                        )
                    )

            channel.add_child(topic_node)

        return channel


if __name__ == "__main__":
    """
    Run this script on the command line using:
        python sushichef.py -v --token=YOURTOKENHERE9139139f3a23232

    """
    chef = FundaWandeSushiChef()
    chef.main()
