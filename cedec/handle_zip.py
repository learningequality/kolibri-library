from zipfile import ZipFile

import lxml.html
import hashlib
from urllib.parse import urlparse, urljoin
from foundry.bits import get_resource, nice_ext
from lxml_tools import globalise, handle_youtube, NoVideoError
import os

from youtube_dl.utils import DownloadError

ALLOYDIR = "__alloy"
try:
    os.mkdir(ALLOYDIR)
except:
    pass

# html_bytes

URL_ATTRS = ['src', 'href']

def debug(*s):
    print(*s)

class NeoFoundry(object):
    def __init__(self):
        self.domains = []
        self.files = {}


    def alloy(self, html_bytes):
        """Modify the relevant HTML to create a structure suitable for becoming a HTML5App"""
        root = lxml.html.fromstring(html_bytes)

        for attr in URL_ATTRS:
            tags = root.xpath("//*[@{}]".format(attr))
            for tag in tags:
                bail = False
                attribute_value = tag.attrib[attr]
                debug("TAG ATTR:", attribute_value)

                # ignore certain tags
                for starter in ["#", "mailto:", "javascript:"]:
                    if attribute_value.startswith(starter):
                        debug("STARTER", starter)
                        bail = True
                if bail: continue
                if not urlparse(attribute_value).netloc: continue # local URL, ignore.

                absolute_value = urljoin("http://foo.com", tag.attrib[attr])
                del attribute_value  # don't use relative URL again
                tag_domain = urlparse(absolute_value).netloc # www.youtube.com

                # handle offsite links: youtube, others
                if "youtube.com" in tag_domain or "youtu.be" in tag_domain: # or "vimeo.com" in tag_domain:
                    debug(lxml.html.tostring(tag))
                    try:
                        filename = handle_youtube(tag, path=ALLOYDIR)  # placeholder, do something with file
                    except DownloadError:
                        continue  # Permament error, e.g. video gone, copyright, geolocked
                    except NoVideoError:
                        continue
                    except Exception as e:
                        print (tag, e, str(e))
                        raise
                    self.files[filename] = filename
                    if "target" in tag.attrib:
                        del(tag.attrib['target'])
                    tag.attrib[attr] = filename
                    tag.attrib['youtube'] = 'youtube'

                if tag_domain not in self.domains and tag.tag=="a" and 'youtube' not in tag.attrib:
                    globalise(tag)
                    continue

                # TODO: handle links which are indirectly resources with a callback here.
                # TODO: correctly handle HTML resources ... somehow!

                if absolute_value in self.files:
                    # If already handled this URL, rewrite and don't download
                    tag.attrib[attr] = self.files[absolute_value]
                    continue

                response = get_resource(absolute_value)
                if response is None:
                    debug("Bad link", absolute_value)
                    continue # bail out either way.

                # We now have a resource (specifically: request response) we must save.
                extension = nice_ext(response)
                filename = hashlib.sha1(absolute_value.encode('utf-8')).hexdigest() + extension
                self.files[absolute_value] = filename
                tag.attrib[attr] = filename
        self.alloyed = lxml.html.tostring(root)
        return self.alloyed

####

# based on https://stackoverflow.com/questions/25738523/how-to-update-one-file-inside-zip-file-using-python?lq=1

def updateZip(zipname_in, zipname_out, new_html, files): # new_html is dict of filename:filename
    # create a temp copy of the archive without filenames
    with ZipFile(zipname_in, 'r') as zin:
        with ZipFile(zipname_out, 'w') as zout:
            zout.comment = zin.comment # preserve the comment
            for item in zin.infolist():
                if item.filename not in new_html.keys():
                    zout.writestr(item, zin.read(item.filename))
                else:
                    print ("Replacing ", item.filename)
                    zout.writestr(item.filename, new_html[item.filename])
            print ("FILES:", files)
            for filename in files:
                if filename and not filename.startswith("http"):
                    print ("Adding ", files[filename])
                    zout.write(filename, files[filename])
####

def handle_zip(in_zip, out_zip):
    htmls = {}
    files = {}
    with ZipFile(in_zip, "r") as zf:
        for htmlfilename in [x for x in zf.namelist() if x.endswith("html")]:
            with zf.open(htmlfilename) as htmlf:
                html = htmlf.read()
                foundry = NeoFoundry()
                foundry.alloy(html)
                new_html = foundry.alloyed
                files.update(foundry.files)
            htmls[htmlfilename] = new_html
    updateZip(in_zip, out_zip, htmls, files)


if __name__ ==  "__main__":
    in_zip = "in.zip"
    out_zip = "demo.zip"
    handle_zip(in_zip, out_zip)

