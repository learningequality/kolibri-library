#!/usr/bin/env python
import os
import sys
sys.path.append(os.getcwd()) # Handle relative imports
from utils import data_writer, path_builder, downloader, slugify
from le_utils.constants import licenses, exercises, content_kinds, file_formats, format_presets, languages

# Additional imports 
###########################################################
from utils.downloader import read
from utils.html import HTMLWriter
from bs4 import BeautifulSoup
import logging
import re

from utils.slugify import slugify
import youtube_dl
from ricecooker.utils.html import download_file

import urllib.request
import uuid
import magic

# Convert pdf files
###########################################################
import requests

def save_response_content(response, filename):
    with open(filename, 'wb') as localfile:
        localfile.write(response.content)

# convert it
def convert_file(document, result):
    microwave_url = 'http://35.185.105.222:8989/unoconv/pdf'
    files = {'file': open(document, 'rb')}
    response = requests.post(microwave_url, files=files)
    save_response_content(response, result)

# Run Constants
###########################################################

CHANNEL_NAME = "RME_ICT_Essentials_for_Teachers"              # Name of channel
CHANNEL_SOURCE_ID = "ict-essentials"      # Channel's unique id
CHANNEL_DOMAIN = "ict-essentials-for-teachers.moodlecloud.com" # Who is providing the content
CHANNEL_LANGUAGE = "en"		# Language of channel
CHANNEL_DESCRIPTION = None                                  # Description of the channel (optional)
CHANNEL_THUMBNAIL = None                                    # Local path or url to image file (optional)
PATH = path_builder.PathBuilder(channel_name=CHANNEL_NAME)  # Keeps track of path to write to csv
WRITE_TO_PATH = "{}{}{}.zip".format(os.path.dirname(os.path.realpath(__file__)), os.path.sep, CHANNEL_NAME) # Where to generate zip file
CHANNEL_LICENSE = licenses.CC_BY_SA
CHANNEL_LICENSE_OWNER = "Ministry of Education, Rwanda"

# Additional Constants 
###########################################################
BASE_URL = "https://ict-essentials-for-teachers.moodlecloud.com/"

# Set up logging tools
LOGGER = logging.getLogger()
__logging_handler = logging.StreamHandler()
LOGGER.addHandler(__logging_handler)
LOGGER.setLevel(logging.INFO)


IMG_LOOKUP = {
        'SectionObjective.png': 'Objective', 
        'UnitSectionConclusion.png': 'Conclusion', 
        'SectionIntroduction%20%281%29.png': 'Introduction', 
        'UnitSectionConclusion%20%281%29.png': 'Conclusion',
        'SectionTime3%20%281%29.png': 'Recommended Time',
        'SectionAttribution.png': 'Attribution',
        'SectionActivity%20%281%29.png': 'Activity',
        'SectiontMethod.png': 'Method',
        'SectionIntroduction.png': 'Introduction',
        'SectionFacilitation.png': 'Facilitator\'s Welcome',
        'SectionPortfolio.png': 'Portfolio assignment',
        'SectionTime3.png': 'Recommended Time',
        'SectionActivity.png': 'Activity',
        'SectionIntroduction%20%283%29.png': 'Introduction',
        'SectionTime3%20%282%29.png': 'Recommended Time',
        'SectionIntroduction%20%282%29.png': 'Introduction',
        'UnitReferences.png': 'References',
        'SectionCompetency.png': 'Competency'
        }

if not os.path.exists("assets"):
    os.makedirs("assets")

def make_fully_qualified_url(url):
    """ Ensure url is qualified """
    if url.startswith("//"):
        return "http:" + url
    elif url.startswith("/"):
        return "http://" + CHANNEL_DOMAIN + url
    assert url.startswith("http"), "Bad URL (relative to unknown location): " + url
    return url

# Main Scraping Method 
###########################################################
def scrape_source(writer):
    """ scrape_source: Scrapes channel page and writes to a DataWriter
        Args: writer (DataWriter): class that writes data to folder/spreadsheet structure
        Returns: None
    """
    content = read(BASE_URL) 

    soup = BeautifulSoup(content, 'html.parser')
    units = get_units_from_site(soup)
    for u in units:
        LOGGER.info('{}'.format(u['name']))
        parse_unit(writer, u['name'], u['link'])

# Helper Methods 
###########################################################

# Unit-related functions
##########################
def get_units_from_site(page):
    """ 
      Get all the unit names and links from the main page
    """
    units = []
    for div in page.find_all("div", class_= "coursename"):
        link = div.find("a", text = re.compile("Unit"))
        if link:
            units.append({ 'name': link.get_text(), 'link': link.get('href')})
    return units

def parse_unit(writer, name, link):
    """ 
      Parse the elements inside a unit
      Extract sections, and each section would be an independent HTML5App
    """
    content = read(link)
    page = BeautifulSoup(content, 'html.parser')
    PATH.open_folder(folder_name(name))

    sections = page.find_all('li', id = re.compile('section-')) 
    description = description_unit(sections[0])
    recommended_time = get_recommended_time_for_section(page.find('li', id = "section-0"))
    writer.add_folder(str(PATH), name, "" + description + "Recommended time: " + str(recommended_time))
    counter = 0
    for section in sections:
        section_type = clasify_block(section) 
        if section_type == 'html':
            add_html5app(writer, section, format_section_number(counter))
        elif section_type == 'video': 
            add_video(writer, section, format_section_number(counter))
        counter += 1
    PATH.go_to_parent_folder()
    return 0

def format_section_number(number):
    return '{:02d} - '.format(number)

def get_recommended_time_for_section(section):
    img = section.find("img", src=re.compile("SectionTime"))
    if not img:
        return ""
    pattern = re.compile(".*(hour|minute|Minute)s?")
    try: 
        if pattern.match(img.get_text()):
            return img.get_text().strip()
        else:
           raise "Continue with execution"
    except:
        try: 
            if pattern.match(img.next_sibling.get_text()):
                return img.next_sibling.get_text().strip()
        except:
            try:
                if pattern.match(img.parent.next_sibling.get_text()):
                    return img.parent.next_sibling.get_text().strip()
            except:
                try:
                    if pattern.match(img.parent.parent.next_sibling.get_text()):
                        return img.parent.parent.next_sibling.get_text().strip()
                except: 
                    return ""


def description_unit(unit):
    learning_objectives = unit.find(["p", "b", "strong"], text=re.compile("Learning Objective"))
    if learning_objectives: 
        description = description_previous_sibling(learning_objectives)	
        if description: 
            return description
        description = description_parent_previous_sibling(learning_objectives)	
        if description: 
            return description
        description = description_parent_parent_previous_sibling(learning_objectives)	
        if description: 
            return description
        description = description_parent_previous_sibling_previous_sibling(learning_objectives)	
        if description: 
            return description
        description = learning_objectives.find_parent().find_previous_sibling(['div', 'p']).find_previous_sibling(['div', 'p'])
        if description and description.get_text():
            return description.get_text()
    return ""

def description_previous_sibling(learning_objectives):
    try: 
        description = learning_objectives.find_previous_sibling(['div', 'p'])
        if description and description.get_text().strip():
            return description.get_text()
    except:
        return ""

def description_parent_previous_sibling(learning_objectives):
    try:
        description = learning_objectives.find_parent().find_previous_sibling(['div', 'p'])
        if description and description.get_text():
            return description.get_text()
    except:
        return ""

def description_parent_parent_previous_sibling(learning_objectives):
    try:
        description = learning_objectives.find_parent().find_parent().find_previous_sibling(['div', 'p'])
        if description and description.get_text():
            return description.get_text()
    except: 
        return ""

def description_parent_previous_sibling_previous_sibling(learning_objectives):
    try:
        description = learning_objectives.find_previous_sibling(['div', 'p']).find_previous_sibling(['div', 'p'])
        if description and description.get_text():
            return description.get_text()
    except:
        return ""

# Generating HTML5 app
##########################

def add_video(writer, section, section_number):
    title = extract_title(section, section_number)
    video = section.find("iframe", src=re.compile("youtube"))
    video_filename = download_video(video.get('src'))
    if video_filename:
        writer.add_file(str(PATH), title, str("./") + str(video_filename), license= CHANNEL_LICENSE, copyright_holder = CHANNEL_LICENSE_OWNER)

def add_html5app(writer, section, section_number):
    title = extract_title(section, section_number)
    recommended_time = get_recommended_time_for_section(section)
    filename = generate_html5app_from_section(writer, section, section_number)
    writer.add_file(str(PATH), title, filename, license= CHANNEL_LICENSE, copyright_holder = CHANNEL_LICENSE_OWNER, ext = "")
    os.remove(filename)


def generate_html5app_from_section(writer, section, section_number):
    title = extract_title(section, section_number)
    filename = html5app_path_from_title(title)
    with HTMLWriter(filename) as html5zip:
        remove_hidden_elements(section)
        add_images_to_zip(html5zip, section)
        replace_links(writer, html5zip, section)
        content = "".join([str(x) for x in section.contents]) 
        html5zip.write_index_contents("<html><head><meta charset=\"utf-8\"></head><body>{}</body></html>".format(content))   
    return filename 

def add_images_to_zip(zipwriter, section):
    images = replace_tags_with_local_content(section)
    for image in images:
        zipwriter.write_file(image["src"])
    return 0

def remove_hidden_elements(section):
  soup = BeautifulSoup("<p></p>", 'html.parser')
  new_tag = soup.p
  spans = section.find_all('span', class_="hidden")
  for span in spans:
      span.replace_with(new_tag)
    

def replace_tags_with_local_content(section):
    images = section.find_all("img") 
    new_images = []
    for image in images:
        if is_valid_title(image):
            soup = BeautifulSoup("<h3></h3>", 'html.parser')
            new_tag = soup.h3
            new_tag.append(real_title(image))
            image.replace_with(new_tag)
        else:	
            try:
                new_images.append(image)
                relpath, _ = download_file(make_fully_qualified_url(image["src"]), "./assets")
                image["src"] = os.path.join("./assets", relpath)
            except Exception:
                image["src"] = "#"
    return new_images 

def replace_links(writer, zipwriter, section):
    links = section.find_all("a")
    for link in links:
        try:
            relpath, status = download_file(make_fully_qualified_url(link["href"]), "./files", filename=str(uuid.uuid4()))
            downloaded_file = os.path.join("./files", relpath)
            if  os.path.exists(downloaded_file)==False: raise("Error downloading file")
            if  is_valid_file(downloaded_file):
                new_file = downloaed_file + parse_extension(downloaed_file)
                os.rename(downloaded_file, new_file)
                link["href"] = new_file 
                writer.add_file(str(PATH), link.get_text().split('/')[-1], new_file, license= CHANNEL_LICENSE, copyright_holder = CHANNEL_LICENSE_OWNER, ext = "")
                zipwriter.write_file(new_file)
            elif is_convertible_file(downloaded_file):
                new_file = os.path.join("./files", str(uuid.uuid4()) + ".pdf")
                convert_file(downloaded_file, new_file)
                link["href"] = new_file 
                writer.add_file(str(PATH), link.get_text(), new_file, license= CHANNEL_LICENSE, copyright_holder = CHANNEL_LICENSE_OWNER, ext = "")
                zipwriter.write_file(new_file)
            else:
                link.replace_with(new_tag_from_link(link))
        except:
            link.replace_with(new_tag_from_link(link))
        if  os.path.exists(downloaded_file)==True: os.remove(downloaded_file)
    return 0


def new_tag_from_link(link):
    soup = BeautifulSoup("<p></p>", 'html.parser')
    new_tag = soup.p
    text = ""
    if is_a_title(link):
       text = link.get_text()
    elif link["href"] == link.get_text():
        text = link["href"]
    else:
        text = link.get_text() + ": " + link["href"]
    new_tag.append(text)
    return new_tag

def is_a_title(link):
   list_of_titles = [ 'h1', 'h2', 'h3', 'h4', 'h5' ]
   for parent in link.parents:
      if any( parent.name in s for s in list_of_titles): 
        return True 
   return False


def is_valid_file(downloaded_file):
    pattern = re.compile(".*(pdf|mp4).*")
    file_type = magic.from_file(downloaded_file, mime = True) 
    if pattern.match(file_type):
        return True
    else:
        return False 

def parse_extension(downloaded_file):
    pattern_pdf = re.compile(".*pdf.*")
    pattern_mp4= re.compile(".*pdf.*")
    file_type = magic.from_file(downloaded_file, mime = True) 
    if pattern_pdf.match(file_type): 
        return ".pdf"
    if pattern_mp4.match(file_type): 
        return ".mp4"
    return ""


def is_convertible_file(downloaded_file):
    # pattern = re.compile(".*(powerpoint|msword|openxml).*")
    # TODO: Verify why powerpoint is not loaded correctly
    pattern = re.compile(".*(msword|openxml).*")
    file_type = magic.from_file(downloaded_file, mime = True) 
    if pattern.match(file_type):
        return True
    else:
        return False 

def extract_title(section, number = ""):
    page_title = section.find("h3", class_="sectionname")
    title = "no title"
    if page_title:
        title = str(number) + page_title.get_text().replace("/","-").strip()
    return title 


def html5app_filename(title):
    return "{}.zip".format(slugify(title))

def html5app_path_from_title(title):
    new_title = title.replace("/", "-")
    return "./{}".format(html5app_filename(new_title))

def folder_name(unit_name):
    """ 
    Extract folder name from full unit name

    Example:
    Unit 01 - Example unit

    returns:
    Unit 01 
    """
    return unit_name.strip()

def clasify_block(module):
    module_type = "html"
    video = module.find("iframe", src=re.compile("youtube"))
    if video:
        module_type = "video"
    return module_type

def real_title(title):
    filename = title.get("src").split("/")[-1]
    return IMG_LOOKUP[filename]

def is_valid_title(title):
    """
    is_valid_title is true if the name of the image contains Unit or Section on it 
    but not contains Quote 
    or Method1 or Method2 
    (because they are extra images on section)
    """
    filename = title.get("src").split("/")[-1]
    try:
        title = IMG_LOOKUP[filename]
        if title:
            return True
        else:
            return False
    except: 
        return False

def download_video(url):
    ydl_options = {
	    'outtmpl': '%(title)s-%(id)s.%(ext)s',
	    'continuedl': True,
	    'quiet' : True,
	    'restrictfilenames':True, 
            'format': 'bestvideo[ext=mp4]'
	    }
    video_filename = ""
    with youtube_dl.YoutubeDL(ydl_options) as ydl:
        try:
            ydl.add_default_info_extractors()
            info = ydl.extract_info(url, download=True)
            video_filename = ydl.prepare_filename(info)
        except (youtube_dl.utils.DownloadError,youtube_dl.utils.ContentTooShortError,youtube_dl.utils.ExtractorError) as e:
            LOGGER.info('Video couldnt be downloaded: {}'.format(url))
            return "" 
    return video_filename 


""" This code will run when the sous chef is called from the command line. """
if __name__ == '__main__':

    # Open a writer to generate files
    with data_writer.DataWriter(write_to_path=WRITE_TO_PATH) as writer:

	# Write channel details to spreadsheet
        thumbnail = writer.add_file(str(PATH), "Channel Thumbnail", CHANNEL_THUMBNAIL, write_data=False)
        writer.add_channel(CHANNEL_NAME, CHANNEL_SOURCE_ID, CHANNEL_DOMAIN, CHANNEL_LANGUAGE, description=CHANNEL_DESCRIPTION, thumbnail=thumbnail)

	# Scrape source content
        scrape_source(writer)

        sys.stdout.write("\n\nDONE: Zip created at {}\n".format(writer.write_to_path))

# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
