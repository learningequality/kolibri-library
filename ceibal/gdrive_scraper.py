#!/usr/bin/env python
# -*- coding: UTF-8 -*-
import re
from le_utils.constants import content_kinds
from pages import BasicPageScraper
import shutil
import tempfile
import io
import pickle
import os.path
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.http import MediaIoBaseDownload
from utils import BasicScraper, BrokenSourceException, UnscrapableSourceException

"""
    ORIGINAL CODE CAN BE FOUND HERE:
    https://github.com/learningequality/sushi-chef-better-world-ed
"""

# If modifying these scopes, delete the file token.pickle.
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']

class MemoryCache():
    # workaround for error "file_cache is unavailable when using oauth2client >= 4.0.0 or google-auth'"
    # via https://github.com/googleapis/google-api-python-client/issues/325#issuecomment-274349841
    _CACHE = {}

    def get(self, url):
        return MemoryCache._CACHE.get(url)

    def set(self, url, content):
        MemoryCache._CACHE[url] = content



class GoogleDriveScraper(BasicPageScraper):
#     """ Logic copied from https://github.com/learningequality/sushi-chef-better-world-ed/blob/master/extract.py """
    directory = 'gdrive'
    replace = True
    kind = content_kinds.DOCUMENT
    default_ext = '.pdf'

    @classmethod
    def test(self, url):
        return re.match(r'https://[^\.]+.google.com/.*(?:file|document)/d/([^/]+)/(?:preview|edit)', url)

    def __init__(self, *args, **kwargs):
        super(GoogleDriveScraper, self).__init__(*args, **kwargs)
        self.file_id = re.search(r'https://[^\.]+.google.com/.*(?:file|document)/d/([^/]+)/(?:preview|edit)', self.url).group(1)

    def get_service(self):
        creds = None
        # The file token.pickle stores the user's access and refresh tokens, and is
        # created automatically when the authorization flow completes for the first
        # time.
        if os.path.exists('credentials/token.pickle'):
            with open('credentials/token.pickle', 'rb') as token:
                creds = pickle.load(token)
        # If there are no (valid) credentials available, let the user log in.
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    'credentials/client_secret.json', SCOPES)
                creds = flow.run_local_server(port=0)
            # Save the credentials for the next run
            with open('credentials/token.pickle', 'wb') as token:
                pickle.dump(creds, token)

        return build('drive', 'v3', credentials=creds)

    def get_extension(self):
        service = self.get_service()
        file_request = service.files().get(fileId=self.file_id)
        file_metadata = file_request.execute()
        return os.path.splitext(file_metadata.get('name') or '.pdf')[1]

    def _download_file(self, write_to_path):
        try:
            service = self.get_service()

            if 'docs.google.com' in self.url:
                request = service.files().export(fileId=self.file_id, mimeType='application/pdf')
            else:
                request = service.files().get_media(fileId=self.file_id)

            fh = io.FileIO(write_to_path, mode='wb')
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                status, done = downloader.next_chunk()
        except Exception as e:
            raise UnscrapableSourceException(str(e))

    def to_zip(self, filename=None):
        try:
            tempdir = tempfile.mkdtemp()
            gdrive_path = os.path.join(tempdir, filename or self.get_filename(self.url, default_ext=self.get_extension()))
            self._download_file(gdrive_path)
            return self.write_file(gdrive_path)
        finally:
            shutil.rmtree(tempdir)

    def to_tag(self, filename=None):
        filepath = self.to_zip(filename=filename)
        if filepath.endswith('pdf'):
            embed_tag = self.create_tag('embed')
            embed_tag['style'] = 'width: 100%;min-height: 500px;'
            embed_tag['src'] = filepath
            return embed_tag
        elif filepath.endswith('png') or filepath.endswith('jpg'):
            self.kind = content_kinds.SLIDESHOW
            img_tag = self.create_tag('img')
            img_tag['src'] = filepath
            return img_tag
        else:
            raise NotImplementedError('Unhandled google drive file type at {}'.format(self.link))
