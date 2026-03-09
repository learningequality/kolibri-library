import os
import shutil

from ricecooker.classes.files import get_hash


class DupeFinder:
    """
    The purpose of this class is to search downloaded content and discover duplicate files. It is used to consolidate
    files for both space-saving purposes and also so that if patching is needed it can be done more efficiently.

    (e.g. if you need to modify 50 files, but they can be consolidated to two, it simplifies implementing and testing the
    modification)

    Note that filename search is case-insensitive.

    """
    def __init__(self, content_root):
        self.content_root = content_root

        assert os.path.exists(self.content_root)

    def find_duplicates(self, filename_to_find):
        """
        Find all copies of the file that are identical in the content root.

        :return: A dictionary
        """

        matches = []
        for root, dirnames, filenames in os.walk(self.content_root):
            for filename in filenames:
                if filename.lower() == filename_to_find.lower():
                    matches.append(os.path.join(root, filename))

        print("len(matches) = {}".format(len(matches)))
        file_instances = {}
        for match in matches:
            hash = get_hash(match)
            if not hash in file_instances:
                file_instances[hash] = []
            file_instances[hash].append(match)

        return file_instances

    def output_duplicates(self, duplicates, output_dir):
        for hash in duplicates:
            ext = ''
            for dupe in duplicates[hash]:
                file_ext = os.path.splitext(dupe)[1]
                # the code assumes all dupes have the same extension, so check that
                if len(ext) > 0:
                    assert file_ext == ext
                else:
                    ext = file_ext
            output_path = os.path.join(output_dir, '{}{}'.format(hash, ext))
            assert dupe
            # files are the same, so just copy the version last assigned to dupe
            shutil.copy(dupe, output_path)
