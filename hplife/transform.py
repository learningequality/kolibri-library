
from bs4 import BeautifulSoup, Tag
import glob
from jinja2 import Template
import json
import os
import re
import requests
import shutil
import tempfile
from urllib.parse import unquote_plus
from urllib.parse import urljoin


from html2text import html2text

from le_utils.constants import content_kinds, file_types, licenses
from ricecooker.utils.zip import create_predictable_zip
from ricecooker.utils.html_writer import HTMLWriter


import slimit
from slimit.parser import Parser
from slimit.visitors import nodevisitor
from slimit import ast
# silence parse warning/errors
# via https://github.com/rspivak/slimit/issues/97#issuecomment-464370110
slimit.lexer.ply.lex.PlyLogger =  \
slimit.parser.ply.yacc.PlyLogger = \
  type('_NullLogger', (slimit.lexer.ply.lex.NullLogger,),
       dict(__init__=lambda s, *_, **__: (None, s.super().__init__())[0]))


# Disable no SSL verify warnings
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)



# TOP-LEVEL FUNCTION
################################################################################

def transform_html(content):
    """
    Transform the HTML markup taken from `content` (str) to file index.html in
    a standalone zip file. Return the neceesary metadata as a dict.
    """
    chef_tmp_dir = 'chefdata/tmp'
    webroot = tempfile.mkdtemp(dir=chef_tmp_dir)

    metadata = dict(
        kind = 'html_content',
        source_id = content[0:30],
        zippath = None,  # to be set below
    )

    doc = BeautifulSoup(content, 'html5lib')
    meta = Tag(name='meta', attrs={'charset':'utf-8'})
    doc.head.append(meta)
    # TODO: add meta language (in case of right-to-left languages)

    # Writeout new index.html
    indexhtmlpath = os.path.join(webroot, 'index.html')
    with open(indexhtmlpath, 'w') as indexfilewrite:
        indexfilewrite.write(str(doc))

    # Zip it
    localize_image_refs(webroot)
    zippath = create_predictable_zip(webroot)
    metadata['zippath'] = zippath

    return metadata




# PARSE COURSE INTRO HTML
################################################################################

COURSE_START_SPLIT_STRINGS = {
    'ar': {
        'cutpoint_starts': [
            'لماذا تبدأ اليوم؟',
            'لماذا نبدأ اليوم؟',
            'لم عليك أن تبدأ اليوم؟',
            'لماذا** ******تبدأ** ******اليوم؟**',
            'لماذا يفيدني البداية اليوم',
        ],
        'cutpoint_start_and_includes': [
            'في هذه الدورة، ستتمكن من:',
        ],
        'cutpoint_ends': [
            'الخطوات في هذه الدورة',
            'خطوات في الدورة التدريبية',
            'خطوات في',
            'الخطوات** ******في** ******الدورة',
            'الخطوات التي تشملها الدورة',
        ],
    },
    'es': {
        'cutpoint_starts': [
            '¿Por qué empezar hoy?',
            '¿Por qué comenzar hoy?',
            '¿Por qué comenzar hoy mismo?',
            '¿Por qué debo empezar hoy mismo?',
        ],
        'cutpoint_start_and_includes': [
            'En este curso',
        ],
        'cutpoint_ends': [
            'Pasos en el curso',
            'Pasos del curso',
            'Etapas del curso',
            'Pasos en el Curso',
            'Pasosen el curso',
            'Este curso fue desarrollado',
            'Este curso se desarrolló',
            'Etapas en el curso',
        ],
    },
    'fr': {
        'cutpoint_starts': [
            'Pourquoi commencer aujourd\'hui ?',
            'Pourquoi commencer aujourd’hui ?',
            'Pourquoi démarrer aujourd\'hui ?',
            'Pourquoi démarrer le cours dès aujourd\'hui?',
        ],
        'cutpoint_start_and_includes': [
            'Durant ce cours, vous allez :',
        ],
        'cutpoint_ends': [
            'Étapes du cours',
            'Etapes du cours',
            'Étapes à suivre',
            'Ce cours a été élaboré',
        ],
    },
    'en': {
        'cutpoint_starts': [
            'Why start today?',
        ],
        'cutpoint_start_and_includes': [
            'In this course, you will:'
        ],
        'cutpoint_ends': [
            'Steps in the course',
            'This course was developed',
        ]
    },
    'hi': {
        'cutpoint_starts': [
            'आज क्यों प्रारंभ करें',
            'आज ही शुरू क्यों करें',
            'आज ही क्यों शुरू करें',
            'आज ही क्यों आरंभ करें',
            'आज ही आरंभ क्यों करें',
        ],
        'cutpoint_start_and_includes': [
            'इस कोर्स को आपको एक विकास इंजिन के विभिन्न',
            'इस कोर्स में आप :',
        ],
        'cutpoint_ends': [
            'पाठ्यक्रम के चरण',
            'पाठ्यक्रम में चरण',
            'कोर्स के चरण',
            'यह पाठ्यक्रम केली स्कूल ऑफ बिज़्नेस',
        ]
    },
    'pt': {
        'cutpoint_starts': [
            'Por que começar hoje?',
        ],
        'cutpoint_start_and_includes': [
            'Aprenda o que é a arte',
            'Neste curso, você irá',
            'Este curso é desenvolvido para',
        ],
        'cutpoint_ends': [
            'Etapas do curso',
            'Etapas do Curso',
            'Etapas no curso',
            'Este curso foi desenvolvido',
            'Grade do curso',
        ]
    },
    'zh': {
        'cutpoint_starts': [
            '为什么从今天开始？',
            '为什么要马上开始？',
            '为何要立即开始？',
            '为什么要从今天开始？',
        ],
        'cutpoint_start_and_includes': [
            '为什么今天开始？',
            '在本课程中，你将：',
        ],
        'cutpoint_ends': [
            '课程步骤',
            '在课程中的步骤',
            '课程提供的步骤',
        ]
    },
}

def get_course_description_from_coursestart_html(content, lang):
    """
    Extracts the course description from the course start HTML content.
    """
    doc = BeautifulSoup(content, 'html5lib')
    body = doc.find('body')
    page_text = html2text(str(body), bodywidth=0)
    if lang == 'hi' and '****' in page_text:  # Dec 18: workaround for html with many **s
        page_text = page_text.replace('**', '')
    # print(page_text)

    SPLIT_STRINGS = COURSE_START_SPLIT_STRINGS[lang]
    course_description_lines = []

    # Process markdown lines
    found_start = False
    found_end = False
    started = False

    for line in page_text.split('\n'):
        if found_start:
            started = True
        if found_end:
            break

        if any(p in line for p in SPLIT_STRINGS['cutpoint_starts']):
            found_start = True
        if any(p in line for p in SPLIT_STRINGS['cutpoint_start_and_includes']) and not found_start:
            found_start = True
            course_description_lines.append(line)
        if any(p in line for p in SPLIT_STRINGS['cutpoint_ends']) and started and not line.startswith('●'):
            if len(''.join(course_description_lines).strip()) > 5:
                found_end = True
            else:
                continue  # keep going if description is too short (workaround for 2455hpl-ar03)

        if started and not found_end:
            course_description_lines.append(line)
        else:
            pass

    if not found_start or not found_end:
        print('ERROR: failed to parse markdown...')
        print(page_text)
        print('\n')

    non_blank_lines = [line for line in course_description_lines if line.strip()]

    # Clean and standardize line outputs
    clean_lines = []
    BOLD_RE = re.compile('\*\*')
    for line in non_blank_lines:
        line = line.replace('**', '').strip()
        line = line.replace('###', '').strip()
        line = line.replace('* · ', '•')
        line = line.replace('·', '•')
        line = line.replace('●', '•')
        line = line.replace('*', '•')
        if line.startswith('_'):
            line = line[1:]
        if line.endswith('_'):
            line = line[:-1]
        #
        if line:
            clean_lines.append(line)

    # prepare output
    couse_description = ''
    for line in clean_lines:
        if len(couse_description) < 400:
            couse_description += ' ' + line.strip()
        else:
            print('SKIPPING desription line', line)

    return couse_description.strip()


def get_activity_descriptions_from_coursestart_html(content, lang):
    """
    Extracts the activity descriptions from the course start HTML content.
    """
    doc = BeautifulSoup(content, 'html5lib')
    tables = doc.find_all('table')
    assert len(tables) == 1, 'uhoh'
    table = tables[0]
    rows = table.find_all('tr')
    # print(table)
    assert len(rows) in [5,6], 'uhoh, expecting table with five rows in coursestart'
    second_col_strings = []
    for row in rows:
        tds = row.find_all('td')
        assert len(tds) == 2, 'uhoh, table has too many cols in coursestart'
        second_col_string = tds[1].text.strip()
        if '\xa0' in second_col_string:
            second_col_string = second_col_string.replace('\xa0', ' ')
        if '\n' in second_col_string:
            second_col_string = second_col_string.replace('\n', ' ')
        second_col_strings.append(second_col_string)
    return {
        'story': second_col_strings[0],
        'businessconcept': second_col_strings[1],
        'technologyskill': second_col_strings[2],
        'nextsteps': second_col_strings[-1],
    }




# TRANSFORM CONTENT FOLDERS
################################################################################


def transform_articulate_storyline_folder(contentdir, activity_ref):
    """
    Transform the contents of the folder of kind `articulate_storyline` called
    `activity_ref` located in the directory `contentdir` to adapt it to Kolibri
    plarform, package it as a zip, and return the neceesary metadata as a dict.
    """
    sourcedir = os.path.join(contentdir, activity_ref)            # source folder
    webroot = os.path.join(contentdir, activity_ref+'_webroot')   # transformed dir

    if not os.path.exists(sourcedir):
        print('WWW Could not find local resource folder for activity_ref=', activity_ref)
        return None
    
    if os.path.exists(webroot):
        shutil.rmtree(webroot)

    # Copy source dir to webroot dir where we'll do the edits and transformations
    shutil.copytree(sourcedir, webroot)
    
    # Remove unnecessary files
    html_files_to_remove = ['story.html', 'story.swf', 'story_flash.html']
    for html_file in html_files_to_remove:
        filepath = os.path.join(webroot, html_file)
        if os.path.exists(filepath):
            os.remove(filepath)

    # Remove all .swf files from webroot/
    for root, dirs, files in os.walk(webroot):
        for file in files:
            filepath = os.path.join(root, file)
            _, ext = os.path.splitext(filepath)
            if ext == '.swf':
                os.remove(filepath)

    metapath = os.path.join(webroot, 'meta.xml')
    metaxml = open(metapath, 'r').read()
    metadoc = BeautifulSoup(metaxml, "html5lib")
    project = metadoc.find('project')
    # TODO: get author from     project > <author name="Victoria" email="" website="" />
    metadata = dict(
        kind = 'articulate_storyline',
        title_en = project['title'],
        source_id = activity_ref,
        thumbnail = os.path.join(webroot, project.attrs['thumburl']),
        datepublished = project['datepublished'],
        duration = project['duration'],
        totalaudio = project['totalaudio'],
        zippath = None,  # to be set below
    )

    # Setup index.html
    indexhtmlpath = os.path.join(webroot,'index.html')
    shutil.move(os.path.join(webroot,'story_html5.html'), indexhtmlpath)
    
    # load index.html
    with open(indexhtmlpath, 'r') as indexfileread:
        indexhtml = indexfileread.read()
    doc = BeautifulSoup(indexhtml, 'html5lib')

    # A. Localize js libs in <HEAD>
    scriptsdir = os.path.join(webroot, 'scripts')
    if not os.path.exists(scriptsdir):
        os.mkdir(scriptsdir)
    headscripts = doc.find('head').find_all('script')
    for script in headscripts:
        script_url = script['src']
        script_basename = os.path.basename(script_url)
        response = requests.get(script_url, verify=False)
        with open(os.path.join(scriptsdir, script_basename), 'wb') as scriptfile:
            scriptfile.write(response.content)
        scriptrelpath = os.path.join('scripts', script_basename)
        script['src'] = scriptrelpath

    # B. Inline css files to avoid CORS issues
    styles = doc.find('body').find_all('link', rel="stylesheet")
    for style in styles:
        style_href = style['href']
        style_path = os.path.join(webroot, style_href)
        if not os.path.exists(style_path) and 'min.css' in style_path:
            style_path = style_path.replace('min.css', 'css')
        style_content = '\n' + open(style_path).read()
        inline_style_tag = doc.new_tag('style')
        inline_style_tag['data-noprefix'] = ''
        inline_style_tag['rel'] = 'stylesheet'
        inline_style_tag.string = style_content
        style.replace_with(inline_style_tag)

    # C. Ensure that js files exist (rewrite app.min.js --> app.js if needed)
    bodyscripts = doc.find('body').find_all('script')
    for script in bodyscripts:
        if script.has_attr('src'):
            script_src = script['src']
            script_path = os.path.join(webroot, script_src)
            if not os.path.exists(script_path) and 'min.js' in script_path:
                new_script_path = script_src.replace('min.js', 'js')
                script['src'] = new_script_path
                print('    replaced script_src', script_src, 'with new_script_path', new_script_path)

    # Save modified index.html
    with open(indexhtmlpath, 'w') as indexfilewrite:
        indexfilewrite.write(str(doc))

    # Zip it
    localize_image_refs(webroot)
    zippath = create_predictable_zip(webroot)
    metadata['zippath'] = zippath

    return metadata



def transform_hpstoryline_folder(contentdir, story_id, node):
    """
    Package the contents of the folder of kind `hpstoryline` called `story_id`
    located in the directory `contentdir` and return the neceesary metadata as a dict.
    """
    sourcedir = os.path.join(contentdir, story_id)
    webroot = os.path.join(contentdir, story_id+'_webroot')   # transformed dir

    if not os.path.exists(sourcedir):
        print('WWW Could not find local resource folder for story_id=', story_id)
        return None

    if os.path.exists(webroot):
        shutil.rmtree(webroot)

    # Copy source dir to webroot dir where we'll do the edits and transformations
    shutil.copytree(sourcedir, webroot)
    metadata = dict(
        kind = 'hpstoryline',
        title_en = node['title'],
        source_id = story_id,
        thumbnail = None, # TODO
        zippath = None,                     # will be set below
    )

    # Zip it
    localize_image_refs(webroot)
    zippath = create_predictable_zip(webroot)
    metadata['zippath'] = zippath

    return metadata


def localize_image_refs(webroot):
    """
    Go through index.html and all .js files in the folder `webroot` and replace
    web-linked images with local ones.
    """
    from sushichef import DEBUG_MODE   # imported here to avoid circular depends

    imagesdir = os.path.join(webroot, 'imagesdir')
    if not os.path.exists(imagesdir):
        os.mkdir(imagesdir)

    # A. Localisze src references for img tags in index.html
    indexhtmlpath = os.path.join(webroot,'index.html')
    with open(indexhtmlpath, 'r') as indexfileread:
        indexhtml = indexfileread.read()
    doc = BeautifulSoup(indexhtml, 'html5lib')
    imgs = doc.find_all('img')
    for img in imgs:
        if img.has_attr('src'):
            img_src = img['src'].strip()
            if img_src.startswith('http'):
                img_basename = os.path.basename(img_src)
                response = requests.get(img_src, verify=False)
                with open(os.path.join(imagesdir, img_basename), 'wb') as imgfile:
                    imgfile.write(response.content)
                imgrelpath = os.path.join('imagesdir', img_basename)
                img['src'] = imgrelpath
                if DEBUG_MODE:
                    print('     replaced img[src] from', img_src, 'to', imgrelpath)
    with open(indexhtmlpath, 'w') as indexfilewrite:
        indexfilewrite.write(str(doc))  # Save modified index.html

    # Define the image resource RE and the download-and-replace helper function
    http_img_pat = re.compile("'((http(s?):)([/|\.|\w|\s|\-|\+])*?\.(jpg|gif|png))'")
    def on_http_img_url(matchobj):
        """Replaces 'http://site/basename.jpg' with 'imagesdir/basename.jpg' """
        img_url = matchobj.group(0)[1:-1]
        img_basename = os.path.basename(img_url)
        try:
            response = requests.get(img_url, verify=False)
            with open(os.path.join(imagesdir, img_basename), 'wb') as imgfile:
                imgfile.write(response.content)
                imgrelpath = os.path.join('imagesdir', img_basename)
                if DEBUG_MODE:
                    print('     js-rewriting img_url from', img_url, 'to', imgrelpath)
                return "'" + imgrelpath + "'"
        except Exception as e:
            print('WARNING: failed to download/rewrite img_url', e)
            return "'" + img_url + "'"

    # B. Search and replace for image refs within all .js files
    js_files_glob_pattern = os.path.join(webroot, '**', '*.js')
    for scriptpath in glob.glob(js_files_glob_pattern, recursive=True):
        with open(scriptpath, 'r') as scriptin:
            script_str = scriptin.read()
        script_out = re.sub(http_img_pat, on_http_img_url, script_str)
        with open(scriptpath, 'w') as scriptout:
            scriptout.write(script_out)





# EXPORT LEGACY hpstoryline STORIES
################################################################################

HPSTORYLINE_BASE_URL = 'https://hpstoryline.edcastcloud.com/hp_storyline/story?story='

PHOTO_CLASS = 'field-name-field-hplife-fotoscreen-photo'
BUBBLES_CLASS = 'field-name-field-hplife-fotoscreen-bubbles'
AUDIO_CLASS = 'field-name-field-hplife-fotoscreen-audio'

ASSETS_DIR_NAME = 'assets'
MEDIA_DIR_NAME='media'
SCRIPTS_DIR_NAME = 'scripts'

def download_hpstoryline(contentdir, story_id):
    """
    Downloads the HTML and all necessary assets to `{contentdir}/{story_id}/`.
    """
    destdir = os.path.join(contentdir, story_id)
    if not os.path.exists(destdir):
        os.makedirs(destdir)

    mediadir = os.path.join(destdir, MEDIA_DIR_NAME)
    if not os.path.exists(mediadir):
        os.makedirs(mediadir)

    assetsdir = os.path.join(destdir, ASSETS_DIR_NAME)
    if not os.path.exists(assetsdir):
        os.makedirs(assetsdir)


    source_url = HPSTORYLINE_BASE_URL + story_id
    html = requests.get(source_url, verify=False).text
    doc = BeautifulSoup(html, 'html5lib')

    # A. Localize js libs
    scriptsdir = os.path.join(destdir, SCRIPTS_DIR_NAME)
    if not os.path.exists(scriptsdir):
        os.mkdir(scriptsdir)
    scripts = doc.find('head').find_all('script')
    for script in scripts:
        if script.has_attr('src'):
            script_url = urljoin(source_url, script['src'])
            script_basename = os.path.basename(script_url)
            destpath = os.path.join(scriptsdir, script_basename)
            if not os.path.exists(destpath):
                response = requests.get(script_url, verify=False)
                script_src = response.text
                edited_script_src = script_src.replace('/assets', 'assets')
                with open(destpath, 'w') as scriptfile:
                    scriptfile.write(edited_script_src)
            scriptrelpath = os.path.join(SCRIPTS_DIR_NAME, script_basename)
            script['src'] = scriptrelpath
        else:
            print('skipping inline script')

    # B. Localize and rewrite css files
    header_links = doc.find('head').find_all('link')
    styles = [link for link in header_links if "stylesheet" in link["rel"]]
    for style in styles:
        style_url = urljoin(source_url, style['href'])
        style_basename = os.path.basename(style_url)
        destpath = os.path.join(assetsdir, style_basename)

        if not os.path.exists(destpath):
            response = requests.get(style_url, verify=False)
            if response.status_code == 200:
                style_str = response.text
                new_style_str = css_rewriter(style_str, source_url, destdir)
                with open(destpath, 'w') as stylefile:
                    stylefile.write(new_style_str)
                    print('\tSaved rewritten css to', destpath)
                    style_rel_path = os.path.join(ASSETS_DIR_NAME, style_basename)
                    style['href'] = style_rel_path
            else:
                print('ERROR failed to GET', style_url)

    # C. Download slideshow assets
    body = doc.find('body')
    main = body.find('div', {'id':'main'})
    article = main.find('article')
    fotonovelas = article.find_all('div', class_="hplife-fotonovela-wrapper")
    for fotonovela in fotonovelas:
        photo_div = None
        bubbles_div = None
        audio_div = None

        fotonovela_divs = fotonovela.find_all('div', recursive=False)
        for div in fotonovela_divs:
            if PHOTO_CLASS in div['class']:
                photo_div = div
            elif BUBBLES_CLASS in div['class']:
                bubbles_div = div
            elif AUDIO_CLASS in div['class']:
                audio_div = div
            else:
                print('unrecognized div', div)

        # C1. download slide bg images 
        # print('photo_div=', photo_div)
        img_rewriter(photo_div, source_url, mediadir)

        # C2.
        # print('bubbles_div=', bubbles_div)
        img_rewriter(bubbles_div, source_url, mediadir)

        # C3. Edit JS code
        # print('audio_div=', audio_div)
        audio_div_script = audio_div.find('script')
        jscode_str = audio_div_script.text
        new_jscode_str = extract_and_download_mp3path(jscode_str, destdir)
        audio_div_script.string = new_jscode_str


    # D. Overlay img (appears in js source)
    overlay_basename = 'play-overlay-fddfa5b71982a2d91bc874f4981abb93.png'
    overlay_url = 'https://hpstoryline.edcastcloud.com/assets/' + overlay_basename
    destpath = os.path.join(assetsdir, overlay_basename)
    if not os.path.exists(destpath):
        response = requests.get(overlay_url, verify=False)
        if response.status_code == 200:
            with open(destpath, 'wb') as overlayimgfile:
                overlayimgfile.write(response.content)
                print('\tSaved overlay_url', overlay_url)

    # E. TODO GET assets/favicon-80ee048bf3522feef23938f79caed29b.ico

    # make sure explicit charset utf-8
    meta = Tag(name='meta', attrs={'charset':'utf-8'})
    doc.head.append(meta)

    indexpath = os.path.join(destdir, 'index.html')
    with open(indexpath,'w') as indexfile:
        indexfile.write(str(doc))



# IMAGES

def img_rewriter(div, source_url, mediadir):
    from sushichef import DEBUG_MODE
    imgs = div.find_all('img')
    assert len(imgs) <= 1, 'more than one img found'
    for img in imgs:
        img_url = urljoin(source_url, img['src'])
        img_basename = os.path.basename(img_url)
        if '%20' in img_basename:
            img_basename = img_basename.replace('%20','_')
        destpath = os.path.join(mediadir, img_basename)
        if not os.path.exists(destpath):
            response = requests.get(img_url, verify=False)
            if response.status_code == 200:
                with open(destpath, 'wb') as imgfile:
                    imgfile.write(response.content)
                    if DEBUG_MODE:
                        print('\tdownloaded img', img_url, 'to', destpath)
            else:
                print('got HTTP', response.status_code, 'for image', img_url)
        img_rel_path = os.path.join(MEDIA_DIR_NAME, img_basename)
        img['src'] = img_rel_path



# CSS rewriter

CSS_URL_RE = re.compile(r"url\(['\"]?(.*?)['\"]?\)")

def css_rewriter(style_str, source_url, destdir):
    from sushichef import DEBUG_MODE
    assetsdir = os.path.join(destdir, ASSETS_DIR_NAME)
    if not os.path.exists(assetsdir):
        os.makedirs(assetsdir)

    # Download linked fonts and images
    def handle_match(match):
        src = match.group(1)
        if '#' in src:
            src = src.split('#')[0]
        if src.startswith('//localhost'):
            print('\t\tfound localhost')
            return 'url()'
        # Don't download data: files
        if src.startswith('data:'):
            # print('\t\tfound data')
            return match.group(0)

        resource_url = urljoin(source_url, src)
        resource_basename = os.path.basename(resource_url)
        destpath = os.path.join(assetsdir, resource_basename)
        if not os.path.exists(destpath):
            response = requests.get(resource_url, verify=False)
            if response.status_code == 200:
                with open(destpath, 'wb') as resourcefile:
                    resourcefile.write(response.content)
                    if DEBUG_MODE:
                        print('\tdownloaded', resource_url, 'to', destpath)
            else:
                # print('got HTTP', response.status_code, 'for url', resource_url)
                return 'url()'

        # need path relative to .css file which is alrady in assets/
        resouce_rel_path = resource_basename
        return 'url("%s")' % resouce_rel_path

    return CSS_URL_RE.sub(handle_match, style_str)



# MP3 path form jscode_str

def extract_and_download_mp3path(jscode_str, destdir, mediadirname=MEDIA_DIR_NAME):
    """
    Extract and rewrite the mp3path path from JavaScript code block jscode_str.
    Returns jscode_str with mp3 path rewritten to `{destdir}/media/{mp3filename}`
    """

    parser = Parser()
    tree = parser.parse(jscode_str)

    found = False
    mp3path = None
    mp3filename = None

    for node in nodevisitor.visit(tree):
        if isinstance(node, ast.Object):
            # Object literal { key: val ...}
            for prop in node:
                left, right = prop.left, prop.right
                if isinstance(left, ast.Identifier) and isinstance(right, ast.String):
                    if left.value == 'mp3':
                        found = True
                        mp3path = right.value.lstrip('"').rstrip('"')
                        mp3filename = os.path.basename(mp3path)
                        assets_path = os.path.join(mediadirname, mp3filename)
                        quoted_assets_path = '"' + assets_path + '"'
                        right.value = quoted_assets_path
    if found:
        destpath = os.path.join(destdir, assets_path)
        if not os.path.exists(destpath):
            response = requests.get(mp3path, verify=False)
            with open(destpath, 'wb') as destfile:
                destfile.write(response.content)
                print('Saved file to', destpath)
        else:
            print('File', destpath, 'already exists')

        return tree.to_ecma()
    else:
        raise ValueError('Could not extract mp3path')







# RESOURCES EXTRACTORS
################################################################################


def extract_course_resouces(parsed_tree, contentdir, course_id, chefargs=None):
    """
    Go through the parsed_tree and:
     - extract all the downloadable resources
     - deduplicate based on source url
     - set title from filename if title missing
     - download them
     - convert any that are in CONVERTIBLE_EXTS


    Modifies the `parsed_tree` to add the new property `resources`:
        parsed_tree = {
            ...
            'resources': [
                {
                    'url': 'https://s3.amazonaws.com/hp-life-content/.../Hoja+de+trabajo.docx',
                    'path': '{contentdir}/downloads/Hoja+de+trabajo.docx',
                    'ext': 'docx',
                    'filename': 'Hoja de trabajo.docx',
                    'title': 'Hoja de trabajo',
                    'convertedfilename': 'Hoja de trabajo.pdf',
                    'convertedpath': '{contentdir}/converted/Hoja de trabajo.pdf',
                },
            ]
        }
    """
    update = True if (chefargs and 'update' in chefargs and chefargs['update']) else False
    resources = []

    # 1. EXTRACT
    ####################################################################

    # 1A. Process the downloadable_resources item
    if 'downloadable_resources' in parsed_tree and parsed_tree['downloadable_resources']: 
        downloadable_resources_item = parsed_tree['downloadable_resources']
        assert downloadable_resources_item['kind'] == 'html'
        downloadable_resources = get_resources_from_downloadable_resouces_item(contentdir, downloadable_resources_item, course_id)
        downloaded_resources = []
        for downloadable_resource in downloadable_resources:
            downloaded_resource = download_resource(downloadable_resource, contentdir, update=update)
            if downloaded_resource:
                downloaded_resources.append(downloaded_resource)
            else:
                print('ERROR: failed to download', downloadable_resource)
        resources.extend(downloaded_resources)
    else:
        print("Course {} doesn't have downloadable_resources".format(course_id))


    # 1B. Check for resources in atriculate storyline items
    for key in ['story', 'businessconcept', 'technologyskill']:
        item = parsed_tree[key]
        kind = item['kind']

        if kind == 'html':
            raise ValueError('unexpected html activity item' + str(item) )

        elif kind == 'problem' and 'activity' in item and item['activity']['kind'] == 'hpstoryline':
            story_id = item['activity']['story_id']
            # print('Skipping hpstoryline resouce', story_id)

        # New-style Articulate Storyline
        elif kind == 'problem' and 'activity' in item:
            activity_ref = item['activity']['activity_ref']
            articulate_storyline_resources = get_resources_from_articulate_storyline(contentdir, activity_ref)
            # print('articulate_storyline_resources=', articulate_storyline_resources)
            resources.extend(articulate_storyline_resources)

    # 2. DE-DUPLICATE `resources` list, preferring resource with title
    ####################################################################
    if resources:
        resources_by_url = {}
        for resource in resources:
            url = resource['url']
            if url not in resources_by_url:
                # Add new resource to the resources_by_url dictionary
                resources_by_url[url] = resource
            else:
                old_resource = resources_by_url[url]
                if not old_resource['title'].strip() and resource['title'].strip():
                    # Repalce existing resource with new one that has a title
                    print('Replacing', old_resource, 'with', resource)
                    resources_by_url[url] = resource
        resources = resources_by_url.values()

    # 3. Set title from filename as fallback to avoid empty titles
    ####################################################################
    if resources:
        for resource in resources:
            if not resource['title'].strip():
                name, _ = os.path.splitext(resource['filename'])
                resource['title'] = name.replace('_', ' ')
                print('Using fallback to set title from filename', resource['title'], 'for URL', resource['url'])

    # 4. TRANSFORM TO PDF all CONVERTIBLE RESOURCES
    ####################################################################
    if resources:
        for resource in resources:
            ext = resource['ext']
            if ext in CONVERTIBLE_EXTS:
                convert_resource(resource, contentdir, update=update)

    # return annotated parsed_tree
    parsed_tree['resources'] = resources
    return parsed_tree





EXTRACTED_DIR_NAME = 'extracted'


ASSETS_URL = 'https://cms-245-hplife.edcastcloud.com/asset-v1:hp-life-e-learning+{course_id}+open+type@asset+block@{filename}'

DEFAULT_EXT_BY_CONTENT_TYPE = {
    'application/pdf': 'pdf',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'docx',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': 'xlsx',
    'application/vnd.openxmlformats-officedocument.presentationml.presentation': 'pptx',
    'application/vnd.oasis.opendocument.spreadsheet': 'ods',
    'application/vnd.ms-excel': 'xls',
}


def get_resources_from_downloadable_resouces_item(contentdir, item, course_id):
    """
    Extracts the resource links from the downloadable resources HTML content of item.
    Returns:
        resources = [
            {
                'url': 'https://s3.amazonaws.com/hp-life-content/.../Hoja+de+trabajo.docx',
                'ext': 'docx',
                'filename': 'Hoja de trabajo.docx',
                'title': 'Hoja de trabajo',
            },
            ...
        ]
    """
    resources = []
    assert item['kind'] == 'html'
    indexhtml = item['content']
    doc = BeautifulSoup(indexhtml, 'html5lib')
    links = doc.find_all('a')
    for link in links:
        if not link.has_attr('href'):
            print('skipping link', link)
            continue
        href = link['href'].strip()
        if 'adobe.com' in href \
            or 'openoffice.org' in href \
            or 'libreoffice.org' in href \
            or 'evernote.com' in href:
            continue

        filename = os.path.basename(href)
        if href.startswith('/'):
            url = ASSETS_URL.format(course_id=course_id, filename=filename)
        else:
            url = href

        response = requests.head(url)
        if response.ok:
            if 'Content-Type' in response.headers:
                content_type = response.headers['Content-Type']
            else:
                print('ERROR: No content_type in header', url, response.status_code, response.headers)
        else:
            print('PROBLEM', url, response.status_code, response.headers)

        _, dotext = os.path.splitext(filename)
        if dotext:
            ext = dotext[1:].lower()
        else:
            ext = DEFAULT_EXT_BY_CONTENT_TYPE[content_type]

        unquoted_filename = unquote_plus(filename)
        unquoted_filename = unquoted_filename.replace('+', '_')
        if '@' in unquoted_filename:
            unquoted_filename = unquoted_filename.split('@')[-1]
        name, _ = os.path.splitext(unquoted_filename)
        localfilename = name + '.' + ext
        resource = dict(
            url=url,
            ext=ext,
            filename=localfilename,
            title=link.text.strip(),
        )
        resources.append(resource)
    return resources


def get_resources_from_articulate_storyline(contentdir, activity_ref):
    """
    Extracts the resource links from the articulate storyline 'frame.json'.
    resources = [dict(
        url='chefdata/{lang}/{course_name}/content/{activity_ref}/story_content/external_files/Additional_Excel_Tips.doc',
        path='chefdata/{lang}/{course_name}/content/extracted/Additional_Excel_Tips.doc',
        ext='doc',
        title='Additional Excel Tips',
    ), ...]
    """
    #print('in get_resource_articulate_storyline for', contentdir, activity_ref)

    resources_links = []

    story_content_path = os.path.join(contentdir, activity_ref, 'story_content')
    if not os.path.exists(story_content_path):
        print( 'No story_content folder in', os.path.join(contentdir,activity_ref) )
    if os.path.exists(story_content_path):
        framepath = os.path.join(story_content_path, 'frame.json')
        if os.path.exists(framepath):
            frame_data = json.load(open(framepath))
            resource_data = frame_data["resource_data"]
            json_resources = resource_data['resources']
            if json_resources:
                for json_resource in json_resources:
                    resource = dict(
                        title=json_resource['title'],
                        relpath=json_resource['url'],
                        iconrelpath=json_resource.get('image', None),
                    )
                    resources_links.append(resource)
        else:
            # if 'frame.json' not found, try to parse 'frame.xml' as fallback
            xmlframepath = os.path.join(story_content_path, 'frame.xml')
            if os.path.exists(xmlframepath):
                # print(xmlframepath)
                frame_data = BeautifulSoup(open(xmlframepath).read(), 'xml')
                resource_data = frame_data.find("resource_data")
                if resource_data:
                    xml_resources = resource_data.find_all('resource')
                    if xml_resources:
                        for xml_resource in xml_resources:
                            resource = dict(
                                title=xml_resource['title'],
                                relpath=xml_resource['url'],
                                iconrelpath=xml_resource.get('image', None),
                            )
                            resources_links.append(resource)
    resources = []
    if resources_links:
        extracteddir = os.path.join(contentdir, EXTRACTED_DIR_NAME)
        if not os.path.exists(extracteddir):
            os.makedirs(extracteddir)
        for resources_link in resources_links:
            abspath = os.path.join(contentdir, activity_ref, resources_link['relpath'])
            _, dotext = os.path.splitext(resources_link['relpath'])
            filename = os.path.basename(abspath)
            destpath = os.path.join(extracteddir, filename)
            if not os.path.exists(abspath):
                continue
            if not os.path.exists(destpath):
                shutil.move(abspath, destpath)
            resource = dict(
                url=abspath,
                path=destpath,
                ext=dotext[1:],
                filename=filename,
                title=resources_link['title'],
            )
            resources.append(resource)
    return resources



# DOWNLOAD RESOURCES
################################################################################
DOWNLOADS_DIR_NAME = 'downloads'

def download_resource(resource, contentdir, update=False):
    from sushichef import DEBUG_MODE
    """
    Downloads the resource path to a local path in {contentdir}/downloads/
    Input:
        resource = {
            'url': 'https://s3.amazonaws.com/hp-life-content/.../Hoja+de+trabajo.docx',
            'ext': 'docx',
            'filename': 'Hoja de trabajo.docx',
            'title': 'Hoja de trabajo',
        }
    Output:
        resource = {
            'url': 'https://s3.amazonaws.com/hp-life-content/.../Hoja+de+trabajo.docx',
            'ext': 'docx',
            'filename': 'Hoja de trabajo.docx',
            'title': 'Hoja de trabajo',
            'path': '{contentdir}/downloads/Hoja+de+trabajo.docx',
        }
        or None if error.
    """
    downloadsdir = os.path.join(contentdir, DOWNLOADS_DIR_NAME)
    if not os.path.exists(downloadsdir):
        os.makedirs(downloadsdir)
    filename = resource['filename']
    destpath = os.path.join(downloadsdir, filename)
    if update or not os.path.exists(destpath):
        download_url = resource['url']
        if DEBUG_MODE:
            print('Downloading resource from', download_url)
        # go GET a sample.docx
        response = requests.get(download_url, verify=False)
        if response.ok:
            with open(destpath, 'wb') as localfile:
                localfile.write(response.content)
        else:
            return None
    assert os.path.exists(destpath), 'ERROR no file saved to ' + str(destpath)
    resource['path'] = destpath
    return resource



# DOCUMENT CONVERSION HELPER
################################################################################

CONVERTIBLE_EXTS = ['doc', 'docx',   'pptx',   'ods', 'xls', 'xlsx']
CONVERTED_DIR_NAME = 'converted'


def convert_resource(resource, contentdir, update=False):
    """
    Convert a Kolibri-imcopatible document format like pptx or docx to pdf
    using the microwave document conversion service.
    Input:
        resource = {
            'path': '{contentdir}/downloads/Hoja+de+trabajo.docx',
            'ext': 'docx',
            'filename': 'Hoja de trabajo.docx',
            'title': 'Hoja de trabajo',
        }
    Output:
      - Saves converted-to-pdf file at `convertedpath` in converted/ dir
      - Modifies the resouce dict to contain convertedfilename and convertedpath
            resource = {
                'path': '{contentdir}/downloads/Hoja+de+trabajo.docx',
                'ext': 'docx',
                'filename': 'Hoja de trabajo.docx',
                'title': 'Hoja de trabajo',
                'convertedfilename': 'Hoja de trabajo.pdf',
                'convertedpath': '{contentdir}/converted/Hoja de trabajo.pdf',
            }
    """
    path = resource['path']

    destdir = os.path.join(contentdir, CONVERTED_DIR_NAME)
    if not os.path.exists(destdir):
        os.makedirs(destdir)

    src_filename = resource['filename']
    name, dotext = os.path.splitext(src_filename)
    ext = dotext[1:]
    assert ext == resource['ext']
    assert ext in CONVERTIBLE_EXTS

    # destination path for converted file
    dest_filename = name + '.pdf'
    destpath = os.path.join(destdir, dest_filename)
    if update or not os.path.exists(destpath):
        print('Convering file', path)
        microwave_url = 'http://35.185.105.222:8989/unoconv/pdf'
        files = {'file': open(path, 'rb')}
        response = requests.post(microwave_url, files=files)
        # save converted output to destination path
        with open(destpath, 'wb') as localfile:
            localfile.write(response.content)

    # add info to resource dict
    resource['convertedfilename'] = dest_filename
    resource['convertedpath'] = destpath


# Downloadable Resouces HTML5App generator
################################################################################

HTML5APP_TEMPLATE = 'chefdata/downloadable_resources_template'
DOWNLOADABLE_RESOURCES_NAME = 'downloadable_resources_webroot'



def make_html5zip_from_resources(resources, contentdir, lang):
    """
    Note: we're assuming resouces are not PDFs, because don't render right.
    """
    zip_path = os.path.join(contentdir, DOWNLOADABLE_RESOURCES_NAME + '.zip')
    if os.path.exists(zip_path):
        os.remove(zip_path)

    # load template
    template_path = os.path.join(HTML5APP_TEMPLATE, 'index.template.html')
    template_src = open(template_path).read()
    template = Template(template_src)

    # prepare template context values
    from sushichef import HPLIFE_STRINGS
    title = HPLIFE_STRINGS[lang]['downloadable_resources']
    content = '    <ul>\n'
    line_template = '      <li><a href="{localhref}">{title}</a></li>\n'
    for resource in resources:
        localhref = './' + resource['filename']
        line = line_template.format(localhref=localhref, title=resource['title'])
        content += line
    content += '    </ul>'

    # save to zip file
    with HTMLWriter(zip_path, 'w') as zipper:
        # index.html = render template to string
        index_html = template.render(
            title=title,
            content=content,
        )
        zipper.write_index_contents(index_html)

        # css/styles.css
        with open(os.path.join(HTML5APP_TEMPLATE, 'css/styles.css')) as stylesf:
            zipper.write_contents('styles.css', stylesf.read(), directory='css/')

        # add files to zip
        for resource in resources:
            filename = resource['filename']
            srcpath = resource['path']
            zipper.write_file(srcpath, filename=filename)

    return zip_path



# DEBUG UTILS
################################################################################

def print_parsed_course_dict(parsed_course):
    """
    Display course tree hierarchy for debugging purposes.
    """
    PARSED_KEYS = [# 'coursestart',
                   'story', 'businessconcept', 'technologyskill',
                   # 'downloadable_resources',
                   'nextsteps', 'nextsteps_video']

    for key in PARSED_KEYS:
        if key in parsed_course and parsed_course[key]:
            item = parsed_course[key]
            extra = ''
            if 'url_name' in item:
                extra += ' url_name=' + item['url_name']
            if 'slug' in item:
                extra += ' slug=' + item['slug']
            if 'activity' in item:
                if item['activity']['kind'] == 'hpstoryline':
                    extra += 'story_id=' + str(item['activity']['story_id'])
                else:
                    extra += 'activity_ref=' + str(item['activity']['activity_ref'])
            # print(item)
            print('   -', key,  'kind='+item['kind'], ' \t', extra)

    if 'resources' in parsed_course:
        resources = parsed_course['resources']
        print('   - resouces:')
        for resource in resources:
            print('       > ', resource['filename'] ) # '   converted =', bool('convertedfilename' in resource) )

    print('\n')
