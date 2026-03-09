import requests
import lxml.html
import subprocess
from subprocess import PIPE
from pathlib import Path
import os
import requests_cache
import zipfile
from collections import namedtuple
from urllib.parse import urlparse
import handle_zip
import ftfy

Metadata = namedtuple("Metadata", ["title", "author", "description"])

requests_cache.install_cache()
ELP = Path("elp/")
ZIP = Path("zip/")

my_env = os.environ.copy()
my_env["PYTHONIOENCODING"] = "utf-8"

ns={'exe': 'http://www.exelearning.org/content/v0.3'}

def elp_metadata(elp_filename):
    def query(s):
        response, = root.xpath("/exe:instance/exe:dictionary/exe:string[@value='"+s+"']/following-sibling::exe:unicode[1]/@value", namespaces=ns)
        return ftfy.fix_text(response)

    with zipfile.ZipFile(elp_filename, "r") as zf:
        with zf.open("contentv3.xml", "r") as xml:
            data = xml.read()
            root = lxml.etree.fromstring(data)
            return Metadata(query('_title'), query('_author'), query('_description'), )

def zipscan(zip_filename):
    with zipfile.ZipFile(zip_filename, "r") as zf:
        htmlfiles = [x for x in zf.namelist() if x.endswith("html")]
        print (htmlfiles)
        for htmlfilename in htmlfiles:
            with zf.open(htmlfilename) as htmlfile:
                root = lxml.html.fromstring(htmlfile.read())
                for href in root.xpath("//@href"):
                    domain =  urlparse(href).netloc
                    if domain and domain != "creativecommons.org":
                        print ("HREF", href)
                for src in root.xpath("//@src"):
                    domain =  urlparse(src).netloc
                    if domain and domain != "creativecommons.org":
                        print ("SRC", src)

def elp_to_zip(elp_url):
    print()
    print(elp_url)
    filename = elp_url.partition("cedec")[2].replace("/", "_")
    try:
        os.mkdir(ELP)
    except FileExistsError:
        pass
    try:
        os.mkdir(ZIP)
    except FileExistsError:
        pass
    zipfilename = filename + ".zip"
    if os.path.isfile(ELP/filename):
        print (f"WARNING: {ELP/filename} exists")
    if not os.path.isfile(ZIP/zipfilename):
        with open(ELP/filename, "wb") as f:
            f.write(requests.get(elp_url).content)
        invocation = ["exe_do", "--export", "webzip", str(ELP/filename), str(ZIP/zipfilename)]
        output = subprocess.run(invocation,
                stdout = PIPE,
                stderr = PIPE,
                env = my_env)

        stdout = output.stdout.decode('utf-8')
        stderr = output.stderr.decode('utf-8')
        print(stdout)
        print(stderr)
        assert not output.returncode
        assert "error was" not in stdout
    zipscan(ZIP/zipfilename)
    return ZIP/zipfilename, elp_metadata(ELP/filename)

# TODO - fix encoding
BASE_URL = "http://cedec.intef.es/recursos/"

html = requests.get(BASE_URL).content
root = lxml.html.fromstring(html)
root.make_links_absolute(BASE_URL)
links = root.xpath("//div[@id='icon']/a/@href")
print (links)

def index():
    for link in links:
        html = requests.get(link).content
        root = lxml.html.fromstring(html)
        root.make_links_absolute(link)
        elps = root.xpath("//a")

        for elp in elps:
            elp_url = elp.attrib['href']
            if not elp_url.endswith(".elp"):
                continue
            grouping, = elp.xpath("./preceding::h2[1]")
            title, = root.xpath("//div[contains(@id, 'post')]/h2")
            group_text = grouping.text_content().strip()
            title_text = title.text_content().strip()
            print(group_text)
            zipfilename, metadata = elp_to_zip(elp_url)
            finalzip = str(zipfilename)+".final.zip"
            handle_zip.handle_zip(zipfilename, finalzip)
            #for item in metadata:
            #    if ftfy.fix_text(item) != item:
            #        metadata[item] = ftfy.fix_text(item)
            yield metadata, finalzip, [title_text, group_text]

def no_dl_index():
    for link in links:
        html = requests.get(link).content
        root = lxml.html.fromstring(html)
        root.make_links_absolute(link)
        elps = root.xpath("//a")

        for elp in elps:
            elp_url = elp.attrib['href']
            if not elp_url.endswith(".elp"):
                continue
            grouping, = elp.xpath("./preceding::h2[1]")
            title, = root.xpath("//div[contains(@id, 'post')]/h2")
            group_text = grouping.text_content().strip()
            title_text = title.text_content().strip()
            print(group_text)

            ########
            elp_filename = elp_url.partition("cedec")[2].replace("/", "_")
            metadata = elp_metadata(ELP/elp_filename)
            zipfilename = ZIP / (elp_filename + ".zip")
            finalzip = str(zipfilename)+".final.zip"
            yield metadata, finalzip, [title_text, group_text]
