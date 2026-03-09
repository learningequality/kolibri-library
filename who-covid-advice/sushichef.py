#!/usr/bin/env python
import json
import os
import re
import sys

from ricecooker.utils import downloader, html_writer
from ricecooker.chefs import SushiChef
from ricecooker.classes import nodes, files, questions, licenses
from ricecooker.config import LOGGER              # Use LOGGER to print messages
from ricecooker.exceptions import raise_for_invalid_channel
from le_utils.constants import exercises, content_kinds, file_formats, format_presets, languages

from bs4 import BeautifulSoup
from hashlib import md5
from io import BytesIO
from pdf2image import convert_from_bytes
from PIL import Image

from webmixer.utils import guess_scraper
from scrapers import who

# Run constants
################################################################################
CHANNEL_NAME = "WHO Covid Advice"                           # Name of Kolibri channel
CHANNEL_SOURCE_ID = "who-covid-advice"                      # Unique ID for content source
CHANNEL_DOMAIN = "who.int"                                  # Who is providing the content
CHANNEL_LANGUAGE = "en"                                     # Language of channel
CHANNEL_DESCRIPTION = None                                  # Description of the channel (optional)
CHANNEL_THUMBNAIL = "https://news.umanitoba.ca/wp-content/uploads/2020/04/WHO.jpg"             # Local path or url to image file (optional)

# Additional constants
################################################################################
BASE_URL = 'https://www.who.int/{language}/emergencies/diseases/novel-coronavirus-2019/advice-for-public/{endpoint}'
SOURCE_MAP = {
    'en': {
        'description': 'Stay aware of the latest information on the COVID-19 outbreak, ' +
                        'available on the WHO website and through your national and local ' +
                        'public health authority. Most countries around the world have '+
                        'seen cases of COVID-19 and many are experiencing outbreaks. ' +
                        'Authorities in China and some other countries have succeeded in ' +
                        'slowing their outbreaks. However, the situation is unpredictable ' +
                        'so check regularly for the latest news.',
    },
    'ar': {
        'description': "احرص على متابعة آخر المستجدات عن فاشية مرض كوفيد-19، على ال" +
                       "موقع الإلكتروني لمنظمة الصحة العالمية ومن خلال سلطات الصحة ال" +
                       "عامة المحلية والوطنية. وفي حين لا تزال عدوى كوفيد-19 متفشية ف" +
                       "ي الصين بشكل أساسي، فهناك بعض بؤر التفشي في بلدان أخرى.  و" +
                       "معظم الأفرادلذين يصابون بالعدوى يشعرون بأعراض خفيفة ويتعافون، و" +
                       "لكن الأعراض قد تظهر بشكل أكثر حدة لدى غيرهم. احرص على العناية ب"  +
                       "صحتك وحماية الآخرين بواسطة التدابير التالية:",
    },
    'es': {
        'description': "Manténgase al día de la información más reciente sobre el brote de COVID-19," +
                       " a la que puede acceder en el sitio web de la OMS y a través de las autoridades" +
                       " de salud pública pertinentes a nivel nacional y local. La COVID-19 sigue afectando " +
                       "principalmente a la población de China, aunque se han producido brotes en otros " +
                       "países. La mayoría de las personas que se infectan padecen una enfermedad leve y se " +
                       "recuperan, pero en otros casos puede ser más grave.",
    },
    'fr': {
        'description': "Tenez-vous au courant des dernières informations sur la flambée de COVID-19, " +
                       "disponibles sur le site Web de l’OMS et auprès des autorités de santé publique " +
                       "nationales et locales. La COVID-19 continue de toucher surtout la population de " +
                       "la Chine, même si des flambées sévissent dans d’autres pays. La plupart des " +
                       "personnes infectées présentent des symptômes bénins et guérissent, mais d’autres " +
                       "peuvent avoir une forme plus grave.",
    },
    'zh': {
        'description': "请随时了解世卫组织网站上以及您所在国家和地方公共卫生机构提供的关于2019冠状病毒病疫情的最新信息。" +
                       "世界上大多数国家都出现了COVID-19病例，许多国家正发生疫情。中国和其他一些国家已经成功地减缓了疫情。" +
                       "但是，这种情况不可预测，因此请定期查看最新消息。",
    },
    'ru': {
        'description': "Следите за новейшей информацией о вспышке COVID-19, которую можно найти на веб-сайте ВОЗ, " +
                       "а также получить от органов общественного здравоохранения вашей страны и населенного пункта." +
                       " Наибольшее число случаев COVID-19 по-прежнему выявлено в Китае, тогда как в других странах " +
                       "отмечаются вспышки локального характера. В большинстве случаев заболевание характеризуется " +
                       "легким течением и заканчивается выздоровлением, хотя встречаются осложнения.",
    },
}
LICENSE = licenses.CC_BY_NC_SALicense(copyright_holder="World Health Organization")
BLACKLIST = ['healthy-parenting']

# The chef subclass
################################################################################
class WhoCovidAdviceChef(SushiChef):
    """
    This class converts content from the content source into the format required by Kolibri,
    then uploads the {channel_name} channel to Kolibri Studio.
    Your command line script should call the `main` method as the entry point,
    which performs the following steps:
      - Parse command line arguments and options (run `./sushichef.py -h` for details)
      - Call the `SushiChef.run` method which in turn calls `pre_run` (optional)
        and then the ricecooker function `uploadchannel` which in turn calls this
        class' `get_channel` method to get channel info, then `construct_channel`
        to build the contentnode tree.
    For more info, see https://ricecooker.readthedocs.io
    """
    DATA_DIR = os.path.abspath('chefdata')
    DOWNLOADS_DIR = os.path.join(DATA_DIR, 'downloads')

    channel_info = {
        'CHANNEL_SOURCE_DOMAIN': CHANNEL_DOMAIN,
        'CHANNEL_SOURCE_ID': CHANNEL_SOURCE_ID,
        'CHANNEL_TITLE': CHANNEL_NAME,
        'CHANNEL_LANGUAGE': CHANNEL_LANGUAGE,
        'CHANNEL_THUMBNAIL': CHANNEL_THUMBNAIL,
        'CHANNEL_DESCRIPTION': CHANNEL_DESCRIPTION,
    }
    language = 'en'  # Default to English if no language is provided
    options = None

    def __init__(self, *args, **kwargs):
        super(WhoCovidAdviceChef, self).__init__(*args, **kwargs)
        self.options = kwargs

    def get_channel(self, *args, **kwargs):
        channel = super(WhoCovidAdviceChef, self).get_channel(*args, **kwargs)
        self.language = self.options['language']
        channel.language = self.language
        channel.source_id = '{}-{}'.format(channel.source_id, self.language)
        channel.description = SOURCE_MAP[self.language]['description']
        channel.source_domain = BASE_URL.format(language=self.language, endpoint='')
        return channel

    def construct_channel(self, *args, **kwargs):
        """
        Creates ChannelNode and build topic tree
        Args:
          - args: arguments passed in on the command line
          - kwargs: extra options passed in as key="value" pairs on the command line
            For example, add the command line option   lang="fr"  and the value
            "fr" will be passed along to `construct_channel` as kwargs['lang'].
        Returns: ChannelNode
        """
        channel = self.get_channel(*args, **kwargs)  # Create ChannelNode from data in self.channel_info
        LOGGER.info('Scraping {}'.format(self.language))

        # Scrape advice page to html zips
        LOGGER.info('  Scraping advice page')
        main_url = BASE_URL.format(language=self.language, endpoint='')
        contents = BeautifulSoup(downloader.read(main_url), 'html5lib')
        title = contents.find('div', {'class': 'section-heading'}).text
        html = self.scrape_page_to_html(main_url, title)
        channel.add_child(html)

        # Get available topics
        for topic in contents.find('ul', {'class': 'accordion-content'}).findAll('a'):
            LOGGER.info('    {}'.format(topic.text.strip().encode('utf-8-sig')))
            endpoint = topic['href'].split('/')[-1]
            topic_url = BASE_URL.format(language=self.language, endpoint=endpoint)
            if endpoint == 'videos':
                video = self.scrape_video_page(topic_url, topic.text.strip())
                channel.add_child(video)
            elif endpoint not in BLACKLIST:
                html = self.scrape_page_to_html(topic_url, topic.text.strip())
                channel.add_child(html)

        return channel

    def scrape_page_to_html(self, url, title):
        """ Creates an html node based on the url """
        scraper = who.WHOPageScraper(url, locale=self.language)
        return scraper.to_contentnode(title, directory=self.DOWNLOADS_DIR, license=LICENSE)

    def scrape_video_page(self, url, title):
        """ Creates a video topic with all the videos on the page """
        IGNORED_VIDEOS = ['google', 'facebook']
        VIDEO_SCRAPERS = [who.WHOWebVideoScraper, who.WHOVideoScraper]

        video_topic = nodes.TopicNode(source_id=url, title=title)
        contents = BeautifulSoup(downloader.read(url), 'html.parser')

        # Scrape youtube embeds
        # e.g. https://www.who.int/emergencies/diseases/novel-coronavirus-2019/advice-for-public/videos
        for iframe in contents.findAll('iframe'):
            if not any([test for test in IGNORED_VIDEOS if test in iframe['src']]):
                header = iframe.find_parent('div', {'class': 'sf_colsIn'}).find('div', {'class': 'section-heading'}).text.strip()
                LOGGER.info('      - Downloading {}'.format(header.encode('utf-8')))
                scraper = guess_scraper(iframe['src'], scrapers=VIDEO_SCRAPERS) # Might be native or youtube video
                video_node = scraper.to_contentnode(header, license=LICENSE, directory="videos")
                video_topic.add_child(video_node)

        # Scrape native videos
        # e.g. https://www.who.int/zh/emergencies/diseases/novel-coronavirus-2019/advice-for-public/videos
        for video in contents.findAll('div', {'class': 'sf-multimedia-item__video'}):
            header = video.find('h3').text.strip()
            LOGGER.info('      - Downloading {}'.format(header.encode('utf-8')))
            video_matches = re.search(r"\(\s*\"(.+)\"\,\s*\"(.+)\"\)", video.find('a')['onclick'])

            # Embedded youtube videos here refer to playlists, so skip them
            if 'YoutubeVideo' == video_matches.group(1):
                continue

            scraper = who.WHOVideoScraper(video_matches.group(2))
            video_node = scraper.to_contentnode(header, license=LICENSE, directory="videos")
            video_topic.add_child(video_node)

        return video_topic


""" Utility function to check if any new languages have been added """
def get_available_languages():
    contents = BeautifulSoup(downloader.read(BASE_URL.format(language='en', endpoint='')), 'html5lib')
    languages = []
    for lang in contents.find('ul', {'class': 'sf-lang-selector'}).findAll('li'):
        languages.append(re.search(r"openLinkWithTranslation\('([^\']+)'\)", lang.find('a')['onclick']).group(1))
    return languages


# CLI
################################################################################
if __name__ == '__main__':
    for language in get_available_languages():
        if not SOURCE_MAP.get(language):
            LOGGER.warning('{} is not listed in the SOURCE_MAP'.format(language))
            continue
        chef = WhoCovidAdviceChef(language=language)
        chef.main()