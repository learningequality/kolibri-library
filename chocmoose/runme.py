import json
import os
import zipfile


data_filename = 'chocmoose_videos_data.json'
data_zip_filename = 'chocmoose_videos_data.json' + '.zip'

if not os.path.exists(data_filename):
    if os.path.exists(data_zip_filename):
        with zipfile.ZipFile(data_zip_filename) as zip_file:
            zip_file.extractall(".")
            print('Extracted', data_zip_filename, 'to', data_filename)
            assert os.path.exists(data_filename), 'extracting zip problem'
    else:
        print(data_zip_filename, 'not found')

with open(data_filename) as data_file:
    projects_tree = json.load(data_file)


for project_name, project_dict in projects_tree.items():
    print(project_name, '(Project)')
    for proj_language in project_dict['children']:
        print('   - ', proj_language['name'], 'lang_tag=', proj_language['lang_tag'], 'le_code=', proj_language['le_code'])
        for video in proj_language['children']:
            print('        ', video['title'], video['webpage_url'])


