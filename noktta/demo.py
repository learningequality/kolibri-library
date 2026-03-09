import requests
import json
from bs4 import BeautifulSoup
from io import BytesIO
from zipfile import ZipFile
from youtube_dl import YoutubeDL
from urllib.parse import urlparse
from shutil import copyfile
from glob import glob
import subprocess
import os

import magic
#import lxml.html
#from lxml.html.clean import Cleaner
TEMP_VIDEO_DIR = "current-video/"  # must end in /
VIDEO_DIR = "videos/"

html_template = """
<html dir="rtl">
  <head>
    <meta charset="utf-8">
    <link rel="stylesheet" type="text/css" href="styles.css">
    <title>{title}</title>
  </head>
  <body>
  <h1>{title}</h1>
    {body}
  </body>
</html>"""

def make_zip(body, title, img, attachments):
    io = BytesIO()
    with ZipFile(io, mode="w") as z:
        z.writestr("index.html", html_template.format(body=body, title=title, img=img))
        for file in attachments:
            z.write(file)
    return io.getvalue()

def ap(o):
    # take a string-like object and render awkward characters as lower-case gibberish
    # avoids problems like ligatures and rtl text not rendering correctly 
    def bowdler(char):
        if ord(char)<256:
            return char
        return chr(ord(char) % 26 + 96)
    
    text = str(o)
    print (''.join([bowdler(i) for i in text]))
    
        
def download_video(url):
    # returns a filename inside VIDEO_DIR
    # which is a cache
    tube_id = urlparse(url).path.split("/")[-1]
    output_glob = glob(VIDEO_DIR+tube_id+".*")
    if output_glob:
        assert len(output_glob) == 1
        filename = output_glob[0].split('/')[-1]
        print ("skipping download: already got "+filename)
    else:
        ydl_opts = {'outtmpl': TEMP_VIDEO_DIR+"video",
                    'format': "bestvideo[height<=640][ext=mp4]+bestaudio[ext=m4a]/best[height<=640][ext=mp4]"}
        for item in glob(TEMP_VIDEO_DIR+".*"):
            print ("removing "+item)
            os.remove(item)
        for item in glob(TEMP_VIDEO_DIR+"*"):
            print ("removing "+item)
            os.remove(item)            
        with YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        for item in glob(TEMP_VIDEO_DIR+".*"):
            print ("removing "+item)
            os.remove(item)
        directory_contents = os.listdir(TEMP_VIDEO_DIR)
        assert len(directory_contents) == 1
        auto_video_filename = TEMP_VIDEO_DIR + directory_contents[0]
        ext = auto_video_filename.split(".")[-1]
        filename = tube_id + "." + ext
        recode_filename = recode_video(auto_video_filename, VIDEO_DIR+filename, False)
    return filename

def recode_video(filename, outfile, encode=True):
    if encode:
        subprocess.call(["ffmpeg", "-i", filename, outfile, "-hide_banner"])
    else:
        copyfile(filename, outfile)
    os.remove(filename)
    return outfile

if __name__ == "__main__":
    url = "https://www.nok6a.net/wp-admin/admin-ajax.php"
    r = requests.post(url, data={'action': 'load_posts',
                                 'next_page': 2,
                                 'cat': 34,
                                 'tag': ''})
    j = json.loads(r.text)
    ## print (j.keys())  ## note there is a max_pages response!
    soup = BeautifulSoup(j['html'], "html5lib")
    for panel in soup.findAll("div", {"class": "panel"}):
        h2 = panel.find("h2")
        a = h2.find("a")
        ap("*"+ a['href'])
        break
    
    video_url = "https://www.nok6a.net/%D9%85%D8%A7-%D9%87%D9%8A-%D8%AA%D9%82%D9%86%D9%8A%D8%A9-%D9%87%D8%A7%D9%8A%D8%A8%D8%B1%D9%84%D9%88%D8%A8%D8%9F-%D9%83%D9%8A%D9%81-%D8%AA%D8%B9%D9%85%D9%84%D8%9F-%D9%87%D9%84-%D8%B3%D8%AA%D8%BA%D9%8A/"
    twitter_url = "https://www.nok6a.net/%D8%A8%D9%84%D8%A7-%D8%A7%D8%B4%D8%A7%D8%B1%D8%A7%D8%AA-%D8%AD%D9%85%D8%B1%D8%A7%D8%A1%D8%8C-%D8%B4%D9%88%D8%A7%D8%B1%D8%B9-%D8%AA%D8%AD%D8%AA-%D8%A7%D9%84%D8%A3%D8%B1%D8%B6-%D9%84%D8%B3%D9%8A%D8%A7/"
    
    attachments = ["styles.css"]
    r = requests.get(video_url)
    soup = BeautifulSoup(r.text, "html5lib")
    
    #block = soup.find("div", {"class": "post-block"})
    #
    #
    #block.decompose()
    for _class in ["post-block", "post-views-label", "post-views-icon", "post-views-count", "shareaholic-canvas", "post-views"]:
        tag = soup.find(None, {"class": _class})
        if tag:
            tag.decompose()
            
    for tagname in ["ins", "script"]:
        tags = soup.findAll(tagname)
        for tag in tags:
            tag.decompose()
            
    #<iframe width="900" height="506" src="https://www.youtube.com/embed/u5V_VzRrSBI?feature=oembed" frameborder="0"
    # allow="autoplay; encrypted-media" allowfullscreen></iframe>
    
    for iframe in soup.findAll("iframe"):
        src = iframe['src']
        if not src: continue
        if "youtube.com" not in src: continue
        filename = download_video(src)
        mime_type = magic.from_file(VIDEO_DIR+filename, mime=True)
            
        video_tag = soup.new_tag('video', controls=True)
        source_tag = soup.new_tag('source', src=filename, type_=mime_type)
        attachments.append(VIDEO_DIR+filename)
        video_tag.append(source_tag)
        iframe.replace_with(video_tag) ## hope this doesn't break for loop!
           
    body = soup.find("div", {"class": "post-text"})       
    #ap(body)
    title = soup.find("h1", {"class": "post-title"}).text
    #ap(title)
    img = soup.find("div", {"class": "post-img"}).find("img")['src']
    #ap(img)
    with open("zipdemo.zip", "wb") as f:
        f.write(make_zip(body, title, img, attachments))
    
    
    
    
    
    
