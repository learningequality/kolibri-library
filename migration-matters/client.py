from robobrowser import RoboBrowser

class Client():
    def __init__(self, email, password):
        self.browser = RoboBrowser(history=True, parser='html.parser')
        self.email = email
        self.password = password

    def login(self, login_url):
        self.browser.open(login_url)
        form = self.browser.get_form(id='new_user')
        form['user[email]'].value = self.email
        form['user[password]'].value = self.password
        self.browser.submit_form(form)

    def get(self, url, headers=None):
        return self.browser.session.get(url, headers=headers or {})
