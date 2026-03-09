import lxml.html
import login
import json
import index
import logging

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s %(levelname)s %(message)s',
                    filename='log_detail.txt',
                    filemode='w')

session = login.session

class Page():
    def __init__(self, url):
        self.url = url
        self.response = session.get(url)
        self.root = lxml.html.fromstring(self.response.content)

url_1 = "https://www.aldarayn.com/course/view.php?id=525" # videos
# url_2 = "https://www.aldarayn.com/course/view.php?id=614" # wiz

def is_known(url, known_list):
    results = [item in url for item in known_list]
    return any(results)

def filter_urls(urls):
    # to consider: /mod/folder/
    bad_url_patterns = ["/forum/", "/wiziq/", "/mod/url/"]
    page_url_patterns = ["/mod/page/"]
    good_url_patterns = page_url_patterns + []
    reduced_urls = [url for url in urls if not is_known(url, bad_url_patterns)]
    unknown_urls = [url for url in reduced_urls if not is_known(url, good_url_patterns)]
    page_urls = [url for url in urls if is_known(url, good_url_patterns)]
    for u in unknown_urls:
        logging.info('unknown url: {}'.format(u))
    return [page_urls, None]  # placeholders for more patterns

def handle_page(url):
    video_list = []
    page = Page(url)
    try:
        body, = page.root.xpath("//ul[@class='section img-text']")
    except ValueError:
        body, = page.root.xpath("//section[@id='region-main']") ## subpage
    raw_activity_urls = body.xpath("//div[@class='activityinstance']/a/@href")
    page_urls, _ = filter_urls(raw_activity_urls)
    # print (("{} pages").format(len(page_urls)))
    for page_url in page_urls:
        video_list.extend(handle_page(page_url))

    videos = body.xpath(".//video")
    for video in videos:
        try:
            data_setup = video.get("data-setup")
            j_data = json.loads(data_setup)
            src = j_data['sources'][0]['src']
            src = src.replace("&amp;", "&")
            video_list.append(src)
        except:
            logging.info("unparsed video tag: {}".format(lxml.html.tostring(video)))

    iframes = body.xpath(".//iframe")
    for iframe in iframes:
        src = iframe.get("src")
        if "youtube" in src:
            video_list.append(src)

    if not video_list:
        logging.info("No videos: {}".format(url))
    # print (len(video_list))
    return video_list



if __name__ == "__main__":
    for _id, name1, name2, url in index.all_courses():
        #print (name1, name2, url)
        try:
            handle_page(url)
        except Exception as e:
            print (e, url)
            raise



#handle_page(url_1)
#handle_page(url_2)
