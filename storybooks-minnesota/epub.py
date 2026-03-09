from ebooklib import epub
import subprocess
import requests_cache
import requests
requests_cache.install_cache()

def make_book(book_data):


    for attr in dir(book_data):
        print (attr, getattr(book_data, attr))

    book = epub.EpubBook()

# set metadata
    book.set_identifier(book_data.url)
    book.set_title(book_data.title)
    book.set_language(book_data.language) # TODO -- lang code

    book.add_author(book_data.author)
    book.add_author(book_data.artist, role='ill', uid='coauthor')
    book.add_metadata(None, 'meta', 'Naro Narrator', {'property': 'media:narrator'})
    book.add_metadata(None, 'meta', '0:01:00.000', {'property': 'media:duration'})

    book.add_metadata(None, 'meta', '0:01:00.000', {'property': 'media:duration', 'refines': '#intro_overlay'})
    book.add_metadata(None, 'meta', '-epub-media-overlay-active', {'property': 'media:active-class'})
# create chapter
#    pages = []
#
#    for i, (text, image, audio) in enumerate(zip(book_data.texts, book_data.imgs, book_data.audios)):
#        image_data = requests.get(image).content
#        image_item = epub.EpubItem(file_name=f'image{i}.jpeg', content=image_data)
#        book.add_item(image_item)
#
#        audio_data = requests.get(image).content
#        audio_item = epub.EpubItem(file_name=f'audio{i}.mp3', content=audio_data)
#        book.add_item(audio_item)
#
#        page = epub.EpubHtml(title=book_data.title, file_name=f'page{i}.xhtml',
#                             media_overlay="intro_overlay")#, lang='hr')
#        page.content=f'<p style="font-size:800%" id=p>{text}</p><img src="image{i}.jpeg" id=play>'
#        book.add_item(page)
#        pages.append(page)
#

# intro chapter
    SMILc1 = epub.EpubHtml(title='Introduction', file_name='intro.xhtml', lang='en', media_overlay='intro_overlay')
    SMILc1.content=u'<html><head></head><body><section epub:type="frontmatter colophon"><h1><span id="header_1">Introduction</span></h1><p><span id="para_1">Introduction paragraph where i explain what is happening.</span></p></section></body></html>'

    SMILs1 = epub.EpubSMIL(uid='intro_overlay', file_name='test.smil', content=open('test.smil', 'rt').read())
    SMILa1 = epub.EpubItem(file_name='chapter1_audio.mp3', content=open('chapter1_audio.mp3', 'rb').read(), media_type='audio/mpeg')
    # add chapters to the book
    book.add_item(SMILc1)
    book.add_item(SMILs1)
    book.add_item(SMILa1)

    book.toc = [epub.Link('intro.xhtml', 'Introduction', 'intro')]

    # add navigation files
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    # create spine
    book.spine = ['nav', SMILc1]

    # create epub file
    epub.write_epub('test.epub', book, {})



# define Table Of Contents
#    book.toc = (epub.Link('page0.xhtml', book_data.title, 'intro'),
#                 (epub.Section(book_data.title),
#                 (pages[0], ))
#                )



def placeholder():
    smil_xml=b"""<smil xmlns="http://www.w3.org/ns/SMIL"
      xmlns:epub="http://www.idpf.org/2007/ops"
      version="3.0">
    <body>
        <par id="id1">
            <text src="page0.xhtml#p"/> <!-- #para_1 -->
            <audio src="audio0.mp3" clipBegin="0:00:00.000" clipEnd="0:00:10.000"/>
        </par>

        <par id="id2">
            <text src="page1.xhtml#p"/> <!-- #para_1 -->
            <audio src="audio1.mp3" clipBegin="0:00:10.000" clipEnd="0:00:20.000"/>
        </par>

        <par id="id3">
            <text src="page2.xhtml#p"/> <!-- #para_1 -->
            <audio src="audio2.mp3" clipBegin="0:00:20.000" clipEnd="0:00:30.000"/>
        </par>
        <par id="id4">
            <text src="page3.xhtml#p"/> <!-- #para_1 -->
            <audio src="audio3.mp3" clipBegin="0:00:30.000" clipEnd="0:00:40.000"/>
        </par>
        <par id="id5">
            <text src="page4.xhtml#p"/> <!-- #para_1 -->
            <audio src="audio4.mp3" clipBegin="0:00:40.000" clipEnd="0:00:50.000"/>
        </par>
        <par id="id6">
            <text src="page5.xhtml#p"/> <!-- #para_1 -->
            <audio src="audio5.mp3" clipBegin="0:00:50.000" clipEnd="0:01:00.000"/>
        </par>
    </body>
    </smil>"""

    smil_item = epub.EpubSMIL(uid='intro_overlay', file_name='test.smil', content=smil_xml)
    book.add_item(smil_item)



# add default NCX and Nav file
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

# define CSS style
    style = 'BODY {color: white;}'
    nav_css = epub.EpubItem(uid="style_nav", file_name="style/nav.css", media_type="text/css", content=style)

# add CSS file
    book.add_item(nav_css)

# basic spine
    book.spine = pages

# write to the file
    epub.write_epub('test.epub', book, {})
    subprocess.check_output(["ebook-viewer", "test.epub"])
    return 'test.epub'
