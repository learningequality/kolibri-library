#!/usr/bin/env python

import json
import logging
import os
import re
import zipfile

from le_utils.constants import content_kinds, licenses
from ricecooker.chefs import JsonTreeChef
from ricecooker.classes.licenses import get_license
from ricecooker.classes.questions import SingleSelectQuestion
from ricecooker.config import LOGGER
from ricecooker.utils.jsontrees import write_tree_to_json_tree
from ricecooker.utils.jsontrees import (TOPIC_NODE, VIDEO_NODE, AUDIO_NODE,
                                        EXERCISE_NODE, DOCUMENT_NODE, HTML5_NODE)
from ricecooker.utils.jsontrees import (VIDEO_FILE, AUDIO_FILE, DOCUMENT_FILE,
                                        HTML5_FILE, THUMBNAIL_FILE, SUBTITLES_FILE)

from le_utils.constants import exercises



# Aflatoun settings
################################################################################
AFLATOUN_LICENSE = get_license(licenses.CC_BY, copyright_holder='Aflatoun International').as_dict()
AFLATOUN_AUTHOR = 'Aflatoun'
AFLATOUN_CONTENT_BASE_DIR = 'content/aflatoun_tree/aflatoun'
AFLATOUN_CONTENT_DIR_DEPTH = 4
LANGUAGE_FOLDER_LOOKUP = dict(
    en = 'English',
    fr = 'French',
)
CONTENT_FOLDERS_FOR_LANG = dict(
    en = ['Aflatoun Series',
          'Teacher Refresher Modules',
          'Training Manual'],
    fr = ['Les Séries Aflatoun',
          'Manuel de Formation',
          'Modules de support pour la formation continue'],
)
DIR_EXCLUDE_PATTERNS = ['Unzipped Files']
FILE_EXCLUDE_EXTENTIONS = ['.DS_Store', '.json']
FILE_SKIP_PATTENRS = []


# Chef settings
################################################################################
DATA_DIR = 'chefdata'
TREES_DATA_DIR = os.path.join(DATA_DIR, 'trees')
RICECOOKER_JSON_TREE_TPL = 'ricecooker_json_tree_{}.json'


# LOGGING SETTINGS
################################################################################
logging.getLogger("cachecontrol.controller").setLevel(logging.WARNING)
logging.getLogger("requests.packages").setLevel(logging.WARNING)
LOGGER.setLevel(logging.DEBUG)



# HELPER FUNCTIONS
################################################################################

def get_metadata_file_path(path):
    if path.endswith('exercise.zip'):
        return path.replace('exercise.zip', 'exercise.json')
    else:
        return path + '.json'

def get_metadata(path):
    """
    Find the json metadata file associated with content at `path` (dir or file).
    """
    metadata_filename = get_metadata_file_path(path)
    if not os.path.exists(metadata_filename):
        return {}
    with open(metadata_filename, 'r') as json_file:
        return json.load(json_file)

def get_path_as_list(path):
    """
    Convert raw_path form os.walk tuple format to a list of subdirectories.
    Returns a list of dirs after the first AFLATOUN_CONTENT_DIR_DEPTH dirs, e.g.,
    >>> get_path_as_list('content/aflatoun_tree/aflatoun/French/Topic1/Subtopic2/SubSubtopic3')
    ['Topic1', 'Subtopic2', 'SubSubtopic3']
    """
    full_path = path.split(os.path.sep)
    path_without_channel = full_path[AFLATOUN_CONTENT_DIR_DEPTH:]
    return path_without_channel

def get_node_for_path(channel, path_as_list):
    """
    Returns the TopicNode dict at the given path inside channel.
    """
    current = channel
    for subtopic in path_as_list:
        current = list(filter(lambda d: d['dirname'] == subtopic, current['children']))[0]
    return current

def source_id_from_path(path):
    return path.replace('content/aflatoun_tree/aflatoun/', 'aflotoun:', 1)




# BUILD JSON TREE
################################################################################

def filter_filenames(filenames):
    filenames_cleaned = []
    for filename in filenames:
        keep = True
        for pattern in FILE_EXCLUDE_EXTENTIONS:
            if filename.endswith(pattern):
                keep = False
        for pattern in FILE_SKIP_PATTENRS:   # This will reject exercises...
            if pattern in filename:
                keep = False
        if keep:
            filenames_cleaned.append(filename)
    return filenames_cleaned

def keep_folder(raw_path):
    keep = True
    for pattern in DIR_EXCLUDE_PATTERNS:
        if pattern in raw_path:
            LOGGER.debug('rejecting', raw_path)
            keep = False
    return keep


def process_folder(channel, raw_path, filenames, lang):
    """
    Create `ContentNode`s from each file in this folder and the node to `channel`
    under the path `raw_path`.
    """
    if not keep_folder(raw_path):
        return
    #
    path_as_list = get_path_as_list(raw_path)
    # A. TOPIC
    dirname = path_as_list.pop()
    parent_node = get_node_for_path(channel, path_as_list)

    # read topic metadata to get title and description
    folder_metadata = get_metadata(raw_path)

    # create topic
    topic = dict(
        kind=TOPIC_NODE,
        dirname=dirname,
        source_id=source_id_from_path(raw_path),
        title=folder_metadata.get('title', dirname),
        description=folder_metadata.get('Description', None),
        language=lang,
        children=[],
    )
    # topic.update(folder_metadata)
    parent_node['children'].append(topic)

    # filter filenames
    filenames_cleaned = filter_filenames(filenames)

    # B. PROCESS FILES
    for filename in filenames_cleaned:
        file_metadata = get_metadata(os.path.join(raw_path, filename))
        node = make_content_node(raw_path, filename, file_metadata, lang)
        if node:
            # attach content node to containing topic
            topic['children'].append(node)
        else:
            print('Skipping None node', filename)


def build_ricecooker_json_tree(args, options, json_tree_path):
    """
    Download all categories, subpages, modules, and resources from open.edu.
    """
    LOGGER.info('Starting to build the ricecooker_json_tree')
    if 'lang' not in options:
        raise ValueError('Must specify lang=?? on the command line. Supported languages are `en` and `fr`')
    lang = options['lang']
    lang_dir = LANGUAGE_FOLDER_LOOKUP[lang]

    # Ricecooker tree
    ricecooker_json_tree = dict(
        source_domain = 'aflatoun.org',
        source_id = 'aflatoun-{}'.format(lang),
        title = 'Aflatoun Academy ({})'.format(lang),
        thumbnail = './content/images/aflatoun_logo.jpg',
        description = 'Aflatoun International offers social and financial'
                      ' education to millions of children and young people'
                      ' worldwide, empowering them to make a positive change'
                      ' for a more equitable world.',
        language = lang,
        children=[],
    )
    channel_base_dir = os.path.join(AFLATOUN_CONTENT_BASE_DIR, lang_dir)
    content_folders = sorted(os.walk(channel_base_dir))

    # MAIN PROCESSING OF os.walk OUTPUT
    ############################################################################
    _ = content_folders.pop(0)  # Skip over channel folder because handled above
    for raw_path, _subfolders, filenames in content_folders:
        LOGGER.info('processing folder ' + str(raw_path))
        sorted_filenames = sorted(filenames)
        process_folder(ricecooker_json_tree, raw_path, sorted_filenames, lang)

    # Write out ricecooker_json_tree_{en/fr}.json
    write_tree_to_json_tree(json_tree_path, ricecooker_json_tree)


def make_content_node(raw_path, filename, metadata, lang):
    """
    Create ContentNode based on the file extention and metadata provided.
    """
    file_key, file_ext = os.path.splitext(filename)
    ext = file_ext[1:]

    kind = None
    if  filename.endswith('exercise.zip'):
        kind = 'exercise_zip'
    elif ext in content_kinds.MAPPING:
        kind = content_kinds.MAPPING[ext]
    else:
        raise ValueError('Could not find kind for extension ' + str(ext) + ' in content_kinds.MAPPING')

    filepath = os.path.abspath(os.path.join(raw_path, filename))
    source_id = source_id_from_path(os.path.join(raw_path, filename))
    title = metadata.get('title', filename)
    description = metadata.get('Description', None)
    # tags = keywords_to_tags(metadata['keywords'])   # TODO
    # related_content = TODO

    if kind == VIDEO_NODE:
        content_node = dict(
            kind=VIDEO_NODE,
            source_id=source_id,
            title=title,
            author=AFLATOUN_AUTHOR,
            description=description,
            language=lang,
            license=AFLATOUN_LICENSE,
            derive_thumbnail=True,  # video-specific option
            files=[{'file_type':VIDEO_FILE, 'path':filepath, 'language':lang}], # ffmpeg_settings={"crf": 24},
        )

    elif kind == AUDIO_NODE:
        content_node = dict(
            kind=AUDIO_NODE,
            source_id=source_id,
            title=title,
            author=AFLATOUN_AUTHOR,
            description=description,
            language=lang,
            license=AFLATOUN_LICENSE,
            files=[{'file_type':AUDIO_FILE, 'path':filepath, 'language':lang}],
        )

    elif kind == DOCUMENT_NODE:
        content_node = dict(
            kind=DOCUMENT_NODE,
            source_id=source_id,
            title=title,
            author=AFLATOUN_AUTHOR,
            description=description,
            language=lang,
            license=AFLATOUN_LICENSE,
            files=[{'file_type':DOCUMENT_FILE, 'path':filepath, 'language':lang}],
        )

    elif kind == 'exercise_zip':
        exercice_dict = exercise_zip_to_dict(filepath)
        # skip exercise with no questions
        if len(exercice_dict['questions']) == 0:
            return None

        else:
            # Special logic to combine two descriptions
            desc1 = exercice_dict['description'].strip()  # from inside zip file
            if description:
                desc2 = description.strip()               # from exericsezip metadata
            else:
                desc2 = ''

            # skip desc2 if the same as desc1
            if desc1 == desc2:
                desc2 = ''

            # append period to desc2 if it exists but doesn't have a period
            if len(desc2) > 0:
                if not desc2.endswith('.'):
                    desc2 = desc2 + '. '
                else:
                    desc2 = desc2 + ' '

            # combine the two
            desc = desc2 + desc1

            content_node = dict(
                kind=EXERCISE_NODE,
                source_id=source_id,
                title=title,
                author=AFLATOUN_AUTHOR,
                description=desc,
                language=lang,
                license=AFLATOUN_LICENSE,
                # exercise_data ({mastery_model:str, randomize:bool, m:int, n:int}): data on mastery requirements (optional)
                # thumbnail (str): local path or url to thumbnail image (optional)
                # extra_fields (dict): any additional data needed for node (optional)
                # domain_ns (str): who is providing the content (e.g. learningequality.org) (optional)
                # questions ([<Question>]): list of question objects for node (optional)
                questions=exercice_dict['questions'],
            )

    else:
        raise ValueError('Not implemented case for kind ' + str(kind))

    return content_node






def exercise_zip_to_dict(ex_path):
    archive = zipfile.ZipFile(ex_path, 'r')
    #
    json_bytes = archive.read('exercise.json')
    exercise_json = json.loads(json_bytes)
    json_bytes2 = archive.read('assessment_items.json')
    asssesment_items = json.loads(json_bytes2)

    # combine to form (numeric_id, quesion_dict) list
    questions = zip(exercise_json['all_assessment_items'], asssesment_items)

    exercise_dict = dict(
        title=exercise_json['title'],
        description=exercise_json['description'],
        questions=[],
    )

    for qid, question in questions:
        # consistcy check
        assert question['itemDataVersion']['major'] == 0, 'Wrong major verison'
        assert question['itemDataVersion']['minor'] == 1, 'Wrong minor verison'
        # question text
        raw_content = question['question']['content']
        raw_content = re.sub('\[\[.*?\]\]', '', raw_content)
        question_text = raw_content.strip()

        if '60b6c0cd92ca746a6f71e5f7c9d34b1c384021ab' in question_text:
            continue  # skip question with missing image reference web+local://.

        # hints
        hints = question['hints']
        if hints:
            print('>>>>', hints)

        # images???
        images = question['question']['images']
        if images:
            print('&&&&', images)

        # answer widget (ASSUMPTION: every question has a single answer widget)
        widgets = question['question']['widgets']
        assert len(widgets.keys())==1, 'multiple widgets question found'
        widget = list(widgets.values())[0]

        # A: select-type question
        if widget['type'] == 'radio':
            multipleSelect = widget['options']['multipleSelect']

            # A.1: MultipleSelectQuestion
            if multipleSelect:
                correct_answers = []
                all_answers = []
                for _wid, wdata in widgets.items():
                    choices = wdata['options']['choices']
                    for choice in choices:
                        choice_text = choice['content'].strip()
                        if choice['correct']:
                            correct_answers.append(choice_text)
                        all_answers.append(choice_text)
                if len(correct_answers) == 0:
                    print('Skipping question because no correct_answers provided', ex_path)
                    continue
                q = dict(
                    question_type=exercises.MULTIPLE_SELECTION,
                    id=str(qid),
                    question=question_text,
                    correct_answers=correct_answers,
                    all_answers=all_answers,
                    hints=hints,
                )
                exercise_dict['questions'].append(q)

            # A.2: SingleSelectQuestion
            else:
                correct_answer = None
                all_answers = []
                for _wid, wdata in widgets.items():
                    choices = wdata['options']['choices']
                    for choice in choices:
                        choice_text = choice['content'].strip()
                        if choice['correct']:
                            correct_answer = choice_text
                        all_answers.append(choice_text)
                if correct_answer is None:
                    print('Skipping question because correct_answer is None', ex_path)
                    continue
                assert correct_answer, 'no choice for correct_answer selected'
                q = dict(
                    question_type=exercises.SINGLE_SELECTION,
                    id=str(qid),
                    question=question_text,
                    correct_answer=correct_answer,
                    all_answers=all_answers,
                    hints=hints,
                )
                exercise_dict['questions'].append(q)

        else:
            print('Skipping unknown question type', widget['type'], ex_path)
            continue


    return exercise_dict




# CHEF
################################################################################

class AflatounChef(JsonTreeChef):
    """
    This sushi chef uses os.walk to import the content in `afaltoun_tree` folder:
      - (directory structure + json metadata files) --> `TopicNode`s
      - (files + json metadata files) --> `ContentNode`s and `File`s
    """

    def pre_run(self, args, options):
        """
        This function is called before `run` in order to build the json tree.
        """
        kwargs = {}   # combined dictionary of argparse args and extra options
        kwargs.update(args)
        kwargs.update(options)
        json_tree_path = self.get_json_tree_path(**kwargs)
        build_ricecooker_json_tree(args, options, json_tree_path)

    def get_json_tree_path(self, **kwargs):
        """
        Return path to ricecooker json tree file for language in kwargs['lang'].
        """
        if 'lang' not in kwargs:
            raise ValueError('Must specify lang=?? on the command line. Supported languages are `en` and `fr`')
        lang = kwargs['lang']
        json_tree_path = os.path.join(TREES_DATA_DIR, RICECOOKER_JSON_TREE_TPL.format(lang))
        return json_tree_path


# CLI
################################################################################

if __name__ == '__main__':
    chef = AflatounChef()
    chef.main()
