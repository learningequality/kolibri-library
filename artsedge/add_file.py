import requests

from ricecooker.classes.nodes import DocumentNode, VideoNode, TopicNode, AudioNode, HTML5AppNode
from ricecooker.classes.files import HTMLZipFile, VideoFile, SubtitleFile, DownloadFile, AudioFile, DocumentFile, ThumbnailFile, WebVideoFile, Base64ImageFile, YouTubeSubtitleFile, YouTubeVideoFile
from le_utils.constants import licenses

from urllib.parse import urlsplit
import hashlib
import os

class UnidentifiedFileType(Exception):
    pass

DOWNLOAD_FOLDER = "__downloads"  # this generates completed files

try:
    os.mkdir(DOWNLOAD_FOLDER)
except FileExistsError:
    pass

metadata = {}

node_dict = {VideoFile: VideoNode,
             AudioFile: AudioNode,
             HTMLZipFile: HTML5AppNode,
             DocumentFile: DocumentNode}

#from build_carousel import create_carousel_zip

# Long-Range TODOs
# -- detect and re-encode non-MP4 videos, non-MP3 audio, etc.
# -- package up images as zip files (using build_carousel)

def guess_extension(url):
    "Return the extension of a URL, i.e. the bit after the ."
    filename = urlsplit(url).path
    if "." not in filename[-8:]: # arbitarily chosen
        return ""
    ext = "." + filename.split(".")[-1].lower()
    if "/" in ext:  # dot isn't in last part of path
        return ""
    return ext

def create_filename(url):
    return hashlib.sha1(url.encode('utf-8')).hexdigest() + guess_extension(url)

def download_file(url):
    # url must be fully specified!
    zip_response = requests.get(url, stream=True)
    filename = DOWNLOAD_FOLDER + "/" + create_filename(url)
    if not os.path.exists(filename):
        print ("Downloading to {}".format(filename))
        print ("{} bytes".format(zip_response.headers.get("content-length")))
        try:
            with open(filename, "wb") as f:
                # https://www.reddit.com/r/learnpython/comments/27ba7t/requests_library_doesnt_download_directly_to_disk/
                for chunk in zip_response.iter_content( chunk_size = 1024 ):
                    if chunk: # filter out keep-alive new chunks
                        f.write(chunk)
        except:  # Explicitly, we also want to catch CTRL-C here.
            print("Catching & deleting bad zip created by quitting")
            try:
                os.remove(filename)
            except FileNotFoundError:
                pass
            raise
            
            print ("{} bytes written".format(zip_response.headers.get("content-length")))
    else:
        print ("Already exists in cache")
    return filename, zip_response.headers.get("content-type")

def create_node(file_class=None, url=None, filename=None, title=None, license=None, copyright_holder=None):
    # note: things will break downstream if license etc. not provided!
    # use 'metadata' to automatically fill in fields
    
    mime = None
    if filename is None:
        assert url, "Neither URL nor filename provided to create_node"
        filename, mime = download_file(url)
        
    if file_class is None:
        with open(filename, "rb") as f:
            magic_bytes = f.read(8)[:8]
        file_class = guess_type(content_type=mime,
                                extension=guess_extension(url),
                                magic=magic_bytes)
        # there is a reasonable chance that the file isn't actually a suitable filetype
        # and that guess_type will raise an UnidentifiedFileType error.
    assert file_class
    
    extensions = {VideoFile: ".mp4",
                  AudioFile: ".mp3",
                  DocumentFile: ".pdf",
                  HTMLZipFile: ".zip",}
    extension = extensions[file_class]
    if not filename.endswith(extension):  # sushichef requires files have correct extension.
        new_filename = filename + extension
        os.rename(filename, new_filename)
        filename = new_filename
    
    print (filename, os.path.getsize(filename))
    assert(os.path.getsize(filename))
    
    # //
    kwargs = {VideoFile: {"ffmpeg_settings": {"max_width": 480, "crf": 28}},
              AudioFile: {},
              DocumentFile: {},
              HTMLZipFile: {}}

    file_instance = file_class(filename, **kwargs[file_class]) # property
    #//    

    node_class = node_dict[file_class]
    
    return node_class(source_id=filename,
                      title=title,
                      license=license or metadata['license'], 
                      copyright_holder=copyright_holder or metadata['copyright_holder'],
                      files=[file_instance],
                      )     

def guess_type(content_type="",
               extension="",
               magic=b""):
    
    content_mapping = {"audio/mp3": AudioFile,
                       "video/mp4": VideoFile,
                       "audio/mp4": VideoFile,
                       "application/pdf": DocumentFile,
                       }
    
    if content_type in content_mapping:
        return content_mapping[content_type]
    
    extension_mapping = {"mp3": AudioFile,
                         "mp4": VideoFile,
                         
                         # m4v!
                         "pdf": DocumentFile,
                         # "zip": HTMLZipFile,  # primarily for carousels
                         }
    
    if extension in extension_mapping:
        return extension_mapping[extension]
    
    # consider using python_magic
    magic_mapping = {b"\xFF\xFB": AudioFile,
                     b"ID3": AudioFile,
                     b"%PDF": DocumentFile, #
                     # b"PK": HTMLZipFile, 
                     }
    
    for mapping in magic_mapping:
        if magic.startswith(mapping):
            return magic_mapping[mapping]
        
    raise UnidentifiedFileType(str([content_type, extension]))

def get_type_and_response(url):
    response = requests.get(url)
    response.raise_for_status()
    # get the bit before the semi-colon -- should be audio/mp3 or similar
    content_type = response.headers.get('Content-Type', "").split(";")[0].strip()
    extension = guess_extension(response.url)
    magic = response.content[:4]
    try:
        file_type = guess_type(content_type, extension, magic)
    except UnidentifiedFileType:
        file_type = None
    return [file_type, response]

def guess_by_url(url):
    return get_type_and_response(url)[0]
    
if __name__ == "__main__":
    print(create_node(DocumentFile, "http://www.pdf995.com/samples/pdf.pdf", license=licenses.CC_BY_NC_ND, copyright_holder="foo"))