import requests
import requests_cache
import lxml.html
import templater
from foundry import foundry
requests_cache.install_cache()
foundry.DEBUG = True
url = "https://global-asp.github.io/storybooks-minnesota/stories/es/0087/"

# TODO
# get level, full audio, diff language headings
# get all langs

class Book(object):
    svg_replace = {"pencil": "author",
                   "art": "artist",
                   "megaphone": "narrator",
                   "language": "language",
                   "level": "level",
                   "global": "translator"}

    def get_text(self, query):
        """There's exactly one tag"""
        tag, = self.xpath(query)
        return tag.text_content()

    def __init__(self, url):
        print(url)
        self.url = url
        html = requests.get(url).content
        root = lxml.html.fromstring(html)
        self.xpath = root.xpath
        self.svg_tagged()
        self.cover = self.cover_url()
        self.coveraudio = self.cover_audio_url()
        self.title = self.get_title()
        self.pages()

    def get_title(self):
        return self.get_text("//h1/span[@class='def']")

    def license(self):
        cc = []
        url = self.xpath("//div[@id='colophon']//a[contains(@href,'commons')]/@href")[0]
        print(url)
        url_bit = url.partition("licenses")[2]
        for bit in ["by", "nc", "sa", "nd"]:
            if bit in url_bit:
                cc.append(bit.upper())
        return "CC "+"-".join(cc)

    def cover_url(self):
        return self.xpath("//div[@id='text01']//img[@class='img-responsive']/@src")[0]

    def cover_audio_url(self):
        return self.xpath("//div[@id='text01']//audio/@src")[0]

    def svg_tagged(self):
        svg_tags = self.xpath("//img[@class='cover-icon']")
        for svg_tag in svg_tags:
            svg_name = svg_tag.xpath("./@src")[0].split("/")[-1].partition(".")[0]
            value = svg_tag.xpath(".//../..")[0].text_content().strip()
            if value:
                setattr(self, Book.svg_replace[svg_name], value)

    def pages(self):
        self.texts = []
        self.imgs = []
        self.audios = []
        self.foreigns = []
        all_page_tags = self.xpath("//div[starts-with(@id, 'text')]")
        page_tags = [x for x in all_page_tags if x.attrib["id"] != "text01"]
        assert len(page_tags) != len(all_page_tags)
        for page_tag in page_tags:
            text, img, audio, foreign = self.parse_page(page_tag)
            self.texts.append(text)
            self.imgs.append(img)
            self.audios.append(audio)
            self.foreigns.append(foreign)

    def parse_page(self, tag):
        text = tag.xpath(".//h3")[0].text_content().strip().replace("\n", " ")
        foreign = tag.xpath(".//h3")[2].text_content().strip().replace("\n", " ")
        img = tag.xpath(".//img[@class='img-responsive']/@src")[0]
        audio = tag.xpath(".//audio/@src")[0]
        return text, img, audio, foreign

#book = Book(url)
#html = templater.Carousel(book).html()

class MyFoundry(foundry.Foundry):
    def melt(self):
        "just take it from Carousel"

        self.book = Book(self.url)
        self.raw_content = templater.Carousel(self.book).html().encode('utf-8')

    def centrifuge(self, callback=None):
        "null centrifuge"
        self.centrifuged = self.raw_content

    def license(self):
        return self.book.license()



if __name__ == "__main__":
    f = MyFoundry(url)
    print (f.book)
