import pickle
import os
import pprint
import re
import le_utils
import json
import pathlib
import pkgutil 
import itertools
from operator import itemgetter

from le_utils.constants.languages import getlang, _LANGLOOKUP, getlang_by_name




if not os.path.exists('chocmoose_info.pickle'):
    print("error, missing chocmoose_info.pickle, please download and unzip in current dir.")

with open('chocmoose_info.pickle', 'rb') as handle:
    info = pickle.load(handle)

# non-entries keys
keys = ['extractor', 'extractor_key', 'title', '_type', 'webpage_url', 'id', 'webpage_url_basename']
for key in keys:
    print(key, ':', info[key])
            
# number of entries
print("\n\nlen(info['entries']) = ", len(info['entries']) )

# sample entry
projects =  [
        { 'pattern': re.compile('.*[EÉI|Ȧŋi]bola.*'),
          'section': "Ebola A Poem For The Living" },
        { 'pattern': re.compile('.*Solar [Campaign|Camgian].*'),
          'section': "Solar Campaign promoting solar lights" },
        { 'pattern': re.compile('.*No Excuses.*', re.I),
          'section': "No Excuses domestic violence prevention" },
        { 'pattern': re.compile('.*Preventing.*', re.I),
          'section': "No Excuses domestic violence prevention" },
        { 'pattern': re.compile('.*buzz-and-bite.*'),
          'section': "Buzz and Bite malaria prevention" },
        { 'pattern': re.compile('.*the-three-amigos.*'),
          'section': "Three Amigos HIV/AIDS prevention" },
        { 'pattern': re.compile('.*Values-.*'),
          'section': "Values For Young Children" },
        { 'pattern': re.compile('.*Zika Prevention.*'),
          'section': "Zika Prevention" },
        { 'pattern': re.compile('.*The Switch Animation.*'),
          'section': "The Switch Animation"},
        { 'pattern': re.compile('.*The Migrant.*'),
          'section': "The Migrant"},
        { 'pattern': re.compile('.*Spot.*'),
          'section': "Rashid Living With Type 1 Diabetes"},
        { 'pattern': re.compile('.*Asbestos.*'),
          'section': "Asbestos"},
        { 'pattern': re.compile('.*Rape Victims.*', re.I),
          'section': "Rape Victims"},
        { 'pattern': re.compile('.*Congo.*', re.I),
          'section': "Rape Victims"},
        { 'pattern': re.compile('.*Coming Together.*'),
          'section': "Coming Together"},
        { 'pattern': re.compile('.*N4A.*'),
          'section': "Nature for All"},
        { 'pattern': re.compile('.*Show You Care, Wear A Pair.*'),
          'section': "Show You Care - Wear A Pair"},
        { 'pattern': re.compile('.*Malawi.*'),
          'section': "Violence Against Children in Malawi"},
        { 'pattern': re.compile('.*Cartoons for Children.*'),
          'section': "Cartoons For Children's Rights"},
        { 'pattern': re.compile('.*Nature For All.*'),
          'section': "Nature for All"},
        { 'pattern': re.compile('.*Biodiver.*'),
          'section': "Biodiversity Is Us"},
        { 'pattern': re.compile('.*cyber-security.*'),
          'section': "UNICEF Cyber Security"},
        { 'pattern': re.compile('.*Preventing.*'),
          'section': "Preventing Violence"},
        { 'pattern': re.compile('.*The Power of Animation.*'),
          'section': "The Power of Animation and Humour"},
        ] 

# TODO: This could be replaced with a more generic solution using: iso369 library
LANGS_LOOKUP = [
        { 'pattern': re.compile('.*Mandarin.*'),
          'lang': 'zh'  },
        { 'pattern': re.compile('.*Greek.*'),
          'lang': 'el'  },
        { 'pattern': re.compile('.*Creole.*'),
          'lang': 'ht'  },
        { 'pattern': re.compile('.*Romanian.*'),
          'lang': 'ro'  },
        { 'pattern': re.compile('.*Sotho.*'),
          'lang': 'st'  },
        # From this: https://en.wikipedia.org/wiki/Krio_language
        { 'pattern': re.compile('.*Krio.*'),
          'lang': 'kri'  },
        { 'pattern': re.compile('.*Themne.*'),
          'lang': 'tem'  },
        { 'pattern': re.compile('.*Susu.*'),
          'lang': 'sus'  },
        { 'pattern': re.compile('.*Maninka.*'),
          'lang': 'emk'  },
        { 'pattern': re.compile('.*Mende.*'),
          'lang': 'men'  },
        { 'pattern': re.compile('.*Otetela.*'),
          'lang': 'tll'  },
        { 'pattern': re.compile('.*Mashi.*'),
          'lang': 'mho'  },
        { 'pattern': re.compile('.*Tshiluba.*'),
          'lang': 'lua'  },
        { 'pattern': re.compile('.*Francais.*'),
          'lang': 'fr'  },
        # Note: Just defined by project name  not because the language
        { 'pattern': re.compile('.*Solar.*'),
          'lang': 'en'  },
        { 'pattern': re.compile('.*Preventing.*'),
          'lang': 'en'  },
        { 'pattern': re.compile('.*Cartoons for Children.*'),
          'lang': "en"},
        { 'pattern': re.compile('.*Values-.*'),
          'lang': "en" },
        { 'pattern': re.compile('.*Éloge de la prévention.*'),
          'lang': 'fr'  },
        { 'pattern': re.compile('.*In Praise of Prevention.*'),
          'lang': 'en'  },
        { 'pattern': re.compile('.*Coming Together.*'),
          'lang': 'es'  },
        { 'pattern': re.compile('.*The Migrant.*'),
          'lang': 'en'  },
        { 'pattern': re.compile('.*Show You Care, Wear A Pair.*'),
          'lang': "en"},
        { 'pattern': re.compile('.*The Power of Animation.*'),
          'lang': "en"},
        # Typos
        { 'pattern': re.compile('.*Pigin.*'),
          'lang': 'pcm'  },
        { 'pattern': re.compile('.*Portugese.*'),
          'lang': 'pt'  },
        { 'pattern': re.compile('.*Enlgish.*'),
          'lang': 'en'  },
        ]

langlist = json.loads(pkgutil.get_data('le_utils', 'resources/languagelookup.json').decode('utf-8'))

def section_from_title(title):
    for project in projects:
        if project['pattern'].match(title):
            return project['section'] 

def lang_from_video(vid):
    for k, v in langlist.items():  
        names = v['name'].split(';')
        for name in names:
          if name in vid['title']:
            return k 
        native_names = v['native_name'].split(',')
        for native_name in native_names:
          if native_name and (native_name in vid['title']):
            return k 

def manual_lang_tag_from_video(vid):
    for language in LANGS_LOOKUP:
        if language['pattern'].match(vid['title']):
            return language['lang'] 


def video_from_url(url):
    return list(filter(lambda video: video['webpage_url'] == url, info['entries']))[0]

# Assign section for the video
for vid in info['entries']:
    vid['project_name'] = section_from_title(vid['title'])

# Look for video without project/section 
remaining = 0
for vid in info['entries']:
    project = vid['project_name']
    if not project: 
        remaining += 1
        print(vid['webpage_url'])
        print(vid['title'],'\033[91m', vid['project_name'], '\033[0m')

# print("Remaining videos:", remaining)

# Assign language tag for video
# If it can be assigned directly, it should be used "the manual way"
for vid in info['entries']:
    vid['lang_tag'] = lang_from_video(vid)
    if not vid['lang_tag']:
       vid['lang_tag'] = manual_lang_tag_from_video(vid)

# Look for video without language assigned
remaining = 0
for vid in info['entries']:
    lang = vid['lang_tag']
    if not lang: 
        remaining += 1
        print(vid['webpage_url'])
        print(vid['title'],'\033[91m', vid['project_name'], '\033[0m')

# print("Remaining videos without language:", remaining)

def match_video(vid1, vid2):
    if vid1.lower() == vid2.lower():
        return True
    if ''.join(vid1.lower().split()) == ''.join(vid2.lower().split()):
        return True
    if ''.join(vid1.lower().split()).replace(" ","") == ''.join(vid2.lower().split()).replace(" ", ""):
        return True
    return False
    
# Search repeated videos based on title
# If the video is "unique" the repeated url-videos would be on 'repeated' key 
for index, vid in enumerate(info['entries']):
    vid['repeated'] = set()
    vid['repeated'].add(vid['webpage_url'])
    if vid.get('marked'):
        continue
    repeated = 0 
    for index2, vid2 in enumerate(info['entries']): 
        # TODO: Improve the way to select duplicated files
        # Currently: if title is the same and the url is different
        if match_video(vid['title'], vid2['title']) and (vid['webpage_url'].strip() != vid2['webpage_url'].strip()): 
            vid2['marked'] = True
            vid['repeated'].add(vid2['webpage_url'])
            repeated += 1


# Count unique elements
counter = 0
for vid in info['entries']:
    if not vid.get('marked'):
        counter += 1

print(counter, 'unique elements')

def highest_resolution_from_video(vid):
    highest_resolution = 0
    for f in vid['formats']:
        if 'http' in f['format_id']:
            resolution = int(re.findall('\d+',f['format_id'])[0])
            if resolution > highest_resolution:
               highest_resolution = resolution
    return highest_resolution


# Select the highest resolution
for vid in info['entries']:
    if not vid.get('marked'):
       # print("Video:", vid['title'], " |  Repeated: ", len(vid['repeated']),"times")
        max_resolution = 0
        max_resolution_video = None
        for url in vid.get('repeated'):
            vid2 = video_from_url(url)
            resolution = highest_resolution_from_video(vid2)
            if resolution > max_resolution:
                max_resolution_video = vid2
                max_resolution = resolution
            elif resolution == max_resolution:
                if vid2['timestamp'] > max_resolution_video['timestamp']:
                  max_resolution_video = vid2
                  max_resolution = resolution
        vid['max_resolution_url'] =  max_resolution_video['webpage_url']

projects = dict()
for vid in info['entries']:
    if not vid.get('marked'):
        if not projects.get(vid.get('project_name')):
            projects[vid.get('project_name')] = dict()
        if not projects[vid.get('project_name')].get(vid.get('lang_tag')):
            projects[vid.get('project_name')][vid.get('lang_tag')] = { 'number': 0, 'videos': [ ] }  
        projects[vid.get('project_name')][vid.get('lang_tag')]['number'] += 1
        projects[vid.get('project_name')][vid.get('lang_tag')]['videos'].append(vid) 


# Print counts
for project, values in projects.items():
    print(project)
    for lang, info in values.items(): 
        print("\t", lang, " - ", info['number'])
        #for vid in info['videos']:
        #   print("\t", vid.get('title'))


# Replaced with printing during Export as JSON
# # Print tree
# for project, values in projects.items():
#     print('')
#     print(project)
#     for lang, info in values.items():
#         print('   - ', lang, info['number'])
#         for vid in info['videos']:
#             print('        ', vid['title'], vid['webpage_url'])




# Language helper
################################################################################
lang_tag_to_lang_dict = {}

for le_code, lang_obj in _LANGLOOKUP.items():
    lang_tag_to_lang_dict[le_code] = dict(
        lang_tag=le_code,
        name=lang_obj.name.split(';')[0],
        le_code=le_code,        
    )


for item in LANGS_LOOKUP:
    lang_tag = item['lang']
    name = repr(item['pattern']).replace("re.compile('.*", "").replace(".*')", "")
    lang_obj = getlang(lang_tag)
    if lang_obj is None:
        lang_obj = getlang_by_name(name)

    lang_tag_to_lang_dict[lang_tag] = dict(
        lang_tag=lang_tag,
        name=name,
        le_code=lang_obj.code if lang_obj else None,        
    )
    


# Export as JSON
################################################################################

projects_tree = {}

for project_name, project_langs in projects.items():
    print('building subtree for ', project_name)
    project_dict = dict(
        project_name=project_name,
        children=[],
    )
    projects_tree[project_name] = project_dict
    for lang_tag, langinfo in project_langs.items():
        print('   - ', lang_tag, langinfo['number'])
        lang_dict = lang_tag_to_lang_dict[lang_tag]
        this_lang_dict = lang_dict.copy()
        this_lang_dict['children'] = []
        project_dict['children'].append(this_lang_dict)        
        for vid in langinfo['videos']:
            print('        ', vid['title'], vid['webpage_url'])
            this_lang_dict['children'].append(vid)

print('Created projects_tree')


# Save tree as JSON
class SetEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, set):
            return list(obj)
        return json.JSONEncoder.default(self, obj)

with open('chocmoose_videos_data.json', 'w', encoding='utf8') as json_file:
    json.dump(projects_tree, json_file, cls=SetEncoder, indent=4, ensure_ascii=False)


print('Saved projects_tree to chocmoose_videos_data.json')







# Category B project helpers --- single video available in multiple languages

# def all_with_one_video(values):
#     for lang, info in values:
#         if not info['number'] == 1:
#             return False
#     return True

# def category_b(project, values):
#     pathlib.Path(os.path.join("ChocMoose",project)).mkdir(parents=True, exist_ok=True) 
#     for lang, info in values.items():
#       for vid in info['videos']:
#           open(os.path.join("ChocMoose", project,vid['title']), 'a').close()
    # if len(values.keys()) == 1:
    #     category_b(project, values)
    # elif all_with_one_video(values.items()):
    #     category_b(project, values)
    # else:
    #     print("Category A")


#sorted_by_language = sorted(info['entries'], key=itemgetter('lang_tag'))
#for key, value in itertools.groupby(sorted_by_language, key=itemgetter('lang_tag')):
#    print(key)
#    for i in value:
#        print("\t", i.get('title'))

#sorted_by_lang = sorted(info['entries'], key=itemgetter('lang_tag'))
#  