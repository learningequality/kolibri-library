import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import hashlib
import os
import requests_cache
import codecs
import shutil
from mime import mime
import magic
import urllib3
from demo import download_video, VIDEO_DIR, TEMP_VIDEO_DIR, html_template
from PIL import Image
from io import BytesIO


urllib3.disable_warnings()
requests_cache.install_cache()

DOMAINS = ["nok6a.net", "", "www.nok6a.net"]
LINK_ATTRIBUTES = ["src", "href"]
DOWNLOAD_FOLDER = "temp_downloads"

"""
TODO LIST:
fix local anchors (even if they don't appear local)
correctly mangle links beginning with ~ -- i.e. ones with no domain
"""

print ("_")

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
    def is_valid_tag(tag):
        if not any(link in tag.attrs for link in LINK_ATTRIBUTES):
            return False
        # do not rewrite self-links
        href = tag.attrs.get("href")
        if href and href[0]== "#":
            return False
        # do not rewrite tags I've already rewritten
        if tag.attrs.get("dragon"):
            return False
        return True

    resources = set()
    for attribute in LINK_ATTRIBUTES:
        l = soup.find_all(lambda tag: is_valid_tag(tag))
        resources.update(l)
    return resources

def clean_soup(soup):
    for _class in ["post-block", "post-views-label", "post-views-icon", "post-views-count", "shareaholic-canvas", "post-views"]:
        tag = soup.find(None, {"class": _class})
        if tag:
            tag.decompose()
            
    for tagname in ["ins", "script"]:
        tags = soup.findAll(tagname)
        for tag in tags:
            tag.decompose()

    for attribute in ["srcset", ]:
        tags = soup.findAll(True, {attribute: True})
        for tag in tags:
            del tag[attribute]
            print ("removed attribute ", attribute, " from ", tag)
    return soup




def make_local(soup, page_url):

    def handle_youtube_iframe(iframe):
        src = iframe['src']
        if not src: return None
        if "youtube.com" not in src: return None
        try:
            filename = download_video(src)
        except Exception as e:
            print ("Unable to download {}: {}".format(src, e))
            iframe.decompose()
            return None
        mime_type = magic.from_file(VIDEO_DIR+filename, mime=True)
            
        video_tag = page_soup.new_tag('video', controls=True, dragon=True)
        source_tag = page_soup.new_tag('source', src=filename, type_=mime_type, dragon=True)
        video_tag.append(source_tag)
        return [VIDEO_DIR+filename, video_tag]


    def full_url(url):
        if urlparse(url).scheme == "":
            url = urljoin("https://", url)
        if urlparse(url).netloc == "":
            return urljoin(page_url, url)
        else:
            return url

    def hashed_url(url):
        return hashlib.sha1(full_url(url).encode('utf-8')).hexdigest() + guess_extension(full_url(url))

    attachments = []
    page_soup = soup
    body = soup.find("div", {"class": "post-text"})     
    
    title = soup.find("h1", {"class": "post-title"}).text
    img_tag = soup.find("div", {"class": "post-img"}).find("img")
    try:
        video_tag = soup.find("div", {"class": "video-space"}).find("iframe")
    except AttributeError:
        video_tag = None
    img = None
    if img_tag:
        img = img_tag['src']
        new_img = page_soup.new_tag("img", src=img)
        body.insert(0, new_img)
    elif video_tag:
        handled = handle_youtube_iframe(video_tag)
        if handled:
            attachment, video_tag = handled
            attachments.append(attachment)
            body.insert(0, video_tag) 
    else:
        print ("No image on ", page_url)

    soup = body
    soup = clean_soup(soup)    
    soup.attrs['class'] = "main-content"
    for iframe in soup.findAll("iframe"):
        handled = handle_youtube_iframe(iframe)
        if not handled: continue
        attachment, tag = handled
        attachments.append(attachment) 
        iframe.replace_with(tag) ## hope this doesn't break for loop!

    try:
        shutil.rmtree(DOWNLOAD_FOLDER)
    except:
        pass

    make_links_absolute(soup, page_url)
    resources = get_resources(soup)
    if img_tag:
        resources.add(img_tag)  # force banner image to be downloaded

    try:
        os.mkdir(DOWNLOAD_FOLDER)
    except FileExistsError:
        pass

    raw_url_list = [resource.attrs.get('href') or resource.attrs.get('src') for resource in resources if "mailto:"]
    url_list = [x for x in raw_url_list if not x.startswith("mailto:")]
    url_list = [full_url(url) for url in url_list]

    # replace URLs
    resource_filenames = {}

    # download content
    # todo: don't download offsite a's?

    for resource in resources:
        for attribute in LINK_ATTRIBUTES:
            attribute_value = full_url(resource.attrs.get(attribute))
            if attribute_value and attribute_value in url_list:
                if attribute_value.startswith("mailto"):
                    continue
                if resource.name == "a" and urlparse(attribute_value).netloc not in DOMAINS:
                    #print (urlparse(attribute_value).netloc)
                    # print ("rewriting non-local URL {} in {}".format(attribute_value, resource.name))
                    new_tag = page_soup.new_tag("span")
                    new_tag.attrs['style'] = "word-break: break-all;"
                    u = page_soup.new_tag("u")
                    u.insert(0, resource.text)
                    new_tag.insert(0, " (url:\xa0{})".format(resource.attrs['href']))
                    new_tag.insert(0, u)
                    resource.replaceWith(new_tag)  # TODO -- this might mess up the iteration?
                    continue

                else:
                    if attribute_value not in resource_filenames:
                        try:
                            r = requests.get(attribute_value, verify=False)
                        except Exception:
                            continue
                        content = r.content
                        try:
                            content_type = r.headers['Content-Type'].split(";")[0].strip()
                        except KeyError:
                            content_type = ""
                        extension = ext_from_mime_type(content_type)
                        filename = hashed_url(attribute_value)+extension

                        with open(DOWNLOAD_FOLDER+"/"+filename, "wb") as f:
                            try:
                                f.write(content)
                            except requests.exceptions.InvalidURL:
                                pass

                        resource_filenames[attribute_value] = filename

                    resource.attrs[attribute] = resource_filenames[attribute_value]
                    continue

    html = html_template.format(body=soup, title=title)
    
    with codecs.open(DOWNLOAD_FOLDER+"/index.html", "wb") as f:
        f.write(html.encode('utf-8'))
        
    # add modified CSS file
    for item in attachments:
        shutil.copy(item, DOWNLOAD_FOLDER)
    shutil.copy("styles.css", DOWNLOAD_FOLDER)
    

    # create zip file
    zipfile_name = shutil.make_archive("__"+DOWNLOAD_FOLDER+"/"+hashed_url(page_url), "zip", # automatically adds .zip extension!
                        DOWNLOAD_FOLDER)
    if img is not None:
       imgdata = requests.get(img).content
       print ("Image: ", img)
       try:
           Image.open(BytesIO(imgdata))
       except:
           img = None
       else:
           with open(zipfile_name+"_2.jpg", "wb") as f:
               f.write(imgdata)

    # delete contents of downloadfolder
    assert "downloads" in DOWNLOAD_FOLDER
    shutil.rmtree(DOWNLOAD_FOLDER)
    print(os.path.getsize(zipfile_name))
    

    return zipfile_name, title

def zip_from_url(url):
    response = requests.get(url)
    soup = BeautifulSoup(response.content, "html5lib")
    return make_local(soup, url) # zipfile_name, title
    


if __name__ == "__main__":
    #sample_url = "https://www.nok6a.net/?p=24029"
    sample_url = "https://www.nok6a.net/?p=22790"
    
    response = requests.get(sample_url)
    soup = BeautifulSoup(response.content, "html5lib")
    
    print (make_local(soup, sample_url))
