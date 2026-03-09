#!/usr/bin/env python
import json
import os
import requests
import sys
sys.path.append(os.getcwd()) # Handle relative imports
from utils import html, logger, downloader
from ricecooker.chefs import SushiChef
from ricecooker.classes import nodes, files, questions, licenses
from ricecooker.config import LOGGER
from ricecooker.exceptions import raise_for_invalid_channel
from le_utils.constants import licenses, exercises, content_kinds, file_formats, format_presets, languages


""" Additional imports """
###########################################################
from requests.exceptions import HTTPError
from bs4 import BeautifulSoup
from client import Client
from multiprocessing.pool import ThreadPool

""" Run Constants"""
###########################################################

CHANNEL_NAME = "Saylor Academy"              # Name of channel
CHANNEL_SOURCE_ID = "sushi-chef-saylor"      # Channel's unique id
CHANNEL_DOMAIN = "jordan@learningequality.org"                   # Who is providing the content
CHANNEL_LANGUAGE = "en"      # Language of channel
CHANNEL_DESCRIPTION = None                                  # Description of the channel (optional)
CHANNEL_THUMBNAIL = "https://pbs.twimg.com/profile_images/879739713418141696/MMpYQqmT.jpg" # Local path or url to image file (optional)


""" Additional Constants """
###########################################################
BASE_URL = "https://www.saylor.org/books/"
COPYRIGHT_HOLDER = "Saylor Academy"
LICENSE = licenses.CC_BY_NC_SA

DOWNLOAD_DIRECTORY = "{}{}{}".format(os.path.dirname(os.path.realpath(__file__)), os.path.sep, "downloads")
if not os.path.exists(DOWNLOAD_DIRECTORY):
    os.makedirs(DOWNLOAD_DIRECTORY)

SHARED_DIRECTORY = "{}{}{}".format(os.path.dirname(os.path.realpath(__file__)), os.path.sep, "shared")
if not os.path.exists(SHARED_DIRECTORY):
    os.makedirs(SHARED_DIRECTORY)
MATHJAX_URL = "mathjax"

# Videos tend to load unreliably, so use json to track links to avoid having to load every time
VIDEO_MAP_JSON = "videos.json"
VIDEO_MAPPING = {}
if not os.path.isfile(VIDEO_MAP_JSON):
    with open(VIDEO_MAP_JSON, "wb") as videojson:
        videojson.write(b"{}")

with open(VIDEO_MAP_JSON, "rb") as videojson:
    VIDEO_MAPPING = json.load(videojson)


""" The chef class that takes care of uploading channel to the content curation server. """
class MyChef(SushiChef):

    channel_info = {                                   # Channel Metadata
        'CHANNEL_SOURCE_DOMAIN': CHANNEL_DOMAIN,       # Who is providing the content
        'CHANNEL_SOURCE_ID': CHANNEL_SOURCE_ID,        # Channel's unique id
        'CHANNEL_TITLE': CHANNEL_NAME,                 # Name of channel
        'CHANNEL_LANGUAGE': CHANNEL_LANGUAGE,          # Language of channel
        'CHANNEL_THUMBNAIL': CHANNEL_THUMBNAIL,      # Local path or url to image file (optional)
        'CHANNEL_DESCRIPTION': CHANNEL_DESCRIPTION,      # Description of the channel (optional)
    }


    """ Main scraping method """
    ###########################################################

    def construct_channel(self, *args, **kwargs):
        """ construct_channel: Creates ChannelNode and build topic tree
            Returns: ChannelNode
        """
        channel = self.get_channel(*args, **kwargs)   # Creates ChannelNode from data in self.channel_info

        scrape_page(channel)

        raise_for_invalid_channel(channel)            # Check for errors in channel construction

        return channel


""" Helper Methods """
###########################################################
def generate_id(text):
    """ Generate source_id based on text """
    return "".join(c for c in text.lower().replace(' ', '-') if c.isalnum() or c == '-')[:200]

def read_source(base, endpoint=None, loadjs=False):
    """ Read url """
    if base.count('http://') > 1: # Special case: http://web.archive.org/web/.../http://2012books.lardbucket.org/books/...
        return downloader.read("http://{}".format(base.split('http://')[-1]), loadjs=loadjs)
    elif not endpoint:
        return downloader.read(base, loadjs=loadjs)
    elif endpoint.startswith('http'):
        return downloader.read(endpoint, loadjs=loadjs)
    elif endpoint.startswith('/'):
        return downloader.read(os.path.dirname(base) + endpoint.lstrip('/'), loadjs=loadjs)
    else:
        return downloader.read(os.path.dirname(base).rstrip("/") + "/" + endpoint, loadjs=loadjs)

def write_to_shared_library_or_zip(main_url, zipper, endpoint=None, directory="files", filename=None):
    """ Write any shared files to library """
    filename = filename or os.path.basename(endpoint)

    # Files shared across pages start with "shared"
    if endpoint and endpoint.startswith("shared"):
        filepath = "{}{}{}".format(SHARED_DIRECTORY, os.path.sep, filename)
        if not os.path.isfile(filepath):
            with open(filepath, 'wb') as fobj:
                fobj.write(read_source(main_url, endpoint=endpoint))
        return "shared/" + filename
    elif endpoint:
        return zipper.write_url(main_url + endpoint, filename, directory=directory)
    else:
        return zipper.write_url(main_url, filename, directory=directory)


def write_shared_library_to_zip(zipper):
    """ Write all shared files to the zip """
    # Automatically write shared files to zip
    for dirpath,dirs,files in os.walk(SHARED_DIRECTORY):
        for f in files:
            zipper.write_file(os.path.join(dirpath, f), directory="shared")

    # Automatically write mathjax to zip
    for dirpath,dirs,files in os.walk(MATHJAX_URL):
        for f in files:
            zipper.write_file(os.path.join(dirpath, f), directory="shared")


def scrape_page(channel):
    """ Read main page for Saylor (https://www.saylor.org/books/) """
    try:
        page = BeautifulSoup(read_source(BASE_URL, loadjs=True), 'html.parser')
        contents = page.find('div', {'class': 'main-content'}).find('div', {'class', 'row'})

        # Site doesn't have special designation for subjects, so get headers
        for subject in contents.find_all('h3'):

            # Create subject topic
            title = subject.text.replace(u'\xa0', u' ').replace('\n', '')
            source_id = generate_id(title)
            category_topic = nodes.TopicNode(source_id=source_id, title=title)
            channel.add_child(category_topic)
            LOGGER.info(title)

            # Get list from subject
            book_list = subject.findNext('ul')
            for book in book_list.find_all('li'):
                license = LICENSE
                page_links = []

                # Some books have subsections for different formats/licenses
                # e.g. See Business-General/Miscellaneous > Information Systems for Business and Beyond
                if book.find('small'):
                    # Determine what license to use
                    for l in licenses.choices:
                        if l[0] in book.find('small').text:
                            license = l[0]
                            break
                    booktitle = book.contents[0]
                    LOGGER.info("    " + booktitle)
                    # Download one of the sublinks
                    for sublink in book.find_all('a'):
                        if not sublink.get('href'):
                            continue
                        elif "PDF" in sublink.text:
                            category_topic.add_child(nodes.DocumentNode(
                                source_id=source_id + os.path.basename(sublink['href']),
                                title=booktitle,
                                license=license,
                                copyright_holder=COPYRIGHT_HOLDER,
                                files=[files.DocumentFile(path=sublink['href'])]
                            ))
                            break # only need to download one format of the book
                        elif "HTML" in sublink.text:
                            html_node = scrape_book(sublink['href'], license=license)
                            if html_node:
                                category_topic.add_child(html_node)
                                break # only need to download one format of the book

                # Most book links go straight to an html page
                else:
                    page_links.append(book.find('a')['href'])
                    html_node = scrape_book(book.find('a')['href'], license)
                    if html_node:
                        category_topic.add_child(html_node)
    finally:
        # No matter what, add link to video mapping for future runs
        with open(VIDEO_MAP_JSON, "w") as videojson:
            json.dump(VIDEO_MAPPING, videojson)

def scrape_book(url, license):
    """ Scrape book and return html node
        e.g. https://saylordotorg.github.io/text_financial-accounting/
    """
    page = BeautifulSoup(read_source(url), 'html.parser')

    if not page.find('div', {'id': 'book-content'}): # Skip books that link to other websites
        return

    # Get fields for new html node
    title = page.find('h1').text.replace(u'\xa0', u' ').replace('\n', '')
    source_id = generate_id(title)
    write_to_path = "{}{}{}.zip".format(DOWNLOAD_DIRECTORY, os.path.sep, source_id)
    LOGGER.info("    " + title)

    # Write to html zip
    # if not os.path.isfile(write_to_path):
    with html.HTMLWriter(write_to_path) as zipper:
        # Parse table of contents
        contents = BeautifulSoup(read_source(url), 'html.parser')
        parse_page_links(url, contents, zipper)

        # Parse all links in the table of contents
        for link in contents.find_all('a'):
            if link.get('href'):
                # Get page content and write to zip
                chapter_contents = BeautifulSoup(read_source(url, endpoint=link['href']), 'html.parser')
                parse_page_links(url, chapter_contents, zipper, link['href'])
                zipper.write_contents(link['href'], chapter_contents.prettify())

        # Write main index.html file and all shared files
        zipper.write_index_contents(contents.prettify())
        write_shared_library_to_zip(zipper)

    return nodes.HTML5AppNode(
        source_id=source_id,
        title=title,
        license=license,
        copyright_holder=COPYRIGHT_HOLDER,
        files=[files.HTMLZipFile(path=write_to_path)]
    )

def parse_page_links(main_url, contents, zipper, endpoint=None):
    """ Parse any links """
    try:
        # Add scripts to shared library or zip
        for script in contents.find_all('script', {'type': 'text/javascript'}):
            if script.get('src'):
                if "mathjax" in script['src']: # Copy mathjax into folder
                    filename = os.path.basename(script['src']).split("?")
                    script['src'] = "shared/MathJax.js{}".format("?" + filename[1] if len(filename) > 1 else "")
                else:
                    script['src'] = write_to_shared_library_or_zip(main_url, zipper, endpoint=script['src'])

        # Add stylesheets to shared library or zip
        for link in contents.find_all('link'):
            if link.get('href'):
                link['href'] = write_to_shared_library_or_zip(main_url, zipper, endpoint=link['href'])

        # Add images to shared library or zip
        for img in contents.find_all('img'):
            try:
                img['src'] = write_to_shared_library_or_zip(main_url, zipper, directory="img", endpoint=img['src'])
            except HTTPError as e:
                img.decompose()
                LOGGER.error("IMAGE ERROR: {} ({}{})".format(str(e), main_url, endpoint))

        # Add videos to zip (skip videos that throw error)
        for video in contents.find_all('div', {'class': 'video'}):
            parse_video(video, zipper, endpoint=endpoint) # Path to downloaded file is set in parse_video

        # Parse page links
        for link in contents.find_all('a'):
            try:
                parse_link(link)
            except Exception as e:
                LOGGER.error("LINK ERROR: {} ({}{})".format(str(e), main_url, endpoint))


        # Set custom styling
        new_style_soup = BeautifulSoup("<b></b>", 'html.parser');
        style_tag = new_style_soup.new_tag("style");
        style_tag.string = generate_styles();
        contents.head.append(style_tag);

        # Set glossary tooltip script
        script_tag = new_style_soup.new_tag("script");
        script_tag.string = generate_gloss_script();
        contents.body.append(script_tag);

    except requests.exceptions.ConnectionError as e:
        LOGGER.error("ERROR: {}".format(str(e)))

    except Exception as e:
        import pdb; pdb.set_trace()
        print(str(e))


def generate_styles():
    """ Create custom style rules """
    # Set navbar so it's always at the top
    css_string = "#navbar-top{background-color: white; z-index: 100;}"

    # Set glossdef tip
    css_string += "a.tip{text-decoration:none; font-weight:bold; cursor:pointer; color:#2196F3;}"
    css_string += "a.tip:hover{position: relative;border-bottom: 1px dashed #2196F3;}"

    # Set glossdef span
    css_string += "a.tip span{display: none;background-color: white;font-weight: normal;border:1px solid gray;width: 250px;}"
    css_string += "a.tip:hover span{display: block;position: absolute;z-index: 100;padding: 5px 15px;}"
    return css_string

def generate_gloss_script():
    """ Create script for glossary to ensure glossary definitions don't go off the page """
    script_string = "var elements = document.getElementsByClassName('tip');";
    script_string += "var maxRight = document.getElementById('book-content').getBoundingClientRect().right;";
    script_string += "for(var i = 0; i < elements.length; i++)";
    script_string +=    "(elements[i].getBoundingClientRect().right + 250 >= maxRight)?";
    script_string +=        "elements[i].firstElementChild.style.right = '0px':";
    script_string +=        "elements[i].firstElementChild.style.left = '0px';";
    return script_string;


def parse_video(video, zipper, endpoint):
    """ Parse videos and embed them directly in the page """
    try:
        video_link = video.find('a')
        video_frame = video_link and video_link.get('data-iframe-code')
        width = None
        height = None
        src = None

        # Some videos are embedded from another page, others are directly on the page
        # e.g. https://saylordotorg.github.io/text_financial-accounting/s04-00-why-is-financial-accounting-im.html
        if video_frame:
            video_soup = BeautifulSoup(video_frame, 'html.parser').contents[0]
            width = video_soup.get('width')
            height = video_soup.get('height')
            src = video_soup.get('src')

        # Create soup to replace iframe with video tag
        new_video_soup = BeautifulSoup("<b></b>", 'html.parser')
        new_tag = new_video_soup.new_tag("video", controls=True)

        if src:
            # See if video link has been recorded already
            video_bin = VIDEO_MAPPING.get(src)

            # Try to download the video (sometimes fails to load)
            video_bin = None
            tries = 10
            while video_bin == None and tries > 0:
                tries -= 1
                video_bin = BeautifulSoup(read_source(src, loadjs=True), 'html.parser').find('a')
                if video_bin:
                    video_bin = video_bin['href']

        # Delete any video tags that failed to download
        if not video_bin:
            video.decompose()
            return

        # Set mapping for faster future runs
        VIDEO_MAPPING[src] = video_bin

        # Generate a unique video name to avoid overwriting in the zip file
        video_name = os.path.basename(video_bin) + ".mp4"

        # Video urls are set to a .bin file, but only need the file.mp4 file
        video_url = video_bin.replace(".bin", "/file.mp4")

        # Create new video tag and download to zip
        new_source_soup = BeautifulSoup("<b></b>", 'html.parser')
        video_path = write_to_shared_library_or_zip(video_url, zipper, directory="videos", filename=video_name)
        source_tag = new_source_soup.new_tag("source", type='video/mp4', src=video_path)
        new_tag.append(source_tag)

        # Set the width and height if provided
        if width:
            new_tag['width'] = width
        if height:
            new_tag['height'] = height

        video_link.replaceWith(new_tag)

    except Exception as e:
        LOGGER.error("VIDEO ERROR: {} (parsing {})".format(str(e), endpoint))

def parse_link(link):
    """ Parse <a> links """
    page_path = os.path.basename(link.get('href') or "")

    # Fix the glossterms so that the description shows up correctly on hover (broken on site)
    if link.get("class") and "glossterm" in link.get("class"):
        definition = link.findNext('span', {'class': "glossdef"})

        # Set glossterm as a tip with the glossdef as a span
        # e.g. <a class='tip'>Word<span>Definition of the word</span></a>
        link['class'] = "tip"
        new_gloss_soup = BeautifulSoup("<b></b>", 'html.parser')
        def_tag = new_gloss_soup.new_tag("span")
        def_tag.string = definition.text
        link.append(def_tag)
        definition.decompose() # Remove old glossdef

    # Keep urls to jump around page
    elif not link.get('href') or link['href'].startswith("#"):
        pass

    # Remove xref links that jump to other chapters (broken on the site)
    # e.g. https://saylordotorg.github.io/text_financial-accounting/s04-why-is-financial-accounting-im.html
    #      has broken link "Chapter 16 "In a Set of Financial Statements, What Information Is Conveyed about Shareholders' Equity?""
    elif link.get("class") and "xref" in link.get("class"):
        del link['href']

    # Don't keep external links (but keep images if there are images)
    elif link['href'].startswith('http'):
        del link['href']
        if not link.find('img'):
            link.string = link.text  + " (Link not available)"


""" This code will run when the sushi chef is called from the command line. """
if __name__ == '__main__':
    chef = MyChef()
    chef.main()
