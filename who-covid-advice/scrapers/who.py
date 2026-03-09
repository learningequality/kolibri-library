import os

from bs4 import BeautifulSoup
from le_utils.constants import content_kinds
from ricecooker.classes import nodes, files
from webmixer.scrapers.pages.base import PDFScraper, HTMLPageScraper, VideoScraper, WebVideoScraper
from webmixer.scrapers.pages.fullscreen import FullscreenPageScraper
from webmixer.scrapers.tags import LinkTag
from webmixer.utils import get_absolute_url


class ContentNodeMixin:
    def to_contentnode(self, title, directory=None, *args, **kwargs):
        # Generate a node based on the kind attribute
        filepath = self.to_file(directory=directory)
        if self.kind == content_kinds.HTML5:
            return nodes.HTML5AppNode(
                source_id=self.url,
                title=title,
                files=[files.HTMLZipFile(filepath)],
                **kwargs
            )
        elif self.kind == content_kinds.VIDEO:
            return nodes.VideoNode(
                source_id=self.url,
                title=title,
                files=[files.VideoFile(filepath)],
                **kwargs
            )


class ThumbnailTag(LinkTag):
    default_ext = '.png'                       # Automatically write files to have extension png
    directory = "img"                          # Write files to img folder in zip
    selector = ('div', {'class': 'sf-image'})  # Process elements with this selector
    scrape_subpages = False                    # Don't scrape linked subpages automatically

    # If any of the urls match the test method on this,write a fullscreen
    # preview page to the zipfile for the given file type (self.link)
    extra_scrapers = [FullscreenPageScraper]

    def process(self):
        # Replace images with linked images
        self.link = self.get_link()
        if 'sf-image' in self.tag['class']:
            div_tag = self.create_preview_tag(self.tag.find('img'))

            # If image is inside a link, replace the parent link with the new linked image
            if self.tag.parent.name == 'a':
                self.tag.parent.replaceWith(div_tag)
            else:
                self.tag.replaceWith(div_tag)

    ##### Helper functions #####

    def format_url(self, url):
        # web-prod urls don't work, so replace with regular www
        return get_absolute_url('https://www.who.int', url).replace('https://web-prod', 'https://www')

    def get_link(self):
        # Try to use the image if possible, otherwise use the immediate child or parent link
        img = self.tag.find('img')
        if img:
            link = img.get('src') or img.get('data-src') or ''
        else:
            link = self.tag.find('a') or self.tag.find_parent('a')
            link = link and link['href']
        return self.format_url(link)

    def create_preview_tag(self, img):
        """
            Creates a linked image to a fullscreen page of the file at self.link
            Args:
                img (BeautifulSoup img tag): in case self.link doesn't point to an image
            Returns
                <div>
                    <a href='link to fullscreen page'>
                        <img src='path to scraped image file'>
                    </a>
                </div>
        """
        # Create elements
        div_tag = self.create_tag('div')
        link_tag = self.get_scraper().to_tag()

        # Download images to zipfile if they haven't been downloaded already
        img_url = img.get('data-src') or img.get('src')
        if not img_url.startswith('img'):
            img['src'] = self.write_url(self.format_url(img_url), directory='img')
        img['style'] = []  # Some images have a display: none rule, so get rid of those
        self.mark_tag_to_skip(img)  # Add class so other tags don't try to scrape it again

        # Add img and link tags to div tag
        link_tag.append(img)
        div_tag.append(link_tag)
        return div_tag


class HighlightWidgetTag(ThumbnailTag):
    """
        Scrapes boxes that are linked on page
        e.g. https://www.who.int/emergencies/diseases/novel-coronavirus-2019/advice-for-public

        There are several ways these should be handled:
        - Top boxes linking to other pages that will be scraped later should be removed (e.g. Myth-busters)
        - Orange boxes linking to other pages should be replaced with copy link messages
        - Blue download boxes should be replaced by thumbnails
    """
    selector = ('div', {'class': 'highlight-widget'})   # Select elements that match this selector

    def process(self):
        # Remove items that aren't linked
        if not self.tag.find('a'):
            self.tag.decompose()
            return

        self.link = self.get_link()

        # Don't scrape main links
        if 'horizontal-title-only' in self.tag['class']:
            self.tag.decompose()

        # Links to other pages
        elif 'image-on-top' in self.tag['class']:
            self.create_external_link_tag()

        # Infographics
        elif 'title-only' in self.tag['class']:
            # Not all links have available thumbnails, so make one
            # e.g. https://www.who.int/emergencies/diseases/novel-coronavirus-2019/advice-for-public
            #       see last item on "Protect yourself and others from getting sick" section
            img = self.tag.parent.find('img')
            if not img:
                img = self.create_tag('img')
                img['src'] = self.link
                preview_tag = self.create_preview_tag(img)
                self.tag.replaceWith(preview_tag)

            # Some links point to pdfs, so make sure to link those instead
            elif self.link.split('?')[0].endswith('.pdf'):
                preview_tag = self.create_preview_tag(img)
                self.tag.replaceWith(preview_tag)

            # Otherwise, delete the thumbnail because it should have already been handled by ThumbnailTag
            else:
                self.tag.decompose()

    ##### Helper functions #####

    def get_link(self):
        link = self.tag.find('a') or self.tag.find_parent('a')
        return link and self.format_url(link['href'])

    def create_external_link_tag(self):
        """
            Some highlight widgets are links to other pages within the WHO site
            e.g. https://www.who.int/emergencies/diseases/novel-coronavirus-2019/advice-for-public
                 see "#HealtyAtHome Campaigns" section

            Instead of scraping those pages, create the following layout:
                Header with the text on the widget
                Image that was used on the widget
                Copy link generated by webmixer

            Example in channel: https://studio.learningequality.org/channels/a1239cf0220a5f8cb633d6d1cafcb9a2/edit/a1239cf/f66a9e4
        """
        # Create header
        div = self.create_tag('div')
        div['style'] = 'margin-bottom: 48px;text-align: center;'
        h3 = self.create_tag('h3')
        h3.string = self.tag.text.strip()
        div.append(h3)

        # Add image
        if self.tag.find('div', {'class': 'background-image'}):
            img = self.create_tag('img')
            img_url = self.tag.find('div', {'class': 'background-image'})['data-image']
            img['src'] = self.write_url(img_url, directory="img")
            img['style'] = 'max-width: 450px; width: 100%;'
            self.mark_tag_to_skip(img)
            div.append(img)

        # Add broken link copy
        copy = self.create_copy_link_message(self.link)
        div.append(copy)
        self.tag.parent['class'] = []
        self.tag.replaceWith(div)


class FigureTag(HighlightWidgetTag):
    # Process items with this selector
    selector = ('div', {'class': 'sf-multimedia-item__infographic'})

    def process(self):
        """
            Replaces the figure with an image tag that links to a fullscreen page
        """
        self.link = self.get_link()
        img = self.create_tag('img')
        img['src'] = self.link
        preview_tag = self.create_preview_tag(img)
        self.tag.replaceWith(preview_tag)


class ExternalLinkTag(LinkTag):
    """
        Automatically replace links with copy link message if they
        weren't handled in the previous methods
        (Inherits ('a',) selector from LinkTag)
    """
    def process(self):
        if self.link:
            self.tag.replaceWith(self.create_copy_link_message(self.link))


class WHOPageScraper(HTMLPageScraper, ContentNodeMixin):
    """
        Scraper for handling WHO pages and converting them to HTML zips
        e.g. https://www.who.int/emergencies/diseases/novel-coronavirus-2019/advice-for-public
    """

    color = "#008DC9"           # Generate copy link text in WHO blue
    scrape_subpages = False     # If there are links on the page, don't scrape those linked pages

    # Other tags to look out for (will use if the selector matches)
    # Order determines which ones should be scraped first
    extra_tags = [
        FigureTag,
        ThumbnailTag,
        HighlightWidgetTag,
        ExternalLinkTag
    ]

    # Automatically remove these sections of the page
    omit_list = [
        ('script',),
        ('header',),
        ('ul', {'class': 'sf-breadscrumb'}),
        ('footer', {'id': 'sf-footer'}),
        ('input', {'type': 'hidden'}),
    ]


    @classmethod
    def test(self, url):
        """ test if this scraper can be used on this url """
        return 'www.who.int' in url

    def preprocess(self, contents):
        """ This method is called before the main scraping occurs """

        # Remove side navigation
        navigation = contents.find('div', {'class': 'left-navigation--wrapper'})
        navigation.parent.decompose()

        # Styling is based on sf-body class, so add it to the main wrapper
        main_row = contents.find('div', {'class': 'row'})
        main_row['class'].append('sf-body')

    def to_tag(self, *args):
        """ Don't do anything for to_tag method """
        return self.create_tag('div')


class WHOVideoScraper(VideoScraper, ContentNodeMixin):
    # Subclassing to take advantage of ContentNodeMixin
    pass


class WHOWebVideoScraper(WebVideoScraper, ContentNodeMixin):
    # Subclassing to take advantage of ContentNodeMixin
    pass
