#!/usr/bin/env python3

import os
import zipfile
import argparse
import uuid
import tempfile

from ricecooker.chefs import SushiChef
from ricecooker.classes.nodes import ChannelNode, TopicNode, DocumentNode
from ricecooker.classes.files import DocumentFile
from le_utils.constants import licenses
from ricecooker.classes.licenses import get_license
from ricecooker.config import LOGGER
from ricecooker.utils.html import WebDriver
from ricecooker.utils import downloader
from le_utils.constants.languages import getlang_by_name

# Variables
FILTERS_URL = "https://storyweaver.org.in/api/v1/books/filters"
SIGNIN_URL = "https://storyweaver.org.in/api/v1/users/sign_in"
BOOK_SEARCH_URL = "https://storyweaver.org.in/api/v1/books-search"
DOWNLOAD_URL = "https://storyweaver.org.in/v0/stories/download-story/{}.pdf"


def get_AS_booklist_dict():
    """
    Get a list of all books on the African Storybooks website to later compare
    with the books on the StoryWeaver website with African Storybooks publisher.
    """
    with WebDriver("http://www.africanstorybook.org/", delay=20000) as driver:

        js_code = """
            var textElement = document.createElement("textarea");
            function decodeHtml(html) {
                textElement.innerHTML = html;
                return textElement.value;
            }

            // Safely decode HTML entities in title field.
            for (var i = bookItems.length - 1; i >= 0; i--) {
                bookItems[i].title = decodeHtml(bookItems[i].title);
            }

            return bookItems;
        """

        books = driver.execute_script(js_code)
        names = []
        # Create a list of book names
        for book in books:
            names.append(book["title"].lower())
        dictionary = {}
        # Create a dictionary of books with name as key
        for (name, book) in zip(names, books):
            if name in dictionary:
                dictionary[name].append(book)
            else:
                dictionary[name] = [book]
        return dictionary


def get_books_from_results(books):
    """
    Get detailed information about each book.
    Parameters:
    * books - The list of books to get detailed information
    """
    booklist = []
    # Loop through all the books for one page
    for i in range(len(books)):
        publisher = books[i]["publisher"]["name"]
        language = books[i]["language"]
        level = books[i]["level"]
        try:
            thumbnail = books[i]["coverImage"]["sizes"][0]["url"]
        except TypeError:
            thumbnail = None

        book_dict = {
            "link": DOWNLOAD_URL.format(books[i]["slug"]),
            "source_id": books[i]["id"],
            "title": books[i]["title"],
            "author": ", ".join([item["name"] for item in books[i]["authors"]]),
            "description": books[i]["description"],
            "thumbnail": thumbnail,
            "language": language,
            "level": level,
            "publisher": publisher,
        }
        booklist.append(book_dict)

    return booklist


def books_for_each_category(category):
    """
    Get all the books for every category
    Parameters:
    * category - The name of the category that is related to the books
    """
    LOGGER.info("\tCrawling books for {}......\n".format(category))

    # Get the json file of the page and parse it
    payload = {"page": 1, "per_page": 24, "categories[]": category}
    response = downloader.make_request(
        BOOK_SEARCH_URL, params=payload, clear_cookies=False
    )
    data = response.json()
    total_pages = data["metadata"]["totalPages"]
    LOGGER.info(
        "\tThere are in total {} pages for {}......\n".format(
            total_pages, category
        )
    )

    # List of books for the first page
    booklist = get_books_from_results(data["data"])

    # get the rest of the pages' books
    for i in range(1, total_pages):
        payload["page"] = i + 1
        response = downloader.make_request(
            BOOK_SEARCH_URL, params=payload, clear_cookies=False
        )

        # Skip the page if there is an error (usually a 500 error)
        if response.status_code != 200:
            continue
        data = response.json()
        booklist += get_books_from_results(data["data"])

    LOGGER.info(
        "\tFinished getting all the books for {}\n\t================\n".format(category)
    )
    return booklist


def download_all():
    """
    Parse the json returned by StoryWeaver API and generate a dictionary that
    contains all the information regarding category, publisher, language, level and
    book.
    """
    resp = downloader.make_request(FILTERS_URL, clear_cookies=False).json()
    categories = [item["name"] for item in resp["data"]["category"]["queryValues"]]

    channel_tree = {}
    for category in categories:
        channel_tree[category] = {}
        booklist = books_for_each_category(category)

        # Reset Storyweaver Community number and index for each category
        storyweaver_community_num = 0
        index = 1
        for book in booklist:
            publisher = book["publisher"]
            language = book["language"]
            level = book["level"]

            if publisher == "StoryWeaver Community":
                storyweaver_community_num += 1
                # Make sure we only have 20 books in one Storyweaver Community folder
                if storyweaver_community_num > 20:
                    index += 1
                    storyweaver_community_num = 1
                publisher = "{}-{}".format(publisher, index)

            if publisher in channel_tree[category]:
                if language in channel_tree[category][publisher]:
                    if level in channel_tree[category][publisher][language]:
                        channel_tree[category][publisher][language][level].append(book)
                    else:
                        channel_tree[category][publisher][language][level] = [book]
                else:
                    channel_tree[category][publisher][language] = {}
                    channel_tree[category][publisher][language][level] = [book]
            else:
                channel_tree[category][publisher] = {}
                channel_tree[category][publisher][language] = {}
                channel_tree[category][publisher][language][level] = [book]
    return channel_tree


def parse_through_tree(tree, parent_topic, as_booklist):
    """
    Recursively parsing through the tree and adding TopicNodes and DocumentNodes.
    Parameters:
    * tree - The tree that contains information about category, publisher, language,
            level, and book and is going to be parsed
    * parent_topic - The parent node that will be attached with Nodes created later
    * as_booklist - the list of books from African Storybook
    """
    for topic_name in sorted(tree):
        content = tree[topic_name]
        try:
            title = "Level {}".format(int(topic_name))
        except ValueError:
            title = topic_name
        current_topic = TopicNode(
            source_id="{}_{}".format(
                parent_topic.source_id, topic_name.replace(" ", "_")
            ),
            title=title,
        )

        if type(content) is list:
            add_node_document(content, current_topic, as_booklist)
        else:
            parse_through_tree(content, current_topic, as_booklist)

        # Only add the current topic node when it has child nodes
        if current_topic.children:
            parent_topic.add_child(current_topic)


def check_if_story_in_AS(as_booklist, story_name):
    """
    Check if the story in StoryWeaver is also in African Storybooks.
    Parameters:
    * as_booklist - The list of books from African Storybooks
    * story_name - The book name from StoryWeaver to check if it exists on
                African Storybooks website
    """
    result = as_booklist.get(story_name.lower().rstrip())
    if result and len(result) == 1:
        return True, result[0]["id"]
    else:
        return False, None


def add_node_document(booklist, level_topic, as_booklist):
    """
    Add books as DocumentNode under a specific level of reading.
    Parameters:
    * booklist - The list of books to be added as DocumentNodes
    * level_topic - The TopicNode regarding current level that the DocumentNodes
                    will be attached to
    * as_booklist - The list of books from African Storybooks
    """
    for item in booklist:
        # Initialize the source domain and content_id
        domain = uuid.uuid5(uuid.NAMESPACE_DNS, "storyweaver.org.in")
        book_id = str(item["source_id"])

        # If the publisher is AS and the book is found,
        # then change the source_domain and content_id
        if item["publisher"] == "African Storybook Initiative":
            check = check_if_story_in_AS(as_booklist, item["title"])
            if check[0]:
                domain = uuid.uuid5(uuid.NAMESPACE_DNS, "www.africanstorybook.org")
                book_id = check[1]

        # Given that StoryWeaver provides the link to a zip file,
        # we will download the zip file and extract the pdf file from it
        with tempfile.NamedTemporaryFile(suffix=".zip") as tempf:
            try:
                resp = downloader.make_request(item["link"], clear_cookies=False)
                resp.raise_for_status()
                tempf.write(resp.content)
                tempf.flush()
            except Exception as e:
                # Do not create the node if download fails
                LOGGER.info("Error: {} when downloading {}".format(e, item["link"]))
                continue

            filename = ""
            with zipfile.ZipFile(tempf.name, "r") as f:
                for zipped_file in f.namelist():
                    if os.path.splitext(zipped_file)[1][1:] == "pdf":
                        tempdir = os.path.dirname(tempf.name)
                        f.extract(zipped_file, path=tempdir)
                        filename = os.path.join(tempdir, zipped_file)
                        break

        # If no pdf file has been found in the zip, do not create the node
        if not filename:
            continue

        # Create the document node with given information
        document_file = DocumentFile(path=filename)
        language_obj = getlang_by_name(item["language"])
        book = DocumentNode(
            title=item["title"],
            source_id=book_id,
            author=item["author"],
            provider=item["publisher"],
            files=[document_file],
            license=get_license(licenses.CC_BY, copyright_holder="StoryWeaver"),
            thumbnail=item.get("thumbnail"),
            description=item["description"],
            domain_ns=domain,
            language=language_obj,
        )
        level_topic.add_child(book)


class PrathamBooksStoryWeaverSushiChef(SushiChef):
    """
    Add two additional arguments about login information.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.arg_parser = argparse.ArgumentParser(
            parents=[self.arg_parser],
            description="Sushi Chef for Pratham Books' StoryWeaver.",
        )
        self.arg_parser.add_argument(
            "--login_email",
            required=True,
            help="Login email for Pratham Books' StoryWeaver website.",
        )
        self.arg_parser.add_argument(
            "--login_password",
            required=True,
            help="Login password for Pratham Books' StoryWeaver website.",
        )

    """
    Get the login information and log in to the website.
    """

    def pre_run(self, args, options):
        payload = {
            # "authenticity_token": _authenticity_token,
            "api_v1_user[email]": args["login_email"],
            "api_v1_user[password]": args["login_password"],
            "api_v1_user[remember_me]": "false",
        }
        # Log in to StoryWeaver website
        response = downloader.DOWNLOAD_SESSION.post(SIGNIN_URL, data=payload)
        if response.json()["email"] != args["login_email"]:
            raise Exception(
                "Failed to log in. Please check if there has been an API change from the upstream."
            )

    def get_channel(self, **kwargs):
        # Create a channel
        channel = ChannelNode(
            source_domain="storyweaver.org.in",
            source_id="Pratham_Books_StoryWeaver",
            title="Pratham Books' StoryWeaver",
            description="",
            language="en",
            thumbnail="thumbnail.png",
        )
        return channel

    def construct_channel(self, **kwargs):
        channel = self.get_channel(**kwargs)

        # add topics and corresponding books to the channel
        channel_tree = download_all()
        as_booklist = get_AS_booklist_dict()
        for category in sorted(channel_tree):
            category_topic = TopicNode(
                source_id=category.replace(" ", "_"), title=category
            )
            channel.add_child(category_topic)
            parse_through_tree(channel_tree[category], category_topic, as_booklist)

        return channel


if __name__ == "__main__":

    # This code will run when the sushi chef is called from the command line.
    chef = PrathamBooksStoryWeaverSushiChef()
    chef.main()
