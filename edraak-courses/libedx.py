from bs4 import BeautifulSoup
from bs4.element import NavigableString
import copy
import json
import os
from urllib.parse import unquote_plus




# HIGH LEVEL API
################################################################################

def extract_course_tree(coursedir):
    """
    Extract a json tree from a edX course 
    """
    recusivedata = parse_xml_file_refusive(coursedir, 'course', 'course')
    # update root element data course/course.xml with data in basedir course.xml
    flatdata = parse_xml_file_refusive(coursedir, None, 'course')
    del flatdata['children']
    recusivedata.update(flatdata)
    return recusivedata





# LOW LEVEL API
################################################################################
# Note: This code has some HP-LIFE specific functions, not general purpose edX

def parse_xml_file(coursedir, kind, name, ext='xml'):
    """
    Parse the XML file at {coursedir}/{kind}/{name}.{ext}
    and return the json tree representation.
    References are not resolved --- see `parse_xml_file_refusive` for that.
    """
    # Build path to XML file
    if kind:
        path = os.path.join(coursedir, kind, name + '.' + ext)
    else:
        path = os.path.join(coursedir, name + '.' + ext)
    if not os.path.exists(path):
        raise ValueError('XML file not found: ' + path)

    # Load XML
    # print('parsing', path)
    xml = open(path, 'r')
    doc = BeautifulSoup(xml, "xml")
    doc_children = list(doc.children)
    assert len(doc_children) == 1, 'Found more than one root element!'
    doc_root = doc_children[0]
    # print(doc)

    # JSON data object
    data = {
        'kind': doc_root.name,
        'url_name': name,
        'children': [],
    }
    data.update(doc_root.attrs)

    # Add children as unresoled references
    for child in doc_root.children:
        if type(child) == NavigableString:
            continue
        assert len(child.attrs) == 1, 'Assumption failed: encountered more than one attr'
        kind = child.name
        child_ref = {
            'kind': kind,
        }
        if kind == 'wiki':
            child_ref['slug'] = child.attrs['slug']
        elif kind == 'html':
            child_ref['url_name'] = child.attrs['url_name']
            child_ref['ext'] = 'html'
        else:
            child_ref['url_name'] = child.attrs['url_name']
        data['children'].append(child_ref)

    return data



def parse_xml_file_refusive(coursedir, kind, name, ext='xml'):
    """
    Parse the XML file at {coursedir}/{kind}/{name}.{ext} recusively
    using the base XML-to-JSON basic parsing function `parse_xml_file`.
    Recusrively resolves all references of the form {kind: AAA, url_name: BBB}
    bu loading the XML data from the file at {coursedir}/AAA/BBB.xml
    Returns a json tree representation.
    """
    root = parse_xml_file(coursedir, kind, name, ext=ext)
    new_children = []
    for child in root['children']:
        child_kind = child['kind']
        if child_kind == 'wiki':
            new_children.append(child)
        elif child_kind == 'html':
            htmldata = parse_html_file(coursedir, child['kind'], child['url_name'], ext='html')
            new_children.append(htmldata)
        elif child_kind == 'video':
            videodata = parse_video_file(coursedir, child['kind'], child['url_name'])
            new_children.append(videodata)
        elif child_kind == 'problem':
            problemdata = parse_problem_file(coursedir, child['kind'], child['url_name'], ext='xml')
            if problemdata:
                new_children.append(problemdata)
        else:
            child_name = child['url_name']
            resolved_child = parse_xml_file_refusive(coursedir, child_kind, child_name, ext='xml')
            new_children.append(resolved_child)
    root['children'] = new_children
    return root




def parse_html_file(coursedir, kind, name, ext='html'):
    """
    Parse the HTML file at {coursedir}/{kind}/{name}.{ext}
    and return the json tree representation.
    """
    # Build path to XML file
    path = os.path.join(coursedir, kind, name + '.' + ext)
    if not os.path.exists(path):
        raise ValueError('HTML file not found: ' + path)
    
    # Read HTML
    html = open(path, 'r').read()
    
    # JSON data object
    data = {
        'kind': kind,
        'url_name': name,
        'content': html,                 # [0:30] + '...',  # used for debugging
        'children': [],
    }

    doc = BeautifulSoup(html, "html5lib")
    links = doc.find_all('a')

    return data






def parse_video_file(coursedir, kind, name, ext='xml'):
    """
    Parse the Video XML file at {coursedir}/{kind}/{name}.{ext}
    and return the json tree representation.
    """
    # Build path to XML file
    path = os.path.join(coursedir, kind, name + '.' + ext)
    if not os.path.exists(path):
        raise ValueError('Video XML file not found: ' + path)

    # Load XML
    xml = open(path, 'r').read()
    # print(xml)

    # JSON data object
    data = {
        'kind': kind,
        'url_name': name,
        'content': xml,
        'children': [],
    }
    return data


def parse_problem_file(coursedir, kind, name, ext='xml'):
    """
    Parse the XML for the problem file at {coursedir}/{kind}/{name}.{ext}
    and return the json tree representation.
    """
    # Build path to XML file
    path = os.path.join(coursedir, kind, name + '.' + ext)
    if not os.path.exists(path):
        raise ValueError('HTML file not found: ' + path)

    # Load XML
    xml = open(path, 'r').read()
    doc = BeautifulSoup(xml, "xml")

    # JSON data object
    data = {
        'kind': kind,
        'url_name': name,
        'children': [],
    }
    data['content'] = xml
    return data


import shelve
from functools import wraps
from time import time
import struct
import io

def cached(f=None, expire=None):
    if f is None:
        cached.expire = expire
        return cached
    c = shelve.open( "/tmp/cache-%s-%s"%(os.getlogin(),f.__name__), 'c', -1 )
    @wraps(f)
    def wrapper( *args, **kwargs ):
        h = str(args)+str(kwargs)
        try:
            result, created = c[h]
            if cached.expire and time()-created > cached.expire:
                print('expired')
                raise KeyError
        except KeyError:
            print('calling f')
            result = f( *args, **kwargs )
            c[h] = result, time()
        except TypeError:
            print('typeerror')
            result = f( *args, **kwargs )
        return result
    return wrapper
cached.expire = None

@cached(expire=500000)
def translate_to_en(text, source_language=None):
    from google.cloud import translate
    translate_client = translate.Client()
    response = translate_client.translate(text, source_language=source_language, target_language='en')
    return response['translatedText']



def print_course(course, translate_from=None):
    """
    Display course tree hierarchy for debugging purposes.
    """
    EXTRA_FIELDS = ['description', 'youtube_id', 'path', 'text']
    
    def print_subtree(subtree, indent=0):
        title = subtree['display_name'] if 'display_name' in subtree else ''
        if translate_from:
            title_en = translate_to_en(title, source_language=translate_from)
            title = title_en  + ' ' + title
        extra = ''
        if 'url_name' in subtree and 'youtube_id' not in subtree and 'path' not in subtree: # and subtree['kind'] != 'html':
            extra += ' url_name=' + subtree['url_name']
        if 'slug' in subtree:
            extra += ' slug=' + subtree['slug']
        if subtree['kind'] == 'course':
            subtreecopy = copy.deepcopy(subtree)
            del subtreecopy['children']
            del subtreecopy['certificates']
            extra += ' attrs='+str(subtreecopy)
        # print all EXTRA_FIELDS
        for key in EXTRA_FIELDS:
            if key in subtree:
                extra += ' {}='.format(key) + subtree[key]
        print('   '*indent, '-', title,  'kind='+subtree['kind'], '\t', extra)
        if 'downloadable_resources' in subtree:
            for resource in subtree['downloadable_resources']:
                print('                  > resouce:', resource['relhref'])
        if 'children' in subtree:
            for child in subtree['children']:
                print_subtree(child, indent=indent+1)
    print_subtree(course)
    print('\n')
