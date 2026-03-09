"""Utilities for crawling nok6a"""
import json
import requests
from bs4 import BeautifulSoup
import requests_cache
requests_cache.install_cache()

author_lookup = {}

def get_json_page(cat, page):
    """Get one page of URLs for a category"""
    url = "https://www.nok6a.net/wp-admin/admin-ajax.php"
    response = requests.post(url, data={'action': 'load_posts',
                                        'next_page': page,
                                        'cat': cat,
                                        'tag': ''})
    j = json.loads(response.text)
    done = page >= j['max_pages']
    soup = BeautifulSoup(j['html'], "html5lib")
    links = []
    for panel in soup.findAll("div", {"class": "panel"}):
        h2 = panel.find("h2")
        a = h2.find("a")
        links.append(a['href'])
        author_i = soup.find("i", {"class": "fa fa-user"})
        if author_i:
            author = author_i.parent.find("a").text
            author_lookup[a['href']] = author
        else:
            author_lookup[a['href']] = ""
    return links, done

def get_all_links(cat):
    print("Getting links for category ", cat)
    """Get all URLs for a category"""
    page = 0
    while True:
        page = page + 1
        items, done = get_json_page(cat, page)
        if done:
            break
        else:
            for item in items:
                yield item

get_json_page(42, 31)

#for each_url in get_all_links(42):
    #print(each_url)
