#!/usr/bin/env python
import base64
from bs4 import BeautifulSoup
from bs4.element import NavigableString
import hashlib
import json
import os
from PIL import Image
import re
import requests
from requests.exceptions import HTTPError, ConnectionError

from urllib.parse import urljoin






from le_utils.constants import content_kinds, exercises, file_types, licenses, roles
from le_utils.constants.languages import getlang  # see also getlang_by_name, getlang_by_alpha2
from ricecooker.chefs import JsonTreeChef
from ricecooker.classes.licenses import get_license
from ricecooker.utils.jsontrees import write_tree_to_json_tree


from ricecooker.config import LOGGER
import logging
LOGGER.setLevel(logging.INFO)


from html2text import html2text
from libpyppeteer import visit_page, get_resource_requests_from_networktab



DEBUG_MODE = True



# EDRAAK CONSTANTS
################################################################################
EDRAAK_DOMAIN = 'edraak.org'
EDRAAK_CHANNEL_DESCRIPTION = """إدراك هي إحدى مبادرات مؤسسة الملكة رانيا في الأردن وهي منصة تزود المتعلمين في المراحل الأساسية والإعدادية والثانوية بدروس مصورة ملحوقة بتمارين تساعدهم في تقدمهم الأكاديمي داخل المدرسة. ومع أنّ المحتوى يتناسب مع المنهاج الوطني الأردني إلا أنه يتناسب أيضا مع كثير من المناهج الدراسية في دول المنطقة الأخرى."""
EDRAAK_LICENSE = get_license(licenses.CC_BY_NC_SA, copyright_holder='Edraak').as_dict()
EDRAAK_MAIN_CONTENT_COMPONENT_ID = '5a6087f46380a6049b33fc19'

EXERCISE_IMAGES_DIR = 'chefdata/exerciseimages/'
EXERCISE_DOWNLOADED_IMAGES_DIR = 'chefdata/downloadedimages/'
EXERCISE_IMAGE_MAX_WIDTH = 500

class UnsupportedMarkdowSyntaxError(Exception):
    """
    This exception is raised when the chef encounters HTML tables with `colspan`
    attributes, which are not supported in Markdown.
    """
    pass


# something breaks when trying to import these exercises --- TODO followup invesigations
EDRAAK_SKIP_COMPONENT_IDS = [
    '5b4c383045dea204a20559b5',
    '5b32a63e4c7ceb04aeb7dbea',
    '5a5c67417dd197717bd70825',
    '5a5c78787dd197717c9c1635',
    '5af3b65f5ad94204a0c934ac',
    '5b704fa7a24abf04a516cbcb',
    '5a55ccd67dd197717c9a1017', # Broken image links from google cloud
]

# Used to temporarily focus work on subset relevant to upcoming Jordan training  TODO uncomment
EDRAAK_SELECTED_COURSES = [
    '5b9e193f78e7f904a04379e0',     # التفاضل والتكامل  = Calculus
    '5b9e191a78e7f904a04379dd',     # الرياضيات التطبيقية (الميكانيكا) = Applied Mathematics (Mechanics)
    '5a60881e6b9064043689772d',     # الإحصاء و الاحتمالات  =  Statistics and Probability
    '5a608819f3a50d049abf68ea',     # الهندسة وعلم المثلثات = Engineering and Trigonometry
    '5a6088188c9a02049a3e69e5',     # الجبر و الأنماط = Algebra and patterns
    '5a608815f3a50d049abf68e9',     # الأعداد والعمليات الحسابية عليها = Numbers and computations
 ]
 



# CRAWLING
################################################################################
START_URL = 'https://www.edraak.org/k12/'
CRAWLING_STAGE_OUTPUT = 'chefdata/trees/web_resource_tree.json'

def get_page(url, loadjs=False, networktab=False):
    """
    Download `url` (following redirects) and soupify response contents.
    Returns (final_url, page) where final_url is URL afrer following redirects.
    """
    result = visit_page(url, loadjs=loadjs, networktab=networktab)
    html = result['content']
    page = BeautifulSoup(html, "html.parser")
    return page


def get_text(element):
    """
    Extract text contents of `element`, normalizing newlines to spaces and stripping.
    """
    if element is None:
        return ''
    else:
        return element.get_text().replace('\r', '').replace('\n', ' ').strip()

def scrape_topics(url):
    """
    Get course links from page 'https://www.edraak.org/k12/'
    The Edraak website calls the different courses topic, e.g. STATS, ALGEBRA, CALC, etc.
    """
    page = get_page(url)
    subject_name = get_text(page.find('div', class_="subject"))
    topics_div = page.find('div', class_="topics")
    topics = []
    for topic_div in topics_div.find_all('div', class_="topic"):
        topic_name = get_text(topic_div.find('div', class_="topic-name"))
        topic_link = topic_div.find('a')
        url = topic_link['href']
        thumbnail_url = topic_link.find('img')['src']
        topic = dict(
            title=topic_name,
            url=url,
            thumbnail_url=thumbnail_url,
        )
        topics.append(topic)
    return topics



def write_web_resource_tree_json(channel_dict):
    destpath = CRAWLING_STAGE_OUTPUT
    parent_dir, _ = os.path.split(destpath)
    if not os.path.exists(parent_dir):
        os.makedirs(parent_dir, exist_ok=True)
    with open(destpath, 'w') as wrt_file:
        json.dump(channel_dict, wrt_file, indent=2, sort_keys=True)


def build_web_resource_tree(start_url):
    channel_dict = dict(
        title='Edraak Channel',
        url=start_url,
        children=[],
    )
    math_dict = dict(
        title='الرياضيات',
        title_en='math',
        children=[],
    )
    channel_dict['children'].append(math_dict)
    
    topics = scrape_topics(start_url)
    for topic in topics:
        print('GET', topic['url'])
        topic_dict = dict(
            title=topic['title'],
            url=topic['url'],
            thumbnail_url=topic['thumbnail_url'],
            children=[],
        )
        topic_dict['root_component_id'] = get_course_root_component_id(topic['url'])
        math_dict['children'].append(topic_dict)

    write_web_resource_tree_json(channel_dict)
    return channel_dict



# WEBSITE SCRAPING
################################################################################

def get_course_root_component_id(url):
    """
    Find the child `component_url` that gets loaded when visiting `url` and walk
    up the component hierarchy until we find the root `component_id` of the course.
    """
    child_component_url = get_child_component_url_from_url(url)

    component_ids = []
    def follow_up(c):
        component_ids.append(c['id'])
        parent_id = c['parent_id']
        if parent_id:
            parent = get_component_from_id(parent_id)
            follow_up(parent)

    topic_item = get_component_from_url(child_component_url)
    follow_up(topic_item)
    assert component_ids[-1] == EDRAAK_MAIN_CONTENT_COMPONENT_ID, 'did not find child of Main Content!'
    return component_ids[-2]  # return the component_id of the course root node


def get_child_component_url_from_url(url):
    """
    Downloads the website page at `url` and watches the network tab to
    extract the `component_url` of the form `/api/component/{component_id}/`.
    This `component_url` corresponds to a the (first) child node within a course.
    """
    result = visit_page(url, loadjs=True, networktab=True)
    networktab = result['networktab']
    resource_requests = get_resource_requests_from_networktab(networktab)
    components = []
    for rr in resource_requests:
        if 'api/component' in rr['url']:
            components.append(rr['url'])
    if len(components) == 0:
        print('url=', url)
        raise ValueError('No components found!')
    elif len(components) == 1:
        print('url=', url)
        raise ValueError('Only a single components found!')
    # THIS IS THE EXPECTED CASE ################################################
    # First request api/compnents request is always the same (algebra), but then
    # the specific request gets loaded a few seconds later (one of the six topics)
    elif len(components) == 2:
        print('found component=', components[-1])
        return components[-1]  # return the last component since it's the one we want
    ############################################################################
    else:
        print('url=', url)
        raise ValueError('More than two component found!')




# API SCRAPING
################################################################################

def get_component_url(component_id):
    return 'https://programs.edraak.org/api/component/' + component_id + '/'

def get_component_from_url(component_url):
    # print('GET', component_url)
    response = requests.get(component_url)
    component = response.json()
    return component

def get_component_from_id(component_id):
    component_url = get_component_url(component_id)
    return get_component_from_url(component_url)








# EXERCISES
################################################################################

def exercise_from_edraak_Exercise_or_Test(exercise, parent_title=None, istest=False):
    """
    Parse an Edraaak `Exercise` or `Test` and create a Kolibri exercise from it.
      - Take questions from: exercise['question_set']['children']
      - Set title based on parent topic
    """
    if parent_title:
        exercise_title = parent_title + ' ' + exercise['title']
    else:
        exercise_title = exercise['title']

    # Exercise node
    exercise_dict = dict(
        kind = content_kinds.EXERCISE,
        title = exercise_title,
        author = 'Edraak',
        source_id=exercise['id'],
        description=exercise['id'] if DEBUG_MODE else '',
        language=getlang('ar').code,
        license=EDRAAK_LICENSE,
        exercise_data={
            'mastery_model': exercises.M_OF_N,
            'randomize': False,
            'm': 3,                   # By default require 3 to count as mastery
        },
        # thumbnail=
        questions=[],
    )
    if istest:
        exercise_dict['role'] = roles.COACH

    # Add questions to exercise node
    question_set = exercise['question_set']
    question_set_children = question_set['children']
    questions = []
    for question in question_set_children:
        try:
            component_type = question['component_type']
            if question['id'] in EDRAAK_SKIP_COMPONENT_IDS:
                continue

            if component_type == 'MultipleChoiceQuestion':
                question_dict = question_from_edraak_MultipleChoiceQuestion(question)
                if question_dict:
                    questions.append(question_dict)

            elif component_type == 'NumericResponseQuestion':
                question_dict = question_from_edraak_NumericResponseQuestion(question)
                if question_dict:
                    questions.append(question_dict)
            else:
                print('skipping component_type', component_type)
        except UnsupportedMarkdowSyntaxError:
            LOGGER.warning('Skipping question ' + question['id'] + ' in exercise id=' + exercise['id'])

    if questions:
        exercise_dict['questions'] = questions
        # Update m in case less than 3 quesitons in the exercise
        if len(questions) < 3:
            exercise_dict['exercise_data']['m'] = len(questions)
        return exercise_dict
    else:
        return None


def question_from_edraak_MultipleChoiceQuestion(question):
    question_md = full_description_str_from_component(question)
    question_dict = dict(
        question_type=exercises.SINGLE_SELECTION,
        id=question['id'],
        question=question_md,
        correct_answer = None,
        all_answers = [],
        hints =[],
    )
    # Add answers to question
    for choice in question['choices']:
        answer_text = text_from_html(choice['description'])
        question_dict['all_answers'].append(answer_text)
        if choice['is_correct']:
            question_dict['correct_answer'] = answer_text

    # Add hints
    for hint in question['hints']:
        if hint['description']:
            hint_text = text_from_html(hint['description'])
            question_dict['hints'].append(hint_text)

    # # Add explanation as last hint
    # if question['explanation']:
    #     explanation_text = text_from_html(question['explanation'])
    #     question_dict['hints'].append(explanation_text)

    return question_dict


def question_from_edraak_NumericResponseQuestion(question):
    question_md = full_description_str_from_component(question)
    question_dict = dict(
        question_type=exercises.INPUT_QUESTION,
        id=question['id'],
        question=question_md,
        answers = [],
        hints =[],
    )
    # Add answers numeric asnwer to question
    correct_ans = question['correct_answer_precise']
    if correct_ans is None:
        print('no correct_answer_precise for', question['id'])
        return None
    correct_ans_str = str(correct_ans)  # pepresent as string even though it's number...
    question_dict['answers'].append(correct_ans_str)

    # Add hints
    for hint in question['hints']:
        if hint['description']:
            hint_text = text_from_html(hint['description'])
            question_dict['hints'].append(hint_text)

    # # Add explanation as last hint
    # if question['explanation']:
    #     explanation_text = text_from_html(question['explanation'])
    #     question_dict['hints'].append(explanation_text)

    return question_dict


# VIDEOS
################################################################################

def extract_youtube_id_from_encoded_videos(encoded_videos):
    for vid in encoded_videos:
        if vid['profile'] == 'youtube':
            return vid['url']

def video_from_edraak_Video(video):
    if 'video_info' not in video:
        return None   #  see README for missing videos list of IDs
    video_title = full_description_str_from_component(video)
    if not video_title:
        video_title = 'Video'
    encoded_videos = video['video_info']['encoded_videos']
    youtube_id = extract_youtube_id_from_encoded_videos(encoded_videos)
    video_dict = dict(
        kind=content_kinds.VIDEO,
        source_id=video['id'],
        title = video_title,
        author = 'Edraak',
        description=video['id'] if DEBUG_MODE else '',
        language=getlang('ar').code,
        license=EDRAAK_LICENSE,
        files=[]
    )
    file_dict = dict(
         file_type=content_kinds.VIDEO,
         youtube_id=youtube_id,
         high_resolution=False
    )
    video_dict['files'].append(file_dict)
    return video_dict





# TREE TRANSFORM
################################################################################

FOLDER_LIKE_CONTENTY_TYPES = [
    'Section',
    'SubSection',
    'OnlineLesson',
]

def node_from_component(component, parent_title=None):
    component_type = component['component_type']

    # Imported components
    if component_type == 'ImportedComponent':
        target_component = component['target_component']
        return node_from_component(target_component)

    # Topic nodes
    if component_type in FOLDER_LIKE_CONTENTY_TYPES:
        print('  - processing folder id=', component['id'])
        topic_dict = dict(
            kind=content_kinds.TOPIC,
            title=component['title'].strip(),
            source_id=component['id'],
            description=component['id'] if DEBUG_MODE else '',
            language=getlang('ar').code,
            license=EDRAAK_LICENSE,
            children=[],
        )
        child_source_ids = []
        for child in component['children']:
            child_node = node_from_component(child, parent_title=component['title'].strip())
            if child_node:
                if child_node['source_id'] not in child_source_ids:
                    topic_dict['children'].append(child_node)
                    child_source_ids.append(child_node['source_id'])
                else:
                    print('Skipping duplicate child with id=', child['id'])

        if topic_dict['children']:
            return topic_dict
        else:
            return None

    elif component_type == 'Video':
        # print('processing video id=', component['id'])
        component_id = component['id']
        video = get_component_from_id(component_id)
        video_dict = video_from_edraak_Video(video)
        return video_dict

    elif component_type == 'Exercise':
        print('processing exercise id=', component['id'])
        component_id = component['id']
        exercise = get_component_from_id(component_id)
        exercise_dict = exercise_from_edraak_Exercise_or_Test(exercise, parent_title=parent_title)
        return exercise_dict

    elif component_type == 'Test':
        print('processing test id=', component['id'])
        component_id = component['id']
        test = get_component_from_id(component_id)
        test_dict = exercise_from_edraak_Exercise_or_Test(test, parent_title=parent_title, istest=True)
        return test_dict

    else:
        print(component)
        raise ValueError('unknown component')




# IMG TRANSFORMS
################################################################################

BASE64_REGEX_STR = r'data:image\/([A-Za-z\+]*);base64,((?:[A-Za-z0-9+\/]{4})*(?:[A-Za-z0-9+\/]{2}==|[A-Za-z0-9+\/]{3}=)*)'
BASE64_REGEX = re.compile(BASE64_REGEX_STR, flags=re.IGNORECASE)

def get_base64_encoding(text):
    return BASE64_REGEX.search(text)

def get_hash_value(text_or_bytes):
    if not type(text_or_bytes) == bytes:
        text_or_bytes = bytes(text_or_bytes, encoding='utf-8')
    hashobj = hashlib.md5()
    hashobj.update(text_or_bytes)
    return hashobj.hexdigest()

def replace_base64_images(page):
    imgs = page.find('body').find_all('img')
    replacement_src = None
    for img in imgs:

        # Step 1. First pre-process any base64 images and download them
        m = get_base64_encoding(img['src'])
        if m:
            if m.group(1) == 'svg+xml':
                ext = '.svg'
            elif m.group(1) == 'png':
                ext = '.png'
            else:
                print(m.group(1))
                raise ValueError('Uknown base64 image format')
            b64data = m.group(2)
            imgdata = base64.b64decode(b64data)
            hashvalue = get_hash_value(b64data)
            filename = hashvalue + ext
            savepath = os.path.join(EXERCISE_IMAGES_DIR, filename)
            if not os.path.exists(savepath):
                with open(savepath, 'wb') as f:
                    f.write(imgdata)
            replacement_src = savepath
        else:
            replacement_src = img['src']
        
        # Step 2. Download image at `replacement_src` if is a HTTP resource
        httpm = re.search('http[s]?://', replacement_src)
        if httpm:
            try:
                response = requests.get(replacement_src)
                if response.status_code == 200:
                    _, imgfilename = os.path.split(replacement_src)
                    _, ext = os.path.splitext(imgfilename)
                    if ext == '':
                        ext = '.png'
                    dfilename = get_hash_value(replacement_src) + ext
                    downloadpath = os.path.join(EXERCISE_DOWNLOADED_IMAGES_DIR, dfilename)
                    with open(downloadpath, 'wb') as f:
                        f.write(response.content)
                    replacement_src = downloadpath
                else:
                    print('Problem downloading image ', replacement_src)
            except (HTTPError, ConnectionError) as e:
                LOGGER.warning('Failed to download img src=' + replacement_src)

        # Step 3. Resize image at `replacement_src` if necessary
        if replacement_src.endswith('.png') and 'http' not in replacement_src:
            print('replacement_src=', replacement_src)
            try:
                image = Image.open(replacement_src)                
                image_width = image.size[0]
                if image_width > EXERCISE_IMAGE_MAX_WIDTH:
                    wpercent = (float(EXERCISE_IMAGE_MAX_WIDTH)/float(image.size[0]))
                    image_height = int((float(image.size[1])*float(wpercent)))
                    image = image.resize((EXERCISE_IMAGE_MAX_WIDTH, image_height), Image.LANCZOS)
                    destpath = replacement_src.replace(EXERCISE_DOWNLOADED_IMAGES_DIR, EXERCISE_IMAGES_DIR)
                    image.save(destpath, compress_level=2)
                    print('resized image', replacement_src, 'to', destpath)
                    replacement_src = destpath
                else:
                    print('image is not too large so leaving alone...')

            except OSError as e:
                print('WARNING problem downloading image', replacement_src, 'so skipping...')

        else:
            pass
            # print('not resizing image because it is not a png', replacement_src)
        img['src'] = replacement_src
    return page


def replace_text_in_tables(page):
    """
    Replace <p> tags with their contents because `html2text` has troubles with p
    tags inside tables.
    """
    tables = page.find('body').find_all('table')
    has_colspan = False
    for table in tables:
        rows = table.find_all(["th", "tr"])
        for row in rows:
            tds = row.find_all('td')
            for td in tds:
                if td.get('colspan') or td.get('rowspan'):
                    raise UnsupportedMarkdowSyntaxError
                new_children = []
                for child in td.children:
                    if type(child) == NavigableString:
                        if child.strip() == '':
                            continue
                        else:
                            new_children.append(child)
                    elif child.name == 'p':
                        # replace p tag with its contents
                        for gchild in child.children:
                            new_children.append(gchild)
                    else:
                        new_children.append(child)
                    child.extract()    # remove child element from containing td
                for new_child in new_children:  # add all new_children to the td
                    td.append(new_child)
    return page

def clean_img_attributes(page):
    """
    Remove image alt and data-mathml attributes because they confuse html2text.
    """
    imgs = page.find_all('img')
    for img in imgs:
        img['alt'] = ''
        img['data-mathml'] = ''
    return page

def text_from_html(html):
    """
    Extract the markdown contents from an HTML snippet
    """
    page = BeautifulSoup(html, 'html5lib')
    # note  BeautifulSoup turned the HTML fragment into a valid HTML document
    # by wrapping in  html > body > {}  and elements
    page = replace_base64_images(page)
    page = replace_text_in_tables(page)
    page = clean_img_attributes(page)
    clean_html = ''.join(str(el) for el in page.find('body').children)
    text = html2text(clean_html, bodywidth=0)
    return text.strip()


def full_description_str_from_component(component):
    full_description = component['full_description']
    if full_description:
        full_description_str = text_from_html(full_description)
    else:
        full_description_str = ''
    return full_description_str




# CHEF
################################################################################

class EdraakChef(JsonTreeChef):
    """
    The chef class that takes care of uploading channel to Kolibri Studio.
    We'll call its `main()` method from the command line script.
    """
    RICECOOKER_JSON_TREE = 'edraak_ricecooker_json_tree.json'

    def pre_run(self, args, options):
        """
        Build the ricecooker json tree for the entire channel.
        """
        LOGGER.info('in pre_run...')

        ricecooker_json_tree = dict(
            title='Edraak (العربيّة)',          # a humand-readbale title
            source_domain=EDRAAK_DOMAIN,       # content provider's domain
            source_id='programs',         # an alphanumeric channel ID
            description=EDRAAK_CHANNEL_DESCRIPTION,
            thumbnail='./chefdata/edraak-logo.png',   # logo created from SVG
            language=getlang('ar').code    ,          # language code of channel
            children=[],
        )
        self.add_content_nodes(ricecooker_json_tree)
        # self.add_sample_content_nodes(ricecooker_json_tree)

        json_tree_path = self.get_json_tree_path()
        write_tree_to_json_tree(json_tree_path, ricecooker_json_tree)


    def add_content_nodes(self, channel):
        """
        Build the hierarchy of topic nodes and content nodes.
        """
        LOGGER.info('Creating channel content nodes...')
        channel_web_rsrc = json.load(open(CRAWLING_STAGE_OUTPUT,'r'))
        for course_web_resouece in channel_web_rsrc['children'][0]['children']:
            root_component_id = course_web_resouece['root_component_id']
            course = get_component_from_id(root_component_id)
            if root_component_id in EDRAAK_SELECTED_COURSES:
                print('Processing course', course['title'], 'id=', course['id'] )
                topic_dict = node_from_component(course)
                topic_dict['thumbnail'] = course_web_resouece['thumbnail_url']
                channel['children'].append(topic_dict)
                print('\n')
            else:
                print('Skipping course', course['title'], 'id=', course['id'] )


    # def add_sample_content_nodes(self, channel):
    # 
    #     sample_exercise_id = '5a4c843b7dd197090857f05c'
    #     exercise = get_component_from_id(sample_exercise_id)
    #     exercise_dict = exercise_from_edraak_Exercise_or_Test(exercise, parent_title='Example MultipleChoiceQuestion')
    #     channel['children'].append(exercise_dict)
    # 
    #     sample_exercise_id2 = '5a4c84377dd197090857ecf2'
    #     exercise2 = get_component_from_id(sample_exercise_id2)
    #     exercise_dict2 = exercise_from_edraak_Exercise_or_Test(exercise2, parent_title='Example NumericResponseQuestion')
    #     channel['children'].append(exercise_dict2)
    # 
    #     # exercise with math images
    #     sample_exercise_id4 = '5a4c9ff07dd197047e9ad8ee'
    #     exercise4 = get_component_from_id(sample_exercise_id4)
    #     exercise_dict4 = exercise_from_edraak_Exercise_or_Test(exercise4, parent_title='Example MultipleChoiceQuestion with images')
    #     channel['children'].append(exercise_dict4)
    # 
    # 
    #     # NEW STUFF
    #     #
    #     exercises_with_tables = [
    #         '5acb6cc06b9064043e21c48a',
    #         '5a4c84497dd197090857fa84',
    #         '5adefc0a6b9064043c647f3b',  # working table
    #         '5b54384045dea204a20aa0e0',  # another working table
    #     ]
    #     for i, sample_exercise_id3 in enumerate(exercises_with_tables):
    #         exercise3 = get_component_from_id(sample_exercise_id3)
    #         exercise_dict3 = exercise_from_edraak_Exercise_or_Test(exercise3, parent_title='Markdown table example ' + str(i+1) )
    #         channel['children'].append(exercise_dict3)
    # 
    #     sample_exercise_id5 = '5b5445bb6b9064043d448ec8'
    #     exercise5 = get_component_from_id(sample_exercise_id5)
    #     exercise_dict5 = exercise_from_edraak_Exercise_or_Test(exercise5, parent_title='SVG images and weird math')
    #     channel['children'].append(exercise_dict5)
    # 
    #     sample_exercise_id6 = '5acb733e3a891b049fe0897c'
    #     # also c0160ae0434e5888a5ea090625ec1703
    #     exercise6 = get_component_from_id(sample_exercise_id6)
    #     exercise_dict6 = exercise_from_edraak_Exercise_or_Test(exercise6, parent_title='Check math alignment for Arabic')
    #     channel['children'].append(exercise_dict6)
    # 
    #     # 'c0160ae0434e5888a5ea090625ec1703' # check 
    #
    #
    #     sample_test_id = '5b3a6d25316e6c04b2919348'
    #     exercise = get_component_from_id(sample_test_id)
    #     test_dict = exercise_from_edraak_Exercise_or_Test(exercise, parent_title='Subsection title', istest=True)
    #     channel['children'].append(test_dict)



# CLI
################################################################################

if __name__ == '__main__':
    """
    This code will run when the sushi chef script is called on the command line.
    """
    chef = EdraakChef()
    chef.main()
