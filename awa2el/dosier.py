import csv
import requests
import re
import requests_cache
requests_cache.install_cache()
from headers import headers
import lxml.html
from urllib.parse import urljoin
import subprocess
import os
import re
FNULL = open(os.devnull, 'w')

def convert(filename):
    q = subprocess.check_output(["soffice", "--headless",
                                 "--convert-to", "pdf",
                                 "--outdir", "temp",
                                 filename], stderr=FNULL)
    assert q != b'' # bad filename?
    g = re.search(b"convert [^ ]+ -> ([^ ]+) using", q).group(1)
    assert (g)
    return g

def docs():
    i = 0
    with open('awa2el.csv', newline='') as csvfile:
        csviter = csv.reader(csvfile, delimiter=',', quotechar='"')
        header = True
        for i, (top_URL, title, b1, b2, b3, b4, p1, p2, p3, p4) in enumerate(csviter):
            if header:
                assert top_URL == "URL"
                header = False
                continue
            html = requests.get(top_URL).content
            root = lxml.html.fromstring(html)
            #bread = [x.text_content().strip() for x in root.xpath("//div[@class='grade-and-subject']//li")]
            bread = [x for x in [b1, b2, b3, b4] if x]

            links = root.xpath("//a[@class='card-file__link']/@href")
            linknames = [x.text_content().strip() for x in root.xpath("//a[@class='card-file__link']")]
            full_links = [urljoin(top_URL, l) for l in links]
            for link,linkname in zip(full_links, linknames):
                r = requests.get(link).content
                i=i+1
                fn = "temp/{}".format(i)
                with open(fn, "wb") as f:
                    f.write(r)
                magic = subprocess.check_output(["file", fn])
                if b'PDF' not in magic:
                    fn = convert(fn)
           #     print(title, bread, link, linkname)
              
                yield {"url": top_URL,
                       "title": title,
                       "bread": bread, 
                       "link": link,
                       "linkname": linkname,
                       "filename": fn}
                    
if __name__ == "__main__":
    
    for d in docs():
        pass
        #print (d)
