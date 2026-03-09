# coding: utf-8
import requests
import json
from le_utils.constants.languages import getlang

BASE_URL = "https://phet-api.colorado.edu"
req = requests.get(f"{BASE_URL}/partner-services/2.0/metadata/simulations")
locales = json.loads(req.text).get("locales")

def getlangs(code):
    """
    Just... tries a few ways to get a match based on things that worked for a few codes
    while I tried things with getlang in the repl.
    """
    lang = getlang(code)
    if not lang:
        lang = getlang(code.replace('_', '-'))
    if not lang:
        lang = getlang(code.lower())
    if not lang:
        lang = getlang(code.lower().replace('_', '-'))
    return lang


matched = set()
unmatched = set()
mapped = dict()

for code in locales:
    x = getlangs(code)
    if x:
        matched.add(code)
        mapped[x.primary_code] = code
    else:
        unmatched.add(code)

with open('kolibri_to_phet_lang_map.json', 'w') as f:
    f.write(json.dumps(mapped, indent=4))
    f.close()
    print("Mapping written to kolibri_to_phet_lang_map.json")

print(f"The following codes were not matched to a supported Kolibri language: {unmatched}")

