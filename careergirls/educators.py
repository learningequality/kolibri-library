import requests
import re
import lxml.html
import cg_index
from bs4 import BeautifulSoup
from urllib.parse  import urljoin
from le_utils.constants.roles import COACH
from ricecooker.classes.files import HTMLZipFile
from ricecooker.classes.nodes import HTML5AppNode
from ricecooker.classes.licenses import SpecialPermissionsLicense
LICENCE = SpecialPermissionsLicense("Career Girls", "For use on Kolibri")
urls = {
"/educators-parents-mentors/teachers/": "Teachers",
"/educators-parents-mentors/school-counselors/": "School Counselors",
"/educators-parents-mentors/librarians/": "Librarians",
"/educators-parents-mentors/group-leaders/": "Group Leaders",
"/educators-parents-mentors/mentors/": "Mentors",
"/educators-parents-mentors/parents/": "Parents"
}

top_url = "https://www.careergirls.org/educators-parents-mentors/"


# get resources
resources = []
resource_data = {"Empowerment Lessons": 38,
             "Inspirational Freebies": 34,
             "Printable Activities": 36,
             "Ready-to-Use Scripts": 33,
             "Toolkits and Guides": 37}

for resource_title, resource_id in resource_data.items():
    r = requests.get("https://www.careergirls.org/educators-parents-mentors/?filter_educator={}".format(resource_id)).content
    root = lxml.html.fromstring(r)
    resource_urls =  [urljoin(top_url, x) for x in root.xpath("//h2[@class='resource-listing__title']/a/@href")]
    resource_titles =  [x.text_content().strip() for x in root.xpath("//h2[@class='resource-listing__title']/a")]
    resources.append([resource_title, zip(resource_titles, resource_urls)])

# get html apps
import localise

apps = []
for url, title in urls.items(): 
    root = lxml.html.fromstring(requests.get(urljoin(top_url, url)).content)
    container, = root.xpath("//section[@class='page__content']")
    drop, = container.xpath(".//div[@id='resource-listing-container']")
    drop.getparent().remove(drop)
    html = lxml.html.tostring(container)
    print(html)
    soup = BeautifulSoup(html, "html5lib")
    zip_ = localise.make_local(soup, url)
    app_file = HTMLZipFile(zip_)
    app = HTML5AppNode(source_id = "app_{}".format(url),
                       title = title,
                       license = LICENCE,
                       files = [app_file],
                       role = COACH)
    apps.append(app)


