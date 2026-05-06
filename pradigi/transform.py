import hashlib
import logging
import os
import requests
import shutil
import tempfile
import zipfile
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from ricecooker.config import LOGGER
from ricecooker.utils.html import download_file
from ricecooker.utils.zip import create_predictable_zip


from corrections import (PRADIGI_CORRECTIONS_LIST, CORRECTIONS_ACTION_KEY,
                         ADD_MARGIN_TOP_ACTION, CORRECTIONS_SOURCE_URL_PAT_KEY)
from corrections import should_replace_with


LOGGER.setLevel(logging.DEBUG)



# GAME_THUMBS_LOCAL_DIR = 'chefdata/gamethumbnails'
HTML5APP_ZIPS_LOCAL_DIR = 'chefdata/zipfiles'




# ZIP FILE DOWNLOADING, TRANFORMS, AND FIXUPS
################################################################################

def make_request(url):
    response = requests.get(url)
    if response.status_code != 200:
        LOGGER.error("ERROR when GETting: %s" % (url))
    return response

def make_temporary_dir_from_key(key_str):
    """
    Creates a subdirectory of HTML5APP_ZIPS_LOCAL_DIR to store
    the downloded, unzipped, and final version of each HTML5Zip file.
    """
    key_bytes = key_str.encode('utf-8')
    m = hashlib.md5()
    m.update(key_bytes)
    subdir = m.hexdigest()
    dest = os.path.join(HTML5APP_ZIPS_LOCAL_DIR, subdir)
    if not os.path.exists(dest):
        os.mkdir(dest)
    return dest

def add_body_margin_top(zip_folder, filename, margin='44px'):
    file_path = os.path.join(zip_folder, filename)
    with open(file_path, 'r') as inf:
        html = inf.read()
    page = BeautifulSoup(html, "html.parser")  # Load index.html as BS4
    body = page.find('body')
    if body.has_attr('style'):
        prev_style_str = body['style']
    else:
        prev_style_str = ''
    body['style'] = prev_style_str + " margin-top:" + margin + ";"
    with open(file_path, 'w') as outf:
        outf.write(str(page))


def get_zip_file(zip_file_url, main_file):
    """
    HTML games are provided as zip files, the entry point of the game is `main_file`.
    THe `main_file` needs to be renamed to index.html to make it compatible with Kolibri.
    """
    key = zip_file_url + main_file
    key_bytes = key.encode('utf-8')
    m = hashlib.md5()
    m.update(key_bytes)
    subdir = m.hexdigest()
    destpath = os.path.join("chefdata/zipfiles/", subdir)
    final_webroot_path = os.path.join(destpath, 'webroot.zip')
    if os.path.exists(final_webroot_path):
        # Existence isn't enough: we've seen 22-byte empty zips in the cache
        # that pass this check but fail later at ricecooker validation with a
        # confusing "No required format preset" error. Verify the zip has at
        # least one entry before returning its path.
        try:
            with zipfile.ZipFile(final_webroot_path) as zf:
                names = zf.namelist()
                if not names:
                    LOGGER.error(
                        "get_zip_file: %s exists but is an EMPTY zip (url=%s)"
                        % (final_webroot_path, zip_file_url)
                    )
                elif "index.html" not in names:
                    LOGGER.error(
                        "get_zip_file: %s has no index.html at root (url=%s). "
                        "top entries: %s"
                        % (final_webroot_path, zip_file_url, names[:3])
                    )
                else:
                    return final_webroot_path
        except zipfile.BadZipFile as e:
            LOGGER.error(
                "get_zip_file: %s exists but is NOT a valid zip: %s (url=%s)"
                % (final_webroot_path, e, zip_file_url)
            )
    else:
        LOGGER.error("get_zip_file: no webroot.zip at %s (url=%s, main_file=%s)"
                     % (final_webroot_path, zip_file_url, main_file))
        if os.path.isdir(destpath):
            for root, dirs, files in os.walk(destpath):
                if files:
                    LOGGER.error("  dir contents: %s" % files)
        else:
            LOGGER.error("  hash dir does not exist at all")
    return None


PHET_INDEX_HTML_TEMPLATE = """
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
</head>
<body>
  <div><p>Redirecting to phet simulation {sim_id} now...</p></div>
</body>
<script type="text/javascript">
    window.location.href = "phetindex.html?id={sim_id}";
</script>
</html>
"""


def get_phet_zip_file(zip_file_url, main_file_and_query):
    """
    Phet simulations are provided in the zip file `phet.zip`, and the entry point
    is passed as a GET parameter in `main_file_and_query`. To make these compatible
    with Kolibri's default behaviour of loading index.html, we will:
      - Rename index.html to phetindex.thml
      - Add a custom index.html that uses javascrpt redirect to phetindex.thml?{sim_id}
    """
    u = urlparse(main_file_and_query)
    idk, sim_id = u.query.split('=')
    assert idk == 'id', 'unknown query sting format found' + main_file_and_query
    main_file = u.scheme + '://' + u.netloc + u.path  # skip querystring
    
    destpath = tempfile.mkdtemp()
    LOGGER.info('saving phet zip file in dir ' + destpath)
    try:
        download_file(zip_file_url, destpath, request_fn=make_request)

        zip_filename = zip_file_url.split('/')[-1]
        zip_basename = zip_filename.rsplit('.', 1)[0]
        zip_folder = os.path.join(destpath, zip_basename)

        # Extract zip file contents.
        local_zip_file = os.path.join(destpath, zip_filename)
        with zipfile.ZipFile(local_zip_file) as zf:
            zf.extractall(destpath)

        # Rename main_file to phetindex.html
        main_file = main_file.split('/')[-1]
        src = os.path.join(zip_folder, main_file)
        dest = os.path.join(zip_folder, 'phetindex.html')
        os.rename(src, dest)

        # Create the 
        index_html = PHET_INDEX_HTML_TEMPLATE.format(sim_id=sim_id)
        with open(os.path.join(zip_folder, 'index.html'), 'w') as indexf:
            indexf.write(index_html)
        
        # Always be zipping!
        return create_predictable_zip(zip_folder)

    except Exception as e:
        LOGGER.error("get_phet_zip_file: %s, %s, %s, %s" %
                     (zip_file_url, main_file_and_query, destpath, e))
        return None




