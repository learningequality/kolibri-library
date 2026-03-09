#!/usr/bin/env python
# -*- coding: UTF-8 -*-
import os
from bs4 import BeautifulSoup
import requests
import re
import hashlib
from urllib.parse import urlparse

MESSAGES = {
    'en': {
        'broken_link': 'Cannot load content',
        'not_supported': 'This content is not able to be viewed from within Kolibri',
        'copy_text': 'Please copy this link in your browser to see the original source',
        'partially_supported': 'Some portion of this content may not be viewable in Kolibri',
        'partially_supported_copy_text': 'If you encounter problems, please copy this link in your browser to see the original source',
        'copy_button': 'Copy',
        'copy_error': 'Failed',
        'copy_success': 'Copied',
        'presentation_source': 'Original at',
        'slide': 'Slide {}',
        'toggle_fullscreen': 'Toggle Fullscreen',
        'next': 'Next',
        'previous': 'Previous',
        'jump_to': 'Jump to...'
    },
    'es': {
        'broken_link': 'No se pudo cargar este contenido',
        'not_supported': 'Este contenido no se puede ver dentro de Kolibri',
        'copy_text': 'Copie este enlace en su navegador si desea ver la fuente original',
        'partially_supported': 'Puede haber partes de este contenido que no se puedan ver en Kolibri',
        'partially_supported_copy_text': 'Si tiene problemas copie este enlace en su navegador para ver la fuente original',
        'copy_button': 'Copiar',
        'copy_error': 'Falló',
        'copy_success': 'Copiado',
        'presentation_source': 'Original en',
        'slide': 'Diapositiva {}',
        'toggle_fullscreen': 'Cambiar modo Pantalla Completa',
        'next': 'Siguiente',
        'previous': 'Anterior',
        'jump_to': 'Saltar a ...',

    }
}

class BrokenSourceException(Exception):
    """ BrokenSourceException: raised when a source is broken """
    def __init__(self,*args,**kwargs):
        Exception.__init__(self,*args,**kwargs)

class UnscrapableSourceException(Exception):
    """ UnscrapableSourceException: raised when a source is not scrapable """
    def __init__(self,*args,**kwargs):
        Exception.__init__(self,*args,**kwargs)

EXCEPTIONS = (requests.exceptions.HTTPError, requests.exceptions.ConnectionError, requests.exceptions.InvalidURL, BrokenSourceException)


class BasicScraper(object):
    url = ""
    zipper = None
    directory = None
    color = 'rgb(153, 97, 137)'

    def __init__(self, url, locale='en', zipper=None, triaged=None):
        """
            url: string                                    # URL to read from
            locale: string                                 # Language to use when writing error messages
        """
        self.url = self.get_relative_url(url)
        self.triaged = triaged or {}
        self.locale = locale
        self.zipper = zipper

    def create_tag(self, tag):
        return BeautifulSoup('', 'html.parser').new_tag(tag)


    def get_filename(self, link, default_ext=None):
        _, ext = os.path.splitext(link.split('#')[0].split('?')[0])
        hash_object = hashlib.md5(link.encode('utf-8'))
        return "{}{}".format(hash_object.hexdigest(), ext or default_ext or self.default_ext)

    def mark_tag_to_skip(self, tag):
        tag['class'] = (tag.get('class') or []) + ['skip-scrape']

    def get_relative_url(self, endpoint, url=None):
        url = url or self.url
        endpoint = endpoint.replace('%20', ' ').strip()
        if endpoint.strip().startswith('http'):
            return endpoint
        elif endpoint.startswith('//'):
            return 'https:{}'.format(endpoint)
        elif '../' in endpoint:
            jumps = len(list(section for section in endpoint.split('/') if section == '..'))
            url_sections = url.split('/')[:-(jumps + 1)] + endpoint.split('/')[jumps:]
            return '{}'.format('/'.join(url_sections))
        elif endpoint.startswith('/'):
            parsed = urlparse(url)
            return "{}://{}/{}".format(parsed.scheme, parsed.netloc, endpoint.strip('/'))
        return "/".join(url.split('/')[:-1] + [endpoint])

    def write_url(self, link, url=None, default_ext=None, filename=None, directory=None):
        return self.zipper.write_url(self.get_relative_url(link, url=url), filename or self.get_filename(link, default_ext=default_ext), directory=directory or self.directory)

    def write_contents(self, filename, contents, directory=None):
        return self.zipper.write_contents(filename, contents, directory=directory or self.directory)

    def write_file(self, filepath, directory=None):
        return self.zipper.write_file(filepath, os.path.basename(filepath), directory=directory or self.directory)

    def create_broken_link_message(self, link):
        return self.create_copy_link_message(link, broken=True)

    def create_copy_link_message(self, link, supported_by_kolibri=False, partially_scrapable=False, broken=False):
        div = self.create_tag('div')
        div['style'] = 'text-align: center;'

        header_msg = ''
        subheader_msg = MESSAGES[self.locale]['copy_text']

        if partially_scrapable:
            header_msg = MESSAGES[self.locale]['partially_supported']
            subheader_msg = MESSAGES[self.locale]['partially_supported_copy_text']
        elif broken:
            header_msg = MESSAGES[self.locale]['broken_link']
        elif not supported_by_kolibri:
            header_msg = MESSAGES[self.locale]['not_supported']


        # Add "This content is not able to be viewed from within Kolibri"
        if header_msg:
            header = self.create_tag('p')
            header['style'] = 'font-size: 12pt;margin-bottom: 0px;color: {};font-weight: bold;'.format(self.color)
            header.string = header_msg
            div.append(header)

        # Add "Please copy this link in your browser to see the original source"
        subheader = self.create_tag('p')
        subheader['style'] = 'font-weight: bold;margin-bottom: 10px;color: #555;margin-top:5px;'
        subheader.string = subheader_msg
        div.append(subheader)

        # Add copy link section
        paragraph = self.create_tag('p')
        div.append(paragraph)
        copytext = self.create_tag('input')
        copytext['type'] = 'text'
        copytext['value'] = link
        copytext['style'] = 'width: 250px; max-width: 100vw;text-align: center;font-size: 12pt;'\
            'background-color: #EDEDED;border: none;padding: 10px;color: #555;outline:none;'
        copytext['readonly'] = 'readonly'
        copytext['id'] = "".join(re.findall(r"[a-zA-Z]+", link))
        paragraph.append(copytext)

        # Add copy button
        copybutton = self.create_tag('button')
        copybutton['style'] = 'display: inline-block;cursor: pointer;min-width: 64px;max-width: 100%;min-height: 36px;padding: 0 16px;margin: 8px;'\
            'overflow: hidden;font-size: 14px;font-weight: bold;line-height: 36px;text-align: center;text-decoration: none;text-transform: uppercase;'\
            'white-space: nowrap;cursor: pointer;user-select: none;border: 0;border-radius: 2px;outline: none;background-color:{};color:white;'.format(self.color)
        copybutton.string = MESSAGES[self.locale]['copy_button']
        copybutton['id'] = 'btn-{}'.format(copytext['id'])
        copybutton['onclick'] = '{}()'.format(copytext['id'][-15:])  # Keep unique in case there are other copy buttons on the page
        paragraph.append(copybutton)

        # Add copy script
        copyscript = self.create_tag('script')
        copyscript.string = "function {function}(){{ " \
                            "  let text = document.getElementById('{id}');" \
                            "  let button = document.getElementById('btn-{id}');" \
                            "  text.select();" \
                            "  try {{ document.execCommand('copy'); button.innerHTML = '{success}';}}" \
                            "  catch (e) {{ button.innerHTML = '{failed}'; }}" \
                            "  if (window.getSelection) {{window.getSelection().removeAllRanges();}}"\
                            "  setTimeout(() => {{ button.innerHTML = '{text}';}}, 2500);" \
                            "}}".format(
                                id=copytext['id'],
                                function=copytext['id'][-15:],
                                success=MESSAGES[self.locale]['copy_success'],
                                text=MESSAGES[self.locale]['copy_button'],
                                failed=MESSAGES[self.locale]['copy_error']
                            )
        self.mark_tag_to_skip(copyscript)
        div.append(copyscript)

        return div


def guess_scraper(url, scrapers=None, allow_default=False):
    from pages import DEFAULT_PAGE_HANDLERS, SinglePageScraper
    scrapers = scrapers or []
    scrapers += DEFAULT_PAGE_HANDLERS
    if allow_default:
        scrapers.append(SinglePageScraper)

    for scraper_class in scrapers:
        if scraper_class.test(url):
            return scraper_class(url)

