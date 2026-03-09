import json
import requests
import requests_cache

requests_cache.install_cache()

SUBJECTS = [2663,6267,6708,2949,8353,2806,1880,1184,3026,8337]
#MEDIA = ["Collection", "Video", "Interactive Lesson", "Interactive", "Lesson Plan",
#         "Media Gallery", "Audio", "Image", "Webpage", "Document", "Teacher-Built"]
MEDIA = ["Video", "Interactive Lesson", "Interactive", "Lesson Plan",
         "Media Gallery", "Audio", "Image", "Webpage", "Document", "Teacher-Built"]

INDEX_URL = "https://ca.pbslearningmedia.org/api/v2/search/?q={query}&selected_facet=subject:{subject}&selected_facet=media_type:{media}&start=0"
DETAIL_URL = "https://ca.pbslearningmedia.org/api/v2/lo/r/{name}/"

def retry_get(url):
    while True:
        try:
            return requests.get(url)
        except Exception as e:
            print (e, url)

def get_index(query,subject,media):
    #print (r.json()['objects'][0].keys())
    #['type', 'uri', 'lo_id', 'guid', 'media_type', 'scope', 'feature_image', 'additional_features', 'poster_images', 'grade_ranges', 'duration', 'description', 'brand', 'title', 'canonical_url', 'grades'])
    r = retry_get(INDEX_URL.format(query=query, subject=subject, media=media))
    print (r.json()['meta']['total'])
    while True:
        for index_obj in r.json()['objects']:
            yield index_obj
        next_uri = r.json()['meta']['next_uri']
        print (next_uri, len(r.json()['objects']))
        if next_uri:
            r = requests.get(next_uri)
        else:
            break

def parse_tags(detail_obj):
    curriculum_tags = {}
    if "curriculum_tags" not in detail_obj:
        return {}
    for tag in detail_obj['curriculum_tags']:
        curriculum_tags[tag['name']] = tag['slug']
    return curriculum_tags

def get_detail_page(index_object):
    canonical_name = index_object['canonical_url'].split("/")[4]
    r = retry_get(DETAIL_URL.format(name=canonical_name))
    detail_obj = r.json()
    return detail_obj, parse_tags(detail_obj)


with open("full.jsonlines", "w") as f:
    for subject in SUBJECTS:
        for media in MEDIA:
            try:
                for i, index_object in enumerate(get_index("", subject, media)):
                    print (subject, i)
                    detail_object, tags = get_detail_page(index_object)
                    j = json.dumps({"index": index_object, "detail": detail_object, "tags": tags})
                    f.write(j)
                    f.write("\n")
            except Exception as e:
                print (e)
                pass
