#!/usr/bin/env python
# encoding=utf-8
import os
import re
import requests

from bs4 import BeautifulSoup
from ricecooker.chefs import SushiChef
from ricecooker.classes.nodes import TopicNode, DocumentNode
from ricecooker.classes.files import DocumentFile
from ricecooker.classes.licenses import get_license
from ricecooker.utils.pdf import PDFParser



CHANNEL_DESCRIPTION = """A collection of programming books from the Stack Overflow Documentation project """ \
                      """that cover topics like Linux, Python, Java, JavaScript, PHP, HTML5, Android, SQL, """ \
                      """and other modern technologies used by professional programmers. """ \
                      """These books can be used by high school students and adult learners """ \
                      """wishing to develop advanced computer skills, or as supplementary materials for technology classes."""

LIGATURES = {   u"\u00DF": "fs",
                u"\u00C6": "AE",
                u"\u00E6": "ae",
                u"\u0152": "OE",
                u"\u0153": "oe",
                u"\uFB00": "ff",
                u"\uFB01": "fi",
                u"\uFB02": "fl",
                u"\uFB03": "ffi",
                u"\uFB04": "ffl",
                u"\uFB05": "ft",
                '®': '',
                '©': '',
                '™': '', }

class GoalkickerChef(SushiChef):
    channel_info = {
        'CHANNEL_TITLE': 'Goalkicker Tech Books',
        'CHANNEL_SOURCE_DOMAIN': 'goalkicker.com',
        'CHANNEL_SOURCE_ID': 'tech-books',
        'CHANNEL_LANGUAGE': 'en',
        'CHANNEL_THUMBNAIL': 'chefdata/channel_thumbnail.png',
        'CHANNEL_DESCRIPTION': CHANNEL_DESCRIPTION,
    }

    def construct_channel(self, **kwargs):
        channel = self.get_channel(**kwargs)

        # Soupify goalkicker main page
        gk_url = 'https://' + self.channel_info['CHANNEL_SOURCE_DOMAIN'] + '/'
        gk_soup = get_soup(gk_url)

        # Get urls for each goalkicker book
        els_with_page_urls = gk_soup.find_all(class_='bookContainer')
        page_urls = [gk_url + el.find('a')['href'] for el in els_with_page_urls]

        for book_counter, page_url in enumerate(page_urls):
            # Soupify book page
            page_soup = get_soup(page_url)

            # Extract and construct book info
            book_info = parse_book_info(page_soup)
            book_info['absolute_url'] = page_url + book_info['relative_url']

            # Add book to channel tree
            book_node_source_id = 'topic/' + book_info['subject']

            # Use separate download directory for each book's pdf chunks. Avoids name conflicts between books
            download_dir = os.path.join('downloads', 'book_' + str(book_counter).rjust(2, '0') + '--' + book_info['subject'])
            # Get chapters info
            pdf_path = book_info['absolute_url']
            book_node = TopicNode(
                title=book_info['subject'],
                description=book_info['description'],
                source_id=book_node_source_id,
            )
            channel.add_child(book_node)
            with PDFParser(pdf_path, directory=download_dir) as pdfparser:
                chapters = pdfparser.split_chapters()

            # Add chapter nodes
            for i, chapter in enumerate(chapters):
                chapter_node_source_id = book_info['source_id'] + '/' + chapter['title']

                if chapter['title'].startswith('Chapter'):
                    chapter_num = re.search('Chapter (\d+)', chapter['title']).group(1)
                    chapter_description = 'Chapter ' + chapter_num + ' of the book on ' + book_info['subject'] + '.'
                else:
                    chapter_description = 'Section "' + chapter['title'] + '" of the book on ' + book_info['subject'] + '.'

                chapter_node = DocumentNode(
                    title=chapter['title'],
                    description=chapter_description,
                    source_id=chapter_node_source_id,
                    license=get_license('CC BY-SA', copyright_holder='Stack Overflow'),
                    language='en',
                    files=[DocumentFile(path=chapter['path'], language='en')]
                )
                book_node.add_child(chapter_node)
        return channel

def replace_ligatures(string):
    for ligature, equiv in LIGATURES.items():
        string = string.replace(ligature, equiv)
    return string


def get_soup(url):
    response = requests.get(url)
    response.encoding = 'utf-8'
    soup = BeautifulSoup(response.text, 'html5lib')
    return soup


def parse_book_info(soup):
    str_with_book_title = soup.find(id='header').find('h1').get_text()
    suffix = ' book'
    book_title = str_with_book_title[:-len(suffix)] if str_with_book_title.endswith(suffix) else str_with_book_title
    book_title = replace_ligatures(book_title)

    suffix = ' Notes for Professionals'
    book_subject = book_title[:-len(suffix)] if book_title.endswith(suffix) else book_title

    book_description = 'A book about ' + book_subject + ' exported from the Stack Overflow Documentation project.'

    book_source_id = 'book/' + book_subject

    str_with_book_url = soup.find('button', class_='download')['onclick']
    book_relative_url = re.search("location.href='(.+)'", str_with_book_url).group(1)

    return {
        'title': book_title,
        'subject': book_subject,
        'description': book_description,
        'source_id': book_source_id,
        'relative_url': book_relative_url
    }


if __name__ == '__main__':
    """
    Run this script on the command line using:
        python sushichef.py   --token=YOURTOKENHERE9139139f3a23232
    """
    goalkicker_chef = GoalkickerChef()
    goalkicker_chef.main()

