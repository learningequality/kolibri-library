#!/usr/bin/env python
# -*- coding: UTF-8 -*-
import os
from bs4 import BeautifulSoup
from ricecooker.utils import downloader, html_writer
from ricecooker.config import LOGGER              # Use LOGGER to print messages
import re
import youtube_dl
import shutil
import tempfile
import json

from le_utils.constants import content_kinds

from tags import COMMON_TAGS, VideoTag
from utils import EXCEPTIONS, BasicScraper, BrokenSourceException, UnscrapableSourceException, MESSAGES

class BasicPageScraper(BasicScraper):
    dl_directory = 'downloads'

    @classmethod
    def test(self, url):
        """ Used to determine if this is the correct scraper to use for a given url """
        raise NotImplementedError('Must implement a test method for {}'.format(str(self.__class__)))

    @classmethod
    def prefetch_filename(self, url):
        return self.get_filename(self, url)


    def preprocess(self, contents):
        """ Place for any operations to occur before main scraping method """
        # Implement in subclasses
        pass

    def process(self):
        return downloader.read(self.url)

    def postprocess(self, contents):
        """ Place for any operations to occur after main scraping method """
        # Implement in subclasses
        pass


    ##### Output methods #####
    def _download_file(self, write_to_path):
        with open(write_to_path, 'wb') as fobj:
            fobj.write(self.process())

    def to_file(self, filename=None, directory=None, overwrite=False):
        directory = directory or self.directory
        if not os.path.exists(directory):
            os.makedirs(directory)

        write_to_path = os.path.join(directory, filename or self.get_filename(self.url))

        if overwrite or not os.path.exists(write_to_path):
            self._download_file(write_to_path)

        return write_to_path

    def to_zip(self, filename=None):
        return self.write_url(self.url, filename=filename)

    def to_tag(self, filename=None):
        # Returns tag with scraped link
        raise NotImplementedError('Must implement to_tag function on {}'.format(str(self.__class__)))


######### KIND SCRAPERS ##########

class HTMLPageScraper(BasicPageScraper):
    partially_scrapable = False     # Not all content can be viewed from within Kolibri (e.g. Wikipedia's linked pages)
    scrape_subpages = True          # Determines whether to scrape any subpages within this page
    default_ext = '.html'           # Default extension when writing files to zip
    main_area_selector = None       # Place where main content is (replaces everything in <body> with this)
    omit_list = None                # Specifies which elements to remove from the DOM
    loadjs = False                  # Determines whether to load js when loading the page
    scrapers = None                 # List of additional scrapers to use on this page (e.g. GoogleDriveScraper)
    extra_tags = None               # List of additional tags to look for (e.g. ImageTag)
    color = 'rgb(153, 97, 137)'     # Color to use for messages (consider contrast when setting this)
    kind = content_kinds.HTML5      # Content kind to write to


    def __init__(self, *args, **kwargs):
        """
            url: string                                    # URL to read from
            html_writer: ricecooker.utils.html_writer      # Zip to write files to
            locale: string                                 # Language to use when writing error messages
        """
        super(HTMLPageScraper, self).__init__(*args, **kwargs)
        self.omit_list = self.omit_list or []
        self.omit_list += [
            ('link', {'type': 'image/x-icon'}),
            ('link', {'rel': 'apple-touch-icon'}),
            ('span', {'class': 'external-iframe-src'}),
            ('link', {'rel': 'icon'}),
            ('div', {'class': 'mw-indicators'})
        ]
        self.extra_tags = self.extra_tags or []
        self.scrapers = (self.scrapers or []) + [self.__class__]

    def process(self):
        # Using html.parser as it is better at handling special characters
        contents = BeautifulSoup(downloader.read(self.url, loadjs=self.loadjs), 'html.parser')

        self.preprocess(contents)

        if self.main_area_selector:
            body = self.create_tag('body')
            body.append(contents.find(*self.main_area_selector))
            contents.body.replaceWith(body)

        for item in self.omit_list:
            for element in contents.find_all(*item):
                element.decompose()

        for tag_class in (self.extra_tags + COMMON_TAGS):
            for tag in contents.find_all(*tag_class.selector):
                scraper = tag_class(tag, self.url,
                    zipper=self.zipper,
                    scrape_subpages=self.scrape_subpages,
                    triaged=self.triaged,
                    locale=self.locale,
                    extra_scrapers=self.scrapers,
                    color=self.color
                )
                scraper.scrape()
        self.postprocess(contents)

        return contents.prettify(formatter="minimal").encode('utf-8-sig', 'ignore')

    ##### Output methods #####
    def _download_file(self, write_to_path):

        with html_writer.HTMLWriter(write_to_path) as zipper:
            try:
                self.zipper = zipper
                self.to_zip(filename='index.html')
            except Exception as e:
                # Any errors here will just say index.html file does not exist, so
                # print out error for more descriptive debugging
                LOGGER.error(str(e))

    def to_file(self, filename=None, **kwargs):
        # Make sure html is being written to a zip file here
        filename = filename or self.get_filename(self.url)
        filename = filename.replace(self.default_ext, '.zip')
        return super(HTMLPageScraper, self).to_file(filename=filename, **kwargs)

    def to_zip(self, filename=None):
        return self.write_contents(filename or self.get_filename(self.url), self.process())


class SinglePageScraper(HTMLPageScraper):
    scrape_subpages = False
    loadjs = True

    @classmethod
    def test(self, url):
        ext = os.path.splitext(url.split('?')[0].split('#')[0])[1].lower()
        return not ext or ext.startswith('.htm')



class PDFScraper(BasicPageScraper):
    directory = 'docs'
    default_ext = '.pdf'
    kind = content_kinds.DOCUMENT

    @classmethod
    def test(self, url):
        return url.split('?')[0].lower().endswith('.pdf')

    def to_tag(self, filename=None):
        try:
            embed = self.create_tag('embed')
            embed['src'] = self.to_zip(filename=filename)
            embed['width'] = '100%'
            embed['style'] = 'height: 500px;max-height: 100vh;'
            return embed
        except EXCEPTIONS as e:
            LOGGER.error(str(e))
            return self.create_broken_link_message(self.url)

class ImageScraper(BasicPageScraper):
    directory = 'img'
    default_ext = '.png'
    kind = content_kinds.SLIDESHOW  # No image type in Studio, so use this

    @classmethod
    def test(self, url):
        return url.lower().endswith('.png') or url.lower().endswith('.jpg')

    def to_file(self, filename=None):
        raise NotImplementedError('Unable to write SLIDESHOW kind to a file')

    def to_tag(self, filename=None):
        try:
            img = self.create_tag('img')
            img['src'] = self.to_zip(filename=filename)
            return img
        except EXCEPTIONS as e:
            LOGGER.error(str(e))
            return self.create_broken_link_message(self.url)

class VideoScraper(BasicPageScraper):
    default_ext = '.mp4'
    kind = content_kinds.VIDEO
    dl_directory = 'videos'
    directory = 'videos'

    @classmethod
    def test(self, url):
        return url.split('?')[0].lower().endswith('.mp4')

    def to_tag(self, filename=None):
        try:
            video = self.create_tag('video')
            video['controls'] = 'controls'
            video['style'] = 'width: 100%;'
            video['preload'] = 'auto'
            source = self.create_tag('source')
            source['src'] = self.to_zip(filename=filename)
            video.append(source)
            return video
        except EXCEPTIONS as e:
            LOGGER.error(str(e))
            return self.create_broken_link_message(self.url)

class AudioScraper(BasicPageScraper):
    default_ext = '.mp3'
    kind = content_kinds.AUDIO
    directory = 'audio'

    @classmethod
    def test(self, url):
        return url.split('?')[0].lower().endswith('.mp4')

    def to_tag(self, filename=None):
        try:
            audio = self.create_tag('audio')
            audio['controls'] = 'controls'
            audio['style'] = 'width: 100%;'
            source = self.create_tag('source')
            source['src'] = self.to_zip(filename=filename)
            audio.append(source)
            return audio
        except EXCEPTIONS as e:
            LOGGER.error(str(e))
            return self.create_broken_link_message(self.url)

class FlashScraper(BasicPageScraper):
    default_ext = '.swf'
    standalone = True
    kind = 'flash'

    @classmethod
    def test(self, url):
        return url.split('?')[0].lower().endswith('.swf')

    def process(self, **kwargs):
        downloader.read(self.url) # Raises broken link error if fails
        raise UnscrapableSourceException('Cannot scrape Flash content')

    def to_tag(self, **kwargs):
        return self.process()

    def to_zip(self, **kwargs):
        return self.process()

class WebVideoScraper(VideoScraper):
    @classmethod
    def test(self, url):
        return 'youtube' in url or 'vimeo' in url


    def process(self):
        write_to_path = self.to_file()
        with open(write_to_path) as fobj:
            return fobj.read()

    def _download_file(self, write_to_path):
        try:
            dl_settings = {
                'outtmpl': write_to_path,
                'quiet': True,
                'overwrite': True,
                'format': self.default_ext.split('.')[-1],
            }
            with youtube_dl.YoutubeDL(dl_settings) as ydl:
                ydl.download([self.url])
        except (youtube_dl.utils.DownloadError, youtube_dl.utils.ExtractorError) as e:
            raise UnscrapableSourceException(str(e))  # Some errors are region-specific, so allow link


    def to_zip(self, filename=None):
        try:
            tempdir = tempfile.mkdtemp()
            video_path = os.path.join(tempdir, filename or self.get_filename(self.url))
            self._download_file(video_path)
            return self.write_file(video_path)
        except FileNotFoundError as e:
            # Some video links don't work, so youtube dl only partially downloads files but doesn't error out
            # leading to the .mp4 not being found (just a .part file)
            raise UnscrapableSourceException(str(e))
        finally:
            shutil.rmtree(tempdir)

    def to_tag(self, filename=None):
        video = self.create_tag('video')
        video['controls'] = 'controls'
        video['style'] = 'width: 100%;'
        video['preload'] = 'auto'
        source = self.create_tag('source')
        source['src'] = self.to_zip(filename=filename)
        video.append(source)
        return video

DEFAULT_PAGE_HANDLERS = [
    WebVideoScraper,
    PDFScraper,
    ImageScraper,
    FlashScraper,
    VideoScraper,
    AudioScraper,
]

########## LESS COMMON SCRAPERS (import as needed) ##########

class PresentationScraper(HTMLPageScraper):
    thumbnail = None
    source = ""
    img_selector = ('img',)
    img_attr='src'

    @classmethod
    def test(self, url):
        return False

    def process(self):
        contents = BeautifulSoup(downloader.read(self.url, loadjs=self.loadjs), 'html.parser')
        images = []
        for img  in contents.find_all(*self.img_selector):
            images.append(self.write_url(img[self.img_attr], directory="slides"))
        return self.generate_slideshow(images)

    def to_zip(self, filename=None):
        contents = self.process()
        return self.write_contents(filename or self.get_filename(self.url), contents)

    def generate_slideshow(self, images):
        # <body>
        page = BeautifulSoup('', 'html5lib')
        page.body['style'] = 'background-color: black; height: 100vh; margin: 0px;'
        page.body['class'] = ['collapsed']
        page.body['onclick'] = 'closeDropdown()'

        # <style>
        style = self.create_tag('style')
        style.string = '#gallery {width: 100vw;}\n'\
                    '#progress, #navigation, .wrapper, #gallery {max-width: 900px;}\n'\
                    'button {cursor: pointer}\n'\
                    'button:disabled { cursor: not-allowed; opacity: 0.5; }\n'\
                    'body.fullscreen .wrapper {max-width: 100%;}\n'\
                    'body.fullscreen #gallery, body.fullscreen #navigation, body.fullscreen #progress {max-width: 100%;}\n'\
                    '#counter::after { content: "▲"; padding-left: 10px; font-size: 7pt; vertical-align: middle; }\n'\
                    '#navigation-menu {list-style: none; padding: 0px; overflow-y: auto; overflow-x: none; height: 250px; max-height: 100vh;background: '\
                        'white; width: max-content; margin: 0 auto; margin-top: -275px; border: 1px solid #ddd; display: none; position: relative;}\n'\
                    '#navigation-menu li:not(:first-child) {border-top: 1px solid #ddd; }'\
                    '#navigation-menu li:hover { background-color: #ddd; }\n'

        style.string += '#progressbar {{ height: 10px; background-color: {}; transition: width 0.5s; }}'.format(self.color)

        page.head.append(style)

        # <div class="wrapper">
        wrapper = self.create_tag('div')
        wrapper['style'] = 'width: max-content; margin: 0 auto; text-align: center;'
        page.body.append(wrapper)

        # <img id="gallery"/>
        gallery = self.create_tag('img')
        gallery['id'] = 'gallery'
        gallery['style'] = 'cursor:pointer; height: auto; max-height: calc(100vh - 45px); object-fit: contain; color: white; font-family: sans-serif;'
        gallery['onclick'] = 'updateImage(1)'
        gallery['src'] = images[0]
        wrapper.append(gallery)

        # <div id="progress">
        progress = self.create_tag('div')
        progress['id'] = 'progress'
        progress['style'] = 'background-color: #4E4E4E; width: 100vw; height: 10px;'
        wrapper.append(progress)

        # <div id="progressbar">
        progressbar = self.create_tag('div')
        progressbar['id'] = 'progressbar'
        progress.append(progressbar)

        # <div id="navigation">
        navigation = self.create_tag('div')
        navigation['id'] = 'navigation'
        navigation['style'] = 'background-color:#353535; text-align:center; height: 33px; width: 100vw;'
        wrapper.append(navigation)

        # <button id="next-btn">
        nextbutton = self.create_tag('button')
        nextbutton['id'] = 'next-btn'
        nextbutton.string = '🡒'
        nextbutton['style'] = 'float:right; background-color: transparent; border: none; font-size: 17pt; color: white; width:75px; font-size:16pt;'
        nextbutton['onclick'] = 'updateImage(1)'
        nextbutton['title'] = MESSAGES[self.locale]['next']
        navigation.append(nextbutton)

        # <a id="fullscreen">
        fullscreentoggle = self.create_tag('a')
        fullscreentoggle['id'] = 'fullscreen'
        fullscreentoggle['style'] = 'float:right; color: white; font-size: 15pt; padding: 5px; cursor: pointer;'
        fullscreentoggle['onclick'] = 'toggleFullScreen()'
        fullscreentoggle['title'] = MESSAGES[self.locale]['toggle_fullscreen']
        fullscreentoggle.string = '⤢'
        navigation.append(fullscreentoggle)

        # <button id="prev-btn">
        prevbutton = self.create_tag('button')
        prevbutton['id'] = 'prev-btn'
        prevbutton.string = '🡐'
        prevbutton['style'] = 'float:left; background-color: transparent; border: none; font-size: 17pt; color: white; width:75px; font-size:16pt;'
        prevbutton['onclick'] = 'updateImage(-1)'
        prevbutton['title'] = MESSAGES[self.locale]['previous']
        navigation.append(prevbutton)

        # <div id="attribution">
        if self.source:
            attribution = self.create_tag('div')
            attribution['id'] = 'attribution'
            attribution['style'] = 'float:left; margin-top:3px;'
            navigation.append(attribution)

            # <img id="sourceLogo">
            if self.thumbnail:
                source_logo = self.create_tag('img')
                source_logo['id'] = 'sourceLogo'
                source_logo['src'] = os.path.basename(self.write_url(self.thumbnail, default_ext=".png"))
                source_logo['style'] = 'width: 24px; height: auto; margin-right: 5px;'
                attribution.append(source_logo)

            # <div id="created">
            created = self.create_tag('div')
            created['style'] = 'text-align: left; color: white; font-family: sans-serif; font-size: 7pt; display: inline-block;'
            created['id'] = 'created'
            created.string = MESSAGES[self.locale]['presentation_source']
            attribution.append(created)

            # <div id="sourceText">
            source_text = self.create_tag('div')
            source_text.string = self.source
            source_text['style'] = 'font-size: 12pt;'
            created.append(source_text)

        # <div id='center'>
        center_nav = self.create_tag('div')
        navigation.append(center_nav)

        # <div id='counter'>
        counter = self.create_tag('div')
        counter['id'] = 'counter'
        counter['style'] = 'padding-top: 5px; color: white; cursor: pointer; font-family: sans-serif;'
        counter['onclick'] = 'openDropdown(event)'
        center_nav.append(counter)

        # <ul id="navigation-menu">
        navmenu = self.create_tag('ul')
        navmenu['id'] = 'navigation-menu'
        center_nav.append(navmenu)

        for index, img  in enumerate(images):
            # <li>
            navmenuitem = self.create_tag('li')
            navmenuitem['style'] = 'font-family: sans-serif; text-align: left; padding: 10px 25px; cursor: pointer;'
            navmenuitem['onclick'] = 'jumpToImage({})'.format(index)
            navmenu.append(navmenuitem)

            # <img class="slide"> Slide #
            slideimg = self.create_tag('img')
            slideimg['class'] = ['slide']
            slideimg['src'] = img
            slideimg['style'] = 'width: 150px; vertical-align: middle; font-size: 12pt; margin-right: 20px;'
            navmenuitem.append(slideimg)
            navmenuitem.append(MESSAGES[self.locale]['slide'].format(index + 1))

        # <script>
        script = self.create_tag('script')
        script.string = "let images = [{images}]; \n"\
            "let index = 0;\n"\
            "let menuExpanded = false;\n"\
            "let img = document.getElementById('gallery');\n"\
            "let prevbutton = document.getElementById('prev-btn');\n"\
            "let nextbutton = document.getElementById('next-btn');\n"\
            "let countText = document.getElementById('counter');\n"\
            "let progress = document.getElementById('progress');\n"\
            "let menu = document.getElementById('navigation-menu');"\
            .format(images=','.join(['\"{}\"'.format(i) for i in images]))

        script.string += "function updateImage(step) {\n"\
            "  if(index + step >= 0 && index + step < images.length)\n"\
            "    index += step;\n"\
            "  jumpToImage(index);\n"\
            "}"

        script.string += "function jumpToImage(step) {\n"\
            "  index = step;\n"\
            "  countText.innerHTML = index + 1 + ' / ' + images.length;\n"\
            "  img.setAttribute('src', images[index]);\n"\
            "  countText.innerHTML = index + 1 + ' / ' + images.length;\n"\
            "  img.setAttribute('src', images[index]);\n"\
            "  (index === 0)? prevbutton.setAttribute('disabled', 'disabled') : prevbutton.removeAttribute('disabled');\n"\
            "  (index === images.length - 1)? nextbutton.setAttribute('disabled', 'disabled') : nextbutton.removeAttribute('disabled');\n"\
            "  progress.children[0].setAttribute('style', 'width:' + ((index + 1) / images.length * 100) + '%;')\n"\
            "}\n"

        script.string += "function toggleFullScreen() {\n"\
            "if ((document.fullScreenElement && document.fullScreenElement !== null) ||(!document.mozFullScreen && !document.webkitIsFullScreen)) {\n"\
            "document.body.setAttribute('class', 'fullscreen');\n"\
            "if (document.documentElement.requestFullScreen) { document.documentElement.requestFullScreen();} \n"\
            "else if (document.documentElement.mozRequestFullScreen) { document.documentElement.mozRequestFullScreen(); } \n"\
            "else if (document.documentElement.webkitRequestFullScreen) { document.documentElement.webkitRequestFullScreen(Element.ALLOW_KEYBOARD_INPUT); }\n"\
            "} else {\n"\
            "document.body.setAttribute('class', 'collapsed');\n"\
            "if (document.cancelFullScreen) { document.cancelFullScreen(); }\n"\
            "else if (document.mozCancelFullScreen) { document.mozCancelFullScreen(); }\n"\
            "else if (document.webkitCancelFullScreen) { document.webkitCancelFullScreen(); }\n"\
            "}\n"\
            "}\n"

        script.string += "function closeDropdown() {\n"\
            "menu.setAttribute('style', 'display: none;');\n"\
            "menuExpanded = false;\n"\
            "}\n"

        script.string += "function openDropdown(event) {\n"\
            "event.stopPropagation();\n"\
            "menu.setAttribute('style', (menuExpanded)? 'display:none;' : 'display:block;');\n"\
            "menuExpanded = !menuExpanded;\n"\
            "}\n"

        script.string += 'updateImage(0);'

        page.body.append(script)

        return page.prettify()
