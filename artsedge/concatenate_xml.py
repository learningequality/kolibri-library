import index_lessons
import requests
import re

from bs4 import BeautifulSoup

lessons = index_lessons.crawl_lesson_index()

with open("cat.xml", "wb") as f:
    for i, lesson in enumerate(lessons):
        print (i, lesson)
        response = requests.get("https://artsedge.kennedy-center.org" + lesson.link)
        soup = BeautifulSoup(response.content, "html5lib")
    
        pattern = " dataSrc: '([^']*)',"
        xml_url = "https://artsedge.kennedy-center.org" + re.search(pattern, response.text).group(1)
        xml_text = requests.get(xml_url).content
        f.write(xml_text)
        
        
# grep -v "?xml" cat.xml > cat2.xml
# surround whole file with "<tag>...</tag>"
# trang cat2.xml cat.xsd
    
