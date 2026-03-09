import json
import pickle
from collections import Counter
js = []
done = set()
tagcounter =Counter()
with open("full.jsonlines") as f:
    ls = f.readlines()
    for i, l in enumerate(ls):
        j = json.loads(l)
        # skip ones we don't have rights for
        # also skips nulls!
        if 'use_rights' not in j['detail'].keys():
            continue
        use = j['detail']['use_rights']
        if not use or "Share" not in use:
            continue
        medias = j['index']['media_type']
        tags = j['tags'].values()
        title = j['index']['canonical_url']
        if title in done:
            continue
        else:
            for tag in tags:
                for media in medias:
                    tagcounter[media+":"+tag] += 1


with open("tags.py", "w") as f:
    f.write("from collections import Counter\ntags = ")
    f.write(str(tagcounter))
print (tagcounter)
print (len(l))
