import requests
import credentials
import requests_cache

requests_cache.install_cache()
session = requests.session()
response = session.post("https://www.aldarayn.com/login/index.php", data=credentials.login)
assert response.url == "https://www.aldarayn.com/my/", response.url
