#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import csv
import json
import re
import requests
import tempfile

from bs4 import BeautifulSoup

from ricecooker.chefs import SushiChef
from ricecooker.classes.files import (
    HTMLZipFile,
    VideoFile,
    DocumentFile,
    WebVideoFile,
    YouTubeVideoFile,
    YouTubeSubtitleFile,
)
from ricecooker.classes.licenses import CC_BYLicense
from ricecooker.classes.nodes import (
    ChannelNode,
    HTML5AppNode,
    TopicNode,
    VideoNode,
    DocumentNode,
)
from ricecooker.utils.caching import FileCache, CacheControlAdapter
from ricecooker.utils.html import download_file
from ricecooker.utils.zip import create_predictable_zip
from le_utils.constants import roles
from le_utils.constants.languages import getlang
from requests.packages.urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter

from deep_translator import GoogleTranslator
from metadata_tags import METADATA_BY_CAT
from ricecooker.config import MAX_CHAR_LIMITS

CHANNEL_METADATA = {}

# see https://docs.google.com/spreadsheets/d/1M5NQLtXUrGymxlvb4reqJmtUGLPCoXYvVB2P8vBVz_k/edit?gid=1471576465#gid=1471576465
# currnently, this is the only a11y label we have that maps to Phet's own a11yFeatures (it's alt text)
ALT_TEXT_KOLIBRI_ID = "Lb0tb9VC"

with open("titles_taglines_descriptions.csv") as csv_file:
    csv_reader = csv.reader(csv_file, delimiter=",")
    line_count = 0
    for row in csv_reader:
        if line_count == 0:
            line_count += 1
            continue
        else:
            CHANNEL_METADATA[row[1]] = {
                "title": row[2],
                "tagline": row[3],
                "description": row[4],
            }

MAX_CHAR_LIMITS.update({"description": {"max": 4096}})

DEFAULT_LANG = "en"
BASE_TITLE = "PhET Interactive Simulations"
BASE_SOURCE_ID = "phet-html5-simulations"

retry_strategy = Retry(total=5, backoff_factor=1)
# adapter = HTTPAdapter(max_retries=retry_strategy)

cache = FileCache(".webcache")
adapter = CacheControlAdapter(cache=cache)
sess = requests.Session()
sess.mount("http://", adapter)
sess.mount("https://", adapter)
ID_BLACKLIST_BY_LANG = {
    "en": ["html", "by-device", "new", "quantum", "general"],
    "ar": ["html", "by-device", "new", "quantum", "general", "by-level"],
}

BASE_URL = "https://phet-api.colorado.edu"
BASE_URL_DOWNLOAD = "https://phet.colorado.edu"

ARABIC_NAME_CATEGORY = {
    "Physics": "الفيزياء",
    "Biology": "الأحياء",
    "Chemistry": "الكيمياء",
    "Motion": "الحركة",
    "Sound and Waves": "الصوت والأمواج",
    "Work Energy and Power": "الشغل والطاقة",
    "Earth Science": "علوم الأرض",
    "Math": "الرياضيات",
    "Heat and Thermodynamics": "الحرارة والديناميكا الحرارية",
    "Quantum Phenomena": "فيزياء الكم",
    "Light and Radiation": "الضوء والإشعاعات",
    "Electricity Magnets and Circuits": "المغناطيس الكهربائي والدّارة الكهربائية",
    "pH Scale": "مقياس معامل الحموضة pH",
    "مقياس pH  : إبتدائي": "مقياس معامل الحموضة pH  : إبتدائي",
    "Beer's Law Lab": "مختبر قانون بير",
    "Bending Light": "انكسار الضوء",
    "Concepts": "مفاهيم",
    "Applications": "تطبيقات",
}

HAITIAN_NAME_CATEGORY = {
    "Elementary School": "Lekòl Elemantè",
    "By Level": "Pa Nivo",
    "Middle School": "Lekòl mwayen",
    "High School": "Lekòl Segondè",
    "University": "Inivèsite",
    "By Device": "Pa Aparèy",
    "Ipad Tablet": "Tablet Ipad",
    "Chromebook": "Chromebook",
    "Html": "Html",
    "Concepts": "Konsèp",
    "Applications": "Aplikasyon",
    "Light and Radiation": "Limyè ak Radyasyon ",
    "Electricity Magnets and Circuits": "Leman elektrisite ak sikwi",
    "Biology": "Biyoloji",
    "Chemistry": "Chimi",
    "Earth Science": "Syans Latè",
    "Math": "Matematik",
    "General": "Jeneral",
    "Root": "Rasin",
    "Physics": "Fizik",
    "Motion": "Mouvman",
    "Sound and Waves": "Son ak Vag",
    "Work Energy and Power": "Travay Enèji ak pouvwa",
    "Heat and Thermodynamics": "Chalè ak Thermodinamik",
    "Quantum Phenomena": "Fenomèn Kantik",
    "Quantum": "Quantum",
}

SIM_TYPO = {
    "أشكال الجزئ": "أشكال الجزيء",
    "مولارية": "المولارية",
    "محاليل حمض-قلوي ": "المحاليل حمضي-قلوي ",
    "بناء ذرة": "بناء الذرة",
    "المظائر والكتلة الذرية": "النظائر والكتلة الذرية",
    "تحت ضغط": "تحت الضغط",
    "انشاء الدّالة": "إنشاء الدّالة",
    "تكوين العشرة": "تكوين العشرات",
    "رؤية اللّون": "رؤية الألوان",
}

CHANNEL_DESCRIPTIONS = {
    "en": "The PhET Interactive Simulations project created by the University of Colorado Boulder provides interactive math and science simulations that engage students with intuitive, game-like environments. Students can learn about math, physics, biology, and chemistry through hands-on exploration and discovery. The simulations are appropriate for all ages and include guiding teacher lesson plans.",
    "ar": "تزوّد هذه القناة والمعمول بمحتواها من قبل جامعة كونيتيكيت الأمريكية مجموعة من برمجيات المحاكاة التي يمكن للمتعلمين في المرحلة الإعدادية والثانوية التفاعل معها لفهم أكبر لما قد يدرسونه من قوانين وتجارب في الرياضيات والعلوم المختلفة وخاصة مادتي الكيمياء والفيزياء.",
}

# CATEGORY_DATA = json.loads(sess.get(f"{BASE_URL}/partner-services/2.0/metadata/categories").text)
# def localized_category_title(cat_id, locale):
# return CATEGORY_DATA[cat_id]["strings"][locale]

# descriptions = ["Char count, Description\n"]


def get_channel_title(lang):
    return CHANNEL_METADATA.get(lang, {}).get("title", None)


def get_channel_description(lang):
    return CHANNEL_METADATA.get(lang, {}).get(
        "description", CHANNEL_DESCRIPTIONS.get(lang, None)
    )


# Maps of IDs to their metadata
"""
The structure / keys we care about:
{ "<cat_id>": { "strings": [ { "<locale>": "<label>" } ], "simulationIds": [ <sim_id>, ...], }
ex: `PHET_CATEGORIES['22']['strings']['en']` would return 'Elementary School'

This specifically maps to manually mapped "categories" which use our own metadata tags (ie, categories, grade_levels, etc)
"""
PHET_CATEGORIES = json.loads(
    sess.get(f"{BASE_URL}/partner-services/2.0/metadata/categories").text
)

"""
Similarly to the above, maps a "keyword_id" to a list of translated strings which can be used as tags
This data will only be applied if there is a localized tag available for the sim-at-hand's locale
"""
PHET_KEYWORDS = json.loads(
    sess.get(f"{BASE_URL}/partner-services/2.0/metadata/keywords").text
)

STATS = {}
STATS["en"] = {"docs": 0, "vids": 0, "sims_downloaded": [], "sims_skipped": []}


class PhET(SushiChef):
    def __init__(self, *args, **kwargs):
        """
        The class is constructed with these defaults as it is meant to run
        initially in English only. This is because all sims are available in
        English and we will gather the other locales as we process them.

        TODO: Once the initial gathering of locale data is complete, it should
        be stored in a file to serve as a cache for future runs. Maybe a
        --skip-cache option could be watched for?
        """
        # Typically we are passing around a Kolibri language code, but we should use the PhET codes
        # in certian cases where they differ. For example, what we call `pt` is `pt_BR` in PhET,
        # Use the helper _get_phet_lang_code when you need the PhET code (ie, API calls)
        with open("all_locales_mapping.json", "r") as f:
            self.lang_map = json.load(f)

        self.channel_name = BASE_TITLE  # English to begin with
        self.channel_source_id = BASE_SOURCE_ID
        self.channel_domain = "https://phet.colorado.edu"
        self.channel_language = DEFAULT_LANG
        self.channel_thumbnail = "chefdata/phet-logo-TM-partners.png"
        self.channel_description = get_channel_description(self.channel_language)
        self.teachers_guide = ""

        self.queued_locales = [
            key for key in list(self.lang_map.keys()) if key not in ["bs", "az"]
        ]
        self.completed_locales = set()

        super().__init__(PhET, *args, **kwargs)

    def _get_phet_lang_code(self, kolibri_lang_code):
        code = self.lang_map.get(kolibri_lang_code)
        if not code:
            raise ValueError(f"Lang code not mapped: {kolibri_lang_code}")
        else:
            return code

    def _update_translators(self):
        self.translator = GoogleTranslator(source="auto", target=self.channel_language)
        self.lang_en_translator = GoogleTranslator(
            source=self.channel_language, target=self.channel_language
        )

    def run_with_locale(self, locale):
        """
        After the English chef completes, this method will be called to run another language.
        """
        # JP: Not sure why this is necessary but it was in the original code
        if locale == "id":
            locale = "in"

        STATS[locale] = {
            "docs": 0,
            "vids": 0,
            "sims_downloaded": [],
            "sims_skipped": [],
        }
        # Setup channel info for new locale

        self.channel_name = self._localized_channel_title(locale)

        if locale == "uk":
            # idk why this is the case but... it is
            self.channel_source_id = "channel_PhET_Interactive_Simulations_TEST-uk"
        elif locale == "pt":
            # idk why this is the case but... it is
            self.channel_source_id = "channel_PhET_Interactive_Simulations_TEST-pt"
        elif locale == "es":
            # idk why this is the case but... it is
            self.channel_source_id = "phet-html5-simulations-es--ACTUALLY-JUST-A-TEST"
            self.channel_domain = "phet.colorado.edu"
        # elif locale == 'ht':
        # self.channel_source_id = "channel_PhET_Interactive_Simulations_TEST-ht"
        elif locale == "en":
            self.channel_source_id = BASE_SOURCE_ID
            self.channel_domain = "phet.colorado.edu"
        else:
            self.channel_source_id = BASE_SOURCE_ID + f"-{locale}"
        self.channel_language = locale

        # Setup translators for new locale
        self.translator = GoogleTranslator(source="auto", target=self.channel_language)
        if locale != "en":
            self.lang_en_translator = GoogleTranslator(
                source=self.channel_language, target=DEFAULT_LANG
            )

        self.teachers_guide = self.translator.translate(text="Coach's Guide")
        self.teachers_video = self.translator.translate(text="Coach's Video")
        self.channel_description = (
            get_channel_description(locale)
            or self.translator.translate(
                text=CHANNEL_DESCRIPTIONS.get(DEFAULT_LANG)
            )  # Fallback to translator
        )
        # print("\n\n")
        # print("\n\n")

        # Run the chef again with the new locale
        self.main()

    def construct_channel(self, *args, **kwargs):
        print(
            "Running Language: ",
            self.channel_language,
            self.channel_name,
            self.channel_domain,
            self.channel_source_id,
            self.channel_description,
        )
        channel = ChannelNode(
            source_domain=self.channel_domain,
            source_id=self.channel_source_id,
            title=self.channel_name,
            thumbnail=self.channel_thumbnail,
            description=self.channel_description,
            language=self.channel_language,
        )
        # print("Constructed channel: ", channel.__dict__)

        r_sim = sess.get(
            f"{BASE_URL}/partner-services/2.0/metadata/simulations?locale={self._get_phet_lang_code(self.channel_language)}"
        )
        r_cat = sess.get(f"{BASE_URL}/partner-services/2.0/metadata/categories")
        r_keyword = sess.get(
            f"{BASE_URL}/partner-services/2.0/metadata/keywords?locale={self._get_phet_lang_code(self.channel_language)}"
        )

        sim_data = json.loads(r_sim.text)
        cat_data = json.loads(r_cat.text)
        keyword_data = json.loads(r_keyword.text)

        dict_downloaded_paths = {}

        self.download_category(
            parent=channel,
            cat_id="1",
            categories=cat_data,
            keywords=keyword_data,
            sims={sim["id"]: sim for sim in sim_data["simulations"]},
            language=self.channel_language,
            dict_downloaded_paths=dict_downloaded_paths,
        )

        # print("Constructed channel: ", channel.title, channel.source_id)
        return channel

    def download_category(
        self,
        parent,
        cat_id,
        categories,
        sims,
        keywords,
        language,
        dict_downloaded_paths,
    ):
        """
        Process a category, and add all its sub-categories, and its simulations/videos.
        """
        # print("Processing category:", cat_id)
        cat = categories[str(cat_id)]
        cat_name = None
        dict_cat_name = cat["strings"]
        if dict_cat_name.get(self.channel_language):
            cat_name = dict_cat_name.get(self.channel_language)
        elif dict_cat_name.get(DEFAULT_LANG):
            cat_name = dict_cat_name.get(DEFAULT_LANG)
        # loop through all subtopics and recursively add them
        # (reverse order seems to give most rational results)
        for child_id in reversed(cat["childrenIds"]):
            # look up the child category by ID
            subcat = categories[str(child_id)]
            # skip it if it's in our blacklist
            if subcat["name"] in ID_BLACKLIST_BY_LANG.get(
                language, ID_BLACKLIST_BY_LANG.get(DEFAULT_LANG, [])
            ):
                continue
            # make the title human-readable, and clean it up

            title = subcat["strings"].get(language)
            if not title:
                title = subcat["name"].replace("-", " ").title()
                title = title.replace(" And ", " and ")
                title = title.replace("Mathconcepts", "Concepts")
                title = title.replace("Mathapplications", "Applications")
            if language == DEFAULT_LANG:
                pass
            elif language == "ar":
                title = ARABIC_NAME_CATEGORY.get(title, title)
            elif language == "ht":
                title = HAITIAN_NAME_CATEGORY.get(title, title)

            subtopic = TopicNode(
                source_id=subcat["name"], title=title, derive_thumbnail=True
            )
            parent.add_child(subtopic)
            # recursively download the contents of the topic
            self.download_category(
                subtopic,
                child_id,
                categories,
                sims,
                keywords,
                language,
                dict_downloaded_paths,
            )

        # loop through all sims in this topic and add them, but only if we're at a leaf topic
        if len(parent.children) == 0:
            for sim_id in list(set(cat["simulationIds"])):
                # print("SIM ID: {}".format(sim_id))
                # skip ones that aren't found (probably as they aren't HTML5)
                if sim_id not in sims:
                    continue
                try:
                    self.download_sim(
                        parent,
                        sims[sim_id],
                        sim_id,
                        keywords,
                        language,
                        dict_downloaded_paths,
                    )
                    STATS[language]["sims_downloaded"].append(sim_id)
                except Exception as e:
                    STATS[language]["sims_skipped"].append(sim_id)
                    print(f"Error downloading sim: {sim_id}", e)

    def download_sim(
        self, topic, sim, sim_id, keywords, language, dict_downloaded_paths
    ):
        """
        Download, zip, and add a node for a sim, as well as any associated video.
        """
        sim_detail_res = sess.get(
            f"https://phet-api.colorado.edu/partner-services/2.0/metadata/simulations/{sim_id}?locale={self._get_phet_lang_code(language)}"
        )
        sim_detail_data = json.loads(sim_detail_res.text)

        if (
            self._get_phet_lang_code(self.channel_language)
            not in sim_detail_data.get("localizedData")
            and self.channel_language != DEFAULT_LANG
        ):
            print("No sim for #{} in {}".format(sim_id, language))
            return

        subject_ids = sim_detail_data.get("subjectIds", [])  # metadata label-mapped
        metadata = {"categories": [], "grade_levels": [], "accessibility_labels": []}
        for subject_id in subject_ids:
            new_metadata = METADATA_BY_CAT.get(subject_id, {}).get("categories", [])
            if new_metadata:
                metadata["categories"] += new_metadata

        low_grade_level_id = sim_detail_data.get("lowGradeLevel", {}).get("id", None)
        high_grade_level_id = sim_detail_data.get("highGradeLevel", {}).get("id", None)
        if low_grade_level_id is not None and high_grade_level_id is None:
            high_grade_level_id = low_grade_level_id + 1

        if low_grade_level_id and high_grade_level_id:
            for grade_level_id in range(low_grade_level_id, high_grade_level_id):
                # Applies the grade levels
                new_metadata = METADATA_BY_CAT.get(grade_level_id, {}).get(
                    "grade_levels", []
                )
                if new_metadata:
                    metadata["grade_levels"] += new_metadata
        elif high_grade_level_id:
            metadata["grade_levels"].extend(
                METADATA_BY_CAT.get(high_grade_level_id, [])
            )

        keyword_ids = sim_detail_data.get("keywordIds", [])  # tags
        tags = []
        for keyword_id in keyword_ids:
            # localized keyword names
            if str(keyword_id) in PHET_KEYWORDS.keys():
                word = (
                    PHET_KEYWORDS.get(str(keyword_id), {})
                    .get("strings", {})
                    .get(self._get_phet_lang_code(language))
                )
                if word and len(word) <= 30:  ## max 30 chars on tags
                    tags.append(word)

        a11y_features = list(
            map(lambda f: f["id"], sim_detail_data.get("a11yFeatures", []))
        )  # accessibility features IDs
        if len(a11y_features) > 0:
            if 3 in a11y_features or 4 in a11y_features:
                # see https://docs.google.com/spreadsheets/d/1M5NQLtXUrGymxlvb4reqJmtUGLPCoXYvVB2P8vBVz_k/edit?gid=1471576465#gid=1471576465
                metadata.update({"accessibility_labels": [ALT_TEXT_KOLIBRI_ID]})

        # localized data may or may not have anything, but when it does, we'll use it first
        localized_data = sim_detail_data.get("localizedData", {}).get(
            self._get_phet_lang_code(language), {}
        )  # localized data
        # if we expect localized data (ie, we're not doing English) but don't get it, we'll get the default_data (english)
        # and then translate it
        default_data = sim_detail_data.get("defaultData", {})  # default data

        run_url = default_data.get("runUrl")
        # Ensure we're downloading the localized sim
        if run_url.endswith("_en.html") and language != DEFAULT_LANG:
            run_url = localized_data.get(
                "runUrl",
                run_url.replace(
                    "_en.html", f"_{self._get_phet_lang_code(language)}.html"
                ),
            )

        title = default_data.get("title")
        description = default_data.get("description")

        # The URL for a teacher's guide document
        document_url = None

        if localized_data:
            if localized_data.get("runUrl"):
                run_url = localized_data.get("runUrl")
            if localized_data.get("title"):
                title = localized_data.get("title")
            if localized_data.get("description"):
                description = localized_data.get("description")
            if localized_data.get("teachersGuide"):
                # if there is a `teachersGuide` field in `localizedData`, add it as a document node
                document_url = localized_data.get("teachersGuide")
        elif self.channel_language != DEFAULT_LANG:
            if self.translator:
                title = self.translator.translate(text=title)
            if description and description != localized_data.get("description"):
                description = self.translator.translate(text=description)
        else:
            if default_data.get("teachersGuide"):
                # otherwise see if we have a defaultData one (this is really only for english)
                document_url = default_data.get("teachersGuide")

        download_url = f"{BASE_URL_DOWNLOAD}{run_url}?download"
        ##print("\tProcessing sim:", title)
        dst = None
        if download_url not in dict_downloaded_paths:
            dst = tempfile.mkdtemp()
            dict_downloaded_paths[download_url] = {"dst": dst}
        if dst:
            download_file(
                download_url,
                dst,
                filename="index.html",
                request_fn=sess.get,
                middleware_callbacks=[process_sim_html],
                middleware_kwargs={"sim_title": title},
            )

            zippath = create_predictable_zip(dst)
            dict_downloaded_paths.get(download_url).update({"zippath": zippath})

        authors = None
        if sim_detail_data.get("thanksTo"):
            authors = re.sub(" \(.*?\)", "", sim_detail_data["thanksTo"])
            authors = re.sub("<br\/?>", ", ", authors)

        if language == "ar":
            if title in ARABIC_NAME_CATEGORY:
                title = ARABIC_NAME_CATEGORY[title]
            if title in SIM_TYPO:
                title = SIM_TYPO[title]
        elif language == "ht":
            if title in HAITIAN_NAME_CATEGORY:
                title = HAITIAN_NAME_CATEGORY.get(title, title)
        elif language != DEFAULT_LANG:
            if self.translator:
                title = self.translator.translate(text=title)
        # get thumbnail image
        lst_sim_images = default_data.get("simImages")
        sim_image = lst_sim_images[0].get("url")
        for dict_image in lst_sim_images:
            if dict_image.get("width") == 128:
                sim_image = dict_image.get("url")
                break

        # create a node for the sim
        zippath = dict_downloaded_paths.get(download_url).get("zippath")
        simnode = HTML5AppNode(
            source_id="sim-%d" % sim["id"],
            files=[HTMLZipFile(zippath)],
            title=title,
            description=description,
            license=CC_BYLicense(
                "PhET Interactive Simulations, University of Colorado Boulder"
            ),
            author=authors,
            # tags=[keywords[topic] for topic in sim["topicIds"]],
            thumbnail=sim_image,
            language=getlang(language),
            derive_thumbnail=True,
            tags=tags,
            **metadata,
        )

        del metadata["accessibility_labels"]

        if document_url:
            documentnode = DocumentNode(
                source_id="document-%d" % sim["id"],
                files=[DocumentFile(document_url)],
                title="(%s) %s" % (self.teachers_guide, title),
                license=CC_BYLicense(
                    "PhET Interactive Simulations, University of Colorado Boulder"
                ),
                derive_thumbnail=True,
                role=roles.COACH,
                tags=tags,
                **metadata,
            )
            STATS[self.channel_language]["docs"] = (
                STATS[self.channel_language]["docs"] + 1
            )
            topic.add_child(documentnode)
        # if there's a video, extract it and put it in the topic right before the sim

        # videos = default_data.get('simPrimerVimeoData', {}).get("files", None)
        if self.channel_language == DEFAULT_LANG:
            # we don't use primer_video_url because the english primer video links are inaccessible private
            # but the specifically encoded files should work fine (as it did before)
            # for the non-English ones we only get their localized `simPrimerUrl` and no encoded variants, so
            # that's the only path to take there
            primer_video_url = None
            if default_data.get("simPrimerVimeoData"):
                videos = sim_detail_data["defaultData"]["simPrimerVimeoData"]["files"]
                if videos:
                    video_url = [v for v in videos if v.get("height") == 540][0]["link"]

                    videonode = VideoNode(
                        source_id="video-%d" % sim["id"],
                        files=[VideoFile(video_url)],
                        title="Video: %s" % title,
                        license=CC_BYLicense(
                            "PhET Interactive Simulations, University of Colorado Boulder"
                        ),
                        thumbnail=sim_image,
                        role=roles.COACH,
                        derive_thumbnail=True,
                    )

                    topic.add_child(videonode)
        else:
            primer_video_url = localized_data.get("simPrimerUrl", None)

        # Only for non-English
        if primer_video_url:
            if "youtube" in primer_video_url:
                youtube_id = primer_video_url.split("/")[-1]
                file = YouTubeVideoFile(
                    youtube_id=youtube_id, language=self.channel_language
                )
            else:
                file = WebVideoFile(
                    web_url=primer_video_url,
                    language=self.channel_language,
                    download_settings={"referer": run_url},
                )

            videonode = VideoNode(
                source_id="video-%d" % sim["id"],
                files=[file],
                title="(%s) %s" % (self.teachers_video, title),
                license=CC_BYLicense(
                    "PhET Interactive Simulations, University of Colorado Boulder"
                ),
                thumbnail=sim_image,
                role=roles.COACH,
                derive_thumbnail=True,
                tags=tags,
                **metadata,
            )

            STATS[self.channel_language]["vids"] = (
                STATS[self.channel_language]["vids"] + 1
            )
            topic.add_child(videonode)

        # add the sim node into the topic
        topic.add_child(simnode)

    def _localized_channel_title(self, locale):
        if locale == "ht":
            return "PhET (Kreyòl ayisyen)"
        title = get_channel_title(locale)
        if title:
            # print("RETURNING TITLE: ", title)
            return title
        else:
            # print("BASE____________ TITLE: ", title)
            return f"{BASE_TITLE} ({getlang(locale).native_name})"


def process_sim_html(content, destpath, **kwargs):
    """Remove various pieces of the code that make requests to online resources, to avoid using
    bandwidth for users expecting a fully offline or zero-rated website."""

    # remove "are we online" check
    content = content.replace(
        "check:function(){var t=this", "check:function(){return;var t=this"
    )

    # remove online links from "about" modal
    content = content.replace(
        "getLinks:function(", "getLinks:function(){return [];},doNothing:function("
    )

    # setting up the query parameters for cases in which it works
    regex = r"(this\.getAllForString\([^,]+,[^w]*)(window\.location\.search)(\s*\))"
    replacement = r"\1window.location.search === '' ? '?allowLinks=false&disableFullscreen' : window.location.search\3"
    content = re.sub(regex, replacement, content)
    soup = BeautifulSoup(content, "html.parser")

    for script in soup.find_all("script"):
        # remove Google Analytics and online image bug requests
        if "analytics.js" in str(script):
            script.extract()

        if "phetWebsite" in str(script):
            # remove menu options that link to online resources
            # fallbacks in case the above regex work fails
            script.string = re.compile(
                'tandem: e.createTandem\("screenshotMenuItem"\),'
            ).sub("", script.string)
            script.string = re.compile(
                'tandem: e.createTandem\("fullScreenMenuItem"\),'
            ).sub("", script.string)
            script.string = re.compile("string!JOIST/menuItem.reportAProblem").sub(
                "", script.string
            )
            script.string = re.compile("string!JOIST/menuItem.phetWebsite").sub(
                "", script.string
            )

    clean_title = kwargs.get("sim_title").replace(" ", "-").replace("'", "-")

    ##############
    # DEBUG HELP #
    ##############
    """
    Set your env var `DUMP_SIMS=true` when running the chef to have the resulting HTML files dumped
    to a `processed_sims` directory
    """
    if os.environ.get("DUMP_SIMS", False):
        # check if the processed_sims directory exists
        if not os.path.exists("processed_sims"):
            # create it if not
            os.makedirs("processed_sims")

        # Write's every sim's HTML to the directory
        # in a terminal, run: python -m http.server <port> to test sims in your browser
        with open("processed_sims/{}.html".format(clean_title), "w") as f:
            f.write(str(soup))
            f.close()
    return str(soup)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="PhET Chef tool", allow_abbrev=False)
    parser.add_argument(
        "--lang",
        "-l",
        help="Comma-separated list of locale codes ex: `--lang=ar,en,ht` (see all_locales_mapping.json for more examples of the keys)",
    )
    args, _ = parser.parse_known_args()

    phet_chef = PhET()

    if args.lang:
        locale_keys = args.lang.split(",")
    else:
        locale_keys = list(phet_chef.lang_map.keys())

    failed_locales = []

    for locale in locale_keys:
        print("Running locale: {}".format(locale))
        try:
            phet_chef.run_with_locale(locale)
        except Exception as e:
            print(e)
