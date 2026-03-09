#!/usr/bin/env python

"""
Sushi Chef for http://3asafeer.com/
We make an HTML5 app out of each interactive reader.
"""

from collections import OrderedDict
import html
import os
import re
import requests
import shutil
import sys
import tempfile
import time
from urllib.parse import urlparse, parse_qs
import uuid

from bs4 import BeautifulSoup, Comment


import le_utils.constants
from ricecooker.chefs import SushiChef
from ricecooker.classes import nodes, files, licenses
from ricecooker.utils.caching import CacheForeverHeuristic, FileCache, CacheControlAdapter, InvalidatingCacheControlAdapter
from cachecontrol.heuristics import ExpiresAfter
from ricecooker.utils.browser import preview_in_browser
from ricecooker.utils.html import download_file, WebDriver
from ricecooker.utils.zip import create_predictable_zip
import selenium.webdriver.support.ui as selenium_ui
from distutils.dir_util import copy_tree



# CHEF and CONTENT DEBUG
################################################################################
DEBUG_MODE = False                    # print extra-verbose info
DOWNLOAD_ONE_TO_webroot = False       # produce debug webroot/ and skip cheffing
DOWNLOAD_ONLY_N = False               # chef only first N books; set to False to disable



sess = requests.Session()
cache = FileCache('.webcache')
chefdev_adapter = CacheControlAdapter(heuristic=ExpiresAfter(days=1), cache=cache)
sess.mount('http://3asafeer.com/', chefdev_adapter)
sess.mount('http://fonts.googleapis.com/', chefdev_adapter)


headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 6.1; WOW64; rv:20.0) Gecko/20100101 Firefox/20.0",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive"
}

# PAUSES and DELAYS
################################################################################
LOADING_WAIT_TIME = 10                                             # long delay
LOADING_WAIT_TIME_MS = LOADING_WAIT_TIME*1000
LOADING_WAIT_TIME_SHORT = 7                                        # short delay


class ThreeAsafeerChef(SushiChef):
    """
    The chef class that takes care of uploading channel to the content curation server.

    We'll call its `main()` method from the command line script.
    """
    channel_info = {
        'CHANNEL_SOURCE_DOMAIN': "3asafeer.com",
        'CHANNEL_SOURCE_ID': "3asafeer",
        'CHANNEL_TITLE': "3asafeer (العربيّة)",
        'CHANNEL_THUMBNAIL': "thumbnail.png",
        'CHANNEL_DESCRIPTION': "اقرأ لأطفالك قصصاً أطفال عربية؛ قصصاً مصوّرة و مقروءة تعلّمهم قيماً أخلاقيّة عالمية وتُطوّر من ذكائهم العاطفي. يمكنك قراءة هذه القصص لأبنائك قبل النوم أو في أي وقت من اليوم!",
    }

    def construct_channel(self, **kwargs):
        """
        Create ChannelNode and build topic tree.
        """
        # create channel
        channel_info = self.channel_info
        channel = nodes.ChannelNode(
            source_domain = channel_info['CHANNEL_SOURCE_DOMAIN'],
            source_id = channel_info['CHANNEL_SOURCE_ID'],
            title = channel_info['CHANNEL_TITLE'],
            thumbnail = channel_info.get('CHANNEL_THUMBNAIL'),
            description = channel_info.get('CHANNEL_DESCRIPTION'),
            language = "ar",
        )

        download_all(channel)
        if DOWNLOAD_ONE_TO_webroot:
            print('Skipping chef upload -- check webroot/ folder for sample book.')
            sys.exit(0)
        return channel


RATING_NUM_MAP = {
    # Novice
    'أ': "مبتدئ أ",
    'ب': "مبتدئ ب",
    'ج': "مبتدئ ج",
    'د': "مبتدئ د",
    'هـ': "مبتدئ هـ",
    'و': "مبتدئ و",

    # Intermediate
    'ح': "المتوسط ح",
    'ط': "المتوسط ط",
    'ي': "المتوسط ي",
    'ك': "المتوسط ك",
    'ل': "المتوسط ل",

    # Advanced
    'م': "المتقدّم م",
    'ن': "المتقدّم ن",
    'س': "المتقدّم س",
    'ع': "المتقدّم ع",
    'ف': "المتقدّم ف",
}


novice_topic = nodes.TopicNode(
    source_id="novice",
    title="المستوى المبتدئ",
    language="ar",
)
intermediate_topic = nodes.TopicNode(
    source_id="intermediate",
    title="المستوى المتوسط",
    language="ar",
)
advanced_topic = nodes.TopicNode(
    source_id="advanced",
    title="المستوى المتقدّم",
    language="ar",
)

RATING_TOPIC_MAP = {
    # Novice
    'أ': novice_topic,
    'ب': novice_topic,
    'ج': novice_topic,
    'د': novice_topic,
    'هـ': novice_topic,
    'و': novice_topic,

    # Intermediate
    'ح': intermediate_topic,
    'ط': intermediate_topic,
    'ي': intermediate_topic,
    'ك': intermediate_topic,
    'ل': intermediate_topic,

    # Advanced
    'م': advanced_topic,
    'ن': advanced_topic,
    'س': advanced_topic,
    'ع': advanced_topic,
    'ف': advanced_topic,
    'ص': advanced_topic,
}


def download_all(channel):
    if DEBUG_MODE:
        print("In download_all")
    # books_count = get_books_count()
    book_infos = get_book_infos()
    if DOWNLOAD_ONLY_N:
        print("Scraping first %s books for testing out of total of %s books available." % (DOWNLOAD_ONLY_N, len(book_infos)))
        book_infos = book_infos[0:DOWNLOAD_ONLY_N]
    else:
        print("There are %s books ... scraping them now!" % len(book_infos))

    topic_nodes = OrderedDict()
    channel.add_child(novice_topic)
    channel.add_child(intermediate_topic)
    channel.add_child(advanced_topic)

    source_ids_seen = []
    for i, book_info in enumerate(book_infos):
        print('-' * 80)
        if DOWNLOAD_ONE_TO_webroot and i > 0:
            print('Processing just one book because DOWNLOAD_ONE_TO_webroot is set')
            return
        print('Downloading book %s of %s' % (i + 1, len(book_infos)))
        book, rating = download_book(book_info['book_id'],
                                     book_info['title'],
                                     book_info['thumbnail'],
                                     book_info['rating_text'])

        if not topic_nodes.get(rating):
            title = RATING_NUM_MAP.get(rating, rating)
            subtopic_node = topic_nodes[rating] = nodes.TopicNode(
                source_id=str(rating),
                title=title,
                language="ar",
            )
            topic_node = RATING_TOPIC_MAP.get(rating)
            if topic_node:
                topic_node.add_child(subtopic_node)
            else:
                channel.add_child(subtopic_node)

            print("creating topic node %s with title %s" % (topic_nodes[rating], title))
        
        source_id = book.source_id
        if source_id not in source_ids_seen:
            topic_nodes[rating].add_child(book)
            source_ids_seen.append(book.source_id)
        else:
            print('found duplicate of book.source_id', book.source_id, book.title)



def click_read_and_wait(driver):
    """
    Clicks the READ link to load the page with the 3safeer apps, then async-loads
    all the elements of the page using the `loadMoreData` javascript function.
    """
    read_link = driver.find_element_by_css_selector('#readLink')
    read_link.click()
    selenium_ui.WebDriverWait(driver, 60).until(
            lambda driver: driver.find_element_by_id('stories-container'))
    time.sleep(LOADING_WAIT_TIME)
    previous_count = 0
    while True:
        story_count = len(driver.find_elements_by_css_selector('.story-cover'))
        if story_count == previous_count or DOWNLOAD_ONE_TO_webroot:
            break
        previous_count = story_count
        if DEBUG_MODE:
            print('story_count =', story_count)
            print('getting more data by calling window.loadMoreData()...')
        driver.execute_script('window.loadMoreData()')
        time.sleep(LOADING_WAIT_TIME_SHORT)


def get_book_infos():
    """
    Simulate a web visitor that loads the entire list of books on the READ page.
    Returns a list of dictionaries that contain the info for each book encountered.
    """
    print('in get_book_infos')
    with WebDriver("http://3asafeer.com/", delay=LOADING_WAIT_TIME_MS) as driver:
        click_read_and_wait(driver)
        books = driver.find_elements_by_css_selector('.story-cover')
        book_infos = []
        for book in books:
            # print(book)
            book_id = book.get_attribute('storyid')
            cover_picture = book.find_element_by_css_selector('picture.cover')
            cover_src = cover_picture.find_element_by_css_selector('.noimage').get_attribute('src')
            thumbnail = make_fully_qualified_url(cover_src)
            title = book.find_element_by_css_selector('.cover-title').text
            rating_text = book.find_element_by_css_selector('.rating-icon').text.strip()
            book_info = dict(
                book_id=book_id,
                title=title,
                thumbnail=thumbnail,
                rating_text=rating_text
            )
            if DEBUG_MODE:
                print('  - found book_info', book_info)
            book_infos.append(book_info)
        return book_infos


def download_book(book_id, title, thumbnail, rating_text):
    """
    Download book id=`book_id` by calling the website's `getPage(.,.,.)` function.
    """
    print('in download_book, book_id =', book_id)
    with WebDriver("http://3asafeer.com/", delay=LOADING_WAIT_TIME_MS) as driver:
        if DEBUG_MODE:
            print('Closing popup')
        close_popup = driver.find_element_by_css_selector('.ui-dialog-titlebar-close')
        close_popup.click()
        time.sleep(LOADING_WAIT_TIME_SHORT)

        print("Calling getPage('read', 'story', '%s')..." % book_id)
        driver.execute_script("getPage('read', 'story', '{id}')".format(id=book_id))
        time.sleep(LOADING_WAIT_TIME_SHORT*2)

        try:
            selenium_ui.WebDriverWait(driver, 30).until(
                    lambda driver: driver.find_element_by_id('reader-viewport'))
        except:
            print("Not able to click into the book :(, check screenshot.png")
            driver.save_screenshot('screenshot.png')
            raise

        time.sleep(LOADING_WAIT_TIME)

        doc = BeautifulSoup(driver.page_source, "html.parser")
        return (process_node_from_doc(doc, book_id, title, thumbnail),
                rating_text)


def process_node_from_doc(doc, book_id, title, thumbnail):
    """
    Create a Ricecooker HTML5AppNode instance given the HTML source and metadata.
    """
    if DOWNLOAD_ONE_TO_webroot:
        # Save the book's contents to the folder `webroot` in the chef root dir.
        # Use the script ./ricecooker/utils/kolibripreview.py to preview in K
        destination = './webroot'
        if os.path.exists(destination):
            shutil.rmtree(destination)
            os.mkdir(destination)
    else:
        # Create a temporary folder to download all the files for a book
        destination = tempfile.mkdtemp()

    # Ensure the thumbnail is in a format Ricecooker can accept, and if not,
    # use the first slide as the thumbnail.
    thumbnail_extensions = ('jpg', 'jpeg', 'png')
    if not thumbnail.lower().endswith(thumbnail_extensions):
        print("Thumbnail src (%s) doesn't end in any of %s."
                " Will use the first slide as the source." % (
            thumbnail, thumbnail_extensions))
        first_slide_src = doc.select_one('#slide-container .slide img')['src']
        thumbnail = make_fully_qualified_url(first_slide_src)
        if not thumbnail.lower().endswith(thumbnail_extensions):
            thumbnail = None

    # Download all the JS/CSS/images/audio/et needed to make a standalone app
    doc = download_static_assets(doc, destination)

    # Remove a bunch of HTML that we don't want showing in our standalone app
    doc.select_one('base')['href'] = ''
    remove_node(doc, '#loading')
    remove_node(doc, '#finishedActions')
    remove_node(doc, '.bookmarkbtn')
    remove_node(doc, '.reader-expand')
    remove_node(doc, '#progressBar')
    remove_node(doc, '#androidNotification')
    remove_node(doc, '#exit')
    remove_node(doc, '#ttmenu')

    # Remove unnecessary scripts in the head
    for pat in tag_content_patterns_to_remove_in_head:
        remove_nodes_containing_pattern(doc, pat, parent_tag_name='head')
    for pat in tag_content_patterns_to_remove_in_body:
        remove_nodes_containing_pattern(doc, pat, parent_tag_name='body')
    for pat_start, pat_end in cut_start_end_patterns:
        remove_nodes_between_comments(doc, pat_start, pat_end, parent_tag_name='body')

    # Write out the HTML source
    with open(os.path.join(destination, "index.html"), "w") as f:
        f.write(str(doc))

    print("Downloaded book %s titled \"%s\" (thumbnail %s) to destination %s" % (
        book_id, title, thumbnail, destination))
    #preview_in_browser(destination)

    zip_path = create_predictable_zip(destination)
    return nodes.HTML5AppNode(
        source_id=book_id,
        title=truncate_metadata(title),
        license=licenses.CC_BY_NC_SALicense(copyright_holder='3asafeer.com'),
        thumbnail=thumbnail,
        files=[files.HTMLZipFile(zip_path)],
        language="ar",
    )


def remove_node(doc, selector):
    """
    Removes a DOM element from the tree.
    """
    node = doc.select_one(selector)
    if node:
        node.decompose()



# DOM CLEANUP
################################################################################

tag_content_patterns_to_remove_in_head = [
    'GoogleAnalyticsObject',
    'chimpstatic.com',
    'resolution=',
    'facebook.com',
    'fb_iframe_widget_fluid_desktop',
    'connect.facebook.net',
]

tag_content_patterns_to_remove_in_body = [
    'connect.facebook.net',
    'refresh_session.php',
]

def remove_nodes_containing_pattern(doc, pattern, parent_tag_name='body'):
    """
    Remove DOM elements that text contain `pattern`.
    """
    parent = doc.select_one(parent_tag_name)
    for child in parent.find_all('script'):
        if pattern in str(child):
            child.extract()
            if DEBUG_MODE:
                print('removed from DOM:', str(child))

cut_start_end_patterns = [
    ('FB SDK Code Start', 'FB SDK Code End')
]

def remove_nodes_between_comments(doc, pattern_start, pattern_end, parent_tag_name='body'):
    """
    Remove DOM elements between pattern_start and pattern_end inclusively.
    """
    parent = doc.select_one(parent_tag_name)
    el_start = parent.find(text=lambda el: isinstance(el,Comment) and pattern_start in str(el))
    el_end = parent.find(text=lambda el: isinstance(el,Comment) and pattern_end in str(el))
    if el_start and el_end:
        el = el_start
        while True:
            if el == el_end:
                el.extract()
                break
            next_el = el.nextSibling
            if DEBUG_MODE:
                print('removed from DOM:', str(el))
            el.extract()
            el = next_el


def truncate_metadata(data_string):
    """
    Avoid probelms with Studio and Kolibri DB constraints.
    """
    MAX_CHARS = 190
    if len(data_string) > MAX_CHARS:
        data_string = data_string[:190] + " ..."
        print('Truncating string', data_string, 'to length 190.')
    return data_string


CSS_URL_RE = re.compile(r"url\(['\"]?(.*?)['\"]?\)")
IMAGES_IN_JS_RE = re.compile(r"images/(.*?)['\")]")


def download_static_assets(doc, destination):
    """
    Download all the static assets for a given book's HTML soup.

    Will download JS, CSS, images, and audio clips.
    """
    # Helper function to download all assets for a given CSS selector.
    def download_assets(selector, attr, url_middleware=None,
            content_middleware=None, node_filter=None):
        nodes = doc.select(selector)

        for i, node in enumerate(nodes):

            if node_filter:
                if not node_filter(node):
                    src = node[attr]
                    # node[attr] = ''
                    node.decompose()
                    print('Skipping node with src ', src)
                    continue

            # Remove preconnect and preload links form header
            relattr = node.get('rel', None)
            if relattr in ['preconnect', 'preload', 'apple-touch-icon']:
                node.decompose()
                continue

            url = make_fully_qualified_url(node[attr])

            if is_blacklisted(url):
                print('Skipping downloading blacklisted url', url)
                node.decompose()
                # node[attr] = ""
                continue

            if url_middleware:
                url = url_middleware(url)

            filename = derive_filename(url)
            node[attr] = filename

            print("Downloading", url, "to filename", filename)
            download_file(url, destination, request_fn=make_request,
                    filename=filename, middleware_callbacks=content_middleware)

    def js_middleware(content, url, **kwargs):
        if DEBUG_MODE:
            print('in js_middleware', url)
        # Download all images referenced in JS files
        for img in IMAGES_IN_JS_RE.findall(content):
            url = make_fully_qualified_url('/images/%s' % img)
            print("Downloading", url, "to filename", img)
            download_file(url, destination, subpath="images",
                    request_fn=make_request, filename=img)

        # Monkey-patch the js code that use localStorage and document.cookie so
        # to use window._localStorage (a plain js object) instead real localStorage
        # This change primarily affects the functions getStoredValue and setStoredValue
        # which are used to set the following properties:
        #  - diffRange: sets age-range for stories (needed to avoid a dialog popup)
        #  - lng: set to arabic
        #  - audio: toggles between read-aloud vs. no read-aloud
        return (content
            .replace("localStorage", "_localStorage")
            .replace('document.cookie.split', '"".split')
            .replace('document.cookie', 'window._document_cookie'))

    def css_url_middleware(url):
        if DEBUG_MODE:
            print('in css_url_middleware', url)
        # Somehow the minified app CSS doesn't render images. Download the
        # original.
        return url.replace("app.min.css", "app.css")

    def css_node_filter(node):
        return "stylesheet" in node["rel"]

    def css_content_middleware(content, url, **kwargs):
        if DEBUG_MODE:
            print('in css_content_middleware', url)
        # Download linked fonts and images
        def repl(match):
            src = match.group(1)
            if src.startswith('//localhost'):
                return 'src()'
            # Don't download data: files
            if src.startswith('data:'):
                return match.group(0)
            src_url = make_fully_qualified_url(src)
            derived_filename = derive_filename(src_url)
            download_file(src_url, destination, request_fn=make_request,
                    filename=derived_filename)
            return 'src("%s")' % derived_filename

        return CSS_URL_RE.sub(repl, content)

    # Download all linked static assets
    # 1. Images
    download_assets("img[src]", "src")
    # 2. CSS
    download_assets("link[href]", "href", url_middleware=css_url_middleware,
            content_middleware=css_content_middleware,
            node_filter=css_node_filter)
    # 3. JS
    download_assets("script[src]", "src", content_middleware=js_middleware)
    # 4. Audio
    download_assets("source[src]", "src")
    download_assets("source[srcset]", "srcset")

    # ... and also run the middleware on CSS/JS embedded in the page source to
    # get resources linked to in .css and .js files
    for node in doc.select('style'):
        node.string = css_content_middleware(node.get_text(), url='')

    for node in doc.select('script'):
        if not node.attrs.get('src'):
            node.string = js_middleware(node.get_text(), url='')

    # Copy over some of our own JS/CSS files and then add links to them in the
    # page source.
    copy_tree("static", os.path.join(destination, "static"))


    # HEAD START
    # Define window.story global constants that needs to be there otherwise js not happy
    # also defines window._localStorage that is used to mock-backend for localStorage
    chef_head_script = doc.new_tag("script", src="static/chef_start_of_head.js")
    doc.select_one('head').insert(0, chef_head_script)
    #
    #
    # Sets some more global vars for compatibiliy:
    # Modernizr.touch = true;    // needed to force mobile layout and show nav buttons
    # setStoredValue('diffRange', 'All');          // Set the age range to avoid popup
    #
    # and sutup hook for displaying the content on document ready
    #  $(document).ready(function() {
    #      $('#maincontent').show();
    #      animateButtons(0.9);            // This is necessary to force-show the buttons
    #  });
    chef_head_script2 = doc.new_tag("script", src="static/chef_end_of_head.js")
    doc.select_one('head').append(chef_head_script2)
    #
    # CSS ovverides for Kolibri
    chef_css = doc.new_tag("link", href="static/chef.css", rel="stylesheet")
    doc.select_one('head').append(chef_css)
    # HEAD END


    # BODY START
    chef_body_script = doc.new_tag("script", src="static/chef_end_of_body.js")
    doc.select_one('body').append(chef_body_script)
    # BODY END


    return doc


url_blacklist = [
    'google-analytics.com/analytics.js',
    'fbds.js',
    'chimpstatic.com',
    'fbcdn.net',
    'facebook.com',
    'facebook.net',
]




def is_blacklisted(url):
    return any((item in url) for item in url_blacklist)


def derive_filename(url):
    return "%s.%s" % (uuid.uuid4().hex, os.path.basename(urlparse(url).path))


def make_request(url, clear_cookies=True, timeout=60, *args, **kwargs):
    # print('Making request to', url)
    if clear_cookies:
        sess.cookies.clear()

    retry_count = 0
    max_retries = 5
    while True:
        try:
            response = sess.get(url, headers=headers, timeout=timeout, *args, **kwargs)
            break
        except (requests.exceptions.ConnectionError, requests.exceptions.ReadTimeout) as e:
            retry_count += 1
            print("Error with connection ('{msg}'); about to perform retry {count} of {trymax}."
                  .format(msg=str(e), count=retry_count, trymax=max_retries))
            time.sleep(retry_count * 1)
            if retry_count >= max_retries:
                return Dummy404ResponseObject(url=url)

    if response.status_code != 200:
        print("NOT FOUND:", url)

    return response


def make_fully_qualified_url(url):
    if url.startswith("../images"):
        return "http://3asafeer.com" + url[2:]
    if url.startswith("../scripts"):
        return "http://3asafeer.com" + url[2:]
    if url.startswith("//"):
        return "http:" + url
    if url.startswith("/"):
        return "http://3asafeer.com" + url
    if not url.startswith("http"):
        return "http://3asafeer.com/" + url
    return url


if __name__ == '__main__':
    """
    This code will run when the sushi chef is called from the command line.
    """
    chef = ThreeAsafeerChef()
    chef.main()
