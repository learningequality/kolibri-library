import requests
import lxml.html
from lxml.html.clean import Cleaner
import requests_cache
import re
from urllib.parse import urljoin
from zipfile import ZipFile
from io import BytesIO
requests_cache.install_cache()

super_cluster_url = "https://www.careergirls.org/explore-careers/career-clusters/"

html_template = """
<html>
  <head>
    <link rel="stylesheet" type="text/css" href="styles.css">
    <title>Resource</title>
  </head>
  <body>
    {}
  </body>
</html>"""

def fetch_resource(url):
    # given a url, get the resource page and then the bytes of the resource proper
    request = requests.get(url) 
    root = lxml.html.fromstring(request.content) 
    target_url, = root.xpath("//div[@class='resource__link']//a/@href") 
    return requests.get(target_url).content  ## should be a byte stream 

def clean_html(source, remove_a = True):
    "see https://lxml.de/4.1/api/lxml.html.clean.Cleaner-class.html"
    "Note that this mangles the original structure!"
    remove_tags = ["div", "span", "svg"]
    if remove_a:
        remove_tags.append("a")
    cleaner = Cleaner(scripts = True,
                      javascript = True,
                      comments = True,
                      style = True, # maybe not 
                      inline_style = True, # maybe not
                      links = True,
                      meta = True,
                      page_structure = False,
                      processing_instructions = True,
                      embedded = True,
                      frames = True,
                      forms = True,
                      annoying_tags = True,
                      remove_tags = remove_tags,
                      kill_tags = [], # also destroys content, unlike remove
                      ## allow_tags = [], # default all
                      remove_unknown_tags = True,
                      safe_attrs_only = True,
                      safe_attrs = ["href"], # default: sane
                      add_nofollow = True,
                      host_whitelist = [],
                      ## whitelist_tags = [], # default: sane
                      )
    new_tree = cleaner.clean_html(source)
    html_text = lxml.html.tostring(new_tree).decode('utf-8')
    html_text = re.sub(" +", " ", html_text)
    html_text = re.sub("[\n ]*\n[\n ]*", "\n", html_text)
    return html_text

#print (clean_html("<html><script>foo</script><b>bar</b></html>"))
#exit()

class Record(object):
    def __init__(self, url):
        self.url = url
        self.response = requests.get(self.url)
        self.root = lxml.html.fromstring(self.response.content)
    
    def __repr__(self):
        return str(self.__dict__)
    
    def keys(self):
        return self.__dict__.keys()

def full_url(link):
    return urljoin(super_cluster_url, link)

def full_urls(_list):
    return [full_url(link) for link in _list]
    
def index_cluster(cluster_url):
    cluster = Record(cluster_url)
    cluster.title = cluster.root.xpath("//h1[@class='cluster__title']/span/text()")
    cluster.description = cluster.root.xpath("//div[@class='cluster__introduction']/p/text()")
    cluster.jobs = full_urls(cluster.root.xpath("//li[@class='career-glossary__title']/a/@href"))
    cluster.skills = cluster.root.xpath("//ul[@class='listing']//a/@href")
    return cluster

def index_job(job_url):
    # TODO -- get job name
    job = Record(job_url)
    job.title = job.root.xpath("//h1[@class='video__title']/text()")[0]
    assert isinstance(job.title, str)
    job.roles = full_urls(job.root.xpath("//div[@class='role-models-related listing-grid listing-container']//a/@href"))
    try:
        job.youtube = re.search("videoId: '([^']+)'", job.response.text).groups()[0]
    except AttributeError:
        job.youtube = None

    raw_accordion = job.root.xpath("//div[@class='career__accordion accordion-wrapper']")[0]  # TODO -- generate HTML 5 app
    
    # replace initial text of <div class="accordion__title">___ with <h3>___</h3>
    accordion_title_tags = raw_accordion.xpath(".//div[@class='accordion__title']")
    for tag in accordion_title_tags:
        h3 = lxml.html.Element("h3")
        h3.text = tag.text
        tag.text=""
        tag.insert(0, h3)
        
    # apparently this'll trash the original structure, but I'm not convinced that's true.
    
    job.html = clean_html(raw_accordion)
    
    io = BytesIO()
    with ZipFile(io, mode="w") as z:
        z.writestr("index.html", html_template.format(job.html))
        z.write("styles.css")
    job.app = io.getvalue()
    return job

def index_video(video_url):
    job = Record(video_url)
    job.title = job.root.xpath("//h1[@class='video__title']/text()")[0]
    assert isinstance(job.title, str)
    try:
        job.youtube = re.search("videoId: '([^']+)'", job.response.text).groups()[0]
    except AttributeError:
        job.youtube = None
    preamble = job.root.xpath("//div[@class='video__introduction wysiwyg']")[0]
    html_page = job.root.xpath("//div[@class='video__body wysiwyg']")[0]
    html_page.insert(0, preamble)
    job.html = clean_html(html_page, remove_a=False)
    
    io = BytesIO()
    with ZipFile(io, mode="w") as z:
        z.writestr("index.html", html_template.format(job.html))
        z.write("styles.css")
    job.app = io.getvalue()
    with open("play.zip", "wb") as z:
        z.write(job.app)
    return job


def index_skill(skill_url):
    from urllib.parse import urljoin
    # TODO: add other bits, should we care about this.
    skill = Record(skill_url)
    try:
        skill.youtube = re.search("videoId: '([^']+)'", skill.response.text).groups()[0]
    except AttributeError:
        skill.youtube = None
    try:
        skill.title = skill.root.xpath("//h1[@class='video__title']/text()")[0]
    except Exception as e:
        print ("No title for ", skill.url)
        skill.title = "Video"
    skill.preamble = skill.root.xpath("//div[@class='video__introduction wysiwyg']")[0]

    skill.body = skill.root.xpath("//div[@class='video__body wysiwyg']")[0]
    skill.body.insert(0, skill.preamble)
    skill.html = clean_html(skill.body)
    
    io = BytesIO()
    with ZipFile(io, mode="w") as z:
        z.writestr("index.html", html_template.format(skill.html))
        z.write("styles.css")
    skill.app = io.getvalue()

    
    links = [urljoin("https://careergirls.org/x", x) for x in skill.body.xpath(".//a/@href")]
    skill.downloads = [get_resource(x) for x in links]
    return skill

def get_resource(resource_url):
    if "careergirls.org" not in resource_url:
        target_url = resource_url
    else:
        resource = Record(resource_url)
        target_url = resource.root.xpath("//a[@class='button']/@href")[0]
    binary = requests.get(target_url).content
    return binary
 
def index_role(role_url):
    # Note, we'll need to do these from the jobs since there doesn't appear to be a master list
    role = Record(role_url)
    role.name = role.root.xpath("//div[@class='role-model__name']")[0].text.strip()
    role.title = role.root.xpath("//h1[@class='role-model__title']")[0].text.strip()
    assert isinstance(role.title, str)
    bio = role.root.xpath("//div[@class='role-model__body wysiwyg']/p")
    if bio:
        role.bio = bio[0].text_content()
    else:
        role.bio = ""
    
    # videos: delete later videos which have the same ID.
    videos = role.root.xpath("//li[@data-video-id]")
    raw_video_names = [video.xpath("./a/text()") for video in videos]
    raw_video_ids = [video.xpath("./@data-video-id") for video in videos]
    role.video_names = []
    role.video_ids = []
    used_ids = []
    for name, _id in zip(raw_video_names, raw_video_ids): 
        if _id not in used_ids:
            role.video_names.append(name)
            role.video_ids.append(_id)
            used_ids.append(_id)
    assert len(role.video_names) == len(role.video_ids)
           
    role.skill_links = [x.split("?")[0] for x in role.root.xpath("//div[@class='role-model__skills slider']//a/@href")]
    role.skill_names = list(map(str.strip, role.root.xpath("//div[@class='role-model__skills slider']//div[@class='listing__title']/text()")))
    
    assert len(role.skill_names)== len(role.skill_links)
    return role

def index_video_index(video_index_url):
    index = Record(video_index_url)
    index.video_urls = [x.partition("?")[0] for x in index.root.xpath("//div[@class='page__video-listing']//ul[@class='listing']//a/@href")]
    resources = index.root.xpath("//ul[@class='resource-listing']")
    index.resource_names = [resource.xpath(".//*[@class='resource-listing__title']/a")[0].text_content() for resource in resources]
    index.resource_download_urls = [full_url(resource.xpath(".//*[@class='resource-listing__title']/a/@href")[0]) for resource in resources]
    index.resource_descriptions = [resource.xpath(".//*[@class='resource-listing__summary']")[0].text_content() for resource in resources]
    return index

def all_jobs():
    cluster = index_cluster("https://www.careergirls.org/explore-careers/careers/")
    for job_url in cluster.jobs:
        yield index_job(job_url)

def all_life_skills():
    response = requests.get("https://www.careergirls.org/be-empowered/develop-life-skills/")
    root = lxml.html.fromstring(response.content)
    skill_urls = root.xpath("//li[contains(@class,'listing__item')]/a/@href")
    for url in skill_urls:
         yield index_skill(url)
 

if __name__ == "__main__":
    index= (index_video_index("https://www.careergirls.org/be-empowered/develop-life-skills/"))
    print (index)
    for video_url in index.video_urls:
        print (index_video(video_url))
    
if __name__ == "__main__2":
    app = index_job("https://www.careergirls.org/career/architect/").app
    with open("app.zip", "wb") as f:
        f.write(app)
    
    response = requests.get(super_cluster_url)
    root = lxml.html.fromstring(response.content)
    hrefs = root.xpath("//a[./div[@class='cluster-listing__title']]/@href")
    hrefs = [full_url(url) for url in hrefs]
    
        
    print (index_role("https://www.careergirls.org/role-model/cultural-anthropologist/").keys())
    
    print(index_skill("https://www.careergirls.org/video/importance-of-math/"))
    
    #for cluster_url in hrefs:
    #    cluster = index_cluster(cluster_url)
    #    print (cluster.jobs)


