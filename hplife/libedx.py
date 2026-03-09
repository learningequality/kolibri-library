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
    path = coursedir
    if kind:
        path = os.path.join(path, kind)
    path = os.path.join(path, name + '.' + ext)
    if not os.path.exists(path):
        raise ValueError('XML file not found: ' + path)
    
    # Load XML
    xml = open(path, 'r')
    doc = BeautifulSoup(xml, "xml")
    doc_children = list(doc.children)
    assert len(doc_children) == 1, 'Found more than one root element!'
    doc_root = doc_children[0]
    # print(doc)
    
    # JSON data object
    data = {
        'kind': doc_root.name,
        'id': name,
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
    path = coursedir
    if kind:
        path = os.path.join(path, kind)
    path = os.path.join(path, name + '.' + ext)
    if not os.path.exists(path):
        raise ValueError('HTML file not found: ' + path)
    
    # Load XML
    html = open(path, 'r').read()
    
    # JSON data object
    data = {
        'kind': kind,
        'url_name': name,
        'content': html,                 # [0:30] + '...',  # used for debugging
        'children': [],
    }

    # Hanlde special case of HTML file with downloadable resources

    is_resources_folder_candidate = False       # True if we find links to s3.amazonaws.com
    seen_tuple = None                           # save (bucket_url, bucket_path, activity_ref) links seen
    is_resources_folder = False                 # True if all links are to the same seen_tuple

    doc = BeautifulSoup(html, "html5lib")
    links = doc.find_all('a')
    for link in links:
        if 'href' in link.attrs and 's3.amazonaws.com' in link['href']:
            is_resources_folder_candidate = True
            # print('Found resources_folder_candidate')
        else:
            # print('No href in ', link)
            pass

        if is_resources_folder_candidate:
            if 'href' in link.attrs and 's3.amazonaws.com' in link['href']:
                url_parts = link['href'].split('/')
                bucket_url = '/'.join(url_parts[0:4])
                bucket_path = '/'.join(url_parts[4:-2])
                activity_ref = unquote_plus(url_parts[-2])
                this_tuple = (bucket_url, bucket_path, activity_ref)
                if seen_tuple is None:
                    seen_tuple = this_tuple
                else:
                    if seen_tuple == this_tuple:
                        is_resources_folder = True
                    else:
                        is_resources_folder = False
            else:
                # print('another link found', link)
                pass

    if is_resources_folder:
        data['activity'] = dict(
            kind = 'resources_folder',
            bucket_url = seen_tuple[0],
            bucket_path = seen_tuple[1],
            activity_ref = seen_tuple[2],
            entrypoint = None,
            url=link['href'],
        )
        # print('Found resources_folder', data['activity'])
    return data


def parse_problem_file(coursedir, kind, name, ext='xml'):
    """
    Parse the XML for an Articulate Storyline file at {coursedir}/{kind}/{name}.{ext}
    and return the json tree representation.
    """
    # Build path to XML file
    path = coursedir
    if kind:
        path = os.path.join(path, kind)
    path = os.path.join(path, name + '.' + ext)
    if not os.path.exists(path):
        raise ValueError('HTML file not found: ' + path)
    
    # Load XML
    xml = open(path, 'r').read()
    doc = BeautifulSoup(xml, "xml")

    # JSON data object
    data = {
        'kind': kind,
        'children': [],
    }

    choiceresponse = doc.find('choiceresponse')
    jsinput = doc.find('jsinput')

    # CASE A: non-articulare choiceresponse activity
    if choiceresponse and jsinput is None:
        data['content'] = xml

    # CASE B: activity files
    elif jsinput and choiceresponse is None:
        url = jsinput['html_file']

        # old-style hpstoryline
        if 'hpstoryline.edcastcloud.com' in url or 'herokuapp.com/hp_storyline' in url:
            querystring = url.split('?')[1]
            story_id = querystring.replace('story=', '')
            data['activity'] = dict(
                kind = 'hpstoryline',
                story_id = story_id,
                url=url,
            )

        # new-style articulare storyline
        else:
            url_parts = url.split('/')
            data['activity'] = dict(
                kind = 'articulate_storyline',
                bucket_url = '/'.join(url_parts[0:4]),
                bucket_path = '/'.join(url_parts[4:-2]),
                activity_ref = unquote_plus(url_parts[-2]),
                entrypoint = url_parts[-1],
                url=url,
            )

        return data
    else:
        print('Found unexpected problem type at', path)
        return None
    




def print_course(course):
    """
    Display course tree hierarchy for debugging purposes.
    """
    def print_subtree(subtree, indent=0):
        title = subtree['display_name'] if 'display_name' in subtree else ''
        
        extra = ''
        if 'url_name' in subtree:
            extra += ' url_name=' + subtree['url_name']
        if 'slug' in subtree:
            extra += ' slug=' + subtree['slug']
        if subtree['kind'] == 'course':
            subtreecopy = copy.deepcopy(subtree)
            del subtreecopy['children']
            extra += ' attrs='+str(subtreecopy)
        if 'activity' in subtree:
            if subtree['activity']['kind'] == 'hpstoryline':
                extra += 'story_id=' + str(subtree['activity']['story_id'])
            else:
                extra += 'activity_ref=' + str(subtree['activity']['activity_ref'])
        print('   '*indent, '-', title,  'kind='+subtree['kind'], '\t', extra)
        if 'children' in subtree:
            for child in subtree['children']:
                print_subtree(child, indent=indent+1)
    print_subtree(course)
    print('\n')

