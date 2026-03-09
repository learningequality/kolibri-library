#!/usr/bin/env python
import logging
import scrapy
import signal
import sys

from twisted.internet import reactor
from scrapy import signals
from scrapy.crawler import CrawlerRunner

from le_utils.constants.licenses import PUBLIC_DOMAIN

from ricecooker.chefs import SushiChef
from ricecooker.classes import nodes, files, licenses
from ricecooker.config import setup_logging
from ricecooker.exceptions import raise_for_invalid_channel


# Run constants
################################################################################
CHANNEL_NAME = "Elejandria Libros"
CHANNEL_SOURCE_ID = "elejandria-libros"
CHANNEL_DOMAIN = "elejandria.com"
CHANNEL_LANGUAGE = "es"
CHANNEL_DESCRIPTION = "La biblioteca Elejandria contiene libros conocidos organizados por tema, organizados en colecciones para ayudar a los estudiantes de todas las edades a descubrir algo de su nivel de leer. Los lectores pueden encontrar cuentos de hadas, clásicos, novelas de suspenso, non-ficción y más para todos los grupos de edad."
CHANNEL_THUMBNAIL = "channel_thumbnail.png"

# Additional constants
################################################################################

DEBUG = True

logger = logging.getLogger(__name__)

setup_logging(
    level=logging.DEBUG if DEBUG else logging.INFO,
    error_log="errors.log",
    add_loggers=["scrapy"],
)

# The top-level node tree that will be appended to the ChannelNode
NODE_TREE = []

# For every book, add a counter when we meet it. Sanity check later.
# Some books are contained in a lot of collections. Example:
# https://www.elejandria.com/libro/orgullo-y-prejuicio/jane-austen/20
NODE_COUNTERS = {}

# True when the ElejandriaLibrosSpider instance finishes from its own
# thread. Used by the main thread to know that it finished and wasn't
# stopped by a signal or exception.
SPIDER_FINISHED = False

# This list is discussed elsewhere - will be finally made and approved by an
# implementing educational partner.
BOOKS_SKIPPED = [
    "76",
    "830",
    "715",
    "708",
    "712",
    "463",
    "709",
    "841",
    "713",
    "707",
    "714",
    "711",
]


class ElejandriaLibrosSpider(scrapy.Spider):
    """
    Crawls collections and categories, creates a topic for each
    collection and category.
    
    Books (leaf nodes) are duplicated, hence stored in a local key-value.
    """

    name = "elejandria-spider"

    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        spider = super().from_crawler(crawler, *args, **kwargs)
        crawler.signals.connect(spider.spider_closed, signal=signals.spider_closed)
        return spider

    def spider_closed(self, spider):
        global SPIDER_FINISHED
        SPIDER_FINISHED = True
        signal.signal(signal.SIGINT, signal.default_int_handler)
        logger.info("Spider closed: %s", spider.name)

    def start_requests(self):
        """
        This is where the spider begins: Create the top-level nodes in
        the channel tree and start crawling collections and categories.
        """
        collections_node = nodes.TopicNode(
            title="Libros organizados por colección", source_id="colecciones",
        )
        categories_node = nodes.TopicNode(
            title="Libros organizados por categoria", source_id="categorias",
        )
        NODE_TREE.append(collections_node)
        NODE_TREE.append(categories_node)
        return [
            scrapy.Request(
                "https://www.elejandria.com/categorias",
                callback=self.parse_categories,
                cb_kwargs={"node": categories_node, "top_level": True},
            ),
            scrapy.Request(
                "https://www.elejandria.com/colecciones",
                callback=self.parse_collections,
                cb_kwargs={"node": collections_node},
            ),
        ]

    def parse_categories(self, response, node, top_level=False):
        """
        Parse a category index (list of categories). This can be the
        top-level page:
        https://www.elejandria.com/categorias
        
        Or a sub-category:
        https://www.elejandria.com/categorias/literatura-y-ficcion/13
        """
        logger.debug("Parsing categories: {}".format(response.url))
        for category_link in response.css("h3.book-description a"):
            # There are two sibling <a> links, we are skipping the second one
            if "btn" in category_link.attrib.get("class", ""):
                continue
            
            # Create a TopicNode for this category and add it to tree
            title = category_link.css("::text").get()
            url = category_link.attrib["href"]
            category_node = nodes.TopicNode(title=title, source_id=url,)
            node.add_child(category_node)
            
            # Where to go next
            if top_level:
                callback=self.parse_categories
            else:
                callback=self.parse_category
            yield scrapy.Request(
                url,
                callback=callback,
                cb_kwargs={"node": category_node},
            )

    def parse_category(self, response, node):
        """
        Get all the books in a category listing and visit the book page.
        Example:
        https://www.elejandria.com/coleccion/descargar-gratis-20-libros-clasicos-para-sobrellevar-la-cuarentena
        """
        logger.debug('Parsing collection "{}": {}'.format(node.title, response.url))
        for book_link in response.css(".book div p a.primary-text-color"):
            url = book_link.attrib["href"]

            to_skip = any(
                url.endswith("/{}".format(book_id)) for book_id in BOOKS_SKIPPED
            )
            if to_skip:
                logger.debug("Skipping {}".format(url))
                continue

            title = book_link.css("::text").get()
            logger.debug("Found book link: {}".format(title))

            yield scrapy.Request(
                url,
                callback=self.parse_book,
                dont_filter=True,
                cb_kwargs={"node": node, "source_prefix": "category"},
            )

    def parse_collections(self, response, node):
        """
        Parses collections and create a TopicNode for each collection
        """
        logger.debug("Parsing collection base page: {}".format(response.url))
        for collection_link in response.css(".book-description h2 a"):
            
            # Create a TopicNode for each collection
            title = collection_link.css("::text").get()
            url = collection_link.attrib["href"]
            logger.debug("Found collection with title: {}".format(title))
            collection_node = nodes.TopicNode(title=title, source_id=url,)
            node.add_child(collection_node)

            yield scrapy.Request(
                collection_link.attrib["href"],
                callback=self.parse_collection,
                cb_kwargs={"node": collection_node},
            )

    def parse_collection(self, response, node):
        """
        Example:
        https://www.elejandria.com/coleccion/descargar-gratis-20-libros-clasicos-para-sobrellevar-la-cuarentena
        """
        logger.debug('Parsing collection "{}": {}'.format(node.title, response.url))
        for book_link in response.css(".book div p a.primary-text-color"):
            url = book_link.attrib["href"]

            to_skip = any(
                url.endswith("/{}".format(book_id)) for book_id in BOOKS_SKIPPED
            )
            if to_skip:
                logger.debug("Skipping {}".format(url))
                continue
            
            title = book_link.css("::text").get()
            logger.debug("Found book link: {} - ".format(title))

            yield scrapy.Request(
                url,
                callback=self.parse_book,
                dont_filter=True,
                cb_kwargs={"node": node, "source_prefix": "collection"},
            )

    def parse_book(self, response, node, source_prefix=""):
        """
        Parse a book page, creating the DocumentNode. This node is not
        appended to the node tree until the download page has been
        visited and a PDF/ePub has been found.
        
        Example:
        https://www.elejandria.com/libro/alicia-en-el-pais-de-las-maravillas/carroll-lewis/94
        
        :param source_prefix: Prefix a DocumentNode's source_id because the same books are added in different subtrees
        """
        logger.debug(
            "Visiting from category '{}' - parsing book page: {}".format(
                node.title, response.url
            )
        )

        # Titles are prefixed "Libro <Book Title>", so we remove this
        book_title = response.css("h1.bordered-heading::text").get()
        if book_title.startswith("Libro "):
            book_title = book_title.replace("Libro ", "", 1)
        # Names are prefixed "de <Author Name>", so we remove this
        author = response.css("h2 a.secondary-text-color::text").get()
        if author.startswith("de "):
            author = author.replace("de ", "", 1)
        thumbnail = response.css("img.img-book-cover::attr(src)").get()

        # Fetch a description based on all the text in P containers
        # There aren't really any semantic tags around this, so it's
        # probably going to break some day...
        description_paragraphs = response.css(
            "div.col-lg-8 div.row div.offset-top div.text-justify p"
        )
        
        # The last paragraph should be ignored, it's a kind of breadcrumb
        # <p><a>category</a> > <a>subcategory</a></p>
        description = ""
        for element in description_paragraphs[:-1]:
            description += "\n\n" + element.css("*::text").get()

        # Some book descriptions end with a list <ul><li>
        description_list = response.css(
            "div.col-lg-8 div.row div.offset-top div.text-justify ul li::text"
        ).getall()
        
        for sentence in description_list:
            description += "\n\n * {}".format(sentence)

        # Count book titles for later sanity checks.
        if book_title not in NODE_COUNTERS:
            NODE_COUNTERS[book_title] = 1
        else:
            NODE_COUNTERS[book_title] += 1

        document_node = nodes.DocumentNode(
            source_id="{}-{}-{}".format(
                source_prefix, NODE_COUNTERS[book_title], response.url
            ),
            title=book_title,
            license=licenses.get_license(PUBLIC_DOMAIN),
            author=author,
            provider=CHANNEL_NAME,
            description=description,
            thumbnail=thumbnail,
            files=[],
        )

        # Find ePub and PDF download buttons
        versions = {}
        for download_button in response.css("a.download-link"):
            button_text = download_button.css("::text").get() or ""
            url = download_button.attrib["href"]
            if "ePub" in button_text:
                versions["ePub"] = url
            elif "PDF" in button_text:
                versions["PDF"] = url

        # Prefer ePub, fall back to PDF
        file_cls = None
        url = None
        if "ePub" in versions:
            url = versions["ePub"]
            file_cls = files.EPubFile
        elif "PDF" in versions:
            url = versions["PDF"]
            file_cls = files.DocumentFile
        else:
            logger.error("No PDF or ePub version found: {}".format(response.url))
            return

        yield scrapy.Request(
            url,
            callback=self.parse_download,
            dont_filter=True,
            cb_kwargs={
                "document_node": document_node,
                "file_cls": file_cls,
                "parent_node": node,
            },
        )

    def parse_download(self, response, document_node, parent_node, file_cls):
        logger.debug("Visiting download page: {}".format(document_node.title, response.url))
        url = response.css(".book-description a.download-link::attr(href)").get()
        if not url:
            logger.error("Could not find download link: {}".format(url))
            return
        else:
            document_node.add_file(file_cls(url))

        # Add the node now that we know a PDF or ePub exists
        parent_node.add_child(document_node)


# The chef subclass
################################################################################
class ElejandriaLibrosChef(SushiChef):

    """
    This class uploads the Elejandria Libros channel to Kolibri Studio.
    Your command line script should call the `main` method as the entry point,
    which performs the following steps:
      - Parse command line arguments and options (run `./sushichef.py -h` for details)
      - Call the `SushiChef.run` method which in turn calls `pre_run` (optional)
        and then the ricecooker function `uploadchannel` which in turn calls this
        class' `get_channel` method to get channel info, then `construct_channel`
        to build the contentnode tree.
    For more info, see https://github.com/learningequality/ricecooker/tree/master/docs
    """

    channel_info = {
        "CHANNEL_SOURCE_DOMAIN": CHANNEL_DOMAIN,
        "CHANNEL_SOURCE_ID": CHANNEL_SOURCE_ID,
        "CHANNEL_TITLE": CHANNEL_NAME,
        "CHANNEL_LANGUAGE": CHANNEL_LANGUAGE,
        "CHANNEL_THUMBNAIL": CHANNEL_THUMBNAIL,
        "CHANNEL_DESCRIPTION": CHANNEL_DESCRIPTION,
    }

    def crawl(self):
        """
        Start Scrapy with CrawlerRunner -- it's the only way to keep it
        from calling its own configure_logging, which messes up logging
        outputs from our own configuration
        """

        # Settings add HttpCacheMiddleware, read more here:
        # https://scrapy.readthedocs.io/en/latest/topics/downloader-middleware.html

        if DEBUG:
            logger.info("Using Scrapy's cache to store HTTP responses in .scrapy/")

        runner = CrawlerRunner(
            settings={
                "HTTPCACHE_ENABLED": DEBUG,
                "HTTPCACHE_ALWAYS_STORE": DEBUG,
                # No error tolerance
                # https://doc.scrapy.org/en/latest/topics/extensions.html#closespider-errorcount
                "CLOSESPIDER_ERRORCOUNT": 1,
            }
        )
        d = runner.crawl(ElejandriaLibrosSpider)
        # d.addBoth(stop_crawling)
        d.addBoth(lambda _: reactor.stop())
        signal.signal(signal.SIGINT, stop_on_sigint)
        reactor.run()

        signal.signal(signal.SIGINT, signal.default_int_handler)

        if not SPIDER_FINISHED:
            logger.error("Spider did not finish crawling")
            runner.stop()
            # Necessary because Twisted handles signals still
            sys.exit(1)

    def check_consistency(self):
        for book, count in NODE_COUNTERS.items():
            # Most books apper twice: Once in a collection and once in
            # a category.
            if count > 2:
                logger.warning("{} appears {} times".format(book, count))
            if count > 8:
                raise AssertionError("Found the same book too many times")

    def pre_run(self, *args, **kwargs):
        self.crawl()
        self.check_consistency()

    def construct_channel(self, *args, **kwargs):
        """
        Creates ChannelNode and build topic tree
        Args:
          - args: arguments passed in on the command line
          - kwargs: extra options passed in as key="value" pairs on the command line
            For example, add the command line option   lang="fr"  and the value
            "fr" will be passed along to `construct_channel` as kwargs['lang'].
        Returns: ChannelNode
        """
        channel = self.get_channel(*args, **kwargs)

        for node in NODE_TREE:
            channel.add_child(node)

        raise_for_invalid_channel(channel)  # Check for errors in channel construction

        return channel


def stop_on_sigint(signum, stackframe):
    """
    Necessary to stop Twisted reactor from CTRL+C or sigint
    """
    reactor.callFromThread(reactor.stop)


# CLI
################################################################################
if __name__ == "__main__":

    signal.signal(signal.SIGINT, stop_on_sigint)

    # This code runs when sushichef.py is called from the command line
    chef = ElejandriaLibrosChef()
    chef.main()
