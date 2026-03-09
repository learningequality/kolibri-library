import requests
import time
from selenium import webdriver
from requests_file import FileAdapter
from utils.downloader import read

class Client():

    def __init__(self, email, password):
        self.session = requests.Session()                          # Session for downloading content from urls
        self.session.mount('https://', requests.adapters.HTTPAdapter(max_retries=3))
        self.session.mount('file://', FileAdapter())
        self.driver = None
        self.email = email
        self.password = password

    def read(self, path, loadjs=False):
        return read(path, loadjs=loadjs, session=self.session, driver=self.driver)

    def login(self, login_url, post_url=None):
        post_url = post_url or login_url
        response = self.session.get(login_url)
        token = response.cookies['csrftoken']
        login_data = {
            'email': self.email,
            'password': self.password,
            'remember': False,
            'csrfmiddlewaretoken': token
        }

        return self.session.post(login_url, data=login_data, headers=dict(Referer=login_url))

    def post(self, url, post_data, referer=None, include_token=True):
        referer = referer or url
        response = self.session.get(referer)
        headers = {'Referer': referer}
        if response.cookies.get('csrftoken'):
            token = response.cookies['csrftoken']
            headers.update({'X-CSRFToken': token})
            if include_token:
                post_data.update({'csrfmiddlewaretoken': token})

        return self.session.post(url, data=post_data, headers=headers)

    def get(self, url, headers=None):
        return self.session.get(url, headers=headers or {})