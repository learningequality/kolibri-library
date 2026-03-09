urls = ["https://ca.pbslearningmedia.org/api/v2/lo/r/march-pbs-newshour/",
        "https://ca.pbslearningmedia.org/api/v2/lo/r/8a4d516a-19b6-4eed-ab30-12c41b728029/",]

import requests
import add_file
from foundry import foundry
import download

class HTMLFoundry(foundry.Foundry):
    def melt(self):
        self.raw_content = self.params['html'].encode('utf-8')

def get_support_nodes(url=None, detail=None, **kwargs):
    if url and "data:" in url:
        return []
    if url:
        detail = requests.get(url).json()
    else:
        url = detail['canonical_url']

    print ("*")
    for i, support in enumerate(detail.get('support_materials', [])):
        if support['media_type'] == "HTMLFragment":


            f = HTMLFoundry(url=url+"#"+str(i),
                            params={"html": support['media'][0]['content']},
                            centrifuge_callback = lambda x: x)
            node = f.node()
            node.title=support['title']
            for arg in kwargs:
                setattr(node, arg, kwargs[arg])
            #node.license = template_node.license
            #node.copyright_holder = template_node.copyright_holder
            #node.author = template_node.author
            yield node
        else:
            try:
                node, _ = download.download_something(
                                 canonical_url=support['canonical_url'],
                                 title=support['title'],          
                                 **kwargs)
            except download.Skip:
                continue
            yield node
        # if media_type is 'HTMLFragment', take media[0]['content'] as a HTML5App
        #support_node, support_medium = download.download_something(
        #    canonical_url=resource_url,
        #    title=support['title'],
        #    license=licence_lookup[index['detail']['use_rights']],
        #    copyright_holder=copyright_string,
        #    author = author_string,
        #    description="",
        #)
                                                        
if __name__ == "__main__":
    for i, url in enumerate(urls):
        print (list(get_support_nodes(url)))

