#!/usr/bin/env python
import os
import sys
sys.path.append(os.getcwd()) # Handle relative imports
#from utils import data_writer, path_builder # , downloader -- we no longer use downloader due to session issues
from le_utils.constants import licenses, exercises, content_kinds, file_formats, format_presets, languages
import requests
from ricecooker.classes import nodes
from ricecooker.classes.files import HTMLZipFile
from ricecooker.chefs import SushiChef


""" Additional imports """
###########################################################
import logging
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import re
import localise
#import ricecooker

""" Run Constants"""
###########################################################

CHANNEL_NAME = "Illustrative Mathematics"		# Name of channel
CHANNEL_SOURCE_ID = "openupresources"			# Channel's unique id
# TODO: what is CHANNEL_DOMAIN?
CHANNEL_DOMAIN = "content@learningequality.org"		# Who is providing the content
CHANNEL_LANGUAGE = "en"					# Language of channel
CHANNEL_DESCRIPTION = "Grade 6-8 Math: A problem-based core program that sparks unparalleled levels of student engagement."  # Description of the channel (optional)
CHANNEL_THUMBNAIL = None                                    # Local path or url to image file (optional)
#PATH = path_builder.PathBuilder(channel_name=CHANNEL_NAME)  # Keeps track of path to write to csv
WRITE_TO_PATH = "{}{}{}.zip".format(os.path.dirname(os.path.realpath(__file__)), os.path.sep, CHANNEL_NAME) # Where to generate zip file
USERNAME = os.getenv('USERNAME')
PASSWORD = os.getenv('PASSWORD')

# make sure we're using the same session as localise is! (geogebra can use a different one, that's fine)
session = localise.session                            # I wanted to use downloader.DOWNLOAD_SESSION, but that doesn't work...

""" Additional Constants """
###########################################################

# only add keys we actively care about
"""METADATA_KEYS = ['content_id', 'author', 'lang_id', 'license', 'copyright_holder']
LICENSE_LOOKUP = {"CC BY-NC-SA": licenses.CC_BY_NC_SA,
                  "CC BY-NC": licenses.CC_BY_NC,
                  "CC BY": licenses.CC_BY,
                  "Public Domain": licenses.PUBLIC_DOMAIN
                  }
""" # TODO - remove if unused
# Set up logging tools
LOGGER = logging.getLogger()
#__logging_handler = logging.StreamHandler()
#LOGGER.addHandler(__logging_handler)
#LOGGER.setLevel(logging.INFO)

# License to be used for content under channel
CHANNEL_LICENSE = licenses.CC_BY_NC_SA
GRADES = [6]#,7,8]
UNITS = [1,2,3,4,5,6,7,8,9]
BASE_URL = 'https://im.openupresources.org/{grade}/{target}'

def login():
    # Handle Login
    sign_in_url = "https://auth.openupresources.org/users/sign_in"

    # get sign-in page
    bs = BeautifulSoup(session.get(sign_in_url).text, 'html.parser')
    form = bs.find("form")
    inputs = form.find_all("input")

    data = {}
    # what we actually care about here is the auth-token.
    for i in inputs:
        data[i.attrs['name']] = i.attrs.get('value')
        data['user[email]'] = USERNAME
    data['user[password]'] = PASSWORD

    posted_response = session.post(sign_in_url, data=data)
    assert "Signed in successfully" in posted_response.text

    # this step is apparently absolutely critical -- click the big button on the success page!
    session.get("https://auth.openupresources.org/register/materials")

    # check it's all OK.
    test_response = session.get("https://im.openupresources.org/7/teachers/5.html")

    assert "sign up as an educator" not in test_response.text
    assert "Rational Number" in test_response.text
    localise.test_login()
    
""" Main Class """

class OpenUpChef(SushiChef):
    channel_info = {
        'CHANNEL_SOURCE_DOMAIN': 'im.openupresources.org', # who is providing the content (e.g. learningequality.org)
        'CHANNEL_SOURCE_ID': 'im_openupresources',         # channel's unique id
        'CHANNEL_TITLE': 'Illustrative Mathematics',
        'CHANNEL_LANGUAGE': 'en',                          # Use language codes from le_utils
        # 'CHANNEL_THUMBNAIL': 'https://im.openupresources.org/assets/im-logo.svg', # (optional) local path or url to image file
        'CHANNEL_DESCRIPTION': 'Grade 6-8 Math: A problem-based core program that sparks unparalleled levels of student engagement.',  # (optional) description of the channel (optional)
    }

    def construct_channel(self, **kwargs):
        # create channel
        channel = self.get_channel(**kwargs)
        # create a topic and add it to channel
        for grade in GRADES:
            grade_node = nodes.TopicNode(source_id=str(grade),
                                          title="Grade {grade}".format(grade=grade),
                                          description="",
                                         )
            channel.add_child(grade_node)
            
            filename = localise.make_local(BASE_URL.format(grade=grade, target='teachers')+"/teacher_course_guide.html")
            print (filename)
            file = HTMLZipFile(filename)

            course_guide_node = nodes.HTML5AppNode(source_id = "{grade}-teachers-teacher_course_guide".format(grade=grade),
                                                   title="Grade {grade} Teacher Course Guide".format(grade=grade),
                                                   license=licenses.CC_BY_NC_SA,
                                                   copyright_holder="Open Up Resources",
                                                   #author="Open Up Resources",
                                                   #description="",
                                                   #thumbnail="",
                                                   #extra_fields={},
                                                   #domain_ns="",
                                                   files=[file],
                                                   )
            grade_node.add_child(course_guide_node)
            
            filename = localise.make_local(BASE_URL.format(grade=grade, target="students")+"/1/1.html")
            print (filename)
            file = HTMLZipFile(filename)
        
            course_guide_node = nodes.HTML5AppNode(source_id = "{grade}-students-1-1".format(grade=grade),
                                                           title="Grade {grade} 1-1".format(grade=grade),
                                                           license=licenses.CC_BY_NC_SA,
                                                           copyright_holder="Open Up Resources",
                                                           #author="Open Up Resources",
                                                           #description="",
                                                           #thumbnail="",
                                                           #extra_fields={},
                                                           #domain_ns="",
                                                           files=[file],
                                                           )
            grade_node.add_child(course_guide_node)
            



            """6/teachers/1.html -- has description of this topic; has drop down list of lessons within it
            6/teachers/1/1.html -- Is a lesson plan.
            6/teachers/1/assessments/unit_assessments.html -- broken
            6/teachers/1/practice_problems.html -- practice problems for all lessons w/solutons
            6/teachers/1/downloads.html -- 7x links to pdfs/zips of pdfs
            6/teachers/1/family_materials.html -- same as family? (YES) topicwide
            6/teachers/teacher_course_guide.html -- single page per year

            6/families/1.html -- same as teachers / family materials

            6/students/1/1.html -- is student resources.
            6/students/1/practice_problems.html - nothing complex
            6/students/1/glossary.html - nothing complex
            6/students/1/my_reflections.html - nothing complex    """


        return channel

    #def run(): # args, options
    #    pass

    #def main():
    #    pass

def make_channel():
    mychef = OpenUpChef()
    args = {'token': os.environ['KOLIBRI_STUDIO_TOKEN'], 'reset': True, 'verbose': True}
    options = {}
    mychef.run(args, options)

login()
make_channel()
exit()
