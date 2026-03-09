import json
import os
from pathlib import Path
import ntpath
from ricecooker.utils import downloader
import requests
from ricecooker.utils.caching import CacheForeverHeuristic, FileCache, CacheControlAdapter
#from le_utils.constants import licenses, content_kinds, file_formats


DATA_DIR = "chefdata"


def save_thumbnail(url, save_as, sess):
    THUMB_DATA_DIR = build_path([DATA_DIR, 'thumbnail'])
    filepath = os.path.join(THUMB_DATA_DIR, save_as)
    try:
        document = downloader.read(url, loadjs=False, session=sess)
    except requests.exceptions.ConnectionError as e:
        return None
    else:
        with open(filepath, 'wb') as f:
            f.write(document)
            return filepath


def if_file_exists(filepath):
    file_ = Path(filepath)
    return file_.is_file()


def if_dir_exists(filepath):
    file_ = Path(filepath)
    return file_.is_dir()


def get_name_from_url(url):
    head, tail = ntpath.split(url)
    params_index = tail.find("&")
    if params_index != -1:
        tail = tail[:params_index]
    basename = ntpath.basename(url)
    params_b_index = basename.find("&")
    if params_b_index != -1:
        basename = basename[:params_b_index]
    return tail or basename


def get_name_from_url_no_ext(url):
    path = get_name_from_url(url)
    path_split = path.split(".")
    if len(path_split) > 1:
        name = ".".join(path_split[:-1])
    else:
        name = path_split[0]
    return name


def build_path(levels):
    path = os.path.join(*levels)
    if not if_dir_exists(path):
        os.makedirs(path)
    return path


def remove_links(content):
    if content is not None:
        for link in content.find_all("a"):
            link.replaceWithChildren()


def remove_iframes(content):
    if content is not None:
        for iframe in content.find_all("iframe"):
            iframe.extract()


def check_shorter_url(url):
    shorters_urls = set(["bitly.com", "goo.gl", "tinyurl.com", "ow.ly", "ls.gd",
                "buff.ly", "adf.ly", "bit.do", "mcaf.ee"])
    index_init = url.find("://")
    index_end = url[index_init+3:].find("/")
    if index_init != -1:
        if index_end == -1:
            index_end = len(url[index_init+3:])
        domain = url[index_init+3:index_end+index_init+3]
        check = len(domain) < 12 or domain in shorters_urls
        return check


def get_level_map(tree, levels):
    actual_node = levels[0]
    r_levels = levels[1:]
    for children in tree.get("children", []):
        if children["source_id"] == actual_node:
            if len(r_levels) >= 1:
                return get_level_map(children, r_levels)
            else:
                return children


def get_node_from_channel(source_id, channel_tree, exclude=None):
    parent = channel_tree["children"]
    while len(parent) > 0:
        for children in parent:
            if children is not None and children["source_id"] == source_id:
                return children
        nparent = []
        for children in parent:
            try:
                if children is not None and children["title"] != exclude:
                    nparent.extend(children["children"])
            except KeyError:
                pass
        parent = nparent


def load_tree(path):
    with open(path, 'r') as f:
        tree = json.load(f)
    return tree
    
