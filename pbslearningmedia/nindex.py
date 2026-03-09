
# query, start
TEMPLATE_URL = "https://ca.pbslearningmedia.org/api/v2/search/?q={query}&start={start}&facet_by=grades,subject,media_type,language,accessibility,additional_features&facet_operator=subject:and&facet_operator=standard:and&facet_operator=language:and&facet_operator=accessibility:and&facet_operator=additional_features:and"

TEMPLATE_URL = "https://ca.pbslearningmedia.org/api/v2/search/?q={query}&start={start}"
import requests

r = requests.get(TEMPLATE_URL.format(query="human", start=10))  # increment start in 10s
#print (r.json()['objects'])
#print (r.json()['meta']['next_uri'])


#print (r.json()['objects'][0].keys())
#['type', 'uri', 'lo_id', 'guid', 'media_type', 'scope', 'feature_image', 'additional_features', 'poster_images', 'grade_ranges', 'duration', 'description', 'brand', 'title', 'canonical_url', 'grades'])

o = r.json()['objects'][0]
for k in o.keys():
    print(k, o[k])
print (r.json()['meta']['total'])

"""
scope []
canonical_url https://www.pbslearningmedia.org/resource/tdc02.sci.life.cell.humcloning/on-human-cloning/
grade_ranges 9-12
grades ['9', '10', '11', '12']
lo_id r48bbf9ba-563d-4852-8b7c-0c74acee3b70
duration 
feature_image None
additional_features ['Support Materials']
brand NOVA
type simple
guid 48bbf9ba-563d-4852-8b7c-0c74acee3b70
poster_images [{'url': 'https://image.pbs.org/poster_images/assets/tdc02_doc_humcloning_thumb1.jpg.resize.710x399.jpg', 'type': 'default', 'alt_text': 'On Human Cloning'}, {'url': 'https://image.pbs.org/poster_images/assets/tdc02_doc_humcloning_thumb1.jpg', 'type': 'original', 'alt_text': 'On Human Cloning'}]
uri https://ca.pbslearningmedia.org/api/v2/lo/r48bbf9ba-563d-4852-8b7c-0c74acee3b70/
description <p>blah blah blah <em>NOVA: 18 Ways to Make a Baby.</em></p>
title On Human Cloning
media_type ['Document']
"""


