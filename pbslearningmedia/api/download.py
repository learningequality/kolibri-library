import login
import os
import lxml.html
import json
import add_file
import requests_cache

session = login.session
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Ubuntu Chromium/71.0.3578.98 Chrome/71.0.3578.98 Safari/537.36"

class NotExpected(Exception):
    pass

class NotAVideo(NotExpected):
    pass

class NotAnImage(NotExpected):
    pass

class Skip(Exception):
    pass

#try:
#    os.mkdir("zipcache")
#except FileExistsError:
#    pass

def download_something(canonical_url, **kwargs):

    def get_url():
        for x in [get_video_url, get_image_url, get_pdf_url, get_swf_url, get_redirect_url, get_server_error]:
            try:
                return x()
            except NotExpected:
                pass
        print ("No detection for", canonical_url)
        return ({"url": None}, "Unknown Error")
        # raise RuntimeError("No detection for ", canonical_url)

    def get_server_error():
        if b"Internal Server Error" in response.content:
            return ({"url": None}, "Server Error")
        if response.status_code > 399:
            return ({"url": None}, "Server Error")
        raise NotExpected()

    def get_redirect_url():
        if "pbslearningmedia.org" not in response.url:
            print ("Redirect")
            return ({"url": None}, "Redirect")
        if "loginRequired" in response.url:
            print("LOGIN")
            return ({"url": None}, "Login")
        raise NotExpected()

    def get_video_url():
        scripts= root.xpath("//script/text()")
        try:
            script, = [x for x in scripts if 'jwSettings1' in x]
        except ValueError:
            raise NotAVideo("no jwSettings1 found")
        except Exception:
            raise
        # start at first `{`, end at first `\n};` for data structure};
        left = script.index("{")
        right = script.index("\n};")
        jsontext = script[left:right+2]
        j = json.loads(jsontext)
        primary_media, = [x for x in j['lo']['media'] if x['primary']]
        if ".mp3" in primary_media:
            return (primary_media, "Audio")
        else:
            return (primary_media, "Videos")

    def get_image_url():
        imgs = root.xpath("//img[@id='asset-image']")
        if imgs:
            print ("Image ", imgs)
            return ({"url": imgs[0].attrib["src"]}, "Images")
        else:
            raise NotAnImage()

    def get_pdf_url():
        if response.content[:4] == b"%PDF":
            return ({"url": canonical_url}, "Documents")
        else:
            raise NotExpected()

    def get_swf_url():
        if b"swfobject.embedSWF" in response.content or b'application/x-shockwave-flash' in response.content:
            print ("FLASH")
            return ({"url": None}, "Flash")
        if b"Slide Show!" in response.content:
            print ("SLIDES")
            return ({"url": None}, "Slideshow")
        
        raise NotExpected()

    # download HTML

    while True:
        try:
            response = session.get(canonical_url, headers={"user-agent": UA})
            break
        except Exception as e:
            print (e)

    root = lxml.html.fromstring(response.content)
    primary_media, media = get_url()
    if media in ["Images", "Flash", "Slideshow", "Redirect", "Login", "Server Error", "Unknown Error"]:
        raise Skip(media)
    assert primary_media['url']

    target_url = primary_media['url']
    
    node = add_file.create_node(url=target_url, source_id=canonical_url, **kwargs)

    if 'caption' in primary_media and primary_media['caption']:
        try:
            caption_url = primary_media['caption']
        except add_file.CantMakeNode:
            pass 
        else:
            caption_file = add_file.create_file(url=caption_url, **kwargs)
            node.add_file(caption_file)

    return node, media

if __name__ == "__main__":
    print(download_something("https://ca.pbslearningmedia.org/asset/cd5c6a16-e3be-4d67-94e3-e5817b0fc1be/"))