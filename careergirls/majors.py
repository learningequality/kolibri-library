import requests
import re
import lxml.html
import cg_index
from bs4 import BeautifulSoup
from urllib.parse  import urljoin
from ricecooker.classes.files import HTMLZipFile
from ricecooker.classes.nodes import HTML5AppNode
from ricecooker.classes.licenses import SpecialPermissionsLicense
import localise
LICENCE = SpecialPermissionsLicense("Career Girls", "For use on Kolibri")


top_url = "https://www.careergirls.org/be-empowered/research-college-majors-requirements/"

response = requests.get(top_url)
root = lxml.html.fromstring(response.content)
links = root.xpath("//div[@id='cluster-listing-container']//a/@href")
link_titles = [x.text_content().strip() for x in root.xpath("//div[@id='cluster-listing-container']//a")]

link_pairs = []
links_so_far = []
for title, link in zip(links, link_titles):
    if link not in links_so_far:
        link_pairs.append([title, link])
        links_so_far.append(link)

apps = []
for link, title in link_pairs:
    app_response = requests.get(urljoin(top_url, link))
    root = lxml.html.fromstring(requests.get(urljoin(top_url, link)).content)
    container, = root.xpath("//div[@class='college-major__body wysiwyg']")
    roles = [x.text_content().strip()  for x in root.xpath("//a[@class='career-wrapper']")]

    h4 = lxml.html.Element("h4")
    h4.text = "Related Careers"
    container.append(h4)
    ul = lxml.html.Element("ul")
    for role in roles:
        li = lxml.html.Element("li")
        li.text = role
        ul.append(li)
    container.append(ul)
    
    html = lxml.html.tostring(container)
    soup = BeautifulSoup(html, "html5lib")
    # add roles to soup
    
    zip_ = localise.make_local(soup, link)
    app_file = HTMLZipFile(zip_)
    app = HTML5AppNode(source_id = "app_{}".format(link),
                       title = title,
                       license = LICENCE,
                       files = [app_file])
    #print (app)
    apps.append(app)


