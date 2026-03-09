#!/usr/bin/env python
# -*- coding: utf-8 -*-

import csv
import glob
import os
import re
import shutil
import tempfile
import zipfile

from imscp.core import extract_from_zip
from imscp.ricecooker_utils import make_topic_tree_with_entrypoints
from le_utils.constants import languages, roles
from ricecooker.chefs import SushiChef
from ricecooker.classes import files
from ricecooker.classes import licenses
from ricecooker.classes import nodes
from ricecooker.config import LOGGER
from ricecooker.utils.zip import create_predictable_zip

from bs4 import BeautifulSoup

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.abspath(os.path.join(THIS_DIR, '..'))
FILES_DIR = os.path.join(ROOT_DIR, 'files')
LANGUAGES = ['en', 'es', 'fr', 'pt']
DEFAULT_LANG = 'en'

TRANSLATIONS = {
    'ICT Route': {
        'en': 'ICT Route',
        'es': 'Ruta TIC',
        'pt': 'Rota TIC'
    },
    'Innovation Route': {
        'en': 'Innovation Route',
        'es': 'Ruta Innovación',
        'pt': 'Rota Inovação'
    }

}

INDEX_TEMPLATE = """
<!DOCTYPE html>
<html>
   <head>
      <title>HTML Meta Tag</title>
      <meta http-equiv = "refresh" content = "0; url = {}" />
   </head>
   <body>
   </body>
</html>
"""


class ProFuturoChef(SushiChef):
    DATA_DIR = os.path.abspath('chefdata')
    lang_id = 'en'
    content_tree = {}

    def __init__(self, lang, *args, **kwargs):
        self.lang_id = lang
        self.lang_data = languages.getlang_by_alpha2(self.lang_id)
        # Code in __init__ may call get_channel, which expects channel_info to be defined,
        # so we do the initialization here.
        self.channel_info = {
            # FIXME: Translate language titles
            'CHANNEL_TITLE': 'ProFuturo ({})'.format(self.lang_data.native_name),
            'CHANNEL_SOURCE_DOMAIN': 'profuturo.education',  # where you got the content
            'CHANNEL_SOURCE_ID': 'profuturo-'+self.lang_id,  # channel's unique id
            'CHANNEL_LANGUAGE': self.lang_id,  # le_utils language code
            'CHANNEL_DESCRIPTION': '',  # (optional)
        }

        super(ProFuturoChef, self).__init__(*args, **kwargs)

    def construct_channel(self, **kwargs):
        self.temp_dir = tempfile.mkdtemp()
        try:

            self.removed_imgs = []
            self.remove_imgs = ['kap_cerrar.png']
            self.replace_images = ['cierre_ara.png', 'cierre_pyxie.png', 'cierre_crux.png']
            self.replaced_images = []
            channel = self.get_channel(**kwargs)

            self.get_content_tree()
            self.content_tree_to_channel(channel)
            # for img in self.remove_imgs:
            #     assert img in self.removed_imgs, "Image {} not removed".format(img)

            # for img in self.replace_images:
            #     assert img in self.replaced_images, "Image {} not replaced".format(img)
        finally:
            shutil.rmtree(self.temp_dir)

        return channel

    def content_tree_to_channel(self, channel):
        source_id = self.channel_info['CHANNEL_SOURCE_DOMAIN']
        child_topics = []
        for subject in self.content_tree:
            subject_id = '{}-{}'.format(source_id, subject)
            title = subject
            if subject.endswith('Route'):
                lang = self.lang_id
                if not self.lang_id in TRANSLATIONS[subject]:
                    lang = 'en'
                title = TRANSLATIONS[subject][lang]
            subject_node = nodes.TopicNode(source_id=subject_id, title=title)

            channel.add_child(subject_node)
            modules = self.content_tree[subject]
            for module in modules:
                if 'file' in module:
                    self.create_leaf_node(module, subject_node, subject_id)
                elif 'children' in module:
                    subtopic_id = '{}-{}'.format(subject_id, module['id'])
                    child_topics.append(module['title'])
                    thumbnail = None
                    if 'thumbnail' in module:
                        thumbnail = module['thumbnail']
                    subtopic_node = nodes.TopicNode(source_id=subtopic_id, title=module['title'],
                                                    description=module['description'], thumbnail=thumbnail)
                    subject_node.add_child(subtopic_node)
                    for child in module['children']:
                        self.create_leaf_node(child, subtopic_node, subtopic_id)


    def create_leaf_node(self, module, subject_node, subject_id):
        # zips are always SCORMs in this case.
        assert 'file' in module, "Invalid module: {}".format(module)
        if 'file' in module:
            ext = os.path.splitext(module['file'])[1].lower()
            if ext == '.zip':
                self.get_scorm_topic_tree(subject_node, module['file'])
            elif ext == '.pdf':
                license = licenses.SpecialPermissionsLicense(copyright_holder="ProFuturo",
                                                             description="FIXME: Get license info")
                doc_id = '{}-{}'.format(subject_id, module['id'])
                doc_file = files.DocumentFile(path=module['file'])
                doc_node = nodes.DocumentNode(title=module['title'], source_id=doc_id, files=[doc_file], license=license)
                subject_node.add_child(doc_node)
            role = roles.LEARNER
            if 'role' in module:
                role = module['role']

            def set_role_recursive(node, role):
                node.role = role
                for child in node.children:
                    set_role_recursive(child, role)

            set_role_recursive(subject_node, role)

    def get_scorm_topic_tree(self, parent, scorm_zip):
        license = licenses.SpecialPermissionsLicense(copyright_holder="ProFuturo", description="FIXME: Get license info")

        mod_zip_dir = os.path.join(self.DATA_DIR, 'modified_zips')
        zip_dir_name = os.path.splitext(os.path.basename(scorm_zip))[0]
        mod_zip_path = os.path.join(mod_zip_dir, '{}.zip'.format(zip_dir_name))
        # temporary workaround for a bug introduced when moving zips, this shouldn't be in the final version.
        if not os.path.exists(scorm_zip) and os.path.exists(mod_zip_path):
            shutil.move(mod_zip_path, scorm_zip)

        with tempfile.TemporaryDirectory() as extract_path:
            imscp_dict = extract_from_zip(
                    scorm_zip, license, extract_path)
            dep_zip_dir = os.path.join(self.DATA_DIR, 'dep_zips')
            os.makedirs(dep_zip_dir, exist_ok=True)
            os.makedirs(mod_zip_dir, exist_ok=True)
            if not os.path.exists(mod_zip_path):
                scorm_zip = self.modify_zip(scorm_zip)
                shutil.copy(scorm_zip, mod_zip_path)

            scorm_zip_hash = files.get_hash(mod_zip_path)
            scorm_zip_filename = '{}.zip'.format(scorm_zip_hash)
            scorm_zip_path = os.path.join(dep_zip_dir, scorm_zip_filename)
            # since we're hashing, if the file exists that means we already
            # copied it and it didn't change since the last run.
            if not os.path.exists(scorm_zip_path):
                shutil.copy(scorm_zip, scorm_zip_path)

            source_id = '{}-{}'.format(parent.source_id, os.path.splitext(os.path.basename(scorm_zip))[0])

            counter = 1
            for topic_dict in imscp_dict['organizations']:
                if not topic_dict['identifier']:
                    topic_dict['identifier'] = 'MANIFEST{}'.format(counter)
                    counter += 1

                node_options = {
                    'height': '580px',
                    'sandbox': 'allow-scripts allow-same-origin'
                }
                topic_tree = make_topic_tree_with_entrypoints(license, scorm_zip_path, topic_dict,
                        extract_path,
                        temp_dir=self.temp_dir, parent_id=source_id, node_options=node_options)
                parent.add_child(topic_tree)

    def modify_zip(self, scorm_zip):
        """
        The SCORM modules we receive in some cases have graphics that reference UI elements that don't exist in
        Kolibri. This function modifies the zip to remove them and returns the modified zip.
        :param scorm_zip: The path to the original zip file.
        :return: Path to the modified zip file, if it exists.
        """
        zip_dir_name = os.path.splitext(os.path.basename(scorm_zip))[0]
        zip_root = os.path.join(self.temp_dir, zip_dir_name)
        output_zip = os.path.join(self.temp_dir, 'out_zips', zip_dir_name)

        os.makedirs(zip_root, exist_ok=True)
        os.makedirs(os.path.dirname(output_zip), exist_ok=True)

        zip = zipfile.ZipFile(scorm_zip)
        zip.extractall(zip_root)

        zip_changed = False
        telas_end_sprites = os.path.join(zip_root, 'curso', 'telas', 'end', 'sprites.png')
        if os.path.exists(telas_end_sprites):
            LOGGER.debug("Deleting sprites at {}".format(telas_end_sprites))
            os.remove(telas_end_sprites)
            zip_changed = True
        else:
            assert "n1_ted_len_en_u01_v02" not in scorm_zip, os.listdir(zip_root)

        for replace_img in self.replace_images:
            img_glob = glob.glob(os.path.join(zip_root, '**', replace_img), recursive=True)
            for img in img_glob:
                os.remove(img)
                shutil.copy(os.path.join(ROOT_DIR, 'assets', replace_img), img)
                if not replace_img in self.replaced_images:
                    self.replaced_images.append(replace_img)

                zip_changed = True

        # make any HTML replacements
        replaced_imgs = []
        for html_file in glob.glob(os.path.join(zip_root, '**', '*.html'), recursive=True):
            soup = BeautifulSoup(open(html_file, 'rb').read(), parser='html.parser')

            for img in self.remove_imgs:
                img_tag = soup.find('img', src = re.compile('{}$'.format(img)))
                if img_tag:
                    if not img in self.removed_imgs:
                        self.removed_imgs.append(img)
                    replaced_imgs.append(img)
                    img_tag.extract()
                    f = open(html_file, 'wb')
                    f.write(soup.prettify('utf-8'))
                    f.close()
                    zip_changed = True
                    break
                else:
                    assert img not in soup.prettify(), "Problem replacing image {} in {}".format(img, scorm_zip)

        if 'n2_tek_en_lan_u09' in scorm_zip:
            assert zip_changed, "Narrative SCORM module had no changes."
            assert 'kap_cerrar.png' in replaced_imgs, "Replaced images = {}".format(replaced_imgs)
            assert 'kap_cerrar.png' in self.removed_imgs, "Removed images = {}".format(self.removed_imgs)

        if zip_changed:
            temp_zip = create_predictable_zip(zip_root)
            scorm_zip = output_zip + '.zip'
            os.rename(temp_zip, scorm_zip)

        return scorm_zip

    def get_content_tree(self):
        lang = self.lang_data.name
        lang_dir = os.path.join(FILES_DIR, lang)
        pattern = os.path.join(lang_dir, '*.csv')
        csv_files = glob.glob(pattern)
        assert len(csv_files) == 1, "Pattern: {}, CSVs: {}".format(pattern, csv_files)
        csv_file = csv_files[0]
        with open(csv_file) as f:
            reader = csv.reader(f, delimiter=';')

            # first line is the field definitions
            lines = list(reader)
            for line in lines[1:]:
                id, title, filename, description, standard, this_lang, subject = line

                # there are sometimes empty placeholders in the metadata that contain no content,
                # so we ignore those.
                if id == "0":
                    if not subject in self.content_tree:
                        self.content_tree[subject] = []

                    item = {
                        'id': id,
                        'title': title,
                        'file': os.path.join(lang_dir, filename),
                        'description': description
                    }
                    self.content_tree[subject].append(item)

        ict_dir = os.path.join(lang_dir, 'ICT-routes')
        if os.path.exists(ict_dir):
            self.content_tree['ICT Route'] = []
            self.content_tree['Innovation Route'] = []
            ict_csv_files = glob.glob(os.path.join(ict_dir, '*.csv'))
            assert len(ict_csv_files) == 1
            ict_csv_file = ict_csv_files[0]

            with open(ict_csv_file) as f:
                reader = csv.reader(f, delimiter=';')

                # first line is the field definitions
                lines = list(reader)
                for line in lines[1:]:
                    id, title, filename, description, image = line[:5]

                    route = 'ICT Route'
                    if filename.startswith('IN'):
                        route = 'Innovation Route'
                    lar_file = os.path.join(ict_dir, filename)
                    children = self.parse_lar_file(lar_file, roles.COACH)

                    item = {
                        'id': title.replace(" ", "_").upper(),
                        'title': title,
                        'description': description,
                        'thumbnail': os.path.join(ict_dir, image),
                        'role': roles.COACH,
                        'children': children
                    }

                    self.content_tree[route].append(item)

        # Add the additional content we were sent.
        if self.lang_id == 'en':
            self.content_tree['Rwanda Alternative Learning Math'] = [{
                'id': 'rwanda-alm',
                'title': 'Math',
                'file': os.path.join(FILES_DIR, 'Rwanda Alternative Learning Math SCORMs.zip'),
                'description': 'Rwanda Alternative Learning Math'
            }]

            dirs = []
            content_dir = os.path.join(FILES_DIR, "Level Up SCORMs offline")
            self.content_tree['Level Up'] = []
            for afile in os.listdir(content_dir):
                basename, ext = os.path.splitext(afile)
                item = {
                    'id': 'level-up-{}'.format(basename.lower()),
                    'title': basename,
                    'file': os.path.join(content_dir, afile),
                    'description': '',
                    'role': roles.COACH
                }
                self.content_tree['Level Up'].append(item)


    def parse_lar_file(self, lar_file, role=roles.LEARNER):
        lang = self.lang_data.name
        lang_dir = os.path.join(FILES_DIR, lang)
        ict_dir = os.path.join(lang_dir, 'ICT-routes')

        subdir_name = os.path.splitext(os.path.basename(lar_file))[0]

        lar_dir = os.path.join(ict_dir, subdir_name)
        if not os.path.exists(lar_dir):
            zip = zipfile.ZipFile(lar_file)
            zip.extractall(lar_dir)

        pattern = os.path.join(lar_dir, 'groups', '*', 'portlets', 'scormadmin_WAR_liferaylmsportlet', 'scormentries',
                               '*.xml')
        metadata_files = glob.glob(pattern)
        assert len(metadata_files) > 0, "No files found for pattern {}".format(pattern)

        items = []

        import xml.etree.ElementTree as ET
        for metadata_file in metadata_files:

            tree = ET.parse(metadata_file)
            root = tree.getroot()
            title = root.find('__title').text
            desc = root.find('__description').text
            id = root.find('__uuid').text

            scorm_file = os.path.join(os.path.splitext(metadata_file)[0], '{}.zip'.format(id))

            item = {
                'id': id,
                'title': title,
                'file': scorm_file,
                'description': desc,
                'role': role,
            }

            items.append(item)

        return items
