import json
import os
import unittest

import pytest

from ekshiksha import chef, utils


class EKShikshaChefTest(unittest.TestCase):
    def setUp(self):
        self.chef = chef.EkShikshaChef()

    def tearDown(self):
        self.chef.cleanup()

    def test_js_to_json(self):
        js = 'var myvar = {"key": "value", "sub_dict": {"number_one": 1, "truedat": true}}'

        mydict = utils.js_to_json(js)
        assert len(mydict) == 1
        myvar = mydict['myvar']
        # test types are converted to Python values properly
        assert myvar['key'] == 'value'
        assert myvar['sub_dict']['number_one'] == 1
        assert myvar['sub_dict']['truedat'] is True

    def test_get_contents(self):
        contents = self.chef.get_contents()

        assert len(contents) > 0
        assert isinstance(contents, list)

    def test_get_topics(self):
        topics = self.chef.get_topics()

        assert len(topics) > 0
        assert isinstance(topics, list)

    def test_get_content_info(self):
        """
        Test that get_file_info_for_content returns the expected information about the content.
        :return:
        """
        contents = self.chef.get_contents()
        for content in contents:
            html_filename = content['htmlFileName']
            ext = os.path.splitext(html_filename)[1]
            file_info = self.chef.get_file_info_for_content(content)
            if ext in ['.jsp', '.swf']:
                assert file_info is None
            else:
                assert file_info is not None, 'No info returned for content {}'.format(content)
                assert 'dir' in file_info
                assert 'dir_absolute' in file_info
                assert 'html_file' in file_info
                assert 'author' in file_info or 'organization' in file_info
                assert 'title' in file_info
                assert os.path.exists(file_info['dir_absolute'])
                assert os.path.exists(os.path.join(file_info['dir_absolute'], file_info['html_file']))

    @pytest.mark.slow
    def test_create_content_zips(self):
        self.chef.create_dependency_zip()
        assert os.path.exists(self.chef.dep_zip)

        contents = self.chef.get_content_metadata()
        for file_info in contents:
            try:
                self.chef.get_html5_zip_node_for_content(file_info)
            except:
                print("Unable to create zip for {}".format(file_info))
                raise
            assert 'html5_zip' in file_info
            assert os.path.exists(file_info['html5_zip'])

    def test_get_content_by_standards(self):
        contents = self.chef.get_content_metadata()
        standards = self.chef.get_contents_by_standard(contents)

        standard_keys = list(standards.keys())
        standard_keys.sort()

        standard_trees = {}
        for standard in standards:
            assert len(standards[standard]) > 0
            standard_trees[standard] = self.chef.get_content_tree(standards[standard])
            assert len(standard_trees[standard]) > 0

    def test_create_dependency_zip(self):
        self.chef.create_dependency_zip()

        assert os.path.exists(self.chef.dep_zip)

    def test_get_content_tree(self):
        contents_info = self.chef.get_content_metadata()
        tree = self.chef.get_content_tree(contents_info)
        assert isinstance(tree, list)
        assert len(tree) != 0
        assert 'subtopics' in tree[0]

    def test_create_ricecooker_nodes(self):
        self.chef.create_dependency_zip()

        contents = self.chef.get_content_metadata()
        info_with_zips = self.chef.get_zips_for_content(contents)
        tree = self.chef.get_content_tree(info_with_zips)

        for root_topic in tree:
            self.chef.create_topic_nodes_recursive(root_topic)

if __name__ == '__main__':
    unittest.main()