import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
session = requests.session()


def get_inputs(soup):
    form = soup.find("form")
    inputs = form.findAll("input")
    return form.attrs['action'], {i.attrs.get('name'): i.attrs.get('value') for i in inputs}

def login():    
    login_1 = session.get("https://www.pbslearningmedia.org/uua/login/?next=/")
    # hidden forms
    soup = BeautifulSoup(login_1.content, "html5lib")
    action, data = get_inputs(soup)
    login_2 = session.post(action, data=data)
    # actual login form
    soup_2 = BeautifulSoup(login_2.content, "html5lib")
    action_2, data_2 = get_inputs(soup_2)
    data_2['email'] = "dave.mckee+null@gmail.com"
    data_2['password'] = "ncRNq8h54QXT"
    data_2['keep_logged_in'] = "checked"
    action_2 = urljoin(login_2.url, action_2)
    login_3 = session.post(action_2, data=data_2, headers={"referer": login_2.url})
    assert login_3.url == "https://ca.pbslearningmedia.org/", login_3.url
    assert "Log Out" in login_3.text, "Log Out not found"
    # confirm zip code
    
    print ("Logged in")
    

if __name__ == "__main__":
    login()