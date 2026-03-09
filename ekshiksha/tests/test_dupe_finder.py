import os
import unittest

from ekshiksha import chef, dupe_finder


class EKShikshaChefTest(unittest.TestCase):
    def setUp(self):
        self.chef = chef.EkShikshaChef()

    def tearDown(self):
        self.chef.cleanup()

    def test_find_duplicates(self):
        finder = dupe_finder.DupeFinder(self.chef.content_root)
        three_js_versions = finder.find_duplicates('Three.js')
        assert len(three_js_versions) == 5, "versions = {}".format(three_js_versions)

        output_dir = os.path.join(self.chef.cache_dir, 'duplicates_library')
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        finder.output_duplicates(three_js_versions, output_dir)

        for hash in three_js_versions:
            version = "{}.js".format(hash)
            assert os.path.exists(os.path.join(output_dir, version))

        min_output_dir = os.path.join(output_dir, 'min')
        if not os.path.exists(min_output_dir):
            os.makedirs(min_output_dir)

        three_js_min_versions = finder.find_duplicates('Three.min.js')
        assert len(three_js_min_versions) == 3, "versions = {}".format(three_js_min_versions)

        finder.output_duplicates(three_js_min_versions, min_output_dir)

        for hash in three_js_min_versions:
            version = "{}.js".format(hash)
            assert os.path.exists(os.path.join(min_output_dir, version))