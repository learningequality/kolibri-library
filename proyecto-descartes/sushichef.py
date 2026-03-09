#!/usr/bin/env python
import os
import re
import requests
import tempfile
import zipfile
from math import ceil
from bs4 import BeautifulSoup
from urllib.parse import unquote
from collections import OrderedDict
from ricecooker.utils import downloader
from ricecooker.chefs import SushiChef
from ricecooker.classes import files
from ricecooker.config import LOGGER              # Use LOGGER to print messages
from ricecooker.exceptions import raise_for_invalid_channel
from ricecooker.classes.nodes import HTML5AppNode, TopicNode
from ricecooker.utils.caching import CacheForeverHeuristic, FileCache, CacheControlAdapter
from ricecooker.classes.licenses import CC_BY_NC_SALicense
from ricecooker.utils.zip import create_predictable_zip


sess = requests.Session()
cache = FileCache('.webcache')
forever_adapter= CacheControlAdapter(heuristic=CacheForeverHeuristic(), cache=cache)

sess.mount('http://', forever_adapter)


# Run constants
################################################################################
CHANNEL_NAME = "Proyecto Descartes"              # Name of channel
CHANNEL_SOURCE_ID = "sushi-chef-proyecto-descartes-es"    # Channel's unique id
CHANNEL_DOMAIN = "proyectodescartes.org"          # Who is providing the content
CHANNEL_LANGUAGE = "es"      # Language of channel
CHANNEL_DESCRIPTION = "Asociación non-gubernamental que promueve la renovación y cambio metodológico en los procesos de aprendizaje y enseñanza de las Matemáticas y en otras áreas de conocimiento. Los recursos digitales interactivos generados en el Proyecto Descartes son hechos completamente por profesores, y son appropriados por todos los niveles de escuela primaria, secundaria, y bachillerato."                                  # Description of the channel (optional)
CHANNEL_THUMBNAIL = None                                    # Local path or url to image file (optional)

# Additional constants
################################################################################
SUBJECT_BLACKLIST = ["", "blog", "plantillas"]
BASE_URL = "http://proyectodescartes.org/descartescms/{}"
MAIN_PAGE_HREF= "/descartescms/"
AGE_RANGE = {
    "10-13 años": ["10 a 11 años", "10 a 12 años", "11 a 12 años", "12 a 13 años"],
    "13-14 años": ["13 a 14 años"],
    "14-15 años": ["14 a 15 años"],
    "15-16 años": ["15 a 16 años"],
    "16-17 años": ["16 a 17 años"],
    "17-18 años": ["17 a 18 años"],
    "18+ años": ["18 años o más"],
}


# The chef subclass
################################################################################
class MyChef(SushiChef):
    """
    This class uploads the Proyecto Descartes channel to Kolibri Studio.
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

        # Parse the index page to get the topics
        resp = downloader.make_request("http://proyectodescartes.org/descartescms/")
        soup = BeautifulSoup(resp.content, "html.parser")
        topics = soup.find_all("a", "item")
        final_topics = self.parse_topics(topics, channel)

        for topic in final_topics:
            self.download_subject(topic[0], topic[1], topic[2])

        raise_for_invalid_channel(channel)  # Check for errors in channel construction

        return channel


    def parse_topics(self, topics, channel):
        """
        Parse the topics on the site.
        """
        final_topics = []
        main_topics = []
        
        for topic in topics:
            href = topic["href"].split(MAIN_PAGE_HREF)
            subject = href[-1].split("/")[0]

            if subject in SUBJECT_BLACKLIST:
                continue
            
            # Get subject information for the topic
            subjectLink = BASE_URL.format(href[-1])
            subjectTitle = topic.text.strip()
            subject_topic = TopicNode(source_id=subjectTitle, title=subjectTitle)

            # When the topic is a subtopic of another
            if topic.parent.parent.attrs["class"][0] == "l2":
                parent = main_topics[-1]
            else:
                parent = channel
                main_topics.append(subject_topic)

            topic_tuple = (subject_topic, subjectLink, parent)
            final_topics.append(topic_tuple)

        return final_topics


    def download_subject(self, subject, link, parent):
        """
        Parse each subject page.
        """
        LOGGER.info("Processing subject: {}".format(subject.title))

        # No need to parse the content under the subject when link is not valid
        if "javascript:void(0);" in link:
            parent.add_child(subject)
            return

        # Parse each subject's index page
        resp = downloader.make_request(link)
        soup = BeautifulSoup(resp.content, "html.parser")

        selected_category = soup.find("option", {"class": "level0", "selected": "selected"})
        if not selected_category:
            return

        parent.add_child(subject)

        for item in AGE_RANGE.keys():
            params = OrderedDict([
                ("category", selected_category["value"]),
                ("moduleId", "282"),
                ("format", "count")
            ])
            for index in range(len(AGE_RANGE[item])):
                params["taga[{}]".format(index)] = AGE_RANGE[item][index]

            # Parse the topics of age range under each subject
            resp = downloader.make_request("{}/itemlist/filter".format(link), params=params)
            count = int(resp.text.split('\n')[0])
            if count == 0:
                continue

            LOGGER.info("Processing topic: {}".format(item))
            age_topic = TopicNode(source_id=item, title=item)
            subject.add_child(age_topic)
            total_pages = ceil(count/20)

            for i in range(total_pages):
                page_params = OrderedDict(params)
                LOGGER.info("Processing page: {}".format(i))
                self.download_content(age_topic, link, page_params, selected_category["value"], i*20)


    def download_content(self, parent, link, params, selected_category, start):
        """
        Parse each content page.
        """
        params["start"] = start
        params.pop("format")

        # Parse each page of the result
        resp = downloader.make_request("{}/itemlist/filter".format(link), params=params)
        soup = BeautifulSoup(resp.content, "html.parser")

        # Find the all the content in each page
        for item in soup.find("tbody").find_all("a"):
            content_url = "http://proyectodescartes.org{}".format(item["href"])
            title = item.text.strip()
            source_id = item["href"].split("/")[-1]

            # Parse each content's page
            response = downloader.make_request(content_url)
            page = BeautifulSoup(response.content, "html.parser")

            thumbnail_url = "http://proyectodescartes.org{}".format(
                page.find("div", class_="itemFullText").find("img")["src"])
            author = self.get_content_author(page)
            zip_path = self.get_content_zip(page)
            if not zip_path:
                LOGGER.info("The url for the zip file does not exist in this page: {}".format(content_url))
                continue

            content_node = HTML5AppNode(
                source_id=source_id,
                title=title,
                license=CC_BY_NC_SALicense(copyright_holder="Proyecto Descartes"),
                language=CHANNEL_LANGUAGE,
                files=[files.HTMLZipFile(zip_path)],
                author=author,
                thumbnail=thumbnail_url,
            )

            parent.add_child(content_node)


    def get_content_author(self, page):
        """
        Get the author name in each content page.
        """
        # On the site, the author section is indicated in three different ways.
        autoria_tag = page.find(string="Autoría")
        autores_tag = page.find(string="Autores")
        autor_tag = page.find(string="Autor")

        if autoria_tag:
            author = str(page.find(string="Autoría").parent.parent).split(
                "Autoría</strong>:")[-1].split("<")[0].strip()
        elif autores_tag:
            author = str(page.find(string="Autores").parent.parent).split(
                "Autores</strong>:")[-1].split("<")[0].strip()
        elif autor_tag:
            author = str(page.find(string="Autor").parent.parent).split(
                "Autores</strong>:")[-1].split("<")[0].strip()
        else:
            author = ""

        return author


    def get_content_zip(self, page):
        """
        Get the zip path of the content.
        """
        # Find the zip url of the content and check if it's valid.
        zip_href = page.find("a", href=re.compile(".zip"))
        if not zip_href:
            return None
        zip_url = "http://proyectodescartes.org{}".format(zip_href["href"])
        zip_resp = downloader.make_request(zip_url)

        if zip_resp.status_code != 200:
            return None

        filepath = "/tmp/{}".format(zip_url.split("/")[-1])
        with open(filepath, "wb") as f:
            f.write(zip_resp.content)

        dst = tempfile.mkdtemp()
        html_name = page.find(
            "div", class_="itemFullText").find("a")["href"].split("/")[-1]

        # Unzip the downloaded zip file and zip the folder again. In case that
        # index.html does not exist on the top most level, rename the index page 
        # in the folder to index.html before zipping the folder again.
        with zipfile.ZipFile(filepath) as zf:
            extracted_src = unquote(filepath.split("/")[-1].split(".zip")[0])
            zf.extractall(dst)
            if html_name != "index.html":
                src_index = os.path.join(dst, extracted_src, html_name)
                dst_index = src_index.replace(html_name, "index.html")
                if os.path.exists(src_index):
                    os.rename(src_index, dst_index) 
            zip_path = create_predictable_zip(os.path.join(dst, extracted_src))

        return zip_path


# CLI
################################################################################
if __name__ == '__main__':
    # This code runs when sushichef.py is called from the command line
    chef = MyChef()
    chef.main()
