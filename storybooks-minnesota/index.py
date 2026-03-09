import requests
import requests_cache
import lxml.html
from urllib.parse import urljoin

requests_cache.install_cache()

base_url = "https://global-asp.github.io/storybooks-minnesota/stories/{}/level{}"

languages = {
    "en": "English",
    "am": "Amharic",
    "ar": "Arabic",
    "fr": "French",
    "de": "German",
    "zh": "Mandarin",
    "nb": "Norwegian",
    "om": "Oromo",
    "so": "Somali",
    "es": "Spanish",
}

def get_lang_level(lang, level):
    html = requests.get(base_url.format(lang, level)).content
    root = lxml.html.fromstring(html)
    urls = set(root.xpath("//a[@class='btn-link']/@href"))
    return (urljoin(base_url, x) for x in urls)


