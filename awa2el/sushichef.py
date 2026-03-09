#!/usr/bin/env python
import os
import sys
sys.path.append(os.getcwd()) # Handle relative imports
import requests
from ricecooker.classes.nodes import DocumentNode, VideoNode, TopicNode
from ricecooker.classes.files import HTMLZipFile, VideoFile, SubtitleFile, DownloadFile, DocumentFile
from ricecooker.classes.licenses import SpecialPermissionsLicense
from ricecooker.chefs import SushiChef
import logging
import video
import arabic
import dosier
import ricecooker.classes.nodes
import badlist

badcount =  0


def _validate(self):
        """ 
        Ensure `self.path` has one of the extensions in `self.allowed_formats`. 
        """ 
        assert self.path, "{} must have a path".format(self.__class__.__name__) 
        _, dotext = os.path.splitext(self.path) 
        try:
            ext = dotext.lstrip('.') 
        except:
            print (repr(dotext), repr(self.path))
            raise
        # don't validate for single-digit extension, or no extension 
        if len(ext) > 1: 
            assert ext in self.allowed_formats, "{} must have one of the following" 
            "extensions: {} (instead, got '{}' from '{}')".format( 
            self.__class__.__name__, self.allowed_formats, ext, self.path) 

DownloadFile.validate = _validate




def _add_child(self, node): 
        """ add_child: Adds child node to node
            Args: node to add as child
            Returns: None 
        """
        assert isinstance(node, Node), "Child node must be a subclass of Node"
        node.parent = self 
        source_ids = [c.source_id for c in self.children]
        if node.source_id not in source_ids:
            self.children += [node]
        else:
            print ("SAME ID")

ricecooker.classes.nodes.add_child = _add_child


assert "--compress" in sys.argv, sys.argv
assert "develop" not in os.environ['STUDIO_URL']

LOGGER = logging.getLogger()
LICENCE = SpecialPermissionsLicense("awa2el.net / nashmi.net", "For use on Kolibri")

class NashmiChef(SushiChef):
    channel_info = {
        'CHANNEL_SOURCE_DOMAIN': 'www.awa2el.net', # who is providing the content (e.g. learningequality.org)
        'CHANNEL_SOURCE_ID': 'awa2el',         # channel's unique id
        'CHANNEL_TITLE': arabic.title,
        'CHANNEL_LANGUAGE': 'ar',                          # Use language codes from le_utils
        'CHANNEL_THUMBNAIL': 'aw.png', # (optional) local path or url to image file
        'CHANNEL_DESCRIPTION': arabic.description  # (optional) description of the channel (optional)
    }

    def construct_channel(self, **kwargs):
        done_nodes = []

        def video_node(video, title):
            v = video.decode('utf-8')
            if v in done_nodes:
                return None
            done_nodes.append(v)
            files = [VideoFile(video.decode('utf-8'))]
            
            return VideoNode(source_id="video "+video.decode('utf-8'),
                             title=title,
                             license=LICENCE,
                             copyright_holder="nashmi.net",
                             files=files,
                             )

        def doc_node(doc, title):
            if type(doc) == bytes:
                doc = doc.decode('utf-8')
            files = [DocumentFile(doc)]
            if str(doc) in done_nodes:
                return None
            done_nodes.append(str(doc))
            return DocumentNode(source_id="doc "+str(doc),
                                title=title, 
                                license = LICENCE,
                                copyright_holder="nashmi.net",
                                files=files,
                               )

        def get_node(_path, rootparent, nodes):
            global badcount
            path = tuple(_path)
            if path in nodes:
                return nodes[path]
            if len(path) > 1:
                parent = get_node(path[:-1], rootparent, nodes)
                assert parent
            else:
                parent = rootparent
            
            if path not in nodes:
                title = path[-1]

                if title in badlist.rename:
                    badcount = badcount + 1
                    print ("badlist: RENAME", title, badcount)
                    title=badlist.rename[title]
                
                # mangle title: 
                if arabic.grade in title:
                    print ("grade: SKIP GRADE", title)
                else:
                     print ("grade: NO GRADE", title)
                     drop = False
                     for drop_word in arabic.drop_words:
                         if drop_word in title:
                             drop = drop_word
                     print ("grade: ", drop)
                     if drop:
                         newtitle = False
                         for subject in arabic.subjects:
                             if subject in title:
                                 title = arabic.subjects[subject]
                                 newtitle = True
                         assert newtitle, title
                         print ("grade: CHANGE TO", title) 

                # check if new title present!
                path = list(path)
                path[-1] = title
                path = tuple(path)
                if path in nodes:
                    print ("NEW PATH")
                    return nodes[path]

                nodes[path] = TopicNode(source_id="topic"+title,
                                        title=title)

                if title in badlist.badlist:
                    badcount = badcount + 1
                    print ("badlist: BAD: ", title, badcount)
                    return nodes[path] # unconnected!
                parent.add_child(nodes[path])
            return nodes[path]
            
        vid_nodes = {}
        pdf_nodes = {}

        channel = self.get_channel(**kwargs)
        video_tln = TopicNode(source_id="videotln", title=arabic.video) 
        pdf_tln = TopicNode(source_id="pdftln", title=arabic.dossier) 
        channel.add_child(video_tln)
        channel.add_child(pdf_tln)

        for doc in dosier.docs():
            print ("BREAD: ", len(doc['bread']), doc['bread'])
            node = get_node(doc['bread'], pdf_tln, pdf_nodes)
            if not node: continue
            dfile = doc_node(doc['filename'], doc['title'])
            if dfile:
                node.add_child(dfile) 

        for path, video_urls in video.videos():
            if len(video_urls) == 1:
                video_url, = video_urls
                title = path[-1]
                path = path[:-1]
                node = get_node(path, video_tln, vid_nodes)
                vfile = video_node(video_url, title)
                if vfile:
                    node.add_child(vfile)
            else:
                node = get_node(path, video_tln, vid_nodes)
                for i, video_url in enumerate(video_urls):
                    vfile = video_node(video_url, arabic.video_123[i])
                    if vfile:
                        node.add_child(vfile)
        return channel # outdent if not debug
            
            
            
        # create channel
        # create a topic and add it to channel
        
        
        

if __name__ == '__main__':
    """
    Set the environment var `CONTENT_CURATION_TOKEN` (or `KOLIBRI_STUDIO_TOKEN`)
    to your Kolibri Studio token, then call this script using:
        python souschef.py  -v --reset
    """
    mychef = NashmiChef()
    if 'KOLIBRI_STUDIO_TOKEN' in os.environ:
        os.environ['CONTENT_CURATION_TOKEN'] = os.environ['KOLIBRI_STUDIO_TOKEN']
    mychef.main()
