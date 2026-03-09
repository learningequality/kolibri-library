from cg_index import index_video_index
import requests
import re
import lxml.html

videos = []
index = index_video_index("https://www.careergirls.org/be-empowered/develop-life-skills/")
video_page_urls = index.video_urls
resources = zip(index.resource_names, index.resource_download_urls)
# todo: resource

print (video_page_urls)
print (resources)

for page in video_page_urls:
    html = requests.get(page).content
    try:
        id_,  = re.search(b"video(?:Id): '([^']*)',", html).groups(1)
    except:
        print (page)
        raise
    root = lxml.html.fromstring(html)
    title_tag, = root.xpath("//h1")
    title = title_tag.text_content().strip()
    videos.append([id_.decode('utf8'), title])
    
