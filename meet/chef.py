#!/usr/bin/env python

"""
Sushi Chef for MEET Community Health Training for Migrants, from
http://migranthealth.eu/etraining/course/index.php?categoryid=1
"""

import os
import re
import requests
import tempfile
import time
from urllib.parse import urlparse, parse_qs
import uuid

from bs4 import BeautifulSoup

from le_utils.constants import languages
from ricecooker.chefs import SushiChef
from ricecooker.classes import nodes, files, licenses
from ricecooker.utils.caching import CacheForeverHeuristic, FileCache, CacheControlAdapter, InvalidatingCacheControlAdapter
from ricecooker.utils.browser import preview_in_browser
from ricecooker.utils.html import download_file, WebDriver
from ricecooker.utils.zip import create_predictable_zip
from ricecooker.utils.downloader import download_static_assets
import selenium.webdriver.support.ui as selenium_ui

try:
    import secrets
except ImportError:
    print("Please place MEET login credentials in a file called secrets.py.\n"
        "See secrets.py.example for a template.")


sess = requests.Session()
cache = FileCache('.webcache')
forever_adapter = CacheControlAdapter(heuristic=CacheForeverHeuristic(), cache=cache)

sess.mount('http://migranthealth.eu', forever_adapter)


headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 6.1; WOW64; rv:20.0) Gecko/20100101 Firefox/20.0",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive"
}

MEET_LICENSE = licenses.SpecialPermissionsLicense(
    description="Permission has been granted by MEET to"
    " distribute this content through Kolibri.",
    copyright_holder="MEET (migranthealth.eu)"
)


class MeetChef(SushiChef):
    """
    The chef class that takes care of uploading channel to the content curation server.

    We'll call its `main()` method from the command line script.
    """
    channel_info = {
        'CHANNEL_SOURCE_DOMAIN': "migranthealth.eu",
        'CHANNEL_SOURCE_ID': "meet-migrant-health",
        'CHANNEL_TITLE': "MEET Community Health Training for Migrants",
        'CHANNEL_THUMBNAIL': "thumbnail.png",
        'CHANNEL_DESCRIPTION': "An initiative of the European Commission's Lifelong Learning Initiative for community health educators",
        'CHANNEL_LANGUAGE': "en",
    }

    def construct_channel(self, **kwargs):
        """
        Create ChannelNode and build topic tree.
        """
        # create channel
        channel = self.get_channel()

        login_to_meet()
        fetch_all_languages(channel)

        return channel


def login_to_meet():
    response = sess.post('http://migranthealth.eu/etraining/login/index.php', {
        'username': secrets.meet_username,
        'password': secrets.meet_password,
        'rememberusername': '1',
        'anchor': '',
    })


def fetch_all_languages(channel):
    doc = get_parsed_html_from_url('http://migranthealth.eu/etraining/')
    for link in doc.select('.category.essentialcats a'):
        url = link['href']
        language_name = link.text.strip()[len('MEET '):]
        language = languages.getlang_by_name(language_name)
        language_node = fetch_language(url, language)
        channel.add_child(language_node)


def fetch_language(url, language):
    """E.g. English from http://migranthealth.eu/etraining/course/index.php?categoryid=1"""
    print('Fetching language %s from %s' % (language.name, url))

    language_node = nodes.TopicNode(
        source_id=language.code,
        title=language.native_name,
        language=language,
    )
    doc = get_parsed_html_from_url(url)

    for course in doc.select('.coursename'):
        title = course.text
        url = course.select_one('a')['href']
        language_node.add_child(fetch_module(url, title))

    return language_node


def fetch_module(url, title):
    """E.g. Module 1: Planning a CHE service
    from http://migranthealth.eu/etraining/course/view.php?id=3
    """
    print('  Fetching module "%s" from %s' % (title, url))

    module_node = nodes.TopicNode(
        source_id=url,
        title=title,
        language="en",
    )
    doc = get_parsed_html_from_url(url)

    # If we haven't enrolled into the module yet, enroll!
    form = doc.select_one('form#mform1')
    if form and form['action'] == 'http://migranthealth.eu/etraining/enrol/index.php':
        print('  ... not enrolled yet, so enrolling then reloading the page.')
        post_values = {}
        for element in doc.select('form#mform1 input'):
            if element.has_attr('value'):
                post_values[element['name']] = element['value']
        sess.post(form['action'], post_values)
        time.sleep(1)
        doc = get_parsed_html_from_url(url)

    for section in doc.select('.course-content .topics .section.main'):
        section_title = section.select_one('.section-title')
        if not section_title:
            continue
        unit_title = section_title.text.strip()
        unit_url = section_title.select_one('a')['href']
        unit_description = section.select_one('.summarytext').text.strip()
        unit = fetch_unit(unit_url, unit_title, unit_description)
        module_node.add_child(unit)

    return module_node


def fetch_unit(url, title, description):
    """E.g. Unit 3: Needs and Context Analysis
    from http://migranthealth.eu/etraining/course/view.php?id=3&section=3
    """
    print('    Fetching unit "%s" from %s' % (title, url))

    unit_node = nodes.TopicNode(
        source_id=url,
        title=title,
        language="en",
        description=description,
    )
    doc = get_parsed_html_from_url(url)
    for unit in doc.select('.course-content .topics .content .activity.modtype_page'):
        article_title = unit.select_one('.instancename').contents[0].strip()
        article_url = unit.select_one('a')['href']
        article = fetch_article(article_url, article_title)
        unit_node.add_child(article)

    return unit_node


def fetch_article(url, title):
    """E.g. The context Section 2
    from http://migranthealth.eu/etraining/mod/page/view.php?id=75
    """
    print('      Fetching article "%s" from %s' % (title, url))
    return download_content_node(url, title)


################################################################################
# General helpers


def derive_filename(url):
    if url.split('/')[-1] == 'all':
        return 'all.css'
    name = os.path.basename(urlparse(url).path).replace('%', '_')
    return ("%s.%s" % (uuid.uuid4().hex, name)).lower()


# TODO(davidhu): Extract this out to Ricecooker too
def download_content_node(url, title):
    doc = get_parsed_html_from_url(url)

    destination = tempfile.mkdtemp()
    doc = download_static_assets(doc, destination,
            'http://migranthealth.eu/', request_fn=make_request,
            url_blacklist=url_blacklist, derive_filename=derive_filename)

    nodes_to_remove = [
        'header',
        '#page-top-header',
        '#block-region-side-pre',
        '#region-main .row-fluid .span4.heading-rts',
        '.readmoreLinks',
        '.courseSectionNext',
        'img[alt="next"]',
        '.modified',
        '.footer-rts',
        '#page-footer',
        '.back-to-top',
        '.skiplinks',
        '.linkicon',
        '.generalbox table tr:nth-of-type(2)',
    ]
    for selector in nodes_to_remove:
        for node in doc.select(selector):
            node.decompose()

    # Write out the HTML source.
    with open(os.path.join(destination, "index.html"), "w") as f:
        f.write(str(doc))

    print("        ... downloaded to %s" % destination)
    #preview_in_browser(destination)

    zip_path = create_predictable_zip(destination)
    return nodes.HTML5AppNode(
        source_id=url,
        title=truncate_metadata(title),
        license=MEET_LICENSE,
        files=[files.HTMLZipFile(zip_path)],
        language="en",
    )


def truncate_metadata(data_string):
    MAX_CHARS = 190
    if len(data_string) > MAX_CHARS:
        data_string = data_string[:190] + " ..."
    return data_string


url_blacklist = [
    'analytics.js',
    'yui_combo.php',
    'fontawesome-webfont',
    'dnd_arrow',
    'pic1.jpg',
]


def make_request(url, headers=headers, timeout=60, *args, **kwargs):
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


def get_parsed_html_from_url(url, *args, **kwargs):
    html = make_request(url, *args, **kwargs).content
    return BeautifulSoup(html, "html.parser")


if __name__ == '__main__':
    """
    This code will run when the sushi chef is called from the command line.
    """
    chef = MeetChef()
    chef.main()
