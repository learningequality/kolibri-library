#!/usr/bin/python
# -*- coding: utf-8 -*-

from collections import defaultdict
from jinja2 import Template
import json
import os
import requests
import pprint
import shutil

from le_utils.constants import content_kinds, exercises, file_types, licenses, format_presets
from le_utils.constants.languages import getlang
from ricecooker.chefs import JsonTreeChef
from ricecooker.config import LOGGER
from ricecooker.classes.licenses import get_license
from ricecooker.utils.html_writer import HTMLWriter
from ricecooker.utils.jsontrees import write_tree_to_json_tree
from ricecooker.classes.files import AudioFile
from ricecooker import config



# KAMKALIMA CONSTANTS
################################################################################
KAMKALIMA_DOMAIN = "https://kamkalima.com"
KAMKALIMA_CHANNEL_DESCRIPTION = """تقدم المصادر التعليمية الخاصة باللغة العربية من منصة كم كلمة محتوى عربي متفاعل لمتعلمي ومعلمي المرحلة الثانوية. وتمكن النصوص والأنشطة التفاعلية المتعلمين من تطوير مهارات الاستماع والقراءة بالإضافة إلى مهارات وقواعد الكتابة العربية. وتقدم القناة للمعلمين مجموعة من الأدوات التربوية لتمكنهم من متابعة تقدم وتعلم المتعلمين على اختلاف مستوياتهم."""
KAMKALIMA_LICENSE = get_license(
    licenses.CC_BY_NC_ND, copyright_holder="Kamkalima"
).as_dict()

# KAMKALIMA API
################################################################################
AUTHORIZATION_ENDPOINT = KAMKALIMA_DOMAIN + "/oauth/token"
API_AUDIOS_ENDPOINT = KAMKALIMA_DOMAIN + "/api/v1/content/audios"
API_TEXTS_ENDPOINT = KAMKALIMA_DOMAIN + "/api/v1/content/texts"

CLIENT_CREDENTIALS_PATH = "credentials/client_credentials.json"


HTML5APP_ZIPS_LOCAL_DIR = "chefdata/zipfiles"
HTML5APP_TEMPLATE = "chefdata/html5app_template"

# CONSTANTS
FAILED_NODES = os.path.join('chefdata', 'failed_nodes')
FAILED_NODES_JSON = os.path.join(FAILED_NODES, 'failed_nodes.json')
# AUTHENTICATION API
################################################################################

def get_authentication_token():
    """
    Call `/oauth/token` to obtain `access_token` for use with the content API.
    """
    client_credentials = json.load(open(CLIENT_CREDENTIALS_PATH))
    data = {
        "grant_type": "client_credentials",
        "client_id": client_credentials["client_id"],
        "client_secret": client_credentials["client_secret"],
    }
    response = requests.post(AUTHORIZATION_ENDPOINT, data=data)
    if response.ok:
        access_token = response.json()['access_token']
        LOGGER.info('Successfully obtained authorization token')
        return access_token
    else:
        raise ConnectionError('Get auth token failed ' + AUTHORIZATION_ENDPOINT)



# API EXTRACT FUNCTIONS
################################################################################

def get_all_items(start_url, access_token):
    """
    Get items from all pages through the API (texts or audios).
    """
    all_items = []
    current_url = start_url
    while True:
        headers = {
            'Authorization': 'Bearer ' + access_token
        }
        LOGGER.debug('GET ' + current_url)
        resp = requests.get(current_url, headers=headers)
        if not resp.ok:
            LOGGER.error("Response " + str(resp.status_code) + " on " + current_url)
            break
        data = resp.json()
        items = data["items"]
        all_items.extend(items)
        if (
            "next_page_url" in data
            and data["next_page_url"]
            and KAMKALIMA_DOMAIN in data["next_page_url"]
        ):  # key exists, is not null, and looks like a valid URL
            current_url = data["next_page_url"]
        else:
            LOGGER.debug('Reached end of API results')
            break
    if all_items:  # > 0
        LOGGER.info("  Found %s items" % len(all_items) )
        return all_items
    else:
        raise RuntimeError("Kamkalima API not accessible or 0 items returned.")


# TRANSFORM FUNCTIONS
################################################################################

EXERCISE_CATEGORY_LOOKUP = {
    "comprehension": "الاستيعاب",
    "grammar": "القواعد",
    "listening": "الاستماع",
    "vocabulary": "المفردات والتراكيب",
}
# EXERCISE_AR = 'ممارسه الرياضه'  # Maybe add this to each catrogy??


def exercise_from_kamkalima_questions_list(item_id, category, exercise_questions):
    exercise_title = EXERCISE_CATEGORY_LOOKUP[category]
    # Exercise node
    exercise_dict = dict(
        kind=content_kinds.EXERCISE,
        title=exercise_title,
        author="Kamkalima",
        source_id=str(item_id) + ":" + category,
        description="",
        language=getlang("ar").code,
        license=KAMKALIMA_LICENSE,
        exercise_data={
            "mastery_model": exercises.M_OF_N,
            "randomize": False,
            "m": 3,  # By default require 3 to count as mastery
        },
        # thumbnail=
        questions=[],
    )
    # Add questions to exercise node
    questions = []
    for exercise_question in exercise_questions:
        question_dict = dict(
            question_type=exercises.SINGLE_SELECTION,
            id=str(exercise_question["id"]),
            question=exercise_question["title"],
            correct_answer=None,
            all_answers=[],
            hints=[],
        )
        # Add answers to question
        for answer in exercise_question["answers"]:
            answer_text = answer["title"]
            if answer_text not in question_dict["all_answers"]:
                question_dict["all_answers"].append(answer_text)
                if answer["is_correct"]:
                    question_dict["correct_answer"] = answer_text
            else:
                LOGGER.warning("Duplicate answer in id=" + question_dict["id"])
        questions.append(question_dict)
    exercise_dict["questions"] = questions
    # Update m in case less than 3 quesitons in the exercise
    if len(questions) < 3:
        exercise_dict["exercise_data"]["m"] = len(questions)
    return exercise_dict


def group_by_theme(items):
    items_by_theme = defaultdict(list)
    for item in items:
        themes = item["themes"]
        for theme in themes:
            theme_name = theme["name"]
            items_by_theme[theme_name].append(item)
    return items_by_theme
    

# def filter_by_theme(items_by_grade):
#     filtered_by_theme = defaultdict(list)
#     for grade in items_by_grade:


def group_items_by_grade_and_theme(items):
    grade_key = {
        4 : "صف ٤-٦",
        7 : "صف ٧-٩",
        10 : "صف ١٠-١٢"
    }

    items_by_grade_and_theme = defaultdict(list)
    for item in items:
        min_level = item["min_level"]
        grade_level = grade_key[min_level]
        if grade_level not in items_by_grade_and_theme.keys():
            items_by_grade_and_theme[grade_level] = defaultdict(list)
        themes = item["themes"]
        for theme in themes:
            theme_name = theme["name"]
            items_by_grade_and_theme[grade_level][theme_name].append(item)
    return items_by_grade_and_theme
        
        

def audio_node_from_kamkalima_audio_item(audio_item):
    if not audio_item["audio"]:
        LOGGER.error('No audio URL for audio id=' + str(audio_item['id']) + '  with title=' + audio_item['title'])
        return None
    audio_node = dict(
        kind=content_kinds.AUDIO,
        source_id=str(audio_item["id"]),
        title=audio_item["title"],
        description=audio_item["excerpt"],
        language=getlang("ar").code,
        license=KAMKALIMA_LICENSE,
        author=audio_item["author"]["name"],
        # aggregator
        # provider
        thumbnail=audio_item["image"],
        files=[
            {
                "file_type": file_types.AUDIO,
                "path": audio_item["audio"],
                "language": getlang("ar").code, 
            }
        ],
    )
    return audio_node


def make_html5zip_from_text_item(text_item):
    id_str = str(text_item["id"])
    zip_path = os.path.join(HTML5APP_ZIPS_LOCAL_DIR, id_str + ".zip")

    # check for audio element
    show_audio_element = False
    audio_href = ''
    audio_file = None
    if text_item['audio']:
        show_audio_element = True
        audio_file = AudioFile(path = text_item["audio"], preset = format_presets.AUDIO_DEPENDENCY)
        audio_filename = audio_file.get_filename()
        first_char_filename = audio_filename[0]
        second_char_filename = audio_filename[1]
        audio_href = "../../storage/{}/{}/{}".format(first_char_filename, second_char_filename, audio_filename)

    if os.path.exists(zip_path):
        LOGGER.debug("Found existing zip at " + zip_path)
        return zip_path, audio_file
    else:
        LOGGER.debug("Creating zip from text_item id=" + str(text_item['id']))

    # load template
    template_path = os.path.join(HTML5APP_TEMPLATE, "index.template.html")
    script_highlighter_path = os.path.join(HTML5APP_TEMPLATE, "text-highlighter-script.js")
    template_src = open(template_path).read()
    template = Template(template_src)

    # extract properties
    time_object = json.loads(text_item['time_object'])
    title = text_item["title"]
    content = text_item["body"]
    author=text_item["author"]["name"],
    description = text_item["excerpt"]
    if "image" in text_item:
        splash_image_url = text_item["image"]
        show_splash_image = True
    else:
        show_splash_image = False

    # render template to string
    index_html = template.render(
        title=title,
        content=content,
        author=author,
        description=description,
        show_splash_image=show_splash_image,
        show_audio_element = show_audio_element,
        audio_href = audio_href,
        time_object=time_object
    )

    # save to zip file
    with HTMLWriter(zip_path, "w") as zipper:
        # index.html
        zipper.write_index_contents(index_html)
        zipper.write_file(script_highlighter_path,filename='text-highlighter-script.js')
        # css/styles.css
        with open(os.path.join(HTML5APP_TEMPLATE, "css/styles.css")) as stylesf:
            zipper.write_contents("styles.css", stylesf.read(), directory="css/")
        if show_splash_image:
            # img/splash.jpg
            resp = requests.get(splash_image_url)
            zipper.write_contents("splash.jpg", resp.content, directory="img/")
        else:
            LOGGER.warning("zip with id " + id_str + " has no splash image")

    return zip_path, audio_file


def html5_node_from_kamkalima_text_item(text_item):
    zip_path, audio_file = make_html5zip_from_text_item(text_item)
    print(zip_path)
    files=[
        {
            "file_type": file_types.HTML5,
            "path": zip_path,
            "language": getlang("ar").code,
        },
    ]
    # add audio_file to files if exists
    if audio_file is not None:
        audio_path = config.get_storage_path(audio_file.get_filename())
        files.append(
            {
                "file_type": file_types.AUDIO,
                "path": audio_path,
                "language": getlang("ar").code,
                "preset": format_presets.AUDIO_DEPENDENCY
            }
        )

    html5_node = dict(
        kind=content_kinds.HTML5,
        source_id=str(text_item["id"]),
        title=text_item["title"],
        description=text_item["excerpt"],
        language=getlang("ar").code,
        license=KAMKALIMA_LICENSE,
        author=text_item["author"]["name"],
        # aggregator
        # provider
        thumbnail=text_item["image"],
        files= files
    )
    return html5_node


def topic_node_from_item(item_type, item):
    """
    In order to keep the audios and texts close to their associated exercises,
    we'll store each item as a topic node.
    `item_type` is either `audio` or `text`
    """
    topic_node = dict(
        kind=content_kinds.TOPIC,
        source_id=str(item["id"]) + ":" + "container",
        title=item["title"],
        # description=item['excerpt'],
        language=getlang("ar").code,
        children=[],
    )

    # Add content node
    if item_type == "audio":
        audio_node = audio_node_from_kamkalima_audio_item(item)
        if audio_node:
            topic_node["children"].append(audio_node)
    elif item_type == "text":
        html5_node = html5_node_from_kamkalima_text_item(item)
        if html5_node:
            topic_node["children"].append(html5_node)
    else:
        raise ValueError("unrecognized item_type " + item_type)

    # Add associated exercises
    item_id = item["id"]
    for category, exercise_questions in item["questions"].items():
        if len(exercise_questions) < 1:
            LOGGER.info("No exercise questions for exercise id: {}, in category: {}".format(item_id, category))
            print(item["title"])

            with open(FAILED_NODES_JSON, "w", encoding = "utf-8") as f:
                dict_failed = {}
                dict_failed["id"] = item_id
                dict_failed["title"] = item["title"]
                dict_failed["category_failed"] = category
                json.dump(dict_failed, f, indent=2, ensure_ascii=False)
                continue
    

        exercise_node = exercise_from_kamkalima_questions_list(
            item_id, category, exercise_questions
        )
        topic_node["children"].append(exercise_node)

        
    return topic_node


# CHEF
################################################################################


class KamkalimaChef(JsonTreeChef):
    """
    The chef class that takes care of uploading channel to Kolibri Studio.
    We'll call its `main()` method from the command line script.
    """

    RICECOOKER_JSON_TREE = "kamkalima_ricecooker_json_tree.json"

    def pre_run(self, args, options):
        """
        Build the ricecooker json tree for the entire channel.
        """
        LOGGER.info("in pre_run...")

        # create faulty nodes JSON
        if os.path.exists(FAILED_NODES):
            os.remove(FAILED_NODES_JSON)
        else:
            os.makedirs(FAILED_NODES, exist_ok=True)
        # create json file
        with open(FAILED_NODES_JSON, 'w+'):
            pass
        if args["update"]:
            LOGGER.info(
                "Deleting all zips in cache dir {}".format(HTML5APP_ZIPS_LOCAL_DIR)
            )
            for zip_file in os.listdir(HTML5APP_ZIPS_LOCAL_DIR):
                zip_file_abs_path = os.path.join(HTML5APP_ZIPS_LOCAL_DIR, zip_file)
                if zip_file_abs_path.endswith(".zip"):
                    os.remove(zip_file_abs_path)

        ricecooker_json_tree = dict(
            # channel_id = 'e5d5dac2cd8d4059baddaa348714fa7c',  # test channel id
            # channel_id = 'd76da4d36cfd59279b575dfc6017aa13',    # main channel_id
            channel_id = 'kamkalima_test_id_test',    # test channel_id
            title="Kamkalima (العربيّة) Test",  # a humand-readbale title
            source_domain=KAMKALIMA_DOMAIN,  # content provider's domain
            source_id="audios-and-texts_test-test",  # an alphanumeric channel ID
            description=KAMKALIMA_CHANNEL_DESCRIPTION,
            thumbnail="kk-logo.png",  # logo created from SVG
            language=getlang("ar").code,  # language code of channel
            children=[],
        )
        self.add_content_nodes(ricecooker_json_tree)

        json_tree_path = self.get_json_tree_path()
        write_tree_to_json_tree(json_tree_path, ricecooker_json_tree)

    def add_content_nodes(self, channel):
        """
        Build the hierarchy of topic nodes and content nodes.
        """
        LOGGER.info("Creating channel content nodes...")

        LOGGER.info("  Calling Kamkalima API to get authorization token.")
        access_token = get_authentication_token()


        LOGGER.info("  Calling Kamkalima API to get texts items:")
        all_texts_items = get_all_items(API_TEXTS_ENDPOINT, access_token)
        texts_by_grade_and_theme = group_items_by_grade_and_theme(all_texts_items)


        LOGGER.info("  Calling Kamkalima API to get audios items:")
        all_audios_items = get_all_items(API_AUDIOS_ENDPOINT, access_token)
        audios_by_grade_and_theme = group_items_by_grade_and_theme(all_audios_items)

        all_audio_grade_levels = set(audios_by_grade_and_theme.keys())
        all_text_grade_levels = set(texts_by_grade_and_theme.keys())


        # add all texts into Reading Comprehension topic (قراءة الفهم)
        reading_topic_node = dict(
            kind = content_kinds.TOPIC,
            source_id = "reading_comprehension",
            title = "دراسة نص",
            children = []
        )
        grade_key = {
            4 : "صف ٤-٦",
            7 : "صف ٧-٩",
            10 : "صف ١٠-١٢"
        }
        grade_arr = ["صف ٤-٦", "صف ٧-٩", "صف ١٠-١٢"]

        LOGGER.info("Organizing text items by theme:")
        # ordering by grade
        for grade in grade_arr:
            for grade_level in all_text_grade_levels:
                if grade_level == grade:
                    all_text_grade_level_themes = set(texts_by_grade_and_theme[grade_level].keys())
                    grade_source_id = "reading_comprehension_" + grade_level
                    grade_topic_node = dict(
                        kind = content_kinds.TOPIC,
                        source_id = grade_source_id,
                        title = grade_level,
                        children = []
                    )

                    for theme in all_text_grade_level_themes:
                        theme_topic_node = dict(
                            kind=content_kinds.TOPIC,
                            source_id= grade_source_id + "_" + theme,
                            title=theme,
                            children=[]
                        )
                        text_items = texts_by_grade_and_theme[grade_level][theme]
                        for text_item in text_items:
                            child_topic = topic_node_from_item("text", text_item)
                            theme_topic_node["children"].append(child_topic)
                        grade_topic_node["children"].append(theme_topic_node)
                    
                    reading_topic_node["children"].append(grade_topic_node)

        channel["children"].append(reading_topic_node)


        # add all audio into Listening Comprehension topic
        listening_topic_node = dict(
            kind = content_kinds.TOPIC,
            source_id = "listening_comprehension",
            title = "إصغاء",
            children = []
        )

        LOGGER.info("Organizing audio items by theme:")
        for grade in grade_arr: 
            for grade_level in all_audio_grade_levels:
                if grade_level == grade:
                    all_audio_grade_level_themes = set(audios_by_grade_and_theme[grade_level].keys())
                    grade_source_id = "listening_comprehension_" + grade_level
                    grade_topic_node = dict(
                        kind = content_kinds.TOPIC,
                        source_id = grade_source_id,
                        title = grade_level,
                        children = []
                    )
                    
                    for theme in all_audio_grade_level_themes:
                        theme_topic_node = dict(
                            kind=content_kinds.TOPIC,
                            source_id= grade_source_id + "_" + theme,
                            title=theme,
                            children=[]
                        )
                        audio_items = audios_by_grade_and_theme[grade_level][theme]
                        for audio_item in audio_items:
                            child_topic = topic_node_from_item("audio", audio_item)
                            theme_topic_node["children"].append(child_topic)
                        grade_topic_node["children"].append(theme_topic_node)

                    listening_topic_node["children"].append(grade_topic_node)
                    
        channel['children'].append(listening_topic_node)



# CLI
################################################################################

if __name__ == "__main__":
    """
    This code will run when the sushi chef scripy is called on the command line.
    """
    chef = KamkalimaChef()
    chef.main()
