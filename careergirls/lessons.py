import lxml.html
import requests
from urllib.parse import urljoin
import re
from sushichef import make_youtube_video

BASE_URL = "https://www.careergirls.org/"

class Lesson(object):
    def __repr__(self):
        return "\n".join((self.title, "Video IDs", str(self.video_ids), "Desc", self.description, "Resources", str(self.resources)))

def lesson(lesson_url):
    L = Lesson()
    response = requests.get(lesson_url).content
    root = lxml.html.fromstring(response)
    L.video_ids = []
    for script in root.xpath("//script"):
        code = script.text_content()
        if "YouTube" not in code:
            continue
        L.video_ids.extend(re.search("video: '([^']*)',", code).groups(1))
    assert L.video_ids
    bigdesc = root.xpath("//div[@class='video__introduction wysiwyg']")[0].text_content()
    smalldesc = root.xpath("//div[@class='video__body wysiwyg']/p")[0].text_content()
    L.description = bigdesc + "\n" + smalldesc
    raw_resources = root.xpath("//div[@class='video__body wysiwyg']//a/@href")
    L.resources = [get_resource(urljoin(lesson_url, x)) for x in raw_resources]
    L.title = root.xpath("//h1[@class='video__title']")[0].text_content()
    return L

def get_resource(url):
    response = requests.get(url).content
    root = lxml.html.fromstring(response)
    new_url, = root.xpath("//h1[@class='resource__title']/a/@href")
    title = root.xpath("//h1[@class='resource__title']/a")[0].text_content()
    return (title, new_url)

def lesson_index():
    response = requests.get("https://www.careergirls.org/explore-careers/find-your-path/").content
    root = lxml.html.fromstring(response)
    lesson_urls = root.xpath("//ul[@class='listing']//a/@href")
    lessons = [lesson(x) for x in lesson_urls]
    resources = root.xpath("//div[@class='resource-info']//a/@href")
    resources_full = [urljoin(BASE_URL, x) for x in resources]
    titles = [x.text_content() for x in root.xpath("//div[@class='resource-info']//a")]
    return lessons, list(zip(titles, resources_full))

def student_resources():
    response = requests.get("https://www.careergirls.org/be-empowered/find-resources-programs/").content
    root = lxml.html.fromstring(response)
    resources = root.xpath("//div[@class='resource-info']//a/@href")
    resources_full = [urljoin(BASE_URL, x) for x in resources]
    titles = [x.text_content() for x in root.xpath("//div[@class='resource-info']//a")]
    return list(zip(titles, resources_full))

if __name__ == "__main__":
    print (student_resources())
#     print (lesson_index())
