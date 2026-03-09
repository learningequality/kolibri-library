# coding=utf-8

class FakeBook(object):
    def __init__(self):
        self.artist="Bronwen Heath, Ingrid Schechter"
        self.audios=['https://globalstorybooks.net/media/audio/en/0009/mp3/02.mp3', 'https://globalstorybooks.net/media/audio/en/0009/mp3/03.mp3', 'https://globalstorybooks.net/media/audio/en/0009/mp3/04.mp3', 'https://globalstorybooks.net/media/audio/en/0009/mp3/05.mp3', 'https://globalstorybooks.net/media/audio/en/0009/mp3/06.mp3', 'https://globalstorybooks.net/media/audio/en/0009/mp3/07.mp3', 'https://globalstorybooks.net/media/audio/en/0009/mp3/08.mp3', 'https://globalstorybooks.net/media/audio/en/0009/mp3/09.mp3']
        self.author="Clare Verbeek, Thembani Dladla, Zanele Buthelezi"
        self.cover="https://raw.githubusercontent.com/global-asp/gsn-imagebank/master/0009/01.jpg"
#        self.cover_audio_url() <bound method Book.cover_audio_url of <detail.Book object at 0x7f82818fe438>>
#cover_url <bound method Book.cover_url of <detail.Book object at 0x7f82818fe438>>
        self.coveraudio="https://globalstorybooks.net/media/audio/en/0009/mp3/01.mp3"
# get_text <bound method Book.get_text of <detail.Book object at 0x7f82818fe438>>
#get_title <bound method Book.get_title of <detail.Book object at 0x7f82818fe438>>
        self.imgs=['https://raw.githubusercontent.com/global-asp/gsn-imagebank/master/0009/02.jpg', 'https://raw.githubusercontent.com/global-asp/gsn-imagebank/master/0009/03.jpg', 'https://raw.githubusercontent.com/global-asp/gsn-imagebank/master/0009/04.jpg', 'https://raw.githubusercontent.com/global-asp/gsn-imagebank/master/0009/05.jpg', 'https://raw.githubusercontent.com/global-asp/gsn-imagebank/master/0009/06.jpg', 'https://raw.githubusercontent.com/global-asp/gsn-imagebank/master/0009/07.jpg', 'https://raw.githubusercontent.com/global-asp/gsn-imagebank/master/0009/08.jpg', 'https://raw.githubusercontent.com/global-asp/gsn-imagebank/master/0009/09.jpg']
        self.language="English"
        self.level="Level 1"
#license <bound method Book.icense of <detail.Book object at 0x7f82818fe438>>
        self.narrator="Darshan Soni"
#pages <bound method Book.pages of <detail.Book object at 0x7f82818fe438>>
#parse_page <bound method Book.parse_page of <detail.Book object at 0x7f82818fe438>>
#svg_replace {'pencil': 'author', 'art': 'artist', 'megaphone': 'narrator', 'language': 'language', 'level': 'level', 'global': 'translator'}
#svg_tagged <bound method Book.svg_tagged of <detail.Book object at 0x7f82818fe438>>
        self.texts=['Where is my cat?', 'Is it under the bed?', 'Is it on top of the cupboard?', 'Is it behind the couch?', 'Is it next to the bin?', 'Is it inside the basket?', 'Is it outside the house?', 'Here it is!']
        self.title="Where is my cat?"
        self.url="https://global-asp.github.io/storybooks-minnesota/stories/en/0009/"

book_data = FakeBook()

from ebooklib import epub
import requests
import requests_cache
requests_cache.install_cache()
def make_book(book_data):
    book = epub.EpubBook()

    # add metadata
    book.set_identifier(book_data.url)
    book.set_title(book_data.title)
    book.set_language(book_data.language)

    book.add_metadata(None, 'meta', book_data.narrator, {'property': 'media:narrator'})
    book.add_metadata(None, 'meta', '0:10:10.500', {'property': 'media:duration'})

    book.add_metadata(None, 'meta', '0:05:00.500', {'property': 'media:duration', 'refines': '#intro_overlay'})
    book.add_metadata(None, 'meta', '-epub-media-overlay-active', {'property': 'media:active-class'})
    book.add_author(book_data.author)

    # intro chapter
    pages = []

    for i, (text, image, audio) in enumerate(zip(book_data.texts, book_data.imgs, book_data.audios)):
        image_data = requests.get(image).content
        image_item = epub.EpubItem(file_name=f'image{i}.jpeg', content=image_data)
        book.add_item(image_item)

        audio_data = requests.get(image).content
        audio_item = epub.EpubItem(file_name=f'audio{i}.mp3',
                                   content=audio_data,
                                   media_type="audio/mpeg")
        book.add_item(audio_item)

        page = epub.EpubHtml(title=book_data.title,
                             file_name=f'page{i}.xhtml',
                             # lang = "en",
                             media_overlay="intro_overlay")

        page.content=f'<p style="font-size:800%" id=p{i}>{text}</p><img src="image{i}.jpeg" id=play>'
        book.add_item(page)
        pages.append(page)


    ######

    c1 = epub.EpubHtml(title='Introduction', file_name='intro.xhtml', lang='en', media_overlay='intro_overlay')
    c1.content=u'<html><head></head><body><section epub:type="frontmatter colophon"><h1><span id="header_1">Introduction</span></h1><p><span id="para_1">Introduction paragraph where i explain what is happening.</span></p></section></body></html>'

    s1 = epub.EpubSMIL(uid='intro_overlay',
                       file_name='test.smil',
                       content=open('test.smil', 'rt').read())

    a1 = epub.EpubItem(file_name='chapter1_audio.mp3',
                       content=open('chapter1_audio.mp3', 'rb').read(),
                       media_type='audio/mpeg')
    # add chapters to the book
    book.add_item(c1)
    book.add_item(s1)
    book.add_item(a1)

    #####

    book.toc = [epub.Link('intro.xhtml', 'Introduction', 'intro')]

    # add navigation files
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    # create spine
    book.spine = ['nav', c1]
    book.spine.extend(pages)

    # create epub file
    epub.write_epub('smil.epub', book, {})

if __name__ == "__main__":
    make_book(book_data)
