#!/usr/bin/env python
import json
import os
import shutil



# EXTRACT
################################################################################
EXPORTED_DIRNAME = 'Exported'
EXTRACT_DIRNAME = 'Courses'
FILES_TO_SKIP = ['.DS_Store', 'Thumbs.db', 'ehthumbs.db', 'ehthumbs_vista.db', '.gitkeep']


def extract_courses():
    """
    Extract all the `.gz`s from `chefdata/Exported/{course_name}.gz`
    to `chefdata/Courses/{course_name}/course`.
    Returns course_names = list of course names encountered.
    """
    course_names = []
    # src
    srcdir = os.path.join('chefdata', EXPORTED_DIRNAME)
    # dest
    extractdir = os.path.join('chefdata', EXTRACT_DIRNAME)
    for filename in os.listdir(srcdir):
        if filename.endswith('.gz') or filename.endswith('.tar.gz'):
            gzpath = os.path.join(srcdir, filename)
            if filename.endswith('.tar.gz'):
                course_name = filename.replace('.tar.gz', '')
            elif filename.endswith('.gz'):
                course_name = filename.replace('.gz', '')
            else:
                print('unexpected filename', filename)
            destdir = os.path.join(extractdir, course_name)
            if not os.path.exists(os.path.join(destdir)):
                print('Untargzipping course', course_name, 'from', gzpath, 'to', destdir)
                shutil.unpack_archive(gzpath, destdir, 'gztar')
            course_names.append(course_name)
        else:
            print('skipping non-gz file', filename)

    return course_names


def extract():
    """
    Call extract_courses to untargz 
        Exported/{course_name}.tar.gz --> Courses/{course_name}/course
    and list of courses in `course_list.json` for later processing.
    """

    course_names = extract_courses()
    print('\textracting course_names', course_names)

    lang = 'ar'
    course_list = {
        "title": "Edraak Continuing Education".format(lang),
        "kind": "edX course listing",
        "courses": []
    }
    for course_name in course_names:
        print('\tCourse course_name=', course_name)
        course_info = {
            "name": course_name,
            "path": os.path.join('chefdata', EXTRACT_DIRNAME, course_name),
            "lang": lang,
        }
        course_list['courses'].append(course_info)

    containerdir = os.path.join('chefdata', EXTRACT_DIRNAME)
    couse_list_path = os.path.join(containerdir, 'course_list.json')
    with open(couse_list_path, 'w') as couse_list_file:
        json.dump(course_list, couse_list_file, indent=4, ensure_ascii=False)



# CLI
################################################################################

if __name__ == '__main__':
    extract()
