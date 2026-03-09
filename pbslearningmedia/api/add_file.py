import requests

from ricecooker.classes.nodes import DocumentNode, VideoNode, TopicNode, AudioNode, HTML5AppNode
from ricecooker.classes.files import HTMLZipFile, VideoFile, SubtitleFile, DownloadFile, AudioFile, DocumentFile, ThumbnailFile, WebVideoFile, Base64ImageFile, YouTubeSubtitleFile, YouTubeVideoFile
from le_utils.constants import licenses

from urllib.parse import urlsplit
import hashlib
import os
import subprocess
import glob

class CantMakeNode(Exception):
    pass

class UnidentifiedFileType(CantMakeNode):
    pass

VALIDATE = True
TEMP_FILE = "__temp"
SUBTITLE_LANGUAGE = "en"

metadata = {}
have_setup = False

node_dict = {VideoFile: VideoNode,
             AudioFile: AudioNode,
             HTMLZipFile: HTML5AppNode,
             DocumentFile: DocumentNode}

# Long-Range TODOs
# -- package up images as zip files (using build_carousel)

def guess_extension(url):
    "Return the extension of a URL, i.e. the bit after the ."
    if not url:
        return ""
    filename = urlsplit(url).path
    if "." not in filename[-8:]: # arbitarily chosen
        return ""
    ext = "." + filename.split(".")[-1].lower()
    if "/" in ext:  # dot isn't in last part of path
        return ""
    return ext

def create_filename(url):
    return hashlib.sha1(url.encode('utf-8')).hexdigest() + guess_extension(url)

def examine_file(url):
    """
    Download file to the DOWNLOAD_FOLDER with a content-generated filename.
    Return that filename and the mime type the server told us the file was
    """

    # url must be fully specified!
    response = requests.get(url, stream=True)
    try:
        os.remove(TEMP_FILE)
    except Exception:
        pass
    try:
        with open(TEMP_FILE, "wb") as f:
            # https://www.reddit.com/r/learnpython/comments/27ba7t/requests_library_doesnt_download_directly_to_disk/
            for chunk in response.iter_content( chunk_size = 1024 ): # might want 32K
                if chunk: # filter out keep-alive new chunks
                    f.write(chunk)
                    break
    except Exception as e:
        print (e)
    content_type = response.headers.get('Content-Type', "").split(";")[0].strip()
    return content_type

def create_file(*args, **kwargs):  # as a ricecooker file object, suitable for inserting into a node, for e.g. subtitles
    return create_node(*args, as_file=True, **kwargs)

def create_node(file_class=None, url=None, title=None, license=None, copyright_holder=None,
                description="", as_file=False, author=None, source_id=None):
    """
    Create a content node from either a URL or filename.
    Which content node is determined by:
    * the 'file_class' explicitly passed (e.g. VideoFile)
    * guessing from downloaded mimetype, file extension or magic bytes
    (see guess_type function)

    Use metadata to automatically fille in licence and copyright_holder details --
    if they're not provided correctly, things will break downstream
    """

    assert url, "URL not provided to create_node"
    if not source_id:
        source_id=url
    mime = examine_file(url)  # TEMP_FILE now contains data

    if file_class is None:
        with open(TEMP_FILE, "rb") as f:
            magic_bytes = f.read(10)[:10]  # increase if we use python_magic
        try:
            file_class = guess_type(mime_type=mime,
                                    extension=guess_extension(url),
                                    magic=magic_bytes,
                                    filename=TEMP_FILE)
        except Exception:
            print(url)
            raise
        # there is a reasonable chance that the file isn't actually a suitable filetype
        # and that guess_type will raise an UnidentifiedFileType error.
    assert file_class
    print (file_class)
   
    keywords = {VideoFile: {"ffmpeg_settings": {"max_width": 480, "crf": 28}},
                AudioFile: {},
                DocumentFile: {},
                HTMLZipFile: {},
                SubtitleFile: {"language": SUBTITLE_LANGUAGE}}
    file_instance = file_class(url, **keywords[file_class])
    if as_file:
        return file_instance

    node_class = node_dict[file_class]
    
    if node_class == VideoNode:
        node = node_class(source_id=source_id,
                      title=title,
                      license=license or metadata.get('license'),
                      copyright_holder=copyright_holder or metadata.get('copyright_holder'),
                      files=[file_instance],
                      description=description,
                      author=author,
                      derive_thumbnail=True,
                      )
    else:
        node = node_class(source_id=source_id,
                      title=title,
                      license=license or metadata.get('license'),
                      copyright_holder=copyright_holder or metadata.get('copyright_holder'),
                      files=[file_instance],
                      description=description,
                      author=author,
                      )
    try:
        if VALIDATE:
            node.validate()
    except Exception as e:
        raise CantMakeNode(str(e))
    return node

def guess_type(mime_type="",
               extension="",
               magic=b"",
               filename=None):

    content_mapping = {"audio/mp3": AudioFile,
                       "video/mp4": VideoFile,
                       "audio/mp4": VideoFile,
                       "video/webm": VideoFile,
                       "application/pdf": DocumentFile,
                       "video/quicktime": VideoFile,
                       "video/x-flv": VideoFile,
                       "video/3gpp": VideoFile,
                       # 'application/xml': DFXP format SubtitleFile -- too vague

                       }

    if mime_type in content_mapping:
        return content_mapping[mime_type]

    extension_mapping = {".mp3": AudioFile,
                         ".mp4": VideoFile,
                         ".webm": VideoFile,
                         ".m4v": VideoFile,
                         #".m4a": AudioFile,
                         ".pdf": DocumentFile,
                         ".vtt": SubtitleFile,
                         ".dfxp": SubtitleFile,
                         # "zip": HTMLZipFile,  # primarily for carousels
                         }

    if extension in extension_mapping:
        return extension_mapping[extension]

    magic_mapping = {b"\xFF\xFB": AudioFile,
                     b"ID3": AudioFile,
                     b"%PDF": DocumentFile,
                     b"\x1A\x45\xDF\xA3": VideoFile,
                     b"WEBVTT": SubtitleFile,
                     # b"PK": HTMLZipFile,
                     }

    for mapping in magic_mapping:
        if magic.startswith(mapping):
            return magic_mapping[mapping]

    # NOT PORTABLE.
    # filename: mime/type; encoding
    file_response = subprocess.check_output(["file", "-i", filename]).decode('utf-8')
    not_filename = file_response.partition(": ")[2]
    file_mime = not_filename.partition(";")[0]

    if file_mime in content_mapping:
        return content_mapping[file_mime] 

    # TODO -- consider using python_magic library

    raise UnidentifiedFileType(str([mime_type, extension, magic, file_mime]))



if __name__ == "__main__":
    pass
    #print(create_node(DocumentFile, "http://www.pdf995.com/samples/pdf.pdf", license=licenses.CC_BY_NC_ND, copyright_holder="foo"))
