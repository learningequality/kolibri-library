#!/usr/bin/env python

"""
Sushi Chef for Tahrir Academy:
Videos from https://www.youtube.com/user/tahriracademy/playlists
More from http://en.tahriracademy.net/
"""

# TODO(davidhu): This is basically a copy pasta of the Open Osmosis sushi chef.
# Abstract into a YouTube playlist scraper and make available in Ricecooker
# utils.

import json
import os
import re
import requests

from bs4 import BeautifulSoup
import youtube_dl

from le_utils.constants import content_kinds
from ricecooker.chefs import JsonTreeChef
from ricecooker.classes import licenses
from ricecooker.utils.caching import CacheForeverHeuristic, FileCache, CacheControlAdapter
from ricecooker.utils.jsontrees import write_tree_to_json_tree


# Chef settings
################################################################################
ROOT_URL = 'http://tahriracademy.org'
DATA_DIR = 'chefdata'
TREES_DATA_DIR = os.path.join(DATA_DIR, 'trees')
SCRAPING_STAGE_OUTPUT = 'ricecooker_json_tree.json'
JSON_YOUTUBE_IDS_FILENAME = 'all_video_ids_in_playlists.json'
json_filename = os.path.join(DATA_DIR, JSON_YOUTUBE_IDS_FILENAME)
TAHRIR_ACADEMY_LICENSE = licenses.CC_BY_NC_NDLicense(copyright_holder='Tahrir Academy (tahriracademy.org)')

# Health/Computer/Skills and development
GENERAL_TOPICS_TRACK_AR = "مواضيع عامة"
TECHNOLOGY_CATEGORY_AR = "تكنولوجيا"
DEVELOPMENT_AND_SKILLS_CATEGORY_AR = "تنمية ومهارات"
HEALTH_CATEGORY_AR = "صحة"

# More videos from Youtube not on tahriracademy.org
MORE_VIDEOS_TRACK_AR = "المزيد من مقاطع الفيديو"


# CACHE LOGIC
################################################################################
SESSION = requests.Session()
cache = FileCache('.webcache')
forever_adapter= CacheControlAdapter(heuristic=CacheForeverHeuristic(), cache=cache)
SESSION.mount(ROOT_URL, forever_adapter)          # TODO: change this in final version

ydl = youtube_dl.YoutubeDL({
    'quiet': False, # True
    'no_warnings': True,
    'writesubtitles': True,
    'allsubtitles': True,
})




# SCRAPING YOUTUBE
################################################################################

def download_all_video_infos_from_youtube():
    """
    Returns a list of (youtube_id, title, playlist_id) for all TahrirAcademy videos on youtube.
    """
    if os.path.exists(json_filename):
        with open(json_filename, 'r') as json_file:
            all_video_infos = json.load(json_file)
            return all_video_infos

    youtube_channel_url = 'https://www.youtube.com/user/tahriracademy/playlists?shelf_id=0&view=1&sort=dd'
    print("Fetching YouTube channel and videos metadata --"
            " this may take a few minutes (%s)" % youtube_channel_url)
    info = ydl.extract_info(youtube_channel_url, download=False)

    all_video_infos = []
    for i, playlist in enumerate(info['entries']):
        title = playlist['title']
        youtube_url = playlist['webpage_url']
        print("  Downloading playlist %s (%s)" % (title, youtube_url))
        # playlist_topic = nodes.TopicNode(source_id=playlist['id'], title=title)
        for j, video in enumerate(playlist['entries']):
            # print('found video  youtube_id=', j, video['id'])
            all_video_infos.append( (video['id'], title, playlist['id']) )
    # print('all_video_infos=', all_video_infos)

    # save json cache
    data_out = []
    for youtube_id, title, playlist_id in all_video_infos:
        data_out.append(
            dict(
                youtube_id=youtube_id,
                title=title,
                playlist_id=playlist_id,
            )
        )
    with open(json_filename, 'wb') as json_file:
        json_string = json.dumps(data_out, ensure_ascii=False, indent=4).encode('utf8')
        json_file.write(json_string)

    return all_video_infos



# SCRAPING WEBSITE
################################################################################

def get_text(x):
    """
    Extract text contents of `x`, normalizing newlines to spaces and stripping.
    """
    return "" if x is None else x.get_text().replace('\r', '').replace('\n', ' ').strip()


def path_to_page_type_and_id(url_or_path):
    """
    Extracts the `page_type` and `id` from a given URL or path, e.g.
    '/category/196/blahabala'  -->  ('category', '196')
    """
    #
    match = re.match('.*/category/(?P<id>\d+).*', url_or_path)
    if match:
        return 'category', match.groupdict()['id']
    #
    match = re.match('.*/course/(?P<id>\d+).*', url_or_path)
    if match:
        return 'course', match.groupdict()['id']
    #
    match = re.match('.*/content/(?P<id>\d+).*', url_or_path)
    if match:
        return 'content', match.groupdict()['id']
    #
    else:
        raise ValueError('Unexpected path ' + url_or_path)


def make_self_href_re(page_type, id):
    """
    Build a regular expression that will href to current page.
    Used to extract section/subsection titles from nav lis.
    """
    return re.compile('.*/' + page_type + '/' + str(id) + '/.*')


youtube_ids_from_site = []

def download_path(path):
    """
    Returns (url, page).
    """
    # print('Downloading page path', path)
    if path.startswith('/'):
        url = ROOT_URL + path
    else:
        url = path
    html = SESSION.get(url).content
    page = BeautifulSoup(html, 'html.parser')
    return (url, page)


def scrape_root(url, page):
    print('Scraping root page', url)
    chennel_dict = dict(
        source_domain='tahriracademy.org',
        source_id='tahrir-academy',
        title='Tahrir Academy',
        thumbnail='https://yt3.ggpht.com/-t2RMfv5dBMM/AAAAAAAAAAI/AAAAAAAAAAA/DL3ELFokTGY/s288-c-k-no-mo-rj-c0xffffff/photo.jpg',
        description='One of the largest Arabic language content sources of locally produced educational videos. Aligned to the Egyptian curriculum as well as that of various other countries across the Middle East and North African region on a case-by-case basis for individual sets of content.',
        language='ar',
        children=[],
    )

    # extract titles for the three top-level tracks
    tracks_wrapper_uls = page.find('div', class_="tracks-wrapper").find_all('ul', recusive=False)
    track_titles = {}
    for tracks_wrapper_ul in tracks_wrapper_uls:
        track_li = tracks_wrapper_ul.find('li', recusive=False)
        track_link = track_li.find('a')
        track_id = track_link['data-target']
        track_title = get_text(track_link)
        track_titles[track_id] = track_title

    # extract categories for each track
    tracks_menu_div = page.find('div', id="subjects-menu")
    track_uls = tracks_menu_div.find_all('ul', recusive=False)
    for track_ul in track_uls:
        track_id = track_ul['id']
        track_dict = dict(
            kind=content_kinds.TOPIC,
            source_id='tahriracademy:'+track_id,
            title=track_titles[track_id],
            description='',
            children=[],
        )
        track_categories = track_ul.find_all('li', recusive=False)
        for category_li in track_categories:
            category_link = category_li.find('a')
            category_path = category_link['href']
            # category_title = get_text(category_li)
            category_url, category_page = download_path(category_path)
            scrape_category(track_dict, category_url, category_page)

        chennel_dict['children'].append(track_dict)

    return chennel_dict


def scrape_category(parent, url, page):
    print('Scraping category', url)
    page_type, page_id = path_to_page_type_and_id(url)
    self_re = make_self_href_re(page_type, page_id)
    self_link = page.find('a', attrs={'href': self_re})
    category_title = get_text(self_link)

    category_dict = dict(
        kind=content_kinds.TOPIC,
        source_id='category:'+page_id,
        title=category_title,
        description='',
        children=[],
    )
    print(category_dict)

    # scrape courses
    links = page.find_all('a')
    for link in links:
        if link.has_attr('data-course-id'):
            data_course_id = link['data-course-id'] # e.g "49"
            # data_remote = link['data-remote'] # e.g. "/course/show-info/49?isInCourse=0"
            course_path = '/course/' + str(data_course_id)
            course_url, course_page = download_path(course_path)
            scrape_course(category_dict, course_url, course_page)

    # check for subcategories, e.g. Secondary -> First secondary -> Biology
    container_div = page.find('div', class_="cat-listing")
    if container_div:
        # scrape subcategories:
        subcategories_ul = container_div.find('ul', id="subjects-nav")
        subcategories_lis = subcategories_ul.find_all('li')
        for subcat_li in subcategories_lis:
            subcat_link = subcat_li.find('a')
            subcat_path = subcat_link['href']
            # subcat_title = get_text(subcat_link.find('h4', class_="subject-title"))
            subcat_url, subcat_page = download_path(subcat_path)
            scrape_subcategory(category_dict, subcat_url, subcat_page)

    parent['children'].append(category_dict)

def scrape_subcategory(parent, url, page):
    print('Scraping subcategory', url)
    page_type, page_id = path_to_page_type_and_id(url)
    self_re = make_self_href_re(page_type, page_id)
    self_link = page.find('a', attrs={'href': self_re})
    subcat_title = get_text(self_link)
    subcategory_dict = dict(
        kind=content_kinds.TOPIC,
        source_id='subcategory:'+page_id,
        title=subcat_title,
        description='',
        children=[],
    )

    # scrape courses
    links = page.find_all('a')
    for link in links:
        if link.has_attr('data-course-id'):
            data_course_id = link['data-course-id'] # e.g "49"
            # data_remote = link['data-remote'] # e.g. "/course/show-info/49?isInCourse=0"
            course_path = '/course/' + str(data_course_id)
            course_url, course_page = download_path(course_path)
            scrape_course(subcategory_dict, course_url, course_page)

    parent['children'].append(subcategory_dict)



def scrape_course(parent, url, page):
    """
    Parameters is `url` of page and parsed BeautifuSoup tree in `page`.
    """
    print('Scraping course', url)
    page_type, page_id = path_to_page_type_and_id(url)

    # get title
    title_h2 = page.find('h2', class_="course-title")     #  id="myModalLabel">
    title = get_text(title_h2)

    # get description
    desc = get_text(page.find('div', class_='course-desc'))
    # print('desc=', desc)

    course_dict = dict(
        kind=content_kinds.TOPIC,
        source_id='course:'+page_id,
        title=title,
        description=desc,
        children=[],
    )

    nav = page.find('nav', class_="course-content-menu")  # id="course-content-menu">
    nav_ul = nav.find('ul', class_="nav-pills")
    content_lis = nav_ul.find_all('li')
    for content_li in content_lis:
        content_id = content_li['id']
        # content_link = content_li.find('a')
        #<img src="/files/content/image/image_برومو_سلسلة_&quot;_ريادة_الأعمال_&quot;_أكادي.jpeg">
        content_path = '/content/' + str(content_id)
        content_url, content_page = download_path(content_path)
        scrape_content(course_dict, content_url, content_page)

    parent['children'].append(course_dict)



def scrape_content(parent, url, page):
    print('Scraping content', url)
    page_type, page_id = path_to_page_type_and_id(url)

    iframe = page.find('iframe', id="youtubePlayer")
    if iframe:
        src = iframe['src']
        m = re.match('.*embed/(.*)\?.*', src)
        youtube_id = m.groups(1)[0]
        youtube_ids_from_site.append(youtube_id)
        video_node = fetch_video(youtube_id)
        if video_node:
            parent['children'].append(video_node)

    else:
        print('ZZZ did not find iframe for', url)
        # content_kinds.HTML5,
        # source_id='content:'+page_id,
        pass  # TODO fix this
        # parent['children'].append({'kind':'Uknownn/no iframe', 'url':url})

def fetch_video(youtube_id):
    try:
        video = ydl.extract_info(youtube_id, download=False)
        title = video['title']
        description = video['description']
        # youtube_url = video['webpage_url']
        # print("    Fetching video data: %s (%s)" % (title, youtube_url))
        video_file = dict(
            file_type=content_kinds.VIDEO,
            youtube_id=youtube_id,
        )
        video_node = dict(
            kind=content_kinds.VIDEO,
            source_id=youtube_id,
            title=truncate_metadata(title),
            license=TAHRIR_ACADEMY_LICENSE.as_dict(),
            description=truncate_description(description),
            derive_thumbnail=True,
            language="ar",
            files=[video_file],
        )
        return video_node
    except (youtube_dl.utils.DownloadError, youtube_dl.utils.ExtractorError) as e:
        print('ERROR', str(e))
        return None


DESCRIPTION_RE = re.compile('Subscribe - .*$')

def truncate_description(description):
    # Return all the lines up to one before the first line that starts with "http"
    lines = description.splitlines()
    cut_index = next((i for i, line in enumerate(lines) if line.startswith('http')), len(lines))
    return '\n'.join(lines[:max(cut_index - 1, 1)])


def truncate_metadata(data_string):
    MAX_CHARS = 190
    if len(data_string) > MAX_CHARS:
        data_string = data_string[:190] + " ..."
    return data_string







# CHEF
################################################################################

class TahrirAcademyChef(JsonTreeChef):
    """
    The chef class that takes care of uploading channel to the content curation server.

    We'll call its `main()` method from the command line script.
    """

    def scrape(self, args, options):
        """
        Build the ricecooker_json_tree that will create the ricecooker channel tree.
        """
        root_url, root_page = download_path('/')
        channel_dict = scrape_root(root_url, root_page)
        # Write out ricecooker_json_tree.json
        write_tree_to_json_tree(os.path.join(TREES_DATA_DIR, SCRAPING_STAGE_OUTPUT), channel_dict)

        # counters = [1,1,1,1,1,1,1]
        # def print_node(node, depth, indent=''):
        #     if 'title' in node:
        #         secion_num = '.'.join([str(n) for n in counters[0:depth]])
        #         print(indent, secion_num, depth, node['title'], '('+node.get('kind', 'channel root node')+')')
        #         counters[depth] += 1
        #     if 'children' in node:
        #         next_depth = depth+1
        #         for child in node['children']:
        #             print_node(child, next_depth, indent=indent+'   ')
        # print_node(channel_dict, 0)

    def pre_run(self, args, options):
        """
        Run the preliminary parts.
        """
        self.scrape(args, options)
        # TODO: add missing videos

        # youtube
        # all_video_infos = download_all_video_infos_from_youtube()
        # print(len(all_video_infos))
        # all_ids_set = set([item[0] for item in all_video_infos])
        # print(len(all_ids_set))

        # website
        # site_ids_set = set(youtube_ids_from_site)
        # len(site_ids_set)

        # for yid, title, playlist_id  in all_video_infos:
        #     if yid not in site_ids_set:
        #         print('https://www.youtube.com/watch?v='+yid+'&list='+playlist_id, title)




# CLI
################################################################################

if __name__ == '__main__':
    """
    This code will run when the sushi chef is called from the command line.
    """
    chef = TahrirAcademyChef()
    chef.main()
