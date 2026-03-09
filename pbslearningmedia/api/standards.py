import requests

standard_stub = "https://ca.pbslearningmedia.org/api/v2/lo/standards/r/"
sample_canon_url = "https://www.pbslearningmedia.org/resource/6b881a3e-8dcc-41ec-9856-fb36cd019d45/13-ambassadors-and-11-ceos-gather-at-modernized-ait-library-inauguration/"

def canonical_to_standards(url):
    assert "resource/" in url, url
    last = url.partition("resource/")[2]
    return standard_stub + last.split("/")[0]

def get_standards(canon_url):
    url = canonical_to_standards(canon_url)
    j=requests.get(url).json()
    nums = []
    for standard_class in j['standards']['national']:
        if standard_class == "College and Career Readiness Standards for Adult Education":
            continue
        nums.extend([standard['num'] for standard in j['standards']['national'][standard_class]])
    return nums
    

