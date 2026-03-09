#!/usr/bin/env python
# -*- coding: UTF-8 -*-
import os
from ricecooker.utils import downloader
from ricecooker.config import LOGGER              # Use LOGGER to print messages
import cssutils
import logging
from le_utils.constants import content_kinds
cssutils.log.setLevel(logging.FATAL)

from utils import EXCEPTIONS, BasicScraper, BrokenSourceException, UnscrapableSourceException, MESSAGES

class BasicScraperTag(BasicScraper):
    default_attribute = 'src'
    default_ext = None
    directory = None
    config = None # Any additional updates to the tags
    scrape_subpages = True
    selector = None
    extra_scrapers = None

    def __init__(self, tag, url, attribute=None, scrape_subpages=True, extra_scrapers=None, color='rgb(153, 97, 137)', **kwargs):
        """
            tag (BeautifulSoup tag): tag to scrape
            attribute (str): tag's attribute where link is found (e.g. 'src' or 'data-src')
        """
        super(BasicScraperTag, self).__init__(url, **kwargs)
        self.config = self.config or {}
        self.tag = tag
        self.attribute = attribute or self.default_attribute
        self.link = self.tag.get(self.attribute) and self.get_relative_url(self.tag.get(self.attribute)).strip('%20')
        self.scrape_subpages = scrape_subpages
        self.extra_scrapers = extra_scrapers or []
        self.color = color

    def format_url(self, zipper_path):
        if '#' in self.link:
            zipper_path += '#' + self.link.split('#')[-1]
        if '?' in self.link:
            zipper_path += '?' + self.link.split('?')[-1]
        return zipper_path

    def scrape(self):
        if 'skip-scrape' in (self.tag.get('class') or []):
            return
        try:
            for key, value in self.config.items():
                if key == 'style':
                    self.tag[key] = ';'.join([(self.tag.get(key) or '').rstrip(';'), value])
                else:
                    self.tag[key] = value
            self.mark_tag_to_skip(self.tag)
            return self.process()
        except EXCEPTIONS as e:
            LOGGER.warning('Broken source found at {} ({})'.format(self.url, self.link))
            self.handle_error()
        except UnscrapableSourceException:
            LOGGER.warning('Unscrapable source found at {} ({})'.format(self.url, self.link))
            self.handle_unscrapable()
        except KeyError as e:
            LOGGER.warning('Key error at {} ({})'.format(self.url, str(e)))

    def process(self):
        self.tag[self.attribute] = self.format_url(self.write_url(self.link))
        return self.tag[self.attribute]

    def handle_error(self):
        self.tag.replaceWith(self.create_broken_link_message(self.link))

    def handle_unscrapable(self):
        self.tag.replaceWith(self.create_copy_link_message(self.link))


class ImageTag(BasicScraperTag):
    default_ext = '.png'
    directory = "img"
    selector = ('img',)

    def process(self):
        if self.link and 'data:image' not in self.link:
            return super(ImageTag, self).process()

class MediaTag(BasicScraperTag):
    directory = "media"
    config = {
        'controls': 'controls',
        'preload': 'auto'
    }
    def process(self):
        if self.tag.find('source'):
            for source in self.tag.find_all('source'):
                self.source_class(source, self.zipper, self.url)
        else:
            return super(MediaTag, self).process()

class SourceTag(BasicScraperTag):
    selector = ('source',)

    def handle_error(self):
        self.tag.decompose()

class AudioSourceTag(SourceTag):
    default_ext = '.mp3'

class VideoSourceTag(BasicScraperTag):
    default_ext = '.mp4'

class AudioTag(MediaTag):
    default_ext = '.mp3'
    source_class = AudioSourceTag
    selector = ('audio',)

class VideoTag(MediaTag):
    default_ext = '.mp4'
    source_class = VideoSourceTag
    selector = ('video',)

class StyleTag(BasicScraperTag):
    default_ext = '.css'
    default_attribute = 'href'
    directory = 'css'
    selector = ('link', {'rel': 'stylesheet'})

    def process(self):
        if 'fonts' in self.link:  # Omit google fonts
            self.tag.decompose()
            return

        # Parse urls in css (using parseString because it is much faster than parseUrl)
        style_sheet = downloader.read(self.link).decode('utf-8-sig', errors='ignore')
        sheet = cssutils.parseString(style_sheet)
        for css_url in cssutils.getUrls(sheet):
            if not css_url.startswith('data:image') and not css_url.startswith('data:application'):
                try:
                    style_sheet = style_sheet.replace(css_url, os.path.basename(self.write_url(css_url, url=self.link, default_ext='.png')))
                except EXCEPTIONS as e:
                    LOGGER.warn('Unable to download stylesheet url at {} ({})'.format(self.url, str(e)))

        self.tag[self.attribute] = self.format_url(self.write_contents(self.get_filename(self.link), style_sheet))
        return self.tag[self.attribute]

    def handle_error(self):
        self.tag.decompose()

class ScriptTag(BasicScraperTag):
    directory = 'js'
    default_ext = '.js'
    selector = ('script',)

    def process(self):
        if self.tag.string and 'google' in self.tag.string:
            self.tag.decompose()
        elif not self.link:
            return
        elif 'google' in self.link:
            self.tag.decompose()
        else:
            return super(ScriptTag, self).process()

    def handle_error(self):
        self.tag.decompose()


class LinkedPageTag(BasicScraperTag):
    def get_scraper(self):
        from pages import DEFAULT_PAGE_HANDLERS
        for handler in (DEFAULT_PAGE_HANDLERS + self.extra_scrapers):
            if handler.test(self.link):
                return handler

        downloader.read(self.link) # Will raise an error if this is broken
        raise UnscrapableSourceException


class EmbedTag(LinkedPageTag):
    default_ext = '.pdf'
    directory = 'files'
    config = {
        'style': 'width:100%; height:500px;max-height: 100vh'
    }
    selector = ('embed',)

    def process(self):
        scraper_class = self.get_scraper()
        scraper = scraper_class(self.link, locale=self.locale, triaged=self.triaged, zipper=self.zipper)
        scraper.to_zip(filename=self.get_filename(self.link))


class LinkTag(LinkedPageTag):
    default_attribute = 'href'
    default_ext = '.html'
    config = {
        'target': ''
    }
    selector = ('a',)

    def process(self):
        if not self.link or 'javascript:void' in self.link \
            or self.tag[self.attribute].startswith("#") or self.tag[self.attribute] == '/':
            return
        elif 'mailto' in self.link:
            self.tag.replaceWith(self.tag.text)
        elif 'creativecommons.org' in self.link:
            # Some links use the image as the link
            new_text = self.create_tag('b')
            new_text.string = self.tag.find('img').get('alt') if self.tag.find('img') else self.tag.text
            self.tag.replaceWith(new_text)

        elif not self.scrape_subpages:
            self.handle_error()

        elif not self.triaged.get(self.link):
            self.triaged[self.link] = self.get_filename(self.link)

            if not self.zipper.contains(self.triaged[self.link]):
                scraper_class = self.get_scraper()
                scraper = scraper_class(self.link, locale=self.locale, triaged=self.triaged, zipper=self.zipper)
                self.triaged[self.link] = scraper.to_zip()
            self.tag[self.attribute] = self.triaged[self.link]
        else:
            self.tag[self.attribute] = self.triaged[self.link]

    def handle_error(self):
        img = self.tag.find('img')
        if img:
            self.tag.replaceWith(img)
        else:
            self.tag.replaceWith(self.tag.text)
            self.tag['style'] = 'font-weight: bold;'

    def handle_unscrapable(self):
        new_tag = self.create_tag('span')
        bold_tag = self.create_tag('b')
        bold_tag.string = self.tag.text
        new_tag.append(bold_tag)
        new_tag.append('({})'.format(self.link))
        self.tag.replaceWith(new_tag)


class IframeTag(LinkedPageTag):
    selector = ('iframe',)
    default_ext = '.html'
    config = {
        'style': 'resize: both;'
    }


    def process(self):
        if not self.link:
            pass
        elif 'googletagmanager' in self.link or 'googleads' in self.link:
            self.tag.decompose()
        else:
            scraper_class = self.get_scraper()
            scraper = scraper_class(self.link, locale=self.locale, triaged=self.triaged, zipper=self.zipper)

            if scraper.kind != content_kinds.HTML5:
                new_tag = scraper.to_tag()
                self.tag.replaceWith(new_tag)
                self.tag = new_tag
            else:
                self.tag[self.attribute] = scraper.to_zip()

COMMON_TAGS = [
    ImageTag,
    StyleTag,
    ScriptTag,
    VideoTag,
    AudioTag,
    EmbedTag,
    LinkTag,
    IframeTag,
]
