import requests
import requests_cache
import lxml.html
import re
from urllib.parse import urljoin
from headers import headers

requests_cache.install_cache()  # WARNING: May cache stale unlogged in data.
session = requests.Session()

BASE_URL = "https://www.nashmi.net/ar"
# do_login() -- currently not working for some reason, we have hardcoded cookie instead.

def abs_links(urls):
    return [urljoin(BASE_URL, url) for url in urls]

class Root(object):
    def __init__(self, url):
        self.url = url
        self.response = session.get(self.url, headers=headers)
        self.html = self.response.content
        self.root = lxml.html.fromstring(self.html)

top = Root(BASE_URL)
top.children = abs_links(top.root.xpath("//div[@class='views-field views-field-name-1']/a/@href"))
top.childnames = [x.text_content().strip() for x in top.root.xpath("//div[@class='views-field views-field-name-1']/a")]

def get_lectures():
    for cat_url, cat_name in zip(top.children, top.childnames):
        cat = Root(cat_url)
        #cat.title = cat.root.xpath("//h1")[0].text_content().strip()
        cat.title = cat_name
        cat.courses = abs_links(cat.root.xpath("//span[@class='field-content']/a/@href"))
        for course_url in cat.courses:
            course = Root(course_url)
            course.title = course.root.xpath("//h1")[0].text_content().strip()
            course.lectures = abs_links(course.root.xpath("//span[@class='field-content']/a/@href"))
            course.lecturenames = [x.text_content().strip() for x in course.root.xpath("//span[@class='field-content']/a")]
            assert not any("/user?" in x for x in course.lectures)
            # these links appear OK but will redirect to /user? if followed
            lectures = zip(course.lectures, course.lecturenames)
            for lecture in lectures:
                yield (course_url, cat.title, course.title, lecture[1], lecture[0])


if __name__ == "__main__":
    get_lectures()
    exit()

    ###

    lecture_url = "https://www.nashmi.net/ar/content/%D8%A7%D9%84%D9%86%D9%87%D8%A7%D9%8A%D8%A7%D8%AA-%D9%85%D9%86-%D8%AE%D9%84%D8%A7%D9%84-%D8%A7%D9%84%D8%AA%D8%B9%D9%88%D9%8A%D8%B6-%D8%A7%D9%84%D9%85%D8%A8%D8%A7%D8%B4%D8%B1-%D8%AD%D8%B5%D8%A9-1"

    lecture = Root(lecture_url)
    assert "user?" not in lecture.response.url, "should be logged in."
    lecture.scripts = [x.text_content() for x in lecture.root.xpath("//script")]
    lecture.scripts_clean = [x for x in lecture.scripts if '"file"' in x]
    lecture.video_urls = [re.search('{"file":"([^"]+)"}', x).group(1) for x in lecture.scripts_clean]
    print (lecture.video_urls)
