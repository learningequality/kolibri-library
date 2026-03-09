#!/usr/bin/env python
import os
import sys
sys.path.append(os.getcwd()) # Handle relative imports
from urllib.parse import urljoin
import logging
from ricecooker.chefs import SushiChef
from ricecooker.classes.licenses import get_license
from ricecooker.classes.nodes import HTML5AppNode, TopicNode
from ricecooker.classes.files import HTMLZipFile
import index
import handle_zip
from mangled import replace
LOGGER = logging.getLogger()
LICENCE=get_license('CC BY-SA', copyright_holder='Centro Nacional de Desarrollo Curricular en Sistemas no Propietarios.')

class CedecChef(SushiChef):
    channel_info = {
        'CHANNEL_SOURCE_DOMAIN': 'cedec.intef.es', # who is providing the content (e.g. learningequality.org)
        'CHANNEL_SOURCE_ID': 'cedec',         # channel's unique id
        'CHANNEL_TITLE': 'Cedec',
        'CHANNEL_LANGUAGE': 'es',                          # Use language codes from le_utils
#        'CHANNEL_THUMBNAIL': 'https://files.constantcontact.com/02b8739a001/91725ebd-c07b-4629-8b55-f91fd79919db.jpg',
        'CHANNEL_DESCRIPTION': "Recursos educativos abiertos: Consulta, aplica, modifica, comparte" # description of the channel (optional)
    }

    def construct_channel(self, **kwargs):
        channel = self.get_channel(**kwargs)
        old_title = None
        old_group = None
        i=0

        for metadata, zfilename, [title, group] in index.no_dl_index():
            i = i + 1
            if title != old_title:
                old_title=title
                title_node = TopicNode(source_id=title+str(i), title=replace(title))
                channel.add_child(title_node)
                old_group = None
            if group != old_group:
                old_group = group
                group_node = TopicNode(source_id=title+group+str(i+0.5), title=replace(group))
                title_node.add_child(group_node)

            doc_node = HTML5AppNode(
                title=metadata.title,
                description=metadata.description,
                source_id=zfilename+str(i+0.9),
                license=LICENCE,
                language='es',
                files=[HTMLZipFile(path=zfilename)],
            )

            group_node.add_child(doc_node)
        return channel

if __name__ == '__main__':
    """
    Set the environment var `CONTENT_CURATION_TOKEN` (or `KOLIBRI_STUDIO_TOKEN`)
    to your Kolibri Studio token, then call this script using:
        python souschef.py  -v --reset
    """
    mychef = CedecChef()
    if 'KOLIBRI_STUDIO_TOKEN' in os.environ:
        os.environ['CONTENT_CURATION_TOKEN'] = os.environ['KOLIBRI_STUDIO_TOKEN']
    mychef.main( )
