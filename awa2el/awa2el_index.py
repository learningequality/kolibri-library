import requests
import lxml.html
import requests_cache
from urllib.parse import urljoin

requests_cache.install_cache()
DOWNLOAD = False
DEBUG = False

#BASE_URL = "https://www.awa2el.net/ar/search/type/80?field_related_grade_and_subject=All&uid="
BASE_URL = "https://www.awa2el.net/ar/search/type/80?field_related_grade_and_subject={}&uid="
#BASE_URL = "https://www.awa2el.net/ar/search/type/80?field_related_grade_and_subject={}"
graderange = [453, 454, 455, 456]

def abs_link(url):
    return urljoin(BASE_URL, url)

def abs_links(urls):
    return [urljoin(BASE_URL, url) for url in urls]

class Root(object):
    def __init__(self, url):
        self.url = url
        self.html = requests.get(self.url).content
        self.root = lxml.html.fromstring(self.html)

class SearchResult(object):
    def __init__(self, node):
        self.node = node
        self.title = node.xpath(".//h5")[0].text_content().strip()
        self.author = node.xpath(".//article[@typeof='schema:Person']//span[@class='list-item__text']")[0].text_content().strip()
        self.link = abs_link(node.xpath(".//h5/a/@href")[0])
        if DEBUG: print("SEARCH: ", self)

    def details(self):
        return Detail(self.link).details()

    def __repr__(self):
        return "<Result: {} - {}>".format(self.title[:4], self.author[:4])

class SearchResultsPage(Root):
    def get_results(self):
        wrappers = self.root.xpath("//div[@class='search-content-wrapper']")
        print ("Found {} search results".format(len(wrappers)))
        for wrapper in wrappers:
            yield SearchResult(wrapper)

class SearchResults(object):
    def __init__(self, url):
        self.url = url
        self.results = []


    def get_results(self):
        page_0 = SearchResultsPage(self.url)
        try:
            max_page_link = abs_link(page_0.root.xpath(".//li[contains(@class, 'pager__item--last')]/a/@href")[0])
            max_page = int(max_page_link.split("=")[-1])
        except:
            max_page = 0
        for result in page_0.get_results():
            yield result
            self.results.append(result)

        for page in range(1, max_page+1):
            print ("Page {} of {}".format(page, max_page))
            search_page = SearchResultsPage(self.url+"&page={}".format(page)).get_results()
            for result in search_page:
                yield result
                #self.results.append(result)
        #return self.results


class Detail(Root):

    def __repr__(self):
        return ("[{}]".format(self.url))

    def details(self):
        # a hierarchy, top first. Write as if english for correct RTL.
        self.breadcrumbs = [x.text_content().strip() for x in self.root.xpath("//div[@class='grade-and-subject']//li")]
        self.pdf_urls = abs_links(self.root.xpath("//a[@class='card-file__link']/@href"))
        self.pdf_names = [x.text_content().strip() for x in self.root.xpath("//a[@class='card-file__link']/span[@class='card-file__title']")]
        try:
            self.title = self.root.xpath("//h1")[0].text_content().strip()
        except:
            self.title = ""
        if DOWNLOAD:
            self.actual_pdf = [requests.get(x).content for x in self.pdf_urls]
            for x in self.actual_pdf:
                if x[:4] != b"%PDF":
                    print(repr(x[:40]))
        return self

# &page=206 -- //a[@rel="last"]/@href

if __name__ == "__main__":
    for i, item in enumerate(SearchResults(BASE_URL.format(453)).get_results()):
        print (i, "\n", item.details())

