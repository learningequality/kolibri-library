#!/usr/bin/env python
import io
import json
import os
import pickle
import re
import shutil



from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request



# GOOGLE APIv3 UTILS
################################################################################

# Creds storage
CLIENT_SECRET_FILE = 'credentials/client_secret.json'  # server application -- this will request OAuth2 login
CLIENT_TOKEN_PICKLE = 'credentials/token.pickle'
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets.readonly',
    'https://www.googleapis.com/auth/drive.readonly',
]

class MemoryCache():
    # workaround for error "file_cache is unavailable when using oauth2client >= 4.0.0 or google-auth'"
    # via https://github.com/googleapis/google-api-python-client/issues/325#issuecomment-274349841
    _CACHE = {}

    def get(self, url):
        return MemoryCache._CACHE.get(url)

    def set(self, url, content):
        MemoryCache._CACHE[url] = content



def get_service(service_name=None, service_version=None):
    creds = None
    # The file credentials/token.pickle stores the user access and refresh tokens
    # it is created automatically after the first authorization flow completes
    if os.path.exists(CLIENT_TOKEN_PICKLE):
        with open(CLIENT_TOKEN_PICKLE, 'rb') as token:
            creds = pickle.load(token)
    # If there are no (valid) credentials available, let the user log in
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, SCOPES)
            creds = flow.run_local_server()
        # Save the credentials for the next run
        with open(CLIENT_TOKEN_PICKLE, 'wb') as token:
            pickle.dump(creds, token)
    service = build(service_name, service_version, credentials=creds, cache=MemoryCache())
    return service



# FILES
################################################################################

FOLDER_MIMETYPE = 'application/vnd.google-apps.folder'
DEFAULT_FILE_FIELDS = 'id,kind,name,mimeType,version,webViewLink,createdTime,modifiedTime'
FORBIDDEN_CHARS_IN_FOLDER_NAMES = ['/', ':']  # will be replaced with underscore

def itercontents(drive, folder_id, order_by='folder,name', file_fields=DEFAULT_FILE_FIELDS):
    """
    Go through all the contents of the Googgle Drive folder `folder_id` and return
    the info requested in `file_fields` for each file (or folder) found.
    """
    fields = 'nextPageToken, files({})'.format(file_fields)
    params = {
        'q': "'"+folder_id+"' in parents",
        'pageToken': None,
        'orderBy': order_by,
        'fields': fields,
    }
    while True:
        response = drive.files().list(**params).execute()
        for file in response['files']:
            yield file
        if 'nextPageToken' in response:
            params['pageToken'] = response['nextPageToken']
        else:
            break


def list_folder(folder_id):
    """
    Non-recursive list of contents of `folder_id`.
    """
    drive = get_service(service_name='drive', service_version='v3')
    from pprint import pprint
    for item in itercontents(drive, folder_id):
        pprint(item)


def _clean_folder_name(name):
    """Remove forbidden chars from folder name and strip any whitespace."""
    for char in FORBIDDEN_CHARS_IN_FOLDER_NAMES:
        name = name.replace(char, '_')
    name = name.strip()
    return name


def gdrive_walk(folder_id, file_fields=DEFAULT_FILE_FIELDS, drive=None):
    """
    Returns a `os.walk`-like (path, dirs, files) triples for all descendants of
    `folder_id`. Each dict in the list `files` has attributes in `file_fields`.
    """
    if drive is None:
        drive = get_service(service_name='drive', service_version='v3')

    # get the file root
    root_data = drive.files().get(fileId=folder_id, fields=file_fields).execute()
    assert root_data['mimeType'] == FOLDER_MIMETYPE, 'must start walk at folder'
    assert root_data['id'] == folder_id, 'wrong folder returned'

    # recursively walk tree, keeping track of current position using a stack that
    # stores (path_tuple, folder_id) of next folder to talk
    root_name = _clean_folder_name(root_data['name'])
    stack = [ ((root_name,), folder_id) ]
    while stack:
        path, folder_id = stack.pop()
        dirnames, files = [], []
        for item in itercontents(drive, folder_id, file_fields=file_fields):
            if item['mimeType'] == FOLDER_MIMETYPE:
                dirname = _clean_folder_name(item['name'])
                dirnames.append(dirname)
                item_path = path + (dirname,)
                stack.append( (item_path, item['id']) )
            else:
                files.append(item)
        yield '/'.join(path), dirnames, files


def gdrive_download_file(file_id, destpath, drive=None):
    """
    Download the file `file_id` to local path `destdir/destfilename`.
    """
    if drive is None:
        drive = get_service(service_name='drive', service_version='v3')

    request = drive.files().get_media(fileId=file_id)
    try:
        # print("\tDownloading file - {}".format(destpath))
        fh = io.FileIO(destpath, mode='wb')
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
    except Exception as e:
        print("\tThere was an error while downloding {}".format(file_id))
        print(e)
        return None



# EXPORT
################################################################################

EXPORTED_DIRNAME = 'Exported'

def get_exported_dir(lang, kind):
    """
    Get the local path to the Exported directory for `lang`.
    if kind==courses:       `chefdata/Exported/{lang}/{Language}`
    if kind==activityfiles: `chefdata/Exported/{lang}/{Language} - Activity Files`
    """
    assert kind in ['courses', 'activityfiles']
    exportdir = os.path.join('chefdata', EXPORTED_DIRNAME, lang)
    data_sources = json.load(open('chefdata/data_sources.json'))
    lang_data_sources = data_sources[lang]
    dirname = lang_data_sources[kind]['name']
    srcdir = os.path.join(exportdir, dirname)
    return srcdir


def export_folder(folder_id, parentdir='', drive=None):
    if not os.path.exists(parentdir):
        os.makedirs(parentdir)
    
    for path, _dirs, files in gdrive_walk(folder_id):
        destdir = os.path.join(parentdir, path)
        print('exporting', len(files), 'files to', destdir)

        if not os.path.exists(destdir):
            os.makedirs(destdir)

        for file in files:
            file_id = file['id']
            filaname = file['name']
            destpath = os.path.join(destdir, filaname)
            if not os.path.exists(destpath):
                gdrive_download_file(file_id, destpath, drive=drive)
            else:
                pass
                # print('skipping download of', destpath, 'since it already exists.')


def export(lang='all'):
    from sushichef import HPLIFE_LANGS
    assert lang == 'all' or lang in HPLIFE_LANGS, 'unexpected lang'
    if lang == 'all':
        langs = HPLIFE_LANGS
    else:
        langs =[lang]

    drive = get_service(service_name='drive', service_version='v3')

    exportdir = os.path.join('chefdata', EXPORTED_DIRNAME)
    data_sources = json.load(open('chefdata/data_sources.json'))

    for lang in langs:
        lang_data_sources = data_sources[lang]
        langdir = os.path.join(exportdir, lang)
        if not os.path.exists(langdir):
            print('Creating export dir parent', langdir)
            os.makedirs(langdir)

        # export courses (tar-gzipped XML files stored in a compressed .gz)
        courses = lang_data_sources['courses']
        export_folder(courses['folder_id'], parentdir=langdir, drive=drive)

        # export course activity files
        content = lang_data_sources['activityfiles']
        export_folder(content['folder_id'], parentdir=langdir, drive=drive)















# RENAME + STANDARDIZE
################################################################################

RENAMED_DIRNAME = 'Renamed'

def get_renamed_dir(lang, kind):
    """
    Get the local path to the Renamed directory for `lang`.
    if kind==courses:       `chefdata/Renamed/{lang}/{Language}`
    if kind==activityfiles: `chefdata/Renamed/{lang}/{Language} - Activity Files`
    """
    assert kind in ['courses', 'activityfiles']
    renameddir = os.path.join('chefdata', RENAMED_DIRNAME, lang)
    data_sources = json.load(open('chefdata/data_sources.json'))
    lang_data_sources = data_sources[lang]
    dirname = lang_data_sources[kind]['name']
    srcdir = os.path.join(renameddir, dirname)
    if not os.path.exists(srcdir):
        os.makedirs(srcdir)
    return srcdir


def _strip_course_number(name):
    """
    Removes the prefix of the form HPL-FR33 followed by : _ or space.
    """
    couse_number_pat = re.compile('HPL-..\d\d[: _-]')
    m = couse_number_pat.search(name)
    if m:
        clean_name = couse_number_pat.sub('', name)
        return clean_name
    else:
        return name


def _normalize_course_name(course_name):
    """
    Do name normalization to fix non-standard names containing _ and :
    """
    HPLIFE_COURSE_FOLDER_RENAMES = {
        'Energy efficiency_ Do more for less': 'Energy efficiency - Do more for less',
        'Eficiencia de la energía hacer más con menos': 'Eficiencia de la energía - hacer más con menos',
        'Eficiencia de la energía_ hacer más con menos': 'Eficiencia de la energía - hacer más con menos',
        'Efficacité énergétique Faire davantage avec moins': 'Efficacité énergétique - Faire davantage avec moins',
        'Efficacité énergétique _ Faire davantage avec moins': 'Efficacité énergétique - Faire davantage avec moins',
        'ऊर्जा कार्यक्षमता_ कम में ज़्यादा करें': 'ऊर्जा कार्यक्षमता- कम में ज़्यादा करें',
        '3D प्रिंटिंग.FDwab0': '3D प्रिंटिंग',
        'व्यावसायिक ईमेल': 'वयावसायिक ईमेल',
    }
    for source_str, replacement_str in HPLIFE_COURSE_FOLDER_RENAMES.items():
        if source_str in course_name:
            course_name = course_name.replace(source_str, replacement_str)
            print('Did normalization edit on course_name', course_name)
    return course_name


def rename_courses(lang):
    """
    Standardize on course names that have : or '  ' in them.
    """
    # source directory = `chefdata/Export/{lang}/{Language}/`
    srcdir = get_exported_dir(lang, 'courses')
    for filename in os.listdir(srcdir):
        if filename in FILES_TO_SKIP:
            continue
        srcpath = os.path.join(srcdir, filename)
        #
        # Case A. Handle special course folder case
        if os.path.isdir(srcpath):
            print('Found course dir', srcpath)
            course_name = _strip_course_number(filename)
            childfilenames = os.listdir(srcpath)
            assert len(childfilenames) == 1, 'errror multiple archives found in ' + srcpath
            childfilename = childfilenames[0]
            srcpath = os.path.join(srcdir, filename, childfilename)
        #
        # Case B: handle normaal case where course is a .gz or .tar.gz file
        else:
            course_name = _strip_course_number(filename)
            if course_name.endswith('.tar.gz'):
                course_name = course_name.replace('.tar.gz', '')
            elif course_name.endswith('.gz'):
                course_name = course_name.replace('.gz', '')
            else:
                print('unexpected filename', filename)
        #
        course_name = _normalize_course_name(course_name)
        #
        # dest
        # dest directory = `chefdata/Renamed/{lang}/{Language}/`
        
        destdir = get_renamed_dir(lang, 'courses')
        destpath = os.path.join(destdir, course_name + '.tar.gz')
        #
        # do copy
        shutil.copy(srcpath, destpath)
        print('Copied course', filename, 'to', destpath)


def rename_activity_files(lang):
    # source directory = chefdata/Export/{lang}/{Language} - Activity Files/
    srcdir = get_exported_dir(lang, 'activityfiles')
    # dest directory = chefdata/Renamed/{lang}/{Language} - Activity Files/
    destdir = get_renamed_dir(lang, 'activityfiles')
    # rename activity folders
    for filename in os.listdir(srcdir):
        if filename in FILES_TO_SKIP:
            continue
        srcpath = os.path.join(srcdir, filename)
        course_name = _normalize_course_name(filename)
        destpath = os.path.join(destdir, course_name)
        shutil.copytree(srcpath, destpath)





# EXTRACT
################################################################################

EXTRACT_DIRNAME = 'Courses'
FILES_TO_SKIP = [
    '.DS_Store', 'Thumbs.db', 'ehthumbs.db', 'ehthumbs_vista.db', '.gitkeep',
    'CRM-Tracking-spreadsheet-PT-BR (6).xlsx',
    'Creating-Customer-Loyalty-PT (4).docx',
    'Creating-a-Communication-Plan-PT (4).docx',
    'Developing-a-Communication-Strategy-PT (4).doc',
    'crm_portuguese.jpg',
    'Developing-a-Communication-Strategy-PT (4).doc',
]


def extract_courses(lang):
    """
    Extract all the `.gz`s from `chefdata/Renamed/{lang}/{Langname}/{course_name}.gz`
    to `chefdata/Courses/{lang}/{course_name}/course`.
    Returns course_names = list of course names encountered.
    """
    course_names = []
    # src
    srcdir = get_renamed_dir(lang, 'courses')
    # dest
    extractdir = os.path.join('chefdata', EXTRACT_DIRNAME, lang)
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
            if not os.path.exists(os.path.join(destdir, 'course')):
                print('Untargzipping course', course_name, 'from', gzpath, 'to', destdir)
                shutil.unpack_archive(gzpath, destdir, 'gztar')
            course_names.append(course_name)
        else:
            print('skipping non-gz file', filename)

    return course_names


def process_content_for_course(lang, course_name):
    """
    Copy over all resource folders `chedata/Renamed/{lang}/{Langname} - Activity Files/{course_name}/{srcfolder}`
    to `chefdata/Courses/{lang}/{course_name}/content/{srcfolder.replace(' - Storyline output','')}`
    Returns `activity_refs` (list) for resource folder names copied over.
    """
    activity_refs = []

    # src
    srcdir = get_renamed_dir(lang, 'activityfiles')
    coursedir = os.path.join(srcdir, course_name)
    # print('coursedir=', coursedir)
    if not os.path.exists(coursedir):
        print('Could not find Activity-Files for course_name', course_name)
        return []

    # dest
    extractdir = os.path.join('chefdata', EXTRACT_DIRNAME, lang)
    contentdir = os.path.join(extractdir, course_name, 'content')

    for srcfolder in os.listdir(coursedir):
        # src
        if srcfolder in FILES_TO_SKIP:
            continue
        srcpath = os.path.join(coursedir, srcfolder)

        # dest
        activity_ref = srcfolder
        # print('          > Processing activity_ref', activity_ref)
        resource_folder = os.path.join(contentdir, activity_ref)
        if not os.path.exists(resource_folder):
            shutil.copytree(srcpath, resource_folder)
        activity_refs.append(activity_ref)

    return activity_refs


def extract(lang):
    print('Extracting lang', lang)
    course_names = extract_courses(lang)
    print('\textracting course_names', course_names)

    course_list = {
        "title": "HP LIFE ({})".format(lang),
        "kind": "HP LIFE couses listing",
        "courses": []
    }
    for course_name in course_names:
        activity_refs = process_content_for_course(lang, course_name)
        if activity_refs:
            print('\tCourse course_name=', course_name, '  activity refs=', activity_refs)
            course_info = {
              "name": course_name,
              "path": course_name,
              "lang": lang,
            }
            course_list['courses'].append(course_info)

        else:
            print('\tno activity_refs for course_name', course_name)

    containerdir = os.path.join('chefdata', EXTRACT_DIRNAME, lang)
    couse_list_path = os.path.join(containerdir, 'course_list.json')
    with open(couse_list_path, 'w') as couse_list_file:
        json.dump(course_list, couse_list_file, indent=4, ensure_ascii=False)



# CLI (for testing)
################################################################################

if __name__ == '__main__':
    from sushichef import HPLIFE_LANGS
    for lang in HPLIFE_LANGS:
        export(lang=lang)
        rename_courses(lang=lang)
        rename_activity_files(lang=lang)
        extract(lang=lang)
