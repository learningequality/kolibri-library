import csv
from functools import cmp_to_key  # we'll use old-school cmp method style of comparison
# see https://docs.python.org/3/howto/sorting.html#the-old-way-using-the-cmp-parameter
import hashlib
from itertools import groupby
import json
import logging
from operator import itemgetter
import os
import re
import requests

from ricecooker.config import LOGGER
from arabic import K12_TEXT




# STRUCTURE = CSV EXPORT of the Google Sheet titled "Aldarayn structure spec"
# https://docs.google.com/spreadsheets/d/1QKXvXxLS1dByxrcYHTT2Y2e-eglvDMhkXvSVvFppq20/edit#gid=0
################################################################################
GSHEETS_BASE = 'https://docs.google.com/spreadsheets/d/'
ALDARAYN_SHEET_ID = '1QKXvXxLS1dByxrcYHTT2Y2e-eglvDMhkXvSVvFppq20'
ALDARAYN_STRUCTURE_SHEET_GID = '0'
ALDARAYN_SHEET_CSV_URL = GSHEETS_BASE + ALDARAYN_SHEET_ID + '/export?format=csv&gid=' + ALDARAYN_STRUCTURE_SHEET_GID
ALDARAYN_SHEET_CSV_PATH = 'chefdata/aldarayn_structure.csv'

SKIP_KEY = "Skip?"
L1_KEY = 'Level 1 Topic *'
L2_KEY = 'Level 2 Topic *'
L3_KEY = 'Level 3 Topic'
L4_KEY = 'Level 4 Topic'
TITLE_KEY = 'Title *'
SEPARATOR_KEY = '-'
WEBSITE_CAT1_KEY = 'Website Category Level 1 *'
WEBSITE_CAT2_KEY = 'Website Category Level 2'
WEBSITE_TITLE_KEY = 'Website Course Title *'
WEBSITE_URL_KEY = 'Course URL *'
WEBSITE_CATID_KEY = 'Category ID *'
CATEGORY_TRANS_KEY = 'Combined Category Trans'
COURSE_TRANS_KEY = 'Course Trans'

ALDARAYN_SHEET_CSV_FIELDNAMES = [
    SKIP_KEY,  # A
    L1_KEY,    # B
    L2_KEY,    # C
    L3_KEY,    # D
    L4_KEY,    # E
    TITLE_KEY, # F
    SEPARATOR_KEY,     # G
    WEBSITE_CAT1_KEY,  # H
    WEBSITE_CAT2_KEY,  # I
    WEBSITE_TITLE_KEY, # J
    WEBSITE_URL_KEY,   # K
    WEBSITE_CATID_KEY, # L
    CATEGORY_TRANS_KEY,# M
    COURSE_TRANS_KEY   # N
]

PYTHON_FIELDNAMES = """
SKIP
L1
L2
L3
L4
TITLE
SEPARATOR
WEBSITE_CAT1
WEBSITE_CAT2
WEBSITE_TITLE
WEBSITE_URL
WEBSITE_CATID
CATEGORY_TRANS
COURSE_TRANS
""".strip().split("\n")

def download_structure_csv():
    response = requests.get(ALDARAYN_SHEET_CSV_URL)
    csv_data = response.content.decode('utf-8')
    with open(ALDARAYN_SHEET_CSV_PATH, 'w') as csvfile:
        csvfile.write(csv_data)
        LOGGER.info('Succesfully saved ' + ALDARAYN_SHEET_CSV_PATH)
    return ALDARAYN_SHEET_CSV_PATH


def _clean_dict(row):
    """
    Transform empty strings values of dict `row` to None.
    """
    row_cleaned = {}
    for key, val in row.items():
        if val is None or val == '':
            row_cleaned[key] = None
        else:
            row_cleaned[key] = val.strip()
    return row_cleaned

def load_aldarayn_structure():
    csv_path = download_structure_csv()
    struct_list = []
    with open(csv_path, 'r') as csvfile:
        reader = csv.DictReader(csvfile, fieldnames=ALDARAYN_SHEET_CSV_FIELDNAMES)
        next(reader)  # Skip Headers row
        for row in reader:
            clean_row = _clean_dict(row)
            if clean_row[SKIP_KEY] == "SKIP":
                continue

            if clean_row[L1_KEY] is not None and clean_row[L2_KEY] is not None:                # @Dave: you can add other sanity checks here
                struct_list.append(clean_row)
            else:
                LOGGER.warning('Unrecognized structure row {}'.format(str(clean_row)))
                assert False, [L1_KEY, L2_KEY]
    return struct_list

def verify_http():
    for x in COURSE_STRUCT:
        assert "http" in x[WEBSITE_URL_KEY] or x[L1_KEY] == K12_TEXT, x[WEBSITE_URL_KEY]

def adult_structure():
    return [x for x in COURSE_STRUCT if x[L1_KEY] != K12_TEXT]

def k12_structure():
    # split into K12 and adult sections
    k12 = [x for x in COURSE_STRUCT if x[L1_KEY] == K12_TEXT]

    # mangle k12 to not have L1_KEY
    for x in k12:
        x[L1_KEY] = x[L2_KEY]
        x[L2_KEY] = x[L3_KEY]
        x[L3_KEY] = x[L4_KEY]
        x[L4_KEY] = None

    return k12

COURSE_STRUCT = load_aldarayn_structure()
verify_http()
#adult_structure()
#k12_structure()

# STRUCTURE LIST TO STRUCTURE TREE
################################################################################

def aldarayn_sort(itemA, itemB):
    """
    Returns sort order according to `keys`
    """
    keys = [L1_KEY, L2_KEY, L3_KEY, L4_KEY, TITLE_KEY]
    for key in keys:

        # if both keys exist
        if itemA[key] and itemB[key]:
            if itemA[key] == itemB[key]: # if keys are the same, check next key
                continue
            elif itemA[key] < itemB[key]:
                return -1
            elif itemA[key] > itemB[key]:
                return 1

        # subfolders first
        if itemA[key] and not itemB[key]:
            return -1
        if not itemA[key] and itemB[key]:
            return 1

        # return 0 if both same
        if not itemA[key] and not itemB[key]:
            return 0


def sane_group_by(items, key):
    """
    Wrapper for itertools.groupby to make it easier to use.
    Returns a dict with keys = possible values of key in items
    and corresponding values being lists of items that have that key.
    """
    sorted_items = sorted(items, key=itemgetter(key))
    return dict((k, list(g)) for k, g in groupby(sorted_items, key=itemgetter(key)))


def print_aldarayn_structure(struct_list):
    # Important to have list fully sorted before doing groupbys
    struct_list = sorted(struct_list, key=cmp_to_key(aldarayn_sort))

    edu_level_dict = sane_group_by(struct_list, L1_KEY)                         # L1
    for edu_level, items_in_edu_level in edu_level_dict.items():

        print('Education level', edu_level)
        subjects_dict = sane_group_by(items_in_edu_level, L2_KEY)               # L2
        for subject, items_in_subject in subjects_dict.items():
            L3_topics_dict = sane_group_by(items_in_subject, L3_KEY)            # L3
            no_L3_items = L3_topics_dict.get(None, [])
            if no_L3_items:
                del L3_topics_dict[None]
            print('   - subject =', repr(subject), 'a', \
                        len(no_L3_items), 'courses', \
                        len(L3_topics_dict.keys()), 'subfolders')

            for L3_topic, items_in_L3_topic in L3_topics_dict.items():

                L4_topics_dict = sane_group_by(items_in_L3_topic, L4_KEY)       # L4
                no_L4_items = L4_topics_dict.get(None, [])
                if no_L4_items:
                    del L4_topics_dict[None]
                print('       - L3_topic =', repr(L3_topic),
                                # '=', items_in_L3_topic[0][CATEGORY_TRANS_KEY],
                                len(no_L4_items), 'courses',
                                len(L4_topics_dict.keys()), 'subfolders')

                for L4_topic, items_in_L4_topic in L4_topics_dict.items():
                        print('            - L4_topic =', repr(L4_topic), '-',
                                              # '=', items_in_L4_topic[0][CATEGORY_TRANS_KEY],
                                              len(items_in_L4_topic), 'items')


# TODO: group courses that have same TITLE_KEY into one
