#!/usr/bin/env python

import html
import os
import pprint
import requests

from bs4 import BeautifulSoup
from copy import copy
from le_utils.constants import roles
from PyPDF2 import PdfFileReader, PdfFileWriter

from ricecooker.chefs import SushiChef
from ricecooker.classes.files import DocumentFile, VideoFile
from ricecooker.classes.licenses import get_license
from ricecooker.classes.nodes import ChannelNode, DocumentNode, TopicNode, VideoNode
from ricecooker.utils.pdf import PDFParser

from pointb import PointBVideo

LE = 'Learning Equality'
LANG_CODE_EN = 'en'
LANG_CODE_MY = 'my'
LANG_CODES = (
    LANG_CODE_EN, 
    LANG_CODE_MY,
    )

POINTB = 'Point B Design and Training'
POINTB_URL = 'http://www.pointb.is/'

DOWNLOADS_PATH = os.path.join(os.getcwd(), "downloads/")
DOWNLOADS_VIDEOS_PATH = os.path.join(DOWNLOADS_PATH, "videos/")
PDF_SPLIT_PATH_EN = os.path.join(DOWNLOADS_PATH, '21CSGuide_English_split/')
PDF_SPLIT_PATH_MY = os.path.join(DOWNLOADS_PATH, '21CSGuide_Myanmar_split/')

POINTB_PDF_URL = ''.join([POINTB_URL, 's/'])
CSGUIDE_PDF_EN = '21CSGuide_English.pdf'
CSGUIDE_PDF_EN_CROPPED = '21CSGuide_English_cropped.pdf'
CSGUIDE_PDF_MY = '21CSGuide_Myanmar.pdf'
CSGUIDE_PDF_MY_CROPPED = '21CSGuide_Myanmar_cropped.pdf'
PDF_URL_EN = ''.join([POINTB_PDF_URL, CSGUIDE_PDF_EN])
PDF_URL_MY = ''.join([POINTB_PDF_URL, CSGUIDE_PDF_MY])
PDF_PATH_EN = os.path.join(os.getcwd(), DOWNLOADS_PATH, CSGUIDE_PDF_EN)
PDF_PATH_EN_CROPPED = os.path.join(os.getcwd(), DOWNLOADS_PATH, CSGUIDE_PDF_EN_CROPPED)
PDF_PATH_MY = os.path.join(os.getcwd(), DOWNLOADS_PATH, CSGUIDE_PDF_MY)
PDF_PATH_MY_CROPPED = os.path.join(os.getcwd(), DOWNLOADS_PATH, CSGUIDE_PDF_MY_CROPPED)


DATA = {
    LANG_CODE_EN: {
        'lang_code': LANG_CODE_EN,
        'pdf_info': {
            'pdf_url': PDF_URL_EN, 
            'pdf_path': PDF_PATH_EN,
            'pdf_path_cropped': PDF_PATH_EN_CROPPED,
            'pdf_split_path': PDF_SPLIT_PATH_EN,
            'page_ranges': [
                {'title': 'Introduction', 'page_start': 0, 'page_end': 13},
                {'title': 'Section 1: Setting a Vision for Your 21st Century Learning Classroom', 'page_start': 13, 'page_end': 21},
                {'title': 'Section 2: 21st Century Mindsets and Practices', 'page_start': 21, 'page_end': 61,
                'children': [
                    {'title': 'Mindset #1: Mindfulness', 'page_start': 23, 'page_end': 31},
                    {'title': 'Mindset #2: Curiousity', 'page_start': 31, 'page_end': 37},
                    {'title': 'Mindset #3: Growth', 'page_start': 37, 'page_end': 41},
                    {'title': 'Mindset #4: Empathy', 'page_start': 41, 'page_end': 47},
                    {'title': 'Mindset #5: Appreciation', 'page_start': 47, 'page_end': 51},
                    {'title': 'Mindset #6: Experimentation', 'page_start': 51, 'page_end': 57},
                    {'title': 'Mindset #7: Systems Thinking', 'page_start': 57, 'page_end': 61}
                ]
                },
                {'title': 'Section 3: 21st Century Skills', 'page_start': 61, 'page_end': 69},
                {'title': 'Section 4: Self-Discovery', 'page_start': 69, 'page_end': 95},
                {'title': 'Section 5: 21st Century Skills Building For Teachers', 'page_start': 95, 'page_end': 109},
                {'title': 'Section 6: Integrating 21st Century Skills Into Your Classroom', 'page_start': 109, 'page_end': 135},
                {'title': 'Thanks To Our Teachers', 'page_start': 135, 'page_end': 137},
            ]

        }, 
        'video_info':  {
            'video_url': ''.join([POINTB_URL, '21cs-videos']), 
            'filename_prefix': 'pointb-video-%s-' % LANG_CODE_EN,
            'download_path': os.path.join(os.getcwd(), DOWNLOADS_VIDEOS_PATH, LANG_CODE_EN, ''),
        },
        'video_titles': {  # vimeo id --> title
            '262755467': '',  # 'visual tools
            '262570817': '',  # think pair share
            '262755072': '', # Jigsaw
            '262755673': '', # Daily review
            '267661918': '', # Experiential Learning Cycle
            '262572490': '' # Brainstorming
        },
    },
    LANG_CODE_MY: {
        'lang_code': LANG_CODE_MY,
        'pdf_info': {
            'pdf_url': PDF_URL_MY, 
            'pdf_path': PDF_PATH_MY,
            'pdf_path_cropped': PDF_PATH_MY_CROPPED,
            'pdf_split_path': PDF_SPLIT_PATH_MY,
            'title': '၂၁ ရာစုခေတ်ကာလ၊ စွမ်းရည်ပြည့်ဝ ဆရာဒ ဆရာမ',  # 21st century guide for teachers (PDF title)
            'page_ranges': [
                {'title': 'နိဒါန်းအဖွင့်', 'page_start': 0, 'page_end': 13},  # Introduction
                {'title': '1 - သင်စ် ၂၁ ရာစု စာသင်ခန်းအတွက် မျှော်မှန်းချက်တစ်ခုထားရှိခြင်း', 'page_start': 13, 'page_end': 23},  # Section 1
                {'title': '2 - ၂၁ ရာစု စိတ်နေသဘောထားများနှင့် အလေ့အကျင့်များ', 'page_start': 23, 'page_end': 61,  # Section 2
                'children': [
                    {'title': '#1: စိတ်တည်ငြိမ်မူ သတိအားကောင်းခြင်း', 'page_start': 25, 'page_end': 33},  # Mindfulness
                    {'title': '#2: သိလိုစိတ်ပြင်းပြခြင်း', 'page_start': 33, 'page_end': 39},  # Curiousity
                    {'title': '#3: ရှင်သန်ကြီးထွားသောစိတ်', 'page_start': 39, 'page_end': 43},  # Growth
                    {'title': '#4: ကိုယ်ချင်းစာ  နားလည်စိတ်', 'page_start': 43, 'page_end': 49},  # Empathy
                    {'title': '#5: တန်ဖိုးထား ဆက်ဆံခြင်း', 'page_start': 49, 'page_end': 53},  # Appreciation
                    {'title': '#6: လက်တွေ့စမ်းသပ်ဆောင်ရွက်တတ်အောင်', 'page_start': 53, 'page_end': 59},  # Experimentation
                    {'title': '#7: စနစ်တစ်ခုလုံးအား ခြုံငုံရဲ စဉ်းစားတွေးခေါ်တတ်အောင်', 'page_start': 59, 'page_end': 63}  # Systems Thinking
                ]
                },
                {'title': '3 - စွမ်းဆောင်ရည်မြှင်ရာစုသစ် 21', 'page_start': 63, 'page_end': 75},  # Section 3
                {'title': '4 - ကိုယ်တိုင်စ် အစွမ်းအစများကို ပြန်လည်ရှာဖွေအကဲဖြတ်ခြင်း', 'page_start': 75, 'page_end': 101},  # Section 4
                {'title': '5 - ဆရာ/ဆရာမများအတွက် စွမ်းရည်များ/ကျွမ်းကျင်မှုများ တည်ဆောက်ပေးခြင်း', 'page_start': 101, 'page_end': 117},  # Section 5
                {'title': '6 - ၂၁ ရာစုခေတ်စွမ်းရည်များကို သင်စ် စာသင်ခန်း ထည့်သွင်းလေ့ကျင့်အသုံးချခြင်း', 'page_start': 117, 'page_end': 143},  # Section 6
                {'title': 'ကျေးဇူးတင်စကား', 'page_start': 143, 'page_end': 145},  # Thanks to our teachers
            ]
        },
        'video_info':  {
            'video_url': ''.join([POINTB_URL, '21cs-videos-mm']), 
            'filename_prefix': 'pointb-video-%s-' % LANG_CODE_MY,
            'download_path': os.path.join(os.getcwd(), DOWNLOADS_VIDEOS_PATH, LANG_CODE_MY, '')
        },
        'video_titles': {  # vimeo id --> title
            '262755467': 'သင်ထောက်ကူ ပစ္စည်းများ',  # 'visual tools
            '262570817': 'တွေးပါ! တ္ပဲပါ! မျှဝေပါ',  # think pair share
            '262755072': 'ဂျစ်ဆော', # Jigsaw
            '262755673': 'နေ့စဉ်သုံးသပ်ဆွေးနွေးခြင်းများ', # Daily review
            '267661918': 'အတွေ့အကြုံများကို အခြေခံသော သင်ယူရေးဖြစ်ရပ်ယန္တယား', # Experiential Learning Cycle
            '262572490': 'အင်တိုက်အားတိုက် ခေါင်းချင်းရိုက် အဖြေရှာခြင်း' # Brainstorming
        }
    }
}


def download_pdfs():
    try:
        for i, lang_code in enumerate(DATA):
            pdf = DATA[lang_code]['pdf_info']
            pdf_url = pdf['pdf_url']
            pdf_path = pdf['pdf_path']
            # Do not download if file already exists.
            if os.path.exists(pdf_path):
                print('==> PDF already exists, NOT downloading:', pdf_path)
            else:
                print('==> Downloading PDF', pdf_url, 'TO', pdf_path)
                response = requests.get(pdf_url)
                assert response.status_code == 200
                # save .pdf to the downloads folder
                with open(pdf_path, 'wb') as pdf_file:
                    pdf_file.write(response.content)
                print('... DONE downloading.')

            # crop from two-paged pdf into single-page pdf
            print('==> Cropping from two-page into single-page...', pdf_path)
            pdf_path_cropped = pdf_path.replace('.pdf', '_cropped.pdf')
            split_left_right_pages(pdf_path, pdf_path_cropped)
            # print_pdf_info(pdf_path_cropped)
            print('... DONE cropping.')

        return True
    except Exception as exc:
        print('==> ERROR downloading PDFs: ', exc)
        return False


def split_chapters(lang_code):
    """
    Splits the chapters for the PDFs.
    """
    pdf = DATA[lang_code]['pdf_info']
    page_ranges = pdf['page_ranges']
    pdf_path_cropped = pdf['pdf_path_cropped']
    pdf_split_path = pdf['pdf_split_path']

    print('==> Splitting chapters for', pdf_path_cropped)
    print('====> PDF_PATH_CROPPED', pdf_path_cropped, 'PDF_SPLIT_PATH', pdf_split_path)
    with PDFParser(pdf_path_cropped, directory=pdf_split_path) as pdfparser:
        chapters = pdfparser.split_subchapters(jsondata=page_ranges)
        # for chapter in chapters:
        #     print(chapter)
    print('==> DONE splitting chapters for {} PDF.'.format(lang_code))
    return chapters


def get_dimensions(pdfin1):
    """
    Get dimensions of second page in PDF file `pdfin1`.
    Returns tuple: (half_width, full_height)
    """
    page = pdfin1.getPage(2)
    double_page_width = page.mediaBox.getUpperRight_x()
    page_width = double_page_width / 2
    page_height = page.mediaBox.getUpperRight_y()
    return page_width, page_height


def split_left_right_pages(pdfin_path, pdfout_path):
    """
    Splits the left and right halves of a page into separate pages.
    We also remove the binders between those separated pages.
    """
    # REF: https://gist.github.com/mdoege/0676e37ee2470fc755ea98177a560b4b
    # RELATED-REF: https://github.com/mstamy2/PyPDF2/issues/100

    pdfin1 = PdfFileReader(open(pdfin_path, "rb"))  # used for left pages
    pdfout = PdfFileWriter()

    num_pages = pdfin1.getNumPages()
    page_ranges = [pdfin1.getPage(i) for i in range(0, num_pages)]
    for nn, left_page in enumerate(page_ranges):
        # use copy for the right pages
        right_page = copy(left_page)
        # copy the existing page dimensions
        (page_width, page_height,) = left_page.mediaBox.upperRight

        is_first_page = (nn == 0)
        is_last_page = (nn + 1 >= num_pages)
        if is_first_page or is_last_page:
            # The first page has the binder to its left while the last page
            # has the binder to its right.
            binder_width = 40
            if is_first_page:
                (page_width, page_height,) = right_page.mediaBox.upperLeft
                right_page.mediaBox.upperLeft = (page_width + binder_width, page_height,)
            if is_last_page:
                (page_width, page_height,) = right_page.mediaBox.upperRight
                right_page.mediaBox.upperRight = (page_width - binder_width, page_height,)
        else:
            # Divide the width by 2 for the other pages (except first and last).
            # We also remove the binders on the left-side of the right pages
            # and the right-side of the left pages.
            page_width = page_width / 2
            binder_width = 20
            right_page.mediaBox.upperLeft = (page_width + binder_width, page_height,)
            left_page.mediaBox.upperRight = (page_width - binder_width, page_height,)
            pdfout.addPage(left_page)
        pdfout.addPage(right_page)

    with open(pdfout_path, "wb") as out_f:
        pdfout.write(out_f)


def print_pdf_info(pdf_path):
    pp = pprint.PrettyPrinter()
    pdf = PdfFileReader(open(pdf_path, "rb"))
    page_width, page_height = get_dimensions(pdf)
    print('==> PDF INFO:', page_width, page_height)
    num_pages = pdf.getNumPages()
    for page_num in range(0, num_pages):
        page = pdf.getPage(page_num)
        this_width = page.mediaBox.getUpperRight_x()
        this_height = page.mediaBox.getUpperRight_y()
        print('==> page', page_num, 'this_width',
              this_width, 'this_height', this_height)
        # pretty print the last 3 pages
        # if page_num + 3 >= num_pages:
        #     pp.pprint(page)


def scrape_video_data(url, lang_code, filename_prefix):
    """
    Scrapes videos based on the URL passed and returns a list of PointBVideo objects.
    For efficiency, the actual download will be done outside of this function, 
    after all video links have been collected.
    """
    video_data = []
    pp = pprint.PrettyPrinter()
    try:
        if lang_code in LANG_CODES:
            print('==> SCRAPING', url)
            response = requests.get(url)
            page = BeautifulSoup(response.text, 'html5lib')

            content_divs = page.find_all('div', class_='content-inner')
            for content_div in content_divs:
                video_block = content_div.find('div', class_='video-block')
                video_wrapper = video_block.find('div', class_='sqs-video-wrapper')
                data_html_raw = video_wrapper['data-html']
                data_html = html.unescape(data_html_raw)
                chunk = BeautifulSoup(data_html, 'html5lib')
                iframe = chunk.find('iframe')
                src = iframe['src']
                title = iframe['title']

                # print('==> SCRAPED VALUES')
                description = ''  # Get from the scraped page details
                block_html = content_div.find_all('div', class_='sqs-block html-block sqs-block-html')
                if isinstance(block_html, list) and len(block_html) > 1:
                    # Video description is the second div block.
                    desc_block = block_html[1]
                    block_content = desc_block.find('div', class_='sqs-block-content')
                    # print('==> BLOCK_CONTENT', block_content)
                    # NOTE: Some descriptions have <em> etc tags, some are separated by <br/> tags, while
                    # most are separated with <p> tags.  So we use `get_text(" ") - replacing those tags
                    # with " " and then stripping whitespaces for a "clean" description.`
                    description = block_content.get_text(" ", strip=True)
                    # print('==> DESCRIPTION', description)
                # print('==> url==', src)
                # print('==> title==', title)
                # print('==> description==', description)
                # print('==> DONE with SCRAPED VALUES')

                video = PointBVideo(
                            url=src, 
                            title=title, 
                            description=description, 
                            lang_code=lang_code,
                            filename_prefix=filename_prefix)
                video_data.append(video)
    except Exception as e:
        print('==> Error scraping video URL', lang_code)
        pp.pprint(e)
    return video_data


def download_videos(lang_code):
    """
    Scrape, collect, and download the videos and their thumbnails.
    """
    video_data = []
    vinfo = DATA[lang_code]['video_info']
    try:
        download_path = vinfo['download_path']
        video_data = scrape_video_data(
                            vinfo['video_url'], 
                            lang_code, 
                            vinfo['filename_prefix'])
        print('==> DOWNLOADING', download_path, '====> vinfo', vinfo)
        # Download video and metadata info for all video objects collected.
        for i, video in enumerate(video_data):
            progress = '%d/%d' % (i+1, len(video_data),)
            progress = '==> %s: Downloading video from %s ...' % (progress, video.url,)
            print(progress)
            video.download(download_dir=download_path, video_data=DATA)
    except Exception as e:
        print('Error downloading videos:')
        pp = pprint.PrettyPrinter()
        pp.pprint(e)
        raise e
    print('==> DONE downloading videos for', vinfo)
    return video_data


def build_english_video_topics(topic):
    """
    """
    video_data = download_videos(LANG_CODE_EN)
    if not video_data:
        print('==> Download of Videos FAILED!')
        return False

    # NOTE(cpauya: VideoNode constructor has no argument for language code?
    for i, video in enumerate(video_data):
        filepath = video.filepath
        title=video.title.replace('(English Language)', '').strip()
        video_node = VideoNode(
                source_id=video.uid, 
                title=title, 
                description=video.description,
                aggregator=LE,
                thumbnail=video.thumbnail,
                license=get_license("CC BY-NC-SA", copyright_holder=POINTB),
                role=roles.COACH,
                files=[
                    VideoFile(
                        path=filepath,
                        language=LANG_CODE_EN
                    )
                ])
        topic.add_child(video_node)

    return topic


def build_burmese_video_topics(topic):
    """
    """
    video_data = download_videos(LANG_CODE_MY)
    if not video_data:
        print('==> Download of Videos FAILED!')
        return False

    for i, video in enumerate(video_data):
        filepath = video.filepath
        video_node = VideoNode(
                source_id=video.uid, 
                title=video.title, 
                description=video.description,
                aggregator=LE,
                thumbnail=video.thumbnail,
                license=get_license("CC BY-NC-SA", copyright_holder=POINTB),
                role=roles.COACH,
                files=[
                    VideoFile(
                        path=filepath,
                        language=LANG_CODE_MY
                    )
                ])
        topic.add_child(video_node)
    return topic


def build_pdf_topics(main_topic, sections, lang_code):
    """
    Adds the documents from the sections tree to the `main_topic`.
     - CASE A = no children => add as DocumentNode
     - CASE B = has children => add as TopicNode and add all children as DocumentNode
    """
    LICENSE = get_license("CC BY-NC-SA", copyright_holder=POINTB)

    for i, section in enumerate(sections):

        # CASE A: All sections except Section 2
        if 'children' not in section:
            title = section['title']
            abspath = section['path']
            filename = os.path.basename(abspath)
            doc_node = DocumentNode(
                title=title,
                description='Chapter from A GUIDE TO BECOMING A 21ST CENTURY TEACHER',
                source_id='%s-%s' % (filename, lang_code),
                license=LICENSE,
                aggregator=LE,
                language=lang_code,
                role=roles.COACH,
                files=[
                    DocumentFile(
                        path=abspath,
                        language=lang_code
                    )
                ])
            main_topic.add_child(doc_node)
        
        # CASE B: Section 2
        else:
            section_topic = TopicNode(
                title=section['title'],
                source_id="pointb_section_" + str(i)
            )
            main_topic.add_child(section_topic)
            
            for subsection in section['children']:
                title = subsection['title']
                abspath = subsection['path']
                filename = os.path.basename(abspath)
                subsection_doc_node = DocumentNode(
                    title=title,
                    description='',
                    source_id='%s-%s' % (filename, lang_code),
                    license=LICENSE,
                    aggregator=LE,
                    language=lang_code,
                    role=roles.COACH,
                    files=[
                        DocumentFile(
                            path=abspath,
                            language=lang_code
                        )
                    ])
                section_topic.add_child(subsection_doc_node)

    return main_topic



class PointBChef(SushiChef):
    channel_info = {
        "CHANNEL_TITLE": "PointB 21CS Guide",
        "CHANNEL_SOURCE_DOMAIN": "pointb.is",
        "CHANNEL_SOURCE_ID": "pointb-21csguide",
        "CHANNEL_LANGUAGE": "mul",  # le_utils language code
        "CHANNEL_THUMBNAIL": 'chefdata/channel_thumbnail.png',
        # (optional)
        "CHANNEL_DESCRIPTION": "Guide To Becoming A 21St Century Teacher",
    }

    def construct_channel(self, **kwargs):

        if not download_pdfs():
            print('==> Download of PDFS FAILED!')
            return False

        chapters_en = split_chapters(LANG_CODE_EN)
        if chapters_en is None:
            print('==> Split chapters for en PDFs FAILED!')
            return False
        chapters_my = split_chapters(LANG_CODE_MY)
        if chapters_en is None:
            print('==> Split chapters for my PDFs FAILED!')
            return False

        channel = self.get_channel(**kwargs)

        # English topics
        main_topic = TopicNode(title="English", source_id="pointb_en_main")
        topic_guide = TopicNode(title="21st Century Guide", source_id="pointb_en_topic")
        topic_videos_en = TopicNode(title="Videos", source_id="pointb_en_videos")
        main_topic.add_child(topic_guide)
        main_topic.add_child(topic_videos_en)

        # Burmese topics
        main_topic_my = TopicNode(title="Burmese", source_id="pointb_my_main")
        topic_guide_my = TopicNode(title="21st Century Guide", source_id="pointb_my_guide")
        topic_videos_my = TopicNode(title="Videos", source_id="pointb_my_videos")
        main_topic_my.add_child(topic_guide_my)
        main_topic_my.add_child(topic_videos_my)

        channel.add_child(main_topic)
        channel.add_child(main_topic_my)

        # English topics
        build_pdf_topics(topic_guide, chapters_en, lang_code=LANG_CODE_EN)
        # Burmese topics
        build_pdf_topics(topic_guide_my, chapters_my, lang_code=LANG_CODE_MY)
        # English videos
        topic = build_english_video_topics(topic_videos_en)
        # Burmese videos
        topic = build_burmese_video_topics(topic_videos_my)

        return channel


if __name__ == "__main__":
    """
    Run this script on the command line using:
        python sushichef.py -v --reset --token=YOURTOKENHERE9139139f3a23232
    """
    chef = PointBChef()
    chef.main()
    # local_construct_pdfs()
    # local_construct_videos()
