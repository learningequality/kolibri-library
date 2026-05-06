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

# Manually-curated localized channel metadata keyed by locale code (row[1] in the CSV).
# The CSV holds human-translated title, tagline, and description for each locale and
# takes priority over the machine-translated fallbacks defined later in this file.
CHANNEL_METADATA = {}

# see https://docs.google.com/spreadsheets/d/1M5NQLtXUrGymxlvb4reqJmtUGLPCoXYvVB2P8vBVz_k/edit?gid=1471576465#gid=1471576465
# currnently, this is the only a11y label we have that maps to Phet's own a11yFeatures (it's alt text)
ALT_TEXT_KOLIBRI_ID = "Lb0tb9VC"

with open("titles_taglines_descriptions.csv") as csv_file:
    csv_reader = csv.reader(csv_file, delimiter=",")
    line_count = 0
    for row in csv_reader:
        if line_count == 0:
            # Skip the header row.
            line_count += 1
            continue
        else:
            CHANNEL_METADATA[row[1]] = {
                "title": row[2],
                "tagline": row[3],
                "description": row[4],
            }

# Raise Ricecooker's description char limit so our longer localized descriptions aren't truncated.
MAX_CHAR_LIMITS.update({"description": {"max": 4096}})

# "en" is the baseline locale: all sims exist in English, so non-English locales
# fall back to the English metadata whenever localized data is missing.
DEFAULT_LANG = "en"
BASE_TITLE = "PhET Interactive Simulations"
# Channel source_ids for locales without a special override are derived as f"{BASE_SOURCE_ID}-{locale}".
# Studio derives a deterministic channel_id from (source_domain, source_id), so changing this value
# would silently redirect every non-overridden locale to a brand-new channel on Studio.
BASE_SOURCE_ID = "phet-html5-simulations"

# Shared HTTP session with retries + on-disk HTTP-cache. The cache lives in `.webcache/` and
# re-uses the Cache-Control headers from PhET's API so repeated chef runs don't re-fetch
# everything from the network.
retry_strategy = Retry(total=5, backoff_factor=1)
# adapter = HTTPAdapter(max_retries=retry_strategy)

cache = FileCache(".webcache")
adapter = CacheControlAdapter(cache=cache)
sess = requests.Session()
sess.mount("http://", adapter)
sess.mount("https://", adapter)

# Per-locale list of PhET category `name`s to skip entirely while walking the category tree.
# "html" / "by-device" / "new" / "quantum" / "general" are duplicates or non-content buckets,
# and Arabic additionally excludes "by-level" because they don't want grade-level grouping.
ID_BLACKLIST_BY_LANG = {
    "en": ["html", "by-device", "new", "quantum", "general"],
    "ar": ["html", "by-device", "new", "quantum", "general", "by-level"],
}

BASE_URL = "https://phet-api.colorado.edu"
BASE_URL_DOWNLOAD = "https://phet.colorado.edu"

# Manual translations for category/sim titles where PhET's API either lacks a localized string
# or where we want to override PhET's default. Used as a last-mile lookup right before the label
# is rendered to a TopicNode/HTML5AppNode.
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
    "Math and Statistics": "Matematik ak Estatistik",
    "Earth and Space": "Latè ak Lespas",
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

# Spelling corrections for Arabic sim titles returned by the PhET API.
# These are applied only when building the Arabic channel.
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

# Hard-coded fallback channel descriptions. Only hit when `CHANNEL_METADATA` (from the CSV)
# has no entry for a given locale; if that fallback is also missing we machine-translate
# the English description in run_with_locale.
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


# Maps of IDs to their metadata. Fetched once at import time (module-level) and re-used
# across every locale run. The cached HTTP session makes subsequent chef runs fast.
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

# Per-locale stats, populated as the chef runs. Used for post-run reporting
# (counts of teacher-guide docs, coach videos, sims downloaded, sims skipped).
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

        # Start configured for English. `run_with_locale` mutates these in-place
        # for each subsequent locale (then calls `self.main()` again).
        self.channel_name = BASE_TITLE  # English to begin with
        self.channel_source_id = BASE_SOURCE_ID
        self.channel_domain = "https://phet.colorado.edu"
        self.channel_language = DEFAULT_LANG
        self.channel_thumbnail = "chefdata/phet-logo-TM-partners.png"
        self.channel_description = get_channel_description(self.channel_language)
        self.teachers_guide = ""

        # `bs` and `az` are intentionally skipped (no localized PhET content of value).
        self.queued_locales = [
            key for key in list(self.lang_map.keys()) if key not in ["bs", "az"]
        ]
        self.completed_locales = set()

        super().__init__(PhET, *args, **kwargs)

    def _get_phet_lang_code(self, kolibri_lang_code):
        # Kolibri and PhET use different locale codes in places (e.g. Kolibri `pt` == PhET `pt_BR`).
        # Use this helper any time you're hitting the PhET API or looking up localized strings
        # indexed by PhET's code.
        code = self.lang_map.get(kolibri_lang_code)
        if not code:
            raise ValueError(f"Lang code not mapped: {kolibri_lang_code}")
        else:
            return code

    def _update_translators(self):
        # `self.translator`: translates arbitrary source → channel language (used for sim titles/descriptions).
        # `self.lang_en_translator`: only meaningful when DEFAULT_LANG != channel_language; see override in run_with_locale.
        self.translator = GoogleTranslator(source="auto", target=self.channel_language)
        self.lang_en_translator = GoogleTranslator(
            source=self.channel_language, target=self.channel_language
        )

    def run_with_locale(self, locale):
        """
        After the English chef completes, this method will be called to run another language.
        """
        # JP: Not sure why this is necessary but it was in the original code
        # (Kolibri's "id" = Indonesian, but PhET historically expected "in".)
        if locale == "id":
            locale = "in"

        # Fresh per-locale stats bucket so the run-summary later has a slot to write into.
        STATS[locale] = {
            "docs": 0,
            "vids": 0,
            "sims_downloaded": [],
            "sims_skipped": [],
        }
        # Setup channel info for new locale

        self.channel_name = self._localized_channel_title(locale)

        # --- Legacy source_id overrides ---
        # Studio derives the deterministic channel_id from (source_domain, source_id).
        # Each of these locales was originally published with a non-default source_id,
        # so we MUST preserve those strings or the chef will push to a brand-new channel
        # instead of updating the existing one. (This exact bug hit `ht` when its override
        # was commented out — the "restore ht" change lives on this branch.)
        if locale == "uk":
            # idk why this is the case but... it is
            self.channel_source_id = "channel_PhET_Interactive_Simulations_TEST-uk"
        elif locale == "pt":
            # idk why this is the case but... it is
            self.channel_source_id = "channel_PhET_Interactive_Simulations_TEST-pt"
        elif locale == "es":
            # idk why this is the case but... it is
            self.channel_source_id = "phet-html5-simulations-es--ACTUALLY-JUST-A-TEST"
            # `es` also uses a schemeless domain, so both source_domain AND source_id must match.
            self.channel_domain = "phet.colorado.edu"
        elif locale == "ht":
            self.channel_source_id = "channel_PhET_Interactive_Simulations_TEST-ht"
        elif locale == "en":
            # English channel uses the "clean" base id (no -locale suffix) since it was published first.
            self.channel_source_id = BASE_SOURCE_ID
            self.channel_domain = "phet.colorado.edu"
        else:
            # Default path for every locale that doesn't have a legacy override.
            self.channel_source_id = BASE_SOURCE_ID + f"-{locale}"
        self.channel_language = locale

        # Setup translators for new locale. We instantiate a *new* GoogleTranslator so any
        # leftover state from the previous locale doesn't leak into this one.
        self.translator = GoogleTranslator(source="auto", target=self.channel_language)
        if locale != "en":
            self.lang_en_translator = GoogleTranslator(
                source=self.channel_language, target=DEFAULT_LANG
            )

        # Pre-translate the UI strings we prepend to teacher-guide docs/videos so we only
        # call the translator API once per locale.
        self.teachers_guide = self.translator.translate(text="Coach's Guide")
        self.teachers_video = self.translator.translate(text="Coach's Video")
        # Description priority: CSV → hard-coded CHANNEL_DESCRIPTIONS → machine-translated English.
        self.channel_description = (
            get_channel_description(locale)
            or self.translator.translate(
                text=CHANNEL_DESCRIPTIONS.get(DEFAULT_LANG)
            )  # Fallback to translator
        )
        # print("\n\n")
        # print("\n\n")

        # Re-enter the SushiChef pipeline with the newly-configured state. This effectively
        # runs the whole chef once per locale.
        self.main()

    def construct_channel(self, *args, **kwargs):
        # Diagnostic print so when a run produces a wrong channel_id on Studio we can compare
        # the (channel_domain, channel_source_id) pair that was used against the expected one.
        print(
            "Running Language: ",
            self.channel_language,
            self.channel_name,
            self.channel_domain,
            self.channel_source_id,
            self.channel_description,
        )
        # (source_domain, source_id) are hashed together to form Studio's deterministic
        # channel_id — so both must be stable across runs for the same channel.
        channel = ChannelNode(
            source_domain=self.channel_domain,
            source_id=self.channel_source_id,
            title=self.channel_name,
            thumbnail=self.channel_thumbnail,
            description=self.channel_description,
            language=self.channel_language,
        )
        # print("Constructed channel: ", channel.__dict__)

        # Fetch the locale-specific simulation list + localized keyword labels. Categories
        # are the same shape for every locale (labels are inside `.strings[<locale>]`).
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

        # Shared across a single locale's run. Avoids downloading+zipping the same sim twice
        # when the same sim appears under multiple categories (the tree is a DAG, not a pure tree).
        dict_downloaded_paths = {}

        # Start walking at root category "1"; this recursively fills out the full channel.
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
        # Resolve the localized display name with an English fallback. (`cat_name` is not
        # actually used downstream, but the language resolution pattern is preserved
        # intentionally — a debugging aid while verifying locale coverage.)
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
            # Blacklist is per-language with English as default (see ID_BLACKLIST_BY_LANG above).
            if subcat["name"] in ID_BLACKLIST_BY_LANG.get(
                language, ID_BLACKLIST_BY_LANG.get(DEFAULT_LANG, [])
            ):
                continue
            # make the title human-readable, and clean it up

            # Prefer PhET's localized label, otherwise reconstruct one from the slug-like `name`
            # (e.g. "math-concepts" → "Math Concepts") and patch a couple of well-known
            # concatenation glitches from PhET's own labels.
            title = subcat["strings"].get(language)
            if not title:
                title = subcat["name"].replace("-", " ").title()
                title = title.replace(" And ", " and ")
                title = title.replace("Mathconcepts", "Concepts")
                title = title.replace("Mathapplications", "Applications")
            # Last-mile manual override for locales whose PhET labels we consider wrong
            # or missing (see ARABIC_NAME_CATEGORY / HAITIAN_NAME_CATEGORY at the top).
            if language == DEFAULT_LANG:
                pass
            elif language == "ar":
                title = ARABIC_NAME_CATEGORY.get(title, title)
            elif language == "ht":
                title = HAITIAN_NAME_CATEGORY.get(title, title)

            # source_id for a topic is the PhET category `name` — stable across locales
            # so that the same topic's channel-tree position is stable on Studio.
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
        # (non-leaf categories are shown in Kolibri as a folder of subfolders with no direct sims).
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
                    # Isolate failures per-sim so one bad sim doesn't tank the whole locale run.
                    STATS[language]["sims_skipped"].append(sim_id)
                    print(f"Error downloading sim: {sim_id}", e)

    def download_sim(
        self, topic, sim, sim_id, keywords, language, dict_downloaded_paths
    ):
        """
        Download, zip, and add a node for a sim, as well as any associated video.
        """
        # Per-sim metadata fetch (one HTTP hit per sim per locale; cached by our session).
        sim_detail_res = sess.get(
            f"https://phet-api.colorado.edu/partner-services/2.0/metadata/simulations/{sim_id}?locale={self._get_phet_lang_code(language)}"
        )
        sim_detail_data = json.loads(sim_detail_res.text)

        # Skip any sim that simply doesn't exist in this locale. English always has all
        # sims, so we never hit this branch for DEFAULT_LANG.
        if (
            self._get_phet_lang_code(self.channel_language)
            not in sim_detail_data.get("localizedData")
            and self.channel_language != DEFAULT_LANG
        ):
            print("No sim for #{} in {}".format(sim_id, language))
            return

        # --- Map PhET metadata → Kolibri metadata (categories + grade levels + a11y) ---
        # `METADATA_BY_CAT` (imported from metadata_tags.py) translates PhET's numeric
        # subject/grade/a11y IDs into the constants Kolibri expects.
        subject_ids = sim_detail_data.get("subjectIds", [])  # metadata label-mapped
        metadata = {"categories": [], "grade_levels": [], "accessibility_labels": []}
        for subject_id in subject_ids:
            new_metadata = METADATA_BY_CAT.get(subject_id, {}).get("categories", [])
            if new_metadata:
                metadata["categories"] += new_metadata

        # Expand the [low, high] grade-level range into individual Kolibri grade tags.
        # If PhET only gives a `low`, assume the sim spans exactly one grade.
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

        # Build localized tags from PhET's keyword IDs. Skip anything over 30 chars because
        # Kolibri rejects long tags.
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

        # Accessibility: PhET a11y feature IDs 3 and 4 correspond to "has alt text".
        # The only Kolibri a11y label we currently support mapping from PhET is alt-text,
        # so that's the only label we set here.
        a11y_features = list(
            map(lambda f: f["id"], sim_detail_data.get("a11yFeatures", []))
        )  # accessibility features IDs
        if len(a11y_features) > 0:
            if 3 in a11y_features or 4 in a11y_features:
                # see https://docs.google.com/spreadsheets/d/1M5NQLtXUrGymxlvb4reqJmtUGLPCoXYvVB2P8vBVz_k/edit?gid=1471576465#gid=1471576465
                metadata.update({"accessibility_labels": [ALT_TEXT_KOLIBRI_ID]})

        # --- Resolve title / description / runUrl ---
        # Priority is (1) localized fields, then (2) defaultData (English), then (3) machine translation.
        # localized data may or may not have anything, but when it does, we'll use it first
        localized_data = sim_detail_data.get("localizedData", {}).get(
            self._get_phet_lang_code(language), {}
        )  # localized data
        # if we expect localized data (ie, we're not doing English) but don't get it, we'll get the default_data (english)
        # and then translate it
        default_data = sim_detail_data.get("defaultData", {})  # default data

        run_url = default_data.get("runUrl")
        # Ensure we're downloading the localized sim
        # PhET's API sometimes returns the English URL inside `defaultData` even when the
        # sim exists in the target locale, so we swap the `_en.html` suffix for `_<locale>.html`
        # if we don't explicitly get a localized runUrl.
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
            # Override every field that the localized blob provides. Anything missing falls
            # through to the already-assigned default_data values.
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
            # No localized blob at all → translate the English fields into the channel locale.
            if self.translator:
                title = self.translator.translate(text=title)
            if description and description != localized_data.get("description"):
                description = self.translator.translate(text=description)
        else:
            if default_data.get("teachersGuide"):
                # otherwise see if we have a defaultData one (this is really only for english)
                document_url = default_data.get("teachersGuide")

        # Zip cache: if we've already downloaded+zipped this sim in this run, re-use the zip.
        # (The same sim can appear under multiple categories, and the zip process is expensive.)
        download_url = f"{BASE_URL_DOWNLOAD}{run_url}?download"
        ##print("\tProcessing sim:", title)
        dst = None
        if download_url not in dict_downloaded_paths:
            dst = tempfile.mkdtemp()
            dict_downloaded_paths[download_url] = {"dst": dst}
        if dst:
            # `process_sim_html` strips online-only behavior from the sim so it runs fully offline.
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

        # PhET's `thanksTo` is human-written HTML-ish prose; strip parenthetical roles and <br>s
        # to produce a clean comma-separated author string for Kolibri's author field.
        authors = None
        if sim_detail_data.get("thanksTo"):
            authors = re.sub(" \(.*?\)", "", sim_detail_data["thanksTo"])
            authors = re.sub("<br\/?>", ", ", authors)

        # Locale-specific last-mile title overrides.
        #  - Arabic: category-name lookup, then a typo fix pass.
        #  - Haitian: category-name lookup only (we trust PhET's title otherwise).
        #  - All other non-English: fall back to Google Translate.
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
        # Prefer the 128x128 variant (matches Kolibri's thumbnail expectations); fall back
        # to whatever is first in the list.
        lst_sim_images = default_data.get("simImages")
        sim_image = lst_sim_images[0].get("url")
        for dict_image in lst_sim_images:
            if dict_image.get("width") == 128:
                sim_image = dict_image.get("url")
                break

        # create a node for the sim
        # source_id `sim-<numeric id>` is stable across locales so updates replace the same node.
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

        # DocumentNode / VideoNode don't accept `accessibility_labels`, so strip it from the
        # metadata dict before reusing it for the document + video below.
        del metadata["accessibility_labels"]

        if document_url:
            # Teacher guide is attached as a Coach-role document right before the sim inside the topic.
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

        # --- Primer video handling (two completely different paths for English vs non-English) ---
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
                    # Pick the 540p encoding for a reasonable size/quality tradeoff.
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
            # Non-English: PhET only exposes a single `simPrimerUrl` (usually a YouTube link,
            # sometimes a Vimeo page URL). No encoded-file variants are available.
            primer_video_url = localized_data.get("simPrimerUrl", None)

        # Only for non-English
        if primer_video_url:
            # YouTube links are resolved through ytdl by yt_id; any other URL goes through
            # the generic WebVideoFile downloader, which needs the sim's runUrl as Referer
            # to pass PhET's hotlink checks.
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
        # Prefer the manually-curated title from the CSV; otherwise generate a predictable
        # fallback like "PhET Interactive Simulations (Français)".
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

    # Short-circuit PhET's network connectivity probe so the sim doesn't stall offline
    # trying to reach phet.colorado.edu.
    # remove "are we online" check
    content = content.replace(
        "check:function(){var t=this", "check:function(){return;var t=this"
    )

    # Kill the list of links the "About" modal would show so no "Visit PhET website" entries appear.
    # remove online links from "about" modal
    content = content.replace(
        "getLinks:function(", "getLinks:function(){return [];},doNothing:function("
    )

    # Inject query params (`allowLinks=false&disableFullscreen`) only when the user hasn't
    # provided any, so we suppress external-link buttons and fullscreen (which can break
    # inside Kolibri's iframe) without clobbering a user-supplied query string.
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
            # Belt-and-suspenders: even if the injected query-string trick above doesn't land
            # (e.g. PhET changes its source), we still strip the offending menu items directly.
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

    # --lang lets you run a subset during dev (e.g. `--lang=ar,ht`). Omitting it runs
    # every locale from `all_locales_mapping.json`.
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

    # Per-locale driver loop. A failure in one locale is caught and logged, so one bad
    # locale (API quirks, translator rate-limits, etc.) doesn't prevent the others from running.
    for locale in locale_keys:
        print("Running locale: {}".format(locale))
        try:
            phet_chef.run_with_locale(locale)
        except Exception as e:
            print(e)
