import requests
import re
import requests_cache
requests_cache.install_cache()

from bs4 import BeautifulSoup
from bs4.element import Tag

index_url = "https://artsedge.kennedy-center.org/educators/lessons?ps=2147483647"

class Lesson(object):
    def __repr__(self):
        return repr(self.link)
    
    def __init__(self, lesson_soup):
        main, grade, subject, other_subject = lesson_soup.find_all("td")
        self.grade = grade.text
        self.subject = subject.text
        self.other_subject = other_subject.text

        anchors = main.find_all("a")
        anchor, = [x for x in anchors if x.text]
        self.title = anchor.text
        assert(self.title)
        self.link = anchor.attrs["href"]
        
        contents = main.find("p").contents
        # remove 'a' tag entirely including inner text
        valid_contents = [str(x) for x in contents if getattr(x, "name", None) not in ["a", "br"]]
        # convert to single string
        description = ''.join(valid_contents)
        # remove left over tags like <i>...</i> preserving inner text
        self.descr = re.sub("<[^>]*>", "", description).strip()

def crawl_lesson_index():
    response = requests.get(index_url)
    soup = BeautifulSoup(response.content, "html5lib")

    lessons_soup = soup.find("div", {"class": "searchResults"}).find_all("tr")
    lessons = []

    for lesson_soup in lessons_soup[2:]: # skip header
        lessons.append(Lesson(lesson_soup))

    return lessons

if __name__ == "__main__":
    print (len(crawl_lesson_index()))
