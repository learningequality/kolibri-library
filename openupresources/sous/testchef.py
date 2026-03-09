#!/usr/bin/env python
import os
import sys
sys.path.append(os.getcwd()) # Handle relative imports
from ricecooker.utils import data_writer, path_builder # , downloader -- we no longer use downloader due to session issues
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
# import localise
#import ricecooker

""" Run Constants"""
###########################################################

USERNAME = os.getenv('USERNAME')
PASSWORD = os.getenv('PASSWORD')

# make sure we're using the same session as localise is! (geogebra can use a different one, that's fine)
# session = localise.session                            # I wanted to use downloader.DOWNLOAD_SESSION, but that doesn't work...

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
GRADES = [6,7,8]
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
    data['user[password'] = PASSWORD

    posted_response = session.post(sign_in_url, data=data)
    assert "Signed in successfully" in posted_response.text

    # this step is apparently absolutely critical -- click the big button on the success page!
    session.get("https://auth.openupresources.org/register/materials")

    # check it's all OK.
    test_response = session.get("https://im.openupresources.org/7/teachers/5.html")

    assert "sign up as an educator" not in test_response.text
    assert "Rational Number" in test_response.text
    # localise.test_login()
    
""" Main Class """

class OpenUpChef(SushiChef):
    channel_info = {
        'CHANNEL_SOURCE_DOMAIN': 'im.openupresources.org', # who is providing the content (e.g. learningequality.org)
        'CHANNEL_SOURCE_ID': 'CORS',         # channel's unique id
        'CHANNEL_TITLE': 'CORS Test Channel',
        'CHANNEL_LANGUAGE': 'en',                          # Use language codes from le_utils
        # 'CHANNEL_THUMBNAIL': 'https://im.openupresources.org/assets/im-logo.svg', # (optional) local path or url to image file
        'CHANNEL_DESCRIPTION': 'Test the Illustrative Math zip files that require CORS to function.',  # (optional) description of the channel (optional)
    }

    def construct_channel(self, **kwargs):
        # create channel
        channel = self.get_channel(**kwargs)
        # create a topic and add it to channel
        
        
        file = HTMLZipFile(path='chefdata/geogebratestMay29.zip')
        node = nodes.HTML5AppNode( source_id = "uniqid",
                                   title="Testing geogebra-containing HTML5App",
                                   license=licenses.CC_BY_NC_SA,
                                   copyright_holder="Open Up Resources",
                                   files=[file],
        )
        channel.add_child(node)

        return channel

def make_channel():
    mychef = OpenUpChef()
    args = {'token': os.environ['KOLIBRI_STUDIO_TOKEN'], 'reset': True, 'verbose': True}
    options = {}
    mychef.run(args, options)

# login()
make_channel()
exit()
