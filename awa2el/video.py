import csv
import requests
import re
import requests_cache
requests_cache.install_cache()
from headers import headers

def whitelist_f():
    with open("nashmi_list.txt") as f:
        l = [x.split("\t") for x in f.read().strip("\n").split("\n")]
    return {x[1]: x[0] != "no" for x in l}
whitelist = whitelist_f()

def get_video_urls(url):
    r = requests.get(url, headers=headers)
    print (len(r.content), url)
    try:
        files = re.findall(b'{"file":"([^"]+)"}', r.content)
    except:
        print ("NO VIDEO: {}".format(url))
        return []
    return files

def videos():
    with open('nashmi.csv', newline='') as csvfile:
        csviter = csv.reader(csvfile, delimiter=',', quotechar='"')
        header = True
        for top_URL, topname, middlename, lowername, url in csviter:
            if header:
                header = False
                continue
            if whitelist[middlename]:
                yield ((topname, middlename, lowername), get_video_urls(url))
            
if __name__ == "__main__":
    print (len(list(videos())))
