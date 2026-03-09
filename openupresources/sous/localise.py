import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import hashlib
import os
import codecs
from io import BytesIO
from zipfile import ZipFile
import shutil
import geogebra
import re

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

session = requests.Session()

DOWNLOAD_FOLDER = "foo"
ZIP_FOLDER = "zips/"
LINK_ATTRIBUTES = ['href', 'src']
IGNORE_COMBOS = [['a', 'href']]

# TODO: handle bad [Are you ready for more?] section icon


def test_login():
    test_response = session.get("https://im.openupresources.org/7/teachers/5.html")
    assert "sign up as an educator" not in test_response.text
    assert "Rational Number" in test_response.text

def create_folder_name(url):
    return (urlparse(url).path.strip('/').replace("/", "_").replace(".html", ""))

def get_resources(soup):
    def is_valid_tag(tag):
        if not any(link in tag.attrs for link in LINK_ATTRIBUTES):
            return False
        # ig
        for combo in IGNORE_COMBOS:
            if tag.name==combo[0] and combo[1] in tag.attrs:
                return False
        # do not rewrite self-links
        href = tag.attrs.get("href")
        if href and href[0]== "#":
            return False
        return True

    resources = set()
    for attribute in LINK_ATTRIBUTES:
        l = soup.find_all(lambda tag: is_valid_tag(tag))
        resources.update(l)
    return resources

def add_geogebra_files():
    geo_folder = DOWNLOAD_FOLDER+"/geogebra"
    try:
        os.mkdir(geo_folder)
    except Exception:
        pass
    with ZipFile("geogebra-math-apps-bundle-5-0-471-0.zip") as geo_data_zip:
        geo_data_zip.extractall(geo_folder)


def handle_geogebra_tag(geo_tag):
    """Given a tag in the webpage, download the relevant data and insert it into an iframe.
    Used by make_local"""
    geo_id = geo_tag.attrs['data-ggb_id']
    geo_filename = "geogebra/geo_"+geo_id+".html"
    html = geogebra.get_html_from_id(geo_id)
    # put html file back into directory
    with open(DOWNLOAD_FOLDER+"/"+geo_filename, "wb") as f:
        f.write(html.encode('utf-8'))

    # one of these script tags has the height and width we want:
    # "width":"580","height":"630"

    # create iframe loading this page
    # TODO: remove old tag
    geo_tag.name = "iframe"
    geo_tag.attrs['src'] = geo_filename
    geo_tag.attrs['width'] = 820
    geo_tag.attrs['height'] = 620
    geo_tag.attrs['scrolling'] = 'no'
    print ("handled {}".format(geo_id))

def make_local(page_url):

    # TODO 404 handling etc.
    try:
        os.mkdir(DOWNLOAD_FOLDER)
    except FileExistsError:
        pass

    html_response = session.get(page_url)
    print (html_response.url)

    soup = BeautifulSoup(html_response.content, 'html.parser')
    resources = get_resources(soup)
    # replace mathjax
    # TODO: actually install it
    try:
        mathjax, = [resource for resource in resources if 'src' in resource.attrs and "MathJax.js" in resource.attrs.get('src')]
    except ValueError:  # probably no mathjax
        print ("Unable to find mathjax on {}".format(page_url))
    else:   # ValueError not raised... replace mathjax
        resources.remove(mathjax)
        mathjax.attrs['src'] = 'mathjax/MathJax.js'

    # replace geogebra
    """<div class="geogebra-embed-wrapper" data-ggb_id="Vxv48Gtz">...</div>"""
    geos = soup.find_all("div", {'class': 'geogebra-embed-wrapper'})
    if geos:
        add_geogebra_files()  # TODO: do generically
    for geo in geos:
        handle_geogebra_tag(geo)

    # remove headers, footers
    tags = soup.find_all(lambda tag: tag.name in ["header", "footer"])
    for tag in tags:
        if 'class' in tag.attrs:
            if 'global-footer' in tag.attrs['class'] or \
               'lesson-footer' in tag.attrs['class'] or \
               'math-header'   in tag.attrs['class'] or \
               'global-header' in tag.attrs['class']:
                tag.extract()  # delete it

    # note: ensure order of raw_url_list remains the same as other url_lists we later generate.
    # (hopefully there's not two different looking but identical urls -- will lead to duplication)
    raw_url_list = [resource.attrs.get('href') or resource.attrs.get('src') for resource in resources]
    full_url_list = [urljoin(page_url, resource_url) for resource_url in raw_url_list]
    # TODO: add extensions to filenames
    hashed_file_list = [hashlib.sha1(resource_url.encode('utf-8')).hexdigest() for resource_url in full_url_list]
    replacement_list = dict(zip(raw_url_list, hashed_file_list))
    for resource in resources:
        for attribute in LINK_ATTRIBUTES:
            attribute_value = resource.attrs.get(attribute)
            if attribute_value in replacement_list.keys():
                resource.attrs[attribute] = replacement_list[attribute_value]

    for url, filename in zip(full_url_list, hashed_file_list):
        #print (url)
        with open(DOWNLOAD_FOLDER+"/"+filename, "wb") as f:
            f.write(session.get(url, verify=False).content)

    with codecs.open(DOWNLOAD_FOLDER+"/index.html", "w", "utf-8") as f:
        f.write(str(soup))

        
    # create zip file
    urlhash = hashlib.sha224(page_url.encode('utf-8')).hexdigest()
    output_zip = shutil.make_archive(ZIP_FOLDER+"/__"+DOWNLOAD_FOLDER+"_"+urlhash, "zip", # automatically adds .zip extension!
                        DOWNLOAD_FOLDER)
    assert "foo" in DOWNLOAD_FOLDER
    shutil.rmtree(DOWNLOAD_FOLDER)
    print ("folder deleted")
    return output_zip
    

if __name__ == "__main__":
    grades = [6]#,7,8]
    units = [1]#,2,3,4,5,6,7,8]
    subunits = [1]#,2,3,4,5,6]

    # 7 5 3
    placeholder_url = "https://im.openupresources.org/{}/students/{}/{}.html"
    for grade in grades:
        for unit in units:
            for subunit in subunits:
                target_url = placeholder_url.format(grade, unit, subunit)
                DOWNLOAD_FOLDER = create_folder_name(target_url)
                try:
                    make_local(target_url)
                except Exception as e:
                    print ("*** FAILURE ON {}, {}".format(target_url, str(e)))
                    with open("fail.log", "a") as f:
                        f.write("{}:{}\n".format(target_url, str(e)))

    print("END")

