import lxml.html
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import hashlib
import os
import requests_cache
import codecs
import shutil
from mime import mime
import urllib3
urllib3.disable_warnings()
requests_cache.install_cache()

DOMAINS = ["careergirls.org", ""]
LINK_ATTRIBUTES = ["src", "href"]
DOWNLOAD_FOLDER = "downloads"
SKIP_HTML = True

"""
TODO LIST:
fix local anchors (even if they don't appear local)
correctly mangle links beginning with ~ -- i.e. ones with no domain
"""

def make_links_absolute(soup, base_url):
    for r in get_resources(soup):
        for attr in LINK_ATTRIBUTES:
            old_url = r.attrs.get(attr, None)
            url = old_url
            if not url:
                continue
            url = url.strip()
            url = urljoin(base_url, url)
            #if url != old_url:
            #    print ("Rewrote {} to {}".format(old_url, url))
            r.attrs[attr] = url

def guess_extension(filename):
    if "." not in filename[-8:]: # arbitarily chosen
        return ""
    ext = "." + filename.split(".")[-1]
    if "/" in ext:
        return ""
    return ext

def ext_from_mime_type(mime_type):
    if mime_type not in mime:
        return ""
    return mime[mime_type][0]

def get_resources(soup):
    """identify the potential resources -- i.e. src and href links"""
    def is_valid_tag(tag):
        if not any(link in tag.attrs for link in LINK_ATTRIBUTES):
            return False
        # do not rewrite self-links
        href = tag.attrs.get("href")
        if href and href[0]== "#":
            return False
        return True

    resources = set()
    for attribute in LINK_ATTRIBUTES:
        l = soup.find_all(lambda tag: is_valid_tag(tag))
        l = [x for x in l if x.get("localise") != "skip"]  # skip over resources we've already modified
        resources.update(l)
    return resources

def make_local(soup, page_url):
    # currently broken due to lack of nice_html function
    new_soup = make_local_html(soup, page_url)
    prefix = b"""<html><head>
      <link rel="stylesheet" type="text/css" href="resources/main.css">
      <meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
    </head>"""
    suffix = b"</html>"
    html = str(new_soup)
    html = html.encode('utf-8')
    with codecs.open(DOWNLOAD_FOLDER+"/index.html", "wb") as f:
        f.write(prefix + html + suffix)    
    return finalise_zip_file(page_url)

def make_local_html(soup, page_url, make_dir=None):
    def full_url(url):
        if urlparse(url).netloc == "":
            return urljoin(page_url, url)
        elif urlparse(url).scheme == "":
            return urljoin("https://", url)
        return url

    def hashed_url(url):
        return hashlib.sha1(full_url(url).encode('utf-8')).hexdigest() + guess_extension(full_url(url))


    try:
        shutil.rmtree(DOWNLOAD_FOLDER)
    except:
        pass

    make_links_absolute(soup, page_url)
    
    if make_dir:
        make_dir()
    else:
        try:
            os.mkdir(DOWNLOAD_FOLDER)
        except FileExistsError:
            pass

    resources = get_resources(soup)
    raw_url_list = [resource.attrs.get('href') or resource.attrs.get('src') for resource in resources]
    url_list = [x for x in raw_url_list if not x.startswith("mailto:")]
    url_list = [full_url(url) for url in url_list]

    # replace URLs
    resource_filenames = {}

    # download content

    for resource in resources:
        if resource.attrs.get("localise") == "skip":  # skip over resources we've already modified
            continue
        for attribute in LINK_ATTRIBUTES:
            attribute_value = full_url(resource.attrs.get(attribute))
            if attribute_value and attribute_value in url_list:
                resource_bytes = None
                if attribute_value.startswith("mailto"):  # skip over emails
                    continue
                if attribute_value.startswith("javascript:"):
                    continue
                if resource.name == "a" and "resource/" not in resource.attrs['href']:
                    # rewrite URL as a written hyperlink
                    new_tag = soup.new_tag("span")
                    u = soup.new_tag("u")
                    u.insert(0, resource.text)
                    new_tag.insert(0, " (url:\xa0{})".format(resource.attrs['href']))
                    new_tag.insert(0, u)
                    resource.replaceWith(new_tag)  # note -- this might mess up the iteration, but I haven't seen it yet
                    continue
                else:
                    if resource.name == "a": # implicit: is a resource
                        r = requests.get(urljoin("http://www.careergirls.org", attribute_value))
                        root = lxml.html.fromstring(r.content)
                        print (attribute_value)
                        try:
                            url__ = root.xpath("//h1//a/@href")[0]
                        except:
                            url__ = root.xpath("//div[@class='resource__link']//a/@href")[0]
                        attribute_value = urljoin("http://www.careergirls.org", url__)
                    if attribute_value not in resource_filenames:
                        try:
                            r = requests.get(attribute_value, verify=False)
                        except requests.exceptions.InvalidURL:
                            continue
                        content = r.content
                        try:
                            content_type = r.headers['Content-Type'].split(";")[0].strip()
                        except KeyError:
                            content_type = ""
                        extension = ext_from_mime_type(content_type)
                        if "htm" in extension and SKIP_HTML: 
                            continue
                        filename = hashed_url(attribute_value)+extension

                        with open(DOWNLOAD_FOLDER+"/"+filename, "wb") as f:
                            try:
                                f.write(content)
                            except requests.exceptions.InvalidURL:
                                pass

                        resource_filenames[attribute_value] = filename

                    resource.attrs[attribute] = resource_filenames[attribute_value]
                    continue


    # add modified CSS file -- moved out 
    os.mkdir(DOWNLOAD_FOLDER+"/resources")
    shutil.copy("main.css", DOWNLOAD_FOLDER+"/resources")
    
    return soup

def finalise_zip_file(url):
    def hashed_url(url):
        return hashlib.sha1(url.encode('utf-8')).hexdigest() + guess_extension(url)
    
    zipfile_name = shutil.make_archive("__"+DOWNLOAD_FOLDER+"/"+hashed_url(url), "zip", # automatically adds .zip extension!
                        DOWNLOAD_FOLDER)

    assert "downloads" in DOWNLOAD_FOLDER
    shutil.rmtree(DOWNLOAD_FOLDER)
    return zipfile_name

if __name__ == "__main__":
    raise RuntimeError
    sample_url = "https://www.mathplanet.com/education/pre-algebra/graphing-and-functions/graphing-linear-inequalities"
    response = requests.get(sample_url)
    soup = BeautifulSoup(response.content, "html5lib")
    print (make_local(soup, sample_url))
