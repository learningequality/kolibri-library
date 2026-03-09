#!/usr/bin/env python
# -*- coding: UTF-8 -*-
import json
import requests
import re
import youtube_dl
from bs4 import BeautifulSoup
from ricecooker.utils import downloader
from le_utils.constants import content_kinds
from gdrive_scraper import GoogleDriveScraper
from pages import HTMLPageScraper, PresentationScraper, BasicPageScraper, ImageScraper, WebVideoScraper, VideoScraper, AudioScraper
from tags import ImageTag, MediaTag

######### CUSTOM TAGS #########

class CeibalVideoAudioTag(MediaTag):
    default_ext = '.mp3'
    selector = ('video',)

    def scrape(self):
        if self.link and self.link.endswith('.mp3'):
            audio_tag = self.create_tag('audio')
            audio_tag['controls'] = 'controls'
            audio_tag['style'] = 'margin-left: auto; margin-right: auto;'
            source_tag = self.create_tag('source')
            audio_tag.append(source_tag)
            source_tag['src'] = self.write_url(self.link)
            self.tag.replaceWith(audio_tag)

class CeibalVideoTag(MediaTag):
    default_ext = '.mp4'
    selector = ('div', {'class': 'mejs-video'})

    def scrape(self):
        if self.tag.find('audio'):
            self.tag.replaceWith(self.tag.find('audio'))
            return
        try:
            video_tag = self.create_tag('video')
            video_tag['style'] = 'margin-left: auto; margin-right: auto; width: 500px;'
            video_tag['preload'] = 'auto'
            video_tag['controls'] = 'controls'
            for source in self.tag.find_all('source'):
                source_tag = self.create_tag('source')
                source_tag['src'] = self.write_url(source['src'])
                video_tag.append(source_tag)
            self.tag.replaceWith(video_tag)
        except Exception as e:
            LOGGER.warn('Cannot parse video at {} ({})'.format(self.url, str(e)))

class CeibalAudioTag(MediaTag):
    default_ext = '.mp3'
    selector = ('div', {'class': 'mejs-audio'})


    def scrape(self):
        try:
            audio_tag = self.create_tag('audio')
            audio_tag['controls'] = 'controls'
            audio_tag['style'] = 'margin-left: auto; margin-right: auto;'
            source_tag = self.create_tag('source')
            audio_tag.append(source_tag)
            source['src'] = self.write_url(self.tag.find('audio')['src'])
            self.tag.replaceWith(audio_tag)
        except Exception as e:
            LOGGER.warn('Cannot parse audio at {}'.format(self.url, str(e)))


class ThingLinkTag(ImageTag):
    selector = ('img', {'class': 'alwaysThinglink'})

    def process(self):
        thinglink_id = re.search(r'image/([^/]+)/', self.link).group(1)
        self.tag['src'] = self.write_url(self.link)
        self.tag.insert_before(self.create_copy_link_message('https://www.thinglink.com/scene/{}'.format(thinglink_id)))

        # Don't import script to render image
        if self.tag.find_next('script'):
            self.tag.find_next('script').decompose()


######### CUSTOM SCRAPERS #########

class ThingLinkScraper(HTMLPageScraper):
    partially_scrapable = True
    loadjs = True
    scrape_subpages = False
    omit_list = [
        ('nav', {'class': 'item-header'}),
    ]

    @classmethod
    def test(self, url):
        return 'thinglink.com' in url

    def preprocess(self, contents):
        thinglink_id = self.url.split('/')[-1]

        for script in contents.find_all('script'):
            if script.get('src') and 'embed.js' in script['src']:
                response = requests.get('https://www.thinglink.com/api/tags?url={}'.format(thinglink_id))
                script_contents = downloader.read(self.get_relative_url(script['src'])).decode('utf-8')
                tag_data = json.loads(response.content)

                if tag_data[thinglink_id].get('image'):
                    tag_data[thinglink_id]['image'] = ImageScraper(tag_data[thinglink_id]['image'], zipper=self.zipper).to_zip()

                for thing in tag_data[thinglink_id]['things']:
                    if thing['thingUrl']:
                        try:
                            thing['thingUrl'] = WebVideoScraper(thing['thingUrl'], zipper=self.zipper).to_zip()
                            thing['contentUrl'] = thing['thingUrl']
                            thing['icon'] = ImageScraper(thing['icon'], zipper=self.zipper).to_zip()
                        except youtube_dl.utils.DownloadError as e:
                            LOGGER.warning('Youtube download error on thinglink page ({})'.format(str(e)))
                    if thing.get('nubbin'):
                        self.write_url('https://cdn.thinglink.me/api/nubbin/{}/plain'.format(thing['nubbin']), filename='nubbin-{}-plain.png'.format(thing['nubbin']), directory="thinglink")
                        self.write_url('https://cdn.thinglink.me/api/nubbin/{}/highlight'.format(thing['nubbin']), filename='nubbin-{}-highlight.png'.format(thing['nubbin']), directory="thinglink")
                        self.write_url('https://cdn.thinglink.me/api/nubbin/{}/hover'.format(thing['nubbin']), filename='nubbin-{}-hover.png'.format(thing['nubbin']), directory="thinglink")
                        self.write_url('https://cdn.thinglink.me/api/nubbin/{}/hoverlink'.format(thing['nubbin']), filename='nubbin-{}-hoverlink.png'.format(thing['nubbin']), directory="thinglink")

                script_contents = script_contents.replace('d.ajax({url:A+"/api/tags",data:u,dataType:"jsonp",success:z})', 'z({})'.format(json.dumps(tag_data)))
                script_contents = script_contents.replace('n.getJSON(A+"/api/internal/logThingAccess?callback=?",{thing:y,sceneId:w,e:"hover",referer:t.referer,dwell:v});', '')
                script_contents = script_contents.replace('n.getJSON(t.getApiBaseUrl()+"/api/internal/logThingAccess?callback=?",{time:y,sceneId:v,thing:w,e:"hoverend",referer:t.referer})', '')
                script_contents = script_contents.replace('n.getJSON(t.getApiBaseUrl()+"/api/internal/logSceneAccess?callback=?",{time:z,sceneId:w,referer:t.referer,dwell:v,event:"scene.hover"})', '')
                script_contents = script_contents.replace('n.getJSON(t.getApiBaseUrl()+"/api/internal/logSceneAccess?callback=?",{sceneId:v,referer:t.referer,event:"scene.view",channelId:b.getChannelId(x)})', '')
                script_contents = script_contents.replace('n.getJSON(B+"/api/internal/logThingAccess?callback=?",z,C);', '')

                icon_str = 'k.src=l;return"style=\\"background-image: url(\'"+l+"\') !important;\\"'
                script_contents = script_contents.replace(icon_str, 'var slices=l.split("/"); l="thinglink/"+slices.slice(slices.length-3,slices.length).join("-")+".png";{}'.format(icon_str))
                script['src'] = self.write_contents('thinglink-{}-embed.js'.format(thinglink_id), script_contents, directory="thinglink")
                self.mark_tag_to_skip(script)

    def postprocess(self, contents):
        style_tag = self.create_tag('style')
        style_tag.string = '.tlExceededViewsLimit, .tlThingText:not(.tlVariantVideoThing) .tlThingClose, .tlSidebar, .tlThinglinkSite {visibility: hidden !important;} .tlFourDotsButton, .btnViewOnSS {pointer-events: none;} .tlFourDotsButton .btn, .tlFourDotsButton .arrowRight {display: none !important;}'
        contents.head.append(style_tag)
        for script in contents.find_all('script'):
            if not script.string or 'skip-scrape' in (script.get('class') or []):
                continue
            elif 'preloadImages' in script.string:
                regex = r"(?:'|\")([^'\"]+)(?:'|\"),"
                for match in re.finditer(regex, script.string, re.MULTILINE):
                    new_str = match.group(0).replace(match.group(1), self.write_url(match.group(1), default_ext=".png", directory="thinglink"))
                    script.string = script.text.replace(match.group(0), new_str)
            elif re.search(r"var url\s*=\s*(?:'|\")([^'\"]+)(?:'|\")", script.string, re.MULTILINE):
                regex = r"url\s*=\s*(?:'|\")([^'\"]+)(?:'|\")"
                for match in re.finditer(regex, script.string, re.MULTILINE):
                    new_str = match.group(0).replace(match.group(1), self.write_url(match.group(1), default_ext=".png", directory="thinglink"))
                    script.string = script.text.replace(match.group(0), new_str)
            elif 'doresize' in script.string:
                match = re.search(r'\$tlJQ\(document\)\.ready\(function\(\) \{\s+(doresize\(\);)', script.string)
                new_str = match.group(0).replace(match.group(1), 'doresize(); __thinglink.reposition(); __thinglink.rebuild();')
                script.string = script.text.replace(match.group(0), new_str)

        for nubbin in contents.find_all('div', {'class': 'nubbin'}):
            for subnubbin in nubbin.find_all('div'):
                if not subnubbin.get('style'):
                    continue
                regex = r"\((?:'|\")*(http[^'\"]+)(?:'|\")*\)"
                for match in re.finditer(regex, subnubbin['style'], re.MULTILINE):
                    subnubbin['style'] = subnubbin['style'].replace(match.group(1), self.write_url(match.group(1), default_ext=".png", directory="thinglink"))


class EducaplayScraper(HTMLPageScraper):
    loadjs = True
    scrape_subpages = False
    partially_scrapable = True
    omit_list = [
        ('ins', {'class': 'adsbygoogle'})
    ]
    media_directory = "media"

    @classmethod
    def test(self, url):
        return 'educaplay.com' in url

    def preprocess(self, contents):
        for script in contents.find_all('script'):
            if script.get('src') and 'xapiEventos.js' in script['src']:
                script_contents = downloader.read(self.get_relative_url(script['src'])).decode('utf-8')
                script_contents = script_contents.replace('img.src=rutaRecursos+imagen;', 'img.src = "img/" + imagen;');
                script_contents = script_contents.replace('/snd_html5/', '{}/-snd_html5-'.format(self.media_directory))
                script['src'] = self.write_contents(self.get_filename(self.url, default_ext='.js'), script_contents, directory="js")
                self.mark_tag_to_skip(script)
            elif script.string and 'socializarPage' in script.string:
                script.decompose()  # Remove share on social media links

    def postprocess(self, contents):
        style_tag = self.create_tag('style')
        style_tag.string = '#banner { display: none !important; }'
        contents.head.append(style_tag)
        for audio in contents.find_all('audio'):
            for source in audio.find_all('source'):
                source['src'] = self.write_url(source['src'], directory=self.media_directory)
            self.mark_tag_to_skip(audio)


class GeniallyScraper(HTMLPageScraper):
    scrape_subpages = False

    @classmethod
    def test(self, url):
        return 'genial.ly' in url

    def preprocess(self, contents):
        # Hide certain elements from the page
        style_tag = self.create_tag('style')
        style_tag.string = '.genially-view-logo { pointer-events: none;} .genially-view-navigation-actions,'\
            ' .genially-view-navigation-actions-toggle-button{display: none !important; pointer-events:none;}'
        contents.head.append(style_tag)

        # Prefetch API response and replace script content accordingly
        genial_id = self.url.split('/')[-1]
        response = requests.get('https://view.genial.ly/api/view/{}'.format(genial_id))
        for script in contents.find_all('script'):
            if script.get('src') and 'main' in script['src']:
                script_contents = downloader.read(self.get_relative_url(script['src'])).decode('utf-8')
                genial_data = json.loads(response.content)

                if len(genial_data['Videos']) or len(genial_data['Audios']):
                    LOGGER.error('Unhandled genial.ly video or audio at {}'.format(url))

                if genial_data['Genially']['ImageRender']:
                    genial_data['Genially']['ImageRender'] = self.write_url(genial_data['Genially']['ImageRender'], directory='webimg')
                for image in genial_data['Images']:
                    image['Source'] = self.write_url(image['Source'], directory='webimg')
                for slide in genial_data['Slides']:
                    slide['Background'] = self.write_url(slide['Background'], directory='webimg')
                for code in genial_data['Contents']:
                    code_contents = BeautifulSoup(code['HtmlCode'], 'html.parser')
                    for img in code_contents.find_all('img'):
                        try:
                            img['src'] = self.write_url(img['src'], directory='webimg')
                        except (requests.exceptions.HTTPError, requests.exceptions.ConnectionError) as e:
                            LOGGER.warning("Error processing genial.ly at {} ({})".format(url, str(e)))
                    code['HtmlCode'] = code_contents.prettify()
                script_contents = script_contents.replace('r.a.get(c).then(function(e){return n(e.data)})', 'n({})'.format(json.dumps(genial_data)))
                script['class'] = ['skip-scrape']
                script['src'] = self.write_contents('genial-{}-embed.js'.format(genial_id), script_contents,  directory="js")


class SlideShareScraper(PresentationScraper):
    thumbnail = "https://is1-ssl.mzstatic.com/image/thumb/Purple113/v4/03/df/99/03df99d1-48c0-d976-c0f3-3ad4a6af5b90/source/200x200bb.jpg"
    source = "SlideShare"
    img_selector = ('img', {'class': 'slide_image'})
    img_attr='data-normal'
    color = '#007bb6'

    @classmethod
    def test(self, url):
        return 'slideshare.net' in url


class EasellyScraper(ImageScraper):
    @classmethod
    def test(self, url):
        return 'easel.ly' in url

    def _download_file(self, write_to_path):
        contents = BeautifulSoup(downloader.read(self.url), 'html5lib')
        easel = contents.find('div', {'id': 'easelly-frame'}).find('img')
        with open(write_to_path, 'wb') as fobj:
            fobj.write(downloader.read(easel['src']))

    def to_zip(self, filename=None):
        contents = BeautifulSoup(downloader.read(self.url), 'html5lib')
        easel = contents.find('div', {'id': 'easelly-frame'}).find('img')
        return self.write_url(easel['src'], filename=filename)


class WeVideoScraper(VideoScraper):
    @classmethod
    def test(self, url):
        return 'wevideo.com' in url

    def _download_file(self, write_to_path):
        video_id = self.url.split('#')[1]
        with open(write_to_path, 'wb') as fobj:
            fobj.write(downloader.read('https://www.wevideo.com/api/2/media/{}/content'.format(video_id)))

    def to_zip(self, filename=None):
        video_id = self.url.split('#')[1]
        return self.write_url('https://www.wevideo.com/api/2/media/{}/content'.format(video_id))


class IVooxScraper(AudioScraper):
    @classmethod
    def test(self, url):
        return 'ivoox.com' in url

    def _download_file(self, write_to_path):
        audio_id = re.search(r'(?:player_ek_)([^_]+)(?:_2_1\.html)', self.url).group(1)
        with open(write_to_path, 'wb') as fobj:
            fobj.write(downloader.read('http://www.ivoox.com/listenembeded_mn_{}_1.m4a?source=EMBEDEDHTML5'.format(audio_id)))

    def to_zip(self, filename=None):
        audio_id = re.search(r'(?:player_ek_)([^_]+)(?:_2_1\.html)', self.url).group(1)
        return self.write_url('http://www.ivoox.com/listenembeded_mn_{}_1.m4a?source=EMBEDEDHTML5'.format(audio_id))

class WikipediaScraper(HTMLPageScraper):
    scrape_subpages = False
    main_area_selector = ('div', {'id': "content"})
    partially_scrapable = True
    omit_list = [
        ('span', {'class': 'mw-editsection'}),
        ('a', {'class': 'mw-jump-link'}),
        ('div', {'class': 'navbox'}),
        ('div', {'class': 'mw-hidden-catlinks'})
    ]

    @classmethod
    def test(self, url):
        return 'wikipedia' in url or 'wikibooks' in url

    def preprocess(self, contents):
        for style in contents.find_all('link', {'rel': 'stylesheet'}):
            if style.get('href') and 'load.php' in style['href']:
                style.decompose()

        for script in contents.find_all('script'):
            if script.get('src') and 'load.php' in script['src']:
                script.decompose()

        for popup in contents.find_all('div', {'class': 'PopUpMediaTransform'}):
            if popup.get('videopayload'):
                video = BeautifulSoup(popup['videopayload'], 'html.parser')
                video.video['style'] = 'width: 100%; height: auto;'
                video.video['preload'] = 'auto'
                self.mark_tag_to_skip(video.video)
                for source in video.find_all('source'):
                    try:
                        source['src'] = self.write_url(source['src'], directory='media')
                    except EXCEPTIONS as e:
                        LOGGER.warning(str(e))
                        source.decompose()
                popup.replaceWith(video.video)

    def postprocess(self, contents):
        # Wikipedia uses a load.php file to load all the styles, so add the more common styling manually
        style_tag = self.create_tag('style')
        style_tag.string = "body { font-family: sans-serif; padding: 2%;} a {text-decoration: none;}"\
            "h1, h2 {font-family: 'Linux Libertine','Georgia','Times',serif;border-bottom: 1px solid #a2a9b1; font-weight:normal; margin-bottom: 0.25em;}"\
            "h2, h3, h4, h5, h6 {overflow: hidden;margin-bottom: .25em;} h3{font-size: 13pt;}"\
            ".toc {display: table; zoom: 1; border: 1px solid #a2a9b1; background-color: #f8f9fa;padding: 7px;}"\
            ".toc h2 {font-size: 100%; font-family: sans-serif; border: none; font-weight: bold; text-align: center; margin: 0;}"\
            ".toc ul { list-style-type: none; list-style-image: none;margin-left: 0; padding: 0; margin-top: 10px;}"\
            ".toc ul li {margin-bottom: 7px; font-size: 10pt;} .toc ul ul {margin: 0 0 0 2em;} .toc .tocnumber {color: #222;}"\
            ".thumbinner { border: 1px solid #c8ccd1; padding: 3px; background-color: #f8f9fa; font-size: 94%; text-align: center; overflow: hidden;}"\
            ".thumbimage {background-color: #fff; border: 1px solid #c8ccd1;} .thumbcaption {font-size: 10pt; text-align: left;padding: 3px;}"\
            ".tright { clear: right; float: right; margin: 0.5em 0 1.3em 1.4em;}"\
            ".catlinks { text-align: left; border: 1px solid #a2a9b1; background-color: #f8f9fa; padding: 5px; margin-top: 1em; clear: both;margin-bottom:50px;}"\
            ".catlinks ul { display: inline; list-style: none none; padding: 0;} .catlinks li { display: inline-block; margin: 0.125em 0;padding: 0 0.5em;}"\
            ".infobox { border: 1px solid #B4BBC8; background-color: #f9f9f9; margin: .5em 0 .7em 1.2em; padding: .4em; clear: right; float: right; font-size: 90%; line-height: 1.5em;width: 22.5em;}"\
            ".wikitable {background-color: #f8f9fa; color: #222; margin: 1em 0; border: 1px solid #a2a9b1; border-collapse: collapse;}"\
            ".wikitable th {background-color: #eaecf0; text-align: center;} .wikitable th, .wikitable td {border: 1px solid #a2a9b1;padding: 0.2em 0.4em;}"\
            ".gallery { text-align: center; } li.gallerybox { display: inline-block; }"\
            ".hlist ul { margin: 0; padding: 0; } .hlist ul ul {display: inline;} .hlist li {display: inline; font-size: 8pt;} .hlist li:not(:last-child)::after {content: ' · ';font-weight: bold;}"\
            ".reflist { font-size: 9pt; }"

        contents.head.append(style_tag)


class SoundCloudScraper(WebVideoScraper):
    default_ext = '.mp3'
    kind = content_kinds.AUDIO
    directory = 'audio'

    @classmethod
    def test(self, url):
        return 'soundcloud' in url and 'search?' not in url and 'playlists' not in url

    def to_tag(self, filename=None):
        # Get image if there is one
        div = self.create_tag('div')
        contents = BeautifulSoup(downloader.read(self.url, loadjs=True), 'html5lib')
        image = contents.find('div', {'class': 'sc-artwork'})
        if image:
            url = re.search(r'background-image:url\(([^\)]+)\)', image.find('span')['style']).group(1)
            img = self.create_tag('img')
            img['src'] = self.write_url(url, directory='webimg', default_ext='.png')
            img['style'] = 'width:300px;'
            div.append(img)
        audio_tag = self.create_tag('audio')
        audio_tag['controls'] = 'controls'
        audio_tag['style'] = 'margin-left: auto; margin-right: auto;'
        source_tag = self.create_tag('source')
        source_tag['src'] = self.to_zip(filename=filename)
        audio_tag.append(source_tag)
        div.append(audio_tag)

        return div

class RecursosticScraper(HTMLPageScraper):

    @classmethod
    def test(self, url):
        return 'recursostic.educacion.es' in url or 'recursos.cnice.mec.es' in url

    def postprocess(self, contents):
        for script in contents.find_all('script'):
            if script.string:
                script.string = script.text.replace('background="HalfBakedBG.gif"', '')
                for match in re.finditer(r'(?:src)=(?:\'|\")([^\'\"]+)(?:\'|\")', script.string, re.MULTILINE):
                    img_filename = match.group(1).split('?')[0].split('/')[-1][-20:]
                    script.string = script.text.replace(match.group(1), self.write_url(match.group(1), directory="webimg"))
                for match in re.finditer(r"onclick=\\(?:'|\")parent\.location\s*=\s*(?:'|\")([^'\"]+)(?:'|\")", script.string, re.MULTILINE):
                    page_filename = 'recursostic-{}'.format(match.group(1).split('?')[0].split('/')[-1])
                    page = BeautifulSoup(downloader.read(self.get_relative_url(match.group(1))), 'html5lib')
                    page_link = RecursosticScraper(self.get_relative_url(match.group(1)), zipper=self.zipper, locale=self.locale).to_zip()
                    script.string = script.text.replace(match.group(1), page_link)


class DisfrutalasmatematicasScraper(HTMLPageScraper):
    scrape_subpages = False
    omit_list = [
        ('div', {'id': 'topads'}),
        ('div', {'id': 'adhid2'}),
        ('div', {'id': 'menu'}),
        ('div', {'id': 'header'}),
        ('div', {'class': 'related'}),
        ('div', {'id': 'footer'}),
        ('div', {'id': 'foot-menu'}),
        ('div', {'id': 'cookieok'}),
    ]

    @classmethod
    def test(self, url):
        return 'disfrutalasmatematicas.com' in url


class ImpoScraper(HTMLPageScraper):
    scrape_subpages = False
    omit_list = [
        ('nav', {'id': 'topnavbar'})
    ]

    @classmethod
    def test(self, url):
        return 'impo.com.uy' in url


class GeoEnciclopediaScraper(HTMLPageScraper):
    scrape_subpages = False
    omit_list = [
        ('header', {'id': 'main-header'}),
        ('div', {'class': 'et_pb_widget_area_right'}),
        ('footer', {'id': 'main-footer'})
    ]

    @classmethod
    def test(self, url):
        return 'geoenciclopedia.com' in url


class CiudadSevaScraper(HTMLPageScraper):
    scrape_subpages = False
    omit_list = [
        ('div', {'class': 'container'}),
        ('nav', {'class': 'navbar-maqin'}),
        ('div', {'class': 'hidden-print'})
    ]

    @classmethod
    def test(self, url):
        return 'ciudadseva.com' in url


class LiteraturaScraper(HTMLPageScraper):
    scrape_subpages = False
    omit_list = [
        ('a', {})
    ]

    @classmethod
    def test(self, url):
        return 'literatura.us' in url

class NoOmitListScraper(HTMLPageScraper):
    scrape_subpages = False
    @classmethod
    def test(self, url):
        return 'infoymate.es' in url or 'edu.xunta.es' in url

class UOCScraper(HTMLPageScraper):
    scrape_subpages = False
    omit_list = [
        ('div', {'class': 'alert-text'}),
        ('div', {'id': 'eines'})
    ]
    @classmethod
    def test(self, url):
        return 'www.uoc.edu' in url

class ContenidosScraper(HTMLPageScraper):
    scrape_subpages = False
    omit_list = [
        ('ul', {'id': 'mainMenu'}),
        ('div', {'class': 'button'}),
        ('div', {'id': 'related'}),
    ]
    @classmethod
    def test(self, url):
        return 'contenidos.ceibal.edu.uy' in url


########## MAIN SCRAPER ##########

class CeibalPageScraper(HTMLPageScraper):
    color = "#2E72B0"
    extra_tags = [
        CeibalVideoAudioTag,
        CeibalVideoTag,
        CeibalAudioTag,
        ThingLinkTag,
    ]

    scrapers = [
        WebVideoScraper,
        ThingLinkScraper,
        SlideShareScraper,
        WikipediaScraper,
        EducaplayScraper,
        GeniallyScraper,
        GoogleDriveScraper,
        EasellyScraper,
        WeVideoScraper,
        IVooxScraper,
        SoundCloudScraper,
        RecursosticScraper,
        DisfrutalasmatematicasScraper,
        ImpoScraper,
        GeoEnciclopediaScraper,
        CiudadSevaScraper,
        LiteraturaScraper,
        NoOmitListScraper,
        UOCScraper,
        ContenidosScraper
    ]

    @classmethod
    def test(self, url):
        return 'rea.ceibal.edu.uy' in url

    def __init__(self, *args, **kwargs):

        super(CeibalPageScraper, self).__init__(*args, **kwargs)
        self.url = self.url.replace('inicio', 'index.html')

    def preprocess(self, contents):
        # Some scripts only load if there's a video on the page
        if 'rea.ceibal.edu.uy' in self.url and contents.find('video'):
            contents = BeautifulSoup(downloader.read(self.url, loadjs=True), 'html5lib')

        for block in contents.find_all('div', {'class': 'iDevice_content'}):
            block['style'] = 'word-break: break-word;'

        for header in contents.find_all('div', {'class': 'iDevice_header'}) + contents.find_all('header', {'class': 'iDevice_header'}):
            header['style'] = "min-height: 25px;"

        for obj in contents.find_all('object'):
            obj.replaceWith(self.create_copy_link_message(self.url))

        for script in contents.find_all('script'):
            if script.string and 'gtag' in script.string:
                script.decompose()
