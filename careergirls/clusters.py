import requests
import lxml.html
import requests_cache
from urllib.parse import urljoin
requests_cache.install_cache()
BASE_URL = "https://www.careergirls.org/explore-careers/career-clusters"

role_data = []
cluster_meta = {}

def full(url):
    return urljoin(BASE_URL, url)

def fetch_job_url(path, url):
    cluster, role = path
    html = requests.get(full(url)).content
    root = lxml.html.fromstring(html)
    tags = root.xpath("//div[@class='listing-wrapper']/ul/li/a") # may be empty!
    for tag in tags:
        job_title = tag.text_content().strip()
        job_url = tag.attrib['href']
        data = [cluster, role, job_title, job_url]
        print (data)
        role_data.append(data)

def fetch_cluster_url(title, url):
    cluster_html = requests.get(full(url)).content
    cluster_root = lxml.html.fromstring(cluster_html)
    cluster_tags = cluster_root.xpath("//a[@class='career-wrapper']")
    for tag in cluster_tags:
        new_title = tag.attrib['title']
        new_url = tag.attrib['href']
        fetch_job_url([title, new_title], new_url)
    cluster_meta[title] = {'img': cluster_root.xpath("//div[@class='cluster__image']//img/@src")[0],
                           'desc': cluster_root.xpath("//div[@class='cluster__introduction']")[0].text_content()}
    

def fetch_root_url(url):
    cluster_html = requests.get("https://www.careergirls.org/explore-careers/career-clusters/").content
    cluster_root = lxml.html.fromstring(cluster_html)
    cluster_tags = cluster_root.xpath("//ul[@class='cluster-listing']/li/a")
    for tag in cluster_tags:
        title = tag.attrib['title']
        target = tag.attrib['href']
        fetch_cluster_url(title, target)

fetch_root_url(None)
# clusters.role_data now populated
top = set([x[0] for x in role_data])
print (top)
second = set([tuple(x[:2]) for x in role_data])
print (second)

# .top, .second, .role_data are imported, also .cluster_meta
