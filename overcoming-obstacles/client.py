import requests
import time
from selenium import webdriver
from requests_file import FileAdapter
from ricecooker.utils.downloader import read

from robobrowser import RoboBrowser


class Client():

    def __init__(self, email, password):
        self.browser = RoboBrowser()
        self.email = email
        self.password = password

    def read(self, path, loadjs=False):
        return read(path, loadjs=loadjs, session=self.browser.session)

    def login(self, login_url):
        self.browser.open(login_url)
        form = self.browser.get_form(id='form-login')
        form['email'].value = self.email
        form['password'].value = self.password
        self.browser.submit_form(form)

    def post(self, url, post_data, referer=None, include_token=True):
        referer = referer or url
        response = self.browser.session.get(referer)
        headers = {'Referer': referer}
        if response.cookies.get('csrftoken'):
            token = response.cookies['csrftoken']
            headers.update({'X-CSRFToken': token})
            if include_token:
                post_data.update({'csrfmiddlewaretoken': token})

        return self.browser.session.post(url, data=post_data, headers=headers)

    def get(self, url, headers=None):
        return self.browser.session.get(url, headers=headers or {})