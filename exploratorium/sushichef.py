#!/usr/bin/env python
import os
import sys
from ricecooker.utils import downloader, html_writer
from ricecooker.chefs import SushiChef
from ricecooker.classes import nodes, files, questions
from ricecooker.config import LOGGER              # Use LOGGER to print messages
from ricecooker.exceptions import raise_for_invalid_channel
from le_utils.constants import exercises, content_kinds, file_formats, format_presets, languages, licenses

import cssutils
import requests
import youtube_dl
from bs4 import BeautifulSoup
from io import BytesIO
from PIL import Image

import logging
cssutils.log.setLevel(logging.CRITICAL)


# Run constants
################################################################################
CHANNEL_NAME = "Exploratorium"              # Name of channel
CHANNEL_SOURCE_ID = "sushi-chef-exploratorium"    # Channel's unique id
CHANNEL_DOMAIN = "www.exploratorium.edu"          # Who is providing the content
CHANNEL_LANGUAGE = "en"      # Language of channel
CHANNEL_DESCRIPTION = "Science tools and experiences helping " + \
                    "students become active explorers: hundreds of " + \
                    "explore-for-yourself exhibits, activities, " + \
                    "videos, and much more. Appropriate for all " + \
                    "ages of students, as supplementary, hands-on " + \
                    "demonstration of scientific principles."
CHANNEL_THUMBNAIL = "http://wtxec.org/exploratorium_tm.jpg" # Local path or url to image file (optional)


# Additional constants
################################################################################
COPYRIGHT_HOLDER = "Exploratorium Teacher Institute"
LICENSE = licenses.CC_BY_NC_SA
BASE_URL = "https://www.exploratorium.edu/{}"
SNACK_URL = "https://www.exploratorium.edu/snacks/snacks-by-subject"
VIDEO_URL = "https://www.exploratorium.edu/video/subjects"
BRIGHTCOVE_URL = "http://players.brightcove.net/{account}/{player}_default/index.html?videoId={videoid}"
IMAGE_EXTENSIONS = ['jpeg', 'jpg', 'gif', 'png', 'svg']
DOWNLOAD_ATTEMPTS = 25

# Directory to download snacks (html zips) into
SNACK_DIRECTORY = "{}{}{}".format(os.path.dirname(os.path.realpath(__file__)), os.path.sep, "snacks")
if not os.path.exists(SNACK_DIRECTORY):
    os.makedirs(SNACK_DIRECTORY)

# Directory to download videos into
VIDEO_DIRECTORY = "{}{}{}".format(os.path.dirname(os.path.realpath(__file__)), os.path.sep, "videos")
if not os.path.exists(VIDEO_DIRECTORY):
    os.makedirs(VIDEO_DIRECTORY)

# Directory to download shared assets (e.g. pngs, gifs, svgs) from stylesheets into
SHARED_ASSET_DIRECTORY = os.path.sep.join([SNACK_DIRECTORY, "shared-assets"])
if not os.path.exists(SHARED_ASSET_DIRECTORY):
    os.makedirs(SHARED_ASSET_DIRECTORY)


# The chef subclass
################################################################################
class MyChef(SushiChef):
    """
    This class uploads the Exploratorium channel to Kolibri Studio.
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

        Channel structure:
            Activities
                Subject
                    Subdirectory (if any)
                        Activity.zip
            Videos
                Subject
                    Collection
                        Video.mp4
        """
        channel = self.get_channel(*args, **kwargs)  # Create ChannelNode from data in self.channel_info

        channel.add_child(scrape_snack_menu(SNACK_URL))
        channel.add_child(scrape_video_menu(VIDEO_URL))

        raise_for_invalid_channel(channel)  # Check for errors in channel construction

        return channel

def read(url):
    """ Read contents from url
        Args:
            url (str): url to read
        Returns contents from url
    """
    return downloader.read(format_url(url))


def format_url(url):
    """ Format relative urls to be absolute urls
        Args:
            url (str): url to format
        Returns absolute url (str)
    """
    if url.startswith('http'):
        return url
    return BASE_URL.format(url.lstrip('/'))


def get_next_page_url(contents):
    """ Get link to next page
        Args:
            contents (BeautifulSoup): page contents to search for next page
        Returns link to next page (str)
    """
    next_link = contents.find('li', {'class': 'pager-next'})
    if next_link:
        return next_link.find('a')['href']


def get_thumbnail_url(url):
    """ Get thumbnail, converting gifs to pngs if necessary
        Args:
            url (str): thumbnail url
        Returns link to next page (str)
    """
    url = url.split("?")[0].rstrip("%20")

    # Convert gifs to pngs
    if url.endswith('.gif'):
        imgfile = BytesIO(read(url))
        url = os.path.sep.join([SNACK_DIRECTORY, url.split("/")[-1].replace('gif', 'png')])
        with Image.open(imgfile) as img:
            img.save(url,'png', optimize=True, quality=70)
    return url or None


def get_brightcove_mapping(contents, get_playlist=False):
    """ Scrape contents for brightcove videos
        Args:
            contents (BeautifulSoup): page contents
            get_playlist (bool): determines whether or not to scrape for playlists too
        Returns mapping of brightcove urls and data
    """
    brightcove_mapping = {}
    account = "" # Store account number as it isn't stored on playlist video elements

    # Get main videos
    for video in contents.find_all('video', {'class': 'bc5player'}):
        account = video['data-account']
        attribution = contents.find('div', {'class': 'attribution'})
        brightcove_mapping.update({video['data-video-id']: {
            "original_el": video,
            "author": attribution and attribution.text,
            "url": BRIGHTCOVE_URL.format(account=video['data-account'],
                                        player=video['data-player'],
                                        videoid=video['data-video-id'])
        }})

    # Add videos from brightcove playlists
    playlist = contents.find('div', {'id': 'media-collection-banner-playlist'})
    if get_playlist and playlist:
        for video in playlist.find_all('div', {'class': 'playlist-item'}):
            brightcove_mapping.update({video['data-id']: {
                "title": video['data-title'],
                "append_to": playlist,
                "url": BRIGHTCOVE_URL.format(account=account,
                                            player=video['data-pid'],
                                            videoid=video['data-id']),
            }})

    return brightcove_mapping



# Video scraping functions
################################################################################
def scrape_video_menu(url):
    """ Scrape videos from url
        Args:
            url (str): url to scrape from (e.g. https://www.exploratorium.edu/video/subjects)
        Returns TopicNode containing all videos
    """
    LOGGER.info("SCRAPING VIDEOS...")
    video_topic = nodes.TopicNode(title="Videos", source_id="main-topic-videos")
    contents = BeautifulSoup(read(url), 'html5lib')

    for subject in contents.find_all('div', {'class': 'subject'}):
        title = subject.find('div', {'class': 'name'}).text.strip().replace("’", "'")
        LOGGER.info("    {}".format(title))
        topic = nodes.TopicNode(
            title=title,
            source_id="videos-{}".format(title),
            thumbnail=get_thumbnail_url(subject.find('img')['src']),
        )
        video_topic.add_child(topic)
        scrape_video_subject(subject.find('a')['href'], topic)

    return video_topic


def scrape_video_subject(url, topic):
    """ Scrape collections under video subject and add to the topic node
        Args:
            url (str): url to subject page (e.g. https://www.exploratorium.edu/search/video?f[0]=field_activity_subject%3A565)
            topic (TopicNode): topic to add collection nodes to
    """
    contents = BeautifulSoup(read(url), 'html5lib')
    sidebar = contents.find("div", {"id": "filter_content"}).find("div", {"class": "content"})
    for collection in sidebar.find_all("li"):
        title = collection.find('span').text.replace('filter', '').replace("Apply", "").strip().replace("’", "'")
        LOGGER.info("        {}".format(title))
        collection_topic = nodes.TopicNode(title=title, source_id="videos-collection-{}".format(title))
        topic.add_child(collection_topic)
        scrape_video_collection(collection.find('a')['href'], collection_topic)


def scrape_video_collection(url, topic):
    """ Scrape videos under video collection and add to the topic node
        Args:
            url (str): url to video page (e.g. https://www.exploratorium.edu/video/inflatable-jimmy-kuehnle)
            topic (TopicNode): topic to add video nodes to
    """
    try:
        collection_contents = BeautifulSoup(read(url), 'html5lib')
        for result in collection_contents.find_all('div', {'class': 'search-result'}):
            header = result.find('div', {'class': 'views-field-field-html-title'})
            LOGGER.info("            {}".format(header.text.strip()))

            # Get video from given url
            description = result.find('div', {'class': 'search-description'})
            video_contents = BeautifulSoup(read(header.find('a')['href']), 'html.parser')
            for k, v in get_brightcove_mapping(video_contents).items():
                video_node = nodes.VideoNode(
                    source_id = k,
                    title = header.text.strip().replace("’", "'"),
                    description = description.text.strip() if description else "",
                    license = LICENSE,
                    copyright_holder = COPYRIGHT_HOLDER,
                    author = v.get('author') or "",
                    files = [files.WebVideoFile(v['url'], high_resolution=False)],
                    thumbnail = get_thumbnail_url(result.find('img')['src']),
                )

                # If video doesn't already exist here, add to topic
                if not next((c for c in topic.children if c.source_id == video_node.source_id), None):
                    topic.add_child(video_node)

        # Scrape next page (if any)
        next_page_url = get_next_page_url(collection_contents)
        if next_page_url:
            scrape_video_collection(next_page_url, topic)

    except requests.exceptions.HTTPError:
        LOGGER.error("Could not read collection at {}".format(url))




# Activity scraping functions
################################################################################
def scrape_snack_menu(url):
    """ Scrape snacks (activities) from  url
        Args:
            url (str): url to scrape from (e.g. https://www.exploratorium.edu/snacks/snacks-by-subject)
        Returns TopicNode containing all snacks
    """
    LOGGER.info("SCRAPING ACTIVITIES...")
    snack_topic = nodes.TopicNode(title="Activities", source_id="main-topic-activities")
    contents = BeautifulSoup(read(url), 'html5lib')

    # Get #main-content-container .field-items
    contents = contents.find('div', {'id': 'main-content-container'})\
                    .find('div', {'class': 'field-items'})

    for column in contents.find_all('ul', {'class': 'menu'}):
        # Skip nested .menu list items (captured in subdirectory)
        if column.parent.name == 'li':
            continue

        # Go through top-level li elements
        for li in column.find_all('li', recursive=False):
            link = li.find('a')
            LOGGER.info("    {}".format(link['title']))
            topic = nodes.TopicNode(title=link['title'].replace("’", "'"), source_id=link['href'])
            snack_topic.add_child(topic)

            # Scrape subcategories (if any)
            if li.find('ul'):
                for sublink in li.find('ul').find_all('a'):
                    LOGGER.info("    > {}".format(sublink['title']))
                    subtopic = nodes.TopicNode(title=sublink['title'].replace("’", "'"), source_id=sublink['href'])
                    topic.add_child(subtopic)
                    scrape_snack_subject(sublink['href'], subtopic)
            else:
                scrape_snack_subject(link['href'], topic)

    return snack_topic


def scrape_snack_subject(slug, topic):
    """ Scrape snack subject page
        Args:
            slug (str): url slug to scrape from (e.g. /subject/arts)
            topic (TopicNode): topic to add html nodes to
    """
    contents = BeautifulSoup(read(slug), 'html5lib')

    for activity in contents.find_all('div', {'class': 'activity'}):
        LOGGER.info("        {}".format(activity.find('h5').text.strip()))
        # Scrape snack pages into zips
        write_to_path, tags = scrape_snack_page(activity.find('a')['href'])
        if not write_to_path:
            continue

        # Create html node
        description = activity.find('div', {'class': 'pod-description'})
        topic.add_child(nodes.HTML5AppNode(
            source_id = activity.find('a')['href'],
            title = activity.find('h5').text.strip().replace("’", "'"),
            description = description.text.strip() if description else "",
            license = LICENSE,
            copyright_holder = COPYRIGHT_HOLDER,
            files = [files.HTMLZipFile(path=write_to_path)],
            thumbnail = get_thumbnail_url(activity.find('img')['src']),
            tags=tags,
        ))

    # Scrape next page (if any)
    next_page_url = get_next_page_url(contents)
    if next_page_url:
        scrape_snack_subject(next_page_url, topic)


def scrape_snack_page(slug, attempts=5):
    """ Writes activity to a zipfile
        Args:
            slug (str): url slug (e.g. /snacks/drawing-board)
            attemps (int): number of times to attempt a download
        Returns
            write_to_path (str): path to generated zip
            tags ([str]): list of tags scraped from activity page
    """
    tags = []
    write_to_path = os.path.sep.join([SNACK_DIRECTORY, "{}.zip".format(slug.split('/')[-1])])

    try:
        contents = BeautifulSoup(read(slug), 'html5lib')
        main_contents = contents.find('div', {'class': 'activity'})

        # Gather keywords from page
        tags.extend(scrape_keywords(main_contents, 'field-name-field-activity-subject'))
        tags.extend(scrape_keywords(main_contents, 'field-name-field-activity-tags'))

        # Don't rezip activities that have already been zipped
        if os.path.isfile(write_to_path):
            return write_to_path, tags

        with html_writer.HTMLWriter(write_to_path) as zipper:
            write_contents = BeautifulSoup("", "html5lib")

            # Scrape stylesheets
            for stylesheet in contents.find_all('link', {'rel': 'stylesheet'}):
                # Don't scrape external style sheets (e.g. fontawesome, google fonts)
                if "exploratorium.edu" not in stylesheet['href']:
                    continue
                style_contents = scrape_style(stylesheet['href'], zipper)
                filename = stylesheet['href'].split('/')[-1]
                stylesheet['href'] = zipper.write_contents(filename, style_contents, directory="css")
                write_contents.head.append(stylesheet)

            # Remove scripts and any unneeded sections
            cluster = main_contents.find('div', {'id': 'curated-cluster'})
            cluster and cluster.decompose()
            service_links = main_contents.find('div', {'class': 'activity-service-links'})
            service_links and service_links.decompose()
            for script in main_contents.find_all("script"):
                script.decompose()

            # Get rid of hardcoded height/width on slideshow element
            slideshow = main_contents.find('div', {'class': 'field-slideshow'})
            if slideshow:
                del slideshow['style']

            # Add images
            for img in main_contents.find_all('img'):
                img['src'] = zipper.write_url(format_url(img['src']), img['src'].split('/')[-1], directory="images")

            # Add videos embedded from youtube
            for video in main_contents.find_all('div', {'class': 'yt-player'}):
                yt_video_path = download_web_video(video['data-ytid'], "{}.mp4".format(video['data-ytid']))
                video_tag = generate_video_tag(yt_video_path, zipper)
                video_tag['style'] = video.find('div', {'class': 'placeholder'}).get('style')
                video.replaceWith(video_tag)

            # Add videos embedded from brightcove and remove playlist element (if any)
            for k, v in get_brightcove_mapping(main_contents, get_playlist=True).items():
                video_path = download_web_video(v['url'], "{}.mp4".format(k))
                if v.get('original_el'):
                    v['original_el'].replaceWith(generate_video_tag(video_path, zipper))
                elif v.get('append_to'):
                    if v.get('title'):
                        p_tag = contents.new_tag("p")
                        p_tag.string = v['title']
                        p_tag['style'] = "margin-top: 40px; margin-bottom: 10px"
                        v['append_to'].parent.append(p_tag)
                    v['append_to'].parent.append(generate_video_tag(video_path, zipper))
            playlist = main_contents.find('div', {'id': 'media-collection-banner-playlist'})
            if playlist:
                playlist.decompose()

            # Handle links (need to start with parent as beautifulsoup returns parent as None on links)
            for paragraph in main_contents.find_all('p') + main_contents.find_all('li'):
                for link in paragraph.find_all('a'):
                    # Skip any previously parsed links
                    if zipper.contains(link['href']):
                        continue

                    # Just bold activities and remove link
                    elif "exploratorium.edu/snacks/" in link['href']:
                        bold_tag = contents.new_tag("b")
                        bold_tag.string = link.text
                        link.replaceWith(bold_tag)

                    # If it's an image, replace the tag with just the image
                    elif link.find('img'):
                        link.replaceWith(link.find('img'))

                    # Get downloadable files and attach them to new pages
                    elif "/sites/default/files/" in link['href']:
                        link['href'] = generate_download_page(link['href'], zipper)

                    # Get any referenced videos
                    elif "exploratorium.edu" in link['href']:
                        linked_page = BeautifulSoup(read(link['href']), 'html5lib')
                        link.replaceWith(link.text.replace(link['href'], ''))
                        for k, v in get_brightcove_mapping(linked_page).items():
                            video_path = download_web_video(v['url'], "{}.mp4".format(k))
                            paragraph.append(generate_video_tag(video_path, zipper))

                    # Scrape any images
                    elif next((e for e in IMAGE_EXTENSIONS if link['href'].lower().endswith(e)), None):
                        img_tag = contents.new_tag('img')
                        img_tag['src'] = zipper.write_url(link['href'], link['href'].split('/')[-1], directory="images")
                        img_tag['style'] = "max-width: 100%;"
                        paragraph.append(img_tag)
                        link.replaceWith(link.text)

                    # Remove hyperlink from external links
                    else:
                        if link['href'] not in link.text and link.text not in link['href']:
                            link.string += " ({}) ".format(link['href'])
                        link.replaceWith(link.text)

            # Write contents and custom tags
            write_contents.body.append(main_contents)
            write_contents.head.append(generate_custom_style_tag()) # Add custom style tag
            write_contents.body.append(generate_custom_script_tag()) # Add custom script to handle slideshow

            # Write main index.html file
            zipper.write_index_contents(write_contents.prettify().encode('utf-8-sig'))

    except Exception as e:
        # Reattempt if there are attempts left
        if attempts > 0:
            return scrape_snack_page(slug, attempts=attempts-1)
        else:
            LOGGER.error("Could not scrape {} ({})".format(slug, str(e)))
    return write_to_path, tags


def generate_download_page(url, zipper):
    """ Create a page for files that are meant to be downloaded (e.g. worksheets)
        Args:
            url (str): url to file that is meant to be downloaded
            zipper (html_writer): where to write download page to
        Returns path to page in zipfile (str)
    """
    # Get template soup
    soup = BeautifulSoup("", "html.parser")
    with open('download.html', 'rb') as templatecode:
        newpage = BeautifulSoup(templatecode.read(), 'html5lib')

    # Determine if link is one of the recognized file types
    download_url = url.split("?")[0]
    filename = download_url.split("/")[-1]
    if download_url.endswith('pdf'):
        render_tag = soup.new_tag('embed')
    elif next((e for e in IMAGE_EXTENSIONS if download_url.lower().endswith(e)), None):
        render_tag = soup.new_tag('img')
    else:
        LOGGER.error("Unknown file type found at {}".format(download_url))
        return ""

    # Add tag to new page and write page to zip
    render_tag['src'] = zipper.write_url(format_url(download_url), filename)
    newpage.body.append(render_tag)
    return zipper.write_contents(filename.split('.')[0] + ".html", newpage.prettify())


def generate_video_tag(filepath, zipper):
    """ Downloads video into zip and creates a corresponding <video> tag
        Args:
            filepath (str): path to video to zip
            zipper (html_writer): where to write video to
        Returns <video> tag
    """
    soup = BeautifulSoup("", "html.parser")
    video_tag = soup.new_tag("video")
    source_tag = soup.new_tag("source")
    source_tag['src'] = zipper.write_file(filepath, directory="videos")
    source_tag['type'] = "video/mp4"
    video_tag['controls'] = 'true'
    video_tag['style'] = "width: 100%;"
    video_tag.append(source_tag)
    return video_tag


def generate_custom_style_tag():
    """ Creates a custom style tag with extra css rules to add to zips
        Returns <style> tag
    """
    soup = BeautifulSoup("", "html.parser")
    style_tag = soup.new_tag('style')
    style_tag.string = "body { padding: 50px; }"
    style_tag.string += ".activity {max-width: 900; margin: auto;}"
    style_tag.string += ".underline { text-decoration: underline; }"
    style_tag.string += "b, strong, h1, h3 {font-weight: 700 !important;}"
    style_tag.string += "body, h1, h2, h3, h4, h5, h6, p, table, tr, td, th, ul, li, ol, dd, dl"
    style_tag.string += "{ font-family: \"Trebuchet MS\", Helvetica, sans-serif !important; }"
    style_tag.string += ".bcVideoWrapper:after {padding-top: 0 !important; }"
    style_tag.string += "#media-collection-banner-content-container {background-color: transparent !important}"
    style_tag.string += "#media-collection-banner-content-container #media-collection-video-container"
    style_tag.string += "{ float: none; width: 100%; }"
    return style_tag


def generate_custom_script_tag():
    """ Creates a custom script tag to handle slideshow elements
        Returns <script> tag
    """
    soup = BeautifulSoup("", "html.parser")
    script_tag = soup.new_tag('script')
    script_tag["type"] = "text/javascript"
    script_tag.string = "var image = document.getElementsByClassName('field-slideshow-image-1')[0];"
    script_tag.string += "var tn = document.getElementsByClassName('field-slideshow-thumbnail');"
    script_tag.string += "function setImage(tn) {image.setAttribute('src', tn.getAttribute('src'));}"
    script_tag.string += "if(tn.length){setInterval(function() {setImage(tn[Math.floor(Math.random()*tn.length)]);}, 3000);"
    script_tag.string += "for (var i = 0; i < tn.length; i++)"
    script_tag.string += "tn[i].addEventListener('click', function(ev) {setImage(ev.target);}, false);}"
    return script_tag


def download_web_video(url, filename):
    """ Downloads a web video to the video directory
        Args:
            url (str): url to video to download
            filename (str): name to save video under
        Returns local path to video (str)
    """
    # Generate write to path and download if it doesn't exist yet
    write_to_path = os.path.sep.join([VIDEO_DIRECTORY, filename])
    if not os.path.isfile(write_to_path):
        download(url, write_to_path)
    return write_to_path


def download(url, write_to_path, attempts=DOWNLOAD_ATTEMPTS):
    """ Download the web video
        Args:
            url (str): url to video to download
            write_to_path (str): where to write video to
            attempts (int): how many times to reattempt a download
    """
    try:
        video_format = "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480][ext=mp4]"
        with youtube_dl.YoutubeDL({"format": video_format, "outtmpl": write_to_path}) as ydl:
            ydl.download([url])
    except youtube_dl.utils.DownloadError as e:
        # If there are more attempts, try again. Otherwise, return error
        if attempts > 0:
            download(url, write_to_path, attempts=attempts-1)
        else:
            LOGGER.error("Could not download video {} ({})".format(url, str(e)))
            raise e


def scrape_keywords(contents, el):
    """ Scrape page contents for keywords
        Args:
            contents (BeautifulSoup): contents to scrape
            el (str): element class to look for
        Returns list of tags ([str])
    """
    soup = BeautifulSoup("<div></div>", "html.parser")
    tags = []
    keyword_section = contents.find('div', {'class': el})
    if keyword_section:
        for related in keyword_section.find_all('a'):
            i_tag = soup.new_tag('span')
            i_tag.string = related.text
            i_tag['class'] = "underline"
            tags.append(related.text[:30])
            related.replaceWith(i_tag) # Remove links to other pages
    return tags


def scrape_style(url, zipper):
    """ Scrape any instances of url(...)
        Args:
            url (str): url to css file
            zipper (html_writer): zip to write to
        Returns str of css style rules
    """
    sheet = cssutils.parseUrl(url)
    rules = sheet.cssText.decode('utf-8')

    # Parse urls in css
    for url in cssutils.getUrls(sheet):
        try:
            # Download any urls in css to the shared asset directory (if not already there)
            filename = url.split('?')[0].split('/')[-1]
            filepath = os.path.sep.join([SHARED_ASSET_DIRECTORY, filename])
            if not os.path.isfile(filepath):
                with open(filepath, 'wb') as fobj:
                    fobj.write(read(url))

            # Replace text with new url
            new_url = zipper.write_file(filepath, filename, directory="assets")
            rules = rules.replace(url, "../" + new_url)

        except requests.exceptions.HTTPError:
            LOGGER.warning("Could not download css url {}".format(url))

    return rules


# CLI
################################################################################
if __name__ == '__main__':
    # This code runs when sushichef.py is called from the command line
    chef = MyChef()
    chef.main()
